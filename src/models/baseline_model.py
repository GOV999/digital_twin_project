import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

# Import the abstract base class from forecasting_engine
from src.forecasting_engine import BaseForecastingModel

logger = logging.getLogger(__name__)

class BaselineModelModel(BaseForecastingModel):
    """
    An improved baseline model using a simple but powerful machine learning model:
    Random Forest Regressor.

    This model learns patterns from time-based features (e.g., hour of day,
    day of week) to predict future energy consumption.
    """
    def __init__(self):
        super().__init__("baseline_model")
        # Initialize the machine learning model.
        # n_estimators=100 means it will build 100 decision trees.
        # random_state=42 ensures that the model gives the same results every time for the same data.
        self.model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        self.is_trained = False
        logger.info(f"Initialized Machine Learning Baseline (Random Forest).")

    def _create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Creates time-series features from a datetime index.
        These features are what the model will learn from.
        """
        df['hour'] = df.index.hour
        df['dayofweek'] = df.index.dayofweek  # Monday=0, Sunday=6
        df['quarter'] = df.index.quarter
        df['month'] = df.index.month
        df['year'] = df.index.year
        df['dayofyear'] = df.index.dayofyear
        df['dayofmonth'] = df.index.day
        df['weekofyear'] = df.index.isocalendar().week.astype(int)
        return df

    def train(self, historical_data: List[Dict[str, Any]]):
        """
        Trains the Random Forest model on the historical data.
        
        Args:
            historical_data: A list of reading dictionaries.
        """
        if not historical_data:
            logger.warning(f"No historical data provided for {self.get_model_name()} training. Model not trained.")
            return

        try:
            # 1. Convert data to a pandas DataFrame
            df = pd.DataFrame(historical_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.set_index('timestamp')

            # 2. Ensure we only train on valid data
            df.dropna(subset=['energy_kwh_import'], inplace=True)
            if df.empty:
                logger.warning("Historical data is empty after dropping nulls. Model not trained.")
                return

            # 3. Feature Engineering: Create features from the timestamp index
            df = self._create_features(df)
            
            # 4. Define our features (X) and target (y)
            FEATURES = ['hour', 'dayofweek', 'quarter', 'month', 'year', 'dayofyear', 'dayofmonth', 'weekofyear']
            TARGET = 'energy_kwh_import'
            
            X_train = df[FEATURES]
            y_train = df[TARGET]

            # 5. Train the model
            logger.info(f"Training Random Forest model with {len(X_train)} data points...")
            self.model.fit(X_train, y_train)
            self.is_trained = True
            logger.info("Model training complete.")

        except Exception as e:
            logger.error(f"Error during model training: {e}", exc_info=True)
            self.is_trained = False

    def predict(self, start_timestamp: datetime, end_timestamp: datetime,
                frequency: timedelta = timedelta(minutes=15)) -> List[Dict[str, Any]]:
        """
        Generates predictions using the trained Random Forest model.
        """
        if not self.is_trained:
            logger.warning(f"{self.get_model_name()} has not been trained. Returning empty predictions.")
            return []

        # 1. Create a DataFrame for the future dates we want to predict
        future_dates = pd.date_range(start=start_timestamp, end=end_timestamp, freq=frequency)
        future_df = pd.DataFrame(index=future_dates)

        # 2. Engineer the same features for the future DataFrame
        future_df = self._create_features(future_df)

        # 3. Select the feature columns in the correct order
        FEATURES = ['hour', 'dayofweek', 'quarter', 'month', 'year', 'dayofyear', 'dayofmonth', 'weekofyear']
        X_future = future_df[FEATURES]

        # 4. Make predictions
        logger.info(f"Generating {len(X_future)} predictions with Random Forest model...")
        predicted_values = self.model.predict(X_future)
        
        # 5. Format the output to match the application's required structure
        predictions = []
        for timestamp, prediction in zip(future_df.index, predicted_values):
            # Convert pandas timestamp back to a python datetime object
            # The API will handle making it timezone-aware for the frontend.
            predictions.append({
                'timestamp': timestamp.to_pydatetime(),
                'predicted_kwh': float(prediction)
            })

        logger.info("Prediction generation complete.")
        return predictions