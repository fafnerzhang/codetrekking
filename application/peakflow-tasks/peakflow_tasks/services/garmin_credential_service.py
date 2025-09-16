"""
Garmin Credential Service for PeakFlow Tasks.

This service handles retrieval and decryption of Garmin credentials from the database,
using the shared encryption module from PeakFlow core.
"""

import logging
import uuid
from typing import Tuple, Optional
from sqlmodel import Session, select

# Export EncryptionService at module level for testing
try:
    from peakflow.utils.encryption import EncryptionService
except ImportError:
    EncryptionService = None

logger = logging.getLogger(__name__)


class GarminCredentialService:
    """Service for retrieving Garmin credentials in PeakFlow Tasks."""
    
    def __init__(self, db: Session):
        """
        Initialize the credential service.
        
        Args:
            db: Database session for credential queries
        """
        self.db = db
        
        # Use shared encryption module from PeakFlow core (Phase 1)
        try:
            from peakflow.utils.encryption import EncryptionService
            self.encryption_service = EncryptionService()
        except ImportError:
            logger.error("Failed to import EncryptionService from peakflow.utils.encryption")
            raise ImportError(
                "Shared encryption module not available. "
                "Ensure Phase 1 (shared encryption infrastructure) is implemented in PeakFlow core."
            )
    
    async def get_credentials(self, user_id: str) -> Tuple[str, str]:
        """
        Retrieve and decrypt Garmin credentials from database.
        
        Args:
            user_id: User identifier (UUID as string)
            
        Returns:
            Tuple of (username, decrypted_password)
            
        Raises:
            ValueError: If no credentials found for user
            Exception: If decryption fails
        """
        try:
            # Import database model from local database module
            try:
                from ..database.models import UserGarminCredentials
            except ImportError:
                logger.warning("UserGarminCredentials model not found in expected location")
                raise ImportError(
                    "UserGarminCredentials model not available. "
                    "Ensure Phase 2 (database integration) is implemented."
                )
            
            # Convert string user_id to UUID if needed
            try:
                user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            except ValueError:
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Query database for user credentials using SQLModel select syntax
            statement = select(UserGarminCredentials).where(
                UserGarminCredentials.user_id == user_uuid
            )
            credential_record = self.db.exec(statement).first()
            
            if not credential_record:
                logger.error(f"No Garmin credentials found for user {user_id}")
                raise ValueError(f"No Garmin credentials found for user {user_id}")
            
            # Decrypt password using shared encryption service (from Phase 1)
            try:
                decrypted_password = self.encryption_service.decrypt(
                    credential_record.encrypted_password
                )
            except Exception as decrypt_error:
                logger.error(f"Failed to decrypt password for user {user_id}: {decrypt_error}")
                raise Exception(f"Failed to decrypt credentials: {decrypt_error}")
            
            logger.info(f"Successfully retrieved credentials for user {user_id}")
            return credential_record.garmin_username, decrypted_password
            
        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise
    
    def get_credentials_sync(self, user_id: str) -> Tuple[str, str]:
        """
        Synchronous version of get_credentials for use in Celery tasks.
        
        Args:
            user_id: User identifier (UUID as string)
            
        Returns:
            Tuple of (username, decrypted_password)
            
        Raises:
            ValueError: If no credentials found for user
            Exception: If decryption fails
        """
        try:
            # Import database model from local database module
            try:
                from ..database.models import UserGarminCredentials
            except ImportError:
                logger.warning("UserGarminCredentials model not found in expected location")
                raise ImportError(
                    "UserGarminCredentials model not available. "
                    "Ensure Phase 2 (database integration) is implemented."
                )
            
            # Convert string user_id to UUID if needed
            try:
                user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
            except ValueError:
                raise ValueError(f"Invalid user_id format: {user_id}")
            
            # Query database for user credentials using SQLModel select syntax
            statement = select(UserGarminCredentials).where(
                UserGarminCredentials.user_id == user_uuid
            )
            credential_record = self.db.exec(statement).first()
            
            if not credential_record:
                logger.error(f"No Garmin credentials found for user {user_id}")
                raise ValueError(f"No Garmin credentials found for user {user_id}")
            
            # Decrypt password using shared encryption service
            try:
                decrypted_password = self.encryption_service.decrypt(
                    credential_record.encrypted_password
                )
            except Exception as decrypt_error:
                logger.error(f"Failed to decrypt password for user {user_id}: {decrypt_error}")
                raise Exception(f"Failed to decrypt credentials: {decrypt_error}")
            
            logger.info(f"Successfully retrieved credentials for user {user_id}")
            return credential_record.garmin_username, decrypted_password
            
        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise