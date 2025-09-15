"""
Logging configuration and utilities for PeakFlow Tasks.

This module provides structured logging configuration with support for different
output formats, log levels, and integration with Celery task logging.
"""

import logging
import logging.config
import sys
from typing import Dict, Any, Optional
from datetime import datetime
import json

import structlog
from structlog.typing import FilteringBoundLogger


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add task context if available
        if hasattr(record, 'task_id'):
            log_entry['task_id'] = record.task_id
        if hasattr(record, 'task_name'):
            log_entry['task_name'] = record.task_name
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'getMessage', 'exc_info', 
                          'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


class ColoredFormatter(logging.Formatter):
    """
    Colored formatter for console output.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def setup_logging(
    level: str = "INFO",
    format_type: str = "console",
    enable_structlog: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Setup logging configuration for PeakFlow Tasks.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: Output format ('console', 'json')
        enable_structlog: Enable structured logging with structlog
        log_file: Optional log file path
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Base configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'console': {
                'class': 'peakflow_tasks.utils.logging.ColoredFormatter',
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            'json': {
                'class': 'peakflow_tasks.utils.logging.JSONFormatter',
            },
            'file': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': format_type,
                'stream': sys.stdout,
            },
        },
        'loggers': {
            'peakflow_tasks': {
                'level': log_level,
                'handlers': ['console'],
                'propagate': False,
            },
            'celery': {
                'level': 'WARNING',
                'handlers': ['console'],
                'propagate': False,
            },
            'celery.app.trace': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False,
            },
            'peakflow': {
                'level': log_level,
                'handlers': ['console'],
                'propagate': False,
            },
        },
        'root': {
            'level': 'WARNING',
            'handlers': ['console'],
        },
    }
    
    # Add file handler if log file is specified
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': log_level,
            'formatter': 'file',
            'filename': log_file,
            'maxBytes': 10_000_000,  # 10MB
            'backupCount': 5,
        }
        
        # Add file handler to all loggers
        for logger_config in config['loggers'].values():
            logger_config['handlers'].append('file')
        config['root']['handlers'].append('file')
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Setup structlog if enabled
    if enable_structlog:
        setup_structlog(level)


def setup_structlog(level: str = "INFO") -> None:
    """
    Setup structured logging with structlog.
    
    Args:
        level: Logging level
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )


def get_task_logger(task_name: str, task_id: Optional[str] = None, **context) -> FilteringBoundLogger:
    """
    Get a structured logger for a specific task.
    
    Args:
        task_name: Name of the task
        task_id: Task ID (optional)
        **context: Additional context to include in logs
        
    Returns:
        Structured logger with task context
    """
    logger = structlog.get_logger(task_name)
    
    # Add task context
    if task_id:
        logger = logger.bind(task_id=task_id)
    
    # Add additional context
    if context:
        logger = logger.bind(**context)
    
    return logger


def log_task_start(task_name: str, task_id: str, **kwargs) -> None:
    """
    Log task start with context.
    
    Args:
        task_name: Name of the task
        task_id: Task ID
        **kwargs: Task arguments to log
    """
    logger = get_task_logger(task_name, task_id)
    logger.info("Task started", **kwargs)


def log_task_progress(task_name: str, task_id: str, current: int, total: int, message: str = "") -> None:
    """
    Log task progress.
    
    Args:
        task_name: Name of the task
        task_id: Task ID
        current: Current progress
        total: Total items
        message: Progress message
    """
    logger = get_task_logger(task_name, task_id)
    percentage = int((current / total) * 100) if total > 0 else 0
    
    logger.info(
        "Task progress",
        current=current,
        total=total,
        percentage=percentage,
        message=message
    )


def log_task_completion(task_name: str, task_id: str, duration: float, **result) -> None:
    """
    Log task completion.
    
    Args:
        task_name: Name of the task
        task_id: Task ID
        duration: Task duration in seconds
        **result: Task result data to log
    """
    logger = get_task_logger(task_name, task_id)
    logger.info(
        "Task completed",
        duration=duration,
        **result
    )


def log_task_error(task_name: str, task_id: str, error: Exception, duration: float) -> None:
    """
    Log task error.
    
    Args:
        task_name: Name of the task
        task_id: Task ID
        error: Exception that occurred
        duration: Task duration before error
    """
    logger = get_task_logger(task_name, task_id)
    logger.error(
        "Task failed",
        error=str(error),
        error_type=type(error).__name__,
        duration=duration,
        exc_info=True
    )


class TaskLoggerMixin:
    """
    Mixin class to add structured logging to task classes.
    """
    
    def get_logger(self) -> FilteringBoundLogger:
        """Get structured logger for this task."""
        task_id = getattr(self.request, 'id', None) if hasattr(self, 'request') else None
        task_name = getattr(self, 'name', self.__class__.__name__)
        
        return get_task_logger(task_name, task_id)
    
    def log_info(self, message: str, **kwargs) -> None:
        """Log info message with task context."""
        self.get_logger().info(message, **kwargs)
    
    def log_warning(self, message: str, **kwargs) -> None:
        """Log warning message with task context."""
        self.get_logger().warning(message, **kwargs)
    
    def log_error(self, message: str, **kwargs) -> None:
        """Log error message with task context."""
        self.get_logger().error(message, **kwargs)
    
    def log_debug(self, message: str, **kwargs) -> None:
        """Log debug message with task context."""
        self.get_logger().debug(message, **kwargs)