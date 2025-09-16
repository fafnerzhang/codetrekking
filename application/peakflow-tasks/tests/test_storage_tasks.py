"""
Unit tests for storage tasks.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from peakflow_tasks.tasks.storage import (
    bulk_index_fitness_data,
    cleanup_old_data,
    ensure_elasticsearch_indices
)
from peakflow_tasks.exceptions import StorageError, ValidationError


class TestStorageTasks:
    """Test suite for storage management tasks."""
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_bulk_index_fitness_data_success(self, mock_config, mock_storage_class):
        """Test successful bulk indexing of fitness data."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_result = Mock()
        mock_result.success_count = 800
        mock_result.failed_count = 0
        mock_result.errors = []
        mock_storage.bulk_index.return_value = mock_result
        mock_storage_class.return_value = mock_storage
        
        # Test data
        documents = [
            {'activity_id': f'{i}', 'user_id': 'test_user', 'timestamp': datetime.now().isoformat()}
            for i in range(1000)
        ]
        
        # Execute task
        result = bulk_index_fitness_data(documents, 'session', batch_size=200)
        
        # Assertions
        assert result['data_type'] == 'session'
        assert result['total_documents'] == 1000
        assert result['successful_documents'] == 4000  # 5 batches * 800 each
        assert result['failed_documents'] == 0
        assert result['batch_size'] == 200
        assert len(result['batch_results']) == 5  # 1000 docs / 200 batch size
        
        # Verify function calls
        mock_storage.initialize.assert_called_once()
        assert mock_storage.bulk_index.call_count == 5
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_bulk_index_fitness_data_with_failures(self, mock_config, mock_storage_class):
        """Test bulk indexing with some failures."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_result = Mock()
        mock_result.success_count = 80
        mock_result.failed_count = 20
        mock_result.errors = ['Document validation failed']
        mock_storage.bulk_index.return_value = mock_result
        mock_storage_class.return_value = mock_storage
        
        # Test data
        documents = [
            {'activity_id': f'{i}', 'user_id': 'test_user'}
            for i in range(100)
        ]
        
        # Execute task
        result = bulk_index_fitness_data(documents, 'record')
        
        # Assertions
        assert result['successful_documents'] == 80
        assert result['failed_documents'] == 20
        assert len(result['batch_results']) == 1
        assert result['batch_results'][0]['errors'] == ['Document validation failed']
    
    def test_bulk_index_fitness_data_invalid_type(self):
        """Test bulk indexing with invalid data type."""
        documents = [{'test': 'data'}]
        
        with pytest.raises(StorageError, match="Bulk indexing failed: Invalid data type: invalid_type"):
            bulk_index_fitness_data(documents, 'invalid_type')
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_bulk_index_fitness_data_storage_error(self, mock_config, mock_storage_class):
        """Test bulk indexing with storage error."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_storage_class.side_effect = Exception("Elasticsearch connection failed")
        
        documents = [{'test': 'data'}]
        
        # Execute and assert
        with pytest.raises(StorageError, match="Bulk indexing failed: Elasticsearch connection failed"):
            bulk_index_fitness_data(documents, 'session')
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_cleanup_old_data_success(self, mock_config, mock_storage_class):
        """Test successful cleanup of old data."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        # Mock search results for each data type
        mock_storage.search.side_effect = [
            [{'_id': 'session_1'}, {'_id': 'session_2'}],  # Sessions
            [{'_id': 'record_1'}, {'_id': 'record_2'}, {'_id': 'record_3'}],  # Records
            [{'_id': 'lap_1'}]  # Laps
        ]
        mock_storage.delete_document.return_value = True
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = cleanup_old_data('test_user', days_to_keep=30)
        
        # Assertions
        assert result['user_id'] == 'test_user'
        assert result['days_to_keep'] == 30
        assert result['total_deleted'] == 6  # 2 + 3 + 1
        assert 'session' in result['documents_deleted']
        assert 'record' in result['documents_deleted']
        assert 'lap' in result['documents_deleted']
        assert result['documents_deleted']['session'] == 2
        assert result['documents_deleted']['record'] == 3
        assert result['documents_deleted']['lap'] == 1
        
        # Verify function calls
        mock_storage.initialize.assert_called_once()
        assert mock_storage.search.call_count == 3
        assert mock_storage.delete_document.call_count == 6
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_cleanup_old_data_no_old_data(self, mock_config, mock_storage_class):
        """Test cleanup when no old data exists."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.search.return_value = []  # No old data found
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = cleanup_old_data('test_user', days_to_keep=365)
        
        # Assertions
        assert result['total_deleted'] == 0
        assert all(count == 0 for count in result['documents_deleted'].values())
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_cleanup_old_data_partial_deletion_failure(self, mock_config, mock_storage_class):
        """Test cleanup with some deletion failures."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.search.side_effect = [
            [{'_id': 'session_1'}, {'_id': 'session_2'}],  # Sessions
            [],  # No records
            []   # No laps
        ]
        # First deletion succeeds, second fails
        mock_storage.delete_document.side_effect = [True, False]
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = cleanup_old_data('test_user', days_to_keep=90)
        
        # Assertions
        assert result['total_deleted'] == 1  # Only one successful deletion
        assert result['documents_deleted']['session'] == 1
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_cleanup_old_data_search_error(self, mock_config, mock_storage_class):
        """Test cleanup with search error for one data type."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        # First search succeeds, second fails, third succeeds
        mock_storage.search.side_effect = [
            [{'_id': 'session_1'}],  # Sessions
            Exception("Search failed"),  # Records
            []  # Laps
        ]
        mock_storage.delete_document.return_value = True
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = cleanup_old_data('test_user')
        
        # Assertions
        assert result['total_deleted'] == 1
        assert result['documents_deleted']['session'] == 1
        assert result['documents_deleted']['record'] == 0  # Error case
        assert result['documents_deleted']['lap'] == 0
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_ensure_elasticsearch_indices_success(self, mock_config, mock_storage_class):
        """Test successful index creation."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.index_exists.return_value = False  # Indices don't exist
        mock_storage.create_index.return_value = True  # Creation succeeds
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = ensure_elasticsearch_indices()
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['indices_created']) == 4  # session, record, lap, user_indicator
        assert len(result['errors']) == 0
        assert 'fitness-session' in result['indices_created']
        assert 'fitness-record' in result['indices_created']
        assert 'fitness-lap' in result['indices_created']
        assert 'fitness-user-indicator' in result['indices_created']
        
        # Verify function calls
        mock_storage.initialize.assert_called_once()
        assert mock_storage.index_exists.call_count == 4
        assert mock_storage.create_index.call_count == 4
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_ensure_elasticsearch_indices_already_exist(self, mock_config, mock_storage_class):
        """Test index creation when indices already exist."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.index_exists.return_value = True  # Indices already exist
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = ensure_elasticsearch_indices()
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['indices_created']) == 0  # No new indices created
        assert len(result['errors']) == 0
        
        # Should not attempt to create indices
        mock_storage.create_index.assert_not_called()
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_ensure_elasticsearch_indices_force_recreate(self, mock_config, mock_storage_class):
        """Test forced index recreation."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.index_exists.return_value = True  # Indices exist
        mock_storage.delete_index.return_value = True  # Deletion succeeds
        mock_storage.create_index.return_value = True  # Recreation succeeds
        mock_storage_class.return_value = mock_storage
        
        # Execute task with force recreation
        result = ensure_elasticsearch_indices(force_recreate=True)
        
        # Assertions
        assert result['status'] == 'success'
        assert len(result['indices_created']) == 4
        assert len(result['indices_recreated']) == 4
        assert len(result['errors']) == 0
        
        # Verify deletion and creation calls
        assert mock_storage.delete_index.call_count == 4
        assert mock_storage.create_index.call_count == 4
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_ensure_elasticsearch_indices_creation_failures(self, mock_config, mock_storage_class):
        """Test index creation with some failures."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.index_exists.return_value = False
        # Alternate between success and failure
        mock_storage.create_index.side_effect = [True, False, True, False]
        mock_storage_class.return_value = mock_storage
        
        # Execute task
        result = ensure_elasticsearch_indices()
        
        # Assertions
        assert result['status'] == 'partial_success'
        assert len(result['indices_created']) == 2  # 2 succeeded
        assert len(result['errors']) == 2  # 2 failed
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_ensure_elasticsearch_indices_storage_error(self, mock_config, mock_storage_class):
        """Test index creation with storage initialization error."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        mock_storage_class.side_effect = Exception("Elasticsearch connection failed")
        
        # Execute and assert
        with pytest.raises(StorageError, match="Index management failed: Elasticsearch connection failed"):
            ensure_elasticsearch_indices()
    
    def test_bulk_index_fitness_data_empty_documents(self):
        """Test bulk indexing with empty document list."""
        with patch('peakflow_tasks.tasks.storage.ElasticsearchStorage') as mock_storage_class, \
             patch('peakflow_tasks.tasks.storage.get_elasticsearch_config', return_value={}):
            
            mock_storage = Mock()
            mock_storage_class.return_value = mock_storage
            
            result = bulk_index_fitness_data([], 'session')
            
            assert result['total_documents'] == 0
            assert result['successful_documents'] == 0
            assert result['failed_documents'] == 0
            assert len(result['batch_results']) == 0
            
            # Should not call bulk_index for empty list
            mock_storage.bulk_index.assert_not_called()
    
    @patch('peakflow_tasks.tasks.storage.ElasticsearchStorage')
    @patch('peakflow_tasks.tasks.storage.get_elasticsearch_config')
    def test_bulk_index_fitness_data_batch_error(self, mock_config, mock_storage_class):
        """Test bulk indexing with batch processing error."""
        # Setup mocks
        mock_config.return_value = {'hosts': ['localhost:9200']}
        
        mock_storage = Mock()
        mock_storage.bulk_index.side_effect = Exception("Batch processing failed")
        mock_storage_class.return_value = mock_storage
        
        documents = [{'test': 'data'}]
        
        # Execute task
        result = bulk_index_fitness_data(documents, 'session')
        
        # Should handle batch error gracefully
        assert result['successful_documents'] == 0
        assert result['failed_documents'] == 1
        assert len(result['batch_results']) == 1
        assert 'Batch processing failed' in result['batch_results'][0]['errors'][0]