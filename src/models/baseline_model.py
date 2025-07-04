# src/models/baseline_model.py

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from src.models.base_model import BaseForecastingModel
from src.weather_client import get_weather_data
from src.config_loader import get_location_config

logger = logging.getLogger(__name__)

MODEL_FEATURES = [
    'hour', 'dayofweek', 'quarter', 'month', 'year',
    'dayofyear', 'dayofmonth', 'weekofyear',
    'temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code'
]
TARGET_COLUMN = 'kwh'

class BaselineModel(BaseForecastingModel):
    """
    An improved baseline model using a Random Forest Regressor, enhanced with
    weather data and event simulation capabilities.
    """
    def __init__(self, params: dict = None):
        super().__init__("baseline_model")
        n_estimators = params.get('n_estimators', 100) if params else 100
        self.model = RandomForestRegressor(n_estimators=n_estimators, random_state=42, n_jobs=-1)
        self.is_trained = False
        logger.info("Initialized Weather-Aware ML Baseline (Random Forest).")

    def _prepare_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        if not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        df.rename(columns={'energy_kwh_import': TARGET_COLUMN}, inplace=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.set_index('timestamp').sort_index()
        return df

    def _create_features(self, df: pd.DataFrame, event_data: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        df_featured = df.copy()

        if not isinstance(df_featured.index, pd.DatetimeIndex):
            if df_featured.empty: return df_featured
            df_featured.index = pd.to_datetime(df_featured.index, utc=True)
        
        df_featured = df_featured.tz_convert('UTC')
        
        weather_cols = [col for col in MODEL_FEATURES if col not in ['hour', 'dayofweek', 'quarter', 'month', 'year', 'dayofyear', 'dayofmonth', 'weekofyear']]
        df_featured.drop(columns=[col for col in weather_cols if col in df_featured.columns], inplace=True, errors='ignore')

        try:
            if not df_featured.empty:
                latitude, longitude = get_location_config()
                start_date = df_featured.index.min().strftime('%Y-%m-%d')
                end_date = df_featured.index.max().strftime('%Y-%m-%d')
                
                weather_df = get_weather_data(latitude, longitude, start_date, end_date)
                
                if not weather_df.empty:
                    df_featured = df_featured.join(weather_df, how='left')
        except Exception as e:
            logger.error(f"BaselineModel: Weather integration failed: {e}.")

        for col in weather_cols:
            if col not in df_featured.columns:
                df_featured[col] = 0.0
        
        if event_data:
            event_type, value = event_data.get('type'), event_data.get('value')
            if event_type == 'heatwave' and value is not None: df_featured['temp'] += value
            elif event_type == 'cold_snap' and value is not None: df_featured['temp'] -= value

        df_featured['hour'] = df_featured.index.hour
        df_featured['dayofweek'] = df_featured.index.dayofweek
        df_featured['quarter'] = df_featured.index.quarter
        df_featured['month'] = df_featured.index.month
        df_featured['year'] = df_featured.index.year
        df_featured['dayofyear'] = df_featured.index.dayofyear
        df_featured['dayofmonth'] = df_featured.index.day
        df_featured['weekofyear'] = df_featured.index.isocalendar().week.astype(int)
        
        df_featured.ffill(inplace=True)
        df_featured.bfill(inplace=True)

        for col in MODEL_FEATURES:
            if col not in df_featured.columns:
                df_featured[col] = 0.0
            df_featured[col] = pd.to_numeric(df_featured[col], errors='coerce').fillna(0)

        return df_featured

    def train(self, historical_data: List[Dict[str, Any]], event_data: Optional[Dict[str, Any]] = None):
        if not historical_data:
            self.is_trained = False; return
        try:
            df = self._prepare_dataframe(historical_data)
            df = df.asfreq('30min').interpolate(method='linear')
            df.dropna(subset=[TARGET_COLUMN], inplace=True)
            if df.empty:
                self.is_trained = False; return

            df_featured = self._create_features(df, event_data=event_data)
            
            X_train = df_featured[MODEL_FEATURES]
            y_train = df_featured[TARGET_COLUMN]

            self.model.fit(X_train, y_train)
            self.is_trained = True
        except Exception as e:
            logger.error(f"Error during Baseline model training: {e}", exc_info=True)
            self.is_trained = False

    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                historical_data: List[Dict[str, Any]], frequency: timedelta,
                event_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self.is_trained: return []

        # --- FIX: Removed the tz='UTC' argument. Pandas will infer it from the start/end times. ---
        future_dates = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        future_df = pd.DataFrame(index=future_dates)
        
        future_df_featured = self._create_features(future_df, event_data=event_data)
        X_future = future_df_featured[MODEL_FEATURES]

        predicted_values = self.model.predict(X_future)
        
        return [{'timestamp': ts.to_pydatetime(), 'predicted_kwh': float(pred)}
                for ts, pred in zip(future_df.index, predicted_values)]