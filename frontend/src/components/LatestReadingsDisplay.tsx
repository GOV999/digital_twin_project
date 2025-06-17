
import React from 'react';
import { Reading } from '../types';
import DataCard from './DataCard'; // Using DataCard for consistent item display

interface LatestReadingsDisplayProps {
  readings: Reading[];
  meterId: string;
}

const LatestReadingsDisplay: React.FC<LatestReadingsDisplayProps> = ({ readings, meterId }) => {
  return (
    <div className="bg-slate-800 p-4 sm:p-6 rounded-lg shadow-xl">
      <h3 className="text-xl font-semibold mb-4 text-sky-300">Latest Meter Readings</h3>
      {readings.length === 0 ? (
        <p className="text-slate-500">No recent readings available for meter {meterId}.</p>
      ) : (
        <div className="space-y-3">
          {readings.map((reading, index) => {
            // Safely convert energy_kwh_import to a number before using toFixed
            const energyValue = reading.energy_kwh_import !== null && reading.energy_kwh_import !== undefined 
                                ? Number(reading.energy_kwh_import) 
                                : null;
            
            const displayValue = (energyValue !== null && !isNaN(energyValue)) 
                                 ? energyValue.toFixed(3) 
                                 : 'N/A';

            return (
              <DataCard
                key={index}
                title={new Date(reading.timestamp).toLocaleString([], {dateStyle: 'short', timeStyle: 'medium'})}
                value={displayValue}
                unit="kWh"
              />
            );
          })}
        </div>
      )}
    </div>
  );
};

export default LatestReadingsDisplay;
