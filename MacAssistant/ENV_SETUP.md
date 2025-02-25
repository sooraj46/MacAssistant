# Environment Setup for MacAssistant

MacAssistant uses environment variables to configure various aspects of the application. These variables are loaded from a `.env` file in the project root directory.

## Setting Up Your .env File

1. If you don't have a `.env` file yet, copy the example file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and fill in your specific values:
   ```bash
   # Use your preferred text editor
   nano .env
   ```

3. Verify your environment variables are loaded correctly:
   ```bash
   python3 check-env.py
   ```

## Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| FLASK_ENV | Environment mode (development, production) | development |
| SECRET_KEY | Secret key for session security | (random string) |
| GOOGLE_API_KEY | Google API key for Gemini LLM | (must be provided) |
| GEMINI_MODEL | Gemini model to use | gemini-2.0-flash-thinking-exp-01-21 |
| LOG_DIR | Directory for logs | logs |
| LOG_LEVEL | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| MAX_EXECUTION_TIME | Maximum execution time for commands (seconds) | 300 |

## Getting a Google Gemini API Key

1. Go to the [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create or sign in to your Google account
3. Click "Create API Key"
4. Copy the API key and paste it in your `.env` file for the `GOOGLE_API_KEY` variable

## Environment Variable Inheritance

When you run MacAssistant using the provided scripts:

- `run.sh` - The environment variables from your `.env` file are automatically loaded
- `deploy-docker.sh` - The environment variables are passed to the Docker container
- `deploy-heroku.sh` - The environment variables are set in your Heroku app configuration

## Testing Your Configuration

You can test that your environment variables are correctly loaded using the provided check-env.py script:

```bash
python3 check-env.py
```

This will display all your environment variables (with sensitive values masked) and confirm if they are properly set.