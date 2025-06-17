import argparse
import configparser
import logging
import os
from datetime import datetime, timedelta, timezone
import sys
import json
from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import pytz
from decimal import Decimal

# Adjust the Python path to import modules from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Import your modules from src/
from src import db_manager
from src import scraper
from src.digital_twin import DigitalTwin
from src.data_analyzer import DataAnalyzer

# --- Configuration & Path Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# --- Global Config Object ---
app_config = configparser.ConfigParser()

# --- Flask App Initialization ---
flask_app = Flask(__name__)
CORS(flask_app)

# Global instance of DataAnalyzer
data_analyzer_instance = None
APP_TIMEZONE = pytz.timezone('Asia/Kolkata') # Ensure consistent timezone

# --- Define logger for main.py module ---
logger = logging.getLogger(__name__)


# --- Custom JSON Encoder for Decimal and datetime objects ---
class CustomJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj.is_nan() or obj.is_infinite(): # Check if Decimal is NaN or Inf
                return None # Convert to None for JSON null
            return float(obj)
        elif isinstance(obj, datetime):
            if obj.tzinfo is None:
                local_dt = APP_TIMEZONE.localize(obj)
            else:
                local_dt = obj.astimezone(APP_TIMEZONE)
            return local_dt.isoformat()
        elif isinstance(obj, float): # Check for float NaN or Inf
            if obj != obj or obj == float('inf') or obj == float('-inf'): # obj != obj is a common way to check for NaN
                return None # Convert to None for JSON null
            return obj
        return super().default(obj)

flask_app.json_encoder = CustomJsonEncoder # Set the custom encoder for the Flask app

def _setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(LOG_DIR, 'main.log')),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('psycopg2').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('PIL').setLevel(logging.WARNING)
    logger.info("Global logging configured.")

def _load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.critical(f"Config file not found at {CONFIG_PATH}. Please create it.")
        raise FileNotFoundError(f"config.ini not found at {CONFIG_PATH}")
    app_config.read(CONFIG_PATH)
    logger.info("Configuration loaded successfully.")

def run_scraper_command(args):
    _load_config()
    logger.info("Starting scraper...")
    db_manager.initialize_db_pool()
    try:
        scraper.main()
    finally:
        db_manager.close_db_pool()

def run_simulation_command(args):
    _load_config()
    logger.info("Running digital twin simulation...")
    db_manager.initialize_db_pool()
    try:
        meter_id = args.meter_id
        model_name = args.model
        duration_hours = args.duration_hours
        training_hours = args.training_hours
        prediction_start_time = None
        prediction_end_time = None

        if args.prediction_start:
            try:
                prediction_start_time = datetime.fromisoformat(args.prediction_start)
                if prediction_start_time.tzinfo is None:
                    prediction_start_time = APP_TIMEZONE.localize(prediction_start_time)
                else:
                    prediction_start_time = prediction_start_time.astimezone(APP_TIMEZONE)
            except ValueError:
                logger.error(f"Invalid prediction-start format: {args.prediction_start}.")
                return

        if args.prediction_end:
            try:
                prediction_end_time = datetime.fromisoformat(args.prediction_end)
                if prediction_end_time.tzinfo is None:
                    prediction_end_time = APP_TIMEZONE.localize(prediction_end_time)
                else:
                    prediction_end_time = prediction_end_time.astimezone(APP_TIMEZONE)
            except ValueError:
                logger.error(f"Invalid prediction-end format: {args.prediction_end}.")
                return

        if prediction_start_time and prediction_end_time and prediction_start_time >= prediction_end_time:
            logger.error("Prediction start time must be before prediction end time.")
            return

        twin = DigitalTwin(meter_id=meter_id)
        results = twin.run_simulation(
            simulation_duration_hours=duration_hours,
            prediction_horizon_hours=duration_hours,
            model_name=model_name,
            data_for_training_hours=training_hours,
            explicit_prediction_start_time=prediction_start_time,
            explicit_prediction_end_time=prediction_end_time
        )
        logger.info(f"Simulation for Meter ID {meter_id} finished. Run ID: {results.get('run_id')}, Metrics: {results.get('metrics')}")
    except Exception as e:
        logger.critical(f"Error during simulation: {e}", exc_info=True)
    finally:
        db_manager.close_db_pool()

