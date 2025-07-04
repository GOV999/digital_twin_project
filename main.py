import argparse
import configparser
import logging
import logging.handlers
import os
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse
import sys
import json
from flask import Flask, jsonify, request
from flask_cors import CORS
import pytz
from decimal import Decimal
import multiprocessing 
from multiprocessing import Queue
import time 
from typing import Optional, List, Dict, Any

# Adjust the Python path to import modules from 'src'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src import db_manager, scraper 
from src.digital_twin import DigitalTwin
from src.data_analyzer import DataAnalyzer

# --- Configuration & Path Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
SCRAPER_LOG_FILE = os.path.join(LOG_DIR, 'scraper.log') 
os.makedirs(LOG_DIR, exist_ok=True)
app_config = configparser.ConfigParser()

# --- Flask App Initialization & Globals ---
flask_app = Flask(__name__)
CORS(flask_app)
data_analyzer_instance = None
APP_TIMEZONE = pytz.timezone('Asia/Kolkata')
scraper_processes: Dict[str, multiprocessing.Process] = {}
stop_scraper_events: Dict[str, multiprocessing.Event] = {}
logger = logging.getLogger(__name__)

# --- Custom JSON Encoder ---
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

# --- Helper Functions ---
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
    logger.info("Global logging configured.")

def _load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"config.ini not found at {CONFIG_PATH}")
    app_config.read(CONFIG_PATH)
    logger.info("Configuration loaded successfully.")

def get_configured_meters() -> List[Dict[str, str]]:
    meters = []
    if 'ConfiguredMeters' in app_config:
        for meter_id, value_str in app_config['ConfiguredMeters'].items():
            try:
                name, meter_number, location = [v.strip() for v in value_str.split(',')]
                meters.append({
                    "meter_id": meter_id,
                    "name": name,
                    "meter_number": meter_number,
                    "location": location,
                    "meter_no": f"SN-{meter_id}"
                })
            except ValueError:
                logger.warning(f"Skipping malformed meter config for id {meter_id}: '{value_str}'")
    else:
        logger.warning("[ConfiguredMeters] section not found in config file.")
    return meters

# --- Custom Log Formatter Class ---
class MeterLogFormatter(logging.Formatter):
    """
    A custom log formatter that includes a meter_id if present,
    but doesn't fail if it's missing.
    """
    def format(self, record):
        if hasattr(record, 'meter_id'):
            self._style._fmt = '%(asctime)s - (Meter %(meter_id)s) - %(name)s - %(levelname)s - %(message)s'
        else:
            self._style._fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        return super().format(record)

