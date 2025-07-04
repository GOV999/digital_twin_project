# src/models/dl_model.py

import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.models.base_model import BaseForecastingModel
from src.weather_client import get_weather_data
from src.config_loader import get_location_config

logger = logging.getLogger(__name__)

# Constants
ARTIFACTS_DIR = 'ml_artifacts' 
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'finetuned_cnn_lstm_model_v1.h5')
SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'simulated_scaler.pkl')
SEQUENCE_LENGTH = 48
REQUIRED_HISTORY_FOR_FEATURES = 336
MODEL_FEATURES = [
    'kwh', 'temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code',
    'hour', 'day_of_week', 'day_of_year', 'week_of_year', 'month',
    'is_weekend', 'lag_kwh_48', 'lag_kwh_336', 'rolling_mean_kwh_6',
    'rolling_std_kwh_6', 'rolling_mean_kwh_48'
]
TARGET_COLUMN = 'kwh'
TARGET_COLUMN_INDEX = MODEL_FEATURES.index(TARGET_COLUMN)

class DlModel(BaseForecastingModel):
    def __init__(self):
        super().__init__("dl_model") 
        self.model = None
        self.scaler = None
        self._load_artifacts()

    def get_required_history_count(self) -> int:
        return REQUIRED_HISTORY_FOR_FEATURES

    def _load_artifacts(self):
        logger.info("DLModel: Loading pre-trained model and scaler...")
        try:
            self.model = tf.keras.models.load_model(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
        except IOError as e:
            logger.error(f"DLModel ERROR: Could not load artifacts: {e}")
            raise

    def _prepare_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        df.rename(columns={'energy_kwh_import': TARGET_COLUMN}, inplace=True)
        df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        df = df.set_index('timestamp').sort_index()
        df = df.asfreq('30min').interpolate(method='linear')
        return df
        
    def _create_features(self, df: pd.DataFrame, event_data: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        df_featured = df.copy()

        if not isinstance(df_featured.index, pd.DatetimeIndex):
            if df_featured.empty: return df_featured
            df_featured.index = pd.to_datetime(df_featured.index, utc=True)
        
        df_featured = df_featured.tz_convert('UTC')
        
        weather_cols = ['temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code']
        df_featured.drop(columns=[col for col in weather_cols if col in df_featured.columns], inplace=True, errors='ignore')

        try:
            if not df_featured.empty:
                latitude, longitude = get_location_config()
                start_date, end_date = df_featured.index.min().strftime('%Y-%m-%d'), df_featured.index.max().strftime('%Y-%m-%d')
                weather_df = get_weather_data(latitude, longitude, start_date, end_date)
                if not weather_df.empty:
                    df_featured = df_featured.join(weather_df, how='left')
        except Exception as e:
            logger.error(f"DLModel: Weather integration failed: {e}.")

        for col in weather_cols:
            if col not in df_featured.columns:
                df_featured[col] = 0.0
        
        if event_data:
            event_type, value = event_data.get('type'), event_data.get('value')
            if event_type == 'heatwave' and value is not None: df_featured['temp'] += value
            elif event_type == 'cold_snap' and value is not None: df_featured['temp'] -= value
            elif event_type == 'holiday_shutdown' and value is not None:
                if 'kwh' in df_featured.columns: df_featured['kwh'] *= (1 - (value / 100.0))

        df_featured['hour'] = df_featured.index.hour
        df_featured['dayofweek'] = df_featured.index.dayofweek
        df_featured['dayofyear'] = df_featured.index.dayofyear
        df_featured['weekofyear'] = df_featured.index.isocalendar().week.astype(int)
        df_featured['month'] = df_featured.index.month
        df_featured['is_weekend'] = (df_featured.index.dayofweek >= 5).astype(int)

        if 'kwh' in df_featured.columns:
            df_featured['lag_kwh_48'] = df_featured['kwh'].shift(48)
            df_featured['lag_kwh_336'] = df_featured['kwh'].shift(336)
            df_featured['rolling_mean_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).mean()
            df_featured['rolling_std_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).std()
            df_featured['rolling_mean_kwh_48'] = df_featured['kwh'].shift(1).rolling(window=48).mean()
        
        df_featured.ffill(inplace=True)
        df_featured.bfill(inplace=True)
        
        for col in MODEL_FEATURES:
            if col not in df_featured.columns:
                df_featured[col] = 0.0
            df_featured[col] = pd.to_numeric(df_featured[col], errors='coerce').fillna(0)

        return df_featured

    def train(self, historical_data: List[Dict[str, Any]], event_data: Optional[Dict[str, Any]] = None):
        if event_data:
            logger.info(f"Applying event {event_data} to historical context for DL model.")
        pass

    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                historical_data: List[Dict[str, Any]], frequency: timedelta,
                event_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if len(historical_data) < self.get_required_history_count():
            return []

        history_df = self._prepare_dataframe(historical_data)
        history_df_with_events = self._create_features(history_df, event_data)
        
        # --- FIX: Removed the conflicting tz='UTC' argument ---
        future_datetimes = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        predictions_list = []

        for dt in future_datetimes:
            feature_base_df = history_df_with_events.tail(REQUIRED_HISTORY_FOR_FEATURES).copy()
            new_row = pd.DataFrame(index=[dt])
            feature_base_df = pd.concat([feature_base_df, new_row])
            
            featured_df = self._create_features(feature_base_df, event_data)
            
            input_sequence_df = featured_df.tail(SEQUENCE_LENGTH)
            if len(input_sequence_df) < SEQUENCE_LENGTH:
                continue
            
            input_sequence_ordered = featured_df[MODEL_FEATURES]
            
            scaled_sequence = self.scaler.transform(input_sequence_ordered)
            model_input = np.expand_dims(scaled_sequence, axis=0)
            
            prediction_scaled = self.model.predict(model_input, verbose=0)[0][0]
            
            dummy_pred = np.zeros((1, len(MODEL_FEATURES)))
            dummy_pred[0, TARGET_COLUMN_INDEX] = prediction_scaled
            prediction_kwh = self.scaler.inverse_transform(dummy_pred)[0, TARGET_COLUMN_INDEX]
            
            prediction_kwh = max(0, prediction_kwh)
            predictions_list.append({
                'timestamp': dt.to_pydatetime(),
                'predicted_kwh': float(prediction_kwh)
            })
            
            history_df_with_events.loc[dt] = {'kwh': prediction_kwh}

        return predictions_list