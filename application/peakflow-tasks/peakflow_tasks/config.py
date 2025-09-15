"""
Configuration management for PeakFlow Tasks.

This module provides centralized configuration management using environment variables
and default values. Configuration is loaded from environment variables with
fallbacks to sensible defaults for development.
"""

import os
from typing import Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the peakflow-tasks directory
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
load_dotenv(env_file)

# Also try to load from the current working directory (for when run from api-service)
load_dotenv()


class RabbitMQConfig(BaseSettings):
    """RabbitMQ connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    host: str = Field(default="localhost", alias="RABBITMQ_HOST")
    port: int = Field(default=5672, alias="RABBITMQ_PORT")
    username: str = Field(default="admin", alias="RABBITMQ_DEFAULT_USER")
    password: str = Field(default="ChangeMe", alias="RABBITMQ_DEFAULT_PASS")
    vhost: str = Field(default="/", alias="RABBITMQ_VHOST")
    
    @property
    def broker_url(self) -> str:
        """Get the complete broker URL for Celery."""
        # Handle root vhost properly - if vhost is '/', don't double slash
        vhost_part = self.vhost if self.vhost != '/' else ''
        return f"pyamqp://{self.username}:{self.password}@{self.host}:{self.port}/{vhost_part}"
    
    @property
    def result_backend(self) -> str:
        """Get the result backend URL."""
        return "rpc://"


class ElasticsearchConfig(BaseSettings):
    """Elasticsearch connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    host: str = Field(default="http://localhost:9200", alias="ELASTICSEARCH_HOST")
    username: str = Field(default="elastic", alias="ELASTICSEARCH_USER")
    password: str = Field(default="ChangeMe", alias="ELASTIC_PASSWORD")
    timeout: int = Field(default=30)
    max_retries: int = Field(default=3)
    retry_on_timeout: bool = Field(default=True)
    verify_certs: bool = Field(default=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            'hosts': [self.host],
            'username': self.username,
            'password': self.password,
            'http_auth': (self.username, self.password),
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'retry_on_timeout': self.retry_on_timeout,
            'verify_certs': self.verify_certs
        }
    
    @property
    def hosts(self) -> list[str]:
        """Get hosts as a list for Elasticsearch client."""
        return [self.host]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Elasticsearch client."""
        return {
            'hosts': self.hosts,
            'http_auth': (self.username, self.password),
            'timeout': self.timeout,
            'max_retries': self.max_retries,
            'retry_on_timeout': self.retry_on_timeout,
            'verify_certs': self.verify_certs,
        }


class DatabaseConfig(BaseSettings):
    """Database connection configuration."""
    
    model_config = SettingsConfigDict(env_prefix="", extra="allow", env_ignore_empty=True)
    
    host: str = Field(default="localhost", alias="POSTGRES_HOST")
    port: int = Field(default=5432, alias="POSTGRES_PORT")
    database: str = Field(default="codetrekking", alias="POSTGRES_DB")
    username: str = Field(default="codetrekking", alias="POSTGRES_USER")
    password: str = Field(default="ChangeMe", alias="POSTGRES_PASSWORD")
    url: Optional[str] = Field(default=None, alias="DATABASE_URL")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary format."""
        return {
            'host': self.host,
            'port': self.port,
            'database': self.database,
            'username': self.username,
            'password': self.password,
            'url': self.url or f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        }


