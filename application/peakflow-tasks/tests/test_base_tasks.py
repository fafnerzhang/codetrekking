"""
Tests for base task classes.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from peakflow_tasks.base_tasks import (
    BaseTask,
    BaseGarminTask,
    BaseProcessingTask,
    BaseStorageTask,
    BaseAnalyticsTask,
)
from peakflow_tasks.exceptions import (
    ConfigurationError,
    StorageError,
    TaskExecutionError,
)


class ConcreteBaseTask(BaseTask):
    """Concrete implementation of BaseTask for testing."""
    
    def __init__(self):
        super().__init__()
        self._request = Mock(id="test_123", retries=0)
        
    @property 
    def request(self):
        return self._request
    
    def execute(self, *args, **kwargs):
        return {"result": "success", "args": args, "kwargs": kwargs}


class ConcreteGarminTask(BaseGarminTask):
    """Concrete implementation of BaseGarminTask for testing."""
    
    def execute(self, *args, **kwargs):
        return {"result": "garmin_success"}


class ConcreteProcessingTask(BaseProcessingTask):
    """Concrete implementation of BaseProcessingTask for testing."""
    
    def execute(self, *args, **kwargs):
        return {"result": "processing_success"}


class ConcreteStorageTask(BaseStorageTask):
    """Concrete implementation of BaseStorageTask for testing."""
    
    def execute(self, *args, **kwargs):
        return {"result": "storage_success"}


class ConcreteAnalyticsTask(BaseAnalyticsTask):
    """Concrete implementation of BaseAnalyticsTask for testing."""
    
    def execute(self, *args, **kwargs):
        return {"result": "analytics_success"}


class TestBaseTask:
    """Test BaseTask functionality."""
    
    def test_task_execution_success(self):
        """Test successful task execution."""
        task = ConcreteBaseTask()
        task.name = "test_task"
        task.max_retries = 3
        
        result = task("arg1", "arg2", key1="value1", key2="value2")
        
        assert result["result"] == "success"
        assert result["args"] == ("arg1", "arg2")
        assert result["kwargs"] == {"key1": "value1", "key2": "value2"}
    
    def test_should_retry_logic(self):
        """Test retry decision logic."""
        task = ConcreteBaseTask()
        task._request.retries = 1
        task.max_retries = 3
        
        # Should retry for ConnectionError
        assert task._should_retry(ConnectionError("Network error")) is True
        
        # Should not retry for ConfigurationError
        assert task._should_retry(ConfigurationError("Config error")) is False
        
        # Should not retry for ValueError
        assert task._should_retry(ValueError("Invalid value")) is False
    
    def test_update_progress(self):
        """Test progress update functionality."""
        task = ConcreteBaseTask()
        task.update_state = Mock()
        
        task.update_progress(50, 100, "Processing data")
        
        task.update_state.assert_called_once_with(
            state="PROGRESS",
            meta={
                "current": 50,
                "total": 100,
                "percentage": 50,
                "message": "Processing data",
            }
        )


class TestBaseGarminTask:
    """Test BaseGarminTask functionality."""
    
    def test_initialization(self):
        """Test task initialization."""
        task = ConcreteGarminTask()
        
        assert task._garmin_client is None
        assert task._peakflow_config is None
    
    @patch('peakflow_tasks.base_tasks.get_peakflow_config')
    def test_setup(self, mock_get_config):
        """Test setup method."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        task = ConcreteGarminTask()
        task._setup()
        
        assert task._peakflow_config == mock_config
        mock_get_config.assert_called_once()
    
    def test_validate_garmin_config_missing(self):
        """Test Garmin configuration validation with missing config."""
        task = ConcreteGarminTask()
        task._peakflow_config = Mock()
        task._peakflow_config.garmin_config_path = Mock()
        
        # Mock non-existent config file
        with patch('pathlib.Path.exists', return_value=False):
            result = task._validate_garmin_config("test_user")
            assert result is False
    
    def test_validate_garmin_config_exists(self):
        """Test Garmin configuration validation with existing config."""
        task = ConcreteGarminTask()
        
        # Create a mock path that returns True for exists()
        mock_config_path = Mock()
        mock_final_path = Mock()
        mock_final_path.exists.return_value = True
        mock_config_path.__truediv__ = Mock(return_value=Mock(__truediv__ = Mock(return_value=mock_final_path)))
        
        task._peakflow_config = Mock()
        task._peakflow_config.garmin_config_path = mock_config_path
        
        result = task._validate_garmin_config("test_user")
        assert result is True
    
    def test_get_garmin_client_import_error(self):
        """Test Garmin client creation with import error."""
        task = ConcreteGarminTask()
        task._peakflow_config = Mock()
        
        # Mock validation to pass but create_garmin_client_from_config to fail
        with patch.object(task, '_validate_garmin_config', return_value=True):
            # The function will fail due to parameter mismatch or other issues
            with pytest.raises(ConfigurationError, match="Failed to create Garmin client"):
                task.get_garmin_client("test_user")
    
    @patch('peakflow_tasks.base_tasks.get_peakflow_config')
    def test_get_garmin_client_invalid_config(self, mock_get_config):
        """Test Garmin client creation with invalid config."""
        task = ConcreteGarminTask()
        task._peakflow_config = Mock()
        
        # Mock failed validation
        with patch.object(task, '_validate_garmin_config', return_value=False):
            with pytest.raises(ConfigurationError, match="Invalid Garmin configuration"):
                task.get_garmin_client("test_user")


