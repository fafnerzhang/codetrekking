"""
Pytest configuration and fixtures for PeakFlow Tasks tests.

This module provides shared fixtures and configuration for testing
PeakFlow Tasks functionality.
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from datetime import datetime, date
import json
from dotenv import load_dotenv

from celery import Celery
from peakflow_tasks.celery_app import create_celery_app
from peakflow_tasks.config import Settings
from peakflow_tasks.utils.monitoring import TaskMonitor

# Load environment variables from .env file at module level
env_file_path = Path(__file__).parent.parent / '.env'
if env_file_path.exists():
    load_dotenv(env_file_path)


@pytest.fixture(scope="session")
def celery_config():
    """Celery configuration for testing."""
    return {
        'broker_url': 'memory://',
        'result_backend': 'cache+memory://',
        'task_always_eager': True,
        'task_eager_propagates': True,
        'task_routes': {},
        'task_annotations': {},
        'include': [],
    }


@pytest.fixture(scope="session")
def celery_app(celery_config):
    """Create Celery app for testing."""
    # Patch the configuration to use test settings
    with patch('peakflow_tasks.celery_app.get_celery_config', return_value=celery_config):
        app = create_celery_app()
        app.config_from_object(celery_config)
        yield app


@pytest.fixture(scope="session")
def celery_worker(celery_app):
    """Create Celery worker for testing."""
    # For in-memory testing, we don't need an actual worker
    # Tasks will be executed synchronously due to task_always_eager=True
    yield None


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_garmin_config(temp_dir):
    """Create sample Garmin configuration for testing."""
    user_id = "test_user"
    config_dir = temp_dir / "garmin" / user_id
    config_dir.mkdir(parents=True)
    
    config_data = {
        "username": "test@example.com",
        "password": "test_password",
        "mfa_enabled": False,
    }
    
    config_file = config_dir / "GarminConnectConfig.json"
    with open(config_file, 'w') as f:
        json.dump(config_data, f)
    
    return {
        "user_id": user_id,
        "config_dir": str(temp_dir / "garmin"),
        "config_file": str(config_file),
        "config_data": config_data,
    }


@pytest.fixture
def sample_fit_file(temp_dir):
    """Create sample FIT file for testing."""
    fit_file = temp_dir / "sample_activity.fit"
    
    # Create a minimal FIT file (just empty for now)
    fit_file.write_bytes(b"FIT_FILE_CONTENT")
    
    return {
        "file_path": str(fit_file),
        "user_id": "test_user",
        "activity_id": "12345678901",
        "file_name": "sample_activity.fit",
    }


@pytest.fixture
def mock_elasticsearch_storage():
    """Mock Elasticsearch storage for testing."""
    mock_storage = Mock()
    mock_storage.initialize.return_value = True
    mock_storage.ping.return_value = True
    mock_storage.index_document.return_value = True
    mock_storage.bulk_index.return_value = Mock(
        success_count=10,
        failed_count=0,
        errors=[]
    )
    mock_storage.search.return_value = []
    mock_storage.close.return_value = None
    
    return mock_storage


@pytest.fixture
def mock_garmin_client():
    """Mock Garmin client for testing."""
    mock_client = Mock()
    mock_client.download_daily_data.return_value = [
        {
            'activity_id': '12345678901',
            'file_path': '/tmp/12345678901_ACTIVITY.fit',
            'file_name': '12345678901_ACTIVITY.fit',
            'file_size': 124567,
            'modified_time': 1704096000.0,
            'download_date': '2024-01-01T07:30:00',
            'output_directory': '/tmp',
        }
    ]
    mock_client.close.return_value = None
    
    return mock_client


@pytest.fixture
def mock_fit_processor():
    """Mock FIT file processor for testing."""
    mock_processor = Mock()
    
    # Mock processing result
    mock_result = Mock()
    mock_result.status.value = "completed"
    mock_result.successful_records = 1500
    mock_result.failed_records = 0
    mock_result.total_records = 1500
    mock_result.processing_time = 45.2
    mock_result.errors = []
    mock_result.warnings = []
    mock_result.metadata = {
        'activity_type': 'running',
        'total_distance': 5000.0,
        'total_time': 1800.0,
    }
    
    mock_processor.process.return_value = mock_result
    mock_processor.get_performance_analytics.return_value = {
        'avg_speed': 2.78,
        'max_speed': 3.5,
        'avg_heart_rate': 145,
        'max_heart_rate': 175,
    }
    
    return mock_processor


@pytest.fixture
def test_settings():
    """Test settings configuration."""
    return Settings(
        environment="test",
        debug=True,
    )


@pytest.fixture
def task_monitor():
    """Task monitor instance for testing."""
    return TaskMonitor(max_history=100)


@pytest.fixture
def sample_task_data():
    """Sample task data for testing."""
    return {
        'garmin_download': {
            'user_id': 'test_user',
            'start_date': '2024-01-01',
            'days': 7,
            'exclude_activity_ids': [],
            'overwrite': False,
        },
        'fit_processing': {
            'file_path': '/tmp/12345678901_ACTIVITY.fit',
            'user_id': 'test_user',
            'activity_id': '12345678901',
            'validate_only': False,
        },
        'analytics': {
            'user_id': 'test_user',
            'start_date': '2024-01-01',
            'end_date': '2024-01-31',
            'metrics': ['total_activities', 'total_distance', 'avg_heart_rate'],
        },
    }


@pytest.fixture(autouse=True)
def cleanup_environment():
    """Clean up environment variables after each test."""
    original_env = os.environ.copy()
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_peakflow_imports():
    """Mock PeakFlow library imports for testing."""
    with patch.dict('sys.modules', {
        'peakflow': Mock(),
        'peakflow.providers': Mock(),
        'peakflow.providers.garmin': Mock(),
        'peakflow.processors': Mock(),
        'peakflow.processors.fit': Mock(),
        'peakflow.storage': Mock(),
        'peakflow.storage.elasticsearch': Mock(),
    }):
        # Mock specific functions and classes
        mock_garmin_provider = Mock()
        mock_garmin_provider.create_garmin_client_from_config.return_value = Mock()
        
        mock_fit_processor = Mock()
        mock_fit_processor.ActivityProcessor.return_value = Mock()
        
        mock_es_storage = Mock()
        mock_es_storage.ElasticsearchStorage.return_value = Mock()
        
        with patch('peakflow.providers.garmin', mock_garmin_provider), \
             patch('peakflow.processors.fit', mock_fit_processor), \
             patch('peakflow.storage.elasticsearch', mock_es_storage):
            yield {
                'garmin': mock_garmin_provider,
                'fit_processor': mock_fit_processor,
                'elasticsearch': mock_es_storage,
            }


@pytest.fixture(scope="session")
def env_rabbitmq_user():
    """RabbitMQ username from environment."""
    return os.environ.get('RABBITMQ_DEFAULT_USER', 'codetrekking')


@pytest.fixture(scope="session")
def env_rabbitmq_password():
    """RabbitMQ password from environment."""
    return os.environ.get('RABBITMQ_DEFAULT_PASS', 'ChangeMe')


@pytest.fixture(scope="session")
def env_rabbitmq_host():
    """RabbitMQ host from environment."""
    return os.environ.get('RABBITMQ_HOST', 'localhost')


@pytest.fixture(scope="session")
def env_rabbitmq_port():
    """RabbitMQ port from environment."""
    return int(os.environ.get('RABBITMQ_PORT', '5672'))


@pytest.fixture(scope="session")
def env_rabbitmq_vhost():
    """RabbitMQ vhost from environment."""
    return os.environ.get('RABBITMQ_VHOST', '/')


@pytest.fixture(scope="session")
def env_elasticsearch_host():
    """Elasticsearch host from environment."""
    return os.environ.get('ELASTICSEARCH_HOST', 'http://localhost:9200')


@pytest.fixture(scope="session")
def env_elasticsearch_user():
    """Elasticsearch username from environment."""
    return os.environ.get('ELASTICSEARCH_USER', 'elastic')


@pytest.fixture(scope="session")
def env_elasticsearch_password():
    """Elasticsearch password from environment."""
    return os.environ.get('ELASTIC_PASSWORD', 'ChangeMe')


# Test data constants
TEST_USER_ID = "test_user"
TEST_ACTIVITY_ID = "12345678901"
TEST_START_DATE = "2024-01-01"
TEST_END_DATE = "2024-01-31"

# Sample test data
SAMPLE_ACTIVITY_METADATA = {
    'activity_id': TEST_ACTIVITY_ID,
    'file_path': f'/tmp/{TEST_ACTIVITY_ID}_ACTIVITY.fit',
    'file_name': f'{TEST_ACTIVITY_ID}_ACTIVITY.fit',
    'file_size': 124567,
    'modified_time': 1704096000.0,
    'download_date': '2024-01-01T07:30:00',
    'output_directory': '/tmp',
}

SAMPLE_ANALYTICS_RESULT = {
    'user_id': TEST_USER_ID,
    'start_date': TEST_START_DATE,
    'end_date': TEST_END_DATE,
    'metrics': {
        'total_activities': 15,
        'total_distance': 75000.0,
        'total_calories': 3500,
        'avg_heart_rate': 145,
        'avg_speed': 2.8,
    },
    'generated_at': '2024-01-01T12:00:00',
}