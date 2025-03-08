#!/bin/bash

# Check if Python is installed
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

# Install backend requirements
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit the .env file to add your API keys and configuration."
fi

# Create logs directory
mkdir -p logs

# Start backend
echo "Starting MacAssistant in development mode..."
echo "Application will be available at http://localhost:5000"
echo "Press Ctrl+C to stop the server"

# Start the server
cd backend && python app.py