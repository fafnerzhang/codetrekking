#!/bin/bash

# Development startup script for CodeTrekking API Service
# This script sets up the development environment and starts the API service

set -e

echo "🚀 Starting CodeTrekking API Service - Development Mode"
echo "=================================================="

# Set working directory
cd "$(dirname "$0")"
API_SERVICE_DIR="$(pwd)"
echo "📁 Working directory: $API_SERVICE_DIR"

# Load environment variables from .env.dev
if [[ -f ".env.dev" ]]; then
    echo "🔧 Loading environment variables from .env.dev..."
    source .env.dev
    echo "✅ Environment variables loaded"
else
    echo "⚠️  Warning: .env.dev file not found, using defaults"
fi

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv package manager is not installed"
    echo "Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "✅ uv package manager found"

# Check if pyproject.toml exists
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found in $API_SERVICE_DIR"
    echo "Please run this script from the api-service directory"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies with uv..."
uv sync --dev

# Install peakflow in development mode
if [[ -d "../peakflow" ]]; then
    echo "📦 Installing peakflow in development mode..."
    uv pip install -e "../peakflow"
else
    echo "⚠️  Warning: PeakFlow directory not found at ../peakflow"
fi

echo "🔧 Environment configured for development"

# Create upload directory if it doesn't exist
mkdir -p /tmp/uploads
echo "📁 Upload directory ready: /tmp/uploads"

# Check if external services are running (optional)
echo "🔍 Checking external services..."

# Check RabbitMQ
if curl -s -f http://localhost:15672 > /dev/null 2>&1; then
    echo "✅ RabbitMQ Management UI is accessible"
else
    echo "⚠️  Warning: RabbitMQ Management UI not accessible at http://localhost:15672"
    echo "   Make sure RabbitMQ is running: docker-compose -f docker/compose/rabbitmq.yml up -d"
fi

# Check Elasticsearch
if curl -s -f http://localhost:9200 > /dev/null 2>&1; then
    echo "✅ Elasticsearch is accessible"
else
    echo "⚠️  Warning: Elasticsearch not accessible at http://localhost:9200"
    echo "   Make sure Elasticsearch is running: docker-compose -f docker/compose/elk.yml up -d"
fi

echo ""
echo "🎯 Starting API Service..."
echo "📖 API Documentation: http://localhost:${API_PORT:-8000}/docs"
echo "🔍 API Status: http://localhost:${API_PORT:-8000}/api/v1/status"
echo "❤️  Health Check: http://localhost:${API_PORT:-8000}/health"
echo "🏠 Root Endpoint: http://localhost:${API_PORT:-8000}/"
echo ""
echo "Press Ctrl+C to stop the service"
echo ""

# Start the FastAPI application with uv
echo "🚀 Starting FastAPI application..."
uv run python -m uvicorn src.main:app --host 0.0.0.0 --port ${API_PORT:-8000} --reload
