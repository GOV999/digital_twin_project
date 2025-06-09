import os
import logging
from datetime import datetime, timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager # Ensure this is installed: pip install webdriver-manager
import configparser
import time # Essential for time.sleep()
import pytz # Essential for timezone handling (pip install pytz)

# Import your custom database manager
import db_manager

# --- Configuration & Path Setup ---
# Calculate the base directory of the project (digital_twin_project/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define paths for logs and debug dumps relative to BASE_DIR
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_DUMPS_DIR = os.path.join(BASE_DIR, 'debug_dumps')
SCREENSHOT_DIR = os.path.join(DEBUG_DUMPS_DIR, 'screenshots')
PAGE_SOURCE_DIR = os.path.join(DEBUG_DUMPS_DIR, 'page_sources')

# Ensure directories exist
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(PAGE_SOURCE_DIR, exist_ok=True)

log_file = os.path.join(LOG_DIR, 'scraper.log')

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set to logging.DEBUG for more verbose output

# Create file handler
fh = logging.FileHandler(log_file)
fh.setLevel(logging.INFO)

# Create console handler
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)

# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)

# Add the handlers to the logger (avoid duplicate handlers if script is reloaded/run in session)
if not logger.handlers:
    logger.addHandler(fh)
    logger.addHandler(ch)

# --- Load Configuration from config.ini ---
config = configparser.ConfigParser()
config_path = os.path.join(BASE_DIR, 'config.ini')

if not os.path.exists(config_path):
    logger.critical(f"Error: config.ini not found at {config_path}. Please ensure it exists.")
    exit(1)

try:
    config.read(config_path)

    # Scraper Configuration
    LOGIN_URL = config.get('Scraper', 'LOGIN_URL')
    DASHBOARD_URL = config.get('Scraper', 'DASHBOARD_URL')
    TABLE_PAGE_URL = config.get('Scraper', 'TABLE_PAGE_URL')
    RELOAD_INTERVAL_SECONDS = config.getint('Scraper', 'RELOAD_INTERVAL_SECONDS')

except Exception as e:
    logger.critical(f"Error loading configuration from config.ini: {e}", exc_info=True)
    exit(1)

# --- Define Timezone for Storage ---
# Define the timezone of the data scraped from the website, which will also be your storage timezone
# IST is UTC+5:30, recognized as 'Asia/Kolkata' by pytz
TARGET_STORAGE_TIMEZONE = pytz.timezone('Asia/Kolkata')


# --- Selectors ---
TABLE_ROW_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable tbody tr') # Selects all rows in the table body
TABLE_HEADER_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable thead th') # Selects all table headers

# --- Target Columns for Data Extraction ---
# These must EXACTLY match the website's table headers.
# Ensure 'Cumulative energy, kVAh (Export)' is only listed once.
TARGET_COLUMNS = [
    "Sl.",
    "Meter No.",
    "Real time clock, date and time",
    "Voltage, VRN",
    "Voltage, VYN",
    "Voltage, VBN",
    "Current, IR",
    "Current, IY",
    "Current, IB",
    "Cumulative energy, kWh (Import)",
    "Cumulative energy, kVAh (Import)",
    "Cumulative energy, kWh (Export)",
    "Cumulative energy, kVAh (Export)",
    "Network Info"
]

# --- Helper Functions ---
def parse_datetime(dt_str):
    """
    Parses a date-time string from the webpage into a timezone-aware
    datetime object, localized to the TARGET_STORAGE_TIMEZONE (IST).
    Expected format: 'DD/MM/YYYY HH:MM'
    """
    if not dt_str:
        return None
    try:
        # Parse the string into a naive datetime object
        naive_dt_object = datetime.strptime(dt_str, '%d/%m/%Y %H:%M')

        # Localize the naive datetime object to the target storage timezone (IST)
        # This will attach the +05:30 offset to your datetime object.
        localized_dt_object = TARGET_STORAGE_TIMEZONE.localize(naive_dt_object)

        # Return this localized datetime object directly.
        # The database will store it with its IST timezone information.
        return localized_dt_object
    except ValueError as e:
        logger.error(f"Failed to parse datetime string '{dt_str}': {e}. Returning None.")
        return None

