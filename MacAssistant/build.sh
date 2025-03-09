#!/bin/bash

echo "Building MacAssistant for production..."

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

# Install backend requirements
echo "Installing backend dependencies..."
pip install -r backend/requirements.txt

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

# Add the human validation settings to .env.example if it exists
if [ -f ".env.example" ]; then
    echo "Updating .env.example with new configuration settings..."
    if ! grep -q "HUMAN_VALIDATION_REQUIRED" .env.example; then
        echo "" >> .env.example
        echo "# Human validation settings" >> .env.example
        echo "HUMAN_VALIDATION_REQUIRED=True" >> .env.example
        echo "LLM_VERIFY_RESULTS=True" >> .env.example
    fi
fi

# Suggest copying .env.example to .env if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "No .env file found. You may want to create one based on .env.example."
    echo "cp .env.example .env"
fi

echo "Build completed successfully!"
echo "To start the application, run: ./run.sh"