import { API_BASE_URL } from '../constants';
import * as CustomTypes from '../types';

async function handleResponse<T,>(response: Response): Promise<T> {
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
  return response.json() as Promise<T>;
}

export const fetchMeters = async (): Promise<CustomTypes.Meter[]> => {
  const response = await fetch(`${API_BASE_URL}/meters`);
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
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.forecast)) {
     return data.forecast;
  }
  return [];
};

export const fetchLatestForecastDetails = async (meterId: string): Promise<CustomTypes.ForecastMetrics | null> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast_details`);
  if (response.status === 404) {
    return null;
  }
  const data = await handleResponse<CustomTypes.ForecastMetrics | {} >(response);
  if (Object.keys(data).length === 0) return null;
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