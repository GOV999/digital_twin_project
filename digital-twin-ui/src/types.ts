// src/types.ts

export interface Meter {
  meter_id: string;
  name: string;
  location: string;
  meter_number: string;
  meter_no: string;
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
  predicted_kwh: number; 
  actual_kwh: number | null; 
  prediction_id?: number; 
  run_id?: string;  
}

// MODIFIED: This interface now better reflects the detailed run info.
// It can be used for displaying metrics cards or logs of past runs.
export interface ForecastRunDetails {
  run_id: string;
  meter_id: string;
  model_name: string;
  prediction_start_time?: string; 
  prediction_end_time?: string; 
  training_data_start?: string; 
  training_data_end?: string;   
  mae: number | null;
  rmse: number | null;
  run_timestamp?: string;       
}

// NEW: This is the specific type for the response from the /simulate endpoint.
// It clearly defines all the new fields related to the graceful fallback.
export interface SimulationResponse {
  message: string;
  status: 'success' | 'error';
  run_id?: string;
  metrics?: {
    mae: number | null;
    rmse: number | null;
  };
  model_requested?: string;
  model_used?: string;
  fallback_reason?: string | null;
}

// Chart data point remains the same, it's a good generic type for plotting.
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

// --- Scraper Control Types ---
// These are well-defined and don't need changes.

export type ScraperRunStatus = 'running' | 'stopped' | 'error' | 'error_stopping' | 'not_started';

export interface ScraperStatusResponse {
  statuses: { [meterId: string]: ScraperRunStatus };
}

export interface ScraperActionResponse {
  status: ScraperRunStatus;
  message?: string;
}

export interface ScraperLogResponse {
  logs: string[];
  error?: string;
}