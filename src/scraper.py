import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time
import datetime 
import sys
import os
import traceback
import logging
import configparser

# --- Configuration & Path Setup ---
# Calculate the base directory of the project (digital_twin_project/)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define paths for data, logs, and debug dumps relative to BASE_DIR
DATA_DIR = os.path.join(BASE_DIR, 'data')
LOG_DIR = os.path.join(BASE_DIR, 'logs')
DEBUG_DUMPS_DIR = os.path.join(BASE_DIR, 'debug_dumps')
SCREENSHOT_DIR = os.path.join(DEBUG_DUMPS_DIR, 'screenshots')
PAGE_SOURCE_DIR = os.path.join(DEBUG_DUMPS_DIR, 'page_sources')

# Ensure directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)
os.makedirs(PAGE_SOURCE_DIR, exist_ok=True)

# Define file paths
OUTPUT_CSV_FILE = os.path.join(DATA_DIR, "meter_readings.csv")
LOG_FILE = os.path.join(LOG_DIR, 'scraper.log')
CONFIG_PATH = os.path.join(BASE_DIR, 'config.ini')

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, # Set to logging.DEBUG for more verbose output temporarily
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Also print to console
    ]
)
logger = logging.getLogger(__name__)

# --- Load Configuration from config.ini ---
config = configparser.ConfigParser()
if not os.path.exists(CONFIG_PATH):
    logger.critical(f"Configuration file not found: {CONFIG_PATH}. Please create it.")
    sys.exit(1)

try:
    config.read(CONFIG_PATH)
    LOGIN_URL = config.get('Scraper', 'LOGIN_URL')
    DASHBOARD_URL = config.get('Scraper', 'DASHBOARD_URL')
    TABLE_PAGE_URL = config.get('Scraper', 'TABLE_PAGE_URL')
    RELOAD_INTERVAL_SECONDS = config.getint('Scraper', 'RELOAD_INTERVAL_SECONDS')
    
except Exception as e:
    logger.critical(f"Error loading configuration from config.ini: {e}", exc_info=True)
    sys.exit(1)

# --- Target Columns for Data Extraction (Duplicate removed) ---
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
    # Removed the duplicate "Cumulative energy, kVAh (Export)"
    "Network Info"
]

# --- Helper functions ---
def parse_datetime(dt_str):
    """Parses a date-time string in 'DD/MM/YYYY HH:MM' format."""
    if pd.isna(dt_str) or not isinstance(dt_str, str):
        return pd.NaT # Not a Time
    try:
        return pd.to_datetime(dt_str, format='%d/%m/%Y %H:%M')
    except Exception:
        logger.warning(f"Could not parse datetime string: '{dt_str}'. Returning NaT.")
        return pd.NaT

