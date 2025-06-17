
import React from 'react';
import { ForecastMetrics } from '../types';
import DataCard from './DataCard';

interface MetricsDisplayProps {
  metrics: ForecastMetrics | null;
}

const MetricsDisplay: React.FC<MetricsDisplayProps> = ({ metrics }) => {
  if (!metrics) {
    return (
      <DataCard title="Forecast Metrics" value="No forecast metrics available." variant="info" />
    );
  }

  // Safely convert mae and rmse to numbers before using toFixed
  const maeValue = metrics.mae !== null && metrics.mae !== undefined ? Number(metrics.mae) : null;
  const rmseValue = metrics.rmse !== null && metrics.rmse !== undefined ? Number(metrics.rmse) : null;

  return (
    <div className="bg-slate-800 p-4 sm:p-6 rounded-lg shadow-xl">
      <h3 className="text-xl font-semibold mb-4 text-sky-300">Forecast Performance</h3>
      <div className="space-y-3">
        <DataCard title="Model Used" value={metrics.model_name || 'N/A'} />
        <DataCard 
          title="Mean Absolute Error (MAE)" 
          value={(maeValue !== null && !isNaN(maeValue)) ? maeValue.toFixed(4) : 'N/A'} 
          unit="kWh"
        />
        <DataCard 
          title="Root Mean Sq. Error (RMSE)" 
          value={(rmseValue !== null && !isNaN(rmseValue)) ? rmseValue.toFixed(4) : 'N/A'} 
          unit="kWh"
        />
        <DataCard title="Forecast Period" value={metrics.forecast_period || 'N/A'} />
        <DataCard title="Run Timestamp" value={metrics.run_timestamp || 'N/A'} />
        {metrics.run_id && <DataCard title="Run ID" value={metrics.run_id} smallText={true} />}
      </div>
    </div>
  );
};

export default MetricsDisplay;
