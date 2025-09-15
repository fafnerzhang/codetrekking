"""
Basic functionality tests that don't require complex mocking.
"""

import pytest
from unittest.mock import Mock
from peakflow_tasks.config import get_settings
from peakflow_tasks.celery_app import celery_app
from peakflow_tasks.exceptions import ValidationError, ConfigurationError
from peakflow_tasks.utils.validation import validate_user_id, validate_date_string
from peakflow_tasks.utils.logging import setup_logging
from peakflow_tasks.utils.monitoring import setup_monitoring


class TestBasicFunctionality:
    """Test basic functionality without external dependencies."""
    
    def test_celery_app_initialization(self):
        """Test that Celery app is properly initialized."""
        assert celery_app is not None
        assert celery_app.main == "peakflow_tasks"
        assert hasattr(celery_app.conf, 'broker_url')
        assert hasattr(celery_app.conf, 'task_routes')
    
    def test_settings_loading(self):
        """Test that settings can be loaded."""
        settings = get_settings()
        assert settings is not None
        assert settings.environment is not None
        assert settings.rabbitmq is not None
        assert settings.elasticsearch is not None
    
    def test_validation_functions(self):
        """Test validation functions work correctly."""
        # Valid cases
        assert validate_user_id("test_user") is True
        assert validate_user_id("user123") is True
        
        # Invalid cases
        with pytest.raises(ValidationError):
            validate_user_id("")
        
        with pytest.raises(ValidationError):
            validate_user_id("ab")  # Too short
        
        with pytest.raises(ValidationError):
            validate_user_id("user with spaces")  # Invalid characters
        
        # Date validation
        date_obj = validate_date_string("2024-01-01")
        assert date_obj.year == 2024
        assert date_obj.month == 1
        assert date_obj.day == 1
        
        with pytest.raises(ValidationError):
            validate_date_string("invalid-date")
        
        with pytest.raises(ValidationError):
            validate_date_string("2024-13-01")  # Invalid month
    
    def test_exception_creation(self):
        """Test custom exception creation."""
        error = ConfigurationError("Test error", {"key": "value"})
        assert str(error) == "Test error (details: {'key': 'value'})"
        
        simple_error = ValidationError("Simple error")
        assert str(simple_error) == "Simple error"
    
    def test_logging_setup(self):
        """Test logging setup doesn't raise errors."""
        try:
            setup_logging()
            assert True  # If we get here, setup succeeded
        except Exception as e:
            pytest.fail(f"Logging setup failed: {e}")
    
    def test_monitoring_setup(self):
        """Test monitoring setup doesn't raise errors."""
        try:
            setup_monitoring()
            assert True  # If we get here, setup succeeded
        except Exception as e:
            pytest.fail(f"Monitoring setup failed: {e}")


class TestConfigurationIntegration:
    """Test configuration integration."""
    
    def test_celery_config_generation(self):
        """Test Celery configuration generation."""
        settings = get_settings()
        celery_config = settings.get_celery_config()
        
        # Check required fields
        required_fields = [
            'broker_url', 'result_backend', 'task_serializer',
            'task_routes', 'include'
        ]
        
        for field in required_fields:
            assert field in celery_config, f"Missing field: {field}"
        
        # Check task routes
        assert len(celery_config['task_routes']) > 0
        assert 'peakflow_tasks.tasks.garmin.*' in celery_config['task_routes']
        
        # Check includes
        assert len(celery_config['include']) > 0
        assert 'peakflow_tasks.tasks.garmin' in celery_config['include']
    
    def test_elasticsearch_config(self):
        """Test Elasticsearch configuration."""
        settings = get_settings()
        es_config = settings.elasticsearch.to_dict()
        
        assert 'hosts' in es_config
        assert 'http_auth' in es_config
        assert isinstance(es_config['hosts'], list)
        assert len(es_config['hosts']) > 0
    
    def test_rabbitmq_broker_url(self):
        """Test RabbitMQ broker URL generation."""
        settings = get_settings()
        broker_url = settings.rabbitmq.broker_url
        
        assert broker_url.startswith('pyamqp://')
        assert 'localhost' in broker_url or settings.rabbitmq.host in broker_url
        assert str(settings.rabbitmq.port) in broker_url