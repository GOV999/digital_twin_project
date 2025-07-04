// src/components/GridStatusCard.tsx

import React from 'react';
import { type MeterReading } from '../types';
// --- FIX: Import LineChart instead of SparklineChart ---
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts';

interface GridStatusCardProps {
  latestReadings: MeterReading[] | null;
  historicalData: MeterReading[] | null;
}

// Helper function to calculate stats from historical data (no changes here)
const getStats = (data: MeterReading[] | null, key: keyof MeterReading) => {
  if (!data || data.length === 0) {
    return { min: 'N/A', max: 'N/A', avg: 'N/A' };
  }
  const values = data.map(d => d[key]).filter(v => typeof v === 'number') as number[];
  if (values.length === 0) {
    return { min: 'N/A', max: 'N/A', avg: 'N/A' };
  }
  const min = Math.min(...values).toFixed(1);
  const max = Math.max(...values).toFixed(1);
  const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
  return { min, max, avg };
};

const GridStatusCard: React.FC<GridStatusCardProps> = ({ latestReadings, historicalData }) => {
  const latestReading = latestReadings && latestReadings.length > 0 ? latestReadings[0] : null;

  if (!latestReading) {
    return (
      <div className="card">
        <h3 className="card-title">Grid Stability Analysis</h3>
        <div className="flex items-center justify-center h-full min-h-[200px]">
            <p className="no-data-text">No recent readings to analyze.</p>
        </div>
      </div>
    );
  }

  // Prepare data for sparkline charts (use the last 48 points, for example)
  const chartData = latestReadings?.slice(-48).map(d => ({
    ...d,
    timestamp: new Date(d.timestamp).getTime(),
  })) || [];

  const voltageStats = {
  R: getStats(latestReadings, 'voltage_vrn'),
  Y: getStats(latestReadings, 'voltage_vyn'),
  B: getStats(latestReadings, 'voltage_vbn'),
 };

 const currentStats = {
  R: getStats(latestReadings, 'current_ir'),
  Y: getStats(latestReadings, 'current_iy'),
  B: getStats(latestReadings, 'current_ib'),
 };
  
  return (
    <div className="card">
      <h3 className="card-title">Grid Stability Analysis </h3>
      <div className="grid-analysis-layout">

        {/* --- Voltage Analysis Section --- */}
        <div className="analysis-section">
          <div className="section-header">
            <h4>Voltage (V)</h4>
            <div className="stats-pills">
            <span>R - Min: {voltageStats.R.min}, Avg: {voltageStats.R.avg}, Max: {voltageStats.R.max}</span>
            <span>Y - Min: {voltageStats.Y.min}, Avg: {voltageStats.Y.avg}, Max: {voltageStats.Y.max}</span>
            <span>B - Min: {voltageStats.B.min}, Avg: {voltageStats.B.avg}, Max: {voltageStats.B.max}</span>
            </div>
          </div>
          <div className="sparkline-container">
            <ResponsiveContainer width="100%" height={80}>
              {/* --- FIX: Use LineChart and hide axes/grid --- */}
              <LineChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(31, 41, 55, 0.9)', border: '1px solid #4A5568', borderRadius: '0.5rem' }} 
                  labelFormatter={(label) => new Date(label).toLocaleTimeString()}
                  formatter={(value: number) => [`${value.toFixed(1)}V`, 'Voltage']}
                />
                <Line type="monotone" dataKey="voltage_vrn" stroke="#8884d8" strokeWidth={2} dot={false} name="R Phase"/>
                <Line type="monotone" dataKey="voltage_vyn" stroke="#82ca9d" strokeWidth={2} dot={false} name="Y Phase"/>
                <Line type="monotone" dataKey="voltage_vbn" stroke="#ffc658" strokeWidth={2} dot={false} name="B Phase"/>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* --- Current Analysis Section --- */}
        <div className="analysis-section">
           <div className="section-header">
            <h4>Current (A)</h4>
             <div className="stats-pills">
            <span>R - Min: {currentStats.R.min}, Avg: {currentStats.R.avg}, Max: {currentStats.R.max}</span>
            <span>Y - Min: {currentStats.Y.min}, Avg: {currentStats.Y.avg}, Max: {currentStats.Y.max}</span>
            <span>B - Min: {currentStats.B.min}, Avg: {currentStats.B.avg}, Max: {currentStats.B.max}</span>
            </div>
          </div>
          <div className="sparkline-container">
            <ResponsiveContainer width="100%" height={80}>
              {/* --- FIX: Use LineChart and hide axes/grid --- */}
              <LineChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 5 }}>
                 <Tooltip 
                  contentStyle={{ backgroundColor: 'rgba(31, 41, 55, 0.9)', border: '1px solid #4A5568', borderRadius: '0.5rem' }}
                  labelFormatter={(label) => new Date(label).toLocaleTimeString()}
                  formatter={(value: number) => [`${value.toFixed(2)}A`, 'Current']}
                />
                <Line type="monotone" dataKey="current_ir" stroke="#8884d8" strokeWidth={2} dot={false} name="R Phase" />
                <Line type="monotone" dataKey="current_iy" stroke="#82ca9d" strokeWidth={2} dot={false} name="Y Phase"/>
                <Line type="monotone" dataKey="current_ib" stroke="#ffc658" strokeWidth={2} dot={false} name="B Phase"/>
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        
      </div>
      <small className="timestamp-footnote">
        Stats based on the latest readings. Last reading at: {new Date(latestReading.timestamp).toLocaleString()}
      </small>
    </div>
  );
};

export default GridStatusCard;