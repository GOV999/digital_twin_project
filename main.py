import argparse
import configparser
import logging
import os
from datetime import datetime, timedelta, timezone
import sys
import json
from flask import Flask, jsonify, request # Import Flask components
from flask_cors import CORS # Needed for cross-origin requests

# Adjust the Python path to import modules from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Import your modules from src/
from src import db_manager
from src import scraper
from src.digital_twin import DigitalTwin # Assuming this file exists now
from src.data_analyzer import DataAnalyzer

# --- Configuration & Path Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# --- Global Config Object ---
app_config = configparser.ConfigParser()

# --- Flask App Initialization ---
# This Flask app will be used when `main.py api-server` command is run
flask_app = Flask(__name__)
CORS(flask_app) # Enable CORS for all routes

# Global instance of DataAnalyzer
data_analyzer_instance = None

def _setup_logging():
    """
    Sets up the global logging configuration for the entire application.
    """
    log_file_path = os.path.join(LOG_DIR, 'digital_twin_app.log')

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    logging.info("Global logging configured.")

    # Suppress verbose logs from external libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('psycopg2').setLevel(logging.WARNING)
    logging.getLogger('webdriver_manager').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING) # Suppress Flask/Werkzeug default logs

def _load_config():
    """Loads application configuration from config.ini into the global app_config object."""
    if not os.path.exists(CONFIG_PATH):
        logging.critical(f"Configuration file not found at {CONFIG_PATH}. Please ensure 'config.ini' exists in the project root.")
        sys.exit(1)
    app_config.read(CONFIG_PATH)
    logging.info("Configuration loaded successfully.")

