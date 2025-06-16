import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Type, Tuple, Union # Ensure these are imported

# --- Logging Setup ---
# Get the logger for this module. Handlers will be configured by main.py
logger = logging.getLogger(__name__)
# Set level for this logger; main.py's root logger configuration will usually override/filter this.
#logger.setLevel(logging.INFO)


class BaseForecastingModel(ABC):
    """
    Abstract Base Class for all pluggable forecasting models.
    All concrete models must inherit from this class and implement its methods.
    """
    def __init__(self, model_name: str):
        self.model_name = model_name
        logger.info(f"Initialized BaseForecastingModel: {self.model_name}")

    @abstractmethod
    def train(self, historical_data: List[Dict[str, Any]]):
        """
        Trains the forecasting model using historical data.

        Args:
            historical_data (List[Dict[str, Any]]): A list of dictionaries,
                                                     each representing a meter reading.
                                                     Expected keys: 'timestamp', 'energy_kwh_import'.
                                                     The data is assumed to be sorted by timestamp.
        """
        pass

    @abstractmethod
    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
        """
        Generates energy consumption predictions for a specified future time range.

        Args:
            start_timestamp (datetime): The starting timestamp for predictions.
            end_timestamp (datetime): The ending timestamp for predictions.
            frequency (timedelta): The interval between predictions (e.g., 15 minutes).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each with 'timestamp' and 'predicted_kwh'.
        """
        pass

    def get_model_name(self) -> str:
        """Returns the name of the forecasting model."""
        return self.model_name

def load_forecasting_model(model_name: str) -> BaseForecastingModel:
    """
    Dynamically loads a forecasting model from the 'models' directory.

    Args:
        model_name (str): The name of the model to load (e.g., "baseline_model").
                          Assumes the model file is 'model_name.py' and the
                          main class is 'ModelNameModel' (CamelCase).

    Returns:
        BaseForecastingModel: An instance of the requested forecasting model.

    Raises:
        ValueError: If the model cannot be found or loaded.
    """
    try:
        # Construct the module path dynamically
        # Example: model_name="baseline_model" -> module_path="src.models.baseline_model"
        module_path = f"src.models.{model_name}"

        # Import the module. The fromlist is important for __import__ to return the module itself.
        module = __import__(module_path, fromlist=[model_name])

        # Convention: Class name is CamelCase of the file name + "Model"
        # e.g., baseline_model.py -> BaselineModel
        class_name = ''.join(word.capitalize() for word in model_name.split('_')) + 'Model'
        model_class: Type[BaseForecastingModel] = getattr(module, class_name)

        # Instantiate and return the model
        logger.info(f"Successfully loaded forecasting model: {class_name} from {module_path}")
        return model_class() # Models will internally set their name via super().__init__(model_name)

    except (ImportError, AttributeError) as e:
        logger.error(f"Could not load forecasting model '{model_name}'. "
                     f"Ensure '{model_name}.py' exists in 'src/models/' "
                     f"and contains a class named '{class_name}': {e}", exc_info=True)
        raise ValueError(f"Forecasting model '{model_name}' not found or incorrectly implemented.")
    except Exception as e:
        logger.error(f"An unexpected error occurred while loading model '{model_name}': {e}", exc_info=True)
        raise

