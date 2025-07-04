# src/weather_client.py
import requests
import pandas as pd
import logging

logger = logging.getLogger(__name__)
API_URL = "https://archive-api.open-meteo.com/v1/archive"

def get_weather_data(latitude: float, longitude: float, start_date: str, end_date: str) -> pd.DataFrame:
    params = {
        "latitude": latitude, "longitude": longitude,
        "start_date": start_date, "end_date": end_date,
        "hourly": "temperature_2m,relative_humidity_2m,dew_point_2m,precipitation,cloud_cover",
        "timezone": "auto" # Ask for local time to correctly interpret timestamps
    }
    
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame(data['hourly'])
        
        # Create a timezone-aware index first using the provided timezone string from the API
        df['timestamp'] = pd.to_datetime(df['time']).dt.tz_localize(data['timezone'])
        
        # --- FIX: Convert the final index to UTC for universal compatibility ---
        df = df.set_index('timestamp').tz_convert('UTC')
        
        df = df.drop(columns=['time'])
        df.rename(columns={
            'temperature_2m': 'temp', 'relative_humidity_2m': 'humidity',
            'dew_point_2m': 'dew_point', 'cloud_cover': 'cloud_cover_code'
        }, inplace=True)
        
        df_resampled = df.resample('30min').interpolate(method='linear')
        
        return df_resampled
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch weather data: {e}", exc_info=True)
        return pd.DataFrame()