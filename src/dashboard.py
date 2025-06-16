import React, { useState, useEffect, useCallback } from 'react';
import { initializeApp } from 'firebase/app';
import { getAuth, signInAnonymously, signInWithCustomToken, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, query, orderBy, limit, onSnapshot, where } from 'firebase/firestore';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { RefreshCcw, Info, Server, TrendingUp, Zap, Clock } from 'lucide-react';

// Ensure these are available in the environment from Canvas context
const appId = typeof __app_id !== 'undefined' ? __app_id : 'default-app-id';
const firebaseConfig = typeof __firebase_config !== 'undefined' ? JSON.parse(__firebase_config) : {};
const initialAuthToken = typeof __initial_auth_token !== 'undefined' ? __initial_auth_token : null;

// Initialize Firebase (only once)
const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const auth = getAuth(app);

// This function will ONLY use the Canvas-specific __fetch_data_for_app bridge.
// The direct HTTP fallback is removed because it caused issues in the Canvas iframe.
const callPythonBackend = async (functionName, ...args) => {
    if (typeof __fetch_data_for_app === 'function') {
        try {
            return await __fetch_data_for_app(functionName, ...args);
        } catch (bridgeError) {
            console.error(`Error calling __fetch_data_for_app for ${functionName}:`, bridgeError);
            throw new Error(`Backend bridge error for ${functionName}: ${bridgeError.message || "Unknown error"}`);
        }
    } else {
        // This case indicates that the dashboard is NOT running in the Canvas environment
        // or the Canvas bridge is not active. It will throw an error to signal this.
        const errorMessage = "Dashboard is not running in Canvas environment or __fetch_data_for_app is not defined. Cannot connect to Python backend.";
        console.error(errorMessage);
        throw new Error(errorMessage);
    }
};

