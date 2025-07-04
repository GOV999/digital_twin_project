# src/models/dl_model.py

import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

from src.models.base_model import BaseForecastingModel
from src.weather_client import get_weather_data
from src.config_loader import get_location_config # <-- Use the new config loader

logger = logging.getLogger(__name__)

# Constants for model artifacts
ARTIFACTS_DIR = 'ml_artifacts' 
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'finetuned_cnn_lstm_model_v1.h5')
SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'simulated_scaler.pkl')

# Constants for model configuration
SEQUENCE_LENGTH = 48
REQUIRED_HISTORY_FOR_FEATURES = 336
MODEL_FEATURES = [
    'kwh', 'temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code',
    'hour', 'day_of_week', 'day_of_year', 'week_of_year', 'month',
    'is_weekend', 'lag_kwh_48', 'lag_kwh_336', 'rolling_mean_kwh_6',
    'rolling_std_kwh_6', 'rolling_mean_kwh_48'
]
TARGET_COLUMN_INDEX = MODEL_FEATURES.index('kwh')

class DlModel(BaseForecastingModel):
    """
    A deep learning forecasting model using a pre-trained CNN-LSTM architecture.
    This version integrates real-time weather data for improved accuracy.
    """
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
            logger.info("DLModel: Artifacts loaded successfully.")
        except IOError as e:
            logger.error(f"DLModel ERROR: Could not load artifacts. Ensure '{MODEL_PATH}' and '{SCALER_PATH}' exist.")
            raise

    def _prepare_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df.rename(columns={'energy_kwh_import': 'kwh'}, inplace=True) 
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp').sort_index()
        df = df.asfreq('30T').interpolate()
        return df
        
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df_featured = df.copy()
        
        try:
            latitude, longitude = get_location_config()
            start_date = df_featured.index.min().strftime('%Y-%m-%d')
            end_date = df_featured.index.max().strftime('%Y-%m-%d')
            
            weather_df = get_weather_data(latitude, longitude, start_date, end_date)
            
            if not weather_df.empty:
                df_featured = df_featured.join(weather_df, how='left')
        except Exception as e:
            logger.error(f"DLModel: Weather integration failed: {e}. Using dummy values.")

        # Time-based features
        df_featured['hour'] = df_featured.index.hour
        df_featured['day_of_week'] = df_featured.index.dayofweek
        df_featured['day_of_year'] = df_featured.index.dayofyear
        df_featured['week_of_year'] = df_featured.index.isocalendar().week.astype(int)
        df_featured['month'] = df_featured.index.month
        df_featured['is_weekend'] = (df_featured.index.dayofweek >= 5).astype(int)

        # Fallback for missing weather columns
        for col in ['temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code']:
             if col not in df_featured.columns:
                 df_featured[col] = 0.0

        # Lag and Rolling features
        df_featured['lag_kwh_48'] = df_featured['kwh'].shift(48)
        df_featured['lag_kwh_336'] = df_featured['kwh'].shift(336)
        df_featured['rolling_mean_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).mean()
        df_featured['rolling_std_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).std()
        df_featured['rolling_mean_kwh_48'] = df_featured['kwh'].shift(1).rolling(window=48).mean()
        
        df_featured.ffill(inplace=True)
        df_featured.bfill(inplace=True)
        
        return df_featured

    def train(self, historical_data: List[Dict[str, Any]]):
        logger.info("DLModel: Training is not required for this pre-trained model.")
        pass

    def predict(self, start_timestamp: datetime, end_timestamp: datetime, historical_data: List[Dict[str, Any]], frequency: timedelta = timedelta(minutes=30)) -> List[Dict[str, Any]]:
        logger.info(f"DLModel: Starting prediction from {start_timestamp} to {end_timestamp}")
        
        if len(historical_data) < self.get_required_history_count():
            logger.error(f"DLModel requires {self.get_required_history_count()} records but got {len(historical_data)}. Cannot predict.")
            return []

        history_df = self._prepare_dataframe(historical_data)
        future_datetimes = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        predictions_list = []

        for dt in future_datetimes:
            feature_base_df = history_df.tail(REQUIRED_HISTORY_FOR_FEATURES).copy()
            new_row = pd.DataFrame(index=[dt])
            feature_base_df = pd.concat([feature_base_df, new_row])
            
            featured_df = self._create_features(feature_base_df)
            
            input_sequence_df = featured_df.tail(SEQUENCE_LENGTH)
            if len(input_sequence_df) < SEQUENCE_LENGTH:
                continue
            
            input_sequence_ordered = input_sequence_df[MODEL_FEATURES]
            
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
            
            history_df.loc[dt] = {'kwh': prediction_kwh}

        return predictions_list