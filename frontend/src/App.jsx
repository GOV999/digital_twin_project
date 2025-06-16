// frontend/src/App.jsx
// This is your main application component.
// It imports DashboardChart from './DashboardChart.jsx' and global CSS.

import React, { useState, useEffect, useCallback } from 'react';
import DashboardChart from './DashboardChart'; // Import DashboardChart component
import './index.css'; // Import your global CSS

// Helper function for simple icons
const Icon = ({ name, size = 24, className = "" }) => {
    const icons = {
        RefreshCcw: "↻",
        Info: "ℹ️",
        Server: "📊",
        TrendingUp: "📈",
        Zap: "⚡",
        Clock: "⏱️",
        Chart: "📈"
    };
    return <span className={`icon ${className}`} style={{ fontSize: `${size}px` }}>{icons[name] || name}</span>;
};

// This function interacts with your Flask backend API
const callPythonBackend = async (functionName, ...args) => {
    const baseUrl = 'http://localhost:5000/api'; // Your Flask API server
    let endpoint = '';
    let method = 'GET';
    let body = null;

    if (functionName === 'get_all_meters') {
        endpoint = '/meters';
    } else if (functionName === 'get_latest_readings') {
        const [meterId, limitCount] = args;
        endpoint = `/meters/${meterId}/latest_readings?limit=${limitCount}`;
    } else if (functionName === 'get_historical_data') {
        const [meterId, hours] = args;
        endpoint = `/meters/${meterId}/historical_data?hours=${hours}`;
    } else if (functionName === 'get_latest_forecast') {
        const [meterId] = args;
        endpoint = `/meters/${meterId}/latest_forecast`;
    } else if (functionName === 'get_latest_forecast_run_details') {
        const [meterId] = args;
        endpoint = `/meters/${meterId}/latest_forecast_details`;
    }

    try {
        const response = await fetch(baseUrl + endpoint, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: body
        });
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, details: ${errorText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error calling Python backend:', error);
        throw error;
    }
};

