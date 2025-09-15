"""
Development configuration for the API service.
"""

import os
from typing import Dict


class DevConfig:
    """Development configuration settings."""

    # API Configuration
    API_HOST = "0.0.0.0"
    API_PORT = 8000
    API_RELOAD = True
    API_LOG_LEVEL = "info"

    # Security
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_ME_IN_PRODUCTION")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24

    # CORS
    CORS_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # RabbitMQ
    RABBITMQ_URL = "amqp://rabbitmq:rabbitmq@localhost:5672/"
    RABBITMQ_EXCHANGE = "codetrekking"
    RABBITMQ_QUEUE_PREFIX = "dev"

    # Elasticsearch
    ELASTICSEARCH_HOST = "http://elasticsearch:9200"
    ELASTICSEARCH_INDEX_PREFIX = "dev-codetrekking"

    # Database
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/codetrekking_dev"

    # Rate Limiting
    DEFAULT_RATE_LIMIT = "100/minute"
    AUTH_RATE_LIMIT = "10/minute"

    # File Storage
    MAX_FILE_SIZE_MB = 50
    UPLOAD_DIRECTORY = "/tmp/uploads"

    # Logging
    LOG_LEVEL = "DEBUG"
    LOG_FORMAT = "json"
    AUDIT_LOG_ENABLED = True

    @classmethod
    def get_env_vars(cls) -> Dict[str, str]:
        """Get environment variables for development."""
        return {
            "ENVIRONMENT": "development",
            "API_HOST": cls.API_HOST,
            "API_PORT": str(cls.API_PORT),
            "JWT_SECRET_KEY": cls.JWT_SECRET_KEY,
            "JWT_ALGORITHM": cls.JWT_ALGORITHM,
            "JWT_EXPIRATION_HOURS": str(cls.JWT_EXPIRATION_HOURS),
            "CORS_ORIGINS": ",".join(cls.CORS_ORIGINS),
            "RABBITMQ_URL": cls.RABBITMQ_URL,
            "RABBITMQ_EXCHANGE": cls.RABBITMQ_EXCHANGE,
            "RABBITMQ_QUEUE_PREFIX": cls.RABBITMQ_QUEUE_PREFIX,
            "ELASTICSEARCH_HOST": cls.ELASTICSEARCH_HOST,
            "ELASTICSEARCH_INDEX_PREFIX": cls.ELASTICSEARCH_INDEX_PREFIX,
            "DATABASE_URL": cls.DATABASE_URL,
            "DEFAULT_RATE_LIMIT": cls.DEFAULT_RATE_LIMIT,
            "AUTH_RATE_LIMIT": cls.AUTH_RATE_LIMIT,
            "MAX_FILE_SIZE_MB": str(cls.MAX_FILE_SIZE_MB),
            "UPLOAD_DIRECTORY": cls.UPLOAD_DIRECTORY,
            "LOG_LEVEL": cls.LOG_LEVEL,
            "LOG_FORMAT": cls.LOG_FORMAT,
            "AUDIT_LOG_ENABLED": str(cls.AUDIT_LOG_ENABLED),
        }


def setup_dev_environment():
    """Setup development environment variables."""
    env_vars = DevConfig.get_env_vars()

    for key, value in env_vars.items():
        os.environ.setdefault(key, value)

    print("Development environment configured:")
    for key, value in env_vars.items():
        if "SECRET" in key or "PASSWORD" in key:
            print(f"  {key}=***")
        else:
            print(f"  {key}={value}")


if __name__ == "__main__":
    setup_dev_environment()

    # Import and run the FastAPI application
    import uvicorn
    from .main import app

    print("\nStarting CodeTrekking API Service in development mode...")
    print(f"API Documentation: http://{DevConfig.API_HOST}:{DevConfig.API_PORT}/docs")
    print(f"API Status: http://{DevConfig.API_HOST}:{DevConfig.API_PORT}/api/v1/status")

    uvicorn.run(
        app,
        host=DevConfig.API_HOST,
        port=DevConfig.API_PORT,
        reload=DevConfig.API_RELOAD,
        log_level=DevConfig.API_LOG_LEVEL,
        access_log=True,
    )
