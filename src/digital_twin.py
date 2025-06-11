import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import uuid # Import uuid for generating and handling UUIDs

# Assuming db_manager and forecasting_engine are in src/
from . import db_manager
from .forecasting_engine import BaseForecastingModel, load_forecasting_model, calculate_forecast_metrics

# # --- Logging Setup ---
# log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
# os.makedirs(log_dir, exist_ok=True)
# log_file = os.path.join(log_dir, 'digital_twin.log')

logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)

# # Ensure handlers are not duplicated
# if not logger.handlers:
#     fh = logging.FileHandler(log_file)
#     fh.setLevel(logging.INFO)
#     ch = logging.StreamHandler()
#     ch.setLevel(logging.INFO)
#     formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     fh.setFormatter(formatter)
#     ch.setFormatter(formatter)
#     logger.addHandler(fh)
#     logger.addHandler(ch)

class DigitalTwin:
    """
    The core simulation engine for the digital twin.
    Manages virtual meter representations, retrieves real data,
    applies forecasting models, and runs demand simulations.
    """
    def __init__(self, meter_id: str): # Changed to str as meter_id is VARCHAR(50)
        self.meter_id = meter_id
        self.forecasting_model: Optional[BaseForecastingModel] = None
        self.latest_real_reading: Optional[Dict[str, Any]] = None
        logger.info(f"DigitalTwin initialized for Meter ID: {self.meter_id}")

    def load_model(self, model_name: str):
        """Loads a specific forecasting model into the digital twin."""
        try:
            self.forecasting_model = load_forecasting_model(model_name)
            logger.info(f"Forecasting model '{model_name}' loaded for Meter {self.meter_id}.")
        except ValueError as e:
            logger.error(f"Failed to load model for Meter {self.meter_id}: {e}")
            raise

    def get_latest_real_reading(self) -> Optional[Dict[str, Any]]:
        """Retrieves the latest real meter reading from the database."""
        logger.info(f"Fetching latest real reading for Meter {self.meter_id}...")
        try:
            latest_reading = db_manager.get_latest_meter_reading(self.meter_id)
            if latest_reading:
                self.latest_real_reading = latest_reading
                logger.info(f"Latest real reading for Meter {self.meter_id}: {latest_reading.get('energy_kwh_import')} kWh at {latest_reading.get('timestamp')}")
                return latest_reading
            else:
                logger.warning(f"No real readings found for Meter {self.meter_id} in the database.")
                return None
        except Exception as e:
            logger.error(f"Error fetching latest real reading for Meter {self.meter_id}: {e}", exc_info=True)
            return None

    def get_historical_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Retrieves historical data for training models or analysis.
        Args:
            hours (int): Number of hours of historical data to retrieve.
        Returns:
            List[Dict[str, Any]]: List of historical meter readings.
        """
        # Ensure consistent timezone for comparison
        end_time = datetime.now(db_manager.get_timezone()).replace(second=0, microsecond=0)
        start_time = end_time - timedelta(hours=hours)
        logger.info(f"Fetching {hours} hours of historical data for Meter {self.meter_id} from {start_time} to {end_time}...")
        try:
            historical_data = db_manager.get_meter_readings_in_range(self.meter_id, start_time, end_time)
            logger.info(f"Retrieved {len(historical_data)} historical data points for Meter {self.meter_id}.")
            return historical_data
        except Exception as e:
            logger.error(f"Error fetching historical data for Meter {self.meter_id}: {e}", exc_info=True)
            return []

    def run_simulation(self,
                       simulation_duration_hours: int = 24,
                       prediction_horizon_hours: int = 24,
                       model_name: str = "baseline_model",
                       data_for_training_hours: int = 24) -> Dict[str, Any]:
        """
        Runs a simulation of energy demand for the digital twin.

        Args:
            simulation_duration_hours (int): The total duration of the simulation in hours.
                                             This defines the time range for which the twin
                                             will generate predicted/simulated data.
            prediction_horizon_hours (int): How far into the future the model predicts.
                                            This is typically the same as simulation_duration_hours
                                            for continuous simulation, or shorter if you want
                                            to simulate a longer period using iterative predictions.
            model_name (str): The name of the forecasting model to use.
            data_for_training_hours (int): How many hours of recent historical data
                                           to fetch for training the model before simulation.

        Returns:
            Dict[str, Any]: Contains simulated data, actual data (if available in the simulation range),
                            forecasts, and accuracy metrics.
        """
        if not self.forecasting_model or self.forecasting_model.get_model_name() != model_name:
            self.load_model(model_name)

        if not self.forecasting_model:
            logger.error("No forecasting model loaded. Cannot run simulation.")
            return {}

        logger.info(f"Running digital twin simulation for Meter {self.meter_id} using {model_name} model...")

        # 1. Get historical data for model training
        historical_data = self.get_historical_data(hours=data_for_training_hours)
        if not historical_data:
            logger.warning(f"Not enough historical data to train model for Meter {self.meter_id}. Trying to get latest reading only.")
            self.get_latest_real_reading() # Try to get latest even if historical is empty


        # 2. Train the model
        try:
            self.forecasting_model.train(historical_data)
            training_data_start = historical_data[0]['timestamp'] if historical_data else None
            training_data_end = historical_data[-1]['timestamp'] if historical_data else None
        except Exception as e:
            logger.error(f"Error during model training for Meter {self.meter_id}: {e}", exc_info=True)
            return {}

        # 3. Define simulation time window
        # Get the latest timestamp from historical data to set the prediction start point
        # If no historical data, start from current time.
        if historical_data:
            sorted_historical = sorted(historical_data, key=lambda x: x['timestamp'])
            last_historical_timestamp = sorted_historical[-1]['timestamp']
            # Start prediction *after* the last historical point, aligning to 15-min intervals
            prediction_start_time = last_historical_timestamp + timedelta(minutes=15)
        elif self.latest_real_reading:
            prediction_start_time = self.latest_real_reading['timestamp'] + timedelta(minutes=15)
        else:
            # Fallback: start from current time, rounded up to the next 15-min interval
            now_tz = datetime.now(db_manager.get_timezone()).replace(second=0, microsecond=0)
            minutes_to_next_quarter = 15 - (now_tz.minute % 15)
            if minutes_to_next_quarter == 15: # If it's already on the quarter, use current time
                prediction_start_time = now_tz
            else:
                prediction_start_time = now_tz + timedelta(minutes=minutes_to_next_quarter)
            logger.warning(f"No historical or latest real data. Starting prediction from current time: {prediction_start_time}")


        prediction_end_time = prediction_start_time + timedelta(hours=prediction_horizon_hours)

        # Ensure start time is before end time
        if prediction_start_time >= prediction_end_time:
            logger.error("Prediction start time is on or after end time. Adjusting end time to be at least 15 min after start.")
            prediction_end_time = prediction_start_time + timedelta(minutes=15) # Ensure at least one prediction point

        # 4. Record the forecast run before predictions
        current_run_id = None
        try:
            current_run_id = db_manager.insert_forecast_run(
                meter_id=self.meter_id,
                model_name=model_name,
                prediction_start_time=prediction_start_time,
                prediction_end_time=prediction_end_time,
                training_data_start=training_data_start,
                training_data_end=training_data_end,
                mae=None, # Temporarily None, updated after calculation
                rmse=None # Temporarily None, updated after calculation
            )
            logger.info(f"New forecast run initiated with ID: {current_run_id}")
        except Exception as e:
            logger.error(f"Failed to record forecast run in DB: {e}", exc_info=True)
            # Decide if you want to stop here or continue without recording the run
            # For robustness, we'll continue, but without DB persistence for this run.

        # 5. Generate forecasts (these are the simulated readings)
        simulated_readings_output = self.forecasting_model.predict(
            start_timestamp=prediction_start_time,
            end_timestamp=prediction_end_time,
            frequency=timedelta(minutes=15) # Assuming 15-min intervals
        )
        logger.info(f"Generated {len(simulated_readings_output)} simulated readings.")

        # 6. Fetch actuals for the simulation period for comparison (if overlap)
        actuals_in_simulation_range = db_manager.get_meter_readings_in_range(
            self.meter_id, prediction_start_time, prediction_end_time
        )
        logger.info(f"Retrieved {len(actuals_in_simulation_range)} actual readings within the simulation range for comparison.")

        # 7. Calculate performance metrics (only if actuals and predictions overlap)
        metrics = calculate_forecast_metrics(actuals_in_simulation_range, simulated_readings_output)

        # 8. Store forecast predictions and update run metrics
        if current_run_id:
            predictions_to_store = []
            # Map actual_kwh to predictions for storage
            actual_map = {a['timestamp']: a['energy_kwh_import'] for a in actuals_in_simulation_range}
            for pred in simulated_readings_output:
                predictions_to_store.append({
                    'timestamp': pred['timestamp'],
                    'predicted_kwh': pred['predicted_kwh'],
                    'actual_kwh': actual_map.get(pred['timestamp']) # Add actual if available for that timestamp
                })
            try:
                db_manager.insert_forecast_predictions(current_run_id, predictions_to_store)
                logger.info(f"Stored {len(predictions_to_store)} forecast predictions for run_id {current_run_id}.")
                db_manager.update_forecast_run_metrics(current_run_id, mae=metrics.get('mae'), rmse=metrics.get('rmse'))
                logger.info(f"Updated metrics for forecast run_id {current_run_id}.")
            except Exception as e:
                logger.error(f"Failed to store predictions or update metrics for run_id {current_run_id}: {e}", exc_info=True)


        return {
            "meter_id": self.meter_id,
            "model_used": model_name,
            "simulation_start": prediction_start_time,
            "simulation_end": prediction_end_time,
            "simulated_readings": simulated_readings_output, # These are the forecast-driven readings
            "actual_readings_in_sim_range": actuals_in_simulation_range, # Real data for comparison
            "metrics": metrics,
            "run_id": current_run_id # Include the run_id in the returned results
        }


if __name__ == '__main__':
    # For standalone testing, a basic logging setup is needed if main.py isn't running.
    # This ensures logs appear if you run this file directly.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # This block is for testing the DigitalTwin in isolation.
    logger.info("--- Testing Digital Twin Component ---")

    # Mock db_manager functions for isolated testing
    class MockDBManager:
        def get_latest_meter_reading(self, meter_id: str):
            # Simulate a latest reading
            # Ensure it's timezone aware. Adjust timestamp to be relevant to current time.
            return {'timestamp': datetime.now(timezone(timedelta(hours=5, minutes=30))) - timedelta(minutes=15),
                    'energy_kwh_import': 58.0}

        def get_meter_readings_in_range(self, meter_id: str, start_time: datetime, end_time: datetime):
            # Simulate some historical data within the last hour for testing
            # Ensure timestamps are timezone aware for consistency
            now_tz = datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(second=0, microsecond=0)
            data = [
                {'timestamp': now_tz - timedelta(minutes=45), 'energy_kwh_import': 50.0},
                {'timestamp': now_tz - timedelta(minutes=30), 'energy_kwh_import': 55.0},
                {'timestamp': now_tz - timedelta(minutes=15), 'energy_kwh_import': 60.0},
                {'timestamp': now_tz, 'energy_kwh_import': 58.0}
            ]
            # Filter based on range
            return [d for d in data if start_time <= d['timestamp'] <= end_time]

        def get_timezone(self):
            return timezone(timedelta(hours=5, minutes=30)) # IST for Jaipur

        def insert_forecast_run(self, meter_id, model_name, prediction_start_time, prediction_end_time,
                                training_data_start, training_data_end, mae, rmse): # Added mae, rmse
            _run_id = uuid.uuid4()
            logger.info(f"MOCKED: Inserted forecast run {_run_id} with MAE={mae}, RMSE={rmse}")
            return _run_id

        def insert_forecast_predictions(self, run_id, predictions_data):
            logger.info(f"MOCKED: Inserted {len(predictions_data)} predictions for run {run_id}")

        def update_forecast_run_metrics(self, run_id, mae, rmse):
            logger.info(f"MOCKED: Updated metrics for run {run_id} (MAE: {mae}, RMSE: {rmse})")


    # Temporarily replace db_manager with our mock for testing purposes
    original_db_manager_get_latest = db_manager.get_latest_meter_reading
    original_db_manager_get_range = db_manager.get_meter_readings_in_range
    original_db_manager_get_timezone = db_manager.get_timezone
    original_db_manager_insert_run = db_manager.insert_forecast_run
    original_db_manager_insert_predictions = db_manager.insert_forecast_predictions
    original_db_manager_update_metrics = db_manager.update_forecast_run_metrics

    # Patch the functions directly in the module imported by DigitalTwin
    db_manager.get_latest_meter_reading = MockDBManager().get_latest_meter_reading
    db_manager.get_meter_readings_in_range = MockDBManager().get_meter_readings_in_range
    db_manager.get_timezone = MockDBManager().get_timezone
    db_manager.insert_forecast_run = MockDBManager().insert_forecast_run
    db_manager.insert_forecast_predictions = MockDBManager().insert_forecast_predictions
    db_manager.update_forecast_run_metrics = MockDBManager().update_forecast_run_metrics

    try:
        meter_id = "TEST_METER_001" # Ensure this matches your db_manager test if you ran it
        twin = DigitalTwin(meter_id=meter_id)

        # Test loading a model (requires baseline_model.py to be present)
        twin.load_model("baseline_model") # This should now load the actual BaselineModelModel class

        # Test fetching latest real reading
        latest_reading = twin.get_latest_real_reading()
        if latest_reading:
            logger.info(f"Latest real reading (from mock): {latest_reading.get('energy_kwh_import')} at {latest_reading.get('timestamp')}")

        # Test fetching historical data
        historical_data_fetched = twin.get_historical_data(hours=1)
        logger.info(f"Historical data fetched (from mock): {len(historical_data_fetched)} points.")

        # Test running a simulation
        simulation_results = twin.run_simulation(
            simulation_duration_hours=1,
            prediction_horizon_hours=1,
            model_name="baseline_model",
            data_for_training_hours=1
        )

        logger.info("\n--- Simulation Summary ---")
        logger.info(f"Meter ID: {simulation_results.get('meter_id')}")
        logger.info(f"Model Used: {simulation_results.get('model_used')}")
        logger.info(f"Simulation Period: {simulation_results.get('simulation_start')} to {simulation_results.get('simulation_end')}")
        logger.info(f"Total Simulated Points: {len(simulation_results.get('simulated_readings', []))}")
        logger.info(f"Forecast Run ID: {simulation_results.get('run_id')}")

        metrics = simulation_results.get('metrics')
        if metrics:
            logger.info(f"Performance Metrics: MAE={metrics.get('mae'):.2f}, RMSE={metrics.get('rmse'):.2f}")
        else:
            logging.warning("No metrics calculated (likely no overlapping actual data for comparison).")

    except Exception as e:
        logger.error(f"Error during DigitalTwin test: {e}", exc_info=True)
    finally:
        # Restore original db_manager functions after testing
        db_manager.get_latest_meter_reading = original_db_manager_get_latest
        db_manager.get_meter_readings_in_range = original_db_manager_get_range
        db_manager.get_timezone = original_db_manager_get_timezone
        db_manager.insert_forecast_run = original_db_manager_insert_run
        db_manager.insert_forecast_predictions = original_db_manager_insert_predictions
        db_manager.update_forecast_run_metrics = original_db_manager_update_metrics