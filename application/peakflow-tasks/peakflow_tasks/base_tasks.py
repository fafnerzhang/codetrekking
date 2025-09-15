"""
Base task classes for PeakFlow Tasks.

This module provides base classes for different categories of tasks with common
functionality like progress tracking, error handling, and resource management.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from datetime import datetime
from pathlib import Path

from celery import Task
from celery.exceptions import Retry

from peakflow_tasks.exceptions import (
    PeakFlowTasksError,
    ConfigurationError,
    GarminAuthenticationError,
    StorageError,
    TaskExecutionError,
)
from peakflow_tasks.config import (
    get_elasticsearch_config, 
    get_peakflow_config,
    ElasticsearchConfig,
    PeakFlowConfig,
)


logger = logging.getLogger(__name__)


class BaseTask(Task, ABC):
    """
    Base class for all PeakFlow tasks.
    
    Provides common functionality:
    - Progress tracking
    - Error handling
    - Logging
    - Configuration access
    """
    
    autoretry_for = (ConnectionError, TimeoutError)
    retry_kwargs = {"max_retries": 3, "countdown": 60}
    retry_backoff = True
    
    def __call__(self, *args, **kwargs):
        """Override to add common task setup and teardown."""
        task_id = self.request.id
        task_name = self.name
        
        logger.info(f"🚀 Starting task {task_name} [{task_id}]")
        start_time = datetime.now()
        
        try:
            # Initialize task-specific resources
            self._setup()
            
            # Execute the actual task
            result = self.execute(*args, **kwargs)
            
            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Task {task_name} completed in {execution_time:.2f}s")
            
            return result
            
        except Exception as exc:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ Task {task_name} failed after {execution_time:.2f}s: {exc}")
            
            # Handle retries for specific exceptions
            if self._should_retry(exc):
                logger.warning(f"🔄 Retrying task {task_name} due to: {exc}")
                raise self.retry(exc=exc)
            
            raise
        finally:
            # Cleanup task-specific resources
            self._teardown()
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """
        Execute the actual task logic.
        
        This method must be implemented by subclasses.
        """
        raise NotImplementedError("Subclasses must implement execute method")
    
    def _setup(self) -> None:
        """Setup task-specific resources. Override in subclasses if needed."""
        pass
    
    def _teardown(self) -> None:
        """Cleanup task-specific resources. Override in subclasses if needed."""
        pass
    
    def _should_retry(self, exc: Exception) -> bool:
        """
        Determine if the task should be retried based on the exception.
        
        Args:
            exc: The exception that occurred
            
        Returns:
            True if the task should be retried
        """
        # Don't retry for configuration errors or validation errors
        if isinstance(exc, (ConfigurationError, ValueError, TypeError)):
            return False
        
        # Retry for network-related errors
        if isinstance(exc, (ConnectionError, TimeoutError)):
            return True
        
        # Check if we have retries left
        return self.request.retries < self.max_retries
    
    def update_progress(self, current: int, total: int, message: str = "") -> None:
        """
        Update task progress.
        
        Args:
            current: Current progress count
            total: Total items to process
            message: Optional progress message
        """
        if total > 0:
            percentage = int((current / total) * 100)
        else:
            percentage = 0
        
        self.update_state(
            state="PROGRESS",
            meta={
                "current": current,
                "total": total,
                "percentage": percentage,
                "message": message,
            }
        )


class BaseGarminTask(BaseTask):
    """
    Base class for Garmin-related tasks.
    
    Provides Garmin-specific functionality:
    - Garmin client initialization
    - Authentication handling
    - Configuration validation
    """
    
    autoretry_for = (GarminAuthenticationError, ConnectionError, TimeoutError)
    
    def __init__(self):
        self._garmin_client = None
        self._peakflow_config: Optional[PeakFlowConfig] = None
    
    def _setup(self) -> None:
        """Setup Garmin-specific resources."""
        super()._setup()
        self._peakflow_config = get_peakflow_config()
        logger.debug("Garmin task setup completed")
    
    def _teardown(self) -> None:
        """Cleanup Garmin-specific resources."""
        if self._garmin_client:
            try:
                # Close Garmin client connection if needed
                if hasattr(self._garmin_client, "close"):
                    self._garmin_client.close()
            except Exception as e:
                logger.warning(f"Error closing Garmin client: {e}")
        super()._teardown()
    
    def get_garmin_client(self, user_id: str):
        """
        Get initialized Garmin client for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Initialized Garmin client
            
        Raises:
            ConfigurationError: If Garmin configuration is invalid
        """
        try:
            from peakflow.utils import create_garmin_client_from_config
            
            if not self._validate_garmin_config(user_id):
                raise ConfigurationError(f"Invalid Garmin configuration for user {user_id}")
            
            self._garmin_client = create_garmin_client_from_config(user_id)
            return self._garmin_client
            
        except ImportError:
            raise ConfigurationError("PeakFlow library not available")
        except Exception as e:
            raise ConfigurationError(f"Failed to create Garmin client: {e}")
    
    def _validate_garmin_config(self, user_id: str) -> bool:
        """
        Validate Garmin configuration for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            True if configuration is valid
        """
        try:
            config_path = self._peakflow_config.garmin_config_path / f"{user_id}" / "GarminConnectConfig.json"
            return config_path.exists()
        except Exception:
            return False


class BaseProcessingTask(BaseTask):
    """
    Base class for data processing tasks.
    
    Provides processing-specific functionality:
    - File validation
    - Memory management
    - Progress tracking for batch operations
    """
    
    def __init__(self):
        self._processor = None
        self._storage = None
    
    def _setup(self) -> None:
        """Setup processing-specific resources."""
        super()._setup()
        logger.debug("Processing task setup completed")
    
    def _teardown(self) -> None:
        """Cleanup processing-specific resources."""
        if self._storage:
            try:
                # Close storage connection if needed
                if hasattr(self._storage, "close"):
                    self._storage.close()
            except Exception as e:
                logger.warning(f"Error closing storage connection: {e}")
        super()._teardown()
    
    def validate_file_path(self, file_path: str) -> Path:
        """
        Validate that file exists and is readable.
        
        Args:
            file_path: Path to file
            
        Returns:
            Path object
            
        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If file is not readable
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        if not os.access(path, os.R_OK):
            raise PermissionError(f"File is not readable: {file_path}")
        
        return path
    
    def get_fit_processor(self):
        """
        Get initialized FIT file processor.
        
        Returns:
            FIT file processor instance
        """
        try:
            from peakflow.processors.activity import ActivityProcessor
            
            if not self._storage:
                self._storage = self.get_elasticsearch_storage()
            
            self._processor = ActivityProcessor(self._storage)
            return self._processor
            
        except ImportError:
            raise ConfigurationError("PeakFlow library not available")
        except Exception as e:
            raise ConfigurationError(f"Failed to create FIT processor: {e}")
    
    def get_elasticsearch_storage(self):
        """
        Get initialized Elasticsearch storage.
        
        Returns:
            Elasticsearch storage instance
        """
        try:
            from peakflow.storage.elasticsearch import ElasticsearchStorage
            
            self._storage = ElasticsearchStorage()
            es_config = get_elasticsearch_config()
            self._storage.initialize(es_config.to_dict())
            
            return self._storage
            
        except ImportError:
            raise ConfigurationError("PeakFlow library not available")
        except Exception as e:
            raise StorageError(f"Failed to initialize Elasticsearch storage: {e}")


