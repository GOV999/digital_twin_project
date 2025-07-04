// src/components/Dashboard.tsx

import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from '../types'; 
import * as apiService from '../services/apiService';
import { 
  CHART_DATA_FETCH_HOURS, 
  LATEST_READINGS_LIMIT, 
  PREDICTION_DURATION_OPTIONS, 
  CHART_HISTORICAL_HOURS_DISPLAY 
} from '../constants';

// Import all child components
import MetricsCard from './MetricsCard';
import DemandChart from './DemandChart';
import ReadingsTable from './ReadingsTable';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';
import ScraperControl from './ScraperControl';
import GridStatusCard from './GridStatusCard';
import EventSimulationCard from './EventSimulationCard';

interface DashboardProps {
  selectedMeterId: string;
  refreshTrigger: number;
  onSimulationComplete: () => void; 
}

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
  
  // --- NEW: State to hold the results of a specific backtest/event simulation ---
  const [backtestData, setBacktestData] = useState<CustomTypes.SimulationResponse | null>(null);

  // --- State for UI Controls & Status ---
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [simulationNotice, setSimulationNotice] = useState<string | null>(null);

  // --- State for Simulation Parameters ---
  const [selectedPredictionHours, setSelectedPredictionHours] = useState<number>(PREDICTION_DURATION_OPTIONS[0].value);
  const [selectedModel, setSelectedModel] = useState<string>(MODEL_OPTIONS[0].value);

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
      setError(err instanceof Error ? err.message : "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  }, [selectedMeterId]);

  useEffect(() => {
    // When the meter changes or a refresh is triggered, clear any old backtest data.
    setBacktestData(null);
    loadDashboardData();
  }, [loadDashboardData, refreshTrigger]);

  // --- MODIFIED: Chart Data Processing Logic ---
  useEffect(() => {
    const chartDataMap = new Map<number, CustomTypes.ChartDataPoint>();
    const isBacktestView = backtestData !== null;

    // Use all historical data as the base for building the chart
    const historicalSource = historicalData || [];
    historicalSource.forEach(reading => {
        const ts = new Date(reading.timestamp).getTime();
        chartDataMap.set(ts, {
            timestamp: ts,
            dateLabel: new Date(reading.timestamp).toLocaleString(),
            actual: reading.energy_kwh_import ?? undefined,
            predicted: undefined 
        });
    });

    // Determine the source of forecast points
    const forecastSource = isBacktestView ? (backtestData.forecast_points || []) : (forecastData || []);
    
    forecastSource.forEach((point) => { 
        const ts = new Date(point.timestamp).getTime();
        const predictedValue = point.predicted_kwh ?? undefined;
        let entry = chartDataMap.get(ts);
        if (entry) {
            entry.predicted = predictedValue;
        } else {
            entry = { timestamp: ts, dateLabel: new Date(point.timestamp).toLocaleString(), actual: undefined, predicted: predictedValue };
        }
        chartDataMap.set(ts, entry); 
    });

    let finalChartData = Array.from(chartDataMap.values());

    // Filter the data to the correct time window
    if (isBacktestView) {
        // For a backtest, show only the simulated time range
        const startTime = new Date(backtestData.simulation_start!).getTime();
        const endTime = new Date(backtestData.simulation_end!).getTime();
        finalChartData = finalChartData.filter(d => d.timestamp >= startTime && d.timestamp <= endTime);
    } else {
        // For the live view, show the default historical window
        const now = new Date();
        const displayHistoricalStartTime = new Date(now.getTime() - CHART_HISTORICAL_HOURS_DISPLAY * 60 * 60 * 1000).getTime();
        finalChartData = finalChartData.filter(d => d.timestamp >= displayHistoricalStartTime);
    }

    setChartData(finalChartData.sort((a, b) => a.timestamp - b.timestamp));
    
  }, [historicalData, forecastData, backtestData]); // This effect now re-runs when backtestData changes

  // --- Handlers for Simulations ---
  const handleRunSimulation = async () => {
    if (!selectedMeterId) return; 
    setIsSimulating(true);
    setSimulationError(null);
    setSimulationNotice(null);
    setBacktestData(null); // Clear any backtest view when running a new live forecast

    try {
      const trainingHours = selectedModel === 'dl_model' ? 168 : 24;
      const result = await apiService.triggerSimulation(
        selectedMeterId, selectedPredictionHours, selectedModel, trainingHours
      );
      
      let noticeMessage = `Live forecast updated using the '${result.model_used}' model.`;
      if (result.fallback_reason) {
        noticeMessage += ` NOTE: ${result.fallback_reason}`;
      }
      setSimulationNotice(noticeMessage);
      onSimulationComplete(); // Trigger a full refresh for live data
    } catch (err: any) {
      setSimulationError(err.message || "An unknown error occurred.");
    } finally {
      setIsSimulating(false);
    }
  };

  const handleEventSimStart = () => {
    setIsSimulating(true);
    setSimulationError(null);
    setSimulationNotice(null);
  };
  
  const handleEventSimComplete = (result: CustomTypes.SimulationResponse) => {
    // Directly update the state with the simulation result
    setBacktestData(result); 
    // Also update the main metrics card with the result of this backtest
    if (result.metrics && result.run_id) {
        const newMetrics: CustomTypes.ForecastRunDetails = {
            run_id: result.run_id, meter_id: selectedMeterId,
            model_name: result.model_used || 'unknown',
            mae: result.metrics.mae, rmse: result.metrics.rmse,
            run_timestamp: new Date().toISOString()
        };
        setMetrics(newMetrics);
    }
    setSimulationNotice("Event simulation finished. Displaying backtest results.");
    setIsSimulating(false);
  };

  const handleEventSimError = (errorMessage: string) => {
    setSimulationError(errorMessage);
    setIsSimulating(false);
  };

  if (loading && !isSimulating) { 
    return (
      <div className="card spinner-container" style={{padding: '2.5rem'}}>
        <Spinner />
        <p className="mt-4 text-xl text-sky-300">Loading dashboard...</p>
      </div>
    );
  }

  if (error) {
    return <ErrorMessage message={error} onRetry={loadDashboardData} />;
  }
  
  const hasData = metrics || (latestReadings && latestReadings.length > 0) || (chartData && chartData.length > 0);

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* 1. Scraper controls are untouched */}
      <ScraperControl selectedMeterId={selectedMeterId} />

      {/* 2. Top control cards for standard forecast are untouched */}
      <div className="top-cards-grid">
        <MetricsCard metrics={metrics} />
        <div className="simulation-controls card">
          <div className="control-group">
            <label htmlFor="model-selector" className="control-label">Forecasting Model:</label>
            <select id="model-selector" value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} className="meter-selector-select" disabled={isSimulating}>
              {MODEL_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <div className="control-group">
            <label htmlFor="prediction-duration-main" className="control-label">Forecast Horizon:</label>
            <select id="prediction-duration-main" value={selectedPredictionHours} onChange={(e) => setSelectedPredictionHours(Number(e.target.value))} className="meter-selector-select" disabled={isSimulating}>
              {PREDICTION_DURATION_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <button onClick={handleRunSimulation} className="run-simulation-button" disabled={isSimulating || !selectedMeterId}>
            {isSimulating ? <Spinner size="sm" /> : 'Run Standard Forecast'}
          </button>
        </div>
      </div>
      
      {/* 3. Display area for notices and errors from the STANDARD simulation */}
      {simulationNotice && <div className="notice success-notice">{simulationNotice}</div>}
      {simulationError && <ErrorMessage message={simulationError} />}
      
      {/* 4. Main Data Display Section */}
      {!hasData && !loading ? (
        <div className="no-data-placeholder card">
          <h3 className="no-data-title">No Data Available</h3>
          <p className="no-data-text">Start scraper to collect data.</p>
        </div>
      ) : (
        <>
          {/* Main "Live" Demand Chart */}
          <div className="card">
            <h2 className="card-title">Demand Forecast vs. Actual</h2>
            <DemandChart data={chartData} />
          </div>

          {/* Readings and Grid Status are unchanged */}
          <div className="card">
            <h2 className="card-title">Latest Meter Readings</h2>
            <ReadingsTable readings={latestReadings} />
          </div>
          
          {latestReadings && latestReadings.length > 0 && (
            <GridStatusCard 
             latestReadings={latestReadings}
             historicalData={historicalData} 
            />
          )}

          {/* --- MODIFIED: The EventSimulationCard is now self-contained --- */}
          {/* It receives the meter ID and the global simulation lock state */}
          <EventSimulationCard 
            meterId={selectedMeterId}
            isSimulating={isSimulating}
            setIsSimulating={setIsSimulating}
          />
        </>
      )}
    </div>
  );
};

export default Dashboard;