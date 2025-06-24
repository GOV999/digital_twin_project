import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Import the abstract base class from forecasting_engine
# Use absolute import here for clarity as this module is part of the 'src' package
from src.forecasting_engine import BaseForecastingModel

# --- Logging Setup ---
# Get the logger for this module. Handlers will be configured by main.py
logger = logging.getLogger(__name__)
# Set level for this logger; main.py's root logger configuration will usually override/filter this.
#logger.setLevel(logging.INFO)


class BaselineModelModel(BaseForecastingModel): # This class name is crucial for the loader
    """
    A simple baseline forecasting model.
    Predicts the last known `energy_kwh_import` value for all future timestamps.
    """
    def __init__(self):
        # Call the base class constructor with the model's name
        super().__init__("baseline_model")
        self.last_known_kwh = None
        self.trained_last_timestamp = None
        logger.info(f"Initialized {self.get_model_name()} ({type(self).__name__}).")

    def train(self, historical_data: List[Dict[str, Any]]):
        """
        Trains the baseline model. For this model, training simply means
        storing the latest historical energy_kwh_import value.

        Args:
            historical_data (List[Dict[str, Any]]): A list of dictionaries,
                                                     each representing a meter reading.
                                                     Expected keys: 'timestamp', 'energy_kwh_import'.
        """
        if not historical_data:
            logger.warning(f"No historical data provided for {self.get_model_name()} training.")
            self.last_known_kwh = None
            self.trained_last_timestamp = None
            return

        # Sort data by timestamp to get the truly last known value
        # Ensure timestamps are comparable (all timezone-aware or all naive)
        sorted_data = sorted(historical_data, key=lambda x: x['timestamp'], reverse=True)
        latest_reading = sorted_data[0]

        self.last_known_kwh = latest_reading.get('energy_kwh_import')
        self.trained_last_timestamp = latest_reading.get('timestamp')
        logger.info(f"{self.get_model_name()} trained. Last known kWh: {self.last_known_kwh} at {self.trained_last_timestamp}")


    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
        """
        Generates energy consumption predictions.
        This baseline model predicts the `last_known_kwh` for all future points.

        Args:
            start_timestamp (datetime): The starting timestamp for predictions.
            end_timestamp (datetime): The ending timestamp for predictions.
            frequency (timedelta): The interval between predictions (e.g., 15 minutes).

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, each with 'timestamp' and 'predicted_kwh'.
        """
        if self.last_known_kwh is None:
            logger.warning(f"{self.get_model_name()} not trained or no last known kWh value. Returning empty predictions.")
            return []

        predictions = []
        current_time = start_timestamp
        while current_time < end_timestamp:
            predictions.append({
                'timestamp': current_time,
                'predicted_kwh': float(self.last_known_kwh) # Ensure prediction is a float
            })
            current_time += frequency
        
        logger.info(f"{self.get_model_name()} generated {len(predictions)} predictions from {start_timestamp} to {end_timestamp}.")
        return predictions


if __name__ == '__main__':
    # This block is for testing the BaselineModel in isolation.
    # For standalone testing, a basic logging setup is needed.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- Testing Baseline Model Component (Standalone) ---")

    model = BaselineModelModel() # Instantiate the correct class name for the test

    # Test training with sample data
    sample_data = [
        {'timestamp': datetime(2025, 6, 11, 8, 0), 'energy_kwh_import': 50.0},
        {'timestamp': datetime(2025, 6, 11, 8, 15), 'energy_kwh_import': 55.0},
        {'timestamp': datetime(2025, 6, 11, 8, 30), 'energy_kwh_import': 60.0},
        {'timestamp': datetime(2025, 6, 11, 8, 45), 'energy_kwh_import': 58.0}
    ]
    model.train(sample_data)
    logger.info(f"Model's last known kWh after training: {model.last_known_kwh}")

    # Test prediction
    prediction_start = datetime(2025, 6, 11, 9, 0)
    prediction_end = datetime(2025, 6, 11, 10, 0) # 1 hour prediction (4 points)
    forecasts = model.predict(prediction_start, prediction_end)

    logger.info("Generated Forecasts:")
    for f in forecasts:
        logger.info(f"  {f['timestamp']}: {f['predicted_kwh']:.2f} kWh")

    # Test with no historical data
    model_no_data = BaselineModelModel() # Instantiate the correct class name
    model_no_data.train([])
    forecasts_no_data = model_no_data.predict(prediction_start, prediction_end)
    logger.info(f"Forecasts with no training data: {forecasts_no_data}")