// frontend/src/DashboardChart.jsx
// This component renders a single Chart.js line graph.
// It relies on Chart.js and react-chartjs-2 being installed.

import React from 'react';
import { Line } from 'react-chartjs-2';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale // Required for time-series data
} from 'chart.js';
import 'chartjs-adapter-date-fns'; // This import connects Chart.js to date-fns

// Register all necessary Chart.js components once.
// In a typical Vite setup, this registration usually happens in main.jsx or a setup file
// to avoid re-registering on every component render.
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Title,
    Tooltip,
    Legend,
    TimeScale
);

// Note: The Icon component is defined in App.jsx. For this combined immersive,
// it's functionally available. If DashboardChart.jsx was a truly separate file
// you'd typically pass Icon as a prop or define it in a shared utility file.
const Icon = ({ name, size = 24, className = "" }) => {
    const icons = {
        RefreshCcw: "↻",
        Info: "ℹ️",
        Server: "📊",
        TrendingUp: "📈",
        Zap: "⚡",
        Clock: "⏱️",
        Chart: "📈"
    };
    return <span className={`icon ${className}`} style={{ fontSize: `${size}px` }}>{icons[name] || name}</span>;
};


const DashboardChart = ({ title, meterId, historicalData, forecastData, attributeKey, yAxisLabel, lineColor, timeWindowStart, timeWindowEnd, currentTime }) => {
    // Filter historical data for the "past 2 hours" segment
    const realDataPoints = historicalData.filter(d => {
        const ts = new Date(d.timestamp);
        return ts >= timeWindowStart && ts <= currentTime;
    }).map(d => ({
        x: new Date(d.timestamp),
        y: parseFloat(d[attributeKey]) || 0
    }));

    // Filter forecast data for the entire "past 2 hours to future 2 hours" window
    const twinDataPoints = forecastData.filter(d => {
        const ts = new Date(d.timestamp);
        return ts >= timeWindowStart && ts <= timeWindowEnd;
    }).map(d => ({
        x: new Date(d.timestamp),
        y: parseFloat(d.predicted_kwh) || 0
    }));

    const data = {
        datasets: [
            {
                label: 'Actual Readings',
                data: realDataPoints,
                borderColor: lineColor,
                backgroundColor: lineColor + '33',
                borderWidth: 2,
                tension: 0.1,
                fill: false,
                pointRadius: 2,
                pointBackgroundColor: lineColor
            },
            {
                label: 'Digital Twin Prediction',
                data: twinDataPoints,
                borderColor: lineColor,
                backgroundColor: lineColor + '11',
                borderWidth: 2,
                tension: 0.1,
                fill: false,
                borderDash: [5, 5], // Dashed line for prediction
                pointRadius: 2,
                pointBackgroundColor: lineColor
            }
        ]
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: {
                type: 'time', // Essential for time-series data
                time: {
                    unit: 'minute', // Display unit on the axis
                    tooltipFormat: 'yyyy-MM-dd HH:mm', // Format for tooltips
                    displayFormats: {
                        minute: 'HH:mm', // Format for minute ticks
                        hour: 'HH:mm'    // Format for hour ticks
                    }
                },
                title: {
                    display: true,
                    text: 'Time'
                },
                ticks: {
                    autoSkip: true,
                    maxTicksLimit: 10 // Limit number of ticks for readability
                }
            },
            y: {
                beginAtZero: false, // Allow y-axis to not start at zero
                title: {
                    display: true,
                    text: yAxisLabel
                }
            }
        },
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    font: {
                        size: 14
                    }
                }
            },
            tooltip: {
                mode: 'index',
                intersect: false,
                callbacks: {
                    title: function(tooltipItems) {
                        return new Date(tooltipItems[0].parsed.x).toLocaleString();
                    },
                    label: function(tooltipItem) {
                        let label = tooltipItem.dataset.label || '';
                        if (label) {
                            label += ': ';
                        }
                        if (tooltipItem.parsed.y !== null && tooltipItem.parsed.y !== undefined) {
                            label += tooltipItem.parsed.y.toFixed(2);
                        }
                        return label;
                    }
                }
            }
        }
    };

    return (
        <div className="card">
            <h2 className="card-title">
                <Icon name="Chart" />
                <span>{title} for Meter {meterId}</span>
            </h2>
            <div className="chart-container-wrapper">
                <Line data={data} options={options} />
            </div>
            {(realDataPoints.length === 0 && twinDataPoints.length === 0) && (
                <p className="no-data-message">
                    No data available for this chart. Please ensure scraper is running and a simulation has been performed.
                </p>
            )}
        </div>
    );
};

export default DashboardChart;