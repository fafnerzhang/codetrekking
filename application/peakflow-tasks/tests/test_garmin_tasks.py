"""
Unit tests for Garmin tasks.
"""

import pytest
import tempfile
import os
import json
from pathlib import Path
from unittest.mock import Mock, patch

from peakflow_tasks.tasks.garmin import download_garmin_daily_data
from peakflow_tasks.exceptions import GarminDownloadError, ConfigurationError


class TestGarminTasks:
    """Test suite for Garmin download tasks."""
    
    @patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials')
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    @patch('peakflow_tasks.tasks.garmin.get_database')
    @patch('peakflow_tasks.tasks.garmin._get_existing_activity_ids')
    @patch('peakflow_tasks.tasks.garmin.process_fit_file_helper')
    def test_download_garmin_daily_data_success(self, mock_process, mock_existing, 
                                               mock_database, mock_credential_service_class, mock_create_client):
        """Test successful Garmin data download."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Setup test paths using temporary directory
            test_storage_path = Path(temp_dir) / 'garmin' / 'test_user'
            
            # Setup database and credential service mocks
            mock_db = Mock()
            mock_credential_service = Mock()
            mock_credential_service.get_credentials_sync.return_value = ('test_user', 'test_pass')
            mock_credential_service_class.return_value = mock_credential_service
            mock_database.return_value = mock_db
            
            # Setup other mocks
            mock_existing.return_value = ['existing_123']
            
            mock_client = Mock()
            mock_client.download_daily_data.return_value = [
                {
                    'activity_id': '123',
                    'file_path': str(test_storage_path / '123_ACTIVITY.fit'),
                    'file_name': '123_ACTIVITY.fit',
                    'file_size': 12345,
                    'download_date': '2024-01-01T07:30:00'
                },
                {
                    'activity_id': '124',
                    'file_path': str(test_storage_path / '124_ACTIVITY.fit'),
                    'file_name': '124_ACTIVITY.fit',
                    'file_size': 23456,
                    'download_date': '2024-01-01T08:30:00'
                }
            ]
            mock_create_client.return_value = mock_client
            
            # Mock the helper to return a mock task signature
            mock_task_signature = Mock()
            mock_task_signature.delay = Mock()
            mock_process.return_value = mock_task_signature

            # Mock the output directory creation to use temp directory
            with patch('peakflow_tasks.tasks.garmin.os.makedirs') as mock_task_makedirs:
                mock_task_makedirs.return_value = None
        
                # Execute task
                result = download_garmin_daily_data('test_user', '2024-01-01', 1)
                
                # Assertions
                assert result['status'] == 'completed'
                assert result['total_activities'] == 2
                assert result['user_id'] == 'test_user'
                assert result['start_date'] == '2024-01-01'
                assert result['days'] == 1
                assert len(result['activities']) == 2
                assert 'download_time' in result
                
                # Verify function calls
                mock_credential_service_class.assert_called_once_with(mock_db)
                mock_credential_service.get_credentials_sync.assert_called_once_with('test_user')
                mock_create_client.assert_called_once_with('test_user', 'test_user', 'test_pass')
                mock_existing.assert_called_once_with('test_user', '2024-01-01', 1)
                
                # Verify processing tasks were queued
                assert mock_task_signature.delay.call_count == 2
                assert mock_process.call_count == 2
    
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    @patch('peakflow_tasks.tasks.garmin.get_database')
    @patch('peakflow_tasks.tasks.garmin.os.makedirs')
    def test_download_garmin_invalid_config(self, mock_makedirs, mock_database, mock_credential_service_class):
        """Test download with invalid Garmin configuration."""
        # Setup mocks for missing credentials
        mock_db = Mock()
        mock_credential_service = Mock()
        mock_credential_service.get_credentials_sync.return_value = (None, None)  # No credentials found
        mock_credential_service_class.return_value = mock_credential_service
        mock_database.return_value = mock_db
        
        # Execute and assert - the task wraps the ConfigurationError in a GarminDownloadError
        with pytest.raises(GarminDownloadError, match="Download failed: Failed to retrieve Garmin credentials: No Garmin credentials found for user invalid_user"):
            download_garmin_daily_data('invalid_user', '2024-01-01', 1)
    
    @patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials')
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    @patch('peakflow_tasks.tasks.garmin.get_database')
    def test_download_garmin_client_error(self, mock_database, mock_credential_service_class, mock_create_client):
        """Test download with Garmin client error."""
        # Setup database and credential service mocks
        mock_db = Mock()
        mock_credential_service = Mock()
        mock_credential_service.get_credentials_sync.return_value = ('test_user', 'test_pass')
        mock_credential_service_class.return_value = mock_credential_service
        mock_database.return_value = mock_db
        
        # Setup client error
        mock_create_client.side_effect = Exception("Connection failed")
        
        # Execute and assert
        with pytest.raises(GarminDownloadError, match="Download failed: Connection failed"):
            download_garmin_daily_data('test_user', '2024-01-01', 1)
    
    @patch('peakflow_tasks.tasks.garmin.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.garmin.get_elasticsearch_config')
    def test_get_existing_activity_ids_success(self, mock_config, mock_storage_class):
        """Test getting existing activity IDs from Elasticsearch."""
        from peakflow_tasks.tasks.garmin import _get_existing_activity_ids
        
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_storage = Mock()
        mock_storage.search.return_value = [
            {'activity_id': '123', 'user_id': 'test_user'},
            {'activity_id': '124', 'user_id': 'test_user'},
            {'no_activity_id': 'should_be_filtered'}
        ]
        mock_storage_class.return_value = mock_storage
        
        # Execute function
        result = _get_existing_activity_ids('test_user', '2024-01-01', 7)
        
        # Assertions
        assert result == ['123', '124']
        mock_storage.initialize.assert_called_once()
        mock_storage.search.assert_called_once()
    
    @patch('peakflow_tasks.tasks.garmin.ElasticsearchStorage')
    def test_get_existing_activity_ids_error(self, mock_storage_class):
        """Test getting existing activity IDs with Elasticsearch error."""
        from peakflow_tasks.tasks.garmin import _get_existing_activity_ids
        
        # Setup mock
        mock_storage_class.side_effect = Exception("Elasticsearch connection failed")
        
        # Execute function
        result = _get_existing_activity_ids('test_user', '2024-01-01', 7)
        
        # Should return empty list on error
        assert result == []
    
    def test_download_garmin_daily_data_no_activities(self):
        """Test download when no new activities are found."""
        with patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials') as mock_create_client, \
             patch('peakflow_tasks.tasks.garmin.GarminCredentialService') as mock_credential_service_class, \
             patch('peakflow_tasks.tasks.garmin.get_database') as mock_database, \
             patch('peakflow_tasks.tasks.garmin._get_existing_activity_ids', return_value=[]), \
             patch('peakflow_tasks.tasks.garmin.os.makedirs'):
            
            # Setup database and credential service mocks
            mock_db = Mock()
            mock_credential_service = Mock()
            mock_credential_service.get_credentials_sync.return_value = ('test_user', 'test_pass')
            mock_credential_service_class.return_value = mock_credential_service
            mock_database.return_value = mock_db
            
            mock_client = Mock()
            mock_client.download_daily_data.return_value = []  # No activities
            mock_create_client.return_value = mock_client
            
            result = download_garmin_daily_data('test_user', '2024-01-01', 1)
            
            assert result['status'] == 'completed'
            assert result['total_activities'] == 0
            assert result['activities'] == []
    
    @patch('peakflow_tasks.tasks.garmin.process_fit_file_helper')
    @patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials')
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    @patch('peakflow_tasks.tasks.garmin.get_database')
    def test_download_garmin_daily_data_with_errors(self, mock_database, mock_credential_service_class, mock_create_client, mock_process):
        """Test download when some activities have errors."""
        # Setup database and credential service mocks
        mock_db = Mock()
        mock_credential_service = Mock()
        mock_credential_service.get_credentials_sync.return_value = ('test_user', 'test_pass')
        mock_credential_service_class.return_value = mock_credential_service
        mock_database.return_value = mock_db
        
        mock_client = Mock()
        # Use relative path for test
        test_file_path = str(Path.cwd() / 'test_storage' / 'garmin' / 'test_user' / '123_ACTIVITY.fit')
        mock_client.download_daily_data.return_value = [
            {
                'activity_id': '123',
                'file_path': test_file_path,
                'file_name': '123_ACTIVITY.fit',
                'file_size': 12345,
                'download_date': '2024-01-01T07:30:00'
            },
            {
                'error': 'Failed to download activity 124',
                'activity_id': '124'
            }
        ]
        mock_create_client.return_value = mock_client
        
        # Mock the helper to return a mock task signature
        mock_task_signature = Mock()
        mock_task_signature.delay = Mock()
        mock_process.return_value = mock_task_signature
        
        with patch('peakflow_tasks.tasks.garmin._get_existing_activity_ids', return_value=[]), \
             patch('peakflow_tasks.tasks.garmin.os.makedirs'):
            
            result = download_garmin_daily_data('test_user', '2024-01-01', 1)
            
            assert result['status'] == 'completed'
            assert result['total_activities'] == 2
            assert len(result['activities']) == 2
            
            # Should only queue processing for successful download (only 1 success)
            mock_task_signature.delay.assert_called_once()
            mock_process.assert_called_once()
    
    def test_download_garmin_daily_data_parameter_validation(self):
        """Test parameter validation for download task."""
        # Test with invalid date format
        with patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials') as mock_create_client, \
             patch('peakflow_tasks.tasks.garmin.GarminCredentialService') as mock_credential_service_class, \
             patch('peakflow_tasks.tasks.garmin.get_database') as mock_database, \
             patch('peakflow_tasks.tasks.garmin.os.makedirs'), \
             patch('peakflow_tasks.tasks.garmin._get_existing_activity_ids', return_value=[]):
            
            # Setup database and credential service mocks
            mock_db = Mock()
            mock_credential_service = Mock()
            mock_credential_service.get_credentials_sync.return_value = ('test_user', 'test_pass')
            mock_credential_service_class.return_value = mock_credential_service
            mock_database.return_value = mock_db
            
            with pytest.raises((ValueError, GarminDownloadError)):
                download_garmin_daily_data('test_user', 'invalid-date', 1)
    
