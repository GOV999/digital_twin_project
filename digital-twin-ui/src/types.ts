
export interface Meter {
  meter_id: string;
  location_type?: string;
  name?: string; // Assuming a potential name field
  status?: string; // e.g. "active", "inactive"
}

export interface MeterReading {
  reading_id: number;
  meter_id: string;
  timestamp: string; // ISO datetime string
  voltage_vrn: number | null;
  voltage_vyn: number | null;
  voltage_vbn: number | null;
  current_ir: number | null;
  current_iy: number | null;
  current_ib: number | null;
  energy_kwh_import: number | null;
  energy_kvah_import: number | null;
  energy_kwh_export: number | null;
  energy_kvah_export: number | null;
  network_info: string | null;
  ingestion_time: string | null; // ISO datetime string
  // 'units' is removed as energy_kwh_import implies kWh. Other units can be part of column names.
}

export interface ForecastPoint {
  timestamp: string; // ISO datetime string
  predicted_value: number;
  actual_value: number | null; 
  meter_id?: string;
  run_id?: string;
}

export interface ForecastMetrics {
  run_id: string;
  meter_id: string;
  model_name: string;
  forecast_generation_time: string; // ISO datetime string
  mae: number | null;
  rmse: number | null;
  prediction_start_time?: string; // ISO datetime string
  prediction_end_time?: string; // ISO datetime string
  training_data_hours?: number;
}

// For chart display
export interface ChartDataPoint {
  timestamp: number; // Unix timestamp for Recharts x-axis
  dateLabel: string; // Formatted date string for tooltip/axis
  actual: number | null | undefined; // Using undefined for Recharts to break lines
  predicted: number | null | undefined; // Using undefined for Recharts to break lines
}

// API Error structure (optional, for more detailed error handling)
export interface ApiError {
  message: string;
  status?: number;
  details?: any;
}