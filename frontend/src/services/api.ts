import { Meter, Reading, ForecastRun, CombinedDataPoint } from '../types';

const API_BASE_URL = 'http://localhost:5000/api'; // Adjust if your Flask API runs elsewhere

async function handleResponse<T,>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.text(); // Read error response as text for more details
    console.error(`API Error Response: ${response.status} ${response.statusText}`, errorData);
    throw new Error(`API Error: ${response.status} ${response.statusText} - ${errorData.substring(0, 300)}`); // Limit error message length
  }
  try {
    return await response.json() as Promise<T>;
  } catch (e) {
    console.error('API Error: Failed to parse JSON response', e);
    const textResponse = await response.text(); // Get text if JSON parsing fails
    throw new Error(`API Error: Failed to parse JSON. Response was: ${textResponse.substring(0, 300)}`);
  }
}

export const fetchMeters = async (): Promise<Meter[]> => {
  const response = await fetch(`${API_BASE_URL}/meters`);
  return handleResponse<Meter[]>(response);
};

export const fetchLatestReadings = async (meterId: string, limit: number = 5): Promise<Reading[]> => {
  // Corrected URL to match backend: /api/meters/<meter_id>/latest_readings
  const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_readings?limit=${limit}`);
  return handleResponse<Reading[]>(response);
};

export const fetchLatestForecastRun = async (meterId: string): Promise<ForecastRun | null> => {
  try {
    // Corrected URL to match backend: /api/meters/<meter_id>/latest_forecast_details
    const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast_details`);
    if (response.status === 404) {
      console.warn(`No latest forecast run details found for meter ${meterId} (404).`);
      return null; 
    }
    return await handleResponse<ForecastRun>(response);
  } catch (error) {
    // Catching errors from handleResponse or network errors
    console.error(`Error fetching latest forecast run details for ${meterId}:`, error);
    return null; // Gracefully return null for UI to handle
  }
};

// New function to fetch chart data from /api/meters/<meter_id>/latest_forecast
// This endpoint is assumed to return CombinedDataPoint[] or a compatible structure.
export const fetchChartData = async (meterId: string): Promise<CombinedDataPoint[]> => {
  try {
    const response = await fetch(`${API_BASE_URL}/meters/${meterId}/latest_forecast`);
    // If the endpoint might return 404 or empty data for no forecast, handle it:
    if (response.status === 404) {
        console.warn(`No chart data (latest forecast) found for meter ${meterId} (404). Returning empty array.`);
        return [];
    }
    const data = await handleResponse<CombinedDataPoint[]>(response);
    // Ensure data is an array, backend might return null or other if no data
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.error(`Error fetching chart data for ${meterId}:`, error);
    return []; // Return empty array on error to prevent chart crashing
  }
};
