FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install peakflow package first
COPY peakflow/ ./peakflow/
RUN cd peakflow && pip install .

# Copy dependency files (excluding peakflow from dependencies)
COPY api-service/pyproject.toml api-service/README.md ./

# Create a version of pyproject.toml without local peakflow dependency for Docker
RUN sed '/peakflow/d' pyproject.toml > pyproject.docker.toml && mv pyproject.docker.toml pyproject.toml

# Install dependencies with uv
RUN uv sync --no-dev

# Copy application code
COPY api-service/src/ ./src/
COPY api-service/main.py ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash apiuser
RUN chown -R apiuser:apiuser /app
USER apiuser

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Run the application
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
