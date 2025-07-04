# Digital Twin for Smart Meter Load Forecasting

![Project Banner](https://via.placeholder.com/1200x300.png/0f172a/38bdf8?text=Smart+Meter+Digital+Twin)

This project is a full-stack application that creates a "Digital Twin" of a smart electrical meter. It continuously scrapes real-world energy consumption data, stores it, runs advanced forecasting models, and provides a rich web interface for visualization, analysis, and what-if scenario planning.

The primary goal is to move beyond simple monitoring and enable powerful predictive analytics, allowing users to forecast future energy demand and simulate the impact of real-world events like weather changes or operational shutdowns.

## ✨ Key Features

*   **Automated Data Scraping:** A resilient Selenium-based scraper logs into a web dashboard, navigates its UI, and extracts time-series data for smart meters.
*   **Robust Data Storage:** Scraped data is stored in a PostgreSQL database with a normalized schema, ensuring data integrity and efficient querying.
*   **Pluggable Forecasting Engine:** Features a flexible architecture that allows for easy addition of new forecasting models.
    *   **Baseline Model:** A weather-aware Random Forest model provides a strong, traditional ML benchmark.
    *   **Advanced DL Model:** A pre-trained CNN-LSTM model captures complex temporal patterns.
*   **Event Simulation & Backtesting:** A powerful "what-if" analysis tool allows users to run simulations on historical data with superimposed events (e.g., "Simulate a Heatwave") to see the impact on energy consumption.
*   **Interactive Web Dashboard:** A modern React/TypeScript frontend provides:
    *   Controls for starting/stopping the scraper process.
    *   Visualization of historical vs. forecasted demand.
    *   A live "Grid Status" card with trend analysis for voltage and current.
    *   A dedicated card for running and visualizing event simulation results.

---

## 🏛️ System Architecture

The project is a full-stack application composed of three main services orchestrated to work together: a Python backend, a PostgreSQL database, and a React frontend.

1.  **Backend (`Python/Flask`)**:
    *   **API Server (`main.py`):** A Flask server that exposes a REST API for the frontend. It manages scraper processes and orchestrates simulation runs.
    *   **Web Scraper (`scraper.py`):** A Selenium process that automates data collection.
    *   **Database Manager (`db_manager.py`):** Handles all communication with the PostgreSQL database, including connection pooling and schema management.
    *   **Digital Twin (`digital_twin.py`):** The core orchestrator that fetches data, runs models, and stores results.
    *   **Forecasting Engine (`forecasting_engine.py`):** A model-agnostic engine that dynamically loads and runs forecasting models from the `src/models/` directory.

2.  **Database (`PostgreSQL`)**:
    *   The persistence layer for all application data, including meter metadata, time-series readings, and the results of every simulation run.

3.  **Frontend (`React/TypeScript`)**:
    *   **UI (`digital-twin-ui/`):** A modern, type-safe web application built with Vite, React, and TypeScript.
    *   **API Service (`apiService.ts`):** A dedicated module that encapsulates all `fetch` calls to the backend API.
    *   **Components:** Reusable components for charts (`Recharts`), tables, and user controls.

---

## 🚀 Getting Started

### Prerequisites

*   Python 3.10+
*   Node.js 18+ and npm
*   PostgreSQL Server
*   A web browser (e.g., Google Chrome) for the Selenium scraper

### 1. Backend Setup

First, set up the Python environment and the database.

```bash
# 1. Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Configure the application
#    - Rename config.ini.example to config.ini
#    - Edit config.ini with your database credentials and meter details.
cp config.ini.example config.ini
nano config.ini # Or use your favorite editor

# 5. Set up the PostgreSQL database
#    - Ensure your PostgreSQL server is running.
#    - Create a new database with the name you specified in config.ini.
#    - Run the setup script to create the necessary tables.
python main.py setup-db


### Frontend setup

# 1. Navigate to the UI directory
cd digital-twin-ui

# 2. Install Node.js dependencies
npm install

# 3. Start the frontend development server
npm run dev

### Running the application 
# In the root project directory (where main.py is)
# Make sure your Python virtual environment is activated

# Start the Flask API server
python main.py api-server


### Project Structure 
.
├── digital-twin-ui/     # React/TypeScript Frontend
│   ├── public/
│   └── src/
│       ├── components/  # Reusable React components
│       ├── services/    # API communication layer
│       └── types.ts     # TypeScript type definitions
├── ml_artifacts/        # Pre-trained ML models and scalers
├── src/                 # Python Backend Source Code
│   ├── models/          # Forecasting model implementations
│   │   ├── base_model.py
│   │   ├── baseline_model.py
│   │   └── dl_model.py
│   ├── config_loader.py # Reads from config.ini
│   ├── data_analyzer.py # Business logic for data queries
│   ├── db_manager.py    # PostgreSQL database interactions
│   ├── digital_twin.py  # Simulation orchestration
│   ├── forecasting_engine.py # Model loading and execution
│   └── scraper.py       # Selenium web scraper
├── config.ini           # Application configuration (DB, meters, etc.)
├── main.py              # Main entry point for Flask API and CLI
└── requirements.txt     # Python dependencies