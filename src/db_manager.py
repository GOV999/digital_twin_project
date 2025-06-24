import logging
import os
from datetime import datetime, timedelta, timezone
from configparser import ConfigParser
from psycopg2 import pool
from psycopg2.extras import DictCursor
from psycopg2 import sql
import pytz
import uuid
from typing import List, Dict, Any, Optional
from decimal import Decimal # Import Decimal for conversion

# --- Logging Setup for db_manager ---
# This ensures logs specific to db_manager are handled
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'db_manager.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Prevent adding duplicate handlers if they already exist (e.g., from multiple imports)
if not logger.handlers:
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter) # Corrected this line in the previous response
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info("db_manager logging handlers added.")
else:
    logger.debug("db_manager logging handlers already present, skipping setup.")


# --- Global Database Pool and Configuration ---
DB_POOL = None
# Define the application's default timezone (e.g., Asia/Kolkata for IST)
APP_TIMEZONE = pytz.timezone('Asia/Kolkata')


def get_timezone() -> timezone:
    """Returns the application's configured timezone for consistency."""
    return APP_TIMEZONE

def get_db_config() -> Dict[str, Any]:
    """Reads database configuration from config.ini."""
    config = ConfigParser()
    # Path to config.ini, assuming it's in the project root (one level up from src/)
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')

    if not os.path.exists(config_path):
        logger.critical(f"Config file not found at {config_path}")
        raise FileNotFoundError(f"config.ini not found at {config_path}")

    config.read(config_path)

    try:
        # These keys should be under a [Database] section in config.ini
        db_host = config.get('Database', 'db_host')
        db_port = config.getint('Database', 'db_port')
        db_name = config.get('Database', 'db_name')
        db_user = config.get('Database', 'db_user')
        db_password = config.get('Database', 'db_password')
    except Exception as e:
        logger.critical(f"Missing or invalid database configuration in config.ini: {e}", exc_info=True)
        raise ValueError("Database configuration error in config.ini. Please check the [Database] section.")

    return {
        'host': db_host,
        'port': db_port,
        'database': db_name,
        'user': db_user,
        'password': db_password
    }

def initialize_db_pool():
    """
    Initializes the PostgreSQL connection pool.
    This function should be called once at application startup (e.g., in main.py's init_app function
    or at the start of a standalone script's main block).
    """
    global DB_POOL
    if DB_POOL is None:
        db_config = get_db_config()
        try:
            DB_POOL = pool.SimpleConnectionPool(
                minconn=1,  # Minimum connections to keep open
                maxconn=10, # Maximum connections to allow
                **db_config # Unpack the dictionary of database parameters
            )
            logger.info("Database connection pool initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize database connection pool: {e}", exc_info=True)
            raise # Re-raise the exception to propagate startup failure

def get_db_conn():
    """Retrieves a connection from the pool."""
    # If the pool hasn't been initialized yet, try to initialize it.
    # This provides some robustness for modules called in isolation.
    if DB_POOL is None:
        logger.warning("Database pool not initialized. Attempting to initialize now.")
        initialize_db_pool() # Call initialization if pool is None

    try:
        conn = DB_POOL.getconn()
        conn.autocommit = False # Ensure transactions are managed explicitly
        return conn
    except Exception as e:
        logger.error(f"Error getting connection from pool: {e}", exc_info=True)
        raise # Propagate connection retrieval errors

def return_db_conn(conn):
    """Returns a connection to the pool."""
    if DB_POOL is None:
        logger.warning("Attempted to return connection to an uninitialized pool. Connection will be discarded.")
        return
    try:
        # Rollback any outstanding transactions before returning to pool
        if not conn.autocommit:
            conn.rollback()
        DB_POOL.putconn(conn)
    except Exception as e:
        logger.error(f"Error returning connection to pool: {e}", exc_info=True)

def close_db_pool():
    """Closes all connections in the pool. Call this when application shuts down."""
    global DB_POOL
    if DB_POOL:
        try:
            DB_POOL.closeall()
            logger.info("Database connection pool closed.")
            DB_POOL = None # Reset the global variable
        except Exception as e:
            logger.error(f"Error closing database connection pool: {e}", exc_info=True)

