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

# --- Logging Setup (Minimal for Module - Main.py handles global setup) ---
logger = logging.getLogger(__name__)


# --- Load Configuration from config.ini ---
config = configparser.ConfigParser()
config_path = os.path.join(BASE_DIR, 'config.ini')

if not os.path.exists(config_path):
    logger.critical(f"Error: config.ini not found at {config_path}. Please ensure it exists.")
    exit(1)

try:
    config.read(config_path)

    LOGIN_URL = config.get('Scraper', 'login_url')
    BASE_METER_DETAILS_URL = config.get('Scraper', 'base_meter_details_url')
    METER_ID = config.get('Scraper', 'meter_id')
    METER_NUMBER = config.get('Scraper', 'meter_number')
    RELOAD_INTERVAL_SECONDS = config.getint('Scraper', 'reload_interval_seconds')

    # Dynamically construct the full URL for the meter details page based on config values
    TABLE_PAGE_URL = f"{BASE_METER_DETAILS_URL}{METER_ID}/MeterNumber/{METER_NUMBER}"

except Exception as e:
    logger.critical(f"Error loading configuration from config.ini: {e}", exc_info=True)
    exit(1)

# --- Define Timezone for Storage ---
TARGET_STORAGE_TIMEZONE = pytz.timezone('Asia/Kolkata')


# --- Selectors ---
TABLE_ROW_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable tbody tr')
TABLE_HEADER_SELECTOR = (By.CSS_SELECTOR, 'table.table.customTable thead th')

# --- Target Columns for Data Extraction ---
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

# --- Helper Functions (DEFINED BEFORE main() to avoid NameError) ---