def calculate_forecast_metrics(actuals: List[Dict[str, Any]], predictions: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculates Mean Absolute Error (MAE) and Root Mean Squared Error (RMSE)
    between actual and predicted values. Assumes inputs are sorted by timestamp
    and contain 'timestamp' and corresponding value keys.

    Args:
        actuals (List[Dict[str, Any]]): List of dicts with 'timestamp' and 'energy_kwh_import'.
        predictions (List[Dict[str, Any]]): List of dicts with 'timestamp' and 'predicted_kwh'.

    Returns:
        Dict[str, float]: A dictionary containing 'mae' and 'rmse'.
                          Returns NaN if no overlapping data points.
    """
    actual_map = {a['timestamp']: a['energy_kwh_import'] for a in actuals}
    aligned_predictions = []
    aligned_actuals = []

    # Iterate through predictions and find corresponding actuals
    for p in predictions:
        if p['timestamp'] in actual_map:
            aligned_predictions.append(p['predicted_kwh'])
            aligned_actuals.append(actual_map[p['timestamp']])

    if not aligned_actuals:
        logger.warning("No overlapping timestamps between actuals and predictions for metric calculation.")
        return {"mae": float('nan'), "rmse": float('nan')}

    # Calculate errors
    errors = [float(a) - float(p) for a, p in zip(aligned_actuals, aligned_predictions)] # Cast to float for math
    abs_errors = [abs(e) for e in errors]
    squared_errors = [e**2 for e in errors]

    # Calculate MAE
    mae = sum(abs_errors) / len(abs_errors) if abs_errors else float('nan')
    # Calculate RMSE
    rmse = (sum(squared_errors) / len(squared_errors))**0.5 if squared_errors else float('nan')

    logger.info(f"Calculated metrics: MAE={mae:.2f}, RMSE={rmse:.2f} (from {len(aligned_actuals)} points).")
    return {"mae": mae, "rmse": rmse}


if __name__ == '__main__':
    # This block is for testing the forecasting_engine component in isolation.
    # It won't run when imported by other modules, as __name__ will not be '__main__'.

    # For standalone testing, a basic logging setup is needed.
    # In full application, main.py configures global logging.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- Testing Forecasting Engine Component (Standalone) ---")

    # Define a mock BaselineModel for testing purposes,
    # as the actual model might not be importable directly
    # if this file is run standalone and not as part of the src package.
    # When digital_twin.py calls load_forecasting_model, it will load the real one.
    class MockBaselineModel(BaseForecastingModel):
        def __init__(self):
            super().__init__("mock_baseline_model_for_test")
            self.trained_data_points = 0
            self.simulated_last_kwh = 0.0

        def train(self, historical_data: List[Dict[str, Any]]):
            self.trained_data_points = len(historical_data)
            if historical_data:
                # Get the last kWh value from historical data for mock prediction
                self.simulated_last_kwh = historical_data[-1].get('energy_kwh_import', 0.0)
            logger.info(f"MockBaselineModel trained with {self.trained_data_points} data points.")

        def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                    frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
            logger.info(f"MockBaselineModel predicting from {start_timestamp} to {end_timestamp} with {frequency} freq.")
            predictions = []
            current_time = start_timestamp
            # Simple mock prediction: predict the last known kWh from training
            while current_time < end_timestamp:
                predictions.append({
                    'timestamp': current_time,
                    'predicted_kwh': float(self.simulated_last_kwh) # Ensure float
                })
                current_time += frequency
            return predictions

    # Test calculate_forecast_metrics
    actual_data = [
        {'timestamp': datetime(2025, 6, 11, 0, 0), 'energy_kwh_import': 95.0},
        {'timestamp': datetime(2025, 6, 11, 0, 15), 'energy_kwh_import': 105.0},
        {'timestamp': datetime(2025, 6, 11, 0, 30), 'energy_kwh_import': 110.0},
        {'timestamp': datetime(2025, 6, 11, 0, 45), 'energy_kwh_import': 100.0}
    ]
    prediction_data = [
        {'timestamp': datetime(2025, 6, 11, 0, 0), 'predicted_kwh': 100.0},
        {'timestamp': datetime(2025, 6, 11, 0, 15), 'predicted_kwh': 100.0},
        {'timestamp': datetime(2025, 6, 11, 0, 30), 'predicted_kwh': 100.0},
        {'timestamp': datetime(2025, 6, 11, 0, 45), 'predicted_kwh': 100.0}
    ]
    metrics = calculate_forecast_metrics(actual_data, prediction_data)
    logger.info(f"Test Metrics: {metrics}")

    # Test with no overlapping data
    no_overlap_actuals = [{'timestamp': datetime(2025, 6, 12, 0, 0), 'energy_kwh_import': 50.0}]
    no_overlap_predictions = [{'timestamp': datetime(2025, 6, 13, 0, 0), 'predicted_kwh': 50.0}]
    no_overlap_metrics = calculate_forecast_metrics(no_overlap_actuals, no_overlap_predictions)
    logger.info(f"Test No Overlap Metrics: {no_overlap_metrics}")

    # Test load_forecasting_model (requires src/models/baseline_model.py to exist and be correct)
    try:
        # Temporarily register the MockBaselineModel in sys.modules
        # so load_forecasting_model can find it during this test
        import sys
        sys.modules['src.models.mock_baseline_model_for_test'] = sys.modules['__main__']
        setattr(sys.modules['__main__'], 'MockBaselineModel', MockBaselineModel)

        # Now try to load the mock model using the function
        loaded_mock_model = load_forecasting_model("mock_baseline_model_for_test")
        logger.info(f"Successfully loaded mock model for test: {loaded_mock_model.get_model_name()}")

        # Clean up sys.modules after test
        del sys.modules['src.models.mock_baseline_model_for_test']
        delattr(sys.modules['__main__'], 'MockBaselineModel')

    except ValueError as e:
        logger.error(f"Failed to load mock model via load_forecasting_model: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during load_forecasting_model test: {e}")