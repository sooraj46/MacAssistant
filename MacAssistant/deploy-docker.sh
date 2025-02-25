#!/bin/bash

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is required but not found. Please install Docker and try again."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "Please edit the .env file to add your API keys and configuration."
    exit 1
fi

# Build and start Docker container
echo "Building and starting MacAssistant in Docker..."
docker-compose up -d --build

echo "MacAssistant is now running in Docker!"
echo "You can access it at: http://localhost:5000"
echo ""
echo "To view logs, run: docker-compose logs -f"
echo "To stop the container, run: docker-compose down"