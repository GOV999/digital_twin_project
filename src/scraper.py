import os
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import configparser
import time
import pytz
import multiprocessing
import sys
from typing import Optional, List, Dict

# Import your custom database manager
from . import db_manager

# --- Configuration & Path Setup ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_DUMPS_DIR = os.path.join(BASE_DIR, 'debug_dumps')
SCREENSHOT_DIR = os.path.join(DEBUG_DUMPS_DIR, 'screenshots')
PAGE_SOURCE_DIR = os.path.join(DEBUG_DUMPS_DIR, 'page_sources')
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(PAGE_SOURCE_DIR, exist_ok=True)
logger = logging.getLogger(__name__)

config = configparser.ConfigParser()
config_path = os.path.join(BASE_DIR, 'config.ini')

# --- Load non-meter-specific configurations ---
LOGIN_URL = ""
TARGET_DASHBOARD_URL_CONFIG = ""
BASE_METER_DETAILS_URL = ""
RELOAD_INTERVAL_SECONDS = 300
WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS = 300
WAIT_FOR_DASHBOARD_POLL_SECONDS = 5

if not os.path.exists(config_path):
    logger.critical(f"CRITICAL: config.ini not found at {config_path}. Scraper will not run.")
else:
    try:
        config.read(config_path)
        LOGIN_URL = config.get('Scraper', 'login_url', fallback="LOGIN_URL_NOT_SET")
        TARGET_DASHBOARD_URL_CONFIG = config.get('Scraper', 'target_dashboard_url', fallback="TARGET_DASHBOARD_URL_NOT_SET")
        BASE_METER_DETAILS_URL = config.get('Scraper', 'base_meter_details_url', fallback="BASE_METER_URL_NOT_SET")
        RELOAD_INTERVAL_SECONDS = config.getint('Scraper', 'reload_interval_seconds', fallback=300)
        WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS = config.getint('Scraper', 'wait_for_dashboard_timeout', fallback=WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS)
        WAIT_FOR_DASHBOARD_POLL_SECONDS = config.getint('Scraper', 'wait_for_dashboard_poll_interval', fallback=WAIT_FOR_DASHBOARD_POLL_SECONDS)
        logger.info("Scraper base configuration loaded successfully.")
    except Exception as e:
        logger.critical(f"Error loading base configuration from config.ini: {e}", exc_info=True)


TARGET_STORAGE_TIMEZONE = pytz.timezone('Asia/Kolkata')
TABLE_ROW_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable tbody tr')
TABLE_HEADER_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable thead th')
TARGET_COLUMNS = [
    "Sl.", "Meter No.", "Real time clock, date and time", "Voltage, VRN", "Voltage, VYN", "Voltage, VBN",
    "Current, IR", "Current, IY", "Current, IB", "Cumulative energy, kWh (Import)", 
    "Cumulative energy, kVAh (Import)", "Cumulative energy, kWh (Export)", 
    "Cumulative energy, kVAh (Export)", "Network Info"
]

def setup_scraper_logging_queue(log_queue: multiprocessing.Queue, meter_id: str):
    q_logger = logging.getLogger('src.scraper')
    if q_logger.hasHandlers():
        q_logger.handlers.clear()
    queue_handler = logging.handlers.QueueHandler(log_queue)
    q_logger.addHandler(queue_handler)
    q_logger.setLevel(logging.INFO)
    q_logger.propagate = False
    return logging.LoggerAdapter(q_logger, {'meter_id': meter_id})

