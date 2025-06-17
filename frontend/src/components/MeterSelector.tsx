
import React from 'react';
import { Meter } from '../types';

interface MeterSelectorProps {
  meters: Meter[];
  selectedMeterId: string | null;
  onSelectMeter: (meterId: string) => void;
}

const MeterSelector: React.FC<MeterSelectorProps> = ({ meters, selectedMeterId, onSelectMeter }) => {
  if (meters.length === 0) {
    return <p className="text-center text-gray-400">No meters available.</p>;
  }

  return (
    <div className="w-full">
      <label htmlFor="meter-select" className="block text-sm font-medium text-sky-300 mb-1">
        Select Meter
      </label>
      <select
        id="meter-select"
        value={selectedMeterId || ''}
        onChange={(e) => onSelectMeter(e.target.value)}
        className="w-full bg-slate-700 border border-slate-600 text-gray-100 py-2 px-3 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500 transition duration-150"
      >
        {meters.map((meter) => (
          <option key={meter.meter_id} value={meter.meter_id}>
            {meter.meter_id} ({meter.location_type})
          </option>
        ))}
      </select>
    </div>
  );
};

export default MeterSelector;
    