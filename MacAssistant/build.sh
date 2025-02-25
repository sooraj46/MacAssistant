#!/bin/bash

echo "Building MacAssistant for production..."

# Check Node.js installation
if ! command -v node &> /dev/null; then
    echo "Node.js is required but not found. Please install Node.js and try again."
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not found. Please install Python 3 and try again."
    exit 1
fi

# Install frontend dependencies
echo "Installing frontend dependencies..."
cd frontend
npm install

# Build frontend
echo "Building frontend..."
npm run build

# Create static directory in backend if it doesn't exist
echo "Setting up backend to serve the frontend..."
mkdir -p ../backend/static/build
cp -r build/* ../backend/static/build/

# Go back to project root
cd ..

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

echo "Build completed successfully!"
echo "To start the application, run: ./run.sh"