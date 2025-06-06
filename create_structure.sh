#!/bin/bash

# Define the root of your project (current directory)
PROJECT_ROOT=$(pwd)

echo "Creating core project directories..."

# Create db/ and src/
mkdir -p "$PROJECT_ROOT/db"
mkdir -p "$PROJECT_ROOT/src"

echo "Moving scraper.py into src/..."
# Move scraper.py into src/
mv "$PROJECT_ROOT/scraper.py" "$PROJECT_ROOT/src/scraper.py"

echo "Creating __init__.py files for Python packages..."
# Create __init__.py files to make src and models Python packages
touch "$PROJECT_ROOT/src/__init__.py"
mkdir -p "$PROJECT_ROOT/src/models"
touch "$PROJECT_ROOT/src/models/__init__.py"

echo "Creating placeholder files for other src modules and db schema..."
# Create placeholder files for other src modules (empty files for structure)
touch "$PROJECT_ROOT/src/db_manager.py"
touch "$PROJECT_ROOT/src/digital_twin.py"
touch "$PROJECT_ROOT/src/forecasting_engine.py"
touch "$PROJECT_ROOT/src/models/baseline_model.py"
touch "$PROJECT_ROOT/src/models/custom_model_example.py"
touch "$PROJECT_ROOT/src/data_analyzer.py"
touch "$PROJECT_ROOT/src/dashboard.py"
touch "$PROJECT_ROOT/db/schema.sql"

echo "Creating logs/ and debug_dumps/ directories..."
# Create logs and debug_dumps directories
mkdir -p "$PROJECT_ROOT/logs"
mkdir -p "$PROJECT_ROOT/debug_dumps/screenshots"
mkdir -p "$PROJECT_ROOT/debug_dumps/page_sources"

echo "Creating main.py and config.ini placeholders..."
# Create main.py and config.ini
touch "$PROJECT_ROOT/main.py"
touch "$PROJECT_ROOT/config.ini"

echo "Creating README.md placeholder..."
# Create README.md
touch "$PROJECT_ROOT/README.md"

echo "Cleaning up top-level __pycache__ if it exists..."
# Clean up the top-level __pycache__ (it will be recreated in src/__pycache__ when code runs)
rm -rf "$PROJECT_ROOT/__pycache__"

echo "Structure creation complete. Please verify and populate config.ini."
echo "Your data/meter_readings.csv should already be in place."
echo "Remember to update config.ini with your credentials and URLs."