# src/models/baseline_model.py

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from src.models.base_model import BaseForecastingModel

logger = logging.getLogger(__name__)

# Define features as a constant to avoid repeating the list.
# This is a good practice to prevent bugs from typos.
MODEL_FEATURES = [
    'hour', 'dayofweek', 'quarter', 'month', 'year',
    'dayofyear', 'dayofmonth', 'weekofyear'
]
TARGET_COLUMN = 'energy_kwh_import'

# The class name is now "BaselineModel" to match the filename "baseline_model.py"
# This is important for your dynamic loader in forecasting_engine.py.
class BaselineModel(BaseForecastingModel):
    """
    An improved baseline model using a Random Forest Regressor.

    This model learns patterns from time-based features (e.g., hour of day,
    day of week) to predict future energy consumption. It serves as a strong,
    traditional ML baseline to compare against more complex DL models.
    """
    def __init__(self):
        super().__init__("baseline_model")
        # Initialize the machine learning model.
        # n_estimators=100 is a good default.
        # random_state=42 ensures reproducibility.
        # n_jobs=-1 uses all available CPU cores for faster training.
        self.model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.is_trained = False
        logger.info("Initialized Machine Learning Baseline (Random Forest).")

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Creates time-series features from a datetime index."""
        # This is excellent feature engineering for a baseline.
        df_featured = df.copy()
        df_featured['hour'] = df_featured.index.hour
        df_featured['dayofweek'] = df_featured.index.dayofweek
        df_featured['quarter'] = df_featured.index.quarter
        df_featured['month'] = df_featured.index.month
        df_featured['year'] = df_featured.index.year
        df_featured['dayofyear'] = df_featured.index.dayofyear
        df_featured['dayofmonth'] = df_featured.index.day
        df_featured['weekofyear'] = df_featured.index.isocalendar().week.astype(int)
        return df_featured

    def train(self, historical_data: List[Dict[str, Any]]):
        """Trains the Random Forest model on the historical data."""
        if not historical_data:
            logger.warning(f"No historical data provided for {self.get_model_name()} training. Model not trained.")
            self.is_trained = False
            return

        try:
            # 1. Convert data to a pandas DataFrame and prepare it
            df = pd.DataFrame(historical_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')

            # 2. Ensure we only train on valid data
            df.dropna(subset=[TARGET_COLUMN], inplace=True)
            if df.empty:
                logger.warning("Historical data is empty after dropping null kWh values. Model not trained.")
                self.is_trained = False
                return

            # 3. Feature Engineering
            df_featured = self._create_features(df)
            
            # 4. Define our features (X) and target (y)
            X_train = df_featured[MODEL_FEATURES]
            y_train = df_featured[TARGET_COLUMN]

            # 5. Train the model
            logger.info(f"Training Random Forest model with {len(X_train)} data points...")
            self.model.fit(X_train, y_train)
            self.is_trained = True
            logger.info("Model training complete.")

        except Exception as e:
            logger.error(f"Error during Random Forest model training: {e}", exc_info=True)
            self.is_trained = False

    # --- CRITICAL FIX: The signature now matches the BaseForecastingModel contract ---
    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                historical_data: List[Dict[str, Any]], # This argument is now present
                frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
        """
        Generates predictions using the trained Random Forest model.
        The 'historical_data' argument is unused here but required by the base class.
        """
        if not self.is_trained:
            logger.warning(f"{self.get_model_name()} has not been trained. Returning empty predictions.")
            return []

        # 1. Create a DataFrame for the future dates we want to predict
        future_dates = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        future_df = pd.DataFrame(index=future_dates)

        # 2. Engineer the same features for the future DataFrame
        future_df_featured = self._create_features(future_df)

        # 3. Select the feature columns in the correct order
        X_future = future_df_featured[MODEL_FEATURES]

        # 4. Make predictions
        logger.info(f"Generating {len(X_future)} predictions with Random Forest model...")
        predicted_values = self.model.predict(X_future)
        
        # 5. Format the output to match the application's required structure
        predictions = []
        for timestamp, prediction in zip(future_df.index, predicted_values):
            predictions.append({
                'timestamp': timestamp.to_pydatetime(),
                'predicted_kwh': float(prediction)
            })

        logger.info("Prediction generation complete.")
        return predictions