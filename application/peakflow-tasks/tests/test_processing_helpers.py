"""
Unit tests for FIT processing helper functions.
"""

import pytest
from unittest.mock import patch
from pathlib import Path

from peakflow_tasks.tasks.processing import (
    detect_fit_file_type,
    process_fit_file_helper
)
from peakflow_tasks.exceptions import FitProcessingError


class TestProcessingHelpers:
    """Test suite for processing helper functions."""

    def test_detect_fit_file_type_activity(self):
        """Test detection of activity files."""
        assert detect_fit_file_type('/path/to/123_ACTIVITY.fit') == 'activity'
        assert detect_fit_file_type('/path/to/456_activity.fit') == 'activity'
        assert detect_fit_file_type('/path/to/regular_file.fit') == 'activity'

    def test_detect_fit_file_type_health(self):
        """Test detection of health/wellness files."""
        assert detect_fit_file_type('/path/to/WELLNESS_123.fit') == 'health'
        assert detect_fit_file_type('/path/to/SLEEP_data.fit') == 'health'
        assert detect_fit_file_type('/path/to/HRV_metrics.fit') == 'health'
        assert detect_fit_file_type('/path/to/MONITORING.fit') == 'health'
        assert detect_fit_file_type('/path/to/BODY_BATTERY.fit') == 'health'
        assert detect_fit_file_type('/path/to/STRESS_levels.fit') == 'health'
        assert detect_fit_file_type('/path/to/HEALTH_data.fit') == 'health'
        assert detect_fit_file_type('/path/to/METRICS_data.fit') == 'health'

    @patch('peakflow_tasks.tasks.processing.Path')
    def test_process_fit_file_helper_activity(self, mock_path):
        """Test helper function for activity files."""
        mock_path.return_value.exists.return_value = True
        
        # Test activity file detection and signature creation
        sig = process_fit_file_helper('/path/to/123_ACTIVITY.fit', 'test_user', '123')
        
        assert sig.task == 'peakflow_tasks.tasks.processing.process_activity_fit_file'
        assert sig.args == ('/path/to/123_ACTIVITY.fit', 'test_user', '123', False)

    @patch('peakflow_tasks.tasks.processing.Path')  
    def test_process_fit_file_helper_health(self, mock_path):
        """Test helper function for health files."""
        # Mock both exists() and name attribute properly
        mock_path_instance = mock_path.return_value
        mock_path_instance.exists.return_value = True
        mock_path_instance.name = 'WELLNESS_123.fit'
        
        # Test health file detection and signature creation
        sig = process_fit_file_helper('/path/to/WELLNESS_123.fit', 'test_user')
        
        assert sig.task == 'peakflow_tasks.tasks.processing.process_health_fit_file'
        assert sig.args == ('/path/to/WELLNESS_123.fit', 'test_user')

    def test_process_fit_file_helper_missing_file(self):
        """Test helper function with missing file."""
        with pytest.raises(FileNotFoundError, match="FIT file not found"):
            process_fit_file_helper('/nonexistent/file.fit', 'test_user', '123')

    @patch('peakflow_tasks.tasks.processing.Path')
    def test_process_fit_file_helper_missing_activity_id(self, mock_path):
        """Test helper function with missing activity ID for activity file."""
        mock_path.return_value.exists.return_value = True
        
        with pytest.raises(FitProcessingError, match="Activity ID is required for activity FIT files"):
            process_fit_file_helper('/path/to/123_ACTIVITY.fit', 'test_user')

    @patch('peakflow_tasks.tasks.processing.Path')
    def test_process_fit_file_helper_no_auto_detect_missing_id(self, mock_path):
        """Test helper function with auto-detection disabled and missing activity ID.""" 
        mock_path.return_value.exists.return_value = True
        
        with pytest.raises(FitProcessingError, match="Activity ID is required when auto-detection is disabled"):
            process_fit_file_helper('/path/to/some_file.fit', 'test_user', auto_detect_type=False)

    @patch('peakflow_tasks.tasks.processing.Path')
    def test_process_fit_file_helper_validate_only(self, mock_path):
        """Test helper function with validate_only flag."""
        mock_path.return_value.exists.return_value = True
        
        sig = process_fit_file_helper('/path/to/123_ACTIVITY.fit', 'test_user', '123', validate_only=True)
        
        assert sig.task == 'peakflow_tasks.tasks.processing.process_activity_fit_file'
        assert sig.args == ('/path/to/123_ACTIVITY.fit', 'test_user', '123', True)
