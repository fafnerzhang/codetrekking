"""
Logging configuration for the API service.
"""

import os
import sys
import logging
import structlog
from typing import Dict, Any


def configure_structured_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    stream=None,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Format type ('json' or 'console')
        stream: Output stream (defaults to stdout)
    """
    # Configure basic logging
    logging.basicConfig(
        format="%(message)s",
        stream=stream or sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Configure processors based on format
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Add format-specific processor
    if log_format == "console":
        processors.append(
            structlog.dev.ConsoleRenderer(colors=True)
        )
    else:
        processors.append(
            structlog.processors.JSONRenderer()
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def setup_application_logging() -> structlog.BoundLogger:
    """
    Setup logging configuration for the application based on environment.

    Returns:
        Main application logger
    """
    # Determine log level from environment
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Determine format based on environment
    environment = os.getenv("ENVIRONMENT", "development").lower()
    log_format = "console" if environment == "development" else "json"

    # Configure logging
    configure_structured_logging(
        log_level=log_level,
        log_format=log_format,
    )

    # Return main logger
    return get_logger("api-service")


class LoggingConfig:
    """Configuration class for application logging."""

    DEFAULT_PROCESSORS = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ]

    @classmethod
    def get_environment_config(cls) -> Dict[str, Any]:
        """Get logging configuration based on environment variables."""
        return {
            "log_level": os.getenv("LOG_LEVEL", "INFO").upper(),
            "environment": os.getenv("ENVIRONMENT", "development").lower(),
            "log_format": "console" if os.getenv("ENVIRONMENT", "development").lower() == "development" else "json",
            "enable_debug": os.getenv("DEBUG", "false").lower() == "true",
            "log_file": os.getenv("LOG_FILE"),
        }

    @classmethod
    def configure_for_environment(cls) -> None:
        """Configure logging based on current environment settings."""
        config = cls.get_environment_config()
        configure_structured_logging(
            log_level=config["log_level"],
            log_format=config["log_format"],
        )