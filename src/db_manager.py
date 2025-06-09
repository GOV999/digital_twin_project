import logging
import os
from datetime import datetime, timedelta, timezone
from configparser import ConfigParser
from psycopg2 import pool
from psycopg2.extras import DictCursor

# --- Logging Setup for db_manager ---
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True) # Ensure logs directory exists
log_file = os.path.join(log_dir, 'db_manager.log')

# Create a logger for db_manager
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create file handler which logs even debug messages
fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO) # Or logging.DEBUG for more verbose console output

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add the handlers to the logger
# IMPORTANT: Check if handlers are already added to prevent duplicates when imported multiple times
if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)

# --- Global Database Pool ---
db_pool = None

def initialize_db_pool(db_config):
    """Initializes the PostgreSQL connection pool."""
    global db_pool
    if db_pool is None:
        try:
            logger.info("Initializing database connection pool...")
            db_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10, # Max connections for the pool
                host=db_config['db_host'],
                port=db_config['db_port'],
                database=db_config['db_name'],
                user=db_config['db_user'],
                password=db_config['db_password']
            )
            logger.info("Database connection pool initialized successfully.")
        except Exception as e:
            logger.exception(f"Failed to initialize database connection pool: {e}")
            raise # Re-raise the exception to stop execution if DB connection fails

def get_db_conn():
    """Gets a connection from the pool."""
    if db_pool is None:
        raise ConnectionError("Database pool is not initialized. Call initialize_db_pool first.")
    return db_pool.getconn()

def return_db_conn(conn):
    """Returns a connection to the pool."""
    if db_pool is not None and conn is not None:
        db_pool.putconn(conn)

def close_db_pool():
    """Closes all connections in the pool."""
    global db_pool
    if db_pool is not None:
        logger.info("Closing database connection pool.")
        db_pool.closeall()
        db_pool = None # Set to None after closing
        logger.info("Database connection pool closed.")

def insert_meter_readings(readings_data):
    """
    Inserts or updates meter and reading data into the database.
    Assumes readings_data is a list of dictionaries with keys like:
    'meter_no', 'timestamp', 'voltage_vrn', etc.
    """
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor(cursor_factory=DictCursor) as cur:
            for reading in readings_data:
                meter_no = reading.get('meter_no')
                timestamp = reading.get('timestamp')

                if not meter_no or not timestamp:
                    logger.warning(f"Skipping reading due to missing meter_no or timestamp: {reading}")
                    continue

                # 1. Insert into meters table (ON CONFLICT DO NOTHING to avoid duplicates)
                meter_id = meter_no # Using meter_no as meter_id for simplicity as discussed
                cur.execute(
                    """
                    INSERT INTO meters (meter_id, meter_no, location)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (meter_id) DO NOTHING;
                    """,
                    (meter_id, meter_no, 'Unknown Location') # You can update location later
                )

                # 2. Insert into readings table
                # Use ON CONFLICT (meter_id, timestamp) DO NOTHING
                # to prevent inserting duplicate readings for the same meter at the exact same time
                cur.execute(
                    """
                    INSERT INTO readings (
                        meter_id, timestamp, voltage_vrn, voltage_vyn, voltage_vbn,
                        current_ir, current_iy, current_ib, energy_kwh_import,
                        energy_kvah_import, energy_kwh_export, network_info
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (meter_id, timestamp) DO NOTHING;
                    """,
                    (
                        meter_id,
                        timestamp,
                        reading.get('voltage_vrn'),
                        reading.get('voltage_vyn'),
                        reading.get('voltage_vbn'),
                        reading.get('current_ir'),
                        reading.get('current_iy'),
                        reading.get('current_ib'),
                        reading.get('energy_kwh_import'),
                        reading.get('energy_kvah_import'),
                        reading.get('energy_kwh_export'),
                        reading.get('network_info')
                    )
                )
                # Check if a new row was actually inserted (rowcount > 0)
                if cur.rowcount > 0:
                    logger.info(f"Inserted new reading for Meter {meter_id} at {timestamp}.")
                else:
                    # If rowcount is 0, it means ON CONFLICT DO NOTHING was triggered
                    logger.debug(f"Reading for Meter {meter_id} at {timestamp} already exists, skipping.")

            conn.commit() # Commit all changes in the transaction
            logger.info(f"Successfully processed {len(readings_data)} readings for database insertion.")

    except Exception as e:
        if conn:
            conn.rollback() # Rollback in case of error
        logger.exception(f"Error during database insertion: {e}")
        raise # Re-raise to signal calling function of failure
    finally:
        if conn:
            return_db_conn(conn)

# Removed the if __name__ == "__main__": test block
# This file is now purely for functions to be imported by scraper.py