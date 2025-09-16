"""
Minimal tests for the garmin_sync workflow.

Tests the simplified Garmin sync workflow that checks existing data,
downloads new data, processes it, and stores to Elasticsearch.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

from peakflow_tasks.tasks.workflows import garmin_sync_workflow
from peakflow_tasks.exceptions import WorkflowError


class TestGarminSyncWorkflow:
    """Test suite for the garmin_sync workflow."""

    @patch('peakflow_tasks.tasks.workflows.get_settings')
    @patch('peakflow_tasks.tasks.workflows.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.workflows._get_existing_activity_ids')
    @patch('peakflow_tasks.tasks.workflows._create_garmin_client')
    @patch('peakflow_tasks.tasks.workflows.ActivityProcessor')
    @patch('peakflow_tasks.tasks.workflows.HealthProcessor')
    @patch('peakflow_tasks.tasks.workflows._find_health_files')
    def test_garmin_sync_success(self, mock_find_health, mock_health_proc, mock_activity_proc,
                                mock_create_client, mock_get_existing, mock_es_storage, mock_settings):
        """Test successful garmin sync workflow."""
        
        # Setup settings mock
        mock_settings_obj = Mock()
        mock_settings_obj.elasticsearch.host = "localhost:9200"
        mock_settings_obj.elasticsearch.username = "elastic"
        mock_settings_obj.elasticsearch.password = "changeme"
        mock_settings_obj.elasticsearch.timeout = 30
        mock_settings_obj.elasticsearch.verify_certs = False
        mock_settings_obj.peakflow.garmin_data_path = Path("/tmp/garmin")
        mock_settings.return_value = mock_settings_obj
        
        # Setup storage mock
        mock_storage = Mock()
        mock_es_storage.return_value = mock_storage
        
        # Setup existing activity IDs
        mock_get_existing.return_value = {'existing_123', 'existing_456'}
        
        # Setup Garmin client mock
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Setup download generator with new files
        downloaded_files = [
            {'file_path': '/tmp/garmin/user1/activity_789.fit', 'activity_id': '789'},
            {'file_path': '/tmp/garmin/user1/activity_101.fit', 'activity_id': '101'}
        ]
        mock_client.download_daily_data.return_value = iter(downloaded_files)
        
        # Setup activity processor
        mock_activity_processor = Mock()
        mock_activity_result = Mock()
        mock_activity_result.successful_records = 1500
        mock_activity_result.errors = []
        mock_activity_processor.process.return_value = mock_activity_result
        mock_activity_proc.return_value = mock_activity_processor
        
        # Setup health processor
        mock_health_processor = Mock()
        mock_health_proc.return_value = mock_health_processor
        
        # Setup health files
        mock_find_health.return_value = [Path('/tmp/garmin/user1/wellness.fit')]
        
        # Mock asyncio.run for health processing
        with patch('asyncio.run') as mock_asyncio:
            mock_asyncio.return_value = True
            
            # Mock Path.exists() to return True
            with patch.object(Path, 'exists', return_value=True):
                # Mock _is_activity_file to return True for activity files
                with patch('peakflow_tasks.tasks.workflows._is_activity_file', return_value=True):
                    # Execute workflow
                    result = garmin_sync_workflow('user1', 30)
        
        # Verify result structure
        assert result['status'] == 'completed'
        assert result['user_id'] == 'user1'
        assert result['days'] == 30
        assert result['activities_processed'] == 2
        assert result['health_files_processed'] == 1
        assert result['existing_activities_skipped'] == 2
        assert 'duration_seconds' in result
        assert 'completed_at' in result
        
        # Verify key function calls
        mock_storage.initialize.assert_called_once()
        mock_get_existing.assert_called_once_with(mock_storage, 'user1', 30)
        mock_create_client.assert_called_once_with('user1', mock_settings_obj)
        mock_client.download_daily_data.assert_called_once()
        assert mock_activity_processor.process.call_count == 2
        mock_asyncio.assert_called_once()

    @patch('peakflow_tasks.tasks.workflows.get_settings')
    @patch('peakflow_tasks.tasks.workflows.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.workflows._get_existing_activity_ids')
    @patch('peakflow_tasks.tasks.workflows._create_garmin_client')
    def test_garmin_sync_no_new_data(self, mock_create_client, mock_get_existing, 
                                   mock_es_storage, mock_settings):
        """Test garmin sync when no new data is available."""
        
        # Setup mocks
        mock_settings_obj = Mock()
        mock_settings_obj.elasticsearch.host = "localhost:9200"
        mock_settings_obj.peakflow.garmin_data_path = Path("/tmp/garmin")
        mock_settings.return_value = mock_settings_obj
        
        mock_storage = Mock()
        mock_es_storage.return_value = mock_storage
        
        mock_get_existing.return_value = set()
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        # Return empty iterator for no new files
        mock_client.download_daily_data.return_value = iter([])
        
        # Execute workflow
        result = garmin_sync_workflow('user1', 7)
        
        # Verify result
        assert result['status'] == 'completed'
        assert result['message'] == 'No new data to process'
        assert result['activities_processed'] == 0
        assert result['health_files_processed'] == 0

    @patch('peakflow_tasks.tasks.workflows.get_settings')
    @patch('peakflow_tasks.tasks.workflows.ElasticsearchStorage')
    def test_garmin_sync_storage_failure(self, mock_es_storage, mock_settings):
        """Test garmin sync with storage initialization failure."""
        
        # Setup settings mock
        mock_settings.return_value = Mock()
        
        # Setup storage to fail initialization
        mock_storage = Mock()
        mock_storage.initialize.side_effect = Exception("Elasticsearch connection failed")
        mock_es_storage.return_value = mock_storage
        
        # Execute and verify exception
        with pytest.raises(WorkflowError, match="Garmin sync workflow failed"):
            garmin_sync_workflow('user1', 7)

    @patch('peakflow_tasks.tasks.workflows.get_settings')
    @patch('peakflow_tasks.tasks.workflows.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.workflows._get_existing_activity_ids')
    @patch('peakflow_tasks.tasks.workflows._create_garmin_client')
    def test_garmin_sync_client_creation_failure(self, mock_create_client, mock_get_existing,
                                                mock_es_storage, mock_settings):
        """Test garmin sync with Garmin client creation failure."""
        
        # Setup mocks
        mock_settings.return_value = Mock(peakflow=Mock(garmin_data_path=Path("/tmp")))
        mock_es_storage.return_value = Mock()
        mock_get_existing.return_value = set()
        
        # Setup client creation to fail
        mock_create_client.side_effect = WorkflowError("No credentials found for user")
        
        # Execute and verify exception
        with pytest.raises(WorkflowError, match="Garmin sync workflow failed"):
            garmin_sync_workflow('user1', 7)


class TestGarminSyncHelpers:
    """Test helper functions for garmin sync workflow."""

    @patch('peakflow_tasks.tasks.workflows.QueryFilter')
    def test_get_existing_activity_ids_success(self, mock_query_filter):
        """Test successful retrieval of existing activity IDs."""
        from peakflow_tasks.tasks.workflows import _get_existing_activity_ids
        
        # Setup mock storage
        mock_storage = Mock()
        mock_sessions = [
            {'activity_id': '123', 'user_id': 'user1'},
            {'activity_id': '456', 'user_id': 'user1'},
            {'activity_id': None, 'user_id': 'user1'}  # Should be filtered out
        ]
        mock_storage.search.return_value = mock_sessions
        
        # Setup query filter mock
        mock_filter = Mock()
        mock_query_filter.return_value = mock_filter
        
        # Execute function
        result = _get_existing_activity_ids(mock_storage, 'user1', 30)
        
        # Verify result
        assert result == {'123', '456'}
        mock_filter.add_term_filter.assert_called_with('user_id', 'user1')
        mock_filter.add_date_range.assert_called_once()

    def test_get_existing_activity_ids_failure(self):
        """Test _get_existing_activity_ids with storage failure."""
        from peakflow_tasks.tasks.workflows import _get_existing_activity_ids
        
        # Setup mock storage to fail
        mock_storage = Mock()
        mock_storage.search.side_effect = Exception("ES query failed")
        
        # Execute function - should not raise, just return empty set
        result = _get_existing_activity_ids(mock_storage, 'user1', 30)
        
        # Verify empty result
        assert result == set()

    @patch('peakflow_tasks.tasks.workflows.get_database')
    @patch('peakflow_tasks.tasks.workflows.GarminCredentialService')
    @patch('peakflow_tasks.tasks.workflows.GarminClient.create_from_config')
    def test_create_garmin_client_success(self, mock_create_client, mock_cred_service, mock_get_db):
        """Test successful Garmin client creation."""
        from peakflow_tasks.tasks.workflows import _create_garmin_client
        
        # Setup database and credential service mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_service = Mock()
        mock_service.get_credentials_sync.return_value = ('username', 'password')
        mock_cred_service.return_value = mock_service
        
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Setup settings
        mock_settings = Mock()
        mock_settings.peakflow.garmin_config_path = "/tmp/config"
        
        # Execute function
        result = _create_garmin_client('user1', mock_settings)
        
        # Verify result
        assert result == mock_client
        mock_service.get_credentials_sync.assert_called_once_with('user1')
        mock_db.close.assert_called_once()

    def test_is_activity_file(self):
        """Test activity file detection."""
        from peakflow_tasks.tasks.workflows import _is_activity_file
        
        assert _is_activity_file('/path/to/activity_123.fit') == True
        assert _is_activity_file('/path/to/wellness.fit') == False
        assert _is_activity_file('/path/to/sleep.fit') == False
        assert _is_activity_file('/path/to/activity_456.txt') == False

    def test_is_health_file(self):
        """Test health file detection."""
        from peakflow_tasks.tasks.workflows import _is_health_file
        
        assert _is_health_file('/path/to/wellness.fit') == True
        assert _is_health_file('/path/to/sleep.fit') == True
        assert _is_health_file('/path/to/hrv_data.fit') == True
        assert _is_health_file('/path/to/metrics.fit') == True
        assert _is_health_file('/path/to/monitoring.fit') == True
        assert _is_health_file('/path/to/activity_123.fit') == False

    def test_find_health_files(self):
        """Test health file discovery."""
        from peakflow_tasks.tasks.workflows import _find_health_files
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'glob') as mock_glob:
                with patch.object(Path, 'rglob') as mock_rglob:
                    # Setup mock file paths
                    sleep_files = [Path('/tmp/user1/sleep/sleep_data.fit')]
                    monitoring_files = [Path('/tmp/user1/monitoring/wellness.fit')]
                    
                    mock_glob.return_value = sleep_files
                    mock_rglob.return_value = monitoring_files
                    
                    # Mock _is_health_file to return True
                    with patch('peakflow_tasks.tasks.workflows._is_health_file', return_value=True):
                        result = _find_health_files(Path('/tmp/user1'))
                    
                    # Verify result includes both types
                    assert len(result) == 2
                    assert Path('/tmp/user1/sleep/sleep_data.fit') in result
                    assert Path('/tmp/user1/monitoring/wellness.fit') in result