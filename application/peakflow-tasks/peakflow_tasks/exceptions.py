"""
Custom exception classes for PeakFlow Tasks.

This module defines the exception hierarchy used throughout the PeakFlow Tasks
application for better error handling and debugging.
"""

from typing import Optional, Any, Dict


class PeakFlowTasksError(Exception):
    """
    Base exception for all PeakFlow Tasks errors.
    
    All custom exceptions in this package should inherit from this class.
    """
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


class ConfigurationError(PeakFlowTasksError):
    """
    Raised when there are configuration-related errors.
    
    Examples:
    - Missing required environment variables
    - Invalid configuration values
    - Missing configuration files
    """
    pass


class GarminAuthenticationError(PeakFlowTasksError):
    """
    Raised when Garmin authentication fails.
    
    Examples:
    - Invalid credentials
    - Authentication timeout
    - Two-factor authentication required
    """
    pass


class GarminDownloadError(PeakFlowTasksError):
    """
    Raised when Garmin download operations fail.
    
    Examples:
    - Network connectivity issues
    - Server-side errors
    - Rate limiting
    - Invalid date ranges
    """
    pass


class FitProcessingError(PeakFlowTasksError):
    """
    Raised when FIT file processing fails.
    
    Examples:
    - Corrupted FIT files
    - Unsupported FIT file format
    - Processing timeout
    - Memory allocation errors
    """
    pass


class StorageError(PeakFlowTasksError):
    """
    Raised when storage operations fail.
    
    Examples:
    - Elasticsearch connection errors
    - Index creation failures
    - Document indexing errors
    - Query execution errors
    """
    pass


class AnalyticsError(PeakFlowTasksError):
    """
    Raised when analytics generation fails.
    
    Examples:
    - Insufficient data for analysis
    - Mathematical computation errors
    - Algorithm failures
    - Result validation errors
    """
    pass


class ValidationError(PeakFlowTasksError):
    """
    Raised when data validation fails.
    
    Examples:
    - Invalid input parameters
    - Schema validation errors
    - Data type mismatches
    - Range validation failures
    """
    pass


class TaskExecutionError(PeakFlowTasksError):
    """
    Raised when task execution fails in unexpected ways.
    
    Examples:
    - Celery worker errors
    - Resource exhaustion
    - Timeout errors
    - Unexpected exceptions
    """
    pass


class WorkflowError(PeakFlowTasksError):
    """
    Raised when workflow orchestration fails.
    
    Examples:
    - Task dependency failures
    - Workflow step errors
    - State management errors
    - Chain execution failures
    """
    pass


# Convenience functions for creating common exceptions

def configuration_error(message: str, **details) -> ConfigurationError:
    """Create a configuration error with details."""
    return ConfigurationError(message, details)


def garmin_auth_error(message: str, **details) -> GarminAuthenticationError:
    """Create a Garmin authentication error with details."""
    return GarminAuthenticationError(message, details)


def garmin_download_error(message: str, **details) -> GarminDownloadError:
    """Create a Garmin download error with details."""
    return GarminDownloadError(message, details)


def fit_processing_error(message: str, **details) -> FitProcessingError:
    """Create a FIT processing error with details."""
    return FitProcessingError(message, details)


def storage_error(message: str, **details) -> StorageError:
    """Create a storage error with details."""
    return StorageError(message, details)


def analytics_error(message: str, **details) -> AnalyticsError:
    """Create an analytics error with details."""
    return AnalyticsError(message, details)


def validation_error(message: str, **details) -> ValidationError:
    """Create a validation error with details."""
    return ValidationError(message, details)


def task_execution_error(message: str, **details) -> TaskExecutionError:
    """Create a task execution error with details."""
    return TaskExecutionError(message, details)


def workflow_error(message: str, **details) -> WorkflowError:
    """Create a workflow error with details."""
    return WorkflowError(message, details)