class PeakFlowConfig(BaseSettings):
    """PeakFlow library configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    garmin_config_dir: str = Field(default="/home/aiuser/codetrekking/storage/garmin", alias="GARMIN_CONFIG_DIR")
    garmin_data_dir: str = Field(default="/home/aiuser/codetrekking/storage/garmin", alias="GARMIN_DATA_DIR")
    
    @property
    def garmin_config_path(self) -> Path:
        """Get Garmin configuration directory as Path object."""
        return Path(self.garmin_config_dir)
    
    @property
    def garmin_data_path(self) -> Path:
        """Get Garmin data directory as Path object."""
        return Path(self.garmin_data_dir)


class CeleryConfig(BaseSettings):
    """Celery application configuration."""
    
    model_config = SettingsConfigDict(env_prefix="")
    
    task_serializer: str = Field(default="json")
    result_serializer: str = Field(default="json")
    accept_content: list[str] = Field(default=["json"])
    timezone: str = Field(default="UTC")
    enable_utc: bool = Field(default=True)
    
    # Task configuration
    task_always_eager: bool = Field(default=False, alias="CELERY_TASK_ALWAYS_EAGER")
    task_eager_propagates: bool = Field(default=True)
    task_acks_late: bool = Field(default=True)
    worker_prefetch_multiplier: int = Field(default=1)
    
    # Task time limits
    task_soft_time_limit: int = Field(default=300)  # 5 minutes
    task_time_limit: int = Field(default=600)  # 10 minutes
    
    # Worker configuration
    worker_concurrency: int = Field(default=4, alias="WORKER_CONCURRENCY")
    worker_log_level: str = Field(default="INFO", alias="WORKER_LOG_LEVEL")
    
    # Task routes - define which tasks go to which queues
    task_routes: Dict[str, Dict[str, str]] = Field(default={
        "peakflow_tasks.tasks.garmin.*": {"queue": "garmin"},
        "peakflow_tasks.tasks.processing.*": {"queue": "processing"},
        "peakflow_tasks.tasks.storage.*": {"queue": "storage"},
        "peakflow_tasks.tasks.workflows.*": {"queue": "workflows"},
    })
    
    # Task annotations for specific task configuration
    task_annotations: Dict[str, Dict[str, Any]] = Field(default={
        "peakflow_tasks.tasks.garmin.download_garmin_daily_data": {
            "time_limit": 1800,  # 30 minutes
            "soft_time_limit": 1500,
            "retry_delay": 60,
            "max_retries": 3,
        },
        "peakflow_tasks.tasks.processing.process_fit_file": {
            "time_limit": 300,   # 5 minutes
            "soft_time_limit": 240,
            "retry_delay": 30,
            "max_retries": 2,
        },
    })


class Settings(BaseSettings):
    """Main application settings combining all configuration sections."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore"  # Allow extra fields in env file to be ignored
    )
    
    # Environment
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    
    # Configuration sections
    rabbitmq: RabbitMQConfig = Field(default_factory=RabbitMQConfig)
    elasticsearch: ElasticsearchConfig = Field(default_factory=ElasticsearchConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    peakflow: PeakFlowConfig = Field(default_factory=PeakFlowConfig)
    celery: CeleryConfig = Field(default_factory=CeleryConfig)
        
    def get_celery_config(self) -> Dict[str, Any]:
        """Get complete Celery configuration dictionary."""
        return {
            # Broker settings
            "broker_url": self.rabbitmq.broker_url,
            "result_backend": self.rabbitmq.result_backend,
            
            # Serialization
            "task_serializer": self.celery.task_serializer,
            "result_serializer": self.celery.result_serializer,
            "accept_content": self.celery.accept_content,
            
            # Timezone
            "timezone": self.celery.timezone,
            "enable_utc": self.celery.enable_utc,
            
            # Task configuration
            "task_always_eager": self.celery.task_always_eager,
            "task_eager_propagates": self.celery.task_eager_propagates,
            "task_acks_late": self.celery.task_acks_late,
            "worker_prefetch_multiplier": self.celery.worker_prefetch_multiplier,
            
            # Time limits
            "task_soft_time_limit": self.celery.task_soft_time_limit,
            "task_time_limit": self.celery.task_time_limit,
            
            # Task routing
            "task_routes": self.celery.task_routes,
            "task_annotations": self.celery.task_annotations,
            
            # Result configuration
            "result_expires": 3600,  # 1 hour
            "result_persistent": True,
            
            # Worker configuration
            "worker_send_task_events": True,
            "task_send_sent_event": True,
            
            # Include modules
            "include": [
                "peakflow_tasks.tasks.garmin",
                "peakflow_tasks.tasks.processing", 
                "peakflow_tasks.tasks.storage",
                "peakflow_tasks.tasks.workflows",
            ],
        }


# Global settings instance
settings = Settings()


def get_rabbitmq_config() -> RabbitMQConfig:
    """Get RabbitMQ configuration."""
    return settings.rabbitmq


def get_elasticsearch_config() -> Dict[str, Any]:
    """Get Elasticsearch configuration as dictionary."""
    return settings.elasticsearch.to_dict()


def get_database_config() -> Dict[str, Any]:
    """Get database configuration as dictionary."""
    return settings.database.to_dict()


def get_peakflow_config() -> PeakFlowConfig:
    """Get PeakFlow configuration."""
    return settings.peakflow


def get_celery_config() -> Dict[str, Any]:
    """Get Celery configuration dictionary."""
    return settings.get_celery_config()


def get_settings() -> Settings:
    """Get complete application settings."""
    return settings