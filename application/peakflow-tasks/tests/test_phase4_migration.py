"""
Tests for Phase 4: PeakFlow Tasks Updates.

This module tests the Garmin credentials migration from file-based to database-backed
credential storage as defined in the migration plan Phase 4.
"""

import uuid
import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlmodel import Session

from peakflow_tasks.services.garmin_credential_service import GarminCredentialService
from peakflow_tasks.database.models import UserGarminCredentials
from peakflow_tasks.exceptions import ConfigurationError, GarminDownloadError


class TestGarminCredentialService:
    """Test the GarminCredentialService functionality."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock(spec=Session)
    
    @pytest.fixture
    def mock_encryption_service(self):
        """Create a mock encryption service."""
        mock_service = Mock()
        mock_service.decrypt.return_value = "decrypted_password"
        return mock_service
    
    @pytest.fixture
    def credential_service(self, mock_db_session, mock_encryption_service):
        """Create a credential service with mocked dependencies."""
        with patch('peakflow.utils.encryption.EncryptionService', 
                  return_value=mock_encryption_service):
            service = GarminCredentialService(mock_db_session)
            return service
    
    @pytest.fixture
    def sample_credential_record(self):
        """Create a sample credential record."""
        return UserGarminCredentials(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            garmin_username="testuser@example.com",
            encrypted_password="encrypted_password_data",
            encryption_version=1
        )
    
    def test_get_credentials_sync_success(self, credential_service, mock_db_session, sample_credential_record):
        """Test successful credential retrieval."""
        # Setup
        user_id = str(sample_credential_record.user_id)
        
        # Mock the SQLModel session.exec() method  
        mock_result = Mock()
        mock_result.first.return_value = sample_credential_record
        mock_db_session.exec.return_value = mock_result
        
        # Execute
        username, password = credential_service.get_credentials_sync(user_id)
        
        # Verify
        assert username == "testuser@example.com"
        assert password == "decrypted_password"
        mock_db_session.exec.assert_called_once()
    
    def test_get_credentials_sync_not_found(self, credential_service, mock_db_session):
        """Test credential retrieval when no credentials exist."""
        # Setup
        user_id = str(uuid.uuid4())
        
        # Mock the SQLModel session.exec() method to return no results
        mock_result = Mock()
        mock_result.first.return_value = None
        mock_db_session.exec.return_value = mock_result
        
        # Execute & Verify
        with pytest.raises(ValueError, match="No Garmin credentials found"):
            credential_service.get_credentials_sync(user_id)
    
    def test_get_credentials_sync_decryption_error(self, credential_service, mock_db_session, sample_credential_record):
        """Test credential retrieval with decryption error."""
        # Setup
        user_id = str(sample_credential_record.user_id)
        
        # Mock the SQLModel session.exec() method
        mock_result = Mock()
        mock_result.first.return_value = sample_credential_record
        mock_db_session.exec.return_value = mock_result
        
        # Reset the mock and set up the side effect
        credential_service.encryption_service.reset_mock()
        credential_service.encryption_service.decrypt.side_effect = Exception("Decryption failed")
        
        # Execute & Verify
        with pytest.raises(Exception, match="Failed to decrypt credentials"):
            credential_service.get_credentials_sync(user_id)
    
    def test_invalid_user_id_format(self, credential_service):
        """Test handling of invalid user ID format."""
        with pytest.raises(ValueError, match="Invalid user_id format"):
            credential_service.get_credentials_sync("invalid-uuid")


class TestGarminTaskUpdates:
    """Test the updated Garmin download task functionality."""
    
    @patch('peakflow_tasks.tasks.garmin.get_database')
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    @patch('peakflow_tasks.tasks.garmin.create_garmin_client_from_credentials')
    @patch('peakflow_tasks.tasks.garmin._get_existing_activity_ids')
    def test_download_garmin_daily_data_with_database_credentials(
        self, mock_get_existing, mock_create_client, mock_credential_service_class, mock_get_db
    ):
        """Test that the download task uses database credentials."""
        from peakflow_tasks.tasks.garmin import download_garmin_daily_data
        
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_credential_service = Mock()
        mock_credential_service.get_credentials_sync.return_value = ("testuser", "testpass")
        mock_credential_service_class.return_value = mock_credential_service
        
        mock_client = Mock()
        mock_client.download_daily_data.return_value = [
            {"activity_id": "123", "file_path": "/path/to/file.fit"}
        ]
        mock_create_client.return_value = mock_client
        
        mock_get_existing.return_value = []
        
        # Create a mock task instance
        task_instance = Mock()
        task_instance.update_state = Mock()
        
        # Execute
        with patch('peakflow_tasks.tasks.garmin.process_fit_file_helper') as mock_process:
            # Mock the helper to return a mock task signature
            mock_task_signature = Mock()
            mock_task_signature.delay = Mock()
            mock_process.return_value = mock_task_signature
            
            # Call the underlying function directly by accessing the raw function
            result = download_garmin_daily_data.run("user123", "2023-01-01", 1)
        
        # Verify database credential retrieval
        mock_get_db.assert_called_once()
        mock_credential_service_class.assert_called_once_with(mock_db)
        mock_credential_service.get_credentials_sync.assert_called_once_with("user123")
        
        # Verify client creation with credentials
        mock_create_client.assert_called_once_with("user123", "testuser", "testpass")
        
        # Verify database connection cleanup
        mock_db.close.assert_called_once()
    
    @patch('peakflow_tasks.tasks.garmin.get_database')
    @patch('peakflow_tasks.tasks.garmin.GarminCredentialService')
    def test_download_task_handles_credential_error(
        self, mock_credential_service_class, mock_get_db
    ):
        """Test that the download task handles credential retrieval errors."""
        from peakflow_tasks.tasks.garmin import download_garmin_daily_data
        
        # Setup mocks
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        mock_credential_service = Mock()
        mock_credential_service.get_credentials_sync.side_effect = ValueError("No credentials found")
        mock_credential_service_class.return_value = mock_credential_service
        
        # Create a mock task instance
        task_instance = Mock()
        task_instance.update_state = Mock()
        
        # Execute & Verify
        with pytest.raises(GarminDownloadError, match="Download failed: Failed to retrieve Garmin credentials"):
            # Call the underlying function directly
            download_garmin_daily_data.run("user123", "2023-01-01", 1)
        
        # Verify cleanup still occurs
        mock_db.close.assert_called_once()


class TestDatabaseConfiguration:
    """Test database configuration components."""
    
    def test_database_config_creation(self):
        """Test database configuration creation."""
        from peakflow_tasks.config import DatabaseConfig
        import os
        
        # Test with clean environment (no env vars)
        with patch.dict(os.environ, {}, clear=True):
            config = DatabaseConfig()
            assert config.host == "localhost"
            assert config.port == 5432
            assert config.database == "codetrekking"
            assert config.username == "codetrekking"
            assert config.password == "ChangeMe"
    
    def test_database_config_dict_conversion(self):
        """Test database configuration dictionary conversion."""
        from peakflow_tasks.config import DatabaseConfig
        import os
        
        # Test with explicit environment variable override
        with patch.dict(os.environ, {
            'POSTGRES_HOST': 'db.example.com',
            'POSTGRES_PORT': '5433',
            'POSTGRES_DB': 'testdb',
            'POSTGRES_USER': 'testuser',
            'POSTGRES_PASSWORD': 'testpass'
        }, clear=True):
            config = DatabaseConfig()
            
            config_dict = config.to_dict()
            expected_url = "postgresql://testuser:testpass@db.example.com:5433/testdb"
            
            assert config_dict['host'] == "db.example.com"
            assert config_dict['port'] == 5433
            assert config_dict['database'] == "testdb"
            assert config_dict['username'] == "testuser"
            assert config_dict['password'] == "testpass"
            assert config_dict['url'] == expected_url
    
    def test_get_database_config_function(self):
        """Test the get_database_config function."""
        from peakflow_tasks.config import get_database_config
        
        config = get_database_config()
        assert isinstance(config, dict)
        assert 'host' in config
        assert 'port' in config
        assert 'database' in config
        assert 'username' in config
        assert 'password' in config
        assert 'url' in config


class TestObsoleteTaskRemoval:
    """Test that obsolete tasks have been removed."""
    
    def test_setup_garmin_config_task_removed(self):
        """Test that the setup_garmin_config task has been removed."""
        import peakflow_tasks.tasks.garmin as garmin_tasks
        
        # Verify the task is not defined
        assert not hasattr(garmin_tasks, 'setup_garmin_config')
        
        # Verify it's not in task configuration
        assert 'setup_garmin_config' not in garmin_tasks.TASK_CONFIG
    
    def test_download_task_config_updated(self):
        """Test that task configuration only contains active tasks."""
        from peakflow_tasks.tasks.garmin import TASK_CONFIG
        
        # Should only contain the download task configuration
        assert len(TASK_CONFIG) == 1
        assert 'download_garmin_daily_data' in TASK_CONFIG
        assert 'setup_garmin_config' not in TASK_CONFIG


class TestDatabaseModels:
    """Test database model definitions."""
    
    def test_user_garmin_credentials_model(self):
        """Test the UserGarminCredentials model structure."""
        from peakflow_tasks.database.models import UserGarminCredentials
        
        # Test model creation
        credential = UserGarminCredentials(
            user_id=uuid.uuid4(),
            garmin_username="testuser",
            encrypted_password="encrypted_data",
            encryption_version=1
        )
        
        assert credential.garmin_username == "testuser"
        assert credential.encrypted_password == "encrypted_data"
        assert credential.encryption_version == 1
        assert credential.__tablename__ == "user_garmin_credentials"
    
    def test_model_repr(self):
        """Test the model string representation."""
        from peakflow_tasks.database.models import UserGarminCredentials
        
        user_id = uuid.uuid4()
        credential = UserGarminCredentials(
            user_id=user_id,
            garmin_username="testuser",
            encrypted_password="encrypted_data"
        )
        
        repr_str = repr(credential)
        assert f"user_id={user_id}" in repr_str
        assert "username=testuser" in repr_str


# Integration test markers
pytestmark = [
    pytest.mark.unit
]