class TestBaseProcessingTask:
    """Test BaseProcessingTask functionality."""
    
    def test_initialization(self):
        """Test task initialization."""
        task = ConcreteProcessingTask()
        
        assert task._processor is None
        assert task._storage is None
    
    def test_validate_file_path_success(self, temp_dir):
        """Test successful file path validation."""
        task = ConcreteProcessingTask()
        test_file = temp_dir / "test.fit"
        test_file.write_text("test content")
        
        result = task.validate_file_path(str(test_file))
        
        assert result == test_file
    
    def test_validate_file_path_not_exists(self):
        """Test file path validation with non-existent file."""
        task = ConcreteProcessingTask()
        
        with pytest.raises(FileNotFoundError, match="File not found"):
            task.validate_file_path("/non/existent/file.fit")
    
    def test_validate_file_path_is_directory(self, temp_dir):
        """Test file path validation with directory."""
        task = ConcreteProcessingTask()
        
        with pytest.raises(ValueError, match="Path is not a file"):
            task.validate_file_path(str(temp_dir))
    
    @patch('peakflow_tasks.base_tasks.get_elasticsearch_config')
    @patch('peakflow.storage.elasticsearch.ElasticsearchStorage')
    def test_get_elasticsearch_storage(self, mock_elasticsearch_storage, mock_get_config):
        """Test Elasticsearch storage initialization."""
        task = ConcreteProcessingTask()
        mock_config = Mock()
        mock_config.to_dict.return_value = {"host": "localhost"}
        mock_get_config.return_value = mock_config
        
        mock_storage = Mock()
        mock_elasticsearch_storage.return_value = mock_storage
        
        result = task.get_elasticsearch_storage()
        
        assert result == mock_storage
        assert task._storage == mock_storage
        mock_storage.initialize.assert_called_once_with({"host": "localhost"})
    
    @patch('peakflow.processors.activity.ActivityProcessor')
    def test_get_fit_processor(self, mock_fit_processor):
        """Test FIT processor initialization."""
        task = ConcreteProcessingTask()
        
        # Mock storage
        mock_storage = Mock()
        task._storage = mock_storage
        
        mock_processor_instance = Mock()
        mock_fit_processor.return_value = mock_processor_instance
        
        result = task.get_fit_processor()
        
        assert result == mock_processor_instance
        assert task._processor == mock_processor_instance


class TestBaseStorageTask:
    """Test BaseStorageTask functionality."""
    
    def test_initialization(self):
        """Test task initialization."""
        task = ConcreteStorageTask()
        
        assert task._storage is None
        assert task._es_config is None
    
    @patch('peakflow_tasks.base_tasks.get_elasticsearch_config')
    def test_setup(self, mock_get_config):
        """Test setup method."""
        mock_config = Mock()
        mock_get_config.return_value = mock_config
        
        task = ConcreteStorageTask()
        task._setup()
        
        assert task._es_config == mock_config
        mock_get_config.assert_called_once()
    
    @patch('peakflow.storage.elasticsearch.ElasticsearchStorage')
    def test_get_elasticsearch_storage(self, mock_elasticsearch_storage):
        """Test Elasticsearch storage initialization."""
        task = ConcreteStorageTask()
        task._es_config = Mock()
        task._es_config.to_dict.return_value = {"host": "localhost"}
        
        mock_storage = Mock()
        mock_elasticsearch_storage.return_value = mock_storage
        
        result = task.get_elasticsearch_storage()
        
        assert result == mock_storage
        assert task._storage == mock_storage
        mock_storage.initialize.assert_called_once_with({"host": "localhost"})
    
    def test_validate_elasticsearch_connection_success(self):
        """Test successful Elasticsearch connection validation."""
        task = ConcreteStorageTask()
        
        mock_storage = Mock()
        mock_storage.ping.return_value = True
        task._storage = mock_storage
        
        with patch.object(task, 'get_elasticsearch_storage', return_value=mock_storage):
            result = task.validate_elasticsearch_connection()
            assert result is True
    
    def test_validate_elasticsearch_connection_failure(self):
        """Test failed Elasticsearch connection validation."""
        task = ConcreteStorageTask()
        
        with patch.object(task, 'get_elasticsearch_storage', side_effect=StorageError("Connection failed")):
            result = task.validate_elasticsearch_connection()
            assert result is False


class TestBaseAnalyticsTask:
    """Test BaseAnalyticsTask functionality."""
    
    def test_initialization(self):
        """Test task initialization."""
        task = ConcreteAnalyticsTask()
        
        assert task._storage is None
        assert task._analytics_engine is None
    
    @patch('peakflow_tasks.base_tasks.get_elasticsearch_config')
    @patch('peakflow.storage.elasticsearch.ElasticsearchStorage')
    def test_get_elasticsearch_storage(self, mock_elasticsearch_storage, mock_get_config):
        """Test Elasticsearch storage initialization."""
        task = ConcreteAnalyticsTask()
        mock_config = Mock()
        mock_config.to_dict.return_value = {"host": "localhost"}
        mock_get_config.return_value = mock_config
        
        mock_storage = Mock()
        mock_elasticsearch_storage.return_value = mock_storage
        
        result = task.get_elasticsearch_storage()
        
        assert result == mock_storage
        assert task._storage == mock_storage
        mock_storage.initialize.assert_called_once_with({"host": "localhost"})
    
    @patch('peakflow.processors.activity.ActivityProcessor')
    def test_get_analytics_processor(self, mock_fit_processor):
        """Test analytics processor initialization."""
        task = ConcreteAnalyticsTask()
        
        # Mock storage
        mock_storage = Mock()
        task._storage = mock_storage
        
        mock_processor_instance = Mock()
        mock_fit_processor.return_value = mock_processor_instance
        
        result = task.get_analytics_processor()
        
        assert result == mock_processor_instance
        assert task._analytics_engine == mock_processor_instance