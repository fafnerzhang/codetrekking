# Monitoring Service Dockerfile
FROM python:3.11-slim

# Create non-root user early
RUN useradd --create-home --shell /bin/bash monitoring

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (keep as root for dependency installation)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code with proper ownership
COPY --chown=monitoring:monitoring . .

# Switch to non-root user (no need for recursive chown on /app)
USER monitoring

# Expose monitoring port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Start monitoring service
CMD ["python", "monitoring.py"]
