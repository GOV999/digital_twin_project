
import React from 'react';
import * as CustomTypes from '../types'; // Changed to namespace import

interface ReadingsTableProps {
  readings: CustomTypes.MeterReading[];
}

const formatNumber = (value: number | null | undefined, precision: number = 2): string => {
  if (value === null || value === undefined || isNaN(value)) {
    return 'N/A';
  }
  return value.toFixed(precision);
};

const formatTimestamp = (timestamp: string | null | undefined): string => {
  if (!timestamp) {
    return 'N/A';
  }
  try {
    return new Date(timestamp).toLocaleString();
  } catch (e) {
    return 'Invalid Date';
  }
};

const ReadingsTable: React.FC<ReadingsTableProps> = ({ readings }) => {
  if (!readings || readings.length === 0) {
    return <p style={{textAlign: 'center', color: '#9ca3af', padding: '1rem 0'}}>No recent readings available.</p>;
  }

  // Define the order and headers for the columns
  const columns = [
    { key: 'timestamp', header: 'Timestamp', render: (r: CustomTypes.MeterReading) => formatTimestamp(r.timestamp) },
    { key: 'energy_kwh_import', header: 'Energy Import (kWh)', render: (r: CustomTypes.MeterReading) => formatNumber(r.energy_kwh_import, 3) },
    { key: 'voltage_vrn', header: 'Voltage VRN (V)', render: (r: CustomTypes.MeterReading) => formatNumber(r.voltage_vrn, 1) },
    { key: 'voltage_vyn', header: 'Voltage VYN (V)', render: (r: CustomTypes.MeterReading) => formatNumber(r.voltage_vyn, 1) },
    { key: 'voltage_vbn', header: 'Voltage VBN (V)', render: (r: CustomTypes.MeterReading) => formatNumber(r.voltage_vbn, 1) },
    { key: 'current_ir', header: 'Current IR (A)', render: (r: CustomTypes.MeterReading) => formatNumber(r.current_ir, 3) },
    { key: 'current_iy', header: 'Current IY (A)', render: (r: CustomTypes.MeterReading) => formatNumber(r.current_iy, 3) },
    { key: 'current_ib', header: 'Current IB (A)', render: (r: CustomTypes.MeterReading) => formatNumber(r.current_ib, 3) },
    { key: 'energy_kvah_import', header: 'Energy Import (kVAh)', render: (r: CustomTypes.MeterReading) => formatNumber(r.energy_kvah_import, 3) },
    { key: 'energy_kwh_export', header: 'Energy Export (kWh)', render: (r: CustomTypes.MeterReading) => formatNumber(r.energy_kwh_export, 3) },
    { key: 'energy_kvah_export', header: 'Energy Export (kVAh)', render: (r: CustomTypes.MeterReading) => formatNumber(r.energy_kvah_export, 3) },
    { key: 'network_info', header: 'Network Info', render: (r: CustomTypes.MeterReading) => r.network_info || 'N/A' },
    { key: 'ingestion_time', header: 'Ingestion Time', render: (r: CustomTypes.MeterReading) => formatTimestamp(r.ingestion_time) },
    { key: 'reading_id', header: 'Reading ID', render: (r: CustomTypes.MeterReading) => r.reading_id ?? 'N/A' },
  ];

  return (
    <div className="table-container">
      <table className="readings-table">
        <thead>
          <tr>
            {columns.map(col => <th key={col.key}>{col.header}</th>)}
          </tr>
        </thead>
        <tbody>
          {readings.map((reading, index) => (
            <tr key={reading.reading_id || index}>
              {columns.map(col => (
                <td key={`${col.key}-${reading.reading_id || index}`} className={typeof (reading as any)[col.key] === 'number' ? 'font-medium' : ''}>
                  {col.render(reading)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ReadingsTable;
