# Simple Dockerfile for chatmock-prod
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy the chatmock package and required files
COPY chatmock ./chatmock
COPY pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir flask requests

# Set environment
ENV PYTHONUNBUFFERED=1
ENV CHATGPT_LOCAL_HOME=/app/data

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run
CMD ["python", "-m", "chatmock", "serve", "--host", "0.0.0.0", "--port", "8080"]