def create_tables():
    """Creates meters, readings, forecast_runs, and forecast_predictions tables if they don't exist."""
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        # 1. Create the 'meters' table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meters (
                meter_id VARCHAR(50) PRIMARY KEY,
                meter_no VARCHAR(50) UNIQUE NOT NULL,
                location VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Table 'meters' ensured to exist.")

        # 2. Update existing 'meters' table with new columns if they are missing
        # This handles cases where the table exists from an older schema version.
        try:
            cur.execute("""
                ALTER TABLE meters ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                ALTER TABLE meters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            """)
            conn.commit() # Commit these alter operations immediately to ensure schema update
            logger.info("Ensured 'created_at' and 'updated_at' columns exist in 'meters' table.")
        except Exception as e:
            logger.warning(f"Could not alter 'meters' table (might already be up-to-date or other issue): {e}", exc_info=True)
            conn.rollback() # Rollback if alter failed, but continue with other tables

        # 3. Create the 'readings' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                reading_id SERIAL PRIMARY KEY,
                meter_id VARCHAR(50) NOT NULL REFERENCES meters(meter_id) ON DELETE CASCADE,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                voltage_vrn DECIMAL(10, 3),
                voltage_vyn DECIMAL(10, 3),
                voltage_vbn DECIMAL(10, 3),
                current_ir DECIMAL(10, 3),
                current_iy DECIMAL(10, 3),
                current_ib DECIMAL(10, 3),
                energy_kwh_import DECIMAL(15, 3),
                energy_kvah_import DECIMAL(15, 3),
                energy_kwh_export DECIMAL(15, 3),
                energy_kvah_export DECIMAL(15, 3),
                network_info VARCHAR(255),
                ingestion_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (meter_id, timestamp) -- Ensure unique readings per meter at a given timestamp
            );
        """)
        logger.info("Table 'readings' ensured to exist.")

        # 4. Create the 'forecast_runs' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecast_runs (
                run_id VARCHAR(255) PRIMARY KEY, -- Using VARCHAR to store UUID as string
                meter_id VARCHAR(50) NOT NULL REFERENCES meters(meter_id) ON DELETE CASCADE,
                model_name VARCHAR(100) NOT NULL,
                prediction_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                prediction_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
                training_data_start TIMESTAMP WITH TIME ZONE,
                training_data_end TIMESTAMP WITH TIME ZONE,
                mae DECIMAL(10, 4), -- Mean Absolute Error
                rmse DECIMAL(10, 4), -- Root Mean Squared Error
                run_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Table 'forecast_runs' ensured to exist.")

        # 5. Create the 'forecast_predictions' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecast_predictions (
                prediction_id SERIAL PRIMARY KEY,
                run_id VARCHAR(255) NOT NULL REFERENCES forecast_runs(run_id) ON DELETE CASCADE,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                predicted_kwh DECIMAL(15, 3) NOT NULL,
                actual_kwh DECIMAL(15, 3), -- Can be NULL if actuals aren't known for that time
                UNIQUE (run_id, timestamp) -- Ensure unique predictions per run at a given timestamp
            );
        """)
        logger.info("Table 'forecast_predictions' ensured to exist.")

        conn.commit() # Commit all table creation/alter operations
        logger.info("All database tables created/updated successfully.")

    except Exception as e:
        if conn:
            conn.rollback() # Rollback changes if any error occurs
        logger.critical(f"Error during table creation/update: {e}", exc_info=True)
        raise # Re-raise to indicate failure
    finally:
        if conn:
            return_db_conn(conn)

# In src/db_manager.py