def process_raw_data(raw_data, meter_no_override=None):
    """
    Processes a dictionary of raw scraped data into the format
    expected by the database, handling parsing and type conversions.
    """
    processed = {}

    # Map scraped data (keys are webpage headers) to database column names
    column_map = {
        'Meter No.': 'meter_no',
        'Real time clock, date and time': 'timestamp',
        'Voltage, VRN': 'voltage_vrn',
        'Voltage, VYN': 'voltage_vyn',
        'Voltage, VBN': 'voltage_vbn',
        'Current, IR': 'current_ir',
        'Current, IY': 'current_iy',
        'Current, IB': 'current_ib',
        'Cumulative energy, kWh (Import)': 'energy_kwh_import',
        'Cumulative energy, kVAh (Import)': 'energy_kvah_import',
        'Cumulative energy, kWh (Export)': 'energy_kwh_export',
        'Cumulative energy, kVAh (Export)': 'energy_kvah_export',
        'Network Info': 'network_info'
    }

    # Use hardcoded meter_no if provided, otherwise try to get from scraped data
    processed['meter_no'] = meter_no_override if meter_no_override else raw_data.get('Meter No.', '')
    if not processed['meter_no']:
        logger.warning(f"Could not determine meter_no for row: {raw_data}. Skipping row.")
        return None

    # Handle Timestamp
    timestamp_str = raw_data.get('Real time clock, date and time', '')
    timestamp_obj = parse_datetime(timestamp_str)
    if not timestamp_obj:
        logger.warning(f"Missing or invalid timestamp for meter {processed['meter_no']} in row: {raw_data}. Skipping row.")
        return None
    processed['timestamp'] = timestamp_obj

    # Process other fields
    for scraped_col, db_col in column_map.items():
        if db_col in ['meter_no', 'timestamp']: # Already handled
            continue

        value = raw_data.get(scraped_col, '').replace(',', '').strip() # Remove commas from numbers

        # Convert numeric fields to float, others to string
        if db_col.startswith(('voltage', 'current', 'energy')):
            try:
                processed[db_col] = float(value) if value else None
            except ValueError:
                logger.warning(f"Could not convert '{value}' for {scraped_col} (DB: {db_col}) to float. Setting to None.")
                processed[db_col] = None
        else:
            processed[db_col] = value if value else None # Store as string, or None if empty

    return processed

def reselect_instant_partial_dropdowns(driver):
    """
    Selects 'Instant Profile' -> 'Instant Partial' to ensure correct view.
    Includes robust waits for reliable interaction.
    """
    logger.info("Attempting to re-select 'Instant Profile' -> 'Instant Partial'...")
    timestamp_for_debug = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        instant_profile_li_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]")

        logger.debug(f"Waiting for 'Instant Profile' parent li element to be visible for hover (max 60s)...")
        profile_dropdown_li = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located(instant_profile_li_locator)
        )

        ActionChains(driver).move_to_element(profile_dropdown_li).perform()
        logger.debug("Hovered over 'Instant Profile' parent li element.")

        time.sleep(2) # Give a short moment for the submenu to appear

        dropdown_ul_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul[contains(@ng-show, 'tab.id==11') and (contains(@style, 'display: block') or not(contains(@style, 'display: none')))]")

        logger.debug(f"Waiting for dropdown <ul> container to be visible (max 30s)...")
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located(dropdown_ul_locator)
        )
        logger.debug("Dropdown <ul> container is now visible.")

        instant_partial_option_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul//div[@class='InstantPushdropdown']//a[normalize-space(text())='Instant Partial']")

        logger.debug(f"Waiting for 'Instant Partial' option to be clickable (max 30s)...")
        partial_option = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable(instant_partial_option_locator)
        )
        partial_option.click()
        logger.info("Selected 'Instant Partial'.")

        # After clicking, wait for the table to be visible AND have at least one row, indicating data load.
        logger.debug("Waiting for table to be visible and populated after dropdown selection...")
        WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
        )
        WebDriverWait(driver, 10).until(
            lambda d: len(d.find_elements(*TABLE_ROW_SELECTOR)) > 0
        )
        logger.info("Table data is now visible and populated after dropdown selection.")

    except Exception as e:
        logger.error(f"Failed to select 'Instant Profile' -> 'Instant Partial' or wait for table data: {type(e).__name__} - {e}", exc_info=True)
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"dropdown_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"dropdown_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
        raise # Re-raise the exception to stop execution

