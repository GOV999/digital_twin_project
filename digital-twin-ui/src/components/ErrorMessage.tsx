import React from 'react';
import { RefreshIcon } from './icons/RefreshIcon';

interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({ message, onRetry }) => {
  return (
    <div className="error-message-container" role="alert">
      <div className="error-message-content">
        <svg xmlns="http://www.w3.org/2000/svg" className="error-message-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <div className="error-message-text">
            <strong>Error:</strong>
            <span>{message}</span>
        </div>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="error-retry-button"
        >
          <RefreshIcon className="error-retry-button-icon" />
          Try Again
        </button>
      )}
    </div>
  );
};

export default ErrorMessage;