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

export interface ForecastMetrics {
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

// New types for Scraper Control

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