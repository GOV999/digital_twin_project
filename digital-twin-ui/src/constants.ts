export const API_BASE_URL: string = 'http://localhost:5000/api';

// How much historical data to FETCH (e.g., for training context or broader view than display)
export const CHART_DATA_FETCH_HOURS: number = 24 * 7; 

// How many recent hours of ACTUAL data to DISPLAY on the chart
export const CHART_HISTORICAL_HOURS_DISPLAY: number = 48; 

export const LATEST_READINGS_LIMIT: number = 10;

export const PREDICTION_DURATION_OPTIONS = [
  { value: 2, label: 'Next 2 Hours' },
  { value: 6, label: 'Next 6 Hours' },
  { value: 12, label: 'Next 12 Hours' },
  { value: 24, label: 'Next 24 Hours' },
  { value: 48, label: 'Next 48 Hours' },
  { value: 72, label: 'Next 72 Hours' },
];