def capture_debug_info(driver, filename_prefix="error"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{filename_prefix}_{timestamp}.png")
    page_source_path = os.path.join(PAGE_SOURCE_DIR, f"{filename_prefix}_{timestamp}.html")
    try:
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to {screenshot_path}")
    except:
        logger.error("Failed to save screenshot")
    try:
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to {page_source_path}")
    except:
        logger.error("Failed to save page source")


def initialize_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,800')
    options.add_argument('--ignore-certificate-errors')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("WebDriver initialized successfully.")
    return driver


def parse_datetime(dt_str):
    if not dt_str: return None
    try:
        naive_dt_object = datetime.strptime(dt_str, '%d/%m/%Y %H:%M')
        return db_manager.get_timezone().localize(naive_dt_object)
    except ValueError as e:
        logger.error(f"Failed to parse datetime string '{dt_str}': {e}. Returning None.")
        return None


def process_raw_data(raw_data, config_meter_id, config_meter_no):
    processed = {}
    column_map = {
        'Meter No.': 'meter_no', 'Real time clock, date and time': 'timestamp', 'Voltage, VRN': 'voltage_vrn',
        'Voltage, VYN': 'voltage_vyn', 'Voltage, VBN': 'voltage_vbn', 'Current, IR': 'current_ir',
        'Current, IY': 'current_iy', 'Current, IB': 'current_ib',
        'Cumulative energy, kWh (Import)': 'energy_kwh_import',
        'Cumulative energy, kVAh (Import)': 'energy_kvah_import',
        'Cumulative energy, kWh (Export)': 'energy_kwh_export',
        'Cumulative energy, kVAh (Export)': 'energy_kvah_export', 'Network Info': 'network_info'}
    processed['meter_id'] = config_meter_id
    processed['meter_no'] = config_meter_no
    scraped_meter_no_from_table = raw_data.get('Meter No.', '').strip()
    if scraped_meter_no_from_table:
        processed['meter_no'] = scraped_meter_no_from_table
    timestamp_str = raw_data.get('Real time clock, date and time', '')
    timestamp_obj = parse_datetime(timestamp_str)
    if not timestamp_obj: return None
    processed['timestamp'] = timestamp_obj
    for scraped_col, db_col in column_map.items():
        if db_col in ['meter_no', 'meter_id', 'timestamp']: continue
        value = raw_data.get(scraped_col, '').replace(',', '').strip()
        if db_col.startswith(('voltage', 'current', 'energy')):
            try: processed[db_col] = float(value) if value else None
            except ValueError: processed[db_col] = None
        else: processed[db_col] = value if value else None
    return processed


def reselect_instant_partial_dropdowns(driver):
    logger.info("Attempting to re-select 'Instant Profile' -> 'Instant Partial'...")
    timestamp_for_debug = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        instant_profile_li_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]")
        profile_dropdown_li = WebDriverWait(driver, 60).until(EC.visibility_of_element_located(instant_profile_li_locator))
        ActionChains(driver).move_to_element(profile_dropdown_li).perform()
        time.sleep(2)
        dropdown_ul_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul[contains(@ng-show, 'tab.id==11') and (contains(@style, 'display: block') or not(contains(@style, 'display: none')))]")
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located(dropdown_ul_locator))
        instant_partial_option_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul//div[@class='InstantPushdropdown']//a[normalize-space(text())='Instant Partial']")
        partial_option = WebDriverWait(driver, 30).until(EC.element_to_be_clickable(instant_partial_option_locator))
        partial_option.click()
        logger.info("Selected 'Instant Partial'.")
        WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
        WebDriverWait(driver, 10).until(lambda d: len(d.find_elements(*TABLE_ROW_SELECTOR)) > 0)
        logger.info("Table data is now visible and populated after dropdown selection.")
    except Exception as e:
        logger.error(f"Failed to select 'Instant Profile' -> 'Instant Partial': {type(e).__name__} - {e}", exc_info=True)
        capture_debug_info(driver, f"dropdown_error_{timestamp_for_debug}")
        raise


def extract_data_from_table(driver):
    raw_readings = []
    timestamp_for_debug = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        table_locator = (By.CSS_SELECTOR, "table.table.customTable")
        time.sleep(5) # Reduced wait time
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located(table_locator))
        table = driver.find_element(*table_locator)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tbody")))

        headers = []
        header_elements = table.find_elements(*TABLE_HEADER_SELECTOR)
        if not header_elements:
            logger.error("No table headers found.")
            return []
        for th in header_elements:
            headers.append(th.text.strip())
            
        col_indices = {target: headers.index(target) for target in TARGET_COLUMNS if target in headers}
        
        rows = table.find_elements(*TABLE_ROW_SELECTOR)
        if not rows:
            logger.info("No data rows found in the table.")
            return []

        for row in rows:
            if not row.text.strip(): continue
            cells = row.find_elements(By.XPATH, ".//th | .//td") # More robustly finds all cell types
            if not cells: continue
            
            raw_row_data = {}
            for target_col, idx in col_indices.items():
                if idx < len(cells):
                    raw_row_data[target_col] = cells[idx].text.strip()
            
            if any(raw_row_data.values()):
                raw_readings.append(raw_row_data)
                
    except Exception as e:
        logger.error(f"Error in extract_data_from_table: {type(e).__name__} - {e}", exc_info=True)
        capture_debug_info(driver, f"extract_error_{timestamp_for_debug}")
    return raw_readings