def capture_debug_info(driver, filename_prefix="error"):
    """Captures screenshot and page source for debugging."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SCREENSHOT_DIR, f"{filename_prefix}_{timestamp}.png")
    page_source_path = os.path.join(PAGE_SOURCE_DIR, f"{filename_prefix}_{timestamp}.html")

    try:
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
    except Exception as e:
        logger.error(f"Failed to save screenshot: {e}")

    try:
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
    except Exception as e:
        logger.error(f"Failed to save page source: {e}")

def initialize_webdriver():
    """Initializes and returns a Chrome WebDriver."""
    options = webdriver.ChromeOptions()
    # options.add_argument('--headless') # Keep this commented for manual login
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1280,800') # Set a consistent window size for visibility
    options.add_argument('--ignore-certificate-errors') # For self-signed certs
    # options.add_argument('--disable-gpu') # Applicable for headless in some environments

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    logger.info("WebDriver initialized successfully (browser window opened).")
    return driver

def parse_datetime(dt_str):
    """
    Parses a date-time string from the webpage into a timezone-aware
    datetime object, localized to the TARGET_STORAGE_TIMEZONE (IST).
    Expected format: 'DD/MM/YYYY HH:MM'.
    """
    if not dt_str:
        return None
    try:
        naive_dt_object = datetime.strptime(dt_str, '%d/%m/%Y %H:%M')
        return naive_dt_object.replace(tzinfo=db_manager.get_timezone())
    except ValueError as e:
        logger.error(f"Failed to parse datetime string '{dt_str}': {e}. Returning None.")
        return None

def process_raw_data(raw_data, config_meter_id, config_meter_number):
    """
    Processes a dictionary of raw scraped data into the format
    expected by the database, handling parsing and type conversions.
    It explicitly takes meter_id and meter_no from config.
    """
    processed = {}
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

    processed['meter_id'] = config_meter_id
    processed['meter_no'] = config_meter_number

    scraped_meter_no_from_table = raw_data.get('Meter No.', '').strip()
    if scraped_meter_no_from_table:
        processed['meter_no'] = scraped_meter_no_from_table
        logger.debug(f"Overriding meter_no with scraped value: {scraped_meter_no_from_table}")

    timestamp_str = raw_data.get('Real time clock, date and time', '')
    timestamp_obj = parse_datetime(timestamp_str)
    if not timestamp_obj:
        logger.warning(f"Missing or invalid timestamp for meter ID {processed['meter_id']}, number {processed['meter_no']} in row: {raw_data}. Skipping row.")
        return None
    processed['timestamp'] = timestamp_obj

    for scraped_col, db_col in column_map.items():
        if db_col in ['meter_no', 'meter_id', 'timestamp']:
            continue

        value = raw_data.get(scraped_col, '').replace(',', '').strip()

        if db_col.startswith(('voltage', 'current', 'energy')):
            try:
                processed[db_col] = float(value) if value else None
            except ValueError:
                logger.warning(f"Could not convert '{value}' for {scraped_col} (DB: {db_col}) to float. Setting to None.")
                processed[db_col] = None
        else:
            processed[db_col] = value if value else None

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
        capture_debug_info(driver, f"dropdown_error_{timestamp_for_debug}")
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
                    raw_row_data[target_col] = "" # Set to empty string if column not found or out of bounds

            if any(value for value in raw_row_data.values() if value):
                raw_readings.append(raw_row_data) # Appending raw data here, processing happens in main()
            else:
                logger.debug(f"Skipping empty or mostly empty scraped row {i+1} from table.")

    except TimeoutException:
        logger.error("Timed out waiting for table data to load.")
        capture_debug_info(driver, f"scrape_timeout_error_{timestamp_for_debug}")
    except NoSuchElementException:
        logger.error("Table elements not found. Check selectors or page structure.")
        capture_debug_info(driver, f"scrape_noelement_error_{timestamp_for_debug}")
    except Exception as e:
        logger.exception(f"An unexpected error occurred during data extraction: {e}")
        capture_debug_info(driver, f"scrape_general_error_{timestamp_for_debug}")
    return raw_readings


# --- Main Scraper Logic ---
def main():
    driver = None
    try:
        # Initialize DB pool
        db_manager.initialize_db_pool() # Removed DB_CONFIG argument

        # Initialize WebDriver using the helper function
        driver = initialize_webdriver()
        driver.maximize_window()
        driver.set_page_load_timeout(60)

        logger.info("Navigating to login page...")
        driver.get(LOGIN_URL)

        # --- Manual Login Prompt ---
        print("\n" + "="*50)
        print(f"Please manually log in to the web dashboard at: {LOGIN_URL}")
        print("After successful login (and CAPTCHA), the browser should be on the dashboard page.")
        print("Once you see the main dashboard content, press Enter here in this terminal to continue the scraper.")
        print("="*50 + "\n")

        input("Press Enter to continue...")
        logger.info("User confirmed manual login. Script will now verify dashboard and navigate to meter details page.")

        # After manual login, the script takes control of navigation
        # Wait for a general dashboard element to confirm login.
        try:
            # THIS IS THE CRITICAL LINE TO ADJUST FOR YOUR WEBSITE.
            # You NEED to find a unique CSS selector for an element that ONLY appears
            # when you are successfully logged in and on the main dashboard page.
            # Example: A div with a specific ID, a unique heading, etc.
            # Replace "div[class*='main-content']" with your actual selector.
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='dashboard']")) # Adjusted example selector
            )
            logger.info("Dashboard element found. Confirmed successful manual login.")
        except TimeoutException:
            logger.critical("Timed out waiting for dashboard element after manual login. Ensure login was successful AND you are on the dashboard page. Exiting.")
            capture_debug_info(driver, "manual_login_dashboard_timeout")
            return # Exit if dashboard is not confirmed

        # Now, navigate directly to the TABLE_PAGE_URL (meter details page)
        logger.info(f"Navigating to meter details page: {TABLE_PAGE_URL}")
        driver.get(TABLE_PAGE_URL)
        
        # Wait for the table to be present on the meter details page after direct navigation
        try:
            WebDriverWait(driver, 60).until( # Increased wait time here for initial table load
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
            )
            logger.info("Main table element found on meter details page.")
        except TimeoutException:
            logger.critical(f"Timed out waiting for the meter data table on {TABLE_PAGE_URL}. Page may not have loaded correctly, session expired, or selector is wrong. Exiting.")
            capture_debug_info(driver, "meter_table_load_timeout")
            return # Exit if table not found

        reselect_instant_partial_dropdowns(driver) # Initial dropdown selection after landing

        while True:
            try:
                current_url_main = driver.current_url
                # Check if current URL *contains* TABLE_PAGE_URL (more robust for SPA routes)
                if TABLE_PAGE_URL not in current_url_main:
                    logger.warning(f"Current URL '{current_url_main}' does not contain expected TABLE_PAGE_URL '{TABLE_PAGE_URL}'. This might indicate session expiration or manual navigation away.")
                    logger.info("Attempting to re-navigate to the meter details page.")
                    driver.get(TABLE_PAGE_URL)
                    logger.info("Waiting 15 seconds for the meter readings page to load robustly after forced re-navigation...")
                    time.sleep(15)
                    # Re-verify table presence after re-navigation
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
                    )
                    reselect_instant_partial_dropdowns(driver)
                else:
                    logger.info("Refreshing page to get latest data for current cycle...")
                    driver.refresh()
                    logger.info("Page refreshed. Waiting a few seconds for content to generally appear (15s)...")
                    time.sleep(15)
                    reselect_instant_partial_dropdowns(driver)
                    logger.info("Dropdowns re-selected for current cycle. Proceeding with table scrape.")

                raw_extracted_readings = extract_data_from_table(driver)

                processed_readings = []
                if raw_extracted_readings:
                    logger.info(f"Successfully extracted {len(raw_extracted_readings)} raw readings from the web.")
                    for raw_row in raw_extracted_readings:
                        # Pass METER_ID and METER_NUMBER from config to process_raw_data as it's designed
                        processed_row = process_raw_data(raw_row, METER_ID, METER_NUMBER)
                        if processed_row:
                            processed_readings.append(processed_row)
                    logger.info(f"Processed {len(processed_readings)} valid readings for database insertion.")
                else:
                    logger.warning("No raw readings extracted in this cycle.")

                if processed_readings:
                    # Insert meter details (upsert) - this ensures meter is in DB before readings
                    db_manager.insert_meter_details(METER_ID, METER_NUMBER, location="Scraped Data Location")
                    db_manager.insert_meter_readings(processed_readings)
                    logger.info(f"Successfully inserted {len(processed_readings)} readings into the database.")
                else:
                    logger.warning("No valid readings to insert into the database in this cycle.")

            except WebDriverException as e:
                logger.error(f"WebDriver error during scraping cycle: {e}. Attempting recovery by re-navigation.", exc_info=True)
                capture_debug_info(driver, "webdriver_recovery")
                # Recovery: Try to go back to meter details page, wait for table, re-select dropdowns
                try:
                    logger.info("Attempting recovery: Re-navigating to meter details page and re-selecting dropdowns...")
                    driver.get(TABLE_PAGE_URL)
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.table.customTable"))
                    )
                    reselect_instant_partial_dropdowns(driver)
                    logger.info("Recovery attempt successful. Resuming scraping loop.")
                except WebDriverException as re_e:
                    logger.critical(f"Failed critical re-navigation during recovery: {re_e}. Exiting scraper.", exc_info=True)
                    break
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

# This __main__ block is intentionally minimal as main.py will call scraper.main()
if __name__ == '__main__':
    # For standalone testing of scraper.py, a basic logging setup is needed.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main()
