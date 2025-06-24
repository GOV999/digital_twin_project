import React, { useState, useEffect, useCallback } from 'react';
import * as CustomTypes from './types';
import { fetchConfiguredMeters } from './services/apiService';
import MeterSelector from './components/MeterSelector';
import Dashboard from './components/Dashboard';
import { RefreshIcon } from './components/icons/RefreshIcon';
import Spinner from './components/Spinner';
import ErrorMessage from './components/ErrorMessage';

const AUTO_REFRESH_INTERVAL_MS = 300000; // 5 minutes

const App: React.FC = () => {
  const [meters, setMeters] = useState<CustomTypes.Meter[]>([]);
  const [selectedMeterId, setSelectedMeterId] = useState<string | null>(null);
  const [loadingMeters, setLoadingMeters] = useState<boolean>(true);
  const [errorMeters, setErrorMeters] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState<number>(0);

  const handleRefreshAll = useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const loadMeters = useCallback(async () => {
    // No need to set loading true here, it's handled by the caller
    setErrorMeters(null);
    try {
      const fetchedMeters = await fetchConfiguredMeters();
      setMeters(fetchedMeters);
      // Set the first meter as selected ONLY if one isn't already selected
      if (fetchedMeters.length > 0 && !selectedMeterId) {
        setSelectedMeterId(fetchedMeters[0].meter_id);
      } else if (fetchedMeters.length === 0) {
        setSelectedMeterId(null);
      }
    } catch (error) {
      console.error("Failed to fetch meters:", error);
      setErrorMeters("Failed to load meter list. Please check the backend and try again.");
      setMeters([]);
      setSelectedMeterId(null);
    } finally {
      setLoadingMeters(false);
    }
  }, [selectedMeterId]); // dependency is correct

  // Initial load effect
  useEffect(() => {
    setLoadingMeters(true);
    loadMeters();
  }, []); // Runs only once on mount

  // Manual refresh effect
  useEffect(() => {
    if (refreshKey > 0) { // Don't run on initial render (key is 0)
        loadMeters();
    }
  }, [refreshKey, loadMeters]);

  // Auto-refresh for dashboard data
  useEffect(() => {
    const intervalId = setInterval(() => {
      if (selectedMeterId) {
        handleRefreshAll();
      }
    }, AUTO_REFRESH_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [selectedMeterId, handleRefreshAll]);


  const handleMeterSelect = (meterId: string) => {
    setSelectedMeterId(meterId);
  };

  const renderHeaderControls = () => {
    // This function decides what to show in the header
    if (loadingMeters) {
        return <Spinner size="sm" />;
    }
    if (errorMeters) {
        return <span className="text-red-400 text-sm">Error loading meters</span>;
    }
    if (meters.length > 0) {
        return (
            <MeterSelector
                meters={meters}
                selectedMeterId={selectedMeterId}
                onSelectMeter={handleMeterSelect}
            />
        );
    }
    return <span className="text-gray-400">No meters available.</span>;
  };
  
  const renderMainContent = () => {
    // This function decides what to show in the main area
    if (loadingMeters) {
        return (
            <div className="spinner-container" style={{height: '16rem'}}>
                <Spinner />
                <p className="spinner-text">Loading meter list...</p>
            </div>
        );
    }
    if (errorMeters) {
        return (
            <div className="mt-8">
                <ErrorMessage message={errorMeters} onRetry={loadMeters} />
            </div>
        );
    }
    if (selectedMeterId) {
        return (
            <Dashboard
                selectedMeterId={selectedMeterId}
                refreshTrigger={refreshKey}
                onSimulationComplete={handleRefreshAll}
            />
        );
    }
    // This is the fallback state if loading is done, no errors, but no meter is selected
    return (
        <div className="no-data-placeholder mt-10" style={{height: '100%'}}>
            <svg xmlns="http://www.w3.org/2000/svg" className="no-data-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <h2 className="no-data-title">Select a Meter</h2>
            <p className="no-data-text">Please select a meter from the dropdown above to view its dashboard.</p>
        </div>
    );
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="header-content">
          <h1 className="header-title">
            Digital Twin: Demand Forecasting
          </h1>
          <div className="header-controls">
            {renderHeaderControls()}
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
        {renderMainContent()}
      </main>
      
      <footer className="app-footer">
        Digital Twin Project © {new Date().getFullYear()}
      </footer>
    </div>
  );
};

export default App;