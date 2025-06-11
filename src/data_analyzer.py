import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional

# Import your custom database manager
from . import db_manager

# --- Logging Setup ---
logger = logging.getLogger(__name__)
# main.py handles global logging setup, so no specific handlers here.
# This logger will inherit from the root logger configured in main.py.


class DataAnalyzer:
    """
    Provides methods to retrieve and prepare data from the database
    for visualization and analysis in the dashboard.
    """

    def __init__(self):
        logger.info("DataAnalyzer initialized.")

    def get_latest_readings(self, meter_id: str, limit_count: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieves the latest 'limit_count' number of real meter readings for a specific meter,
        ordered by timestamp descending (most recent first).
        """
        logger.info(f"Fetching latest {limit_count} real readings for Meter ID: {meter_id}...")
        try:
            # Calls a new function in db_manager
            latest_readings = db_manager.get_latest_meter_readings_by_limit(meter_id, limit_count)
            logger.info(f"Retrieved {len(latest_readings)} latest readings for Meter ID {meter_id}.")
            return latest_readings
        except Exception as e:
            logger.error(f"Error fetching latest readings for dashboard (Meter ID: {meter_id}): {e}", exc_info=True)
            return []

    def get_historical_data(self, meter_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Retrieves historical real meter readings for a specific meter
        within the last 'hours' for dashboard display.
        """
        logger.info(f"Fetching {hours} hours of historical real data for Meter ID: {meter_id}...")
        try:
            end_time = datetime.now(db_manager.get_timezone())
            start_time = end_time - timedelta(hours=hours)
            # Calls an existing or new function in db_manager
            historical_data = db_manager.get_meter_readings_in_range(meter_id, start_time, end_time)
            # Ensure chronological order for charting
            sorted_data = sorted(historical_data, key=lambda x: x['timestamp'])
            logger.info(f"Retrieved {len(sorted_data)} historical readings for Meter ID {meter_id}.")
            return sorted_data
        except Exception as e:
            logger.error(f"Error fetching historical data for dashboard (Meter ID: {meter_id}): {e}", exc_info=True)
            return []

    def get_latest_forecast(self, meter_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the latest forecast run's predictions for a specific meter.
        """
        logger.info(f"Fetching latest forecast for Meter ID: {meter_id}...")
        try:
            # Calls a new function in db_manager
            latest_run = db_manager.get_latest_forecast_run(meter_id)
            if latest_run:
                forecast_run_id = latest_run['run_id']
                # Calls a new function in db_manager
                predictions = db_manager.get_forecast_predictions(forecast_run_id)
                # Ensure chronological order for charting
                sorted_predictions = sorted(predictions, key=lambda x: x['timestamp'])
                logger.info(f"Retrieved {len(sorted_predictions)} predictions for latest forecast run ({forecast_run_id}) for Meter ID {meter_id}.")
                return sorted_predictions
            else:
                logger.warning(f"No latest forecast run found for Meter ID: {meter_id}.")
                return []
        except Exception as e:
            logger.error(f"Error fetching latest forecast for dashboard (Meter ID: {meter_id}): {e}", exc_info=True)
            return []

    def get_all_meters(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all unique meter IDs stored in the database.
        """
        logger.info("Fetching all unique meter IDs...")
        try:
            # Calls an existing or new function in db_manager
            meters = db_manager.get_all_meter_details()
            logger.info(f"Retrieved {len(meters)} unique meters.")
            return meters
        except Exception as e:
            logger.error(f"Error fetching all meter IDs: {e}", exc_info=True)
            return []

    def get_forecast_run_metrics(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the latest forecast run's metrics (MAE, RMSE) for a specific meter.
        """
        logger.info(f"Fetching latest forecast run metrics for Meter ID: {meter_id}...")
        try:
            # Calls a new function in db_manager
            latest_run = db_manager.get_latest_forecast_run(meter_id)
            if latest_run:
                metrics = {
                    'mae': latest_run.get('mae'),
                    'rmse': latest_run.get('rmse'),
                    'model_name': latest_run.get('model_name'),
                    'prediction_start_time': latest_run.get('prediction_start_time'),
                    'prediction_end_time': latest_run.get('prediction_end_time')
                }
                logger.info(f"Retrieved metrics for latest forecast run for Meter ID {meter_id}: MAE={metrics['mae']}, RMSE={metrics['rmse']}.")
                return metrics
            else:
                logger.warning(f"No latest forecast run found for Meter ID: {meter_id} to retrieve metrics.")
                return None
        except Exception as e:
            logger.error(f"Error fetching forecast run metrics (Meter ID: {meter_id}): {e}", exc_info=True)
            return None


if __name__ == '__main__':
    # This block is for testing DataAnalyzer in isolation.
    # It requires a functional db_manager and database.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    print("--- Testing DataAnalyzer Component (requires active DB connection) ---")
    try:
        # Initialize DB pool for testing data analyzer directly
        db_manager.initialize_db_pool()
        analyzer = DataAnalyzer()

        # IMPORTANT: Replace with an actual meter ID that exists in your database
        # You can get meter_id from `SELECT meter_id FROM meters LIMIT 1;` after scraping has run.
        test_meter_id = "1000613" # <<<--- CHANGE THIS TO A REAL METER_ID FROM YOUR DB

        print(f"\n--- Fetching all meters ---")
        all_meters = analyzer.get_all_meters()
        if all_meters:
            print(f"Found meters: {all_meters}")
            test_meter_id = all_meters[0]['meter_id'] # Use the first available meter for testing
            print(f"Using meter: {test_meter_id} for tests.")
        else:
            print("No meters found in DB. Please run scraper to populate meters table first.")
            exit()

        print(f"\n--- Fetching latest readings for {test_meter_id} ---")
        latest = analyzer.get_latest_readings(test_meter_id, limit_count=5)
        for r in latest:
            print(f"  {r['timestamp']} - {r.get('energy_kwh_import', 'N/A')} kWh, {r.get('voltage_vrn', 'N/A')}V")

        print(f"\n--- Fetching historical data (last 24 hours) for {test_meter_id} ---")
        historical = analyzer.get_historical_data(test_meter_id, hours=24)
        print(f"Retrieved {len(historical)} historical points.")
        # Only print a few to avoid flooding console
        for r in historical[:5]:
            print(f"  {r['timestamp']} - {r.get('energy_kwh_import', 'N/A')} kWh")
        if len(historical) > 5:
            print("  ...")


        print(f"\n--- Fetching latest forecast for {test_meter_id} ---")
        forecast = analyzer.get_latest_forecast(test_meter_id)
        print(f"Retrieved {len(forecast)} forecast points.")
        # Only print a few to avoid flooding console
        for p in forecast[:5]:
            print(f"  {p['timestamp']} - {p.get('predicted_kwh', 'N/A')} predicted kWh")
        if len(forecast) > 5:
            print("  ...")

        print(f"\n--- Fetching forecast run metrics for {test_meter_id} ---")
        metrics = analyzer.get_forecast_run_metrics(test_meter_id)
        print(f"Metrics: {metrics}")

    except Exception as e:
        logger.error(f"Error during DataAnalyzer test: {e}", exc_info=True)
    finally:
        db_manager.close_db_pool()

