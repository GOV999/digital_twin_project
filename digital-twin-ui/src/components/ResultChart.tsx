// src/components/ResultChart.tsx

import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Brush } from 'recharts';
import { type ChartDataPoint } from '../types';

interface ResultChartProps {
  data: ChartDataPoint[];
  title: string;
}

const ResultChart: React.FC<ResultChartProps> = ({ data, title }) => {
  if (!data || data.length === 0) {
    return <div className="flex items-center justify-center h-48"><p className="no-data-text">No data to display in chart.</p></div>;
  }

  // --- Dynamic Y-Axis Domain Logic (This is correct, no changes needed) ---
  const allValues = data
    .flatMap(d => [d.actual, d.predicted])
    .filter(v => typeof v === 'number') as number[];
  
  let yDomain: [number | string, number | string] = ['auto', 'auto'];
  if (allValues.length > 0) {
    const dataMin = Math.min(...allValues);
    const dataMax = Math.max(...allValues);
    const padding = (dataMax - dataMin) * 0.1;
    yDomain = [Math.max(0, dataMin - padding), dataMax + padding];
  }

  // --- NEW: Formatter function for the Y-Axis ticks ---
  const formatYAxis = (tickItem: number) => {
    // Rounds the number to 2 decimal places for a clean look
    return tickItem.toFixed(2);
  };

  return (
    <div className="card">
      <h2 className="card-title">{title}</h2>
      <div style={{ width: '100%', height: 400 }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 50 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" />
            <XAxis 
              dataKey="timestamp" 
              tickFormatter={(unixTime) => new Date(unixTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              stroke="#9CA3AF" 
              label={{ value: "Time", position: "insideBottom", offset: -35, fill:"#9CA3AF" }}
              tick={{ fontSize: 12 }}
              domain={['dataMin', 'dataMax']}
              type="number"
            />
            {/* --- MODIFIED: Added the tickFormatter prop to the Y-axis --- */}
            <YAxis 
              stroke="#9CA3AF"
              label={{ value: 'Energy (kWh)', angle: -90, position: 'insideLeft', fill:"#9CA3AF", dx: -10 }}
              tick={{ fontSize: 12 }}
              domain={yDomain}
              allowDataOverflow={true}
              tickFormatter={formatYAxis} // <-- Apply the new formatter here
            />
            <Tooltip 
              contentStyle={{ backgroundColor: 'rgba(31, 41, 55, 0.9)', border: '1px solid #4A5568', borderRadius: '0.5rem' }} 
              labelFormatter={(label: number) => new Date(label).toLocaleString()}
              formatter={(value: number, name: string) => [`${value.toFixed(2)} kWh`, name === 'actual' ? 'Actual' : 'Simulated']}
            />
            <Legend wrapperStyle={{paddingTop: "20px"}} />
            <Line type="monotone" dataKey="actual" name="Actual Demand" stroke="#34D399" strokeWidth={2} dot={false} connectNulls={false} />
            <Line type="monotone" dataKey="predicted" name="Simulated Demand" stroke="#60A5FA" strokeWidth={2} dot={false} connectNulls={false} />
            <Brush dataKey="timestamp" height={30} stroke="#8884d8" y={320} tickFormatter={(unixTime) => new Date(unixTime).toLocaleDateString()} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};

export default ResultChart;