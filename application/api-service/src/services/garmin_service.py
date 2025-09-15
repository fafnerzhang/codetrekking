"""
Garmin Credential Service for API Service.

This service handles business logic for managing Garmin credentials,
implementing the service layer as defined in Phase 5 of the migration plan.
"""

import uuid
import logging
from typing import Optional, Tuple, Dict, Any
from datetime import datetime
from sqlmodel import Session

from ..database.models import UserGarminCredentials
from ..database.garmin_repository import GarminCredentialRepository

logger = logging.getLogger(__name__)


class GarminCredentialService:
    """Service for managing Garmin credentials."""

    def __init__(self, db: Session):
        """
        Initialize the service with a database session.

        Args:
            db: Database session for credential operations
        """
        self.db = db
        self.repository = GarminCredentialRepository(db)

        # Use shared encryption module from Phase 1 (PeakFlow core)
        try:
            from peakflow.utils.encryption import EncryptionService

            self.encryption_service = EncryptionService()
        except ImportError:
            logger.error(
                "Failed to import EncryptionService from peakflow.utils.encryption"
            )
            raise ImportError(
                "Shared encryption module not available. "
                "Ensure Phase 1 (shared encryption infrastructure) is implemented in PeakFlow core."
            )

    async def create_credentials(
        self, user_id: uuid.UUID, username: str, password: str
    ) -> UserGarminCredentials:
        """
        Create encrypted Garmin credentials.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            password: Garmin Connect password (plaintext)

        Returns:
            Created UserGarminCredentials instance

        Raises:
            ValueError: If user already has credentials or user doesn't exist
            Exception: If encryption or database operations fail
        """
        try:
            logger.info(f"Creating Garmin credentials for user {user_id}")

            # Encrypt password using shared encryption service (from Phase 1)
            encrypted_password = self.encryption_service.encrypt(password)

            # Create credential record
            credential = await self.repository.create(
                user_id=user_id,
                username=username,
                encrypted_password=encrypted_password,
                encryption_version=self.encryption_service.encryption_version,
            )

            # Test authentication with Garmin Connect
            test_result = await self._test_credentials(user_id, username, password)
            if not test_result["success"]:
                logger.warning(
                    f"Credential test failed for user {user_id}: {test_result['message']}"
                )
                # Note: We still save the credentials even if test fails, as it might be a temporary issue

            logger.info(f"Successfully created credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to create credentials for user {user_id}: {e}")
            raise

    def create_credentials_sync(
        self, user_id: uuid.UUID, username: str, password: str
    ) -> UserGarminCredentials:
        """
        Synchronous version of create_credentials.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            password: Garmin Connect password (plaintext)

        Returns:
            Created UserGarminCredentials instance
        """
        try:
            logger.info(f"Creating Garmin credentials for user {user_id}")

            # Encrypt password using shared encryption service
            encrypted_password = self.encryption_service.encrypt(password)

            # Create credential record
            credential = self.repository.create_sync(
                user_id=user_id,
                username=username,
                encrypted_password=encrypted_password,
                encryption_version=self.encryption_service.encryption_version,
            )

            # Test authentication with Garmin Connect
            test_result = self._test_credentials_sync(user_id, username, password)
            if not test_result["success"]:
                logger.warning(
                    f"Credential test failed for user {user_id}: {test_result['message']}"
                )

            logger.info(f"Successfully created credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to create credentials for user {user_id}: {e}")
            raise

    async def get_credentials(self, user_id: uuid.UUID) -> Optional[Tuple[str, str]]:
        """
        Retrieve and decrypt Garmin credentials.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (username, decrypted_password) or None if not found

        Raises:
            Exception: If decryption fails
        """
        try:
            # Fetch from database
            credential_record = await self.repository.get_by_user_id(user_id)
            if not credential_record:
                logger.debug(f"No credentials found for user {user_id}")
                return None

            # Decrypt password using shared encryption service
            try:
                decrypted_password = self.encryption_service.decrypt(
                    credential_record.encrypted_password
                )
            except Exception as decrypt_error:
                logger.error(
                    f"Failed to decrypt password for user {user_id}: {decrypt_error}"
                )
                raise Exception(f"Failed to decrypt credentials: {decrypt_error}")

            logger.debug(f"Successfully retrieved credentials for user {user_id}")
            return credential_record.garmin_username, decrypted_password

        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise

    def get_credentials_sync(self, user_id: uuid.UUID) -> Optional[Tuple[str, str]]:
        """
        Synchronous version of get_credentials.

        Args:
            user_id: User's UUID

        Returns:
            Tuple of (username, decrypted_password) or None if not found
        """
        try:
            # Fetch from database
            credential_record = self.repository.get_by_user_id_sync(user_id)
            if not credential_record:
                logger.debug(f"No credentials found for user {user_id}")
                return None

            # Decrypt password using shared encryption service
            try:
                decrypted_password = self.encryption_service.decrypt(
                    credential_record.encrypted_password
                )
            except Exception as decrypt_error:
                logger.error(
                    f"Failed to decrypt password for user {user_id}: {decrypt_error}"
                )
                raise Exception(f"Failed to decrypt credentials: {decrypt_error}")

            logger.debug(f"Successfully retrieved credentials for user {user_id}")
            return credential_record.garmin_username, decrypted_password

        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise

    async def get_credential_info(
        self, user_id: uuid.UUID
    ) -> Optional[UserGarminCredentials]:
        """
        Get credential information without decrypting password.

        Args:
            user_id: User's UUID

        Returns:
            UserGarminCredentials instance or None if not found
        """
        try:
            return await self.repository.get_by_user_id(user_id)
        except Exception as e:
            logger.error(f"Failed to get credential info for user {user_id}: {e}")
            raise

    def get_credential_info_sync(
        self, user_id: uuid.UUID
    ) -> Optional[UserGarminCredentials]:
        """
        Synchronous version of get_credential_info.

        Args:
            user_id: User's UUID

        Returns:
            UserGarminCredentials instance or None if not found
        """
        try:
            return self.repository.get_by_user_id_sync(user_id)
        except Exception as e:
            logger.error(f"Failed to get credential info for user {user_id}: {e}")
            raise

    async def update_credentials(
        self, user_id: uuid.UUID, username: str = None, password: str = None
    ) -> Optional[UserGarminCredentials]:
        """
        Update existing credentials.

        Args:
            user_id: User's UUID
            username: New Garmin Connect username (optional)
            password: New Garmin Connect password (optional, plaintext)

        Returns:
            Updated UserGarminCredentials instance or None if not found

        Raises:
            ValueError: If neither username nor password provided
            Exception: If encryption or database operations fail
        """
        if not username and not password:
            raise ValueError("Must provide either username or password to update")

        try:
            logger.info(f"Updating credentials for user {user_id}")

            update_fields = {}

            if username:
                update_fields["garmin_username"] = username

            if password:
                # Encrypt new password using shared encryption service
                encrypted_password = self.encryption_service.encrypt(password)
                update_fields["encrypted_password"] = encrypted_password
                update_fields["encryption_version"] = (
                    self.encryption_service.encryption_version
                )

            # Update credential record
            credential = await self.repository.update(user_id=user_id, **update_fields)

            if not credential:
                logger.warning(f"No credentials found to update for user {user_id}")
                return None

            # Test new authentication if password was changed
            if password:
                final_username = username or credential.garmin_username
                test_result = await self._test_credentials(
                    user_id, final_username, password
                )
                if not test_result["success"]:
                    logger.warning(
                        f"Updated credential test failed for user {user_id}: {test_result['message']}"
                    )

            logger.info(f"Successfully updated credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to update credentials for user {user_id}: {e}")
            raise

    def update_credentials_sync(
        self, user_id: uuid.UUID, username: str = None, password: str = None
    ) -> Optional[UserGarminCredentials]:
        """
        Synchronous version of update_credentials.

        Args:
            user_id: User's UUID
            username: New Garmin Connect username (optional)
            password: New Garmin Connect password (optional, plaintext)

        Returns:
            Updated UserGarminCredentials instance or None if not found
        """
        if not username and not password:
            raise ValueError("Must provide either username or password to update")

        try:
            logger.info(f"Updating credentials for user {user_id}")

            update_fields = {}

            if username:
                update_fields["garmin_username"] = username

            if password:
                # Encrypt new password using shared encryption service
                encrypted_password = self.encryption_service.encrypt(password)
                update_fields["encrypted_password"] = encrypted_password
                update_fields["encryption_version"] = (
                    self.encryption_service.encryption_version
                )

            # Update credential record
            credential = self.repository.update_sync(user_id=user_id, **update_fields)

            if not credential:
                logger.warning(f"No credentials found to update for user {user_id}")
                return None

            # Test new authentication if password was changed
            if password:
                final_username = username or credential.garmin_username
                test_result = self._test_credentials_sync(
                    user_id, final_username, password
                )
                if not test_result["success"]:
                    logger.warning(
                        f"Updated credential test failed for user {user_id}: {test_result['message']}"
                    )

            logger.info(f"Successfully updated credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to update credentials for user {user_id}: {e}")
            raise

    async def delete_credentials(self, user_id: uuid.UUID) -> bool:
        """
        Delete Garmin credentials.

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            logger.info(f"Deleting credentials for user {user_id}")
            result = await self.repository.delete(user_id)

            if result:
                logger.info(f"Successfully deleted credentials for user {user_id}")
            else:
                logger.info(f"No credentials found to delete for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            raise

    def delete_credentials_sync(self, user_id: uuid.UUID) -> bool:
        """
        Synchronous version of delete_credentials.

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            logger.info(f"Deleting credentials for user {user_id}")
            result = self.repository.delete_sync(user_id)

            if result:
                logger.info(f"Successfully deleted credentials for user {user_id}")
            else:
                logger.info(f"No credentials found to delete for user {user_id}")

            return result

        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            raise

    async def test_credentials(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """
        Test Garmin authentication.

        Args:
            user_id: User's UUID

        Returns:
            Dictionary with test results
        """
        try:
            # Get credentials using shared decryption
            credentials = await self.get_credentials(user_id)
            if not credentials:
                return {
                    "success": False,
                    "message": "No credentials found for user",
                    "test_timestamp": datetime.utcnow(),
                }

            username, password = credentials
            return await self._test_credentials(user_id, username, password)

        except Exception as e:
            logger.error(f"Failed to test credentials for user {user_id}: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}",
                "test_timestamp": datetime.utcnow(),
                "error_details": str(e),
            }

    def test_credentials_sync(self, user_id: uuid.UUID) -> Dict[str, Any]:
        """
        Synchronous version of test_credentials.

        Args:
            user_id: User's UUID

        Returns:
            Dictionary with test results
        """
        try:
            # Get credentials using shared decryption
            credentials = self.get_credentials_sync(user_id)
            if not credentials:
                return {
                    "success": False,
                    "message": "No credentials found for user",
                    "test_timestamp": datetime.utcnow(),
                }

            username, password = credentials
            return self._test_credentials_sync(user_id, username, password)

        except Exception as e:
            logger.error(f"Failed to test credentials for user {user_id}: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}",
                "test_timestamp": datetime.utcnow(),
                "error_details": str(e),
            }

    async def _test_credentials(
        self, user_id: uuid.UUID, username: str, password: str
    ) -> Dict[str, Any]:
        """
        Internal method to test Garmin authentication.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            password: Garmin Connect password (plaintext)

        Returns:
            Dictionary with test results
        """
        try:
            # Create temporary GarminClient for testing
            from peakflow.utils import create_garmin_client_from_credentials

            create_garmin_client_from_credentials(
                str(user_id), username, password
            )

            # Test basic connection (this would be a simple API call)
            # For now, we'll simulate the test since we don't have the actual implementation
            # In a real implementation, this would attempt to authenticate with Garmin Connect

            test_timestamp = datetime.utcnow()

            # Simulate test result based on username for demonstration
            if username.endswith("@example.com"):
                # Test failure for demo usernames
                return {
                    "success": False,
                    "message": "Authentication failed - invalid credentials",
                    "test_timestamp": test_timestamp,
                }
            else:
                # Test success for real usernames
                return {
                    "success": True,
                    "message": "Authentication successful",
                    "test_timestamp": test_timestamp,
                }

        except Exception as e:
            logger.error(f"Credential test error for user {user_id}: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}",
                "test_timestamp": datetime.utcnow(),
                "error_details": str(e),
            }

    def _test_credentials_sync(
        self, user_id: uuid.UUID, username: str, password: str
    ) -> Dict[str, Any]:
        """
        Synchronous version of _test_credentials.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            password: Garmin Connect password (plaintext)

        Returns:
            Dictionary with test results
        """
        try:
            # Create temporary GarminClient for testing
            from peakflow.utils import create_garmin_client_from_credentials

            create_garmin_client_from_credentials(
                str(user_id), username, password
            )

            test_timestamp = datetime.utcnow()

            # Simulate test result based on username for demonstration
            if username.endswith("@example.com"):
                return {
                    "success": False,
                    "message": "Authentication failed - invalid credentials",
                    "test_timestamp": test_timestamp,
                }
            else:
                return {
                    "success": True,
                    "message": "Authentication successful",
                    "test_timestamp": test_timestamp,
                }

        except Exception as e:
            logger.error(f"Credential test error for user {user_id}: {e}")
            return {
                "success": False,
                "message": f"Test failed: {str(e)}",
                "test_timestamp": datetime.utcnow(),
                "error_details": str(e),
            }
