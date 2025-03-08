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
   ```

3. Run the application:
   ```bash
   ./run.sh
   ```

4. Access the application at `http://localhost:5000`

## 2. Docker Deployment

Using Docker provides better isolation and makes it easier to deploy on different machines.

### Steps:

1. Create a Dockerfile in the project root:

```dockerfile
FROM python:3.9-slim
WORKDIR /app

# Install dependencies
COPY MacAssistant/backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY MacAssistant/backend /app/

# Create logs directory
RUN mkdir -p logs

# Set environment variables
ENV FLASK_ENV=production
ENV SECRET_KEY=change-this-in-production
ENV LOG_DIR=logs
ENV LOG_LEVEL=INFO
ENV MAX_EXECUTION_TIME=300

# Expose port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
```

2. Build the Docker image:
   ```bash
   docker build -t macassistant .
   ```

3. Run the Docker container:
   ```bash
   docker run -p 5000:5000 --env-file .env macassistant
   ```

4. Access the application at `http://localhost:5000`

## 3. Heroku Deployment

Heroku offers simple cloud deployment.

### Steps:

1. Install the Heroku CLI and login:
   ```bash
   brew install heroku
   heroku login
   ```

2. Create a new Heroku app:
   ```bash
   heroku create macassistant
   ```

3. Create a Procfile in the project root:
   ```
   web: cd MacAssistant/backend && python app.py
   ```

4. Add a runtime.txt file:
   ```
   python-3.9.13
   ```

5. Set environment variables:
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY=your-secret-key-here
   heroku config:set GOOGLE_API_KEY=your-google-api-key-here
   heroku config:set GEMINI_MODEL=gemini-2.0-flash-thinking-exp-01-21
   heroku config:set LOG_DIR=logs
   heroku config:set LOG_LEVEL=INFO
   heroku config:set MAX_EXECUTION_TIME=300
   ```

6. Deploy to Heroku:
   ```bash
   git push heroku main
   ```

7. Open the application:
   ```bash
   heroku open
   ```

## 4. AWS Elastic Beanstalk Deployment

AWS Elastic Beanstalk provides a managed platform for running web applications.

### Steps:

1. Install the AWS CLI and EB CLI:
   ```bash
   pip install awscli awsebcli
   ```

2. Configure AWS credentials:
   ```bash
   aws configure
   ```

3. Initialize EB application:
   ```bash
   eb init -p python-3.9 macassistant
   ```

4. Create an application.py file in the MacAssistant/backend directory:
   ```python
   from app import app as application
   
   if __name__ == "__main__":
       application.run()
   ```

5. Make sure the backend/requirements.txt file includes all dependencies.

6. Create a .ebextensions/01_flask.config file:
   ```yaml
   option_settings:
     aws:elasticbeanstalk:container:python:
       WSGIPath: MacAssistant/backend/application.py
     aws:elasticbeanstalk:application:environment:
       FLASK_ENV: production
       SECRET_KEY: your-secret-key-here
       GOOGLE_API_KEY: your-google-api-key-here
       GEMINI_MODEL: gemini-2.0-flash-thinking-exp-01-21
       LOG_DIR: logs
       LOG_LEVEL: INFO
       MAX_EXECUTION_TIME: 300
   ```

7. Create an environment and deploy:
   ```bash
   eb create macassistant-env
   ```

8. Open the application:
   ```bash
   eb open
   ```

## Project Structure

```
MacAssistant/
├── backend/                  # Flask backend server
│   ├── app.py                # Main application entry point
│   ├── config.py             # Configuration handling
│   ├── modules/              # Backend modules
│   │   ├── agent_orchestrator.py
│   │   ├── command_generator.py
│   │   ├── execution_engine.py
│   │   ├── llm_integration.py
│   │   ├── logger.py
│   │   └── safety_checker.py
│   ├── static/               # Static files (CSS, JavaScript)
│   ├── templates/            # HTML templates
│   └── requirements.txt      # Python dependencies
├── build.sh                  # Production build script
├── run.sh                    # Production run script
├── start-dev.sh              # Development mode script
└── .env.example              # Example environment variables
```

## Important Security Considerations

For any deployment option:

1. Never commit API keys or sensitive information to the repository
2. Use environment variables for configuration
3. Use HTTPS in production environments
4. Consider implementing user authentication
5. Be cautious with command execution permissions in shared environments
6. Regularly update dependencies to address security vulnerabilities

## Production Considerations

1. Use a production-ready WSGI server like Gunicorn or uWSGI instead of Flask's built-in server
2. Set up proper logging and monitoring
3. Implement error tracking
4. Configure proper SSL/TLS certificates
5. Implement rate limiting to protect against abuse