# CodeTrekking API Service

FastAPI-based REST API service for the CodeTrekking fitness data pipeline with RabbitMQ integration.

## Features

- RESTful API endpoints for fitness data pipeline operations
- RabbitMQ message publishing for task distribution
- JWT authentication and authorization
- Rate limiting and request validation
- Health checks and monitoring endpoints

## Development

```bash
# Quick start with development script
./dev_start.sh

# Manual setup:
# Install dependencies
uv sync --dev

# Load environment variables
source .env.dev

# Run the service
uv run python main.py

# Alternative: Run with uvicorn directly
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8002

# Run tests
uv run pytest

# Format code
uv run black src/
uv run ruff check src/
```

## Service URLs

When running in development mode:
- **API Service**: http://localhost:8002
- **API Documentation**: http://localhost:8002/docs
- **API Status**: http://localhost:8002/api/v1/status
- **Health Check**: http://localhost:8002/health

## Docker

```bash
# Build image
docker build -f ../../docker/dockerfile/api-service.Dockerfile -t api-service .

# Run container
docker run -p 8002:8002 api-service
```

## Environment Variables

- `API_HOST`: API server host (default: 0.0.0.0)
- `API_PORT`: API server port (default: 8002)
- `ENVIRONMENT`: Environment mode (development/production)
- `RABBITMQ_HOST`: RabbitMQ server hostname
- `RABBITMQ_PORT`: RabbitMQ server port
- `RABBITMQ_USER`: RabbitMQ username
- `RABBITMQ_PASS`: RabbitMQ password
- `RABBITMQ_VHOST`: RabbitMQ virtual host
- `ELASTICSEARCH_HOST`: Elasticsearch server URL
- `JWT_SECRET_KEY`: JWT signing secret key
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)
- `CORS_ORIGINS`: Allowed CORS origins
