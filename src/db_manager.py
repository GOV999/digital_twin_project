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

# --- Logging Setup for db_manager ---
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'db_manager.log')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.info("db_manager logging handlers added.")
else:
    logger.debug("db_manager logging handlers already present, skipping setup.")


# --- Global Database Pool and Configuration ---
DB_POOL = None
APP_TIMEZONE = pytz.timezone('Asia/Kolkata')


def get_timezone() -> timezone:
    """Returns the application's configured timezone for consistency."""
    return APP_TIMEZONE

def get_db_config() -> Dict[str, Any]:
    """Reads database configuration from config.ini."""
    config = ConfigParser()
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.ini')
    
    if not os.path.exists(config_path):
        logger.critical(f"Config file not found at {config_path}")
        raise FileNotFoundError(f"config.ini not found at {config_path}")
    
    config.read(config_path)

    try:
        db_host = config.get('Database', 'db_host')
        db_port = config.getint('Database', 'db_port')
        db_name = config.get('Database', 'db_name')
        db_user = config.get('Database', 'db_user')
        db_password = config.get('Database', 'db_password')
    except Exception as e:
        logger.critical(f"Missing or invalid database configuration in config.ini: {e}", exc_info=True)
        raise ValueError("Database configuration error in config.ini")

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
    Should be called once at application startup (e.g., in main.py).
    """
    global DB_POOL
    if DB_POOL is None:
        db_config = get_db_config()
        try:
            DB_POOL = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                **db_config
            )
            logger.info("Database connection pool initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize database connection pool: {e}", exc_info=True)
            raise

def get_db_conn():
    """Retrieves a connection from the pool."""
    if DB_POOL is None:
        initialize_db_pool()
    try:
        conn = DB_POOL.getconn()
        conn.autocommit = False
        return conn
    except Exception as e:
        logger.error(f"Error getting connection from pool: {e}", exc_info=True)
        raise

def return_db_conn(conn):
    """Returns a connection to the pool."""
    if DB_POOL is None:
        logger.warning("Attempted to return connection to an uninitialized pool.")
        return
    try:
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
            DB_POOL = None
        except Exception as e:
            logger.error(f"Error closing database connection pool: {e}", exc_info=True)

def create_tables():
    """Creates meters, readings, forecast_runs, and forecast_predictions tables if they don't exist."""
    conn = None
    try:
        conn = get_db_conn()
        cur = conn.cursor()

        # 1. Create the 'meters' table if not exists
        # This will create the table with the defined schema IF it doesn't exist at all.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS meters (
                meter_id VARCHAR(50) PRIMARY KEY,
                meter_no VARCHAR(50) UNIQUE NOT NULL,
                location VARCHAR(100),
                created_at TIMESTAMP WITH TIME ZONE,
                updated_at TIMESTAMP WITH TIME ZONE
            );
        """)
        logger.info("Table 'meters' ensured to exist.")

        # 2. Add missing columns to 'meters' table if they don't exist
        # This handles cases where the table exists from an older schema version.
        try:
            cur.execute("""
                ALTER TABLE meters ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
                ALTER TABLE meters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
            """)
            conn.commit() # Commit these alter operations immediately
            logger.info("Ensured 'created_at' and 'updated_at' columns exist in 'meters' table.")
        except Exception as e:
            logger.warning(f"Could not alter 'meters' table (might already be up-to-date or other issue): {e}", exc_info=True)
            conn.rollback() # Rollback if alter failed, but keep trying other tables

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
                UNIQUE (meter_id, timestamp)
            );
        """)
        logger.info("Table 'readings' ensured to exist.")

        # 4. Create the 'forecast_runs' table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS forecast_runs (
                run_id VARCHAR(255) PRIMARY KEY,
                meter_id VARCHAR(50) NOT NULL REFERENCES meters(meter_id) ON DELETE CASCADE,
                model_name VARCHAR(100) NOT NULL,
                prediction_start_time TIMESTAMP WITH TIME ZONE NOT NULL,
                prediction_end_time TIMESTAMP WITH TIME ZONE NOT NULL,
                training_data_start TIMESTAMP WITH TIME ZONE,
                training_data_end TIMESTAMP WITH TIME ZONE,
                mae DECIMAL(10, 4),
                rmse DECIMAL(10, 4),
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
                actual_kwh DECIMAL(15, 3),
                UNIQUE (run_id, timestamp)
            );
        """)
        logger.info("Table 'forecast_predictions' ensured to exist.")

        conn.commit()
        logger.info("All database tables created/updated successfully.")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.critical(f"Error during table creation/update: {e}", exc_info=True)
        raise
    finally:
        if conn:
            return_db_conn(conn)

def insert_meter_details(meter_id: str, meter_no: str, location: str = None):
    """
    Inserts new meter details or updates existing ones if meter_id already exists.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO meters (meter_id, meter_no, location, updated_at, created_at)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP, COALESCE((SELECT created_at FROM meters WHERE meter_id = %s), CURRENT_TIMESTAMP))
                ON CONFLICT (meter_id) DO UPDATE SET
                    meter_no = EXCLUDED.meter_no,
                    location = EXCLUDED.location,
                    updated_at = EXCLUDED.updated_at
                RETURNING meter_id;
                """,
                (meter_id, meter_no, location, meter_id) # Pass meter_id again for COALESCE
            )
            inserted_id = cur.fetchone()[0]
            conn.commit()
            logger.info(f"Meter details for '{inserted_id}' inserted/updated.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting/updating meter details for {meter_id}: {e}", exc_info=True)
        raise
    finally:
        if conn:
            return_db_conn(conn)

def insert_meter_readings(readings_data: List[Dict[str, Any]]):
    """
    Inserts a list of meter readings into the database.
    Handles duplicates using ON CONFLICT DO NOTHING.
    """
    conn = None
    if not readings_data:
        logger.info("No readings data provided for insertion.")
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
                timestamp_utc = reading['timestamp'].astimezone(timezone.utc)
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
                logger.info("No readings to insert.")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.exception(f"Error during database insertion: {e}")
        raise
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
            prediction_start_time_utc = prediction_start_time.astimezone(timezone.utc)
            prediction_end_time_utc = prediction_end_time.astimezone(timezone.utc)
            training_data_start_utc = training_data_start.astimezone(timezone.utc) if training_data_start else None
            training_data_end_utc = training_data_end.astimezone(timezone.utc) if training_data_end else None

            cur.execute(
                """
                INSERT INTO forecast_runs (
                    run_id, meter_id, model_name, prediction_start_time, prediction_end_time,
                    training_data_start, training_data_end, mae, rmse
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (run_id) DO NOTHING
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
                logger.debug(f"Forecast run '{run_id}' for meter '{meter_id}' already exists, skipping insertion.")
            return run_id

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting forecast run {run_id}: {e}", exc_info=True)
        raise
    finally:
        if conn:
            return_db_conn(conn)

def insert_forecast_predictions(run_id: str, predictions_data: List[Dict[str, Any]]):
    """Inserts a list of forecast predictions for a given run ID."""
    conn = None
    if not predictions_data:
        logger.info(f"No forecast predictions data provided for run {run_id}.")
        return

    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            insert_query = sql.SQL("""
                INSERT INTO forecast_predictions (run_id, timestamp, predicted_kwh, actual_kwh)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (run_id, timestamp) DO NOTHING;
            """)
            records_to_insert = []
            for p in predictions_data:
                timestamp_utc = p['timestamp'].astimezone(timezone.utc) if isinstance(p['timestamp'], datetime) else p['timestamp']
                records_to_insert.append(
                    (run_id, timestamp_utc, p['predicted_kwh'], p.get('actual_kwh'))
                )

            cur.executemany(insert_query, records_to_insert)
            conn.commit()
            logger.info(f"Successfully inserted {len(records_to_insert)} forecast predictions for run '{run_id}'.")
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error inserting forecast predictions for run {run_id}: {e}", exc_info=True)
        raise
    finally:
        if conn:
            return_db_conn(conn)

# --- Data Retrieval Functions (for DataAnalyzer) ---

def get_latest_meter_readings_by_limit(meter_id: str, limit_count: int = 20) -> List[Dict[str, Any]]:
    """
    Retrieves the latest 'limit_count' energy readings for a given meter ID,
    ordered by timestamp descending (most recent first).
    Returns a list of dictionaries with all relevant reading columns.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute(
                """
                SELECT
                    meter_id, timestamp,
                    voltage_vrn, voltage_vyn, voltage_vbn,
                    current_ir, current_iy, current_ib,
                    energy_kwh_import, energy_kvah_import, energy_kwh_export, energy_kvah_export,
                    network_info
                FROM readings
                WHERE meter_id = %s
                ORDER BY timestamp DESC
                LIMIT %s;
                """,
                (meter_id, limit_count)
            )
            readings = cur.fetchall()
            return [dict(row) for row in readings]
    except Exception as e:
        logger.error(f"Error fetching latest readings for meter {meter_id}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

def get_meter_readings_in_range(meter_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """
    Retrieves meter readings for a given meter ID within a specified time range.
    Returns a list of dictionaries with all relevant reading columns.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
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
            return [dict(row) for row in readings]
    except Exception as e:
        logger.error(f"Error fetching historical readings for meter {meter_id} in range {start_time}-{end_time}: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)

def get_latest_forecast_run(meter_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the most recent forecast run record for a given meter ID.
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
            return dict(latest_run) if latest_run else None
    except Exception as e:
        logger.error(f"Error fetching latest forecast run for meter {meter_id}: {e}", exc_info=True)
        return None
    finally:
        if conn:
            return_db_conn(conn)

def get_forecast_predictions(run_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all forecast predictions for a given forecast run ID.
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
            return [dict(row) for row in predictions]
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
            return [dict(row) for row in meters]
    except Exception as e:
        logger.error(f"Error fetching all meter details: {e}", exc_info=True)
        return []
    finally:
        if conn:
            return_db_conn(conn)
