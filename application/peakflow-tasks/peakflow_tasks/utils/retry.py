"""
Retry logic and decorators for PeakFlow Tasks.

This module provides utilities for implementing retry logic with exponential backoff,
jitter, and circuit breaker patterns for robust task execution.
"""

import random
import time
import logging
from functools import wraps
from typing import Any, Callable, Optional, Tuple, Type, Union, List
from datetime import datetime, timedelta

from tenacity import (
    Retrying,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
    before_sleep_log,
)

from peakflow_tasks.exceptions import (
    GarminAuthenticationError,
    GarminDownloadError,
    StorageError,
    TaskExecutionError,
)

logger = logging.getLogger(__name__)


def exponential_backoff_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError),
    logger_name: Optional[str] = None,
):
    """
    Exponential backoff retry decorator with jitter.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to delay
        retry_on: Tuple of exception types to retry on
        logger_name: Logger name for retry messages
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retry_logger = logging.getLogger(logger_name or func.__module__)
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as exc:
                    if attempt == max_retries:
                        retry_logger.error(
                            f"Function {func.__name__} failed after {max_retries} retries: {exc}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter if enabled
                    if jitter:
                        delay = delay * (0.5 + random.random() * 0.5)
                    
                    retry_logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {exc}. "
                        f"Retrying in {delay:.2f} seconds..."
                    )
                    
                    time.sleep(delay)
                except Exception as exc:
                    # Don't retry for exceptions not in retry_on
                    retry_logger.error(f"Function {func.__name__} failed with non-retryable error: {exc}")
                    raise
            
        return wrapper
    return decorator


def tenacity_retry_config(
    task_name: str,
    max_attempts: int = 3,
    min_wait: float = 1.0,
    max_wait: float = 60.0,
    retry_on_exceptions: Tuple[Type[Exception], ...] = (ConnectionError, TimeoutError),
):
    """
    Create a tenacity retry configuration for tasks.
    
    Args:
        task_name: Name of the task for logging
        max_attempts: Maximum retry attempts
        min_wait: Minimum wait time between retries
        max_wait: Maximum wait time between retries
        retry_on_exceptions: Exceptions to retry on
        
    Returns:
        Tenacity retry decorator
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retry_on_exceptions),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


class CircuitBreaker:
    """
    Circuit breaker pattern implementation for task failures.
    
    Prevents cascading failures by temporarily stopping calls to a failing service.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply circuit breaker to function."""
        @wraps(func)
        def wrapper(*args, **kwargs):
            if self.state == "OPEN":
                if self._should_attempt_reset():
                    self.state = "HALF_OPEN"
                    logger.info(f"Circuit breaker HALF_OPEN for {func.__name__}")
                else:
                    raise TaskExecutionError(
                        f"Circuit breaker OPEN for {func.__name__}. "
                        f"Will retry after {self.recovery_timeout} seconds."
                    )
            
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exception as exc:
                self._on_failure()
                raise
        
        return wrapper
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True
        
        return (
            datetime.now() - self.last_failure_time
        ).total_seconds() >= self.recovery_timeout
    
    def _on_success(self) -> None:
        """Handle successful function call."""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker CLOSED - service recovered")
    
    def _on_failure(self) -> None:
        """Handle failed function call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"Circuit breaker OPEN - failure threshold ({self.failure_threshold}) reached"
            )


def garmin_retry_config():
    """Pre-configured retry for Garmin operations."""
    return tenacity_retry_config(
        task_name="garmin",
        max_attempts=3,
        min_wait=2.0,
        max_wait=30.0,
        retry_on_exceptions=(
            GarminAuthenticationError,
            GarminDownloadError,
            ConnectionError,
            TimeoutError,
        )
    )


def storage_retry_config():
    """Pre-configured retry for storage operations."""
    return tenacity_retry_config(
        task_name="storage",
        max_attempts=5,
        min_wait=1.0,
        max_wait=60.0,
        retry_on_exceptions=(
            StorageError,
            ConnectionError,
            TimeoutError,
        )
    )


def processing_retry_config():
    """Pre-configured retry for processing operations."""
    return tenacity_retry_config(
        task_name="processing",
        max_attempts=2,
        min_wait=5.0,
        max_wait=30.0,
        retry_on_exceptions=(
            MemoryError,
            OSError,
            ConnectionError,
        )
    )


class RetryableTask:
    """
    Mixin class to add retry functionality to task classes.
    """
    
    def with_retry(
        self,
        func: Callable,
        max_attempts: int = 3,
        exceptions: Tuple[Type[Exception], ...] = (Exception,),
        delay: float = 1.0,
        backoff: float = 2.0,
        jitter: bool = True,
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            max_attempts: Maximum retry attempts
            exceptions: Exceptions to retry on
            delay: Base delay between retries
            backoff: Backoff multiplier
            jitter: Add random jitter
            
        Returns:
            Function result
        """
        for attempt in range(max_attempts):
            try:
                return func()
            except exceptions as exc:
                if attempt == max_attempts - 1:
                    raise
                
                # Calculate delay
                current_delay = delay * (backoff ** attempt)
                if jitter:
                    current_delay *= (0.5 + random.random() * 0.5)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                    f"Retrying in {current_delay:.2f} seconds..."
                )
                
                time.sleep(current_delay)


