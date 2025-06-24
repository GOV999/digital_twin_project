import { API_BASE_URL } from '../constants';
import * as CustomTypes from '../types';

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
  // This can return null if the body is empty
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

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

  // This logic is good, handles different possible response shapes
  if (!data) return [];
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.forecast)) {
     return data.forecast;
  }
  return []; 
};

// --- THIS FUNCTION IS THE ONE TO FIX ---
export const fetchLatestForecastDetails = async (meterId: string): Promise<CustomTypes.ForecastMetrics | null> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast_details`);
  if (response.status === 404) {
    return null;
  }
  const data = await handleResponse<CustomTypes.ForecastMetrics | {} | null>(response);

  // ** THE FIX IS HERE **
  // Add a check to ensure `data` is a non-null object before calling Object.keys()
  if (!data || Object.keys(data).length === 0) {
    return null;
  }
  
  return data as CustomTypes.ForecastMetrics;
};

export const triggerSimulation = async (meterId: string, durationHours: number): Promise<{ message: string; run_id?: string; metrics?: any }> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/simulate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ duration_hours: durationHours }),
  });
  return handleResponse<{ message: string; run_id?: string; metrics?: any }>(response);
};

// --- Scraper API Functions ---

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