def setup_db_command(args):
    _load_config()
    logger.info("Setting up database...")
    db_manager.initialize_db_pool()
    try:
        db_manager.create_tables()
        logger.info("Database setup complete.")
    except Exception as e:
        logger.critical(f"Error during database setup: {e}", exc_info=True)
    finally:
        db_manager.close_db_pool()

def run_api_server_command(args):
    global data_analyzer_instance
    _load_config()
    logger.info("Starting Flask API server...")
    db_manager.initialize_db_pool()
    data_analyzer_instance = DataAnalyzer()

    @flask_app.route('/api/meters', methods=['GET'])
    def get_meters():
        try:
            meters = data_analyzer_instance.get_all_meters()
            return jsonify(meters)
        except Exception as e:
            logger.error(f"Error fetching meters: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch meters", "details": str(e)}), 500

    @flask_app.route('/api/meters/<meter_id>/latest_readings', methods=['GET'])
    def get_latest_readings(meter_id):
        try:
            limit = request.args.get('limit', type=int, default=10)
            readings = data_analyzer_instance.get_latest_readings(meter_id, limit_count=limit)
            return jsonify(readings)
        except Exception as e:
            logger.error(f"Error fetching latest readings for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch latest readings", "details": str(e)}), 500

    @flask_app.route('/api/meters/<meter_id>/historical_data', methods=['GET'])
    def get_historical_data(meter_id):
        try:
            hours = request.args.get('hours', type=int, default=24) # Default fetch is 24h, frontend filters display
            data = data_analyzer_instance.get_historical_data(meter_id, hours=hours)
            return jsonify(data)
        except Exception as e:
            logger.error(f"Error fetching historical data for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch historical data", "details": str(e)}), 500

    @flask_app.route('/api/meters/<meter_id>/latest_forecast', methods=['GET'])
    def get_latest_forecast(meter_id):
        try:
            forecast = data_analyzer_instance.get_latest_forecast(meter_id)
            return jsonify(forecast)
        except Exception as e:
            logger.error(f"Error fetching latest forecast for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch latest forecast", "details": str(e)}), 500

    @flask_app.route('/api/meters/<meter_id>/latest_forecast_details', methods=['GET'])
    def get_latest_forecast_details(meter_id):
        try:
            run_details = data_analyzer_instance.get_latest_forecast_run_details(meter_id)
            # Explicitly check and convert NaN to None before jsonify for metrics
            if run_details and 'metrics' in run_details and isinstance(run_details['metrics'], dict):
                if 'mae' in run_details['metrics'] and isinstance(run_details['metrics']['mae'], float) and run_details['metrics']['mae'] != run_details['metrics']['mae']:
                    run_details['metrics']['mae'] = None
                if 'rmse' in run_details['metrics'] and isinstance(run_details['metrics']['rmse'], float) and run_details['metrics']['rmse'] != run_details['metrics']['rmse']:
                    run_details['metrics']['rmse'] = None
            elif run_details: # Handle if metrics themselves might be NaN from older DB data
                 if 'mae' in run_details and isinstance(run_details['mae'], float) and run_details['mae'] != run_details['mae']:
                    run_details['mae'] = None
                 if 'rmse' in run_details and isinstance(run_details['rmse'], float) and run_details['rmse'] != run_details['rmse']:
                    run_details['rmse'] = None
            return jsonify(run_details)
        except Exception as e:
            logger.error(f"Error fetching latest forecast details for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to fetch forecast details", "details": str(e)}), 500

    @flask_app.route('/api/meters/<meter_id>/simulate', methods=['POST'])
    def trigger_simulation_endpoint(meter_id):
        logger.info(f"Received simulation trigger for meter_id: {meter_id}")
        try:
            data = request.get_json()
            if not data or 'duration_hours' not in data:
                return jsonify({"error": "Missing 'duration_hours' in request body"}), 400

            duration_hours = int(data['duration_hours'])
            model_name = str(data.get('model_name', "baseline_model")) # Default model
            training_hours = int(data.get('training_hours', 24 * 7)) # Default training hours

            if duration_hours <= 0:
                return jsonify({"error": "'duration_hours' must be positive"}), 400

            logger.info(f"Attempting simulation for meter {meter_id}, duration: {duration_hours}h, model: {model_name}, training: {training_hours}h")

            if db_manager.DB_POOL is None:
                logger.warning("DB_POOL was None in /simulate endpoint, re-initializing.")
                db_manager.initialize_db_pool()

            twin = DigitalTwin(meter_id=meter_id)
            results = twin.run_simulation(
                simulation_duration_hours=duration_hours,
                prediction_horizon_hours=duration_hours,
                model_name=model_name,
                data_for_training_hours=training_hours
            )
            
            # Sanitize metrics before sending response
            simulation_metrics = results.get('metrics')
            if isinstance(simulation_metrics, dict):
                if 'mae' in simulation_metrics and isinstance(simulation_metrics['mae'], float) and simulation_metrics['mae'] != simulation_metrics['mae']: # Check for NaN
                    simulation_metrics['mae'] = None
                if 'rmse' in simulation_metrics and isinstance(simulation_metrics['rmse'], float) and simulation_metrics['rmse'] != simulation_metrics['rmse']: # Check for NaN
                    simulation_metrics['rmse'] = None
            else: # If metrics is not a dict or is None
                simulation_metrics = {"mae": None, "rmse": None}


            logger.info(f"Simulation for Meter ID {meter_id} triggered via API completed. Run ID: {results.get('run_id')}")
            return jsonify({
                "message": "Simulation triggered successfully", 
                "run_id": results.get('run_id'), 
                "metrics": simulation_metrics # Send sanitized metrics
            }), 200

        except ValueError as ve:
            logger.error(f"ValueError during API-triggered simulation for {meter_id}: {ve}", exc_info=True)
            return jsonify({"error": f"Invalid input: {str(ve)}"}), 400
        except Exception as e:
            logger.critical(f"Unhandled error during API-triggered simulation for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to trigger simulation due to an internal server error", "details": str(e)}), 500

    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False) # debug=False for production, use_reloader=False if not needed
    
    # This teardown might not run if server is killed forcefully
    logger.info("Shutting down Flask API server.")
    db_manager.close_db_pool()