def create_task_retry_decorator(
    task_type: str,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
):
    """
    Create a retry decorator for specific task types.
    
    Args:
        task_type: Type of task (garmin, storage, processing, analytics)
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Retry decorator configured for the task type
    """
    # Define retry exceptions based on task type
    retry_exceptions = {
        "garmin": (GarminAuthenticationError, GarminDownloadError, ConnectionError, TimeoutError),
        "storage": (StorageError, ConnectionError, TimeoutError),
        "processing": (MemoryError, OSError, ConnectionError),
        "analytics": (StorageError, ConnectionError, TimeoutError),
    }
    
    exceptions = retry_exceptions.get(task_type, (ConnectionError, TimeoutError))
    
    return exponential_backoff_retry(
        max_retries=max_attempts - 1,
        base_delay=base_delay,
        max_delay=max_delay,
        retry_on=exceptions,
        logger_name=f"peakflow_tasks.retry.{task_type}",
    )


# Pre-configured decorators for common use cases
garmin_retry = create_task_retry_decorator("garmin", max_attempts=3, base_delay=2.0)
storage_retry = create_task_retry_decorator("storage", max_attempts=5, base_delay=1.0)
processing_retry = create_task_retry_decorator("processing", max_attempts=2, base_delay=5.0)
analytics_retry = create_task_retry_decorator("analytics", max_attempts=3, base_delay=2.0)


# Advanced Error Recovery Patterns

class ErrorRecoveryManager:
    """
    Manages error recovery strategies for different failure scenarios.
    """
    
    def __init__(self):
        self.recovery_strategies = {
            'connection_error': self._handle_connection_error,
            'timeout_error': self._handle_timeout_error,
            'memory_error': self._handle_memory_error,
            'storage_full_error': self._handle_storage_full_error,
        }
    
    def recover_from_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """
        Attempt to recover from an error based on its type.
        
        Args:
            error: The exception that occurred
            context: Additional context about the failure
            
        Returns:
            Dict with recovery results and recommendations
        """
        error_type = self._classify_error(error)
        recovery_strategy = self.recovery_strategies.get(error_type, self._handle_generic_error)
        
        return recovery_strategy(error, context)
    
    def _classify_error(self, error: Exception) -> str:
        """Classify error type for recovery strategy selection."""
        error_name = error.__class__.__name__.lower()
        
        if 'connection' in error_name or 'network' in error_name:
            return 'connection_error'
        elif 'timeout' in error_name:
            return 'timeout_error'
        elif 'memory' in error_name:
            return 'memory_error'
        elif 'auth' in error_name or 'permission' in error_name:
            return 'authentication_error'
        elif 'corrupt' in str(error).lower() or 'invalid' in str(error).lower():
            return 'data_corruption_error'
        elif 'space' in str(error).lower() or 'full' in str(error).lower():
            return 'storage_full_error'
        else:
            return 'unknown_error'
    
    def _handle_connection_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle connection-related errors."""
        return {
            'recovery_possible': True,
            'strategy': 'retry_with_backoff',
            'parameters': {
                'max_attempts': 5,
                'base_delay': 10.0,
                'backoff_factor': 2.0
            },
            'additional_actions': [
                'check_network_connectivity',
                'verify_service_availability'
            ]
        }
    
    def _handle_timeout_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle timeout-related errors."""
        return {
            'recovery_possible': True,
            'strategy': 'retry_with_increased_timeout',
            'parameters': {
                'timeout_multiplier': 2.0,
                'max_attempts': 3
            },
            'additional_actions': [
                'reduce_batch_size',
                'check_system_load'
            ]
        }
    
    def _handle_memory_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle memory-related errors."""
        return {
            'recovery_possible': True,
            'strategy': 'reduce_memory_usage',
            'parameters': {
                'chunk_size_reduction': 0.5,
                'enable_streaming': True
            },
            'additional_actions': [
                'clear_cache',
                'garbage_collect',
                'reduce_concurrency'
            ]
        }
    
    def _handle_authentication_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle authentication-related errors."""
        return {
            'recovery_possible': True,
            'strategy': 'refresh_credentials',
            'parameters': {
                'retry_after_refresh': True,
                'max_refresh_attempts': 2
            },
            'additional_actions': [
                'validate_credentials',
                'check_token_expiry'
            ]
        }
    
    def _handle_data_corruption_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle data corruption errors."""
        return {
            'recovery_possible': True,
            'strategy': 'skip_corrupted_data',
            'parameters': {
                'continue_with_remaining': True,
                'log_corrupted_entries': True
            },
            'additional_actions': [
                'validate_remaining_data',
                'notify_administrators'
            ]
        }
    
    def _handle_storage_full_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle storage full errors."""
        return {
            'recovery_possible': True,
            'strategy': 'cleanup_and_retry',
            'parameters': {
                'cleanup_old_files': True,
                'compress_data': True
            },
            'additional_actions': [
                'monitor_disk_usage',
                'alert_administrators'
            ]
        }
    
    def _handle_generic_error(self, error: Exception, context: dict[str, Any]) -> dict[str, Any]:
        """Handle generic errors with basic retry strategy."""
        return {
            'recovery_action': 'basic_retry',
            'recommendations': [
                'Review error logs for patterns',
                'Monitor system resources',
                'Consider increasing retry intervals'
            ],
            'retry_delay': 60,
            'max_retries': 3,
            'additional_actions': [
                'log_detailed_error'
            ]
        }


