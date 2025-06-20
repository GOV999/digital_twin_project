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
import multiprocessing 
import time 
from typing import Optional, List, Dict, Any # <<<<<<< ADD THIS LINE (or just Optional if others not needed at global scope)

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
SCRAPER_LOG_FILE = os.path.join(LOG_DIR, 'scraper.log') 
os.makedirs(LOG_DIR, exist_ok=True)

# --- Global Config Object ---
app_config = configparser.ConfigParser()

# --- Flask App Initialization ---
flask_app = Flask(__name__)
CORS(flask_app)

# Global instance of DataAnalyzer
data_analyzer_instance = None
APP_TIMEZONE = pytz.timezone('Asia/Kolkata')

# --- Scraper Process Management ---
scraper_process: Optional[multiprocessing.Process] = None
stop_scraper_event: Optional[multiprocessing.Event] = None # Now Optional and Event are defined

# --- Define logger for main.py module ---
logger = logging.getLogger(__name__)

# ... (rest of your main.py file remains the same as the one I provided for scraper controls) ...

# --- Custom JSON Encoder for Decimal and datetime objects ---
class CustomJsonEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj.is_nan() or obj.is_infinite():
                return None
            return float(obj)
        elif isinstance(obj, datetime):
            if obj.tzinfo is None:
                local_dt = APP_TIMEZONE.localize(obj)
            else:
                local_dt = obj.astimezone(APP_TIMEZONE)
            return local_dt.isoformat()
        elif isinstance(obj, float):
            if obj != obj or obj == float('inf') or obj == float('-inf'):
                return None
            return obj
        return super().default(obj)

flask_app.json_encoder = CustomJsonEncoder

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
    scraper_logger = logging.getLogger('src.scraper') 
    if not scraper_logger.handlers:
        fh_scraper = logging.FileHandler(SCRAPER_LOG_FILE)
        fh_scraper.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        scraper_logger.addHandler(fh_scraper)
        scraper_logger.setLevel(logging.INFO)

    logger.info("Global logging configured.")

def _load_config():
    if not os.path.exists(CONFIG_PATH):
        logger.critical(f"Config file not found at {CONFIG_PATH}. Please create it.")
        raise FileNotFoundError(f"config.ini not found at {CONFIG_PATH}")
    app_config.read(CONFIG_PATH)
    logger.info("Configuration loaded successfully.")

def run_scraper_process(stop_event_param: multiprocessing.Event):
    logger.info("Scraper process started via run_scraper_process wrapper.")
    try:
        if hasattr(scraper, 'main'):
            import inspect
            sig = inspect.signature(scraper.main)
            if 'stop_event' in sig.parameters:
                 scraper.main(stop_event=stop_event_param)
            else:
                logger.warning("scraper.main does not accept 'stop_event'. Stop functionality will be impaired.")
                scraper.main() 
        else:
            logger.error("scraper.py does not have a main() function.")
    except Exception as e:
        logger.error(f"Exception in scraper process: {e}", exc_info=True)
    finally:
        logger.info("Scraper process (run_scraper_process wrapper) finished.")

