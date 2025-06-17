
export interface Meter {
  meter_id: string;
  location_type: string;
  installation_date: string; // ISO date string
  status: string;
}

export interface Reading {
  meter_id: string;
  timestamp: string; // ISO date string
  energy_kwh_import: number;
  is_simulated: boolean; // Not directly used in UI but part of data model
}

export interface ForecastRun {
  run_id: string;
  meter_id: string;
  model_name: string;
  forecast_start_time: string; // ISO date string
  forecast_end_time: string; // ISO date string
  mae: number | null;
  rmse: number | null;
  run_timestamp: string; // ISO date string
}

export interface CombinedDataPoint {
  timestamp: string; // ISO date string
  actual_kwh: number | null;
  predicted_kwh: number | null;
  is_forecast: boolean; // Provided by API, can be used for styling if needed
}

// For MetricsDisplay component
export interface ForecastMetrics {
  mae: number | null;
  rmse: number | null;
  model_name?: string;
  run_id?: string;
  run_timestamp?: string;
  forecast_period?: string;
}
    