def run_setup_db_command(args):
    """
    Handles the 'setup-db' command.
    Initializes the DB pool, creates/updates tables, and then closes the pool.
    """
    logging.info("Running database setup and table creation/update...")
    try:
        db_manager.initialize_db_pool()
        db_manager.create_tables()
        logging.info("Database setup complete.")
    except Exception as e:
        logging.error(f"Failed to set up database: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_manager.close_db_pool()

def run_scraper_command(args):
    """
    Handles the 'run-scraper' command.
    Starts the web scraper process. This typically runs indefinitely.
    """
    logging.info("Starting web scraper. Press Ctrl+C to stop.")
    try:
        scraper.main()
    except KeyboardInterrupt:
        logging.info("Scraper gracefully stopped by user (Ctrl+C).")
    except Exception as e:
        logging.critical(f"Scraper encountered a fatal error: {e}", exc_info=True)
        sys.exit(1)

def run_simulation_command(args):
    """
    Handles the 'run-simulation' command.
    Runs a digital twin simulation for a specific meter using a chosen model.
    """
    logging.info(f"Running digital twin simulation for meter ID '{args.meter_id}' using model '{args.model}' for {args.duration_hours} hours...")

    try:
        db_manager.initialize_db_pool()
    except Exception as e:
        logging.critical(f"Failed to initialize database pool for simulation: {e}", exc_info=True)
        sys.exit(1)

    try:
        twin = DigitalTwin(meter_id=args.meter_id)

        simulation_results = twin.run_simulation(
            simulation_duration_hours=args.duration_hours,
            prediction_horizon_hours=args.duration_hours,
            model_name=args.model,
            data_for_training_hours=args.training_hours
        )

        logging.info("\n--- Digital Twin Simulation Summary ---")
        logging.info(f"Meter ID: {simulation_results.get('meter_id')}")
        logging.info(f"Forecasting Model Used: {simulation_results.get('model_used')}")
        logging.info(f"Simulation Period: {simulation_results.get('simulation_start').strftime('%Y-%m-%d %H:%M:%S%z')} to {simulation_results.get('simulation_end').strftime('%Y-%m-%d %H:%M:%S%z')}")
        logging.info(f"Number of Simulated Points Generated: {len(simulation_results.get('simulated_readings', []))}")
        logging.info(f"Associated Forecast Run ID: {simulation_results.get('run_id')}")

        metrics = simulation_results.get('metrics')
        if metrics and not (isinstance(metrics.get('mae'), float) and metrics.get('mae') is None):
             logging.info(f"Performance Metrics: MAE={metrics.get('mae'):.2f}, RMSE={metrics.get('rmse'):.2f}")
        else:
            logging.warning("No performance metrics calculated (likely no overlapping actual data in simulation period, or model not trained).")

    except Exception as e:
        logging.error(f"An error occurred during digital twin simulation: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_manager.close_db_pool()

# --- New: API Server Command & Canvas Bridge ---

def run_api_server_command(args):
    """
    Handles the 'api-server' command.
    Starts the Flask API server within the Canvas environment.
    This will be the entry point for the React dashboard.
    """
    global data_analyzer_instance
    logging.info("Starting Flask API server...")
    try:
        db_manager.initialize_db_pool()
        data_analyzer_instance = DataAnalyzer() # Initialize the DataAnalyzer instance
        logging.info("DataAnalyzer instance created for API server.")

        # This will make the Flask app available to the Canvas environment
        # when running `python main.py api-server`.
        # The __fetch_data_for_app will effectively call `route_api_call`
        # for various endpoint requests.
        logging.info("Flask API server is ready to handle requests from Canvas.")
        flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False) # Important: debug=False, use_reloader=False for Canvas
    except Exception as e:
        logging.critical(f"Fatal error starting API server: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_manager.close_db_pool()
        logging.info("API Server shutdown complete and DB pool closed.")

# --- Flask API Routes (moved from api_server.py) ---

@flask_app.route('/api/meters', methods=['GET'])
def api_get_meters():
    """Returns a list of all meters."""
    try:
        meters = data_analyzer_instance.get_all_meters()
        # Convert datetime objects to ISO format for JSON serialization
        for meter in meters:
            if 'created_at' in meter and meter['created_at']:
                meter['created_at'] = meter['created_at'].isoformat()
            if 'updated_at' in meter and meter['updated_at']:
                meter['updated_at'] = meter['updated_at'].isoformat()
        return jsonify(meters)
    except Exception as e:
        logging.error(f"Error in /api/meters: {e}", exc_info=True)
        return jsonify({"error": "Failed to fetch meters"}), 500

@flask_app.route('/api/readings/latest/<string:meter_id>', methods=['GET'])
def api_get_latest_readings(meter_id):
    """Returns the latest readings for a specific meter."""
    try:
        limit_count = request.args.get('limit', default=20, type=int)
        latest_readings = data_analyzer_instance.get_latest_readings(meter_id, limit_count)
        # Convert datetime objects to ISO format for JSON serialization
        for reading in latest_readings:
            if 'timestamp' in reading and reading['timestamp']:
                reading['timestamp'] = reading['timestamp'].isoformat()
            if 'ingestion_time' in reading and reading['ingestion_time']:
                reading['ingestion_time'] = reading['ingestion_time'].isoformat()
        return jsonify(latest_readings)
    except Exception as e:
        logging.error(f"Error in /api/readings/latest/{meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch latest readings for {meter_id}"}), 500

@flask_app.route('/api/readings/historical/<string:meter_id>', methods=['GET'])
def api_get_historical_data(meter_id):
    """Returns historical data for a specific meter within a time range."""
    try:
        hours = request.args.get('hours', default=24, type=int)
        historical_data = data_analyzer_instance.get_historical_data(meter_id, hours)
        # Convert datetime objects to ISO format for JSON serialization
        for data_point in historical_data:
            if 'timestamp' in data_point and data_point['timestamp']:
                data_point['timestamp'] = data_point['timestamp'].isoformat()
            if 'ingestion_time' in data_point and data_point['ingestion_time']:
                data_point['ingestion_time'] = data_point['ingestion_time'].isoformat()
        return jsonify(historical_data)
    except Exception as e:
        logging.error(f"Error in /api/readings/historical/{meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch historical data for {meter_id}"}), 500

@flask_app.route('/api/forecast/latest/<string:meter_id>', methods=['GET'])
def api_get_latest_forecast(meter_id):
    """Returns the latest forecast predictions for a specific meter."""
    try:
        forecast_predictions = data_analyzer_instance.get_latest_forecast(meter_id)
        for prediction in forecast_predictions:
            if 'timestamp' in prediction and prediction['timestamp']:
                prediction['timestamp'] = prediction['timestamp'].isoformat()
        return jsonify(forecast_predictions)
    except Exception as e:
        logging.error(f"Error in /api/forecast/latest/{meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch latest forecast for {meter_id}"}), 500