# --- MODIFIED PAGINATION LOGIC WITH ROBUST WAIT ---
def extract_all_data_from_paginated_table(driver, stop_event: Optional[multiprocessing.Event], full_fetch=False):
    all_raw_data = []
    MAX_READINGS = 100 if full_fetch else 10
    page_count = 0
    max_pages_to_try = 10 if full_fetch else 2

    while len(all_raw_data) < MAX_READINGS:
        if stop_event and stop_event.is_set():
            logger.info("Pagination: Stop event detected. Stopping.")
            break
        
        page_count += 1
        if page_count > max_pages_to_try:
            logger.info(f"Pagination: Reached max page attempts ({max_pages_to_try}). Stopping.")
            break

        logger.info(f"Pagination: Extracting page {page_count}. Total collected: {len(all_raw_data)}.")
        current_page_data = extract_data_from_table(driver)
        
        if not current_page_data:
            logger.info("Pagination: No data on current page. Assuming end.")
            break
        
        all_raw_data.extend(current_page_data)

        if len(all_raw_data) >= MAX_READINGS:
            logger.info(f"Pagination: Reached target MAX_READINGS ({MAX_READINGS}).")
            break

        # Get a stable identifier for the current page's first row's content
        # The timestamp is a better candidate than "Sl. No." as it's more unique.
        first_row_timestamp_locator = (By.XPATH, "//table[contains(@class, 'customTable')]/tbody/tr[1]/td[2]")
        try:
            old_first_row_timestamp = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located(first_row_timestamp_locator)
            ).text
        except TimeoutException:
            logger.warning("Pagination: Could not find first row timestamp to check for changes. Breaking.")
            break
        
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "span.next")
            if "disabled" in next_button.get_attribute("class"):
                logger.info("Pagination: 'Next' button is disabled. End of pages.")
                break
            
            # Click the next button
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
            time.sleep(0.5)
            next_button.click()
            logger.info(f"Pagination: Clicked 'Next'. Waiting for table to update from timestamp: {old_first_row_timestamp}")

            # ** THE NEW ROBUST WAIT LOGIC **
            page_changed = False
            # Try for up to 20 seconds (20 attempts, 1 second each)
            for _ in range(20):
                try:
                    # Attempt to find the new first row timestamp
                    new_first_row_timestamp = driver.find_element(*first_row_timestamp_locator).text
                    if new_first_row_timestamp != old_first_row_timestamp:
                        logger.info(f"Pagination: Table content has changed. New timestamp: {new_first_row_timestamp}")
                        page_changed = True
                        break # Success! Exit the wait loop.
                except NoSuchElementException:
                    # This is expected if the table is briefly empty during reload.
                    logger.debug("Pagination wait: Table content not yet visible.")
                    pass
                time.sleep(1) # Wait one second before the next attempt
            
            if not page_changed:
                logger.warning("Pagination: Timed out waiting for table content to change. Assuming end of pages or stuck page.")
                break # Exit the main pagination loop if we timed out
            
        except NoSuchElementException:
            logger.info("Pagination: 'Next' button not found. Assuming end of pages.")
            break
        except Exception as e:
            logger.warning(f"Pagination: An error occurred: {type(e).__name__}", exc_info=True)
            capture_debug_info(driver, f"pagination_error_page_{page_count}")
            break
            
    return all_raw_data[:MAX_READINGS]

