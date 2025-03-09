# Deployment Options for MacAssistant

## 1. Local Deployment

The simplest deployment is running MacAssistant locally on your Mac.

### Steps:

1. Build the application:
   ```bash
   cd /path/to/MacAssistant
   ./build.sh
   ```

2. Create a `.env` file with your Google API key:
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   GOOGLE_API_KEY=your-google-api-key-here
   GEMINI_MODEL=gemini-2.0-flash-thinking-exp-01-21
   LOG_DIR=logs
   LOG_LEVEL=INFO
   MAX_EXECUTION_TIME=300
   HUMAN_VALIDATION_REQUIRED=True
   LLM_VERIFY_RESULTS=True
   ```

3. Run the application:
   ```bash
   ./run.sh
   ```

4. Access the application at `http://localhost:5000`

## 2. Docker Deployment

Using Docker provides better isolation and makes it easier to deploy on different machines.

### Steps:

1. Create a `.env` file with your Google API key as shown above

2. Run the Docker deployment script:
   ```bash
   ./deploy-docker.sh
   ```

3. Access the application at `http://localhost:5000`

## 3. Heroku Deployment

Heroku offers simple cloud deployment.

### Steps:

1. Run the Heroku deployment script:
   ```bash
   ./deploy-heroku.sh
   ```

2. Follow the prompts to create your app and enter your Google API key

3. Access your app at the provided Heroku URL

## Configuration Options

### Human-in-the-Loop Settings

MacAssistant now includes enhanced human-in-the-loop features that can be configured through environment variables:

* `HUMAN_VALIDATION_REQUIRED` (True/False):
  - When True, the assistant will pause after each step for user feedback
  - When False, the assistant will continue automatically, but still pause on errors

* `LLM_VERIFY_RESULTS` (True/False):
  - When True, the LLM will analyze each command's output to verify success
  - When False, success is determined solely by the command's return code

### Setting Environment Variables

#### Local
Edit the `.env` file in your project root

#### Docker
Edit the `.env` file, or adjust settings in `docker-compose.yml`

#### Heroku
Set environment variables using the Heroku CLI:
```bash
heroku config:set HUMAN_VALIDATION_REQUIRED=True --app your-app-name
heroku config:set LLM_VERIFY_RESULTS=True --app your-app-name
```

## Security Considerations

1. Never commit API keys or sensitive information to the repository
2. Use environment variables for configuration
3. Use HTTPS in production environments
4. Consider implementing user authentication
5. Be cautious with command execution permissions in shared environments
6. Regularly update dependencies to address security vulnerabilities

## Production Considerations

1. MacAssistant now uses Gunicorn with eventlet worker for production
2. Set up proper logging and monitoring
3. Implement error tracking
4. Configure proper SSL/TLS certificates
5. Implement rate limiting to protect against abuse

## Troubleshooting

### Common Issues

1. **Missing Dependencies**: If you encounter errors about missing dependencies, make sure you've run the build script and installed all required packages.

2. **API Key Issues**: Verify that your Google API key is correctly set in your environment variables. Make sure it has access to the Gemini API.

3. **Permission Errors**: Make sure your application has permission to write to the logs directory.

4. **Docker Issues**: If using Docker, make sure Docker is running and you have the necessary permissions.

### Getting Help

If you encounter issues not covered in this guide, check the project's GitHub repository for known issues, or open a new issue with details about your problem.