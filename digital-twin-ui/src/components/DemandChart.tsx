import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import * as CustomTypes from '../types'; 

interface DemandChartProps {
  data: CustomTypes.ChartDataPoint[];
}

const DemandChart: React.FC<DemandChartProps> = ({ data }) => {
  // ***** ADD THIS CONSOLE LOG *****
  console.log("[DemandChart] Data received for chart (first 10 points):", data.slice(0, 10));
  const pointsWithPredictions = data.filter(d => d.predicted !== undefined && d.predicted !== null);
  console.log("[DemandChart] Points with defined predictions (count and first 5):", pointsWithPredictions.length, pointsWithPredictions.slice(0, 5));
  // *******************************

  if (!data || data.length === 0) {
    return <p style={{textAlign: 'center', color: '#9ca3af', padding: '2rem 0'}}>No data available for chart.</p>;
  }
  
  // Check if there's any data to plot for either line
  const hasActualData = data.some(p => typeof p.actual === 'number');
  const hasPredictedData = data.some(p => typeof p.predicted === 'number');

  if (!hasActualData && !hasPredictedData) {
    return <p style={{textAlign: 'center', color: '#9ca3af', padding: '2rem 0'}}>No actual or predicted values to plot.</p>;
  }

  return (
    <div style={{ width: '100%', height: 400 }}>
      <ResponsiveContainer>
        <LineChart
          data={data}
          margin={{
            top: 5, right: 30, left: 20, bottom: 20,
          }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#4A5568" /> 
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={(unixTime) => new Date(unixTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            stroke="#9CA3AF" 
            label={{ value: "Time", position: "insideBottom", offset: -15, fill:"#9CA3AF" }}
            tick={{ fontSize: 12 }}
            domain={['dataMin', 'dataMax']} // Ensure all timestamps are considered
            type="number" // Important for time-series data
          />
          <YAxis 
            stroke="#9CA3AF"
            label={{ value: 'Energy (kWh)', angle: -90, position: 'insideLeft', fill:"#9CA3AF", dx: -10 }}
            tick={{ fontSize: 12 }}
            domain={['auto', 'auto']} // Default, usually fine
          />
          <Tooltip 
            contentStyle={{ backgroundColor: 'rgba(31, 41, 55, 0.9)', border: '1px solid #4A5568', borderRadius: '0.5rem' }} 
            labelStyle={{ color: '#E5E7EB', fontWeight: 'bold' }}
            itemStyle={{ color: '#D1D5DB' }}
            formatter={(value: number | null | undefined, name: string, props: any) => {
                if (value === null || value === undefined) return ['N/A', name === 'actual' ? 'Actual Demand' : 'Predicted Demand'];
                return [`${(value as number).toFixed(2)} kWh`, name === 'actual' ? 'Actual Demand' : 'Predicted Demand'];
            }}
            labelFormatter={(label: number) => new Date(label).toLocaleString()}
          />
          <Legend wrapperStyle={{paddingTop: "20px"}} />
          {hasActualData && (
            <Line 
              type="monotone" 
              dataKey="actual" 
              stroke="#34D399" 
              strokeWidth={2}
              dot={{ r: 2, fill: '#34D399' }}
              activeDot={{ r: 5 }}
              name="Actual Demand" 
              connectNulls={false} // Important: don't connect over missing actuals
            />
          )}
          {hasPredictedData && (
            <Line 
              type="monotone" 
              dataKey="predicted" 
              stroke="#60A5FA" 
              strokeWidth={2}
              strokeDasharray="5 5" 
              dot={{ r: 2, fill: '#60A5FA' }}
              activeDot={{ r: 5 }}
              name="Predicted Demand" 
              connectNulls={false} // Important: don't connect over missing predictions if any (though ideally all future points are predicted)
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
};

export default DemandChart;