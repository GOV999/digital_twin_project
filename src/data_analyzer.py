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
            latest_readings = db_manager.get_latest_meter_readings_by_limit(meter_id, limit_count)
            logger.info(f"Retrieved {len(latest_readings)} latest readings for Meter ID {meter_id}.")
            return latest_readings
        except Exception as e:
            logger.error(f"Error fetching latest readings for dashboard (Meter ID {meter_id}): {e}", exc_info=True)
            return []

    def get_historical_data(self, meter_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Retrieves historical energy consumption data for a specific meter
        for the last 'hours' number of hours.
        """
        logger.info(f"Fetching {hours} hours of historical data for Meter ID: {meter_id}...")
        try:
            end_time = datetime.now(db_manager.get_timezone()).replace(second=0, microsecond=0)
            start_time = end_time - timedelta(hours=hours)
            historical_data = db_manager.get_meter_readings_in_range(meter_id, start_time, end_time)
            logger.info(f"Retrieved {len(historical_data)} historical points for Meter ID {meter_id}.")
            return historical_data
        except Exception as e:
            logger.error(f"Error fetching historical data for dashboard (Meter ID {meter_id}): {e}", exc_info=True)
            return []

    def get_latest_forecast(self, meter_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves the latest forecast predictions for a given meter ID.
        This involves getting the latest forecast run and then its associated predictions.
        """
        logger.info(f"Fetching latest forecast for Meter ID: {meter_id}...")
        try:
            latest_run = db_manager.get_latest_forecast_run(meter_id)
            if latest_run and latest_run.get('run_id'):
                forecast_predictions = db_manager.get_forecast_predictions(latest_run['run_id'])
                logger.info(f"Retrieved {len(forecast_predictions)} forecast points for Meter ID {meter_id} from run {latest_run['run_id']}.")
                return forecast_predictions
            else:
                logger.warning(f"No latest forecast run found for Meter ID: {meter_id}.")
                return []
        except Exception as e:
            logger.error(f"Error fetching latest forecast for dashboard (Meter ID {meter_id}): {e}", exc_info=True)
            return []

    def get_latest_forecast_run_details(self, meter_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the full details of the latest forecast run for a given meter ID,
        including MAE and RMSE.
        """
        logger.info(f"Fetching latest forecast run details for Meter ID: {meter_id}...")
        try:
            run_details = db_manager.get_latest_forecast_run(meter_id)
            if run_details:
                logger.info(f"Retrieved latest forecast run details for Meter ID {meter_id}: Run ID {run_details.get('run_id')}.")
                return run_details
            else:
                logger.warning(f"No latest forecast run details found for Meter ID: {meter_id}.")
                return None
        except Exception as e:
            logger.error(f"Error fetching latest forecast run details for Meter ID {meter_id}: {e}", exc_info=True)
            return None


    def get_all_meters(self) -> List[Dict[str, Any]]:
        """
        Retrieves details for all meters in the database.
        """
        logger.info("Fetching all meter details...")
        try:
            all_meters = db_manager.get_all_meter_details()
            logger.info(f"Retrieved {len(all_meters)} meter details.")
            return all_meters
        except Exception as e:
            logger.error(f"Error fetching all meter details: {e}", exc_info=True)
            return []


if __name__ == '__main__':
    # For standalone testing of data_analyzer.py, a basic logging setup is needed.
    # In normal app execution, main.py would configure this.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Running standalone DataAnalyzer test.")

    try:
        db_manager.initialize_db_pool()
        logger.info("Database connection pool initialized for standalone DataAnalyzer test.")

        analyzer = DataAnalyzer()

        test_meter_id = "your_existing_meter_id_with_data" # <<< IMPORTANT: REPLACE WITH A REAL METER ID!
        if test_meter_id == "your_existing_meter_id_with_data":
            logger.critical("WARNING: Please replace 'your_existing_meter_id_with_data' with an actual meter_id from your PostgreSQL database in data_analyzer.py!")
            logger.critical("Exiting standalone test. Run `python main.py setup-db` and `python main.py run-scraper` first.")
            exit(1)


        print(f"\n--- Fetching latest readings for {test_meter_id} ---")
        latest = analyzer.get_latest_readings(test_meter_id, limit_count=5)
        for r in latest:
            energy = r.get('energy_kwh_import', 'N/A')
            voltage = r.get('voltage_vrn', 'N/A')
            current = r.get('current_ir', 'N/A')
            print(f"  {r['timestamp']} - {energy} kWh, {voltage}V, {current}A")


        print(f"\n--- Fetching historical data (last 24 hours) for {test_meter_id} ---")
        historical = analyzer.get_historical_data(test_meter_id, hours=24)
        print(f"Retrieved {len(historical)} historical points.")
        for r in historical[:5]:
            print(f"  {r['timestamp']} - {r.get('energy_kwh_import', 'N/A')} kWh")
        if len(historical) > 5:
            print("  ...")


        print(f"\n--- Fetching latest forecast for {test_meter_id} ---")
        forecast = analyzer.get_latest_forecast(test_meter_id)
        print(f"Retrieved {len(forecast)} forecast points.")
        for p in forecast[:5]:
            print(f"  {p['timestamp']} - {p.get('predicted_kwh', 'N/A')} predicted kWh (Actual: {p.get('actual_kwh', 'N/A')})")
        if len(forecast) > 5:
            print("  ...")

        print(f"\n--- Fetching latest forecast run details for {test_meter_id} ---")
        forecast_run_details = analyzer.get_latest_forecast_run_details(test_meter_id)
        if forecast_run_details:
            print(f"  Run ID: {forecast_run_details.get('run_id')}")
            print(f"  Model: {forecast_run_details.get('model_name')}")
            print(f"  MAE: {forecast_run_details.get('mae', 'N/A')}, RMSE: {forecast_run_details.get('rmse', 'N/A')}")
        else:
            print("  No latest forecast run details found.")


        print(f"\n--- Fetching all meter details ---")
        all_meters = analyzer.get_all_meters()
        for m in all_meters:
            print(f"  Meter ID: {m['meter_id']}, No: {m['meter_no']}, Location: {m['location']}")


    except Exception as e:
        logger.error(f"Error during standalone DataAnalyzer test: {e}", exc_info=True)
    finally:
        try:
            if db_manager.DB_POOL:
                db_manager.close_db_pool()
                logger.info("Database connection pool closed.")
        except Exception as e:
            logger.error(f"Error closing DB pool: {e}")
        logger.info("Standalone DataAnalyzer test finished.")