def main():
    _setup_logging()
    parser = argparse.ArgumentParser(description="Digital Twin for Smart Meter Demand Forecasting.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True) # Makes command mandatory

    # setup-db command
    setup_db_parser = subparsers.add_parser(
        "setup-db", help="Creates and updates database tables."
    )
    setup_db_parser.set_defaults(func=setup_db_command)

    # run-scraper command
    run_scraper_parser = subparsers.add_parser(
        "run-scraper", help="Starts the web scraping process for meter data."
    )
    run_scraper_parser.set_defaults(func=run_scraper_command)

    # run-simulation command (updated)
    run_simulation_parser = subparsers.add_parser(
        "run-simulation", help="Runs the digital twin simulation to generate forecasts."
    )
    run_simulation_parser.add_argument(
        "--meter-id",
        type=str,
        required=True,
        help="The ID of the meter for which to run the simulation."
    )
    run_simulation_parser.add_argument(
        "--model",
        type=str,
        default="baseline_model",
        help="The name of the forecasting model to use (e.g., 'baseline_model')."
    )
    run_simulation_parser.add_argument( # Default changed to 2 hours
        "--duration-hours",
        type=int,
        default=2, 
        help="The duration in hours for which to generate future demand predictions (forecast horizon)."
    )
    run_simulation_parser.add_argument(
        "--training-hours",
        type=int,
        default=24 * 7,
        help="Amount of historical data (in hours) for training. Defaults to 168 hours (7 days).'"
    )
    run_simulation_parser.add_argument(
        "--prediction-start",
        type=str,
        help="Optional: Explicit start timestamp for prediction (ISO format:YYYY-MM-DDTHH:MM:SS[+/-]HH:MM). Overrides dynamic start time.",
        required=False
    )
    run_simulation_parser.add_argument(
        "--prediction-end",
        type=str,
        help="Optional: Explicit end timestamp for prediction (ISO format:YYYY-MM-DDTHH:MM:SS[+/-]HH:MM). Requires --prediction-start.",
        required=False
    )
    run_simulation_parser.set_defaults(func=run_simulation_command)

    # api-server command
    api_server_parser = subparsers.add_parser(
        "api-server",
        help="Starts the Flask API server to serve data to the dashboard."
    )
    api_server_parser.set_defaults(func=run_api_server_command)

    args = parser.parse_args()

    # Call the function associated with the chosen sub-command
    if hasattr(args, 'func'):
        try:
            args.func(args)
        except Exception as e:
            # More specific error for command execution failure
            logger.critical(f"Command '{args.command}' execution failed: {e}", exc_info=True)
    else:
        # Should not happen if subparsers are required=True, but good practice
        parser.print_help() 

if __name__ == '__main__':
    main()