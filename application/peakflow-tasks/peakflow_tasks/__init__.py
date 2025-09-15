"""
PeakFlow Tasks - Distributed task processing for CodeTrekking fitness data pipeline.

This package provides Celery-based task processing for fitness data operations including:
- Garmin data download and processing
- FIT file analysis and storage
- Analytics generation
- Data pipeline orchestration

Author: CodeTrekking Team
License: MIT
"""

__version__ = "0.1.0"
__author__ = "CodeTrekking Team"

from peakflow_tasks.celery_app import celery_app

__all__ = ["celery_app"]