def run_scraper_command_cli(args):
    _load_config()
    logger.info("Starting scraper via CLI command...")
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
    global data_analyzer_instance, scraper_process, stop_scraper_event
    _load_config()
    logger.info("Starting Flask API server...")
    db_manager.initialize_db_pool()
    data_analyzer_instance = DataAnalyzer()
    stop_scraper_event = multiprocessing.Event() 

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
            # Ensure CHART_DATA_FETCH_HOURS_DEFAULT is defined if you use it here
            # For safety, use a hardcoded default or get from app_config
            hours = request.args.get('hours', type=int, default=24*7) 
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
            if run_details and 'metrics' in run_details and isinstance(run_details['metrics'], dict):
                if 'mae' in run_details['metrics'] and isinstance(run_details['metrics']['mae'], float) and run_details['metrics']['mae'] != run_details['metrics']['mae']:
                    run_details['metrics']['mae'] = None
                if 'rmse' in run_details['metrics'] and isinstance(run_details['metrics']['rmse'], float) and run_details['metrics']['rmse'] != run_details['metrics']['rmse']:
                    run_details['metrics']['rmse'] = None
            elif run_details:
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
            model_name = str(data.get('model_name', "baseline_model"))
            training_hours = int(data.get('training_hours', 24 * 7))
            if duration_hours <= 0: return jsonify({"error": "'duration_hours' must be positive"}), 400
            
            twin = DigitalTwin(meter_id=meter_id)
            results = twin.run_simulation(
                simulation_duration_hours=duration_hours,
                prediction_horizon_hours=duration_hours,
                model_name=model_name,
                data_for_training_hours=training_hours
            )
            simulation_metrics = results.get('metrics')
            if isinstance(simulation_metrics, dict):
                if 'mae' in simulation_metrics and isinstance(simulation_metrics['mae'], float) and simulation_metrics['mae'] != simulation_metrics['mae']:
                    simulation_metrics['mae'] = None
                if 'rmse' in simulation_metrics and isinstance(simulation_metrics['rmse'], float) and simulation_metrics['rmse'] != simulation_metrics['rmse']:
                    simulation_metrics['rmse'] = None
            else: simulation_metrics = {"mae": None, "rmse": None}
            logger.info(f"Simulation for Meter ID {meter_id} via API completed. Run ID: {results.get('run_id')}")
            return jsonify({"message": "Simulation triggered successfully", "run_id": results.get('run_id'), "metrics": simulation_metrics}), 200
        except ValueError as ve:
            logger.error(f"ValueError during API-triggered simulation for {meter_id}: {ve}", exc_info=True)
            return jsonify({"error": f"Invalid input: {str(ve)}"}), 400
        except Exception as e:
            logger.critical(f"Error during API-triggered simulation for {meter_id}: {e}", exc_info=True)
            return jsonify({"error": "Failed to trigger simulation", "details": str(e)}), 500

    @flask_app.route('/api/scraper/start', methods=['POST'])
    def start_scraper_endpoint():
        global scraper_process, stop_scraper_event
        logger.info("Attempting to start scraper...")
        if scraper_process and scraper_process.is_alive():
            logger.warning("Scraper is already running.")
            return jsonify({"message": "Scraper is already running.", "status": "running"}), 409
        
        if stop_scraper_event is None: 
             stop_scraper_event = multiprocessing.Event()
        stop_scraper_event.clear() 

        try:
            logger.info("Creating new scraper process.")
            scraper_process = multiprocessing.Process(target=run_scraper_process, args=(stop_scraper_event,))
            scraper_process.daemon = True 
            scraper_process.start()
            logger.info(f"Scraper process started with PID: {scraper_process.pid}")
            return jsonify({"message": "Scraper started successfully.", "status": "running"}), 200
        except Exception as e:
            logger.error(f"Failed to start scraper process: {e}", exc_info=True)
            return jsonify({"message": f"Failed to start scraper: {str(e)}", "status": "error"}), 500

    @flask_app.route('/api/scraper/stop', methods=['POST'])
    def stop_scraper_endpoint():
        global scraper_process, stop_scraper_event
        logger.info("Attempting to stop scraper...")
        if not scraper_process or not scraper_process.is_alive():
            logger.warning("Scraper is not running or process object not found.")
            return jsonify({"message": "Scraper is not running.", "status": "stopped"}), 200

        if stop_scraper_event:
            logger.info("Setting stop event for scraper process.")
            stop_scraper_event.set()
            
            scraper_process.join(timeout=30) 
            if scraper_process.is_alive():
                logger.warning("Scraper process did not terminate gracefully after 30s. Terminating forcefully.")
                scraper_process.terminate() 
                scraper_process.join(timeout=5) 
            
            if not scraper_process.is_alive():
                logger.info("Scraper process stopped successfully.")
                scraper_process = None 
                return jsonify({"message": "Scraper stopped successfully.", "status": "stopped"}), 200
            else:
                logger.error("Failed to stop scraper process even after terminate.")
                return jsonify({"message": "Failed to stop scraper.", "status": "error_stopping"}), 500
        else:
            logger.error("Stop event not initialized. Cannot stop scraper.")
            return jsonify({"message": "Cannot stop scraper: internal error (stop event missing).", "status": "error"}), 500

    @flask_app.route('/api/scraper/status', methods=['GET'])
    def get_scraper_status():
        global scraper_process
        if scraper_process and scraper_process.is_alive():
            return jsonify({"status": "running"}), 200
        return jsonify({"status": "stopped"}), 200

    @flask_app.route('/api/scraper/logs', methods=['GET'])
    def get_scraper_logs():
        try:
            num_lines = request.args.get('lines', default=100, type=int)
            if not os.path.exists(SCRAPER_LOG_FILE):
                return jsonify({"logs": ["Scraper log file not found."], "error": "Log file missing"}), 404
            
            lines = []
            with open(SCRAPER_LOG_FILE, 'r', encoding='utf-8') as f:
                from collections import deque
                lines = list(deque(f, num_lines))
            return jsonify({"logs": lines}), 200
        except Exception as e:
            logger.error(f"Error fetching scraper logs: {e}", exc_info=True)
            return jsonify({"logs": [], "error": str(e)}), 500

    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    logger.info("Shutting down Flask API server.")
    if scraper_process and scraper_process.is_alive():
        logger.info("Flask server exiting, attempting to stop active scraper process...")
        if stop_scraper_event: stop_scraper_event.set()
        scraper_process.terminate() 
        scraper_process.join(5)
    db_manager.close_db_pool()

def main():
    _setup_logging() 
    parser = argparse.ArgumentParser(description="Digital Twin for Smart Meter Demand Forecasting.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    setup_db_parser = subparsers.add_parser("setup-db", help="Creates/updates database tables.")
    setup_db_parser.set_defaults(func=setup_db_command)

    run_scraper_parser = subparsers.add_parser("run-scraper", help="Starts web scraping (direct run, not via API).")
    run_scraper_parser.set_defaults(func=run_scraper_command_cli) 

    run_simulation_parser = subparsers.add_parser("run-simulation", help="Runs digital twin simulation.")
    run_simulation_parser.add_argument("--meter-id",type=str,required=True,help="Meter ID for simulation.")
    run_simulation_parser.add_argument("--model",type=str,default="baseline_model",help="Forecasting model.")
    run_simulation_parser.add_argument("--duration-hours",type=int,default=2,help="Forecast horizon (hours).")
    run_simulation_parser.add_argument("--training-hours",type=int,default=24 * 7,help="Historical data for training (hours).")
    run_simulation_parser.add_argument("--prediction-start",type=str,help="Optional: Explicit prediction start (ISO).")
    run_simulation_parser.add_argument("--prediction-end",type=str,help="Optional: Explicit prediction end (ISO).")
    run_simulation_parser.set_defaults(func=run_simulation_command)

    api_server_parser = subparsers.add_parser("api-server", help="Starts the Flask API server with scraper controls.")
    api_server_parser.set_defaults(func=run_api_server_command)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        try:
            args.func(args)
        except Exception as e:
            logger.critical(f"Command '{args.command}' execution failed: {e}", exc_info=True)
    else:
        parser.print_help()

if __name__ == '__main__':
    multiprocessing.freeze_support() 
    main()