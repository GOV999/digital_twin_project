// src/services/apiService.ts

import { API_BASE_URL } from '../constants';
import * as CustomTypes from '../types';

// This helper function is well-written and requires no changes.
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch (e) {
      errorData = { message: response.statusText };
    }
    const error = new Error(errorData.message || `API request failed with status ${response.status}`) as any;
    error.status = response.status;
    error.data = errorData;
    throw error;
  }
  if (response.status === 204) {
    return {} as T;
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

// No changes needed for these functions
export const fetchConfiguredMeters = async (): Promise<CustomTypes.Meter[]> => {
  const response = await fetch(`${API_BASE_URL}/config/meters`);
  return handleResponse<CustomTypes.Meter[]>(response);
};

export const fetchLatestReadings = async (meterId: string, limit: number): Promise<CustomTypes.MeterReading[]> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_readings?limit=${limit}`);
  return handleResponse<CustomTypes.MeterReading[]>(response);
};

export const fetchHistoricalData = async (meterId: string, hours: number): Promise<CustomTypes.MeterReading[]> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/historical_data?hours=${hours}`);
  return handleResponse<CustomTypes.MeterReading[]>(response);
};

export const fetchLatestForecast = async (meterId: string): Promise<CustomTypes.ForecastPoint[]> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast`);
  const data = await handleResponse<CustomTypes.ForecastPoint[] | { forecast?: CustomTypes.ForecastPoint[] }>(response);

  if (!data) return [];
  if (Array.isArray(data)) {
    return data;
  }
  if (data && 'forecast' in data && Array.isArray(data.forecast)) {
     return data.forecast;
  }
  return []; 
};

// --- MODIFIED FUNCTION ---
// Renamed the return type from ForecastMetrics to the more accurate ForecastRunDetails
export const fetchLatestForecastDetails = async (meterId: string): Promise<CustomTypes.ForecastRunDetails | null> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast_details`);
  if (response.status === 404) {
    return null;
  }
  const data = await handleResponse<CustomTypes.ForecastRunDetails | {} | null>(response);

  if (!data || Object.keys(data).length === 0) {
    return null;
  }
  
  return data as CustomTypes.ForecastRunDetails;
};

// --- MODIFIED FUNCTION ---
// Updated to accept all necessary parameters for the simulation
// and to return the new, more descriptive SimulationResponse type.
export const triggerSimulation = async (
  meterId: string,
  durationHours: number,
  modelName: string,
  trainingHours: number
): Promise<CustomTypes.SimulationResponse> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ 
      duration_hours: durationHours,
      model_name: modelName,
      training_hours: trainingHours
    }),
  });
  return handleResponse<CustomTypes.SimulationResponse>(response);
};

// --- Scraper API Functions (No changes needed) ---

export const startScraper = async (meterId: string): Promise<CustomTypes.ScraperActionResponse> => {
  const response = await fetch(`${API_BASE_URL}/scraper/start`, { 
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ meter_id: meterId }),
  });
  return handleResponse<CustomTypes.ScraperActionResponse>(response);
};

export const stopScraper = async (meterId: string): Promise<CustomTypes.ScraperActionResponse> => {
  const response = await fetch(`${API_BASE_URL}/scraper/stop`, { 
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ meter_id: meterId }),
  });
  return handleResponse<CustomTypes.ScraperActionResponse>(response);
};

export const fetchScraperStatus = async (): Promise<CustomTypes.ScraperStatusResponse> => {
  const response = await fetch(`${API_BASE_URL}/scraper/status`);
  return handleResponse<CustomTypes.ScraperStatusResponse>(response);
};

export const fetchScraperLogs = async (meterId: string, lines: number = 50): Promise<CustomTypes.ScraperLogResponse> => {
  if (!meterId) {
    return Promise.resolve({ logs: ["Select a meter to view its logs."] });
  }
  const response = await fetch(`${API_BASE_URL}/scraper/logs?meter_id=${meterId}&lines=${lines}`);
  return handleResponse<CustomTypes.ScraperLogResponse>(response);
};