def load_latest_timestamp_from_csv(file_path):
    """
    Reads only the first data row of the CSV to get the latest timestamp.
    Assumes the CSV is sorted newest-first for efficiency.
    Returns a pandas Timestamp object or None if file is empty/invalid.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None
    try:
        # Read only the first row (after header)
        df_head = pd.read_csv(file_path, nrows=1, encoding='utf-8')
        if not df_head.empty and "Real time clock, date and time" in df_head.columns:
            latest_str = df_head.loc[0, "Real time clock, date and time"]
            return parse_datetime(latest_str)
    except Exception as e:
        logger.error(f"Error reading latest timestamp from CSV '{file_path}': {e}", exc_info=True)
    return None

# --- Function to re-select dropdowns ---
def reselect_instant_partial_dropdowns(driver):
    logger.info("Attempting to re-select 'Instant Profile' -> 'Instant Partial'...")
    timestamp_for_debug = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    try:
        instant_profile_li_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]")
        
        logger.debug(f"Waiting for 'Instant Profile' parent li element: {instant_profile_li_locator} to be visible for hover (max 60s)...")
        profile_dropdown_li = WebDriverWait(driver, 60).until(
            EC.visibility_of_element_located(instant_profile_li_locator)
        )
        
        ActionChains(driver).move_to_element(profile_dropdown_li).perform()
        logger.debug("Hovered over 'Instant Profile' parent li element.")

        time.sleep(2) # Give a short moment for the submenu to appear

        dropdown_ul_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul[contains(@ng-show, 'tab.id==11') and (contains(@style, 'display: block') or not(contains(@style, 'display: none')))]")
        
        logger.debug(f"Waiting for dropdown <ul> container: {dropdown_ul_locator} to be visible (max 30s)...")
        WebDriverWait(driver, 30).until(
            EC.visibility_of_element_located(dropdown_ul_locator)
        )
        logger.debug("Dropdown <ul> container is now visible.")

        instant_partial_option_locator = (By.XPATH, "//li[./a[normalize-space(text())='Instant Profile']]/ul//div[@class='InstantPushdropdown']//a[normalize-space(text())='Instant Partial']")

        logger.debug(f"Waiting for 'Instant Partial' option: {instant_partial_option_locator} to be clickable (max 30s)...")
        partial_option = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable(instant_partial_option_locator)
        )
        partial_option.click()
        logger.info("Selected 'Instant Partial'.")

        time.sleep(5) # Wait for page content to update after selection
        logger.info("Dropdown selections complete and page should be updated.")

    except Exception as e:
        logger.error(f"Failed to re-select 'Instant Profile' -> 'Instant Partial': {type(e).__name__} - {e}", exc_info=True)
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"dropdown_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"dropdown_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
        raise # Re-raise the exception to stop execution


# --- Function to scrape table data (can scrape top X rows or all) ---
def scrape_table_data(driver, num_rows=None):
    logger.info(f"Attempting to scrape {'top ' + str(num_rows) + ' row(s)' if num_rows else 'all visible rows'} from table...")
    timestamp_for_debug = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

    try:
        table_locator = (By.CSS_SELECTOR, "table.table.customTable")

        logger.debug("Adding a 10-second sleep to allow for full rendering before table scrape...")
        time.sleep(10)

        logger.debug(f"Waiting for main table element: {table_locator} to be present and visible (max 90s)...")
        WebDriverWait(driver, 90).until(EC.visibility_of_element_located(table_locator))
        
        table = driver.find_element(*table_locator)
        logger.debug(f"Table element found. Displayed: {table.is_displayed()}, Size: {table.size}")

        tbody_locator = (By.CSS_SELECTOR, "table.table.customTable tbody")
        logger.debug(f"Waiting for table body: {tbody_locator} to be present (max 30s)...")
        WebDriverWait(driver, 30).until(EC.presence_of_element_located(tbody_locator))

        first_row_check_locator = (By.CSS_SELECTOR, "table.table.customTable tbody tr.evenRow")
        logger.debug(f"Waiting for at least one data row: {first_row_check_locator} to be visible (max 30s)...")
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located(first_row_check_locator))

        logger.debug("Adding a 2-second buffer to allow all cell data to render...")
        time.sleep(2)

        # Header extraction
        headers_found = []
        header_elements = table.find_elements(By.XPATH, ".//thead//th")
        for th in header_elements:
            span_element = th.find_elements(By.TAG_NAME, "span")
            if span_element:
                headers_found.append(span_element[0].text.strip())
            else:
                headers_found.append(th.text.strip())

        if "Sl" in headers_found and "Sl." not in headers_found:
            headers_found[headers_found.index('Sl')] = 'Sl.' # Correct 'Sl' to 'Sl.' if found as 'Sl'

        logger.debug(f"Headers found on page: {headers_found}")
        logger.debug(f"Expected TARGET_COLUMNS: {TARGET_COLUMNS}")

        col_indices = {}
        for target_col in TARGET_COLUMNS:
            try:
                col_indices[target_col] = headers_found.index(target_col)
            except ValueError:
                logger.warning(f"Target column '{target_col}' not found in scraped headers. This column will be empty in output.")
                col_indices[target_col] = -1

        if all(idx == -1 for idx in col_indices.values()):
            logger.error("None of the TARGET_COLUMNS were found in the scraped headers. Aborting scrape for this cycle.")
            return None

        data = []
        # Select rows. If num_rows is specified, take only that many, otherwise all visible.
        rows_to_scrape_elements = table.find_elements(By.XPATH, ".//tbody/tr[contains(@class, 'Row')]")
        if num_rows is not None:
            rows_to_scrape_elements = rows_to_scrape_elements[:num_rows]


        if not rows_to_scrape_elements:
            logger.info("No data rows found in the table's tbody to scrape.")
            return None

        for i, row_element in enumerate(rows_to_scrape_elements):
            cells_th = row_element.find_elements(By.TAG_NAME, "th")
            cells_td = row_element.find_elements(By.TAG_NAME, "td")
            all_cells_elements = cells_th + cells_td

            row_data = {}
            for target_col in TARGET_COLUMNS:
                idx = col_indices.get(target_col, -1)
                if idx != -1 and idx < len(all_cells_elements):
                    cell_element = all_cells_elements[idx]
                    span_in_cell = cell_element.find_elements(By.TAG_NAME, "span")
                    if span_in_cell:
                        row_data[target_col] = span_in_cell[0].text.strip()
                    else:
                        row_data[target_col] = cell_element.text.strip()
                else:
                    if idx != -1: 
                            logger.warning(f"For scraped row {i+1}, target column '{target_col}' (expected index {idx}) is out of bounds for {len(all_cells_elements)} cells found.")
                    row_data[target_col] = ""

            if any(value for value in row_data.values() if value):
                data.append(row_data)
            else:
                logger.debug(f"Skipping empty or mostly empty scraped row {i+1} from table.")

        if not data:
            logger.info("No meaningful data extracted during scrape process.")
            return None

        df_scraped = pd.DataFrame(data, columns=TARGET_COLUMNS) # Ensure all target columns are present from start
        # Convert to datetime objects for comparison and sorting
        df_scraped['Real time clock, date and time'] = df_scraped['Real time clock, date and time'].apply(parse_datetime)
        df_scraped.dropna(subset=['Real time clock, date and time'], inplace=True) # Remove rows with bad timestamps
        
        # The webpage displays newest first, so keep this order for new data
        if not df_scraped.empty:
            df_scraped.sort_values(by='Real time clock, date and time', ascending=False, inplace=True)
            # IMPORTANT FIX: Reset index after sorting to ensure unique index for concatenation
            df_scraped.reset_index(drop=True, inplace=True)
            logger.debug(f"Scraped {len(df_scraped)} row(s) and sorted them newest first.")

        # Convert back to string format for CSV writing (only for 'Real time clock, date and time')
        if not df_scraped.empty and 'Real time clock, date and time' in df_scraped.columns:
            df_scraped['Real time clock, date and time'] = df_scraped['Real time clock, date and time'].dt.strftime('%d/%m/%Y %H:%M')

        return df_scraped

    except Exception as e:
        logger.error(f"Error during table scraping: {type(e).__name__} - {e}", exc_info=True)
        screenshot_path = os.path.join(SCREENSHOT_DIR, f"scrape_error_{timestamp_for_debug}.png")
        driver.save_screenshot(screenshot_path)
        logger.error(f"Screenshot saved to: {screenshot_path}")
        page_source_path = os.path.join(PAGE_SOURCE_DIR, f"scrape_error_page_source_{timestamp_for_debug}.html")
        with open(page_source_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.error(f"Page source saved to: {page_source_path}")
        raise # Re-raise to ensure the main loop catches it


# --- Main execution block ---
if __name__ == "__main__":
    # Ensure CSV is empty at the start of each run
    if os.path.exists(OUTPUT_CSV_FILE):
        try:
            os.remove(OUTPUT_CSV_FILE)
            logger.info(f"Existing CSV file '{OUTPUT_CSV_FILE}' deleted to ensure an empty start.")
        except Exception as e:
            logger.error(f"Error deleting existing CSV file '{OUTPUT_CSV_FILE}': {e}", exc_info=True)
            # Decide if to exit or proceed with potentially stale data. For now, we'll proceed.

    logger.info("Starting Selenium WebDriver...")
    driver = None

    try:
        # Initialize WebDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service)
        driver.maximize_window()

        # --- MANUAL LOGIN SECTION ---
        logger.info("\n*** MANUAL INTERACTION REQUIRED ***")
        logger.info(f"Please log in manually in the Chrome browser that just opened. Navigate to: {LOGIN_URL}")
        logger.info(f"Ensure you land on the dashboard URL: {DASHBOARD_URL}")
        
        driver.get(LOGIN_URL)

        input("\nPress ENTER in THIS terminal when you are on the dashboard and ready to proceed: ")
        logger.info("Manual login acknowledged. Proceeding...")
        # --- END MANUAL LOGIN SECTION ---

        logger.info(f"Navigating to meter readings page: {TABLE_PAGE_URL}")
        driver.get(TABLE_PAGE_URL)

        logger.info("Waiting 15 seconds for the meter readings page to load robustly after navigation...")
        time.sleep(15)

        # Initial dropdown selection
        reselect_instant_partial_dropdowns(driver)
        logger.info("Initial dropdown selections automated successfully.")

        # Main scraping loop
        while True:
            current_url_main = driver.current_url
            if TABLE_PAGE_URL not in current_url_main:
                logger.warning(f"Current URL '{current_url_main}' does not match expected TABLE_PAGE_URL '{TABLE_PAGE_URL}'. This might indicate session expiration or manual navigation away.")
                logger.info("You will need to manually log in again if your session has expired.")
                input("\nPress ENTER in THIS terminal once you have manually re-logged in and are on the correct page (or are ready to proceed with a fresh navigation): ")
                driver.get(TABLE_PAGE_URL) # Attempt to navigate back
                time.sleep(15)
                reselect_instant_partial_dropdowns(driver)
            else:
                logger.info("Refreshing page to get latest data for current cycle...")
                driver.refresh()
                logger.info("Page refreshed. Waiting a few seconds for content to generally appear (15s)...")
                time.sleep(15)
                reselect_instant_partial_dropdowns(driver)
                logger.info("Dropdowns re-selected for current cycle. Proceeding with table scrape.")

            # --- CSV Data Handling Logic (New Strategy) ---
            latest_timestamp_in_csv = load_latest_timestamp_from_csv(OUTPUT_CSV_FILE)
            
            if latest_timestamp_in_csv is None:
                logger.info("CSV is empty or new. Performing initial full scrape (10 rows).")
                df_scraped_current = scrape_table_data(driver, num_rows=10) # Scrape initial N rows
            else:
                logger.info(f"CSV exists. Latest timestamp in CSV: {latest_timestamp_in_csv}. Scraping only top row.")
                df_scraped_current = scrape_table_data(driver, num_rows=1) # Scrape only the top row

            if df_scraped_current is not None and not df_scraped_current.empty:
                # Convert the 'Real time clock, date and time' column in df_scraped_current back to datetime objects
                # for proper comparison, as scrape_table_data formats it to string before return.
                # Only if it's not already datetime.
                if pd.api.types.is_string_dtype(df_scraped_current['Real time clock, date and time']):
                    df_scraped_current['Real time clock, date and time'] = df_scraped_current['Real time clock, date and time'].apply(parse_datetime)
                    df_scraped_current.dropna(subset=['Real time clock, date and time'], inplace=True)
                
                if df_scraped_current.empty: # Check again after conversion if it became empty
                    logger.warning("Scraped data became empty after datetime conversion/cleanup. Skipping CSV update.")
                    continue

                new_top_row_timestamp_dt = df_scraped_current.loc[0, 'Real time clock, date and time']

                if latest_timestamp_in_csv is None or new_top_row_timestamp_dt > latest_timestamp_in_csv:
                    logger.info(f"Found new data (Timestamp: {new_top_row_timestamp_dt}). Updating CSV.")
                    
                    # Read existing CSV data
                    existing_df = pd.DataFrame(columns=TARGET_COLUMNS) # Initialize empty DataFrame
                    if os.path.exists(OUTPUT_CSV_FILE) and os.path.getsize(OUTPUT_CSV_FILE) > 0:
                        try:
                            existing_df = pd.read_csv(OUTPUT_CSV_FILE, encoding='utf-8')
                            logger.debug(f"Read {len(existing_df)} existing rows from CSV.")
                            # Convert datetime column in existing CSV for consistent type
                            if "Real time clock, date and time" in existing_df.columns:
                                existing_df['Real time clock, date and time'] = existing_df['Real time clock, date and time'].apply(parse_datetime)
                                existing_df.dropna(subset=['Real time clock, date and time'], inplace=True)
                            # IMPORTANT FIX: Reset index after reading existing data
                            existing_df.reset_index(drop=True, inplace=True) 
                        except pd.errors.EmptyDataError:
                            logger.debug("Existing CSV is empty for merge.")
                        except Exception as e:
                            logger.error(f"Error reading existing CSV for merge: {e}", exc_info=True)
                            existing_df = pd.DataFrame(columns=TARGET_COLUMNS) # Reset if error

                    # Concatenate new scraped data (which is already a DataFrame) with existing DataFrame
                    # The `df_scraped_current` from scrape_table_data is already sorted newest first
                    # We want to prepend this to `existing_df`
                    combined_df = pd.concat([df_scraped_current, existing_df], ignore_index=True)
                    logger.debug(f"Combined existing and new scraped data. Total before deduplication: {len(combined_df)} rows.")

                    # Sort the entire combined DataFrame by timestamp descending (newest first)
                    combined_df.sort_values(by='Real time clock, date and time', ascending=False, inplace=True)
                    logger.debug("Combined and sorted DataFrame newest first.")

                    # Deduplicate based on Meter No. and Real time clock, date and time
                    initial_rows_count = len(combined_df)
                    combined_df.drop_duplicates(subset=['Meter No.', 'Real time clock, date and time'], inplace=True)
                    if len(combined_df) < initial_rows_count:
                        logger.info(f"Removed {initial_rows_count - len(combined_df)} duplicate rows.")
                    
                    # Convert timestamp back to string format for CSV writing
                    if 'Real time clock, date and time' in combined_df.columns:
                        combined_df['Real time clock, date and time'] = combined_df['Real time clock, date and time'].dt.strftime('%d/%m/%Y %H:%M')

                    # Overwrite the CSV with the sorted and deduplicated data
                    combined_df.to_csv(OUTPUT_CSV_FILE, mode='w', header=True, index=False, encoding='utf-8')
                    logger.info(f"Successfully updated CSV with {len(combined_df)} rows. Newest entry: {new_top_row_timestamp_dt}")

                else:
                    logger.info(f"No new data found (webpage top row timestamp: {new_top_row_timestamp_dt} is not newer than CSV's latest: {latest_timestamp_in_csv}). Skipping CSV update.")
            else:
                logger.info("Scraped data is empty or invalid. Skipping CSV update.")

            logger.info(f"Waiting for {RELOAD_INTERVAL_SECONDS // 60} minutes ({RELOAD_INTERVAL_SECONDS} seconds) before next scrape cycle...")
            time.sleep(RELOAD_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Script interrupted by user. Exiting.")
    except Exception as e:
        logger.critical(f"A critical, unhandled error occurred in the main scraper loop: {type(e).__name__} - {e}", exc_info=True)
        if driver:
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"critical_error_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            driver.save_screenshot(screenshot_path)
            logger.critical(f"Screenshot of critical error saved to: {screenshot_path}")
    finally:
        if driver is not None:
            logger.info("Closing browser...")
            driver.quit()
        logger.info("Scraper script execution finished.")
        sys.exit()