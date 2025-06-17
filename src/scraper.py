# This is the scraper.py you provided, with ONLY extract_all_data_from_paginated_table modified.
# All other functions and the main structure remain IDENTICAL to your last "existing files" version.

import os
import logging
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import configparser
import time
import pytz
# Changes for stop_event and URL login
from typing import Optional
import multiprocessing

# Import your custom database manager
from . import db_manager

# --- Configuration & Path Setup (from your file) ---
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

LOGIN_URL = ""
TARGET_DASHBOARD_URL_CONFIG = "" # For URL check
BASE_METER_DETAILS_URL = ""
METER_ID_CONFIG = ""
METER_NUMBER_CONFIG = ""
RELOAD_INTERVAL_SECONDS = 300
TABLE_PAGE_URL = ""
WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS = 300 
WAIT_FOR_DASHBOARD_POLL_SECONDS = 5

if not os.path.exists(config_path):
    logger.critical(f"CRITICAL: config.ini not found at {config_path}. Using default/empty values which may fail.")
else:
    try:
        config.read(config_path)
        LOGIN_URL = config.get('Scraper', 'login_url', fallback="LOGIN_URL_NOT_SET")
        TARGET_DASHBOARD_URL_CONFIG = config.get('Scraper', 'target_dashboard_url', fallback="TARGET_DASHBOARD_URL_NOT_SET")
        BASE_METER_DETAILS_URL = config.get('Scraper', 'base_meter_details_url', fallback="BASE_METER_URL_NOT_SET")
        METER_ID_CONFIG = config.get('Scraper', 'meter_id', fallback="DEFAULT_METER_ID")
        METER_NUMBER_CONFIG = config.get('Scraper', 'meter_number', fallback="DEFAULT_METER_NUMBER")
        RELOAD_INTERVAL_SECONDS = config.getint('Scraper', 'reload_interval_seconds', fallback=300)
        TABLE_PAGE_URL = f"{BASE_METER_DETAILS_URL}{METER_ID_CONFIG}/MeterNumber/{METER_NUMBER_CONFIG}"
        WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS = config.getint('Scraper', 'wait_for_dashboard_timeout', fallback=WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS)
        WAIT_FOR_DASHBOARD_POLL_SECONDS = config.getint('Scraper', 'wait_for_dashboard_poll_interval', fallback=WAIT_FOR_DASHBOARD_POLL_SECONDS)
        logger.info("Scraper configuration loaded successfully.")
        if TARGET_DASHBOARD_URL_CONFIG == "TARGET_DASHBOARD_URL_NOT_SET":
            logger.warning("target_dashboard_url not set in config.ini, login check might be unreliable.")
    except Exception as e:
        logger.critical(f"Error loading configuration from config.ini: {e}", exc_info=True)

TARGET_STORAGE_TIMEZONE = pytz.timezone('Asia/Kolkata')
TABLE_ROW_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable tbody tr')
TABLE_HEADER_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable thead th')
TARGET_COLUMNS = [
    "Sl.", "Meter No.", "Real time clock, date and time", "Voltage, VRN", "Voltage, VYN", "Voltage, VBN",
    "Current, IR", "Current, IY", "Current, IB", "Cumulative energy, kWh (Import)", 
    "Cumulative energy, kVAh (Import)", "Cumulative energy, kWh (Export)", 
    "Cumulative energy, kVAh (Export)", "Network Info"
]

