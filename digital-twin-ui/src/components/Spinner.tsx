import React from 'react';

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  // Color is now handled by the .spinner class in styles.css
}

const Spinner: React.FC<SpinnerProps> = ({ size = 'md' }) => {
  let sizeClass = 'spinner-md';
  if (size === 'sm') sizeClass = 'spinner-sm';
  if (size === 'lg') sizeClass = 'spinner-lg';

  return (
    <div className={`spinner ${sizeClass}`} role="status">
      <span className="sr-only">Loading...</span>
    </div>
  );
};

export default Spinner;