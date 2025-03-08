FROM python:3.9-slim
WORKDIR /app

# Install dependencies
COPY backend/requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend /app/

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