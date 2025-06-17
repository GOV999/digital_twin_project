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

    console.log(`[Dashboard] loadDashboardData triggered for meter: ${selectedMeterId}. Refresh key: ${refreshTrigger}`);
    setLoading(true);
    setError(null);
    try {
      const [histData, fcData, metricData, latestData] = await Promise.all([
        fetchHistoricalData(selectedMeterId, CHART_DATA_FETCH_HOURS), 
        fetchLatestForecast(selectedMeterId),
        fetchLatestForecastDetails(selectedMeterId),
        fetchLatestReadings(selectedMeterId, LATEST_READINGS_LIMIT),
      ]);
      
      console.log("[Dashboard] Fetched HistData Points:", histData ? histData.length : 0);
      console.log("[Dashboard] Fetched FcData Points:", fcData ? fcData.length : 0, "| First 2 FcPoints:", fcData ? fcData.slice(0,2) : "N/A");

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
  }, [selectedMeterId, refreshTrigger]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]); 

  useEffect(() => {
    console.log("[ChartEffect] START. SelectedHours:", selectedPredictionHours, "Hist Data available:", !!historicalData, "Forecast Data available:", !!forecastData);

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
    console.log("[ChartEffect] Filtered Displayable Forecast Data Points:", displayableForecastData.length, "| First 2 Displayable FcPoints:", displayableForecastData.slice(0,2));

    displayableForecastData.forEach((point, index) => { 
      const ts = new Date(point.timestamp).getTime();
      // ***** CORRECTED TO USE point.predicted_kwh *****
      const predictedValue = (typeof point.predicted_kwh === 'number') ? point.predicted_kwh : undefined; 
      
      if (index < 5 || index >= displayableForecastData.length - 5) { 
        console.log(`[ChartEffect] Processing Forecast Point ${index}: Timestamp: ${new Date(ts).toLocaleString()}, Original point.predicted_kwh: ${point.predicted_kwh}, Type: ${typeof point.predicted_kwh}, Parsed predictedValue: ${predictedValue}`);
      }
      
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
        entry.actual = undefined; 
      }
      chartDataMap.set(ts, entry); 
    });
    
    const finalChartData = Array.from(chartDataMap.values());
    finalChartData.sort((a, b) => a.timestamp - b.timestamp);
    
    console.log("[ChartEffect] Final Processed Chart Data Points:", finalChartData.length, "| First 5 chart entries:", finalChartData.slice(0, 5));
    const predictionsInChart = finalChartData.filter(d => d.predicted !== undefined);
    console.log("[ChartEffect] Final Chart Data with Predictions (count and first 5):", predictionsInChart.length, predictionsInChart.slice(0,5));
    
    setChartData(finalChartData);

  }, [historicalData, forecastData, selectedPredictionHours]);

  const handleRunSimulation = async () => {
    if (!selectedMeterId) return; 
    if (!onSimulationComplete) {
        console.warn("[Dashboard] onSimulationComplete prop is not defined. Cannot trigger refresh automatically via App.tsx.");
    }
    setIsSimulating(true);
    setSimulationError(null);
    try {
      console.log(`[Dashboard] Triggering simulation for meter ${selectedMeterId} with duration ${selectedPredictionHours} hours.`);
      await triggerSimulation(selectedMeterId, selectedPredictionHours);
      if (onSimulationComplete) { 
          onSimulationComplete(); 
      } else {
          console.warn("[Dashboard] onSimulationComplete not provided, attempting local data reload.");
          loadDashboardData(); 
          alert("Simulation triggered! Data reloaded. (Manual refresh might be needed if issues persist).");
      }
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

  if (error && !simulationError) {
    return <ErrorMessage message={error} onRetry={loadDashboardData} />;
  }
  
  const noMetricsData = !metrics;
  const noReadingsData = !latestReadings || latestReadings.length === 0;

  if (noMetricsData && noReadingsData && chartData.length === 0 && !simulationError && !loading && !isSimulating) {
    return (
      <div className="no-data-placeholder">
         <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="no-data-title">No Data Available for Meter {selectedMeterId}</h3>
        <p className="no-data-text">No forecasting data or recent readings. Try running a new simulation or refresh.</p>
        <div className="simulation-controls card" style={{ marginTop: '1rem', padding: '1rem' }}>
          <label htmlFor="prediction-duration-sim-nodata" className="prediction-duration-label">Forecast Horizon:</label>
          <select
            id="prediction-duration-sim-nodata"
            value={selectedPredictionHours}
            onChange={(e) => setSelectedPredictionHours(Number(e.target.value))}
            className="meter-selector-select"
            disabled={isSimulating}
            style={{ minWidth: '180px', marginBottom: '0.5rem' }}
          >
            {PREDICTION_DURATION_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunSimulation}
            className="run-simulation-button"
            disabled={isSimulating || !selectedMeterId}
          >
            {isSimulating ? <Spinner size="sm" /> : null}
            {isSimulating ? 'Simulating...' : 'Run Simulation & Update Forecast'}
          </button>
          {simulationError && <ErrorMessage message={simulationError} onRetry={handleRunSimulation} />}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      <div className="dashboard-controls">
        {metrics ? <MetricsCard metrics={metrics} /> : 
          (!loading && <div className="card no-data-placeholder" style={{padding: '1rem'}}><p className="no-data-text">No performance metrics available for the latest forecast.</p></div>)
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
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunSimulation}
            className="run-simulation-button"
            disabled={isSimulating || !selectedMeterId}
          >
            {isSimulating ? <Spinner size="sm" /> : null}
            {isSimulating ? 'Simulating...' : 'Run Simulation & Update Forecast'}
          </button>
        </div>
      </div>
      
      {simulationError && <ErrorMessage message={simulationError} onRetry={handleRunSimulation} />}
      
      {(chartData.length > 0 || (loading && !isSimulating)) ? ( 
         <div className="card">
          <h2 className="card-title">Demand Forecast vs. Actual (Last {CHART_HISTORICAL_HOURS_DISPLAY}hrs Actuals)</h2>
          {loading && !isSimulating && chartData.length === 0 && <div className="spinner-container" style={{height:'100px'}}><Spinner size="md"/><p>Loading chart data...</p></div>}
          {chartData.length > 0 && <DemandChart data={chartData} />}
        </div>
      ) : (
        !loading && !error && !simulationError && ( 
          <div className="card no-data-placeholder">
            <h2 className="no-data-title">No Chart Data Available</h2>
            <p className="no-data-text">Historical or forecast data for the chart is not available for the selected criteria. Please try running a simulation or adjusting the forecast horizon.</p>
          </div>
        )
      )}
      {loading && !isSimulating && chartData.length === 0 && ( 
          <div className="card spinner-container" style={{height:'150px', padding: '1rem'}}>
              <Spinner size="md"/>
              <p className="spinner-text" style={{fontSize: '1rem', marginTop: '0.5rem'}}>Loading chart data...</p>
          </div>
      )}


      {latestReadings && latestReadings.length > 0 ? (
        <div className="card">
          <h2 className="card-title">Latest Meter Readings</h2>
          <ReadingsTable readings={latestReadings} />
        </div>
      ) : (
         !loading && !error && !simulationError && ( 
          <div className="card no-data-placeholder">
            <h2 className="no-data-title">No Recent Readings Found</h2>
            <p className="no-data-text">No recent readings found for this meter.</p>
          </div>
        )
      )}
      {loading && !isSimulating && (!latestReadings || latestReadings.length === 0) && ( 
          <div className="card spinner-container" style={{height:'150px', padding: '1rem'}}>
              <Spinner size="md"/>
              <p className="spinner-text" style={{fontSize: '1rem', marginTop: '0.5rem'}}>Loading latest readings...</p>
          </div>
      )}

    </div>
  );
};

export default Dashboard;