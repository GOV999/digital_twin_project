import React from 'react';
import * as CustomTypes from '../types'; // Changed to namespace import

interface MeterSelectorProps {
  meters: CustomTypes.Meter[];
  selectedMeterId: string | null;
  onSelectMeter: (meterId: string) => void;
}

const MeterSelector: React.FC<MeterSelectorProps> = ({ meters, selectedMeterId, onSelectMeter }) => {
  if (!meters || meters.length === 0) {
    return <span className="text-gray-400">No meters available</span>;
  }

  return (
    <div style={{display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
      <label htmlFor="meter-select" className="meter-selector-label">Select Meter:</label>
      <select
        id="meter-select"
        value={selectedMeterId || ''}
        onChange={(e) => onSelectMeter(e.target.value)}
        className="meter-selector-select"
      >
        <option value="" disabled>-- Select a Meter --</option>
        {meters.map((meter) => (
          <option key={meter.meter_id} value={meter.meter_id}>
            {meter.name || `Meter ${meter.meter_id}`} {meter.location_type ? `(${meter.location_type})` : ''}
          </option>
        ))}
      </select>
    </div>
  );
};

export default MeterSelector;