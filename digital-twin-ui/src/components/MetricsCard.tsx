import React from 'react';
import * as CustomTypes from '../types'; // Changed to namespace import

interface MetricsCardProps {
  metrics: CustomTypes.ForecastMetrics;
}

const MetricItem: React.FC<{ label: string; value: string | number | null | undefined; unit?: string }> = ({ label, value, unit }) => {
    const displayValue = (value === null || value === undefined || (typeof value === 'number' && isNaN(value)))
        ? 'N/A'
        : value;
    return (
        <div className="metric-item">
            <span className="metric-item-label">{label}</span>
            <span className="metric-item-value">
                {displayValue} {value !== null && value !== undefined && unit ? unit : ''}
            </span>
        </div>
    );
};

const MetricsCard: React.FC<MetricsCardProps> = ({ metrics }) => {
  const { model_name, mae, rmse, forecast_generation_time, training_data_hours, prediction_start_time, prediction_end_time } = metrics;

  return (
    <div className="card">
      <h2 className="card-title">Forecasting Model Performance</h2>
      <div className="metrics-grid">
        <MetricItem label="Model Name" value={model_name || 'N/A'} />
        <MetricItem label="MAE" value={mae?.toFixed(3)} />
        <MetricItem label="RMSE" value={rmse?.toFixed(3)} />
        {forecast_generation_time && <MetricItem label="Forecast Generated" value={new Date(forecast_generation_time).toLocaleString()} />}
        {training_data_hours !== undefined && <MetricItem label="Training Data" value={training_data_hours} unit="hours" />}
        {prediction_start_time && <MetricItem label="Prediction Start" value={new Date(prediction_start_time).toLocaleString()} />}
        {prediction_end_time && <MetricItem label="Prediction End" value={new Date(prediction_end_time).toLocaleString()} />}
      </div>
    </div>
  );
};

export default MetricsCard;