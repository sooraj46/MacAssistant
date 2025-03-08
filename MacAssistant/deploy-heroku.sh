#!/bin/bash

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "Heroku CLI is required but not found. Please install it using: brew install heroku"
    exit 1
fi

# Check if logged in to Heroku
heroku auth:whoami > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "You need to login to Heroku first. Running: heroku login"
    heroku login
fi

# Ask for app name
read -p "Enter a name for your Heroku app (e.g., my-macassistant): " APP_NAME

# Create Heroku app
echo "Creating Heroku app: $APP_NAME"
heroku create $APP_NAME

# Add buildpacks
echo "Adding buildpacks..."
heroku buildpacks:add heroku/python --app $APP_NAME

# Set environment variables
echo "Setting environment variables..."
heroku config:set FLASK_ENV=production --app $APP_NAME
heroku config:set SECRET_KEY=$(openssl rand -hex 32) --app $APP_NAME
heroku config:set LOG_DIR=logs --app $APP_NAME
heroku config:set LOG_LEVEL=INFO --app $APP_NAME
heroku config:set MAX_EXECUTION_TIME=300 --app $APP_NAME

# Prompt for Google API key
read -p "Enter your Google API key: " GOOGLE_API_KEY
heroku config:set GOOGLE_API_KEY=$GOOGLE_API_KEY --app $APP_NAME
heroku config:set GEMINI_MODEL=gemini-2.0-flash-thinking-exp-01-21 --app $APP_NAME

# Deploy to Heroku
echo "Deploying to Heroku..."
git subtree push --prefix MacAssistant heroku main

# Open the app
echo "Opening your deployed app..."
heroku open --app $APP_NAME

echo "Deployment complete! Your app is running at: https://$APP_NAME.herokuapp.com"
echo "To view logs, run: heroku logs --tail --app $APP_NAME"