@flask_app.route('/api/forecast/metrics/<string:meter_id>', methods=['GET'])
def api_get_forecast_metrics(meter_id):
    """Returns the latest forecast run metrics for a specific meter."""
    try:
        metrics = data_analyzer_instance.get_forecast_run_metrics(meter_id)
        if metrics:
            if 'prediction_start_time' in metrics and metrics['prediction_start_time']:
                metrics['prediction_start_time'] = metrics['prediction_start_time'].isoformat()
            if 'prediction_end_time' in metrics and metrics['prediction_end_time']:
                metrics['prediction_end_time'] = metrics['prediction_end_time'].isoformat()
            if 'run_timestamp' in metrics and metrics['run_timestamp']:
                metrics['run_timestamp'] = metrics['run_timestamp'].isoformat()
            return jsonify(metrics)
        else:
            return jsonify({}), 404
    except Exception as e:
        logging.error(f"Error in /api/forecast/metrics/{meter_id}: {e}", exc_info=True)
        return jsonify({"error": f"Failed to fetch forecast metrics for {meter_id}"}), 500

# --- Custom 404 Error Handler for Flask API ---
@flask_app.errorhandler(404)
def not_found_error_flask(error):
    logging.warning(f"Flask API 404 Not Found: {request.path}")
    return jsonify({"error": "API endpoint not found", "path": request.path}), 404

# --- Main CLI Logic ---

def main():
    """
    Main entry point for the Digital Twin for Demand Forecasting command-line application.
    Parses arguments and dispatches to the appropriate command handler.
    """
    _setup_logging()
    _load_config()

    parser = argparse.ArgumentParser(
        description="Digital Twin for Demand Forecasting Project CLI. Use subcommands to perform various operations.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Subparser for 'setup-db' command
    setup_db_parser = subparsers.add_parser(
        "setup-db",
        help="Initializes or updates PostgreSQL database tables.",
        description="Ensures all necessary database tables are created or updated."
    )
    setup_db_parser.set_defaults(func=run_setup_db_command)

    # Subparser for 'run-scraper' command
    run_scraper_parser = subparsers.add_parser(
        "run-scraper",
        help="Starts the web scraper to continuously fetch smart meter readings.",
        description="Initiates the web scraping process. Runs continuously. Press Ctrl+C to stop."
    )
    run_scraper_parser.set_defaults(func=run_scraper_command)

    # Subparser for 'run-simulation' command
    run_simulation_parser = subparsers.add_parser(
        "run-simulation",
        help="Runs a digital twin demand simulation and forecasts future consumption.",
        description="Executes a digital twin simulation for a specified meter."
    )
    run_simulation_parser.add_argument(
        "--meter-id",
        type=str,
        required=True,
        help="The unique ID of the meter for which to run the simulation (e.g., '1000613')."
    )
    run_simulation_parser.add_argument(
        "--model",
        type=str,
        default="baseline_model",
        help="The name of the forecasting model to use (e.g., 'baseline_model')."
    )
    run_simulation_parser.add_argument(
        "--duration-hours",
        type=int,
        default=24,
        help="The duration in hours for which to generate future demand predictions."
    )
    run_simulation_parser.add_argument(
        "--training-hours",
        type=int,
        default=24 * 7,
        help="Amount of historical data (in hours) for training. Defaults to 168 hours (7 days)."
    )
    run_simulation_parser.set_defaults(func=run_simulation_command)

    # New: Subparser for 'api-server' command
    api_server_parser = subparsers.add_parser(
        "api-server",
        help="Starts the Flask API server to serve data to the dashboard.",
        description="Launches the Flask API server which exposes data from the database. "
                    "This command should be run in the Canvas environment to connect to the dashboard."
    )
    api_server_parser.set_defaults(func=run_api_server_command)

    args = parser.parse_args()

    if args.command:
        try:
            args.func(args)
        except Exception as e:
            logging.critical(f"An unhandled error occurred during command execution: {e}", exc_info=True)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
