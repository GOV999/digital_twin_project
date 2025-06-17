
import { API_BASE_URL } from '../constants';
import * as CustomTypes from '../types'; // Changed to namespace import

async function handleResponse<T,>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch (e) {
      // If response is not JSON, use status text
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
  const data = await handleResponse<CustomTypes.ForecastPoint[] | { forecast?: CustomTypes.ForecastPoint[] }>(response); // Backend might wrap it
  if (Array.isArray(data)) {
    return data;
  }
  if (data && Array.isArray(data.forecast)) { // Handle potential wrapping from backend { "forecast": [...] }
     return data.forecast;
  }
  return []; // Return empty if structure is unexpected or no forecast
};

export const fetchLatestForecastDetails = async (meterId: string): Promise<CustomTypes.ForecastMetrics | null> => {
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast_details`);
   // Handle cases where details might be null or an empty object from backend if no forecast exists
  if (response.status === 404) { // Or if backend returns empty for no details
    return null;
  }
  const data = await handleResponse<CustomTypes.ForecastMetrics | {} >(response);
  if (Object.keys(data).length === 0) return null; // Empty object means no details
  return data as CustomTypes.ForecastMetrics;
};