def extract_data_from_table(driver):
    """
    Extracts data from the visible table rows.
    Returns a list of raw dictionaries, each representing a row.
    """
    raw_readings = []
    timestamp_for_debug = datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        table_locator = (By.CSS_SELECTOR, "table.table.customTable")

        logger.debug("Adding a 10-second sleep to allow for full rendering before table scrape...")
        time.sleep(10) # Initial static wait for rendering

        logger.debug(f"Waiting for main table element to be present and visible (max 90s)...")
        WebDriverWait(driver, 90).until(EC.visibility_of_element_located(table_locator))

        table = driver.find_element(*table_locator)
        logger.debug(f"Table element found. Displayed: {table.is_displayed()}, Size: {table.size}")

        tbody_locator = (By.CSS_SELECTOR, "table.table.customTable tbody")
        logger.debug(f"Waiting for table body to be present (max 30s)...")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located(tbody_locator))

        first_row_check_locator = (By.CSS_SELECTOR, "table.table.customTable tbody tr.evenRow")
        logger.debug(f"Waiting for at least one data row to be visible (max 30s)...")
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located(first_row_check_locator))

        logger.debug("Adding a 2-second buffer to allow all cell data to render...")
        time.sleep(2) # Buffer for cell data rendering

        # Get headers
        headers = []
        header_elements = table.find_elements(*TABLE_HEADER_SELECTOR)
        if not header_elements:
             logger.error("No table headers found. Check TABLE_HEADER_SELECTOR.")
             return []

        for th in header_elements:
            span_element = th.find_elements(By.TAG_NAME, "span")
            if span_element:
                headers.append(span_element[0].text.strip())
            else:
                headers.append(th.text.strip())

        logger.debug(f"Detected table headers: {headers}")

        col_indices = {}
        for target_col in TARGET_COLUMNS:
            try:
                col_indices[target_col] = headers.index(target_col)
            except ValueError:
                logger.warning(f"Target column '{target_col}' not found in scraped headers. It will be an empty string in output.")
                col_indices[target_col] = -1

        if all(idx == -1 for idx in col_indices.values()):
            logger.error("None of the TARGET_COLUMNS were found in the scraped headers. Aborting scrape for this cycle.")
            return []

        rows_to_scrape_elements = table.find_elements(By.XPATH, ".//tbody/tr[contains(@class, 'Row')]")

        if not rows_to_scrape_elements:
            logger.info("No data rows found in the table's tbody to scrape.")
            return raw_readings

        current_meter_id = "1000613" # Hardcoded, ideally dynamically extracted from URL/page

        for i, row_element in enumerate(rows_to_scrape_elements):
            if not row_element.text.strip():
                logger.debug(f"Skipping empty row {i+1}.")
                continue

            cells_th = row_element.find_elements(By.TAG_NAME, "th")
            cells_td = row_element.find_elements(By.TAG_NAME, "td")
            all_cells_elements = cells_th + cells_td

            if not all_cells_elements:
                logger.debug(f"Row {i+1} has no cells. Skipping.")
                continue

            raw_row_data = {}
            for target_col in TARGET_COLUMNS:
                idx = col_indices.get(target_col, -1)
                if idx != -1 and idx < len(all_cells_elements):
                    cell_element = all_cells_elements[idx]
                    span_in_cell = cell_element.find_elements(By.TAG_NAME, "span")
                    if span_in_cell:
                        raw_row_data[target_col] = span_in_cell[0].text.strip()
                    else:
                        raw_row_data[target_col] = cell_element.text.strip()
                else:
                    if idx != -1: # Only warn if the column was expected but index was out of bounds
                        logger.warning(f"For scraped row {i+1}, target column '{target_col}' (expected index {idx}) is out of bounds for {len(all_cells_elements)} cells found.")
                    raw_row_data[target_col] = ""

            # Only add to raw_readings if it has any meaningful content
            if any(value for value in raw_row_data.values() if value):
                raw_row_data['Meter No.'] = raw_row_data.get('Meter No.', current_meter_id) # Ensure meter no is present
                raw_readings.append(raw_row_data)
            else:
                logger.debug(f"Skipping empty or mostly empty scraped row {i+1} from table.")

    except TimeoutException:
        logger.error("Timed out waiting for table data to load.")
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"scrape_timeout_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"scrape_timeout_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
    except NoSuchElementException:
        logger.error("Table elements not found. Check selectors or page structure.")
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"scrape_noelement_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"scrape_noelement_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during data extraction: {e}")
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"scrape_general_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"scrape_general_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
    return raw_readings