const DashboardApp = () => {
    const [selectedMeterId, setSelectedMeterId] = useState('');
    const [meters, setMeters] = useState([]);
    const [latestReadings, setLatestReadings] = useState([]);
    const [historicalData, setHistoricalData] = useState([]);
    const [forecastData, setForecastData] = useState([]);
    const [metrics, setMetrics] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [userId, setUserId] = useState(null);

    // Firebase Auth setup
    useEffect(() => {
        const unsubscribe = onAuthStateChanged(auth, async (user) => {
            if (user) {
                setUserId(user.uid);
            } else {
                try {
                    if (initialAuthToken) {
                        await signInWithCustomToken(auth, initialAuthToken);
                    } else {
                        await signInAnonymously(auth);
                    }
                } catch (err) {
                    console.error("Firebase Auth Error:", err);
                    setError("Failed to authenticate with Firebase.");
                }
            }
        });
        return () => unsubscribe();
    }, [initialAuthToken]);

    const fetchData = useCallback(async (meterToFetch = selectedMeterId) => {
        setLoading(true);
        setError(null);
        try {
            // Fetch all meters first using the Canvas bridge
            const allMeters = await callPythonBackend("get_all_meters");
            setMeters(allMeters);

            let currentMeterId = meterToFetch;
            if (!currentMeterId && allMeters.length > 0) {
                currentMeterId = allMeters[0].meter_id;
                setSelectedMeterId(currentMeterId);
            } else if (currentMeterId && !allMeters.some(m => m.meter_id === currentMeterId)) {
                console.warn(`Selected meter ID ${currentMeterId} not found, defaulting to first available meter.`);
                if (allMeters.length > 0) {
                    currentMeterId = allMeters[0].meter_id;
                    setSelectedMeterId(currentMeterId);
                } else {
                    setLatestReadings([]);
                    setHistoricalData([]);
                    setForecastData([]);
                    setMetrics(null);
                    setLoading(false);
                    return;
                }
            } else if (!currentMeterId && allMeters.length === 0) {
                console.warn("No meters available to fetch data for.");
                setLatestReadings([]);
                setHistoricalData([]);
                setForecastData([]);
                setMetrics(null);
                setLoading(false);
                return;
            }

            if (currentMeterId) {
                // Now, fetch data for the selected/default meter using the Canvas bridge
                const latest = await callPythonBackend("get_latest_readings", currentMeterId, 20); // Get latest 20
                const historical = await callPythonBackend("get_historical_data", currentMeterId, 24); // Get last 24 hours
                const forecast = await callPythonBackend("get_latest_forecast", currentMeterId);
                const modelMetrics = await callPythonBackend("get_forecast_run_metrics", currentMeterId);

                setLatestReadings(latest);
                setHistoricalData(historical);
                setForecastData(forecast);
                setMetrics(modelMetrics);
            }

        } catch (err) {
            console.error("Error fetching data from backend:", err, err.stack); // Log stack trace
            setError("Failed to load data for the dashboard. Please ensure the API server is running in Canvas.");
        } finally {
            setLoading(false);
        }
    }, [selectedMeterId]);

    // Initial fetch for meters and set default selected meter
    useEffect(() => {
        fetchData();
    }, [fetchData]);


    const handleMeterChange = (event) => {
        setSelectedMeterId(event.target.value);
    };

    const handleRefresh = () => {
        fetchData();
    };

    const formatTimestamp = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        // Ensure timezone is correctly handled, potentially using `timeZone: 'Asia/Kolkata'` if the data is consistently in IST
        return date.toLocaleString('en-IN', {
            hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', year: 'numeric', hour12: false
        });
    };

    // Data structure for charts
    const chartData = [...historicalData];
    // Append forecast data, ensuring no overlap if timestamps are same
    forecastData.forEach(fData => {
        if (!chartData.some(hData => hData.timestamp === fData.timestamp)) {
            chartData.push(fData);
        }
    });
    // Sort combined data chronologically for the chart
    chartData.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());


    if (loading && !meters.length) {
        return (
            <div className="flex items-center justify-center min-h-screen bg-gray-100 p-4">
                <div className="flex flex-col items-center p-8 bg-white rounded-lg shadow-xl animate-pulse">
                    <div className="animate-spin rounded-full h-16 w-16 border-t-2 border-b-2 border-blue-500"></div>
                    <p className="mt-4 text-lg text-gray-700 font-semibold">Loading dashboard data...</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-100 p-4 sm:p-6 lg:p-8 font-inter text-gray-800">
            <div className="max-w-7xl mx-auto bg-white rounded-xl shadow-lg p-6 sm:p-8">
                <header className="flex flex-col sm:flex-row justify-between items-start sm:items-center border-b pb-4 mb-6">
                    <h1 className="text-3xl sm:text-4xl font-bold text-blue-800 mb-4 sm:mb-0">
                        Digital Twin Dashboard
                    </h1>
                    <div className="flex items-center space-x-4">
                        <select
                            className="p-3 border border-gray-300 rounded-lg shadow-sm focus:ring-blue-500 focus:border-blue-500 text-base"
                            value={selectedMeterId}
                            onChange={handleMeterChange}
                            disabled={loading}
                        >
                            {meters.length > 0 ? (
                                meters.map((meter) => (
                                    <option key={meter.meter_id} value={meter.meter_id}>
                                        Meter ID: {meter.meter_id} (No: {meter.meter_no})
                                    </option>
                                ))
                            ) : (
                                <option value="">No Meters Available</option>
                            )}
                        </select>
                        <button
                            onClick={handleRefresh}
                            className="p-3 bg-blue-600 text-white rounded-lg shadow-md hover:bg-blue-700 transition-all duration-300 flex items-center justify-center text-base disabled:opacity-50 disabled:cursor-not-allowed"
                            disabled={loading}
                        >
                            <RefreshCcw size={20} className={loading ? "animate-spin mr-2" : "mr-2"} /> Refresh
                        </button>
                    </div>
                </header>

                {userId && (
                    <div className="text-sm text-gray-600 mb-4 bg-blue-50 p-3 rounded-lg flex items-center">
                        <Info size={16} className="mr-2 text-blue-600" />
                        Authenticated User ID: <span className="font-semibold ml-1 text-blue-800">{userId}</span>
                    </div>
                )}

                {error && (
                    <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded-lg relative mb-6" role="alert">
                        <strong className="font-bold">Error!</strong>
                        <span className="block sm:inline ml-2">{error}</span>
                    </div>
                )}

                {loading ? (
                    <div className="flex items-center justify-center p-12">
                        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
                        <p className="ml-4 text-lg text-gray-600">Loading data...</p>
                    </div>
                ) : (
                    <div>
                        {/* Metrics Card */}
                        {metrics && (
                            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-6 mb-8">
                                <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-lg p-5 shadow-md flex items-center justify-between">
                                    <Zap size={28} className="mr-3" />
                                    <div>
                                        <p className="text-sm opacity-80">Model Used</p>
                                        <p className="text-xl font-semibold">{metrics.model_name || 'N/A'}</p>
                                    </div>
                                </div>
                                <div className="bg-gradient-to-r from-green-500 to-green-600 text-white rounded-lg p-5 shadow-md flex items-center justify-between">
                                    <TrendingUp size={28} className="mr-3" />
                                    <div>
                                        <p className="text-sm opacity-80">MAE (Mean Absolute Error)</p>
                                        <p className="text-xl font-semibold">{metrics.mae !== null ? metrics.mae.toFixed(2) : 'N/A'}</p>
                                    </div>
                                </div>
                                <div className="bg-gradient-to-r from-purple-500 to-purple-600 text-white rounded-lg p-5 shadow-md flex items-center justify-between">
                                    <Server size={28} className="mr-3" />
                                    <div>
                                        <p className="text-sm opacity-80">RMSE (Root Mean Square Error)</p>
                                        <p className="text-xl font-semibold">{metrics.rmse !== null ? metrics.rmse.toFixed(2) : 'N/A'}</p>
                                    </div>
                                </div>
                                <div className="col-span-1 sm:col-span-2 md:col-span-3 bg-gradient-to-r from-yellow-500 to-yellow-600 text-white rounded-lg p-5 shadow-md flex items-center justify-between">
                                    <Clock size={28} className="mr-3" />
                                    <div>
                                        <p className="text-sm opacity-80">Prediction Period</p>
                                        <p className="text-lg font-semibold">
                                            {metrics.prediction_start_time ? formatTimestamp(metrics.prediction_start_time) : 'N/A'} to {metrics.prediction_end_time ? formatTimestamp(metrics.prediction_end_time) : 'N/A'}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* Charts Section */}
                        <div className="mb-8">
                            <h2 className="text-2xl font-semibold text-gray-700 mb-4">Energy Consumption & Forecast (Last 24 Hours)</h2>
                            {chartData.length > 0 ? (
                                <ResponsiveContainer width="100%" height={400}>
                                    <LineChart
                                        data={chartData}
                                        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
                                        <XAxis
                                            dataKey="timestamp"
                                            tickFormatter={(isoString) => new Date(isoString).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false })}
                                            angle={-45}
                                            textAnchor="end"
                                            height={60}
                                            interval="preserveStartEnd"
                                        />
                                        <YAxis label={{ value: 'Energy (kWh)', angle: -90, position: 'insideLeft' }} />
                                        <Tooltip labelFormatter={(isoString) => new Date(isoString).toLocaleString()} />
                                        <Legend />
                                        <Line
                                            type="monotone"
                                            dataKey="energy_kwh_import"
                                            stroke="#8884d8"
                                            name="Actual kWh"
                                            dot={false}
                                            isAnimationActive={false}
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="predicted_kwh"
                                            stroke="#82ca9d"
                                            name="Predicted kWh"
                                            dot={false}
                                            isAnimationActive={false}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            ) : (
                                <p className="text-center text-gray-500 text-lg py-10">No historical or forecast data available for charting.</p>
                            )}
                        </div>

                        {/* Latest Readings Table */}
                        <div>
                            <h2 className="text-2xl font-semibold text-gray-700 mb-4">Latest Readings</h2>
                            {latestReadings.length > 0 ? (
                                <div className="overflow-x-auto rounded-lg shadow-md border border-gray-200">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead className="bg-gray-50">
                                            <tr>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider rounded-tl-lg">
                                                    Timestamp
                                                </th>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    Energy (kWh)
                                                </th>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    Voltage (VRN)
                                                </th>
                                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider rounded-tr-lg">
                                                    Current (IR)
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody className="bg-white divide-y divide-gray-200">
                                            {latestReadings.map((reading, index) => (
                                                <tr key={index} className="hover:bg-gray-50">
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                                        {formatTimestamp(reading.timestamp)}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {reading.energy_kwh_import !== null && reading.energy_kwh_import !== undefined ? reading.energy_kwh_import.toFixed(2) : 'N/A'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {reading.voltage_vrn !== null && reading.voltage_vrn !== undefined ? reading.voltage_vrn.toFixed(2) : 'N/A'}
                                                    </td>
                                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                        {reading.current_ir !== null && reading.current_ir !== undefined ? reading.current_ir.toFixed(2) : 'N/A'}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-center text-gray-500 text-lg py-10">No latest readings available.</p>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DashboardApp;