def main(meter_id: str, meter_number: str, meter_no: str, stop_event: Optional[multiprocessing.Event] = None, log_queue: Optional[multiprocessing.Queue] = None):
    """
    Main scraper function for a single, specific meter.
    It receives all necessary info as arguments.
    """
    if log_queue:
        logger = setup_scraper_logging_queue(log_queue, meter_id)
    else:
        logger = logging.getLogger(__name__)

    if any(not var or "NOT_SET" in var for var in [LOGIN_URL, TARGET_DASHBOARD_URL_CONFIG, BASE_METER_DETAILS_URL]):
        logger.critical("Scraper base URLs are not set in config.ini. Exiting.")
        return

    logger.info(f"Scraper process started.")
    
    driver = None
    db_pool_initialized_by_scraper = False
    try:
        if db_manager.DB_POOL is None:
            logger.info(f"DB_POOL is None, initializing in scraper process...")
            db_manager.initialize_db_pool()
            db_pool_initialized_by_scraper = True
        
        driver = initialize_webdriver() 
        driver.maximize_window()
        driver.set_page_load_timeout(60)

        logger.info(f"Navigating to login: {LOGIN_URL}")
        driver.get(LOGIN_URL)

        logger.info(f"Waiting for dashboard URL: '{TARGET_DASHBOARD_URL_CONFIG}'.")
        if not stop_event: 
            print(f"\n[SCRAPER FOR {meter_id}] Browser open. If needed, log in manually.\n")
        
        dashboard_reached = False
        start_wait_time = time.time()
        while time.time() - start_wait_time < WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS:
            if stop_event and stop_event.is_set(): 
                logger.info(f"Stop event while waiting for dashboard. Exiting.")
                return 
            if driver.current_url.strip() == TARGET_DASHBOARD_URL_CONFIG.strip(): 
                logger.info(f"Target dashboard URL reached.")
                dashboard_reached = True
                break
            time.sleep(WAIT_FOR_DASHBOARD_POLL_SECONDS)

        if not dashboard_reached:
            logger.critical(f"Timed out waiting for dashboard URL.")
            capture_debug_info(driver, f"dashboard_timeout_{meter_id}")
            return
        
        # Build the URL with the arguments passed to this function.
        table_page_url = f"{BASE_METER_DETAILS_URL}{meter_id}/MeterNumber/0"
        
        logger.info(f"Navigating to meter details: {table_page_url}")
        driver.get(table_page_url)
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
        logger.info(f"Meter details page loaded.")
        
        reselect_instant_partial_dropdowns(driver) 
        first_run_data_fetch = True

        while not (stop_event and stop_event.is_set()):
            logger.info(f"--- Scrape cycle start ---")
            try:
                if table_page_url not in driver.current_url:
                    logger.warning(f"Not on the correct meter page. Re-navigating.")
                    driver.get(table_page_url)
                else:
                    driver.refresh()
                
                WebDriverWait(driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
                reselect_instant_partial_dropdowns(driver)
                
                raw_extracted_readings = extract_all_data_from_paginated_table(driver, stop_event, full_fetch=first_run_data_fetch)
                first_run_data_fetch = False
                
                if stop_event and stop_event.is_set(): break

                processed_readings = []
                if raw_extracted_readings:
                    # The meter_no is now passed in as an argument, so this is correct.
                    for raw_row in raw_extracted_readings:
                        processed_row = process_raw_data(raw_row, meter_id, meter_no)
                        if processed_row:
                            processed_readings.append(processed_row)
                    logger.info(f"Processed {len(processed_readings)} valid readings.")

                if processed_readings:
                    db_manager.insert_meter_readings(processed_readings)
                else:
                    logger.warning(f"No valid readings to insert.")

            except Exception as e:
                logger.exception(f"Unexpected error in scrape cycle: {e}")
                capture_debug_info(driver, f"cycle_error_{meter_id}")
            
            logger.info(f"Waiting {RELOAD_INTERVAL_SECONDS}s for next cycle.")
            for _ in range(RELOAD_INTERVAL_SECONDS // 5):
                if stop_event and stop_event.is_set(): break
                time.sleep(5)
            if stop_event and stop_event.is_set(): break
            
    except Exception as e:
        logger.critical(f"Fatal error in scraper process: {e}", exc_info=True)
    finally:
        if driver: driver.quit()
        if db_pool_initialized_by_scraper: db_manager.close_db_pool()
        logger.info(f"Scraper process terminated.")