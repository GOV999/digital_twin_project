import React, { useState, useEffect, useCallback, useRef } from 'react';
import * as apiService from '../services/apiService';
import * as CustomTypes from '../types';
import Spinner from './Spinner';
import ErrorMessage from './ErrorMessage';

const LOG_REFRESH_INTERVAL_MS = 5000; // Refresh logs every 5 seconds if scraper is running

const ScraperControl: React.FC = () => {
  const [status, setStatus] = useState<CustomTypes.ScraperRunStatus>('not_started');
  const [logs, setLogs] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false); // For button actions
  const [isFetchingLogs, setIsFetchingLogs] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const logDisplayRef = useRef<HTMLPreElement>(null);

  const getStatusColor = () => {
    switch (status) {
      case 'running': return 'text-green-400';
      case 'stopped': return 'text-yellow-400';
      case 'not_started': return 'text-gray-400';
      case 'error':
      case 'error_stopping':
        return 'text-red-400';
      default: return 'text-gray-400';
    }
  };

  const fetchStatus = useCallback(async () => {
    try {
      setError(null);
      const response = await apiService.fetchScraperStatus();
      setStatus(response.status);
    } catch (err) {
      console.error("Failed to fetch scraper status:", err);
      setStatus('error');
      setError(err instanceof Error ? err.message : "Failed to fetch status");
    }
  }, []);

  const fetchLogs = useCallback(async (showLoading = false) => {
    if (showLoading) setIsFetchingLogs(true);
    try {
      setError(null); // Clear general error when fetching logs
      const response = await apiService.fetchScraperLogs(100); // Fetch last 100 lines
      setLogs(response.logs || []);
      if (response.error) {
        // If backend reports error with logs (e.g. file not found)
        setError(`Log fetch issue: ${response.error}`);
      }
    } catch (err) {
      console.error("Failed to fetch scraper logs:", err);
      // Don't overwrite scraper status error with log fetch error unless critical
      if (status !== 'error' && status !== 'error_stopping') {
          setError(err instanceof Error ? err.message : "Failed to fetch logs");
      }
      setLogs(prevLogs => [...prevLogs, `--- Error fetching logs: ${err instanceof Error ? err.message : "Unknown error"} ---`]);
    } finally {
      if (showLoading) setIsFetchingLogs(false);
    }
  }, [status]); // status dependency to avoid setting error if scraper itself is in error state

  useEffect(() => {
    fetchStatus(); // Initial status fetch
    fetchLogs(true); // Initial log fetch
  }, [fetchStatus, fetchLogs]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null;
    if (status === 'running') {
      intervalId = setInterval(() => {
        fetchLogs(); // Fetch logs without showing main loading spinner
      }, LOG_REFRESH_INTERVAL_MS);
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [status, fetchLogs]);

  useEffect(() => {
    // Auto-scroll log display to the bottom
    if (logDisplayRef.current) {
      logDisplayRef.current.scrollTop = logDisplayRef.current.scrollHeight;
    }
  }, [logs]);


  const handleStartScraper = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiService.startScraper();
      setStatus(response.status || 'running'); // Assume running on success
      setLogs(prev => [...prev, `--- ${response.message || 'Scraper start requested.'} ---`]);
      fetchLogs(); // Fetch logs immediately after starting
    } catch (err) {
      console.error("Failed to start scraper:", err);
      setStatus('error');
      setError(err instanceof Error ? err.message : "Failed to start scraper");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopScraper = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiService.stopScraper();
      setStatus(response.status || 'stopped'); // Assume stopped on success
      setLogs(prev => [...prev, `--- ${response.message || 'Scraper stop requested.'} ---`]);
    } catch (err) {
      console.error("Failed to stop scraper:", err);
      setStatus('error_stopping'); // Special status for stop error
      setError(err instanceof Error ? err.message : "Failed to stop scraper");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="card scraper-controls-container">
      <h2 className="card-title">Scraper Control</h2>
      <div className="scraper-status-section">
        <span>Status: </span>
        <span className={`scraper-status ${getStatusColor()}`}>{status.replace('_', ' ')}</span>
        { (isLoading || (status === 'running' && isFetchingLogs)) && <Spinner size="sm" />}
      </div>

      {error && <ErrorMessage message={error} onRetry={status.startsWith('error') ? fetchStatus : fetchLogs} />}

      <div className="scraper-buttons">
        <button
          onClick={handleStartScraper}
          disabled={isLoading || status === 'running'}
          className="button start-scraper-button"
        >
          {isLoading && status !== 'running' ? <Spinner size="sm"/> : null}
          Start Scraper
        </button>
        <button
          onClick={handleStopScraper}
          disabled={isLoading || (status !== 'running' && status !== 'error_stopping')}
          className="button stop-scraper-button"
        >
         {isLoading && (status === 'running' || status === 'error_stopping') ? <Spinner size="sm"/> : null}
          Stop Scraper
        </button>
         <button
          onClick={() => fetchLogs(true)}
          disabled={isFetchingLogs}
          className="button refresh-logs-button"
          title="Refresh Logs Manually"
        >
          {isFetchingLogs ? <Spinner size="sm"/> : 'Refresh Logs'}
        </button>
      </div>

      <div className="scraper-log-display-container">
        <h3 className="scraper-log-title">Scraper Logs (Last ~100 lines):</h3>
        <pre ref={logDisplayRef} className="scraper-log-display">
          {logs.length > 0 ? logs.join('\n') : 'No logs to display. Start scraper to see logs.'}
        </pre>
      </div>
    </div>
  );
};

export default ScraperControl;