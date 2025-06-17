
import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { CombinedDataPoint } from '../types';

interface LineChartComponentProps {
  data: CombinedDataPoint[];
}

const formatDateTick = (tickItem: string) => {
  const date = new Date(tickItem);
  // Show date if it's the first tick of a new day or the very first tick, otherwise just time
  // This is a simplified heuristic; more robust logic might be needed for sparse data
  if (date.getHours() === 0 && date.getMinutes() === 0) {
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};


const LineChartComponent: React.FC<LineChartComponentProps> = ({ data }) => {
  if (!data || data.length === 0) {
    return <p className="text-center text-slate-500">No data available for chart.</p>;
  }

  // Ensure timestamps are sorted for Recharts if not guaranteed by API
  const sortedData = [...data].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());

  return (
    <div style={{ width: '100%', height: 400 }}>
      <ResponsiveContainer>
        <LineChart
          data={sortedData}
          margin={{
            top: 5,
            right: 20, // Adjusted for better label visibility
            left: 0,  // Adjusted for better label visibility
            bottom: 30, // Increased for XAxis labels
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" /> {/* Darker grid for light text */}
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={formatDateTick} 
            stroke="#94A3B8" // Light gray for axis line and ticks
            tick={{ fontSize: 10, fill: '#94A3B8' }} // Tick text color
            angle={-30} // Angle labels to prevent overlap
            textAnchor="end" // Align angled labels
            interval="preserveStartEnd" // Show first and last, and some in between
            minTickGap={30} // Minimum gap between ticks
          />
          <YAxis 
            stroke="#94A3B8" 
            tick={{ fontSize: 10, fill: '#94A3B8' }}
            label={{ value: 'Energy (kWh)', angle: -90, position: 'insideLeft', fill: '#94A3B8', fontSize: 12, dx: -5 }}
           />
          <Tooltip
            contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid #334155', borderRadius: '0.375rem' }} // Tailwind slate-800 like
            labelStyle={{ color: '#E2E8F0', fontWeight: 'bold' }} // Tailwind slate-200
            itemStyle={{ color: '#CBD5E1' }} // Tailwind slate-300
            formatter={(value: number | string | null | undefined, name: string) => {
              // Safely convert value to number and format, or display 'N/A'
              const numValue = value !== null && value !== undefined ? Number(value) : null;
              if (numValue !== null && !isNaN(numValue)) {
                return [`${numValue.toFixed(3)} kWh`, name];
              }
              return ['N/A', name]; // Display 'N/A' if value is not a valid number
            }}
            labelFormatter={(label: string) => new Date(label).toLocaleString()}
          />
          <Legend wrapperStyle={{ color: '#CBD5E1', paddingTop: '10px' }} />
          <Line 
            type="monotone" 
            dataKey="actual_kwh" 
            stroke="#38BDF8" // Sky-400
            strokeWidth={2} 
            dot={{ r: 2, fill: '#38BDF8' }} 
            activeDot={{ r: 5 }}
            name="Actual Consumption" 
            connectNulls={true}
          />
          <Line 
            type="monotone" 
            dataKey="predicted_kwh" 
            stroke="#34D399" // Emerald-400
            strokeWidth={2}
            dot={{ r: 2, fill: '#34D399' }}
            activeDot={{ r: 5 }}
            name="Predicted Demand"
            connectNulls={true}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default LineChartComponent;
