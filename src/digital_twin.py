import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import uuid

# Assuming db_manager and forecasting_engine are in src/
from . import db_manager
from .forecasting_engine import BaseForecastingModel, load_forecasting_model, calculate_forecast_metrics

logger = logging.getLogger(__name__)

class DigitalTwin:
    """
    The core simulation engine for the digital twin.
    Manages virtual meter representations, retrieves real data,
    applies forecasting models, and runs demand simulations.
    """
    def __init__(self, meter_id: str):
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
            latest_readings = db_manager.get_latest_meter_readings_by_limit(self.meter_id, 1)
            if latest_readings:
                self.latest_real_reading = latest_readings[0]
                logger.info(f"Latest real reading for Meter {self.meter_id}: {self.latest_real_reading.get('energy_kwh_import')} kWh at {self.latest_real_reading.get('timestamp')}")
                return self.latest_real_reading
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

    # In src/digital_twin.py

    def run_simulation(self,
                   model_name: str,
                   data_for_training_hours: int,
                   simulation_duration_hours: int = 24,
                   prediction_horizon_hours: int = 24,
                   event_data: Optional[Dict[str, Any]] = None,
                   explicit_prediction_start_time: Optional[datetime] = None,
                   explicit_prediction_end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Runs a comprehensive simulation of energy demand.

        This method can perform two types of simulations:
        1. Standard Forecast: Predicts future consumption from the latest data point.
        2. Event Simulation/Backtest: Simulates a past period with an optional
        event (e.g., a heatwave) to test model performance under what-if scenarios.

        It includes graceful fallback to a baseline model if data requirements for
        a complex model are not met.

        Args:
            model_name (str): The name of the forecasting model to use.
            data_for_training_hours (int): Hours of historical data for training.
            simulation_duration_hours (int): Duration for a standard forecast.
            prediction_horizon_hours (int): How far to predict in a standard forecast.
            event_data (Optional[Dict]): An optional dictionary describing a simulated event.
                                        e.g., {'type': 'heatwave', 'value': 5}
            explicit_prediction_start_time (Optional[datetime]): The start time for a backtest.
            explicit_prediction_end_time (Optional[datetime]): The end time for a backtest.

        Returns:
            A dictionary containing the full results of the simulation.
        """
        if event_data:
            logger.info(f"Starting EVENT simulation for Meter {self.meter_id} | Model: '{model_name}' | Event: {event_data}")
        else:
            logger.info(f"Starting simulation for Meter {self.meter_id} | Model: '{model_name}'")

        # 1. FETCH HISTORICAL DATA
        historical_data = self.get_historical_data(hours=data_for_training_hours)
        if not historical_data:
            # It's impossible to run any meaningful simulation without some data.
            raise ValueError("Not enough historical data to run a simulation. Please scrape more data first.")

        # 2. DECIDE WHICH MODEL TO USE (GRACEFUL FALLBACK)
        model_to_use = model_name
        fallback_reason = None
        try:
            requested_model_instance = load_forecasting_model(model_name)
            required_records = requested_model_instance.get_required_history_count()
            if len(historical_data) < required_records:
                fallback_reason = (f"Insufficient data for '{model_name}' (had {len(historical_data)} of {required_records} required). Used baseline instead.")
                logger.warning(fallback_reason)
                model_to_use = "baseline_model"
        except Exception as e:
            fallback_reason = f"Could not load requested model '{model_name}'. Used baseline instead. Error: {e}"
            logger.error(fallback_reason, exc_info=True)
            model_to_use = "baseline_model"

        # 3. LOAD & TRAIN THE FINAL MODEL
        # Pass params to load_model if we add hyperparameter tuning back in the future.
        self.load_model(model_to_use) 
        if not self.forecasting_model:
            raise RuntimeError("Fatal: Could not load any forecasting model, including the baseline.")
        
        # Pass event data to the training step. This is crucial for events that modify 'kwh'.
        self.forecasting_model.train(historical_data, event_data=event_data)
        training_data_start = historical_data[0]['timestamp']
        training_data_end = historical_data[-1]['timestamp']

        # 4. DEFINE SIMULATION TIME WINDOW
        if explicit_prediction_start_time and explicit_prediction_end_time:
            prediction_start_time = explicit_prediction_start_time
            prediction_end_time = explicit_prediction_end_time
            logger.info(f"Using explicit backtest window: {prediction_start_time} to {prediction_end_time}")
        else:
            # Standard forecast logic
            last_historical_timestamp = max(d['timestamp'] for d in historical_data)
            prediction_start_time = last_historical_timestamp + timedelta(minutes=15)
            prediction_end_time = prediction_start_time + timedelta(hours=prediction_horizon_hours)
            logger.info(f"Inferred forecast window: {prediction_start_time} to {prediction_end_time}")

        if prediction_start_time >= prediction_end_time:
            raise ValueError("Prediction start time cannot be on or after the end time.")

        # 5. RECORD THE FORECAST RUN
        current_run_id = str(uuid.uuid4())
        db_manager.insert_forecast_run(
            run_id=current_run_id, meter_id=self.meter_id, model_name=model_to_use,
            prediction_start_time=prediction_start_time, prediction_end_time=prediction_end_time,
            training_data_start=training_data_start, training_data_end=training_data_end
        )
        logger.info(f"New forecast run initiated with ID: {current_run_id}")

        # 6. GENERATE FORECASTS
        simulated_readings_output = self.forecasting_model.predict(
            start_timestamp=prediction_start_time,
            end_timestamp=prediction_end_time,
            historical_data=historical_data,
            frequency=timedelta(minutes=30),
            event_data=event_data # Pass event data to the prediction step
        )
        logger.info(f"Generated {len(simulated_readings_output)} simulated readings.")

        # 7. EVALUATE & STORE RESULTS
        actuals_in_simulation_range = db_manager.get_meter_readings_in_range(
            self.meter_id, prediction_start_time, prediction_end_time
        )
        metrics = calculate_forecast_metrics(actuals_in_simulation_range, simulated_readings_output)
        
        predictions_to_store = []
        actual_map = {a['timestamp']: a['energy_kwh_import'] for a in actuals_in_simulation_range}
        for pred in simulated_readings_output:
            predictions_to_store.append({
                'timestamp': pred['timestamp'],
                'predicted_kwh': pred['predicted_kwh'],
                'actual_kwh': actual_map.get(pred['timestamp'])
            })
        
        db_manager.insert_forecast_predictions(current_run_id, predictions_to_store)
        if metrics.get('mae') is not None:
            db_manager.update_forecast_run_metrics(current_run_id, mae=metrics.get('mae'), rmse=metrics.get('rmse'))

        # 8. RETURN COMPLETE RESULTS
        return {
            "meter_id": self.meter_id,
            "model_requested": model_name,
            "model_used": model_to_use,
            "fallback_reason": fallback_reason,
            "simulation_start": prediction_start_time,
            "simulation_end": prediction_end_time,
            "simulated_readings": simulated_readings_output,
            "actual_readings_in_sim_range": actuals_in_simulation_range,
            "metrics": metrics,
            "run_id": current_run_id
        }


if __name__ == '__main__':
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- Testing Digital Twin Component with REAL DB Manager ---")

    try:
        db_manager.initialize_db_pool()
        logger.info("Database connection pool initialized for standalone DigitalTwin test.")

        meter_id = "your_existing_meter_id_with_data" # <<< IMPORTANT: REPLACE!
        if meter_id == "your_existing_meter_id_with_data":
            logger.critical("WARNING: Please replace 'your_existing_meter_id_with_data' with an actual meter_id from your PostgreSQL database in digital_twin.py!")
            logger.critical("Exiting standalone test. Run `python main.py setup-db` and `python main.py run-scraper` first.")
            exit(1)

        twin = DigitalTwin(meter_id=meter_id)
        twin.load_model("baseline_model")

        # --- Example of running a simulation for a PAST period ---
        # Get current time for setting a past window
        now_tz = datetime.now(db_manager.get_timezone()).replace(second=0, microsecond=0) # Corrected
        
        # Define a past 24-hour window (e.g., from 48 hours ago to 24 hours ago)
        # Adjust these timestamps based on when you know you have data from your scraper
        # Example: Predict for yesterday (assuming scraper ran yesterday)
        prediction_start = now_tz - timedelta(hours=48)
        prediction_end = now_tz - timedelta(hours=24)

        logger.info(f"Running simulation for a PAST period: {prediction_start} to {prediction_end}")

        simulation_results = twin.run_simulation(
            model_name="baseline_model",
            data_for_training_hours=24*7, # Train on 7 days of data
            explicit_prediction_start_time=prediction_start, # Pass explicit start
            explicit_prediction_end_time=prediction_end      # Pass explicit end
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
        logger.error(f"Error during DigitalTwin test with real DB: {e}", exc_info=True)
    finally:
        try:
            if db_manager.DB_POOL:
                db_manager.close_db_pool()
                logger.info("Database connection pool closed.")
        except Exception as e:
            logger.error(f"Error closing DB pool: {e}")

