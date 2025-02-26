#!/bin/bash

set -e  # Exit on error

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3 and try again."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing dependencies..."
pip install -r backend/requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit the .env file to add your API keys and configuration before running again."
    exit 1
fi

# Create logs directory
mkdir -p logs

# Determine environment
ENV=${FLASK_ENV:-development}

# Run the application
echo "Starting MacAssistant in $ENV mode..."
cd backend

if [ "$ENV" = "production" ]; then
    # Run with gunicorn in production
    echo "Using production server (gunicorn)..."
    gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app
else
    # Run with Flask development server
    echo "Using development server (Flask)..."
    python app.py
fi