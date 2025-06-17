export interface Meter {
  meter_id: string;
  location_type?: string;
  name?: string; 
  status?: string; 
}

export interface MeterReading {
  reading_id: number;
  meter_id: string;
  timestamp: string; 
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
  ingestion_time: string | null; 
}

export interface ForecastPoint {
  timestamp: string; 
  predicted_kwh: number;      // Corrected from predicted_value
  actual_kwh: number | null;  // Changed actual_value to actual_kwh to match backend
  prediction_id?: number;     // From backend schema
  run_id?: string;            // From backend schema
  // meter_id is usually part of the run, not each point, but can be kept if backend sends it
}

export interface ForecastMetrics {
  run_id: string;
  meter_id: string;
  model_name: string;
  prediction_start_time?: string; 
  prediction_end_time?: string; 
  training_data_start?: string; // Added to match db_manager potential
  training_data_end?: string;   // Added to match db_manager potential
  mae: number | null;
  rmse: number | null;
  run_timestamp?: string;       // Added to match db_manager
  // forecast_generation_time seems to be run_timestamp
  // training_data_hours is not directly in forecast_runs, calculated if needed
}

export interface ChartDataPoint {
  timestamp: number; 
  dateLabel: string; 
  actual: number | null | undefined; 
  predicted: number | null | undefined; 
}

export interface ApiError {
  message: string;
  status?: number;
  details?: any;
}