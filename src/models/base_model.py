# src/models/base_model.py

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

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

    # --- MODIFIED: Added the optional event_data parameter ---
    @abstractmethod
    def train(self, historical_data: List[Dict[str, Any]], event_data: Optional[Dict[str, Any]] = None):
        """
        Trains or prepares the model using historical data.

        Args:
            historical_data: A list of past meter readings.
            event_data (Optional): A dictionary describing a simulated event to apply
                                   before training, e.g., for 'holiday_shutdown'.
        """
        pass

    # --- MODIFIED: Added the optional event_data parameter ---
    @abstractmethod
    def predict(self,
                start_timestamp: datetime,
                end_timestamp: datetime,
                historical_data: List[Dict[str, Any]],
                frequency: timedelta,
                event_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Generates a forecast for a given time period.

        Args:
            start_timestamp: The beginning of the prediction period.
            end_timestamp: The end of the prediction period.
            historical_data: A list of past meter readings to create initial features.
            frequency: The time interval between predictions.
            event_data (Optional): A dictionary describing a simulated event to apply,
                                   e.g., for a 'heatwave'.
        """
        pass

    def get_required_history_count(self) -> int:
        """
        Returns the minimum number of historical records required for this
        model to make a prediction. Default is 1 for simple models.
        """
        return 1