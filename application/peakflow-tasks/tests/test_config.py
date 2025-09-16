"""
Tests for configuration management.
"""

import pytest
import os
from unittest.mock import patch

from peakflow_tasks.config import (
    RabbitMQConfig,
    ElasticsearchConfig,
    PeakFlowConfig,
    CeleryConfig,
    Settings,
    get_settings,
)


class TestRabbitMQConfig:
    """Test RabbitMQ configuration."""
    
    def test_default_config(self, env_rabbitmq_host, env_rabbitmq_port, env_rabbitmq_user, env_rabbitmq_password, env_rabbitmq_vhost):
        """Test default configuration values."""
        config = RabbitMQConfig()
        
        assert config.host == env_rabbitmq_host
        assert config.port == env_rabbitmq_port
        assert config.username == env_rabbitmq_user
        assert config.password == env_rabbitmq_password
        assert config.vhost == env_rabbitmq_vhost
    
    def test_broker_url(self, env_rabbitmq_user, env_rabbitmq_password, env_rabbitmq_host, env_rabbitmq_port, env_rabbitmq_vhost):
        """Test broker URL generation."""
        config = RabbitMQConfig()
        # Handle root vhost properly - if vhost is '/', don't double slash
        vhost_part = env_rabbitmq_vhost if env_rabbitmq_vhost != '/' else ''
        expected_url = f"pyamqp://{env_rabbitmq_user}:{env_rabbitmq_password}@{env_rabbitmq_host}:{env_rabbitmq_port}/{vhost_part}"
        assert config.broker_url == expected_url
    
    def test_result_backend(self):
        """Test result backend URL."""
        config = RabbitMQConfig()
        assert config.result_backend == "rpc://"
    
    def test_environment_override(self):
        """Test environment variable override."""
        with patch.dict(os.environ, {
            'RABBITMQ_HOST': 'test-host',
            'RABBITMQ_PORT': '5673',
            'RABBITMQ_DEFAULT_USER': 'test-user',
            'RABBITMQ_DEFAULT_PASS': 'test-pass',
            'RABBITMQ_VHOST': 'test-vhost',
        }):
            config = RabbitMQConfig()
            assert config.host == "test-host"
            assert config.port == 5673
            assert config.username == "test-user"
            assert config.password == "test-pass"
            assert config.vhost == "test-vhost"


class TestElasticsearchConfig:
    """Test Elasticsearch configuration."""
    
    def test_default_config(self, env_elasticsearch_host, env_elasticsearch_user, env_elasticsearch_password):
        """Test default configuration values."""
        config = ElasticsearchConfig()
        
        assert config.host == env_elasticsearch_host
        assert config.username == env_elasticsearch_user
        assert config.password == env_elasticsearch_password
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.retry_on_timeout is True
        assert config.verify_certs is False
    
    def test_hosts_property(self, env_elasticsearch_host):
        """Test hosts property."""
        config = ElasticsearchConfig()
        assert config.hosts == [env_elasticsearch_host]
    
    def test_to_dict(self, env_elasticsearch_host, env_elasticsearch_user, env_elasticsearch_password):
        """Test conversion to dictionary."""
        config = ElasticsearchConfig()
        result = config.to_dict()
        
        expected = {
            'hosts': [env_elasticsearch_host],
            'http_auth': (env_elasticsearch_user, env_elasticsearch_password),
            'timeout': 30,
            'max_retries': 3,
            'retry_on_timeout': True,
            'verify_certs': False,
        }
        
        assert result == expected


class TestPeakFlowConfig:
    """Test PeakFlow configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = PeakFlowConfig()
        
        assert config.garmin_config_dir == "/storage/garmin"
        assert config.garmin_data_dir == "/storage/garmin"
    
    def test_path_properties(self):
        """Test path properties."""
        config = PeakFlowConfig()
        
        assert str(config.garmin_config_path) == "/storage/garmin"
        assert str(config.garmin_data_path) == "/storage/garmin"


class TestCeleryConfig:
    """Test Celery configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = CeleryConfig()
        
        assert config.task_serializer == "json"
        assert config.result_serializer == "json"
        assert config.accept_content == ["json"]
        assert config.timezone == "UTC"
        assert config.enable_utc is True
        assert config.task_always_eager is False
        assert config.worker_concurrency == 4
    
    def test_task_routes(self):
        """Test task routes configuration."""
        config = CeleryConfig()
        
        assert "peakflow_tasks.tasks.garmin.*" in config.task_routes
        assert config.task_routes["peakflow_tasks.tasks.garmin.*"]["queue"] == "garmin"
    
    def test_task_annotations(self):
        """Test task annotations configuration."""
        config = CeleryConfig()
        
        assert "peakflow_tasks.tasks.garmin.download_garmin_daily_data" in config.task_annotations
        garmin_config = config.task_annotations["peakflow_tasks.tasks.garmin.download_garmin_daily_data"]
        assert garmin_config["time_limit"] == 1800
        assert garmin_config["max_retries"] == 3


class TestSettings:
    """Test main settings."""
    
    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        
        assert settings.environment == "development"
        assert settings.debug is False
        assert isinstance(settings.rabbitmq, RabbitMQConfig)
        assert isinstance(settings.elasticsearch, ElasticsearchConfig)
        assert isinstance(settings.peakflow, PeakFlowConfig)
        assert isinstance(settings.celery, CeleryConfig)
    
    def test_get_celery_config(self):
        """Test Celery configuration generation."""
        settings = Settings()
        config = settings.get_celery_config()
        
        # Check required fields
        assert "broker_url" in config
        assert "result_backend" in config
        assert "task_serializer" in config
        assert "task_routes" in config
        assert "include" in config
        
        # Check include modules
        expected_modules = [
            "peakflow_tasks.tasks.garmin",
            "peakflow_tasks.tasks.processing", 
            "peakflow_tasks.tasks.storage",
            "peakflow_tasks.tasks.workflows",
        ]
        assert config["include"] == expected_modules
    
    def test_get_settings_function(self):
        """Test get_settings function."""
        settings = get_settings()
        assert isinstance(settings, Settings)