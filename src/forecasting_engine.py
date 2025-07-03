import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Type, Tuple, Union # Ensure these are imported
from src.models.base_model import BaseForecastingModel

# --- Logging Setup ---
# Get the logger for this module. Handlers will be configured by main.py
logger = logging.getLogger(__name__)
# Set level for this logger; main.py's root logger configuration will usually override/filter this.
#logger.setLevel(logging.INFO)


# In src/forecasting_engine.py

import importlib
import logging
from typing import Dict, List, Any, Type

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from src.models.base_model import BaseForecastingModel

logger = logging.getLogger(__name__)


def load_forecasting_model(model_name: str) -> BaseForecastingModel:
    """
    Dynamically imports and instantiates a forecasting model from the src/models directory.

    Args:
        model_name (str): The underscore-separated name of the model file
                          (e.g., 'baseline_model', 'dl_model').

    Returns:
        An instance of the requested forecasting model.
    
    Raises:
        ValueError: If the model module or class cannot be found.
    """
    try:
        # --- THIS IS THE LOGIC TO FIX ---
        
        # Convert snake_case (e.g., 'baseline_model') to CamelCase (e.g., 'BaselineModel')
        # 1. Split the string by underscores: ['baseline', 'model']
        # 2. Capitalize each part: ['Baseline', 'Model']
        # 3. Join them together: 'BaselineModel'
        
        # OLD LOGIC (likely hardcoded or incorrect):
        # class_name = model_name.replace('_', ' ').title().replace(' ', '') + "Model" 
        # For 'baseline_model', this produces 'BaselineModelModel', which is wrong.

        # NEW, CORRECT LOGIC:
        class_name = "".join(word.capitalize() for word in model_name.split('_'))
        
        # Dynamically import the module (e.g., src.models.baseline_model)
        module_path = f"src.models.{model_name}"
        module = importlib.import_module(module_path)
        
        # Get the class from the imported module
        model_class: Type[BaseForecastingModel] = getattr(module, class_name)
        
        # Instantiate and return the model class
        logger.info(f"Successfully loaded and instantiated model '{class_name}' from '{module_path}'.")
        return model_class()

    except ImportError:
        logger.error(f"Could not import module for model '{model_name}'. Ensure '{model_name}.py' exists in 'src/models/'.", exc_info=True)
        raise ValueError(f"Forecasting model '{model_name}' not found or incorrectly implemented.")
    except AttributeError:
        logger.error(
            f"Could not load forecasting model '{model_name}'. "
            f"Ensure '{model_name}.py' exists in 'src/models/' and contains a class named '{class_name}'",
            exc_info=True
        )
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