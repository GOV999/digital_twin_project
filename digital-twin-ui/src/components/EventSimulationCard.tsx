// src/components/EventSimulationCard.tsx

import React, { useState, useEffect } from 'react';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';
import * as apiService from '../services/apiService';
import { type SimulationResponse, type ChartDataPoint } from '../types';
import ResultChart from './ResultChart'; // Import our new reusable chart

interface EventSimulationCardProps {
  meterId: string;
  isSimulating: boolean;
  setIsSimulating: (isSimulating: boolean) => void;
}

const EVENT_TYPES = [
  { value: 'none', label: 'No Event (Backtest only)' },
  { value: 'heatwave', label: 'Simulate Heatwave' },
  { value: 'cold_snap', label: 'Simulate Cold Snap' },
  { value: 'holiday_shutdown', label: 'Simulate Holiday/Shutdown' },
];

const EventSimulationCard: React.FC<EventSimulationCardProps> = ({
  meterId,
  isSimulating,
  setIsSimulating
}) => {
  // Set default dates for the date pickers
  const today = new Date().toISOString().split('T')[0];
  const sevenDaysAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];

  // State for the simulation parameters
  const [startDate, setStartDate] = useState(sevenDaysAgo);
  const [endDate, setEndDate] = useState(today);
  const [eventType, setEventType] = useState('none');
  const [eventValue, setEventValue] = useState(5);

  // NEW: State for this card's specific results
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resultData, setResultData] = useState<SimulationResponse | null>(null);
  const [chartData, setChartData] = useState<ChartDataPoint[]>([]);

  const handleRunEventSimulation = async () => {
    if (new Date(startDate) >= new Date(endDate)) {
      setError("Start date must be before end date.");
      return;
    }
    
    setIsSimulating(true);
    setError(null);
    setNotice(null);
    setResultData(null);

    try {
      const modelName = 'dl_model';
      const trainingHours = 336;
      const eventObject = eventType !== 'none' ? { type: eventType, value: eventValue } : null;

      const result = await apiService.triggerEventSimulation(
        meterId, modelName, trainingHours, startDate, endDate, eventObject
      );
      
      setResultData(result); // Store the entire result object
      setNotice(`Backtest successful using the '${result.model_used}' model.`);
    } catch (err: any) {
      setError(err.message || 'An unknown error occurred during the simulation.');
    } finally {
      setIsSimulating(false);
    }
  };

  // useEffect to process data for the result chart whenever new results are available
  useEffect(() => {
    if (!resultData) {
      setChartData([]);
      return;
    }

    const newChartDataMap = new Map<number, ChartDataPoint>();

    // Add historical actuals that were returned with the simulation result
    (resultData.actual_readings_in_sim_range || []).forEach(reading => {
      const ts = new Date(reading.timestamp).getTime();
      newChartDataMap.set(ts, {
        timestamp: ts,
        dateLabel: new Date(ts).toLocaleString(),
        actual: reading.energy_kwh_import ?? undefined,
        predicted: undefined,
      });
    });

    // Add the new simulated predictions, updating existing points if they match
    (resultData.forecast_points || []).forEach(point => {
      const ts = new Date(point.timestamp).getTime();
      const predictedValue = point.predicted_kwh ?? undefined;
      let entry = newChartDataMap.get(ts);
      if (entry) {
        entry.predicted = predictedValue;
      } else {
        entry = { timestamp: ts, dateLabel: new Date(ts).toLocaleString(), actual: undefined, predicted: predictedValue };
      }
      newChartDataMap.set(ts, entry);
    });

    setChartData(Array.from(newChartDataMap.values()).sort((a, b) => a.timestamp - b.timestamp));
  }, [resultData]);

  const getEventLabel = () => {
    switch (eventType) {
      case 'heatwave': return 'Temperature Increase (°C)';
      case 'cold_snap': return 'Temperature Decrease (°C)';
      case 'holiday_shutdown': return 'Load Reduction (%)';
      default: return 'Event Value';
    }
  };

  return (
    <div className="card">
      <h2 className="card-title">Scenario & Event Simulation</h2>
      <p className="card-subtitle">
        Run a backtest on a historical period with a simulated event to see its impact.
      </p>

      <div className="event-simulation-controls">
        <div className="control-group">
          <label htmlFor="start-date" className="control-label">Start Date</label>
          <input type="date" id="start-date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="event-control-input" disabled={isSimulating} />
        </div>
        <div className="control-group">
          <label htmlFor="end-date" className="control-label">End Date</label>
          <input type="date" id="end-date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="event-control-input" disabled={isSimulating} />
        </div>
        <div className="control-group">
          <label htmlFor="event-type" className="control-label">Event Type</label>
          <select id="event-type" value={eventType} onChange={(e) => setEventType(e.target.value)} className="event-control-input" disabled={isSimulating}>
            {EVENT_TYPES.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </div>
        {eventType !== 'none' && (
          <div className="control-group">
            <label htmlFor="event-value" className="control-label">{getEventLabel()}</label>
            <input type="number" id="event-value" value={eventValue} onChange={(e) => setEventValue(Number(e.target.value))} className="event-control-input"
              step={eventType === 'holiday_shutdown' ? 10 : 1}
              min={0} max={eventType === 'holiday_shutdown' ? 100 : 50} disabled={isSimulating}
            />
          </div>
        )}
      </div>

      <button onClick={handleRunEventSimulation} className="run-simulation-button" disabled={isSimulating || !meterId}>
        {isSimulating ? <Spinner size="sm" /> : 'Run Event Simulation'}
      </button>

      {/* Display Area for Notices, Errors, and the Result Chart */}
      {notice && <div className="notice success-notice" style={{ marginTop: '1rem' }}>{notice}</div>}
      {error && <ErrorMessage message={error} />}

      {resultData && chartData.length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          {/* Note: We pass a hardcoded title here. The component is reusable. */}
          <ResultChart data={chartData} title="Event Simulation Result" />
        </div>
      )}
    </div>
  );
};

export default EventSimulationCard;