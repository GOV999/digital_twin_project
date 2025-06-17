
import React, { useState, useEffect, useCallback } from 'react';
import { Meter } from './types';
import { fetchMeters } from './services/api';
import MeterSelector from './components/MeterSelector';
import Dashboard from './components/Dashboard';
import LoadingSpinner from './components/LoadingSpinner';

const App: React.FC = () => {
  const [meters, setMeters] = useState<Meter[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [isLoadingMeters, setIsLoadingMeters] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadMeters = async () => {
      try {
        setIsLoadingMeters(true);
        setError(null);
        const fetchedMeters = await fetchMeters();
        setMeters(fetchedMeters);
        if (fetchedMeters.length > 0) {
          setSelectedMeterId(fetchedMeters[0].meter_id);
        }
      } catch (err) {
        console.error("Failed to fetch meters:", err);
        setError("Failed to load meter data. Please ensure the backend API is running.");
      } finally {
        setIsLoadingMeters(false);
      }
    };
    loadMeters();
  }, []);

  const handleSelectMeter = useCallback((meterId: string) => {
    setSelectedMeterId(meterId);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-700 text-gray-100 p-4 sm:p-6 lg:p-8">
      <header className="mb-8 text-center">
        <h1 className="text-4xl font-bold tracking-tight text-transparent bg-clip-text bg-gradient-to-r from-sky-400 to-blue-500">
          Digital Twin Demand Forecasting
        </h1>
      </header>

      {isLoadingMeters && (
        <div className="flex justify-center items-center h-64">
          <LoadingSpinner />
          <p className="ml-3 text-lg">Loading meters...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-700 text-white p-4 rounded-md shadow-lg max-w-2xl mx-auto">
          <h2 className="font-semibold text-xl mb-2">Error</h2>
          <p>{error}</p>
        </div>
      )}

      {!isLoadingMeters && !error && meters.length === 0 && (
         <div className="bg-slate-800 text-yellow-400 p-4 rounded-md shadow-lg max-w-2xl mx-auto text-center">
           <h2 className="font-semibold text-xl mb-2">No Meters Found</h2>
           <p>No smart meters are available. Please check the backend configuration or data source.</p>
         </div>
      )}

      {!isLoadingMeters && !error && meters.length > 0 && (
        <>
          <div className="max-w-xs mx-auto mb-8">
            <MeterSelector
              meters={meters}
              selectedMeterId={selectedMeterId}
              onSelectMeter={handleSelectMeter}
            />
          </div>
          {selectedMeterId && <Dashboard key={selectedMeterId} selectedMeterId={selectedMeterId} />}
        </>
      )}
       <footer className="text-center mt-12 text-sm text-slate-400">
        <p>Digital Twin Dashboard v1.0</p>
      </footer>
    </div>
  );
};

export default App;
    