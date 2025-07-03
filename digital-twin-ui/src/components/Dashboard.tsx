import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from '../types'; 
import * as apiService from '../services/apiService';
import { 
  CHART_DATA_FETCH_HOURS, 
  LATEST_READINGS_LIMIT, 
  PREDICTION_DURATION_OPTIONS, 
  CHART_HISTORICAL_HOURS_DISPLAY 
} from '../constants';

import MetricsCard from './MetricsCard';
import DemandChart from './DemandChart';
import ReadingsTable from './ReadingsTable';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';
import ScraperControl from './ScraperControl';

interface DashboardProps {
  selectedMeterId: string;
  refreshTrigger: number;
  onSimulationComplete: () => void; 
}

// --- NEW: Define model options for the UI ---
const MODEL_OPTIONS = [
  { value: 'baseline_model', label: 'Baseline Model' },
  { value: 'dl_model', label: 'DL Model (CNN-LSTM)' },
];

const Dashboard: React.FC<DashboardProps> = ({ selectedMeterId, refreshTrigger, onSimulationComplete }) => {
  // --- State for Data ---
  const [historicalData, setHistoricalData] = useState<CustomTypes.MeterReading[] | null>(null);
  const [forecastData, setForecastData] = useState<CustomTypes.ForecastPoint[] | null>(null);
  const [metrics, setMetrics] = useState<CustomTypes.ForecastRunDetails | null>(null);
  const [latestReadings, setLatestReadings] = useState<CustomTypes.MeterReading[] | null>(null);
  const [chartData, setChartData] = useState<CustomTypes.ChartDataPoint[]>([]);
  
  // --- State for UI Controls & Status ---
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [simulationNotice, setSimulationNotice] = useState<string | null>(null); // For success/fallback messages

  // --- NEW: State for Simulation Parameters ---
  const [selectedPredictionHours, setSelectedPredictionHours] = useState<number>(PREDICTION_DURATION_OPTIONS[0].value);
  const [selectedModel, setSelectedModel] = useState<string>(MODEL_OPTIONS[0].value);

  // --- Data Fetching Logic (largely unchanged) ---
  const loadDashboardData = useCallback(async () => {
    if (!selectedMeterId) return;
    setLoading(true);
    setError(null);
    try {
      const [histData, fcData, metricData, latestData] = await Promise.all([
        apiService.fetchHistoricalData(selectedMeterId, CHART_DATA_FETCH_HOURS), 
        apiService.fetchLatestForecast(selectedMeterId),
        apiService.fetchLatestForecastDetails(selectedMeterId),
        apiService.fetchLatestReadings(selectedMeterId, LATEST_READINGS_LIMIT),
      ]);
      setHistoricalData(histData);
      setForecastData(fcData);
      setMetrics(metricData);
      setLatestReadings(latestData);
    } catch (err) {
      console.error("[Dashboard] Failed to load data:", err);
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  }, [selectedMeterId]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData, refreshTrigger]);

  // --- Chart Data Processing Logic (unchanged) ---
  useEffect(() => {
    // This logic is complex but correct, no changes needed here.
    const chartDataMap = new Map<number, CustomTypes.ChartDataPoint>();
    const now = new Date();
    const displayHistoricalStartTime = new Date(now.getTime() - CHART_HISTORICAL_HOURS_DISPLAY * 60 * 60 * 1000).getTime();
    const currentHistoricalData = historicalData || [];
    const displayableHistoricalData = currentHistoricalData.filter(r => new Date(r.timestamp).getTime() >= displayHistoricalStartTime);
    let latestActualTimestamp = Math.max(...displayableHistoricalData.map(r => new Date(r.timestamp).getTime()), 0);
    const predictionAnchorTime = latestActualTimestamp || displayHistoricalStartTime;

    displayableHistoricalData.forEach(reading => {
      const ts = new Date(reading.timestamp).getTime();
      chartDataMap.set(ts, {
          timestamp: ts,
          dateLabel: new Date(reading.timestamp).toLocaleString(),
          actual: (typeof reading.energy_kwh_import === 'number') ? reading.energy_kwh_import : undefined,
          predicted: undefined 
      });
    });

    const currentForecastData = forecastData || [];
    currentForecastData.forEach((point) => { 
      const ts = new Date(point.timestamp).getTime();
      const predictedValue = (typeof point.predicted_kwh === 'number') ? point.predicted_kwh : undefined; 
      let entry = chartDataMap.get(ts);
      if (!entry) {
        entry = { timestamp: ts, dateLabel: new Date(point.timestamp).toLocaleString(), actual: undefined, predicted: predictedValue };
      } else {
        entry.predicted = predictedValue;
      }
      chartDataMap.set(ts, entry); 
    });
    
    setChartData(Array.from(chartDataMap.values()).sort((a, b) => a.timestamp - b.timestamp));
  }, [historicalData, forecastData]);


  // --- UPDATED Simulation Handler ---
  const handleRunSimulation = async () => {
    if (!selectedMeterId) return; 
    
    setIsSimulating(true);
    setSimulationError(null);
    setSimulationNotice(null); // Clear previous notices

    try {
      // Dynamically set training hours based on model choice
      const trainingHours = selectedModel === 'dl_model' ? 168 : 24; // 7 days for DL, 1 day for others

      const result = await apiService.triggerSimulation(
        selectedMeterId, 
        selectedPredictionHours,
        selectedModel,
        trainingHours
      );
      
      let noticeMessage = `Simulation successful using the '${result.model_used}' model.`;
      if (result.fallback_reason) {
        noticeMessage += ` NOTE: ${result.fallback_reason}`;
      }
      setSimulationNotice(noticeMessage);

      onSimulationComplete(); // Trigger data refresh in parent component

    } catch (err: any) {
      console.error("[Dashboard] Failed to trigger simulation:", err);
      setSimulationError(err.message || "An unknown error occurred during simulation.");
    } finally {
      setIsSimulating(false);
    }
  };

  // --- RENDER LOGIC ---
  if (loading && !isSimulating) { 
    return (
      <div className="card spinner-container" style={{padding: '2.5rem'}}>
        <Spinner />
        <p className="mt-4 text-xl text-sky-300">Loading dashboard for Meter {selectedMeterId}...</p>
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadDashboardData} />;
  }
  
  const hasData = metrics || (latestReadings && latestReadings.length > 0) || (chartData && chartData.length > 0);

  return (
    <div className="space-y-6 sm:space-y-8">
      <ScraperControl selectedMeterId={selectedMeterId} />

      <div className="dashboard-controls">
        {metrics && <MetricsCard metrics={metrics} />}
        
        <div className="simulation-controls card">
          {/* --- MODEL SELECTION DROPDOWN --- */}
          <div className="control-group">
            <label htmlFor="model-selector" className="control-label">Forecasting Model:</label>
            <select
              id="model-selector"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="meter-selector-select"
              disabled={isSimulating}
            >
              {MODEL_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>
          
          {/* --- HORIZON SELECTION DROPDOWN --- */}
          <div className="control-group">
            <label htmlFor="prediction-duration-main" className="control-label">Forecast Horizon:</label>
            <select
              id="prediction-duration-main"
              value={selectedPredictionHours}
              onChange={(e) => setSelectedPredictionHours(Number(e.target.value))}
              className="meter-selector-select"
              disabled={isSimulating}
            >
              {PREDICTION_DURATION_OPTIONS.map(option => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </div>

          <button
            onClick={handleRunSimulation}
            className="run-simulation-button"
            disabled={isSimulating || !selectedMeterId}
          >
            {isSimulating ? <Spinner size="sm" /> : 'Run Simulation'}
          </button>
        </div>
      </div>
      
      {/* Display Simulation Notices & Errors */}
      {simulationNotice && <div className="notice success-notice">{simulationNotice}</div>}
      {simulationError && <ErrorMessage message={simulationError} onRetry={handleRunSimulation} />}
      
      {/* Main Data Display */}
      {!hasData && !loading ? (
        <div className="no-data-placeholder card">
          <h3 className="no-data-title">No Data Available</h3>
          <p className="no-data-text">Start the scraper to collect data, then run a simulation.</p>
        </div>
      ) : (
        <>
          <div className="card">
            <h2 className="card-title">Demand Forecast vs. Actual</h2>
            {chartData.length > 0 ? <DemandChart data={chartData} /> : <p className="no-data-text">Chart data is not available.</p>}
          </div>
          <div className="card">
            <h2 className="card-title">Latest Meter Readings</h2>
            {latestReadings && latestReadings.length > 0 ? <ReadingsTable readings={latestReadings} /> : <p className="no-data-text">No recent readings found.</p>}
          </div>
        </>
      )}
    </div>
  );
};

export default Dashboard;