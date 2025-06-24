import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from '../types'; 
import { 
  fetchHistoricalData, 
  fetchLatestForecast, 
  fetchLatestForecastDetails, 
  fetchLatestReadings,
  triggerSimulation 
} from '../services/apiService';
import { CHART_DATA_FETCH_HOURS, LATEST_READINGS_LIMIT, PREDICTION_DURATION_OPTIONS, CHART_HISTORICAL_HOURS_DISPLAY } from '../constants';
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

const Dashboard: React.FC<DashboardProps> = ({ selectedMeterId, refreshTrigger, onSimulationComplete }) => {
  const [historicalData, setHistoricalData] = useState<CustomTypes.MeterReading[] | null>(null);
  const [forecastData, setForecastData] = useState<CustomTypes.ForecastPoint[] | null>(null);
  const [metrics, setMetrics] = useState<CustomTypes.ForecastMetrics | null>(null);
  const [latestReadings, setLatestReadings] = useState<CustomTypes.MeterReading[] | null>(null);
  
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [chartData, setChartData] = useState<CustomTypes.ChartDataPoint[]>([]);
  const [selectedPredictionHours, setSelectedPredictionHours] = useState<number>(PREDICTION_DURATION_OPTIONS[0].value);

  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [simulationError, setSimulationError] = useState<string | null>(null);


  const loadDashboardData = useCallback(async () => {
    if (!selectedMeterId) return;

    setLoading(true);
    setError(null);
    try {
      const [histData, fcData, metricData, latestData] = await Promise.all([
        fetchHistoricalData(selectedMeterId, CHART_DATA_FETCH_HOURS), 
        fetchLatestForecast(selectedMeterId),
        fetchLatestForecastDetails(selectedMeterId),
        fetchLatestReadings(selectedMeterId, LATEST_READINGS_LIMIT),
      ]);
      
      setHistoricalData(histData);
      setForecastData(fcData);
      setMetrics(metricData);
      setLatestReadings(latestData);

    } catch (err) {
      console.error("[Dashboard] Failed to load dashboard data for meter " + selectedMeterId + ":", err);
      const errorMsg = err instanceof Error ? err.message : "An unknown error occurred.";
      setError(`Failed to load data for this meter. ${errorMsg}`);
      setHistoricalData(null);
      setForecastData(null);
      setMetrics(null);
      setLatestReadings(null);
      setChartData([]);
    } finally {
      setLoading(false);
    }
  }, [selectedMeterId]); // Removed refreshTrigger as it's handled in the calling useEffect

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData, refreshTrigger]); // Added refreshTrigger back here

  useEffect(() => {
    const chartDataMap = new Map<number, CustomTypes.ChartDataPoint>();
    const now = new Date();
    
    const displayHistoricalStartTime = new Date(now.getTime() - CHART_HISTORICAL_HOURS_DISPLAY * 60 * 60 * 1000).getTime();

    const currentHistoricalData = historicalData || [];
    const displayableHistoricalData = currentHistoricalData.filter(reading => {
      const readingTimestamp = new Date(reading.timestamp).getTime();
      return readingTimestamp >= displayHistoricalStartTime;
    });

    let latestActualReadingTimestamp = 0;
    if (displayableHistoricalData.length > 0) {
      const validActualTimestamps = displayableHistoricalData
          .filter(r => typeof r.energy_kwh_import === 'number')
          .map(r => new Date(r.timestamp).getTime());
      if (validActualTimestamps.length > 0) {
        latestActualReadingTimestamp = Math.max(...validActualTimestamps);
      }
    }
    
    const predictionAnchorTime = latestActualReadingTimestamp || displayHistoricalStartTime;

    const predictionEndTime = predictionAnchorTime + selectedPredictionHours * 60 * 60 * 1000;

    displayableHistoricalData.forEach(reading => {
      const ts = new Date(reading.timestamp).getTime();
      if (ts <= predictionAnchorTime) { 
        chartDataMap.set(ts, {
            timestamp: ts,
            dateLabel: new Date(reading.timestamp).toLocaleString(),
            actual: (typeof reading.energy_kwh_import === 'number') ? reading.energy_kwh_import : undefined,
            predicted: undefined 
        });
      }
    });

    const currentForecastData = forecastData || [];
    const displayableForecastData = currentForecastData.filter(point => {
      const ts = new Date(point.timestamp).getTime();
      return ts > predictionAnchorTime && ts <= predictionEndTime;
    });

    displayableForecastData.forEach((point) => { 
      const ts = new Date(point.timestamp).getTime();
      const predictedValue = (typeof point.predicted_kwh === 'number') ? point.predicted_kwh : undefined; 
      
      let entry = chartDataMap.get(ts);
      if (!entry) {
        entry = {
          timestamp: ts,
          dateLabel: new Date(point.timestamp).toLocaleString(),
          actual: undefined, 
          predicted: predictedValue
        };
      } else {
        entry.predicted = predictedValue;
      }
      chartDataMap.set(ts, entry); 
    });
    
    const finalChartData = Array.from(chartDataMap.values());
    finalChartData.sort((a, b) => a.timestamp - b.timestamp);
    
    setChartData(finalChartData);

  }, [historicalData, forecastData, selectedPredictionHours]);

  const handleRunSimulation = async () => {
    if (!selectedMeterId) return; 
    
    setIsSimulating(true);
    setSimulationError(null);
    try {
      await triggerSimulation(selectedMeterId, selectedPredictionHours);
      onSimulationComplete(); 
    } catch (err) {
      console.error("[Dashboard] Failed to trigger simulation:", err);
      const errorMsg = err instanceof Error ? err.message : "An unknown error occurred during simulation.";
      setSimulationError(`Failed to run simulation: ${errorMsg}`);
    } finally {
      setIsSimulating(false);
    }
  };

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
  
  // ** THE FIX IS HERE: Defining `hasData` before the return statement. **
  const hasData = (metrics || (latestReadings && latestReadings.length > 0) || (chartData && chartData.length > 0));

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* ScraperControl is now ALWAYS visible and receives the selected meter ID */}
      <ScraperControl selectedMeterId={selectedMeterId} />

      {/* Main dashboard content */}
      <div className="dashboard-controls">
        {metrics ? <MetricsCard metrics={metrics} /> : 
          (!loading && <div className="card no-data-placeholder" style={{padding: '1rem'}}><p className="no-data-text">No performance metrics available.</p></div>)
        }
        <div className="simulation-controls card">
          <label htmlFor="prediction-duration-main" className="prediction-duration-label">Forecast Horizon:</label>
          <select
            id="prediction-duration-main"
            value={selectedPredictionHours}
            onChange={(e) => setSelectedPredictionHours(Number(e.target.value))}
            className="meter-selector-select"
            disabled={isSimulating}
            style={{ minWidth: '180px', marginBottom: '0.5rem' }}
          >
            {PREDICTION_DURATION_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
          <button
            onClick={handleRunSimulation}
            className="run-simulation-button"
            disabled={isSimulating || !selectedMeterId}
          >
            {isSimulating ? <Spinner size="sm" /> : 'Run Simulation'}
          </button>
        </div>
      </div>
      
      {simulationError && <ErrorMessage message={simulationError} onRetry={handleRunSimulation} />}
      
      {/* Conditional rendering for the rest of the dashboard based on data */}
      {!hasData && !loading && !simulationError ? (
        <div className="no-data-placeholder card">
          <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <h3 className="no-data-title">No Data Available for Meter {selectedMeterId}</h3>
          <p className="no-data-text">No historical readings or forecasts found. Please start the scraper to collect data, then run a simulation.</p>
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