function App() {
    const [selectedMeterId, setSelectedMeterId] = useState('');
    const [meters, setMeters] = useState([]);
    const [latestReadings, setLatestReadings] = useState([]);
    const [historicalData, setHistoricalData] = useState([]);
    const [forecastData, setForecastData] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // Fetch all meters on component mount
    useEffect(() => {
        const fetchMeters = async () => {
            setLoading(true);
            setError(null);
            try {
                const allMeters = await callPythonBackend('get_all_meters');
                setMeters(allMeters);
                if (allMeters.length > 0) {
                    setSelectedMeterId(allMeters[0].meter_id);
                }
            } catch (err) {
                console.error("Failed to fetch meters:", err);
                setError("Failed to load meters. Please ensure the Flask API is running and accessible.");
            } finally {
                setLoading(false);
            }
        };
        fetchMeters();
    }, []);

    // Fetch data whenever selectedMeterId changes or on interval
    useEffect(() => {
        const fetchDataForMeter = async () => {
            if (!selectedMeterId) return;

            setLoading(true);
            setError(null);
            try {
                // Current time for window calculation
                const now = new Date();
                const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000);
                const twoHoursFuture = new Date(now.getTime() + 2 * 60 * 60 * 1000);

                const latest = await callPythonBackend('get_latest_readings', selectedMeterId, 5);
                setLatestReadings(latest);

                const historical = await callPythonBackend('get_historical_data', selectedMeterId, 24); // Fetch wider range for charts
                setHistoricalData(historical);

                const forecast = await callPythonBackend('get_latest_forecast', selectedMeterId);
                setForecastData(forecast);

                const latestForecastRunDetails = await callPythonBackend('get_latest_forecast_run_details', selectedMeterId);
                if (latestForecastRunDetails &&
                    (latestForecastRunDetails.mae !== null && latestForecastRunDetails.mae !== undefined && !isNaN(parseFloat(latestForecastRunDetails.mae)) ||
                     latestForecastRunDetails.rmse !== null && latestForecastRunDetails.rmse !== undefined && !isNaN(parseFloat(latestForecastRunDetails.rmse)))) {
                    setMetrics({
                        mae: parseFloat(latestForecastRunDetails.mae),
                        rmse: parseFloat(latestForecastRunDetails.rmse)
                    });
                } else {
                    setMetrics(null);
                }

            } catch (err) {
                console.error("Failed to fetch dashboard data:", err);
                setError(`Failed to load data for meter ${selectedMeterId}. Details: ${err.message}. Ensure the Flask API is running, database is populated, and a recent simulation has been run.`);
            } finally {
                setLoading(false);
            }
        };

        fetchDataForMeter();
        const interval = setInterval(fetchDataForMeter, 30000); // Refresh every 30 seconds
        return () => clearInterval(interval);
    }, [selectedMeterId]);

    const handleMeterChange = (event) => {
        setSelectedMeterId(event.target.value);
    };

    // Dynamically determine the time window for charting
    const now = new Date();
    const twoHoursAgo = new Date(now.getTime() - 2 * 60 * 60 * 1000);
    const twoHoursFuture = new Date(now.getTime() + 2 * 60 * 60 * 1000);

    const renderCharts = useCallback(() => {
        if (!selectedMeterId) return null;

        const attributes = [
            { key: 'energy_kwh_import', title: 'Energy Consumption (kWh)', yAxisLabel: 'kWh', color: '#3b82f6' }, // blue-500
            { key: 'voltage_vrn', title: 'Voltage (V)', yAxisLabel: 'Volts', color: '#10b981' }, // green-500
            { key: 'current_ir', title: 'Current (A)', yAxisLabel: 'Amperes', color: '#ef4444' }, // red-500
        ];

        return attributes.map(attr => (
            <DashboardChart
                key={attr.key}
                title={attr.title}
                meterId={selectedMeterId}
                historicalData={historicalData}
                forecastData={forecastData}
                attributeKey={attr.key}
                yAxisLabel={attr.yAxisLabel}
                lineColor={attr.color}
                timeWindowStart={twoHoursAgo}
                timeWindowEnd={twoHoursFuture}
                currentTime={now}
            />
        ));
    }, [selectedMeterId, historicalData, forecastData]);

    return (
        <div className="main-container">
            <h1 className="dashboard-title">
                Digital Twin Dashboard
                <button
                    onClick={() => window.location.reload()}
                    className="refresh-button"
                >
                    <Icon name="RefreshCcw" size={18} />
                    <span>Refresh</span>
                </button>
            </h1>

            {error && (
                <div className="error-message" role="alert">
                    <strong>Error!</strong>
                    <span>{error}</span>
                </div>
            )}

            <div className="meter-select-container">
                <label htmlFor="meter-select" className="meter-select-label">
                    Select Meter:
                </label>
                <select
                    id="meter-select"
                    value={selectedMeterId}
                    onChange={handleMeterChange}
                    className="meter-select"
                    disabled={loading || meters.length === 0}
                >
                    {loading ? (
                        <option value="">Loading Meters...</option>
                    ) : meters.length > 0 ? (
                        meters.map((meter) => (
                            <option key={meter.meter_id} value={meter.meter_id}>
                                {meter.meter_no} ({meter.location || 'No Location'})
                            </option>
                        ))
                    ) : (
                        <option value="">No meters available</option>
                    )}
                </select>
            </div>

            {loading && (
                <div className="loading-state">
                    <p>Loading data for {selectedMeterId || 'selected meter'}...</p>
                    <div className="spinner"></div>
                </div>
            )}

            {!loading && selectedMeterId && (
                <div className="dashboard-grid">
                    {/* Latest Readings Card */}
                    <div className="card latest-readings-card">
                        <h2 className="card-title">
                            <Icon name="Info" />
                            <span>Latest 5 Readings ({selectedMeterId})</span>
                        </h2>
                        {latestReadings.length > 0 ? (
                            <div className="table-container">
                                <table className="readings-table">
                                    <thead>
                                        <tr>
                                            <th>Timestamp</th>
                                            <th>Energy (kWh)</th>
                                            <th>Voltage (V)</th>
                                            <th>Current (A)</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {latestReadings.map((reading, index) => (
                                            <tr key={index}>
                                                <td>{new Date(reading.timestamp).toLocaleString()}</td>
                                                <td>{reading.energy_kwh_import !== null && reading.energy_kwh_import !== undefined ? parseFloat(reading.energy_kwh_import).toFixed(2) : 'N/A'}</td>
                                                <td>{reading.voltage_vrn !== null && reading.voltage_vrn !== undefined ? parseFloat(reading.voltage_vrn).toFixed(2) : 'N/A'}</td>
                                                <td>{reading.current_ir !== null && reading.current_ir !== undefined ? parseFloat(reading.current_ir).toFixed(2) : 'N/A'}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        ) : (
                            <p className="no-data-message">No latest readings available.</p>
                        )}
                    </div>

                    {/* Dynamically rendered charts */}
                    {renderCharts()}

                    {/* Performance Metrics Card */}
                    <div className="card metrics-card">
                        <h2 className="card-title">
                            <Icon name="Zap" />
                            <span>Forecast Performance Metrics</span>
                        </h2>
                        {metrics ? (
                            <div className="metrics-content">
                                <p><strong>Mean Absolute Error (MAE):</strong> <span className="metric-value">{metrics.mae !== null && metrics.mae !== undefined && !isNaN(metrics.mae) ? metrics.mae.toFixed(4) : 'N/A'}</span></p>
                                <p><strong>Root Mean Squared Error (RMSE):</strong> <span className="metric-value">{metrics.rmse !== null && metrics.rmse !== undefined && !isNaN(metrics.rmse) ? metrics.rmse.toFixed(4) : 'N/A'}</span></p>
                                <p className="metrics-info">Metrics are calculated for periods where actual data overlaps with predictions. If 'N/A', no overlap or no actual data was available.</p>
                            </div>
                        ) : (
                            <p className="no-data-message">No performance metrics available for the latest forecast run.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}

export default App;