def capture_debug_info(driver, filename_prefix="error"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{filename_prefix}_{timestamp}.png")
    page_source_path = os.path.join(PAGE_SOURCE_DIR, f"{filename_prefix}_{timestamp}.html")
    try: driver.save_screenshot(screenshot_path); logger.error(f"Screenshot: {screenshot_path}")
    except: logger.error("Failed to save screenshot")
    try:
        with open(page_source_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
        logger.error(f"Page source: {page_source_path}")
    except: logger.error("Failed to save page source")

def initialize_webdriver():
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,800') 
    options.add_argument('--ignore-certificate-errors') 
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("WebDriver initialized successfully (browser window opened).")
    return driver

def parse_datetime(dt_str): # Your original
    if not dt_str: return None
    try:
        naive_dt_object = datetime.strptime(dt_str, '%d/%m/%Y %H:%M')
        return db_manager.get_timezone().localize(naive_dt_object)
    except ValueError as e:
        logger.error(f"Failed to parse datetime string '{dt_str}': {e}. Returning None.")
        return None

def process_raw_data(raw_data, config_meter_id, config_meter_number): # Your original
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
    processed['meter_no'] = config_meter_number 
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

def reselect_instant_partial_dropdowns(driver): # Your original
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

def extract_data_from_table(driver): # Your original
    raw_readings = []
    timestamp_for_debug = datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        table_locator = (By.CSS_SELECTOR, "table.table.customTable")
        time.sleep(10) # Your existing sleep
        WebDriverWait(driver, 90).until(EC.visibility_of_element_located(table_locator))
        table = driver.find_element(*table_locator)
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable tbody")))
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "table.table.customTable tbody tr.evenRow")))
        time.sleep(2) # Your existing sleep
        headers = []
        header_elements = table.find_elements(*TABLE_HEADER_SELECTOR)
        if not header_elements: logger.error("No table headers found."); return []
        for th in header_elements:
            span_element = th.find_elements(By.TAG_NAME, "span")
            if span_element: headers.append(span_element[0].text.strip())
            else: headers.append(th.text.strip())
        col_indices = {}
        for target_col in TARGET_COLUMNS:
            try: col_indices[target_col] = headers.index(target_col)
            except ValueError: col_indices[target_col] = -1
        if all(idx == -1 for idx in col_indices.values()): logger.error("None TARGET_COLUMNS found."); return []
        rows_to_scrape_elements = table.find_elements(By.XPATH, ".//tbody/tr[contains(@class, 'Row')]")
        if not rows_to_scrape_elements: logger.info("No data rows found."); return raw_readings
        for i, row_element in enumerate(rows_to_scrape_elements):
            if not row_element.text.strip(): continue
            cells_th = row_element.find_elements(By.TAG_NAME, "th"); cells_td = row_element.find_elements(By.TAG_NAME, "td")
            all_cells_elements = cells_th + cells_td
            if not all_cells_elements: continue
            raw_row_data = {}
            for target_col in TARGET_COLUMNS:
                idx = col_indices.get(target_col, -1)
                if idx != -1 and idx < len(all_cells_elements):
                    cell_element = all_cells_elements[idx]
                    span_in_cell = cell_element.find_elements(By.TAG_NAME, "span")
                    if span_in_cell: raw_row_data[target_col] = span_in_cell[0].text.strip()
                    else: raw_row_data[target_col] = cell_element.text.strip()
                else: raw_row_data[target_col] = ""
            if any(value for value in raw_row_data.values() if value): raw_readings.append(raw_row_data)
    except Exception as e: # Catching generic Exception as per your original
        logger.error(f"Error in extract_data_from_table: {type(e).__name__} - {e}", exc_info=True) # More info
        capture_debug_info(driver, f"extract_error_{timestamp_for_debug}")
    return raw_readings

# MODIFIED: extract_all_data_from_paginated_table to accept and check stop_event
# Minimal change to pagination logic itself, focusing on stop_event and reliable next click
def extract_all_data_from_paginated_table(driver, stop_event: Optional[multiprocessing.Event], full_fetch=False):
    all_raw_data = []
    MAX_READINGS = 100 if full_fetch else 10
    page_count = 0
    # For full_fetch, allow more pages; for regular, your original logic implies one page primarily.
    # Let's allow checking a couple of pages to ensure MAX_READINGS can be met if first page is short.
    max_pages_to_try = 10 if full_fetch else 2 
    previous_page_first_row_content_str = None # For detecting stuck pages

    while len(all_raw_data) < MAX_READINGS:
        if stop_event and stop_event.is_set():
            logger.info("Pagination: Stop event detected. Stopping.")
            break
        
        page_count += 1
        if page_count > max_pages_to_try:
            logger.info(f"Pagination: Reached max page attempts ({max_pages_to_try}). Stopping pagination.")
            break

        logger.info(f"Pagination: Attempting to extract page {page_count}. Data collected so far: {len(all_raw_data)}/{MAX_READINGS}")
        current_page_data = extract_data_from_table(driver) # Your existing function
        
        if not current_page_data:
            logger.info(f"Pagination: No data returned from page {page_count}. Assuming end of data or error in extraction.")
            break

        # Check for stuck pagination (content not changing)
        current_first_row_content_str = "".join(str(v) for v in current_page_data[0].values()) # Create string from first row
        if page_count > 1 and current_first_row_content_str == previous_page_first_row_content_str:
            logger.warning(f"Pagination: Content of page {page_count} appears identical to previous page. Assuming stuck or end of unique data.")
            break
        previous_page_first_row_content_str = current_first_row_content_str

        remaining_needed = MAX_READINGS - len(all_raw_data)
        all_raw_data.extend(current_page_data[:remaining_needed])

        if len(all_raw_data) >= MAX_READINGS:
            logger.info(f"Pagination: Reached target MAX_READINGS ({MAX_READINGS}).")
            break
        
        # Your original pagination logic for clicking next:
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, "span.next")
            if "disabled" in next_button.get_attribute("class"):
                logger.info("Pagination: 'Next' button is disabled. End of pages.")
                break
            
            # Before clicking, get a reference to an element on the current page
            # to check for staleness. The first row is a good candidate.
            current_rows = driver.find_elements(*TABLE_ROW_SELECTOR)
            stale_element = current_rows[0] if current_rows else next_button

            driver.execute_script("arguments[0].scrollIntoView(true);", next_button)
            time.sleep(0.5) # Small pause after scroll, before click
            next_button.click() # Your original click
            logger.info(f"Pagination: Clicked 'Next' to go to page {page_count + 1}.")
            
            # Wait for the page to update. Using staleness of an old element is good.
            try:
                WebDriverWait(driver, 20).until(EC.staleness_of(stale_element)) # Increased timeout
                logger.debug("Pagination: Old page content became stale.")
                time.sleep(2) # Wait for new content to fully render (your original sleep)
            except TimeoutException:
                logger.warning("Pagination: Content did not become stale after clicking 'Next'. Page might be stuck or this is the actual last page.")
                # Additional check: is the "next" button now disabled?
                try:
                    if "disabled" in driver.find_element(By.CSS_SELECTOR, "span.next").get_attribute("class"):
                        logger.info("Pagination: 'Next' button is now disabled after staleness timeout. Confirming end of pages.")
                        break 
                except NoSuchElementException: # Next button might have disappeared
                    logger.info("Pagination: 'Next' button no longer found after staleness timeout. Confirming end of pages.")
                    break
                # If still not conclusive, the stuck content check at the start of the loop will catch it.
                
        except NoSuchElementException: # This is from your original logic
            logger.info("Pagination: 'Next' button not found. Assuming end of pages.")
            break
        except Exception as e: # Catch other errors during pagination
            logger.warning(f"Pagination: Error clicking 'Next' or waiting: {type(e).__name__} - {e}")
            capture_debug_info(driver, f"pagination_error_page_{page_count}")
            break # Stop pagination on error
            
    return all_raw_data # Returns whatever was collected up to MAX_READINGS or error/end


