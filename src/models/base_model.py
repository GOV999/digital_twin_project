# src/models/base_model.py  <-- NEW FILE

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List

class BaseForecastingModel(ABC):
    """
    Abstract Base Class for all forecasting models in the digital twin.
    It defines the standard interface that all models must implement.
    """
    def __init__(self, model_name: str):
        self.model_name = model_name

    def get_model_name(self) -> str:
        """Returns the name of the model."""
        return self.model_name

    @abstractmethod
    def train(self, historical_data: List[Dict[str, Any]]):
        """Trains or prepares the model using historical data."""
        pass

    @abstractmethod
    def predict(self, start_timestamp: datetime, end_timestamp: datetime, historical_data: List[Dict[str, Any]], frequency: timedelta) -> List[Dict[str, Any]]:
        """Generates a forecast for a given time period."""
        pass

    def get_required_history_count(self) -> int:
        """
        Returns the minimum number of historical records required for this
        model to make a prediction. Default is 1 for simple models.
        """
        return 1