class FailureAnalyzer:
    """
    Analyzes failure patterns to provide insights and recommendations.
    """
    
    def __init__(self):
        self.failure_history = []
    
    def record_failure(self, task_name: str, error: Exception, context: dict[str, Any]):
        """Record a task failure for analysis."""
        failure_record = {
            'timestamp': datetime.now(),
            'task_name': task_name,
            'error_type': error.__class__.__name__,
            'error_message': str(error),
            'context': context
        }
        
        self.failure_history.append(failure_record)
        
        # Keep only recent failures (last 1000)
        if len(self.failure_history) > 1000:
            self.failure_history = self.failure_history[-1000:]
    
    def analyze_failure_patterns(self, time_window_hours: int = 24) -> dict[str, Any]:
        """Analyze failure patterns within a time window."""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        recent_failures = [
            f for f in self.failure_history 
            if f['timestamp'] >= cutoff_time
        ]
        
        if not recent_failures:
            return {'status': 'no_recent_failures'}
        
        # Analyze patterns
        error_counts = {}
        task_counts = {}
        hourly_distribution = [0] * 24
        
        for failure in recent_failures:
            # Count by error type
            error_type = failure['error_type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
            
            # Count by task
            task_name = failure['task_name']
            task_counts[task_name] = task_counts.get(task_name, 0) + 1
            
            # Hourly distribution
            hour = failure['timestamp'].hour
            hourly_distribution[hour] += 1
        
        # Find patterns
        most_common_error = max(error_counts.items(), key=lambda x: x[1]) if error_counts else None
        most_failing_task = max(task_counts.items(), key=lambda x: x[1]) if task_counts else None
        peak_failure_hour = hourly_distribution.index(max(hourly_distribution))
        
        return {
            'total_failures': len(recent_failures),
            'error_distribution': error_counts,
            'task_distribution': task_counts,
            'most_common_error': most_common_error,
            'most_failing_task': most_failing_task,
            'peak_failure_hour': peak_failure_hour,
            'failure_rate': len(recent_failures) / time_window_hours,
            'recommendations': self._generate_recommendations(error_counts, task_counts)
        }
    
    def _generate_recommendations(self, error_counts: dict[str, int], 
                                task_counts: dict[str, int]) -> List[str]:
        """Generate recommendations based on failure analysis."""
        recommendations = []
        
        # Error-based recommendations
        if error_counts.get('ConnectionError', 0) > 5:
            recommendations.append("High connection errors detected - check network stability")
        
        if error_counts.get('TimeoutError', 0) > 3:
            recommendations.append("Frequent timeouts - consider increasing timeout values")
        
        if error_counts.get('MemoryError', 0) > 1:
            recommendations.append("Memory errors detected - reduce batch sizes or scale resources")
        
        # Task-based recommendations
        for task, count in task_counts.items():
            if count > 10:
                recommendations.append(f"High failure rate for {task} - investigate task logic")
        
        return recommendations


# Resilience patterns

class BulkheadPattern:
    """
    Implements bulkhead pattern for isolating failures.
    """
    
    def __init__(self, max_failures_per_partition: int = 3):
        self.max_failures_per_partition = max_failures_per_partition
        self.partition_failures = {}
        self.isolated_partitions = set()
    
    def execute_with_bulkhead(self, partition: str, func: Callable, *args, **kwargs):
        """Execute function with bulkhead isolation."""
        if partition in self.isolated_partitions:
            raise TaskExecutionError(f"Partition {partition} is isolated due to repeated failures")
        
        try:
            result = func(*args, **kwargs)
            # Reset failure count on success
            self.partition_failures[partition] = 0
            return result
            
        except Exception as e:
            # Increment failure count
            failures = self.partition_failures.get(partition, 0) + 1
            self.partition_failures[partition] = failures
            
            # Isolate partition if threshold reached
            if failures >= self.max_failures_per_partition:
                self.isolated_partitions.add(partition)
                logger.warning(f"Partition {partition} isolated after {failures} failures")
            
            raise
    
    def reset_partition(self, partition: str):
        """Reset partition isolation."""
        self.partition_failures[partition] = 0
        self.isolated_partitions.discard(partition)
        logger.info(f"Partition {partition} isolation reset")


# Global instances
error_recovery_manager = ErrorRecoveryManager()
failure_analyzer = FailureAnalyzer()
bulkhead_manager = BulkheadPattern()