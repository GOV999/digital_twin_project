import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from './types'; // Changed to namespace import
import { fetchMeters } from './services/apiService';
import MeterSelector from './components/MeterSelector';
import Dashboard from './components/Dashboard';
import { RefreshIcon } from './components/icons/RefreshIcon';
import Spinner from './components/Spinner'; 
import ErrorMessage from './components/ErrorMessage';

const AUTO_REFRESH_INTERVAL_MS = 60000; // 60 seconds

const App: React.FC = () => {
  const [meters, setMeters] = useState<CustomTypes.Meter[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [loadingMeters, setLoadingMeters] = useState<boolean>(true);
  const [errorMeters, setErrorMeters] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const loadMeters = useCallback(async (isInitialLoad = false) => {
    setLoadingMeters(true);
    setErrorMeters(null);
    try {
      const fetchedMeters = await fetchMeters();
      setMeters(fetchedMeters);
      if (fetchedMeters.length > 0 && (isInitialLoad || !selectedMeterId)) {
        setSelectedMeterId(fetchedMeters[0].meter_id);
      } else if (fetchedMeters.length === 0) {
        setSelectedMeterId(null);
      }
    } catch (error) {
      console.error("Failed to fetch meters:", error);
      setErrorMeters("Failed to load meter list. Please try again.");
      setMeters([]);
      setSelectedMeterId(null);
    } finally {
      setLoadingMeters(false);
    }
  }, [selectedMeterId]);

  // Initial load and manual refresh
  useEffect(() => {
    loadMeters(true); // Pass true for initial load logic
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]); // Removed loadMeters from dependencies to avoid loop with setSelectedMeterId

  // Auto-refresh mechanism
  useEffect(() => {
    const intervalId = setInterval(() => {
      setRefreshKey(prev => prev + 1);
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => clearInterval(intervalId); // Cleanup interval on component unmount
  }, []);


  const handleMeterSelect = (meterId: string) => {
    setSelectedMeterId(meterId);
  };

  const handleRefreshAll = () => {
    setRefreshKey(prev => prev + 1); 
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <h1 className="header-title">
            Digital Twin: Demand Forecasting
          </h1>
          <div className="header-controls">
            {loadingMeters && <Spinner size="sm" />}
            {!loadingMeters && errorMeters && <span className="text-red-400 text-sm">Error loading meters</span>}
            {!loadingMeters && !errorMeters && meters.length > 0 && (
              <MeterSelector
                meters={meters}
                selectedMeterId={selectedMeterId}
                onSelectMeter={handleMeterSelect}
              />
            )}
             {!loadingMeters && meters.length === 0 && !errorMeters && (
              <span className="text-gray-400">No meters available.</span>
            )}
            <button
              onClick={handleRefreshAll}
              disabled={loadingMeters}
              className="button"
              title="Refresh all data"
            >
              <RefreshIcon style={{width: '1.25rem', height: '1.25rem'}} />
            </button>
          </div>
        </div>
      </header>

      <main className="main-content">
        {loadingMeters && !errorMeters && (
          <div className="spinner-container" style={{height: '16rem'}}> {/* h-64 */}
            <Spinner />
            <p className="spinner-text">Loading meter list...</p>
          </div>
        )}
        {errorMeters && (
          <div className="mt-8">
            <ErrorMessage message={errorMeters} onRetry={() => loadMeters(true)} />
          </div>
        )}
        {!loadingMeters && !errorMeters && meters.length === 0 && (
           <div className="no-data-placeholder mt-10" style={{height: '100%'}}>
            <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="no-data-title">No Meters Found</h2>
            <p className="no-data-text">The system did not return any meters. Please check the backend configuration or try refreshing.</p>
          </div>
        )}
        {!loadingMeters && !errorMeters && meters.length > 0 && !selectedMeterId && (
          <div className="no-data-placeholder mt-10" style={{height: '100%'}}>
             <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            <h2 className="no-data-title">Select a Meter</h2>
            <p className="no-data-text">Please select a meter from the dropdown above to view its dashboard.</p>
          </div>
        )}
        {selectedMeterId && (
          <Dashboard selectedMeterId={selectedMeterId} refreshTrigger={refreshKey} />
        )}
      </main>
      <footer className="app-footer">
        Digital Twin Project &copy; {new Date().getFullYear()}
      </footer>
    </div>
  );
};

export default App;