def log_listener_process(queue: Queue, log_file: str):
    formatter = MeterLogFormatter()
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    
    while True:
        try:
            record = queue.get()
            if record is None:
                break
            logger_for_record = logging.getLogger(record.name)
            logger_for_record.propagate = False
            logger_for_record.addHandler(file_handler)
            logger_for_record.handle(record)
            logger_for_record.removeHandler(file_handler)
        except Exception:
            import sys, traceback
            print('Error in log listener:', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

def run_scraper_process(meter_id: str, meter_number: str, meter_no: str, stop_event_param: multiprocessing.Event, log_queue: Queue):
    try:
        scraper.main(
            meter_id=meter_id, 
            meter_number=meter_number,
            meter_no=meter_no, 
            stop_event=stop_event_param,
            log_queue=log_queue
        )
    except Exception as e:
        logging.error(f"Exception in scraper process wrapper for meter {meter_id}: {e}", exc_info=True)

# --- CLI Command Functions ---
def run_scraper_command_cli(args):
    configured_meters = get_configured_meters()
    if not configured_meters:
        logger.error("No meters found in [ConfiguredMeters] section of config.ini. Cannot run scraper.")
        return
    first_meter = configured_meters[0]
    logger.info(f"Starting scraper via CLI command for first meter: {first_meter['meter_id']}")
    db_manager.initialize_db_pool()
    try:
        scraper.main(
            meter_id=first_meter['meter_id'],
            meter_number=first_meter['meter_number'],
            meter_no=first_meter['meter_no']
        )
    finally:
        db_manager.close_db_pool()

def run_simulation_command(args):
    db_manager.initialize_db_pool()
    try:
        twin = DigitalTwin(meter_id=args.meter_id)
        twin.run_simulation(
            simulation_duration_hours=args.duration_hours,
            prediction_horizon_hours=args.duration_hours,
            model_name=args.model,
            data_for_training_hours=args.training_hours
        )
    finally:
        db_manager.close_db_pool()

def setup_db_command(args):
    db_manager.initialize_db_pool()
    try:
        db_manager.create_tables()
        logger.info("Database setup complete.")
    finally:
        db_manager.close_db_pool()

# --- Main API Server Function ---
def run_api_server_command(args):
    global data_analyzer_instance

    log_queue = multiprocessing.Queue(-1)
    listener_process = multiprocessing.Process(target=log_listener_process, args=(log_queue, SCRAPER_LOG_FILE))
    listener_process.daemon = True
    listener_process.start()
    logger.info("Log listener process started.")

    db_manager.initialize_db_pool()
    data_analyzer_instance = DataAnalyzer()
    
    # --- API Endpoints ---
    @flask_app.route('/api/config/meters', methods=['GET'])
    def get_configured_meters_endpoint():
        return jsonify(get_configured_meters())

    @flask_app.route('/api/meters/<meter_id>/latest_readings', methods=['GET'])
    def get_latest_readings(meter_id):
        return jsonify(data_analyzer_instance.get_latest_readings(meter_id, request.args.get('limit', 10, type=int)))

    @flask_app.route('/api/meters/<meter_id>/historical_data', methods=['GET'])
    def get_historical_data(meter_id):
        return jsonify(data_analyzer_instance.get_historical_data(meter_id, request.args.get('hours', 24*7, type=int)))

    @flask_app.route('/api/meters/<meter_id>/latest_forecast', methods=['GET'])
    def get_latest_forecast(meter_id):
        return jsonify(data_analyzer_instance.get_latest_forecast(meter_id))

    @flask_app.route('/api/meters/<meter_id>/latest_forecast_details', methods=['GET'])
    def get_latest_forecast_details(meter_id):
        run_details = data_analyzer_instance.get_latest_forecast_run_details(meter_id)
        if run_details is None: return jsonify({})
        if 'mae' in run_details and isinstance(run_details['mae'], float) and run_details['mae'] != run_details['mae']:
            run_details['mae'] = None
        if 'rmse' in run_details and isinstance(run_details['rmse'], float) and run_details['rmse'] != run_details['rmse']:
            run_details['rmse'] = None
        return jsonify(run_details)

    
    @flask_app.route('/api/meters/<meter_id>/simulate', methods=['POST'])
    def trigger_simulation_endpoint(meter_id):
        """
        Triggers a forecasting simulation for a given meter.
        This single endpoint handles both standard forecasts and event-based backtests.
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({"message": "Request body must be JSON.", "status": "error"}), 400

            # --- Extract all possible parameters ---
            model_name = str(data.get('model_name', "baseline_model"))
            training_hours = int(data.get('training_hours', 24 * 14)) # Default to 2 weeks
            duration_hours = int(data.get('duration_hours', 24))
            event_data = data.get('event', None)
            start_time_str = data.get('explicit_prediction_start_time', None)
            end_time_str = data.get('explicit_prediction_end_time', None)
            
            # --- Prepare arguments dictionary for the DigitalTwin ---
            kwargs_for_simulation = {
                "model_name": model_name,
                "data_for_training_hours": training_hours,
                "event_data": event_data,
            }

            # --- Logic to differentiate between a backtest and a standard forecast ---
            if start_time_str and end_time_str:
                logger.info(f"Received backtest/event simulation request for meter '{meter_id}'.")
                
                start_time = isoparse(start_time_str)
                end_time = isoparse(end_time_str)
                
                # --- THIS IS THE FIX: Localize naive datetimes from the frontend ---
                app_tz = db_manager.get_timezone()
                if start_time.tzinfo is None:
                    start_time = app_tz.localize(start_time)
                    logger.info(f"Localized naive start_time to: {start_time}")
                if end_time.tzinfo is None:
                    end_time = app_tz.localize(end_time)
                    logger.info(f"Localized naive end_time to: {end_time}")

                kwargs_for_simulation['explicit_prediction_start_time'] = start_time
                kwargs_for_simulation['explicit_prediction_end_time'] = end_time
            else:
                logger.info(f"Received standard forecast request for meter '{meter_id}'.")
                kwargs_for_simulation['simulation_duration_hours'] = duration_hours
                kwargs_for_simulation['prediction_horizon_hours'] = duration_hours

            # Enforce minimum training data for the DL model
            if model_name == 'dl_model' and kwargs_for_simulation.get("data_for_training_hours", 0) < 168:
                logger.warning(f"DL model requested; increasing training data to minimum of 168 hours.")
                kwargs_for_simulation['data_for_training_hours'] = 168

            # --- Run the simulation ---
            twin = DigitalTwin(meter_id=meter_id)
            results = twin.run_simulation(**kwargs_for_simulation)
            
            # --- Process and return results ---
            simulation_metrics = results.get('metrics', {})
            # NaN handling
            if 'mae' in simulation_metrics and isinstance(simulation_metrics['mae'], float) and simulation_metrics['mae'] != simulation_metrics['mae']:
                simulation_metrics['mae'] = None
            if 'rmse' in simulation_metrics and isinstance(simulation_metrics['rmse'], float) and simulation_metrics['rmse'] != simulation_metrics['rmse']:
                simulation_metrics['rmse'] = None

            response_data = {
                "message": "Simulation completed successfully.",
                "status": "success",
                "run_id": results.get('run_id'),
                "metrics": simulation_metrics,
                "model_requested": results.get('model_requested'),
                "model_used": results.get('model_used'),
                "fallback_reason": results.get('fallback_reason'),
                "forecast_points": results.get('simulated_readings'),
                "actual_readings_in_sim_range": results.get('actual_readings_in_sim_range'),
                "simulation_start": results.get('simulation_start'),
                "simulation_end": results.get('simulation_end')
            }
            
            return jsonify(response_data), 200

        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Simulation for '{meter_id}' failed with a client data error: {str(e)}", exc_info=True)
            return jsonify({"message": f"Invalid request parameter or data: {str(e)}", "status": "error"}), 400
            
        except Exception as e:
            logger.error(f"Unhandled error during simulation for meter '{meter_id}': {e}", exc_info=True)
            return jsonify({"message": "An internal server error occurred during the simulation.", "status": "error"}), 500
                    
    @flask_app.route('/api/scraper/start', methods=['POST'])
    def start_scraper_endpoint():
        data = request.get_json()
        meter_id = data.get('meter_id')
        if not meter_id: return jsonify({"message": "meter_id is required"}), 400

        if meter_id in scraper_processes and scraper_processes[meter_id].is_alive():
            return jsonify({"message": f"Scraper for {meter_id} is already running."}), 409

        meter_to_start = next((m for m in get_configured_meters() if m['meter_id'] == meter_id), None)
        if not meter_to_start:
            return jsonify({"message": f"Meter {meter_id} not found in configuration."}), 404
            
        try:
            db_manager.insert_meter_details(
                meter_id=meter_to_start['meter_id'],
                meter_no=meter_to_start['meter_no'],
                location=meter_to_start['location']
            )
        except Exception as e:
            return jsonify({"message": f"Database error preparing meter: {str(e)}", "status": "error"}), 500

        stop_scraper_events[meter_id] = multiprocessing.Event()
        process = multiprocessing.Process(
            target=run_scraper_process,
            args=(
                meter_to_start['meter_id'], 
                meter_to_start['meter_number'],
                meter_to_start['meter_no'], 
                stop_scraper_events[meter_id],
                log_queue
            )
        )
        process.daemon = True
        process.start()
        scraper_processes[meter_id] = process
        return jsonify({"message": f"Scraper for {meter_id} started.", "status": "running"}), 200

    @flask_app.route('/api/scraper/stop', methods=['POST'])
    def stop_scraper_endpoint():
        data = request.get_json()
        meter_id = data.get('meter_id')
        if not meter_id: return jsonify({"message": "meter_id is required"}), 400
        
        process = scraper_processes.get(meter_id)
        if not process or not process.is_alive():
            return jsonify({"message": f"Scraper for {meter_id} is not running.", "status": "stopped"}), 200

        stop_event = stop_scraper_events.get(meter_id)
        if stop_event:
            stop_event.set()
            process.join(timeout=30)
            if process.is_alive():
                process.terminate(); process.join(5)
            del scraper_processes[meter_id]
            del stop_scraper_events[meter_id]
            return jsonify({"message": f"Scraper for {meter_id} stopped.", "status": "stopped"}), 200
        return jsonify({"message": "Cannot stop scraper: internal error."}), 500

    @flask_app.route('/api/scraper/status', methods=['GET'])
    def get_scraper_status():
        statuses = {}
        for meter in get_configured_meters():
            meter_id = meter['meter_id']
            process = scraper_processes.get(meter_id)
            statuses[meter_id] = "running" if process and process.is_alive() else "stopped"
        return jsonify({"statuses": statuses}), 200

    @flask_app.route('/api/scraper/logs', methods=['GET'])
    def get_scraper_logs():
        meter_id = request.args.get('meter_id')
        if not meter_id:
            return jsonify({"logs": ["Error: meter_id is required to fetch logs."], "error": "Missing parameter"}), 400
        
        # This endpoint now reads from the single, shared log file
        num_lines = request.args.get('lines', default=150, type=int)
        if not os.path.exists(SCRAPER_LOG_FILE):
            return jsonify({"logs": ["Scraper log file not found."], "error": "Log file missing"}), 404
        
        with open(SCRAPER_LOG_FILE, 'r', encoding='utf-8') as f:
            from collections import deque
            lines = list(deque(f, num_lines))
        return jsonify({"logs": lines}), 200
    
    flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    
    logger.info("Shutting down Flask API server.")
    for meter_id, process in list(scraper_processes.items()):
        if process.is_alive():
            logger.info(f"Stopping active scraper for meter {meter_id}...")
            if meter_id in stop_scraper_events: stop_scraper_events[meter_id].set()
            process.terminate(); process.join(5)
            
    log_queue.put(None)
    listener_process.join()
    logger.info("Log listener process stopped.")
    
    db_manager.close_db_pool()


# --- Main Entry Point ---
def main():
    _setup_logging()
    _load_config()
    
    parser = argparse.ArgumentParser(description="Digital Twin for Smart Meter Demand Forecasting.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands", required=True)

    setup_db_parser = subparsers.add_parser("setup-db", help="Creates/updates database tables.")
    setup_db_parser.set_defaults(func=setup_db_command)

    run_scraper_parser = subparsers.add_parser("run-scraper", help="Starts web scraping for the first configured meter.")
    run_scraper_parser.set_defaults(func=run_scraper_command_cli) 

    run_simulation_parser = subparsers.add_parser("run-simulation", help="Runs digital twin simulation.")
    run_simulation_parser.add_argument("--meter-id",type=str,required=True,help="Meter ID for simulation.")
    run_simulation_parser.add_argument("--model",type=str,default="baseline_model",help="Forecasting model.")
    run_simulation_parser.add_argument("--duration-hours",type=int,default=2,help="Forecast horizon (hours).")
    run_simulation_parser.add_argument("--training-hours",type=int,default=24*7,help="Historical data for training (hours).")
    run_simulation_parser.set_defaults(func=run_simulation_command)

    api_server_parser = subparsers.add_parser("api-server", help="Starts the Flask API server with scraper controls.")
    api_server_parser.set_defaults(func=run_api_server_command)

    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    multiprocessing.freeze_support() 
    main()