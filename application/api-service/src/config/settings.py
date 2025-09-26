"""
Application settings and configuration for the API service.
"""

from functools import lru_cache
from typing import List
from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import ConfigDict, Field


class AppSettings(BaseSettings):
    """Application configuration settings."""

    # Environment
    environment: str = Field(
        default="development", description="Application environment"
    )

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8002, description="API port")
    api_reload: bool = Field(default=True, description="Enable API reload")
    api_log_level: str = Field(default="info", description="API log level")

    # Security
    jwt_secret_key: str = Field(
        default="CHANGE_ME_IN_PRODUCTION",
        description="JWT secret key - must be set via environment variable",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration in hours")

    # CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8080,http://127.0.0.1:3000,http://127.0.0.1:8080",
        description="CORS allowed origins (comma-separated)",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # File Storage Paths - using same structure as PeakFlow
    garmin_base_dir: str = Field(
        default="/home/aiuser/codetrekking/storage/garmin",
        alias="GARMIN_STORAGE",
        description="Base directory for Garmin data storage",
    )

    upload_directory: str = Field(
        default="/tmp/uploads", description="Directory for uploaded files"
    )

    max_file_size_mb: int = Field(default=50, description="Maximum file size in MB")

    # RabbitMQ
    rabbitmq_url: str = Field(
        default="amqp://codetrekking:ChangeMe@localhost:5672/",
        description="RabbitMQ connection URL",
    )
    rabbitmq_exchange: str = Field(
        default="codetrekking", description="RabbitMQ exchange name"
    )
    rabbitmq_queue_prefix: str = Field(
        default="api", description="RabbitMQ queue prefix"
    )

    # Elasticsearch
    elasticsearch_host: str = Field(
        default="http://localhost:9200", description="Elasticsearch host URL"
    )
    elasticsearch_user: str = Field(
        default="elastic", alias="ELASTIC_USER", description="Elasticsearch username"
    )
    elasticsearch_password: str = Field(
        default="", alias="ELASTIC_PASSWORD", description="Elasticsearch password"
    )
    elasticsearch_index_prefix: str = Field(
        default="codetrekking", description="Elasticsearch index prefix"
    )

    # Rate Limiting
    default_rate_limit: str = Field(
        default="100/minute", description="Default rate limit"
    )
    auth_rate_limit: str = Field(
        default="10/minute", description="Authentication rate limit"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Application log level")
    log_format: str = Field(default="json", description="Log format")
    audit_log_enabled: bool = Field(default=True, description="Enable audit logging")

    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    def get_fit_file_path(
        self, user_id: str, activity_id: str, file_type: str = "fit"
    ) -> str:
        """
        Generate standardized fit file path under Garmin config directory structure.

        Args:
            user_id: User identifier
            activity_id: Activity identifier
            file_type: File type (fit, json, etc.)

        Returns:
            Full path to the file
        """
        if file_type.lower() == "fit":
            filename = f"{activity_id}_ACTIVITY.fit"
            subdir = "activities"
        elif file_type.lower() == "json":
            filename = f"activity_{activity_id}.json"
            subdir = "activities"
        else:
            filename = f"{activity_id}.{file_type}"
            subdir = "data"

        return str(
            Path(self.garmin_base_dir) / user_id / "downloads" / subdir / filename
        )

    def get_user_garmin_directory(self, user_id: str) -> str:
        """
        Get user's Garmin data directory path.

        Args:
            user_id: User identifier

        Returns:
            Path to user's Garmin directory
        """
        return str(Path(self.garmin_base_dir) / user_id)

    def get_user_downloads_directory(self, user_id: str) -> str:
        """
        Get user's downloads directory path.

        Args:
            user_id: User identifier

        Returns:
            Path to user's downloads directory
        """
        return str(Path(self.garmin_base_dir) / user_id / "downloads")


@lru_cache()
def get_app_settings() -> AppSettings:
    """Get cached application settings."""
    return AppSettings()


# Convenience function for getting settings
def get_settings() -> AppSettings:
    """Get application settings."""
    return get_app_settings()
