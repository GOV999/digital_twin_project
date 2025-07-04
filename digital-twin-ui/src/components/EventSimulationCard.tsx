// src/components/EventSimulationCard.tsx

import React, { useState } from 'react';
import Spinner from './Spinner';

// Define the shape of the props this component will receive
interface EventSimulationCardProps {
  meterId: string;
  onSimulationStart: () => void;
  onSimulationComplete: (result: any) => void;
  onSimulationError: (error: string) => void;
  isSimulating: boolean;
}

const EVENT_TYPES = [
  { value: 'none', label: 'No Event' },
  { value: 'heatwave', label: 'Simulate Heatwave' },
  { value: 'cold_snap', label: 'Simulate Cold Snap' },
  { value: 'holiday_shutdown', label: 'Simulate Holiday/Shutdown' },
];

const EventSimulationCard: React.FC<EventSimulationCardProps> = ({
  meterId,
  onSimulationStart,
  onSimulationComplete,
  onSimulationError,
  isSimulating
}) => {
  const today = new Date().toISOString().split('T')[0];
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  // State for the simulation parameters
  const [startDate, setStartDate] = useState(sevenDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [eventType, setEventType] = useState('none');
  const [eventValue, setEventValue] = useState(5); // Default for heatwave/coldsnap

  const handleRunEventSimulation = async () => {
    // Basic validation
    if (new Date(startDate) >= new Date(endDate)) {
      onSimulationError("Start date must be before end date.");
      return;
    }

    onSimulationStart();
    
    // This is where you would call your apiService function.
    // For now, we'll just log the parameters.
    // In the next step, we will create this function in apiService.
    console.log("Running Event Simulation with params:", {
      meterId,
      startDate,
      endDate,
      eventType,
      eventValue,
    });

    // Placeholder for actual API call
    // try {
    //   const result = await apiService.triggerEventSimulation(...);
    //   onSimulationComplete(result);
    // } catch (err: any) {
    //   onSimulationError(err.message);
    // }
  };

  const getEventLabel = () => {
    switch (eventType) {
      case 'heatwave':
        return 'Temperature Increase (°C)';
      case 'cold_snap':
        return 'Temperature Decrease (°C)';
      case 'holiday_shutdown':
        return 'Load Reduction (%)';
      default:
        return 'Event Value';
    }
  };

  return (
    <div className="card">
      <h2 className="card-title">Scenario & Event Simulation</h2>
      <p className="card-subtitle">
        Run a backtest on a historical period with a simulated event to see its impact on consumption.
      </p>

      <div className="event-simulation-controls">
        {/* Date Range Pickers */}
        <div className="control-group">
          <label htmlFor="start-date" className="control-label">Start Date</label>
          <input
            type="date"
            id="start-date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            // --- ADD/REPLACE class here ---
            className="event-control-input"
            disabled={isSimulating}
          />
        </div>
        <div className="control-group">
          <label htmlFor="end-date" className="control-label">End Date</label>
          <input
            type="date"
            id="end-date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            // --- ADD/REPLACE class here ---
            className="event-control-input"
            disabled={isSimulating}
          />
        </div>

        {/* Event Type Dropdown */}
        <div className="control-group">
          <label htmlFor="event-type" className="control-label">Event Type</label>
          <select
            id="event-type"
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            // --- ADD/REPLACE class here ---
            className="event-control-input"
            disabled={isSimulating}
          >
            {EVENT_TYPES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </div>

        {/* Conditional Event Value Input */}
        {eventType !== 'none' && (
          <div className="control-group">
            <label htmlFor="event-value" className="control-label">{getEventLabel()}</label>
            <input
              type="number"
              id="event-value"
              value={eventValue}
              onChange={(e) => setEventValue(Number(e.target.value))}
              // --- ADD/REPLACE class here ---
              className="event-control-input"
              // ... other props
            />
          </div>
        )}
      </div>

      <button
        onClick={handleRunEventSimulation}
        className="run-simulation-button"
        disabled={isSimulating || !meterId}
      >
        {isSimulating ? <Spinner size="sm" /> : 'Run Event Simulation'}
      </button>
    </div>
  );
};

export default EventSimulationCard;