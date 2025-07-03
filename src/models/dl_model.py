# src/models/dl_model.py

import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Import the abstract base class
from src.models.base_model import BaseForecastingModel

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Define constants for model artifacts ---
# Assumes the script is run from the project root (where main.py is)
ARTIFACTS_DIR = 'ml_artifacts' 
MODEL_PATH = os.path.join(ARTIFACTS_DIR, 'finetuned_cnn_lstm_model_v1.h5')
SCALER_PATH = os.path.join(ARTIFACTS_DIR, 'simulated_scaler.pkl')

# --- Define constants for model configuration ---
SEQUENCE_LENGTH = 48  # Must match the sequence length used during training
REQUIRED_HISTORY_FOR_FEATURES = 336 # We need 1 week of data to calculate all lags
MODEL_FEATURES = [      # Must match the exact feature order from training
    'kwh', 'temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code',
    'hour', 'day_of_week', 'day_of_year', 'week_of_year', 'month',
    'is_weekend', 'lag_kwh_48', 'lag_kwh_336', 'rolling_mean_kwh_6',
    'rolling_std_kwh_6', 'rolling_mean_kwh_48'
]
TARGET_COLUMN_INDEX = MODEL_FEATURES.index('kwh')

class DlModel(BaseForecastingModel): # Class name must be DlModel to match "dl_model"
    """
    A deep learning forecasting model using a pre-trained, fine-tuned
    CNN-LSTM-Attention architecture.
    """
    def get_required_history_count(self) -> int:
        """Returns the specific number of records this DL model needs."""
        return REQUIRED_HISTORY_FOR_FEATURES
    
    def __init__(self):
        # The model name here must match the filename for the dynamic loader to work
        super().__init__("dl_model") 
        self.model = None
        self.scaler = None
        self._load_artifacts()

    def _load_artifacts(self):
        """Loads the saved Keras model and scikit-learn scaler from disk."""
        logger.info("DLModel: Loading pre-trained model and scaler...")
        try:
            # Note: The model needs to be loaded without the custom Attention layer object
            # if you are using a standard Keras version.
            # If it fails, you might need to pass custom_objects={'Attention': tf.keras.layers.Attention}
            self.model = tf.keras.models.load_model(MODEL_PATH)
            self.scaler = joblib.load(SCALER_PATH)
            logger.info("DLModel: Artifacts loaded successfully.")
        except IOError as e:
            logger.error(f"DLModel ERROR: Could not load artifacts. Ensure '{MODEL_PATH}' and '{SCALER_PATH}' exist.")
            raise

    def _prepare_dataframe(self, data: List[Dict[str, Any]]) -> pd.DataFrame:
        """Converts the list of dicts to a clean, indexed DataFrame."""
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # Rename column to match our 'kwh' standard
        df.rename(columns={'energy_kwh_import': 'kwh'}, inplace=True) 
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.set_index('timestamp')
        df.sort_index(inplace=True)
        # Ensure a regular frequency, which is good practice
        df = df.asfreq('30T').interpolate()
        return df
        
    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Creates the full set of features required by the model."""
        df_featured = df.copy()
        
        # Time-based features
        df_featured['hour'] = df_featured.index.hour
        df_featured['day_of_week'] = df_featured.index.dayofweek
        df_featured['day_of_year'] = df_featured.index.dayofyear
        df_featured['week_of_year'] = df_featured.index.isocalendar().week.astype(int)
        df_featured['month'] = df_featured.index.month
        df_featured['is_weekend'] = (df_featured.index.dayofweek >= 5).astype(int)

        # Weather and other features - assume they don't exist in scraped data, so we create dummies
        # In a future version, you could fetch weather data here.
        for col in ['temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code']:
             if col not in df_featured.columns:
                 df_featured[col] = 0.0

        # Lag and Rolling features
        df_featured['lag_kwh_48'] = df_featured['kwh'].shift(48)
        df_featured['lag_kwh_336'] = df_featured['kwh'].shift(336)
        df_featured['rolling_mean_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).mean()
        df_featured['rolling_std_kwh_6'] = df_featured['kwh'].shift(1).rolling(window=6).std()
        df_featured['rolling_mean_kwh_48'] = df_featured['kwh'].shift(1).rolling(window=48).mean()
        
        # We need to handle NaNs created during feature engineering
        # A backfill followed by a forward fill is a robust way to handle this
        df_featured.bfill(inplace=True)
        df_featured.ffill(inplace=True)
        
        return df_featured

    def train(self, historical_data: List[Dict[str, Any]]):
        """For this pre-trained model, training is a no-op."""
        logger.info(f"DLModel: Training is not required for this pre-trained model. Skipping.")
        pass

    def predict(self, start_timestamp: datetime, end_timestamp: datetime, historical_data: List[Dict[str, Any]], frequency: timedelta = timedelta(minutes=30)) -> List[Dict[str, Any]]:
        """Generates a forecast using an autoregressive prediction loop."""
        logger.info(f"DLModel: Starting prediction from {start_timestamp} to {end_timestamp}")
        
        if len(historical_data) < REQUIRED_HISTORY_FOR_FEATURES:
            logger.error(f"DLModel requires at least {REQUIRED_HISTORY_FOR_FEATURES} historical records for feature creation, but got {len(historical_data)}. Cannot predict.")
            return []

        # Convert the incoming list of dicts to a usable DataFrame
        history_df = self._prepare_dataframe(historical_data)
        
        # Generate future timestamps
        future_datetimes = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        
        predictions_list = []

        for dt in future_datetimes:
            # 1. Create a base for feature calculation including the new timestamp
            feature_base_df = history_df.tail(REQUIRED_HISTORY_FOR_FEATURES).copy()
            new_row = pd.DataFrame(index=[dt])
            feature_base_df = pd.concat([feature_base_df, new_row])
            
            # 2. Engineer features for this extended dataframe
            featured_df = self._create_features(feature_base_df)
            
            # 3. Get the last N rows to form the input sequence for the model
            input_sequence_df = featured_df.tail(SEQUENCE_LENGTH)

            if len(input_sequence_df) < SEQUENCE_LENGTH:
                logger.warning(f"Skipping prediction for {dt} due to insufficient data for a full sequence.")
                continue
            
            # 4. Scale the data and predict
            input_sequence_ordered = input_sequence_df[MODEL_FEATURES]
            scaled_sequence = self.scaler.transform(input_sequence_ordered)
            model_input = np.expand_dims(scaled_sequence, axis=0)
            
            prediction_scaled = self.model.predict(model_input, verbose=0)[0][0]
            
            # 5. Inverse transform to get the real kWh value
            dummy_pred = np.zeros((1, len(MODEL_FEATURES)))
            dummy_pred[0, TARGET_COLUMN_INDEX] = prediction_scaled
            prediction_kwh = self.scaler.inverse_transform(dummy_pred)[0, TARGET_COLUMN_INDEX]
            
            prediction_kwh = max(0, prediction_kwh)
            predictions_list.append({
                'timestamp': dt.to_pydatetime(),
                'predicted_kwh': float(prediction_kwh)
            })
            
            # 6. CRITICAL: Update history with the new prediction for the next loop
            history_df.loc[dt] = {'kwh': prediction_kwh}

        return predictions_list