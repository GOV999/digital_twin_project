
import React from 'react';

interface DataCardProps {
  title: string;
  value: string | number;
  unit?: string;
  variant?: 'info' | 'warning' | 'default';
  smallText?: boolean;
}

const DataCard: React.FC<DataCardProps> = ({ title, value, unit, variant = 'default', smallText = false }) => {
  let bgColor = 'bg-slate-700';
  let titleColor = 'text-sky-400';
  let valueColor = 'text-gray-100';

  if (variant === 'info') {
    bgColor = 'bg-blue-700';
    titleColor = 'text-blue-200';
    valueColor = 'text-blue-50';
  } else if (variant === 'warning') {
    bgColor = 'bg-yellow-700';
    titleColor = 'text-yellow-200';
    valueColor = 'text-yellow-50';
  }

  return (
    <div className={`p-3 rounded-md shadow ${bgColor}`}>
      <h4 className={`text-xs font-medium ${titleColor} ${smallText ? 'mb-0.5' : 'mb-1'}`}>{title}</h4>
      <p className={`font-semibold ${valueColor} ${smallText ? 'text-sm' : 'text-lg'}`}>
        {value} {unit && <span className={`text-xs ${smallText ? '' : 'ml-1'}`}>{unit}</span>}
      </p>
    </div>
  );
};

export default DataCard;
    