# This function needs to handle the new meter_number column
def insert_meter_details(meter_id: str, meter_no: str, location: str):
    """
    Inserts new meter details or updates existing ones.
    This version correctly ACCEPTS ONLY 3 ARGUMENTS.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            # The SQL statement correctly references only columns that exist.
            cur.execute(
                """
                INSERT INTO meters (meter_id, meter_no, location, updated_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (meter_id) DO UPDATE SET
                    meter_no = EXCLUDED.meter_no,
                    location = EXCLUDED.location,
                    updated_at = CURRENT_TIMESTAMP;
                """,
                (meter_id, meter_no, location)
            )
            conn.commit()
            logger.info(f"Meter details for '{meter_id}' were successfully inserted or updated.")
    except Exception as e:
        if conn: conn.rollback()
        logger.error(f"Error inserting/updating meter details for {meter_id}: {e}", exc_info=True)
        raise
    finally:
        if conn: return_db_conn(conn)
            
def insert_meter_readings(readings_data: List[Dict[str, Any]]):
    """
    Inserts a list of meter readings into the database.
    Handles duplicates using ON CONFLICT DO NOTHING to prevent errors on re-insertion.
    """
    conn = None
    if not readings_data:
        logger.info("No readings data provided for insertion. Skipping.")
        return

    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            insert_query = sql.SQL("""
                INSERT INTO readings (
                    meter_id, timestamp, voltage_vrn, voltage_vyn, voltage_vbn,
                    current_ir, current_iy, current_ib, energy_kwh_import,
                    energy_kvah_import, energy_kwh_export, energy_kvah_export, network_info
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (meter_id, timestamp) DO NOTHING;
            """)

            records_to_insert = []
            for reading in readings_data:
                # Ensure timestamp is timezone-aware and converted to UTC for storage
                # If timestamp is naive (no tzinfo), assume it's in APP_TIMEZONE then convert to UTC
                timestamp_obj = reading['timestamp']
                if isinstance(timestamp_obj, datetime):
                    if timestamp_obj.tzinfo is None:
                        timestamp_utc = APP_TIMEZONE.localize(timestamp_obj).astimezone(timezone.utc)
                    else:
                        timestamp_utc = timestamp_obj.astimezone(timezone.utc)
                else:
                    timestamp_utc = timestamp_obj # If not datetime, pass as is (e.g., already string)

                records_to_insert.append(
                    (
                        reading.get('meter_id'),
                        timestamp_utc,
                        reading.get('voltage_vrn'),
                        reading.get('voltage_vyn'),
                        reading.get('voltage_vbn'),
                        reading.get('current_ir'),
                        reading.get('current_iy'),
                        reading.get('current_ib'),
                        reading.get('energy_kwh_import'),
                        reading.get('energy_kvah_import'),
                        reading.get('energy_kwh_export'),
                        reading.get('energy_kvah_export'),
                        reading.get('network_info')
                    )
                )

            if records_to_insert:
                cur.executemany(insert_query, records_to_insert)
                conn.commit()
                logger.info(f"Successfully processed {len(records_to_insert)} readings for database insertion. Inserted/skipped based on conflict.")
            else:
                logger.info("No valid readings to insert after processing.")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.exception(f"Error during database insertion of readings: {e}")
        raise # Re-raise to signal failure
    finally:
        if conn:
            return_db_conn(conn)

def insert_forecast_run(run_id: str, meter_id: str, model_name: str,
                        prediction_start_time: datetime, prediction_end_time: datetime,
                        training_data_start: Optional[datetime] = None, training_data_end: Optional[datetime] = None,
                        mae: Optional[float] = None, rmse: Optional[float] = None) -> str:
    """Inserts a new forecast run record and returns the generated run_id."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            # Ensure timestamps are UTC for database storage consistency
            prediction_start_time_utc = prediction_start_time.astimezone(timezone.utc)
            prediction_end_time_utc = prediction_end_time.astimezone(timezone.utc)
            training_data_start_utc = training_data_start.astimezone(timezone.utc) if training_data_start and training_data_start.tzinfo else APP_TIMEZONE.localize(training_data_start).astimezone(timezone.utc) if training_data_start else None
            training_data_end_utc = training_data_end.astimezone(timezone.utc) if training_data_end and training_data_end.tzinfo else APP_TIMEZONE.localize(training_data_end).astimezone(timezone.utc) if training_data_end else None


            cur.execute(
                """
                INSERT INTO forecast_runs (
                    run_id, meter_id, model_name, prediction_start_time, prediction_end_time,
                    training_data_start, training_data_end, mae, rmse
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING -- Prevents error if run_id somehow already exists
                RETURNING run_id;
                """,
                (run_id, meter_id, model_name,
                 prediction_start_time_utc, prediction_end_time_utc,
                 training_data_start_utc, training_data_end_utc, mae, rmse)
            )
            result = cur.fetchone()
            inserted_run_id = result[0] if result else None
            conn.commit()
            if inserted_run_id:
                logger.info(f"Forecast run '{inserted_run_id}' for meter '{meter_id}' inserted.")
            else:
                logger.debug(f"Forecast run '{run_id}' for meter '{meter_id}' already exists or was not inserted.")
            return run_id # Always return the passed run_id

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting forecast run {run_id}: {e}", exc_info=True)
        raise # Re-raise to signal failure
    finally:
        if conn:
            return_db_conn(conn)

def update_forecast_run_metrics(run_id: str, mae: Optional[float], rmse: Optional[float]) -> bool:
    """Updates the MAE and RMSE for an existing forecast run."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE forecast_runs
                SET mae = %s, rmse = %s, run_timestamp = CURRENT_TIMESTAMP -- Update run_timestamp on metric update
                WHERE run_id = %s;
                """,
                (mae, rmse, run_id)
            )
            conn.commit()
            if cur.rowcount > 0:
                logger.info(f"Updated metrics for forecast run ID: {run_id} (MAE: {mae}, RMSE: {rmse}).")
                return True
            else:
                logger.warning(f"No forecast run found with ID: {run_id} to update metrics for.")
                return False
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating metrics for forecast run {run_id}: {e}", exc_info=True)
        raise # Re-raise to signal failure
    finally:
        if conn:
            return_db_conn(conn)


def insert_forecast_predictions(run_id: str, predictions_data: List[Dict[str, Any]]):
    """Inserts a list of forecast predictions for a given run ID."""
    conn = None
    if not predictions_data:
        logger.info(f"No forecast predictions data provided for run {run_id}. Skipping insertion.")
        return

    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            insert_query = sql.SQL("""
                INSERT INTO forecast_predictions (run_id, timestamp, predicted_kwh, actual_kwh)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id, timestamp) DO UPDATE SET -- Update existing predictions if conflict
                    predicted_kwh = EXCLUDED.predicted_kwh,
                    actual_kwh = EXCLUDED.actual_kwh;
            """)
            records_to_insert = []
            for p in predictions_data:
                # Ensure timestamp is timezone-aware and converted to UTC for storage
                timestamp_obj = p['timestamp']
                if isinstance(timestamp_obj, datetime):
                    if timestamp_obj.tzinfo is None:
                        timestamp_utc = APP_TIMEZONE.localize(timestamp_obj).astimezone(timezone.utc)
                    else:
                        timestamp_utc = timestamp_obj.astimezone(timezone.utc)
                else:
                    timestamp_utc = timestamp_obj # If not datetime, pass as is (e.g., already string)

                records_to_insert.append(
                    (run_id, timestamp_utc, p['predicted_kwh'], p.get('actual_kwh'))
                )

            cur.executemany(insert_query, records_to_insert)
            conn.commit()
            logger.info(f"Successfully inserted/updated {len(records_to_insert)} forecast predictions for run '{run_id}'.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting forecast predictions for run {run_id}: {e}", exc_info=True)
        raise # Re-raise to signal failure
    finally:
        if conn:
            return_db_conn(conn)

# --- Data Retrieval Functions (for DataAnalyzer and DigitalTwin) ---

def get_latest_meter_readings_by_limit(meter_id: str, limit_count: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieves the latest 'limit_count' energy readings for a given meter ID,
    ordered by timestamp descending (most recent first).
    Returns a list of dictionaries with all relevant reading columns.
    Timestamps are converted to APP_TIMEZONE.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    reading_id, meter_id, timestamp,
                    voltage_vrn, voltage_vyn, voltage_vbn,
                    current_ir, current_iy, current_ib,
                    energy_kwh_import, energy_kvah_import, energy_kwh_export, energy_kvah_export,
                    network_info, ingestion_time
                FROM readings
                WHERE meter_id = %s
                ORDER BY timestamp DESC
                LIMIT %s;
                """,
                (meter_id, limit_count)
            )
            readings = cur.fetchall()
            
            # Process results: convert DictRow to dict, handle timezone and Decimal
            processed_readings = []
            for row in readings:
                row_dict = dict(row) # Convert DictRow to standard dict

                # Convert timestamp to APP_TIMEZONE
                if 'timestamp' in row_dict and isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].astimezone(APP_TIMEZONE)
                if 'ingestion_time' in row_dict and isinstance(row_dict['ingestion_time'], datetime):
                    row_dict['ingestion_time'] = row_dict['ingestion_time'].astimezone(APP_TIMEZONE)

                # Convert Decimal fields to float for JSON serialization
                for key, value in row_dict.items():
                    if isinstance(value, Decimal):
                        row_dict[key] = float(value)
                
                processed_readings.append(row_dict)

            logger.debug(f"Retrieved {len(processed_readings)} latest readings for meter {meter_id}.")
            return processed_readings
    except Exception as e:
        logger.error(f"Error fetching latest readings for meter {meter_id}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

def get_meter_readings_in_range(meter_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """
    Retrieves meter readings for a given meter ID within a specified time range.
    Returns a list of dictionaries with essential reading columns for forecasting.
    Timestamps are converted to APP_TIMEZONE.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Convert input times to UTC for database query consistency
            start_time_utc = start_time.astimezone(timezone.utc)
            end_time_utc = end_time.astimezone(timezone.utc)

            cur.execute(
                """
                SELECT
                    meter_id, timestamp,
                    energy_kwh_import, voltage_vrn, current_ir
                FROM readings
                WHERE meter_id = %s AND timestamp >= %s AND timestamp <= %s
                ORDER BY timestamp ASC;
                """,
                (meter_id, start_time_utc, end_time_utc)
            )
            readings = cur.fetchall()
            
            processed_readings = []
            for row in readings:
                row_dict = dict(row)
                if 'timestamp' in row_dict and isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].astimezone(APP_TIMEZONE)
                
                # Convert Decimal fields to float
                for key, value in row_dict.items():
                    if isinstance(value, Decimal):
                        row_dict[key] = float(value)
                
                processed_readings.append(row_dict)

            return processed_readings
    except Exception as e:
        logger.error(f"Error fetching historical readings for meter {meter_id} in range {start_time}-{end_time}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

def get_latest_forecast_run(meter_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the most recent forecast run record for a given meter ID.
    Timestamps in the result are converted to APP_TIMEZONE.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    run_id, meter_id, model_name, prediction_start_time, prediction_end_time,
                    training_data_start, training_data_end, mae, rmse, run_timestamp
                FROM forecast_runs
                WHERE meter_id = %s
                ORDER BY run_timestamp DESC
                LIMIT 1;
                """,
                (meter_id,)
            )
            latest_run = cur.fetchone()
            if latest_run:
                # Convert DictRow to dict
                result_dict = dict(latest_run)
                
                # Convert all relevant timestamps to APP_TIMEZONE
                for key in ['prediction_start_time', 'prediction_end_time', 'training_data_start', 'training_data_end', 'run_timestamp']:
                    if key in result_dict and isinstance(result_dict[key], datetime):
                        result_dict[key] = result_dict[key].astimezone(APP_TIMEZONE)
                
                # Convert Decimal fields to float
                for key in ['mae', 'rmse']:
                    if key in result_dict and isinstance(result_dict[key], Decimal):
                        result_dict[key] = float(result_dict[key])

                return result_dict
            return None
    except Exception as e:
        logger.error(f"Error fetching latest forecast run for meter {meter_id}: {e}", exc_info=True)
        return None
    finally:
        if conn:
            return_db_conn(conn)

def get_forecast_predictions(run_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all forecast predictions for a given forecast run ID.
    Timestamps are converted to APP_TIMEZONE.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    prediction_id, run_id, timestamp, predicted_kwh, actual_kwh
                FROM forecast_predictions
                WHERE run_id = %s
                ORDER BY timestamp ASC;
                """,
                (run_id,)
            )
            predictions = cur.fetchall()
            
            processed_predictions = []
            for row in predictions:
                row_dict = dict(row)
                if 'timestamp' in row_dict and isinstance(row_dict['timestamp'], datetime):
                    row_dict['timestamp'] = row_dict['timestamp'].astimezone(APP_TIMEZONE)
                
                # Convert Decimal fields to float
                for key in ['predicted_kwh', 'actual_kwh']:
                    if key in row_dict and isinstance(row_dict[key], Decimal):
                        row_dict[key] = float(row_dict[key])
                
                processed_predictions.append(row_dict)

            return processed_predictions
    except Exception as e:
        logger.error(f"Error fetching forecast predictions for run {run_id}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

def get_all_meter_details() -> List[Dict[str, Any]]:
    """
    Retrieves details for all meters in the database.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT meter_id, meter_no, location FROM meters ORDER BY meter_no ASC;
                """
            )
            meters = cur.fetchall()
            # No Decimal or complex datetime conversions typically needed here, but keeping it consistent
            return [dict(row) for row in meters]
    except Exception as e:
        logger.error(f"Error fetching all meter details: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

# This __main__ block is intentionally minimal as main.py handles global setup.
# It's primarily for quick, isolated testing of db_manager functions.
if __name__ == '__main__':
    # For standalone testing of db_manager.py, a basic logging setup is needed.
    # In normal app execution, main.py would configure this.
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("Running standalone db_manager test functions.")

    # Initialize the DB pool for this standalone run
    try:
        initialize_db_pool() # Call the correct initialization function
        create_tables() # Ensure tables exist for testing

        # --- Basic Test Sequence ---
        test_meter_id = "test_meter_" + str(uuid.uuid4())[:8] # Unique ID for testing
        test_meter_no = "TM-XYZ-999"
        test_location = "Test Lab"

        # Test insert_meter_details (which includes upsert logic)
        logger.info(f"\n--- Testing insert_meter_details for {test_meter_id} ---")
        insert_meter_details(test_meter_id, test_meter_no, test_location)

        # Test insert_meter_readings
        logger.info(f"\n--- Testing insert_meter_readings for {test_meter_id} ---")
        now_utc = datetime.now(timezone.utc)
        # Create a naive datetime in APP_TIMEZONE for testing the conversion logic
        now_app_tz = now_utc.astimezone(APP_TIMEZONE)
        
        test_readings = [
            {'meter_id': test_meter_id, 'timestamp': (now_app_tz - timedelta(minutes=45)).replace(tzinfo=None), 'energy_kwh_import': Decimal('10.5'), 'voltage_vrn': Decimal('230.1'), 'current_ir': Decimal('0.1')},
            {'meter_id': test_meter_id, 'timestamp': (now_app_tz - timedelta(minutes=30)).replace(tzinfo=None), 'energy_kwh_import': Decimal('11.2'), 'voltage_vrn': Decimal('230.5'), 'current_ir': Decimal('0.11')},
            {'meter_id': test_meter_id, 'timestamp': (now_app_tz - timedelta(minutes=15)).replace(tzinfo=None), 'energy_kwh_import': Decimal('10.8'), 'voltage_vrn': Decimal('229.8'), 'current_ir': Decimal('0.12')},
            {'meter_id': test_meter_id, 'timestamp': now_app_tz.replace(tzinfo=None), 'energy_kwh_import': Decimal('11.5'), 'voltage_vrn': Decimal('231.0'), 'current_ir': Decimal('0.13')},
        ]
        insert_meter_readings(test_readings)

        # Test get_latest_meter_readings_by_limit
        logger.info(f"\n--- Testing get_latest_meter_readings_by_limit for {test_meter_id} ---")
        latest = get_latest_meter_readings_by_limit(test_meter_id, limit_count=2)
        for r in latest:
            # All fields should now be present and Decimals converted to float
            logger.info(f"  Latest Reading: {r['timestamp']} - {r['energy_kwh_import']} kWh (Voltage: {r['voltage_vrn']}) - Type of energy_kwh_import: {type(r['energy_kwh_import'])}")

        # Test get_meter_readings_in_range
        logger.info(f"\n--- Testing get_meter_readings_in_range for {test_meter_id} ---")
        historical_start = (now_app_tz - timedelta(hours=1))
        historical_end = now_app_tz + timedelta(minutes=1) # Small buffer to include last reading
        
        historical = get_meter_readings_in_range(test_meter_id, historical_start, historical_end)
        for r in historical:
            logger.info(f"  Historical Reading: {r['timestamp']} - {r['energy_kwh_import']} kWh (Voltage: {r['voltage_vrn']}) - Type of energy_kwh_import: {type(r['energy_kwh_import'])}")

        # Test forecast run and predictions
        logger.info(f"\n--- Testing forecast run and predictions for {test_meter_id} ---")
        pred_start = now_app_tz + timedelta(minutes=15)
        pred_end = now_app_tz + timedelta(hours=1, minutes=15)

        # Note: MAE/RMSE are mock values for this test as there's no actual model run
        test_run_id = str(uuid.uuid4()) # Generate UUID here, pass as string
        insert_forecast_run(
            run_id=test_run_id, # Pass the generated run_id
            meter_id=test_meter_id, model_name="test_model",
            prediction_start_time=pred_start, # Already in APP_TIMEZONE, will be converted to UTC in function
            prediction_end_time=pred_end,     # Already in APP_TIMEZONE, will be converted to UTC in function
            training_data_start=now_app_tz - timedelta(hours=2), training_data_end=now_app_tz,
            mae=0.5, rmse=0.7 # Mock MAE/RMSE for initial insert
        )

        test_predictions = [
            {'timestamp': pred_start, 'predicted_kwh': Decimal('12.0'), 'actual_kwh': None},
            {'timestamp': pred_start + timedelta(minutes=15), 'predicted_kwh': Decimal('12.1'), 'actual_kwh': None}
        ]
        insert_forecast_predictions(test_run_id, test_predictions)
        update_forecast_run_metrics(test_run_id, 0.6, 0.8) # Update with some mock metrics

        # Test get_latest_forecast_run and get_forecast_predictions
        latest_run = get_latest_forecast_run(test_meter_id)
        if latest_run:
            logger.info(f"\n--- Latest Forecast Run: {latest_run['run_id']} ---")
            logger.info(f"  Model: {latest_run['model_name']}, MAE: {latest_run['mae']}, RMSE: {latest_run['rmse']}")
            logger.info(f"  Type of MAE: {type(latest_run['mae'])}, Type of RMSE: {type(latest_run['rmse'])}")
            predictions_for_run = get_forecast_predictions(latest_run['run_id'])
            for p in predictions_for_run:
                logger.info(f"  Prediction: {p['timestamp']} - {p['predicted_kwh']} kWh (Actual: {p['actual_kwh']})")
                logger.info(f"  Type of predicted_kwh: {type(p['predicted_kwh'])}")

        # Test get_all_meter_details
        logger.info(f"\n--- Testing get_all_meter_details ---")
        all_meters = get_all_meter_details()
        for m in all_meters:
            logger.info(f"  Meter: {m['meter_id']} ({m['meter_no']}) at {m['location']}")


    except Exception as e:
        logger.error(f"Error during standalone db_manager test: {e}", exc_info=True)
    finally:
        # Close the DB pool when done
        close_db_pool()
        logger.info("Standalone db_manager test finished.")