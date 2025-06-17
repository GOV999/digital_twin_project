
import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from '../types'; // Changed to namespace import
import { 
  fetchHistoricalData, 
  fetchLatestForecast, 
  fetchLatestForecastDetails, 
  fetchLatestReadings 
} from '../services/apiService';
import { CHART_HISTORICAL_HOURS, LATEST_READINGS_LIMIT } from '../constants';
import MetricsCard from './MetricsCard';
import DemandChart from './DemandChart';
import ReadingsTable from './ReadingsTable';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';

interface DashboardProps {
  selectedMeterId: string;
  refreshTrigger: number;
}

const Dashboard: React.FC<DashboardProps> = ({ selectedMeterId, refreshTrigger }) => {
  const [historicalData, setHistoricalData] = useState<CustomTypes.MeterReading[] | null>(null);
  const [forecastData, setForecastData] = useState<CustomTypes.ForecastPoint[] | null>(null);
  const [metrics, setMetrics] = useState<CustomTypes.ForecastMetrics | null>(null);
  const [latestReadings, setLatestReadings] = useState<CustomTypes.MeterReading[] | null>(null);
  
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [chartData, setChartData] = useState<CustomTypes.ChartDataPoint[]>([]);

  const loadDashboardData = useCallback(async () => {
    if (!selectedMeterId) return;

    setLoading(true);
    setError(null);
    try {
      const [histData, fcData, metricData, latestData] = await Promise.all([
        fetchHistoricalData(selectedMeterId, CHART_HISTORICAL_HOURS),
        fetchLatestForecast(selectedMeterId),
        fetchLatestForecastDetails(selectedMeterId),
        fetchLatestReadings(selectedMeterId, LATEST_READINGS_LIMIT),
      ]);
      
      setHistoricalData(histData);
      setForecastData(fcData);
      setMetrics(metricData);
      setLatestReadings(latestData);

    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      setError("Failed to load data for this meter. Please try refreshing or selecting another meter.");
      setHistoricalData(null);
      setForecastData(null);
      setMetrics(null);
      setLatestReadings(null);
      setChartData([]);
    } finally {
      setLoading(false);
    }
  }, [selectedMeterId]);

  useEffect(() => {
    loadDashboardData();
  }, [selectedMeterId, refreshTrigger, loadDashboardData]);

  useEffect(() => {
    if (historicalData || forecastData) {
      const newChartData: CustomTypes.ChartDataPoint[] = [];
      const dataMap = new Map<number, Partial<CustomTypes.ChartDataPoint>>();
      const now = new Date().getTime(); // Current time for distinguishing past/future

      let latestActualTimestamp = 0;
      if (historicalData && historicalData.length > 0) {
        // Find the latest timestamp from actual historical data
        latestActualTimestamp = Math.max(...historicalData.map(r => new Date(r.timestamp).getTime()));
      }
       // If no historical data, but forecast has actuals, consider those
      if (forecastData && forecastData.length > 0) {
        const latestForecastActualTimestamp = Math.max(
          ...forecastData
            .filter(fp => fp.actual_value !== null)
            .map(fp => new Date(fp.timestamp).getTime())
        );
        if (latestForecastActualTimestamp > latestActualTimestamp) {
            latestActualTimestamp = latestForecastActualTimestamp;
        }
      }
      // If no actuals at all, use current time as the cut-off, so all predictions are in the future part of the graph.
      const cutOffTime = latestActualTimestamp > 0 ? latestActualTimestamp : now;


      // Process historical data for actual values
      (historicalData || []).forEach(reading => {
        const ts = new Date(reading.timestamp).getTime();
        if (!dataMap.has(ts)) dataMap.set(ts, { timestamp: ts, dateLabel: new Date(reading.timestamp).toLocaleString() });
        const entry = dataMap.get(ts)!;
        if (typeof reading.energy_kwh_import === 'number') { // Use energy_kwh_import
          entry.actual = reading.energy_kwh_import;
        } else {
          entry.actual = undefined; // Ensure non-numbers are undefined for chart
        }
      });

      // Process forecast data
      (forecastData || []).forEach(point => {
        const ts = new Date(point.timestamp).getTime();
        if (!dataMap.has(ts)) dataMap.set(ts, { timestamp: ts, dateLabel: new Date(point.timestamp).toLocaleString() });
        const entry = dataMap.get(ts)!;

        // Populate actual value from forecast if it exists (for historical comparison within forecast range)
        if (point.actual_value !== null && typeof point.actual_value === 'number') {
           if (ts <= cutOffTime) { // Only set actuals from forecast if they are for past/current points
             entry.actual = point.actual_value;
           }
        }
        
        // Populate predicted value
        if (typeof point.predicted_value === 'number') {
          if (ts >= cutOffTime) {
            entry.predicted = point.predicted_value;
          } else {
             entry.predicted = point.predicted_value;
          }
        } else {
          entry.predicted = undefined;
        }

        // If it's a future point, ensure 'actual' is undefined so the line breaks
        if (ts > cutOffTime && entry.actual === undefined) {
             entry.actual = undefined;
        }
      });
      
      newChartData.push(...Array.from(dataMap.values()).map(item => ({
        timestamp: item.timestamp!,
        dateLabel: item.dateLabel!,
        actual: item.actual,
        predicted: item.predicted,
      })));
      newChartData.sort((a, b) => a.timestamp - b.timestamp);
      setChartData(newChartData);
    } else {
      setChartData([]);
    }
  }, [historicalData, forecastData]);


  if (loading) {
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
  
  const noDataAvailable = !metrics && chartData.length === 0 && (!latestReadings || latestReadings.length === 0);

  if (noDataAvailable) {
    return (
      <div className="no-data-placeholder">
        <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <h3 className="no-data-title">No Data Available for Meter {selectedMeterId}</h3>
        <p className="no-data-text">There is currently no forecasting data or recent readings for this meter. A simulation might need to be run, or data might still be processing.</p>
        <button 
          onClick={loadDashboardData} 
          className="no-data-retry-button"
        >
          Try Refreshing Data
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8"> {/* sm:space-y-8 will be handled by media query in styles.css */}
      {metrics && <MetricsCard metrics={metrics} />}
      
      {chartData.length > 0 ? (
         <div className="card">
          <h2 className="card-title">Demand Forecast vs. Actual</h2>
          <DemandChart data={chartData} />
        </div>
      ) : (
        <div className="no-data-placeholder">
          <h2 className="no-data-title">No Chart Data</h2>
          <p className="no-data-text">Historical or forecast data for the chart is not available for this meter.</p>
        </div>
      )}

      {latestReadings && latestReadings.length > 0 ? (
        <div className="card">
          <h2 className="card-title">Latest Meter Readings</h2>
          <ReadingsTable readings={latestReadings} />
        </div>
      ) : (
         <div className="no-data-placeholder">
          <h2 className="no-data-title">No Recent Readings</h2>
          <p className="no-data-text">No recent readings found for this meter.</p>
        </div>
      )}
    </div>
  );
};

export default Dashboard;