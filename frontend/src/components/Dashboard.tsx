import React, { useState, useEffect, useCallback } from 'react';
import { CombinedDataPoint, ForecastRun, Reading, ForecastMetrics as Metrics } from '../types';
// Updated imports: fetchChartData added, fetchCombinedData removed
import { fetchLatestForecastRun, fetchChartData, fetchLatestReadings } from '../services/api';
import LineChartComponent from './LineChartComponent';
import MetricsDisplay from './MetricsDisplay';
import LatestReadingsDisplay from './LatestReadingsDisplay';
import LoadingSpinner from './LoadingSpinner';
import DataCard from './DataCard';

interface DashboardProps {
  selectedMeterId: string;
}

const formatDateForDisplay = (isoDate: string | null | undefined): string => {
  if (!isoDate) return 'N/A';
  try {
    return new Date(isoDate).toLocaleString([], { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: true });
  } catch (e) {
    console.warn("Error formatting date:", isoDate, e);
    return 'Invalid Date';
  }
};


const Dashboard: React.FC<DashboardProps> = ({ selectedMeterId }) => {
  const [latestRun, setLatestRun] = useState<ForecastRun | null>(null);
  const [chartData, setChartData] = useState<CombinedDataPoint[]>([]);
  const [latestReadings, setLatestReadings] = useState<Reading[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = useCallback(async () => {
    if (!selectedMeterId) return;

    setIsLoading(true);
    setError(null);
    try {
      // Fetch metadata for the latest forecast run
      const runDetails = await fetchLatestForecastRun(selectedMeterId);
      setLatestRun(runDetails);

      if (runDetails) {
        setMetrics({
          mae: runDetails.mae,
          rmse: runDetails.rmse,
          model_name: runDetails.model_name,
          run_id: runDetails.run_id,
          run_timestamp: formatDateForDisplay(runDetails.run_timestamp),
          forecast_period: `${formatDateForDisplay(runDetails.forecast_start_time)} - ${formatDateForDisplay(runDetails.forecast_end_time)}`
        });
      } else {
        setMetrics(null); // No run details, so no metrics
      }

      // Fetch chart data from the dedicated endpoint (e.g., /latest_forecast)
      // This endpoint is assumed to return CombinedDataPoint[] or compatible
      const dataForChart = await fetchChartData(selectedMeterId);
      setChartData(dataForChart);
      
      if (dataForChart.length === 0 && !runDetails) {
        // If no chart data AND no run details, it's likely there's no forecast at all.
         console.log(`No chart data or forecast run details for meter ${selectedMeterId}.`);
      }


      const readings = await fetchLatestReadings(selectedMeterId, 5);
      setLatestReadings(readings);

    } catch (err) {
      console.error("Failed to load dashboard data:", err);
      let errorMessage = "Failed to load data for this meter. ";
      if (err instanceof Error) {
        errorMessage += err.message;
      } else {
        errorMessage += "An unknown error occurred.";
      }
      setError(errorMessage);
      setChartData([]); // Clear data on error
      setMetrics(null);
      setLatestReadings([]);
      setLatestRun(null);
    } finally {
      setIsLoading(false);
    }
  }, [selectedMeterId]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-8 bg-slate-800 rounded-lg shadow-xl min-h-[400px]">
        <LoadingSpinner />
        <p className="mt-4 text-xl text-sky-300">Loading dashboard for {selectedMeterId}...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-800 border border-red-600 text-white p-6 rounded-lg shadow-xl max-w-3xl mx-auto">
        <h3 className="font-semibold text-2xl mb-3">Dashboard Error</h3>
        <p className="text-red-200">{error}</p>
        <button 
          onClick={loadDashboardData} 
          className="mt-4 bg-sky-500 hover:bg-sky-600 text-white font-semibold py-2 px-4 rounded transition duration-150"
          aria-label="Retry loading dashboard data"
        >
          Try Again
        </button>
      </div>
    );
  }
  
  return (
    <div className="space-y-8">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <MetricsDisplay metrics={metrics} />
          <LatestReadingsDisplay readings={latestReadings} meterId={selectedMeterId} />
        </div>
        <div className="lg:col-span-2 bg-slate-800 p-4 sm:p-6 rounded-lg shadow-xl">
          <h2 className="text-2xl font-semibold mb-1 text-sky-300">Energy Consumption & Forecast</h2>
          <p className="text-sm text-slate-400 mb-4">
            Meter ID: {selectedMeterId}
            {latestRun ? ` | Model: ${latestRun.model_name}` : (chartData.length > 0 ? ' | Latest available data' : ' | No forecast data available')}
          </p>
          {chartData.length > 0 ? (
            <LineChartComponent data={chartData} />
          ) : (
            <div className="flex items-center justify-center h-64 border-2 border-dashed border-slate-700 rounded-md">
              <p className="text-slate-500 text-lg text-center px-4">
                No chart data available for this meter.
                {!latestRun && " A forecast run may not have occurred yet."}
              </p>
            </div>
          )}
        </div>
      </div>
       {latestRun === null && chartData.length === 0 && !isLoading && (
         <DataCard title="Forecast Status" value="No forecast run found, and no chart data available for this meter." variant="warning" />
       )}
    </div>
  );
};

export default Dashboard;