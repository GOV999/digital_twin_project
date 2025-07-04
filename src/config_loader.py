# src/config_loader.py

import configparser
import os
import logging

logger = logging.getLogger(__name__)

# This part runs only once when the module is first imported, making it efficient.
_config = configparser.ConfigParser()
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.ini')

if not os.path.exists(CONFIG_FILE_PATH):
    raise FileNotFoundError(f"CRITICAL: The configuration file was not found at {CONFIG_FILE_PATH}")

_config.read(CONFIG_FILE_PATH)

def get_location_config():
    """
    Reads and returns the default location coordinates from config.ini.
    Provides a hardcoded fallback if the config is missing, with a warning.
    """
    try:
        latitude = _config.getfloat('Location', 'default_latitude')
        longitude = _config.getfloat('Location', 'default_longitude')
        return latitude, longitude
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logger.warning(
            f"Could not find [Location] section or keys in config.ini. "
            f"Using hardcoded fallback coordinates. Error: {e}"
        )
        # Fallback to Jaipur coordinates if config is not set
        return 26.9124, 75.7873

# You can add other config-reading functions here in the future, for example:
# def get_scraper_config():
#     ...