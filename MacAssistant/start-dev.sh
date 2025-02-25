#!/bin/bash

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "Node.js is required but not found. Please install Node.js and try again."
    exit 1
fi

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

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install
cd ..

# Create logs directory
mkdir -p logs

# Start backend and frontend in parallel
echo "Starting MacAssistant in development mode..."
echo "Backend will be available at http://localhost:5000"
echo "Frontend will be available at http://localhost:3000"
echo "Press Ctrl+C to stop both servers"

# Start both servers
(cd backend && python app.py) & 
(cd frontend && npm start) &

# Wait for any process to exit
wait