FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy PeakFlow dependency to /app/peakflow
COPY application/peakflow /app/peakflow

# Copy PeakFlow Tasks to /app/peakflow-tasks  
COPY application/peakflow-tasks /app/peakflow-tasks

# Set working directory to peakflow-tasks
WORKDIR /app/peakflow-tasks

# Install dependencies with uv (peakflow path is now ../peakflow which matches the original)
RUN uv sync --frozen

# Create storage directories
RUN mkdir -p /storage/garmin /storage/processed-data

# Set environment variables
ENV PYTHONPATH=/app/peakflow-tasks
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD uv run celery -A peakflow_tasks.celery_app inspect ping || exit 1

# Default command (can be overridden)
CMD ["uv", "run", "celery", "-A", "peakflow_tasks.celery_app", "worker", "--loglevel=info"]
