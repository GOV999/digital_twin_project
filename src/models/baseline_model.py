# src/models/baseline_model.py

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from src.models.base_model import BaseForecastingModel
from src.weather_client import get_weather_data
from src.config_loader import get_location_config # <-- Use the new config loader

logger = logging.getLogger(__name__)

# Add weather features to the model's feature list
MODEL_FEATURES = [
    'hour', 'dayofweek', 'quarter', 'month', 'year',
    'dayofyear', 'dayofmonth', 'weekofyear',
    'temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code'
]
TARGET_COLUMN = 'energy_kwh_import'

class BaselineModel(BaseForecastingModel):
    """
    An improved baseline model using a Random Forest Regressor.
    This version is enhanced with weather data to provide a stronger benchmark.
    """
    def __init__(self):
        super().__init__("baseline_model")
        self.model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.is_trained = False
        logger.info("Initialized Weather-Aware ML Baseline (Random Forest).")

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Creates time-series and weather features from a datetime index."""
        df_featured = df.copy()
        
        # Fetch and join weather data using coordinates from the config file
        try:
            if not df_featured.empty:
                latitude, longitude = get_location_config()
                start_date = df_featured.index.min().strftime('%Y-%m-%d')
                end_date = df_featured.index.max().strftime('%Y-%m-%d')
                
                weather_df = get_weather_data(latitude, longitude, start_date, end_date)
                
                if not weather_df.empty:
                    df_featured = df_featured.join(weather_df, how='left')
                else:
                    logger.warning("BaselineModel: Weather data fetch unsuccessful.")
        except Exception as e:
            logger.error(f"BaselineModel: Weather integration failed: {e}. Using dummy values.")

        # Time-based features
        df_featured['hour'] = df_featured.index.hour
        df_featured['dayofweek'] = df_featured.index.dayofweek
        df_featured['quarter'] = df_featured.index.quarter
        df_featured['month'] = df_featured.index.month
        df_featured['year'] = df_featured.index.year
        df_featured['dayofyear'] = df_featured.index.dayofyear
        df_featured['dayofmonth'] = df_featured.index.day
        df_featured['weekofyear'] = df_featured.index.isocalendar().week.astype(int)

        # Fallback for missing weather columns
        for col in ['temp', 'humidity', 'dew_point', 'precipitation', 'cloud_cover_code']:
            if col not in df_featured.columns:
                df_featured[col] = 0.0

        # Fill any potential missing values after the join
        df_featured.ffill(inplace=True)
        df_featured.bfill(inplace=True)
        
        return df_featured

    def train(self, historical_data: List[Dict[str, Any]]):
        """Trains the Random Forest model on historical data with weather features."""
        if not historical_data:
            logger.warning(f"No historical data for {self.get_model_name()} training. Model not trained.")
            self.is_trained = False
            return

        try:
            df = pd.DataFrame(historical_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')
            df.dropna(subset=[TARGET_COLUMN], inplace=True)
            if df.empty:
                logger.warning("Historical data is empty after dropping nulls. Model not trained.")
                self.is_trained = False
                return

            df_featured = self._create_features(df)
            
            # Defensive check for columns
            for col in MODEL_FEATURES:
                if col not in df_featured.columns:
                    raise ValueError(f"Missing required feature column for training: {col}")

            X_train = df_featured[MODEL_FEATURES]
            y_train = df_featured[TARGET_COLUMN]

            logger.info(f"Training Random Forest model with {len(X_train)} data points...")
            self.model.fit(X_train, y_train)
            self.is_trained = True
            logger.info("Model training complete.")

        except Exception as e:
            logger.error(f"Error during Random Forest model training: {e}", exc_info=True)
            self.is_trained = False

    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                historical_data: List[Dict[str, Any]],
                frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
        if not self.is_trained:
            logger.warning(f"{self.get_model_name()} has not been trained. Returning empty predictions.")
            return []

        future_dates = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        future_df = pd.DataFrame(index=future_dates)
        future_df_featured = self._create_features(future_df)
        
        # Defensive check for columns
        for col in MODEL_FEATURES:
            if col not in future_df_featured.columns:
                raise ValueError(f"Missing required feature column for prediction: {col}")

        X_future = future_df_featured[MODEL_FEATURES]

        logger.info(f"Generating {len(X_future)} predictions with Random Forest model...")
        predicted_values = self.model.predict(X_future)
        
        predictions = []
        for timestamp, prediction in zip(future_df.index, predicted_values):
            predictions.append({
                'timestamp': timestamp.to_pydatetime(),
                'predicted_kwh': float(prediction)
            })
        return predictions