# --- Main Scraper Logic ---
def main():
    driver = None
    try:
        # Initialize DB pool
        db_config = dict(config['Database'])
        db_manager.initialize_db_pool(db_config)

        logger.info("Initializing WebDriver...")
        # Use ChromeService for newer Selenium versions
        service = webdriver.ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.maximize_window()
        driver.set_page_load_timeout(60) # Increased timeout for initial page load

        logger.info("Navigating to login page...")
        driver.get(LOGIN_URL)

        # --- Manual Login Prompt ---
        print("\n" + "="*50)
        print(f"Please manually log in to the web dashboard ({LOGIN_URL})")
        print(f"and navigate to the Meter Details page for the meter: {TABLE_PAGE_URL}")
        print("Once the table data is visible, press Enter here to continue the scraper.")
        print("="*50 + "\n")

        input("Press Enter to continue...")
        logger.info("User confirmed manual login and navigation. Starting data extraction loop.")

        # Ensure we are on the correct page after manual navigation (initial check)
        # and re-navigate if not.
        if driver.current_url != TABLE_PAGE_URL:
            logger.warning(f"Current URL ({driver.current_url}) does not match expected ({TABLE_PAGE_URL}) after manual navigation. Attempting to navigate directly.")
            driver.get(TABLE_PAGE_URL)
            # Wait for main table element to be present after direct navigation
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
            )
            logger.info("Main table element found after initial direct navigation.")

        # Initial dropdown selection after landing on the page
        reselect_instant_partial_dropdowns(driver)

        while True:
            try:
                # --- Robust Reloading Logic ---
                current_url_main = driver.current_url
                if TABLE_PAGE_URL not in current_url_main:
                    logger.warning(f"Current URL '{current_url_main}' does not match expected TABLE_PAGE_URL '{TABLE_PAGE_URL}'. This might indicate session expiration or manual navigation away.")
                    logger.info("You will need to manually log in again if your session has expired.")
                    input("\nPress ENTER in THIS terminal once you have manually re-logged in and are on the correct page (or are ready to proceed with a fresh navigation): ")
                    driver.get(TABLE_PAGE_URL) # Attempt to navigate back
                    logger.info("Waiting 15 seconds for the meter readings page to load robustly after forced navigation...")
                    time.sleep(15) # Wait after forced navigation
                    reselect_instant_partial_dropdowns(driver)
                else:
                    logger.info("Refreshing page to get latest data for current cycle...")
                    driver.refresh() # <-- Explicit Page Refresh for Live Data
                    logger.info("Page refreshed. Waiting a few seconds for content to generally appear (15s)...")
                    time.sleep(15) # Wait after refresh to allow dynamic content to load
                    reselect_instant_partial_dropdowns(driver) # Re-select dropdowns to activate latest data view
                    logger.info("Dropdowns re-selected for current cycle. Proceeding with table scrape.")
                # --- End Robust Reloading Logic ---

                # Extract raw data from the table
                raw_extracted_readings = extract_data_from_table(driver)

                processed_readings = []
                if raw_extracted_readings:
                    logger.info(f"Successfully extracted {len(raw_extracted_readings)} raw readings from the web.")
                    for raw_row in raw_extracted_readings:
                        processed_row = process_raw_data(raw_row)
                        if processed_row:
                            processed_readings.append(processed_row)
                    logger.info(f"Processed {len(processed_readings)} valid readings for database insertion.")
                else:
                    logger.warning("No raw readings extracted in this cycle.")

                if processed_readings:
                    db_manager.insert_meter_readings(processed_readings)
                    logger.info(f"Successfully inserted {len(processed_readings)} readings into the database.")
                else:
                    logger.warning("No valid readings to insert into the database in this cycle.")

            except WebDriverException as e:
                logger.error(f"WebDriver error during scraping cycle: {e}. Attempting to re-navigate and continue.", exc_info=True)
                try:
                    logger.info("Attempting recovery by re-navigating and re-selecting dropdowns...")
                    driver.get(TABLE_PAGE_URL)
                    # Wait for recovery page load
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
                    )
                    reselect_instant_partial_dropdowns(driver)
                except WebDriverException as re_e:
                    logger.critical(f"Failed to re-navigate after WebDriver error: {re_e}. Exiting scraper.", exc_info=True)
                    break # Exit main loop on unrecoverable WebDriver error
            except Exception as e:
                logger.exception(f"An unexpected error occurred during scraping cycle: {e}")

            logger.info(f"Waiting for {RELOAD_INTERVAL_SECONDS // 60} minutes ({RELOAD_INTERVAL_SECONDS} seconds) before next scrape cycle.")
            time.sleep(RELOAD_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Script interrupted by user. Exiting.")
    except Exception as e:
        logger.critical(f"A fatal error occurred in the main scraper function: {e}", exc_info=True)
    finally:
        if driver:
            logger.info("Closing WebDriver.")
            driver.quit()
        db_manager.close_db_pool()
        logger.info("Scraper script execution finished.")

if __name__ == '__main__':
    main()