# --- Main Scraper Logic ---
# MODIFIED: To accept stop_event and use URL check for login
def main(stop_event: Optional[multiprocessing.Event] = None):
    if not LOGIN_URL or LOGIN_URL == "LOGIN_URL_NOT_SET" or \
       not TARGET_DASHBOARD_URL_CONFIG or TARGET_DASHBOARD_URL_CONFIG == "TARGET_DASHBOARD_URL_NOT_SET":
        logger.critical("Scraper URLs (login_url or target_dashboard_url) not in config.ini. Exiting.")
        return

    logger.info(f"Scraper started. PID: {os.getpid()}. Stop event: {bool(stop_event)}.")
    driver = None
    db_pool_initialized_by_scraper = False
    try:
        if db_manager.DB_POOL is None:
            logger.info("DB_POOL is None, initializing in scraper process...")
            db_manager.initialize_db_pool()
            db_pool_initialized_by_scraper = True
        
        driver = initialize_webdriver() 
        driver.maximize_window()
        driver.set_page_load_timeout(60)

        logger.info(f"Navigating to login: {LOGIN_URL}")
        driver.get(LOGIN_URL)

        logger.info(f"Waiting for dashboard URL: '{TARGET_DASHBOARD_URL_CONFIG}'. Max wait: {WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS}s.")
        if not stop_event: 
            print("\n" + "="*60 + f"\nSCRAPER: Browser opened to {LOGIN_URL}.\nIf manual login needed, please log in.\nScript proceeds upon reaching: {TARGET_DASHBOARD_URL_CONFIG}\nTimeout: {WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS // 60} mins.\n" + "="*60 + "\n")
        
        dashboard_reached = False
        start_wait_time = time.time()
        while time.time() - start_wait_time < WAIT_FOR_DASHBOARD_TIMEOUT_SECONDS:
            if stop_event and stop_event.is_set(): logger.info("Stop event while waiting for dashboard. Exiting."); return 
            current_url = driver.current_url.strip()
            target_url = TARGET_DASHBOARD_URL_CONFIG.strip()
            if current_url == target_url: logger.info(f"Target dashboard URL '{target_url}' reached."); dashboard_reached = True; break
            else: logger.debug(f"Not on dashboard. Current: '{current_url}'. Poll in {WAIT_FOR_DASHBOARD_POLL_SECONDS}s."); time.sleep(WAIT_FOR_DASHBOARD_POLL_SECONDS)
        if not dashboard_reached:
            logger.critical(f"Timed out waiting for dashboard URL. Current: {driver.current_url}"); capture_debug_info(driver, "dashboard_url_timeout"); return 
        
        logger.info(f"Navigating to meter details: {TABLE_PAGE_URL}")
        driver.get(TABLE_PAGE_URL)
        WebDriverWait(driver, 60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
        logger.info("Meter details page loaded.")
        
        reselect_instant_partial_dropdowns(driver) 
        first_run_data_fetch = True # Your original flag

        while True: 
            if stop_event and stop_event.is_set(): logger.info("Scraper loop: Stop event. Breaking."); break
            logger.info(f"--- Scrape cycle start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            try:
                current_url_main = driver.current_url.strip()
                # Your original logic for checking if on correct page / session expiry
                if TABLE_PAGE_URL not in current_url_main or (LOGIN_URL in current_url_main and "auth/login" in current_url_main):
                    logger.warning(f"Not on meter page or redirected to login (Current: '{current_url_main}'). Re-navigating.")
                    driver.get(TABLE_PAGE_URL)
                    WebDriverWait(driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
                    reselect_instant_partial_dropdowns(driver)
                else:
                    logger.info("Refreshing page for latest data...")
                    driver.refresh()
                    WebDriverWait(driver, 45).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
                    reselect_instant_partial_dropdowns(driver)
                
                logger.info(f"Extracting data. Full fetch this cycle: {first_run_data_fetch}")
                # Pass your first_run_data_fetch flag here, and the stop_event
                raw_extracted_readings = extract_all_data_from_paginated_table(driver, stop_event, full_fetch=first_run_data_fetch)
                first_run_data_fetch = False # Set to False after the first iteration
                
                if stop_event and stop_event.is_set(): logger.info("Stop event after data extraction. Exiting loop."); break

                processed_readings = []
                if raw_extracted_readings:
                    logger.info(f"Extracted {len(raw_extracted_readings)} raw readings.")
                    for raw_row in raw_extracted_readings:
                        # Using METER_ID_CONFIG and METER_NUMBER_CONFIG from the global scope
                        processed_row = process_raw_data(raw_row, METER_ID_CONFIG, METER_NUMBER_CONFIG)
                        if processed_row: processed_readings.append(processed_row)
                    logger.info(f"Processed {len(processed_readings)} valid readings.")
                else: logger.warning("No raw readings extracted.")

                if processed_readings:
                    db_manager.insert_meter_details(METER_ID_CONFIG, METER_NUMBER_CONFIG, location="Scraped Data Location")
                    db_manager.insert_meter_readings(processed_readings)
                    logger.info(f"Inserted {len(processed_readings)} readings.")
                else: logger.warning("No valid readings to insert.")

            except WebDriverException as e:
                logger.error(f"WebDriver error in cycle: {type(e).__name__}. Attempting recovery.", exc_info=False)
                capture_debug_info(driver, "webdriver_recovery")
                try:
                    logger.info("Recovery: Re-navigating..."); driver.get(TABLE_PAGE_URL)
                    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable")))
                    reselect_instant_partial_dropdowns(driver); logger.info("Recovery successful.")
                except Exception as re_e: logger.critical(f"Recovery failed: {re_e}. Exiting.", exc_info=True); break 
            except Exception as e: logger.exception(f"Unexpected error in cycle: {e}")

            if stop_event and stop_event.is_set(): logger.info("Stop event before sleep. Exiting loop."); break
            logger.info(f"Waiting {RELOAD_INTERVAL_SECONDS}s for next cycle.")
            sleep_segment = max(1, WAIT_FOR_DASHBOARD_POLL_SECONDS)
            for _ in range(RELOAD_INTERVAL_SECONDS // sleep_segment):
                if stop_event and stop_event.is_set(): logger.info("Stop event during sleep. Exiting."); break 
                time.sleep(sleep_segment)
            if stop_event and stop_event.is_set(): break
            
        logger.info("Scraper main loop finished.")
    except KeyboardInterrupt: logger.info("Script interrupted. Exiting.");
    except Exception as e: logger.critical(f"Fatal error in main scraper: {e}", exc_info=True);
    finally:
        if driver: logger.info("Closing WebDriver."); driver.quit()
        if db_pool_initialized_by_scraper: logger.info("Closing scraper-initialized DB pool."); db_manager.close_db_pool()
        logger.info(f"Scraper process (PID: {os.getpid()}) terminated.")

if __name__ == '__main__':
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch = logging.StreamHandler(sys.stdout); ch.setFormatter(log_formatter)
    scraper_log_path = os.path.join(LOG_DIR, 'scraper_standalone_run.log') 
    fh = logging.FileHandler(scraper_log_path); fh.setFormatter(log_formatter)
    logger.setLevel(logging.INFO) 
    if logger.hasHandlers(): logger.handlers.clear()
    logger.addHandler(ch); logger.addHandler(fh); logger.propagate = False 
    db_module_logger = logging.getLogger('src.db_manager') 
    if not db_module_logger.hasHandlers(): db_module_logger.setLevel(logging.INFO); db_module_logger.addHandler(ch) 
    db_module_logger.propagate = False
    logger.info("--- Running scraper.py standalone for testing ---")
    try: main() 
    except Exception as e: logger.critical(f"Standalone run failed: {e}", exc_info=True)