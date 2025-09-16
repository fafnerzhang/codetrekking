"""
Unit tests for FIT processing tasks.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from peakflow_tasks.tasks.processing import (
    process_fit_file_helper,
    detect_fit_file_type,
    process_activity_fit_file, 
    process_health_fit_file,
    process_fit_file_batch, 
    validate_processed_data
)
from peakflow_tasks.exceptions import FitProcessingError, ValidationError


class TestProcessingTasks:
    """Test suite for FIT processing tasks."""
    
    @patch('peakflow_tasks.tasks.processing.Path')
    # NOTE: The following tests were for the old process_fit_file task which was removed
    # due to Celery synchronous blocking anti-pattern. The functionality is now 
    # handled by helper functions and direct task calls.
    
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

    @patch('peakflow_tasks.tasks.processing.Path')
    def test_process_fit_file_helper_activity(self, mock_path):
        """Test helper function for activity files."""
        mock_path.return_value.exists.return_value = True
        
        sig = process_fit_file_helper('/path/to/123_ACTIVITY.fit', 'test_user', '123')
        assert sig.task == 'peakflow_tasks.tasks.processing.process_activity_fit_file'

    @patch('peakflow_tasks.tasks.processing.Path')  
    def test_process_fit_file_helper_health(self, mock_path):
        """Test helper function for health files."""
        mock_path.return_value.exists.return_value = True
        
        sig = process_fit_file_helper('/path/to/WELLNESS_123.fit', 'test_user')
        assert sig.task == 'peakflow_tasks.tasks.processing.process_health_fit_file'

    # NOTE: Original process_fit_file tests removed due to task refactoring
    # The old process_fit_file task was removed to fix Celery synchronous blocking issues

    @patch('peakflow_tasks.tasks.processing.process_fit_file_helper')
    def test_process_fit_batch_success(self, mock_helper):
        """Test successful batch processing of FIT files."""
        # Setup mock to return task signatures that return expected results  
        mock_sig1 = Mock()
        mock_sig1.apply.return_value.get.return_value = {
            'status': 'completed',
            'successful_records': 1500,
            'activity_id': '123'
        }
        mock_sig2 = Mock()
        mock_sig2.apply.return_value.get.return_value = {
            'status': 'completed', 
            'successful_records': 800,
            'activity_id': '124'
        }
        mock_helper.side_effect = [mock_sig1, mock_sig2]
        
        file_metadata_list = [
            {'file_path': '/storage/garmin/test_user/123_ACTIVITY.fit', 'activity_id': '123'},
            {'file_path': '/storage/garmin/test_user/124_ACTIVITY.fit', 'activity_id': '124'}
        ]
        
        # Execute task
        result = process_fit_file_batch(file_metadata_list, 'test_user')
        
        # Assertions
        assert result['user_id'] == 'test_user'
        assert result['total_files'] == 2
        assert result['processed_files'] == 2
        assert result['successful_files'] == 2
        assert result['failed_files'] == 0
        assert len(result['results']) == 2
        
        # Verify helper function calls
        assert mock_helper.call_count == 2
    
    @patch('peakflow_tasks.tasks.processing.process_fit_file_helper')
    def test_process_fit_batch_with_errors(self, mock_helper):
        """Test batch processing with some files failing.""" 
        # Setup mock - first succeeds, second fails
        def side_effect(*args, **kwargs):
            call_count = getattr(side_effect, 'call_count', 0)
            side_effect.call_count = call_count + 1
            
            mock_sig = Mock()
            if call_count == 0:
                mock_sig.apply.return_value.get.return_value = {
                    'status': 'completed',
                    'successful_records': 1500,
                    'activity_id': '123'
                }
            else:
                mock_sig.apply.return_value.get.side_effect = Exception("File processing failed")
            
            return mock_sig
        
        mock_helper.side_effect = side_effect
            
            if call_count == 0:
                mock_result = Mock()
                mock_result.get.return_value = {
                    'status': 'completed',
                    'successful_records': 1500,
                    'activity_id': '123'
                }
                return mock_result
            else:
                raise Exception("Processing failed for file 124")
        
        mock_process_fit.apply.side_effect = side_effect
        
        file_metadata_list = [
            {'file_path': '/storage/garmin/test_user/123_ACTIVITY.fit', 'activity_id': '123'},
            {'file_path': '/storage/garmin/test_user/124_ACTIVITY.fit', 'activity_id': '124'}
        ]
        
        # Execute task
        result = process_fit_file_batch(file_metadata_list, 'test_user')
        
        # Assertions
        assert result['total_files'] == 2
        assert result['processed_files'] == 2
        assert result['successful_files'] == 1
        assert result['failed_files'] == 1
        assert len(result['results']) == 2
        
        # Check that error was recorded
        failed_result = next(r for r in result['results'] if r.get('status') == 'failed')
        assert 'error' in failed_result
        assert failed_result['activity_id'] == '124'
    
    def test_process_fit_batch_empty_list(self):
        """Test batch processing with empty file list."""
        result = process_fit_file_batch([], 'test_user')
        
        assert result['total_files'] == 0
        assert result['processed_files'] == 0
        assert result['successful_files'] == 0
        assert result['failed_files'] == 0
        assert result['results'] == []
    
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_validate_processed_data_success(self, mock_config, mock_storage_class):
        """Test successful data validation."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.search.side_effect = [
            [{'activity_id': '123', 'user_id': 'test_user', '_id': 'session_123'}],  # Sessions
            [{'activity_id': '123', 'user_id': 'test_user', '_id': 'record_1'}],     # Records (first call)
            [{'activity_id': '123', 'user_id': 'test_user', '_id': f'record_{i}'} for i in range(100)],  # Records (count call)
            [{'activity_id': '123', 'user_id': 'test_user', '_id': 'lap_1'}]         # Laps
        ]
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = validate_processed_data('123', 'test_user')
        
        # Assertions
        assert result['activity_id'] == '123'
        assert result['user_id'] == 'test_user'
        assert result['status'] == 'valid'
        assert 'sessions' in result['data_types_found']
        assert 'records' in result['data_types_found']
        assert 'laps' in result['data_types_found']
        assert result['record_counts']['sessions'] == 1
        assert result['record_counts']['records'] == 100
        assert result['record_counts']['laps'] == 1
        assert len(result['validation_errors']) == 0
    
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_validate_processed_data_missing_data(self, mock_config, mock_storage_class):
        """Test validation with missing data types."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.search.side_effect = [
            [],  # No sessions
            [{'activity_id': '123', 'user_id': 'test_user'}],  # Has records
            [{'activity_id': '123', 'user_id': 'test_user', '_id': f'record_{i}'} for i in range(50)],  # Record count
            []   # No laps
        ]
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = validate_processed_data('123', 'test_user')
        
        # Assertions
        assert result['status'] == 'partially_valid'
        assert 'records' in result['data_types_found']
        assert 'sessions' not in result['data_types_found']
        assert 'laps' not in result['data_types_found']
        assert 'No session data found' in result['validation_errors']
        assert 'No lap data found' in result['validation_errors']
    
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_validate_processed_data_no_data(self, mock_config, mock_storage_class):
        """Test validation with no data found."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.search.return_value = []  # No data found
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = validate_processed_data('123', 'test_user')
        
        # Assertions
        assert result['status'] == 'invalid'
        assert len(result['data_types_found']) == 0
        assert len(result['validation_errors']) == 3  # No sessions, records, or laps
    
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_validate_processed_data_storage_error(self, mock_config, mock_storage_class):
        """Test validation with storage error."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_storage_class.side_effect = Exception("Storage connection failed")
        
        # Execute and assert
        with pytest.raises(ValidationError, match="Data validation failed: Storage connection failed"):
            validate_processed_data('123', 'test_user')
    
    @patch('peakflow_tasks.tasks.processing.Path')
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.ActivityProcessor')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_process_fit_file_validate_only(self, mock_config, mock_processor_class,
                                           mock_storage_class, mock_path):
        """Test FIT file processing in validation-only mode."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_path.return_value.exists.return_value = True
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_processor = Mock()
        mock_result = Mock()
        mock_result.status.value = 'completed'
        mock_result.successful_records = 0  # No records processed in validation mode
        mock_result.failed_records = 0
        mock_result.total_records = 1500
        mock_result.processing_time = 5.0
        mock_result.errors = []
        mock_result.warnings = []
        mock_result.metadata = {'sport_type': 'running'}
        mock_processor.process.return_value = mock_result
        mock_processor_class.return_value = mock_processor
        
        # Execute task in validation mode
        result = process_fit_file(
            '/storage/garmin/test_user/123_ACTIVITY.fit',
            'test_user',
            '123',
            validate_only=True
        )
        
        # Assertions
        assert result['status'] == 'completed'
        assert result['total_records'] == 1500
    
    @patch('peakflow_tasks.tasks.processing.Path')
    @patch('peakflow_tasks.tasks.processing.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.processing.ActivityProcessor')
    @patch('peakflow_tasks.tasks.processing.get_elasticsearch_config')
    def test_process_fit_file_partial_success(self, mock_config, mock_processor_class,
                                             mock_storage_class, mock_path):
        """Test FIT file processing with partial success."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_path.return_value.exists.return_value = True
        
        mock_storage = Mock()
        mock_storage_class.return_value = mock_storage
        
        mock_processor = Mock()
        mock_result = Mock()
        mock_result.status.value = 'partially_completed'
        mock_result.successful_records = 1200
        mock_result.failed_records = 300
        mock_result.total_records = 1500
        mock_result.processing_time = 45.2
        mock_result.errors = ['Some records failed to parse']
        mock_result.warnings = ['GPS data quality issues']
        mock_result.metadata = {'sport_type': 'cycling'}
        mock_processor.process.return_value = mock_result
        mock_processor_class.return_value = mock_processor
        
        # Analytics task removed from processing
        
        # Execute task
        result = process_fit_file(
            '/storage/garmin/test_user/123_ACTIVITY.fit',
            'test_user',
            '123'
        )
        
        # Assertions
        assert result['status'] == 'partially_completed'
        assert result['successful_records'] == 1200
        assert result['failed_records'] == 300
        assert len(result['errors']) == 1
        assert len(result['warnings']) == 1
        
        # Analytics should still be queued for partial success
        # Analytics task call removed