class BaseStorageTask(BaseTask):
    """
    Base class for storage-related tasks.
    
    Provides storage-specific functionality:
    - Elasticsearch connection management
    - Index validation
    - Bulk operation optimization
    """
    
    autoretry_for = (ConnectionError, TimeoutError, StorageError)
    
    def __init__(self):
        self._storage = None
        self._es_config: Optional[ElasticsearchConfig] = None
    
    def _setup(self) -> None:
        """Setup storage-specific resources."""
        super()._setup()
        self._es_config = get_elasticsearch_config()
        logger.debug("Storage task setup completed")
    
    def _teardown(self) -> None:
        """Cleanup storage-specific resources."""
        if self._storage:
            try:
                if hasattr(self._storage, "close"):
                    self._storage.close()
            except Exception as e:
                logger.warning(f"Error closing storage connection: {e}")
        super()._teardown()
    
    def get_elasticsearch_storage(self):
        """
        Get initialized Elasticsearch storage.
        
        Returns:
            Elasticsearch storage instance
        """
        if self._storage is None:
            try:
                from peakflow.storage.elasticsearch import ElasticsearchStorage
                
                self._storage = ElasticsearchStorage()
                self._storage.initialize(self._es_config.to_dict())
                
            except ImportError:
                raise ConfigurationError("PeakFlow library not available")
            except Exception as e:
                raise StorageError(f"Failed to initialize Elasticsearch storage: {e}")
        
        return self._storage
    
    def validate_elasticsearch_connection(self) -> bool:
        """
        Validate Elasticsearch connection.
        
        Returns:
            True if connection is valid
        """
        try:
            storage = self.get_elasticsearch_storage()
            # Try a simple operation to validate connection
            return storage.ping() if hasattr(storage, "ping") else True
        except Exception as e:
            logger.error(f"Elasticsearch connection validation failed: {e}")
            return False


class BaseAnalyticsTask(BaseTask):
    """
    Base class for analytics tasks.
    
    Provides analytics-specific functionality:
    - Data aggregation
    - Statistical processing
    - Result formatting
    """
    
    def __init__(self):
        self._storage = None
        self._analytics_engine = None
    
    def _setup(self) -> None:
        """Setup analytics-specific resources."""
        super()._setup()
        logger.debug("Analytics task setup completed")
    
    def _teardown(self) -> None:
        """Cleanup analytics-specific resources."""
        if self._storage:
            try:
                if hasattr(self._storage, "close"):
                    self._storage.close()
            except Exception as e:
                logger.warning(f"Error closing storage connection: {e}")
        super()._teardown()
    
    def get_elasticsearch_storage(self):
        """
        Get initialized Elasticsearch storage.
        
        Returns:
            Elasticsearch storage instance
        """
        if self._storage is None:
            try:
                from peakflow.storage.elasticsearch import ElasticsearchStorage
                
                self._storage = ElasticsearchStorage()
                es_config = get_elasticsearch_config()
                self._storage.initialize(es_config.to_dict())
                
            except ImportError:
                raise ConfigurationError("PeakFlow library not available")
            except Exception as e:
                raise StorageError(f"Failed to initialize Elasticsearch storage: {e}")
        
        return self._storage
    
    def get_analytics_processor(self):
        """
        Get analytics processor with storage.
        
        Returns:
            Analytics processor instance
        """
        try:
            from peakflow.processors.activity import ActivityProcessor
            
            if not self._storage:
                self._storage = self.get_elasticsearch_storage()
            
            self._analytics_engine = ActivityProcessor(self._storage)
            return self._analytics_engine
            
        except ImportError:
            raise ConfigurationError("PeakFlow library not available")
        except Exception as e:
            raise ConfigurationError(f"Failed to create analytics processor: {e}")


# Import os for file access checks
import os