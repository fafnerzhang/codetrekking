"""
Celery application setup for PeakFlow Tasks.

This module creates and configures the Celery application instance that will be used
for distributed task processing. It includes configuration loading, task autodiscovery,
and signal handlers for monitoring.
"""

import os
import logging
from celery import Celery
from celery.signals import (
    task_prerun,
    task_postrun, 
    task_failure,
    worker_ready,
    worker_shutdown,
)

from peakflow_tasks.config import get_celery_config, get_settings


logger = logging.getLogger(__name__)


def create_celery_app() -> Celery:
    """
    Create and configure Celery application.
    
    Returns:
        Configured Celery application instance
    """
    # Get configuration
    config = get_celery_config()
    settings = get_settings()
    
    # Create Celery app
    app = Celery("peakflow_tasks")
    
    # Update configuration
    app.config_from_object(config)
    
    # Auto-discover tasks
    app.autodiscover_tasks([
        "peakflow_tasks.tasks.garmin",
        "peakflow_tasks.tasks.processing",
        "peakflow_tasks.tasks.storage", 
        "peakflow_tasks.tasks.workflows"
    ])
    
    # Setup logging
    _setup_logging(settings.debug)
    
    # Register signal handlers
    _register_signal_handlers()
    
    logger.info("✅ Celery application initialized successfully")
    return app


def _setup_logging(debug: bool = False) -> None:
    """
    Setup logging configuration for Celery tasks.
    
    Args:
        debug: Enable debug level logging
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Configure specific loggers
    loggers = [
        "peakflow_tasks",
        "celery.app.trace", 
        "celery.worker",
        "celery.task",
    ]
    
    for logger_name in loggers:
        log = logging.getLogger(logger_name)
        log.setLevel(log_level)


def _register_signal_handlers() -> None:
    """Register Celery signal handlers for monitoring and logging."""
    
    @task_prerun.connect
    def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Log task start."""
        logger.info(f"🚀 Task {task.name} [{task_id}] started")
        logger.debug(f"Task args: {args}, kwargs: {kwargs}")

    @task_postrun.connect  
    def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                            retval=None, state=None, **kwds):
        """Log task completion."""
        logger.info(f"✅ Task {task.name} [{task_id}] completed with state: {state}")

    @task_failure.connect
    def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
        """Log task failure."""
        logger.error(f"❌ Task {sender.name} [{task_id}] failed: {exception}")
        logger.debug(f"Traceback: {traceback}")

    @worker_ready.connect
    def worker_ready_handler(sender=None, **kwds):
        """Log worker ready."""
        logger.info(f"🔄 Worker {sender.hostname} is ready")

    @worker_shutdown.connect  
    def worker_shutdown_handler(sender=None, **kwds):
        """Log worker shutdown."""
        logger.info(f"🛑 Worker {sender.hostname} is shutting down")


# Create the Celery app instance
celery_app = create_celery_app()


# For backward compatibility and ease of import
app = celery_app