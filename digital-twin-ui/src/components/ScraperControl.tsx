import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as apiService from '../services/apiService';
import * as CustomTypes from '../types';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';

interface ScraperControlProps {
  selectedMeterId: string | null;
}

const ScraperControl: React.FC<ScraperControlProps> = ({ selectedMeterId }) => {
  const [statuses, setStatuses] = useState<CustomTypes.ScraperStatusResponse['statuses']>({});
  const [logs, setLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isFetchingLogs, setIsFetchingLogs] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const logDisplayRef = useRef<HTMLPreElement>(null);

  // --- ROBUST STATUS DERIVATION ---
  // This now safely handles the case where the meter ID might not be in the statuses object yet.
  const currentStatus: CustomTypes.ScraperRunStatus = 
    selectedMeterId && statuses[selectedMeterId] ? statuses[selectedMeterId] : 'not_started';

  const getStatusColor = () => {
    switch (currentStatus) {
      case 'running': return 'text-green-400';
      case 'stopped': return 'text-yellow-400';
      case 'error':
      case 'error_stopping': return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const updateStatus = useCallback(async () => {
    try {
      setError(null);
      const response = await apiService.fetchScraperStatus();
      setStatuses(response.statuses || {});
    } catch (err) {
      console.error("Failed to fetch scraper status:", err);
      setError(err instanceof Error ? err.message : "Failed to fetch status");
      // Don't set a component-wide status, just show the error message
    }
  }, []);

  const handleFetchLogs = useCallback(async (showLoading = false) => {
    if (!selectedMeterId) {
        setLogs(["Please select a meter to view its logs."]);
        return;
    }
    if (showLoading) setIsFetchingLogs(true);
    try {
      const response = await apiService.fetchScraperLogs(selectedMeterId, 150);
      setLogs(response.logs || []);
    } catch (err) {
      console.error("Failed to fetch scraper logs:", err);
      setLogs(prev => [...prev, `--- Error fetching logs: ${err instanceof Error ? err.message : "Unknown error"} ---`]);
    } finally {
      if (showLoading) setIsFetchingLogs(false);
    }
  }, [selectedMeterId]);

  // Initial and periodic status updates
  useEffect(() => {
    updateStatus();
    const interval = setInterval(updateStatus, 5000); // Poll status every 5 seconds
    return () => clearInterval(interval);
  }, [updateStatus]);

  // Fetch logs when the selected meter changes
  useEffect(() => {
    handleFetchLogs(true);
  }, [handleFetchLogs]);


  useEffect(() => {
    if (logDisplayRef.current) {
      logDisplayRef.current.scrollTop = logDisplayRef.current.scrollHeight;
    }
  }, [logs]);


  
  const handleStartScraper = async () => {
    if (!selectedMeterId) return;
    setIsLoading(true);
    setError(null); // Clear previous errors
    try {
      await apiService.startScraper(selectedMeterId);
      setStatuses(prev => ({ ...prev, [selectedMeterId]: 'running' }));
      setTimeout(updateStatus, 1000);
    } catch (err) {
      // --- THIS IS THE ENHANCEMENT ---
      // Display the specific error message from the backend
      const apiError = err as CustomTypes.ApiError;
      const errorMessage = apiError.data?.message || apiError.message || "An unknown error occurred.";
      console.error("Failed to start scraper:", errorMessage);
      setError(`Start failed: ${errorMessage}`);
      updateStatus();
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopScraper = async () => {
    if (!selectedMeterId) return;
    setIsLoading(true);
    setError(null);
    try {
      await apiService.stopScraper(selectedMeterId);
      // Immediately update status to give user feedback
      setStatuses(prev => ({ ...prev, [selectedMeterId]: 'stopped' }));
      setTimeout(updateStatus, 1000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to stop scraper");
      updateStatus();
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card scraper-controls-container">
      <h2 className="card-title">Scraper Control {selectedMeterId && `for Meter ${selectedMeterId}`}</h2>
      <div className="scraper-status-section">
        <span>Status: </span>
        <span className={`scraper-status ${getStatusColor()}`}>{currentStatus.replace(/_/g, ' ')}</span>
        {(isLoading || isFetchingLogs) && <Spinner size="sm" />}
      </div>

      {error && <ErrorMessage message={error} onRetry={updateStatus} />}

      <div className="scraper-buttons">
        <button
          onClick={handleStartScraper}
          disabled={!selectedMeterId || isLoading || currentStatus === 'running'}
          className="button start-scraper-button"
        >
          {isLoading && currentStatus !== 'running' ? <Spinner size="sm"/> : 'Start Scraper'}
        </button>
        <button
          onClick={handleStopScraper}
          disabled={!selectedMeterId || isLoading || currentStatus !== 'running'}
          className="button stop-scraper-button"
        >
         {isLoading && currentStatus === 'running' ? <Spinner size="sm"/> : 'Stop Scraper'}
        </button>
         <button
          onClick={() => handleFetchLogs(true)}
          disabled={isFetchingLogs || !selectedMeterId}
          className="button refresh-logs-button"
          title="Refresh Logs Manually"
        >
          {isFetchingLogs ? <Spinner size="sm"/> : 'Refresh Logs'}
        </button>
      </div>

      <div className="scraper-log-display-container">
        <h3 className="scraper-log-title">Scraper Logs (Last ~150 lines):</h3>
        <pre ref={logDisplayRef} className="scraper-log-display">
          {logs.length > 0 ? logs.join('\n') : 'No logs to display.'}
        </pre>
      </div>
    </div>
  );
};

export default ScraperControl;