"""
Garmin Credential Repository for API Service.

This repository handles database operations for Garmin credentials,
implementing the data access layer as defined in Phase 5 of the migration plan.
"""

import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from sqlmodel import Session, select

from .models import UserGarminCredentials, User

logger = logging.getLogger(__name__)


class GarminCredentialRepository:
    """Repository for Garmin credential database operations."""

    def __init__(self, db: Session):
        """
        Initialize the repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        username: str,
        encrypted_password: str,
        encryption_version: int = 1,
    ) -> UserGarminCredentials:
        """
        Create new credential record.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            encrypted_password: Encrypted password
            encryption_version: Encryption version for key rotation support

        Returns:
            Created UserGarminCredentials instance

        Raises:
            Exception: If user doesn't exist or creation fails
        """
        try:
            # Verify user exists
            user = self.db.get(User, user_id)
            if not user:
                raise ValueError(f"User with ID {user_id} does not exist")

            # Check if credentials already exist for this user
            existing = self.get_by_user_id_sync(user_id)
            if existing:
                raise ValueError(f"Credentials already exist for user {user_id}")

            # Create new credential record
            credential = UserGarminCredentials(
                user_id=user_id,
                garmin_username=username,
                encrypted_password=encrypted_password,
                encryption_version=encryption_version,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            self.db.add(credential)
            self.db.commit()
            self.db.refresh(credential)

            logger.info(f"Created Garmin credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to create credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    def create_sync(
        self,
        user_id: uuid.UUID,
        username: str,
        encrypted_password: str,
        encryption_version: int = 1,
    ) -> UserGarminCredentials:
        """
        Synchronous version of create method.

        Args:
            user_id: User's UUID
            username: Garmin Connect username
            encrypted_password: Encrypted password
            encryption_version: Encryption version for key rotation support

        Returns:
            Created UserGarminCredentials instance
        """
        try:
            # Verify user exists
            user = self.db.get(User, user_id)
            if not user:
                raise ValueError(f"User with ID {user_id} does not exist")

            # Check if credentials already exist for this user
            existing = self.get_by_user_id_sync(user_id)
            if existing:
                raise ValueError(f"Credentials already exist for user {user_id}")

            # Create new credential record
            credential = UserGarminCredentials(
                user_id=user_id,
                garmin_username=username,
                encrypted_password=encrypted_password,
                encryption_version=encryption_version,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            self.db.add(credential)
            self.db.commit()
            self.db.refresh(credential)

            logger.info(f"Created Garmin credentials for user {user_id}")
            return credential

        except Exception as e:
            logger.error(f"Failed to create credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    async def get_by_user_id(
        self, user_id: uuid.UUID
    ) -> Optional[UserGarminCredentials]:
        """
        Get credentials by user ID.

        Args:
            user_id: User's UUID

        Returns:
            UserGarminCredentials instance or None if not found
        """
        try:
            statement = select(UserGarminCredentials).where(
                UserGarminCredentials.user_id == user_id
            )
            result = self.db.exec(statement)
            credential = result.first()

            if credential:
                logger.debug(f"Found credentials for user {user_id}")
            else:
                logger.debug(f"No credentials found for user {user_id}")

            return credential

        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise

    def get_by_user_id_sync(
        self, user_id: uuid.UUID
    ) -> Optional[UserGarminCredentials]:
        """
        Synchronous version of get_by_user_id method.

        Args:
            user_id: User's UUID

        Returns:
            UserGarminCredentials instance or None if not found
        """
        try:
            statement = select(UserGarminCredentials).where(
                UserGarminCredentials.user_id == user_id
            )
            result = self.db.exec(statement)
            credential = result.first()

            if credential:
                logger.debug(f"Found credentials for user {user_id}")
            else:
                logger.debug(f"No credentials found for user {user_id}")

            return credential

        except Exception as e:
            logger.error(f"Failed to get credentials for user {user_id}: {e}")
            raise

    async def update(
        self, user_id: uuid.UUID, **kwargs
    ) -> Optional[UserGarminCredentials]:
        """
        Update credential record.

        Args:
            user_id: User's UUID
            **kwargs: Fields to update (garmin_username, encrypted_password, etc.)

        Returns:
            Updated UserGarminCredentials instance or None if not found
        """
        try:
            # Get existing credential
            credential = await self.get_by_user_id(user_id)
            if not credential:
                logger.warning(f"No credentials found to update for user {user_id}")
                return None

            # Update fields
            update_fields = {}
            if "garmin_username" in kwargs:
                credential.garmin_username = kwargs["garmin_username"]
                update_fields["garmin_username"] = kwargs["garmin_username"]

            if "encrypted_password" in kwargs:
                credential.encrypted_password = kwargs["encrypted_password"]
                update_fields["encrypted_password"] = "[ENCRYPTED]"

            if "encryption_version" in kwargs:
                credential.encryption_version = kwargs["encryption_version"]
                update_fields["encryption_version"] = kwargs["encryption_version"]

            # Update timestamp
            credential.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(credential)

            logger.info(f"Updated credentials for user {user_id}: {update_fields}")
            return credential

        except Exception as e:
            logger.error(f"Failed to update credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    def update_sync(
        self, user_id: uuid.UUID, **kwargs
    ) -> Optional[UserGarminCredentials]:
        """
        Synchronous version of update method.

        Args:
            user_id: User's UUID
            **kwargs: Fields to update (garmin_username, encrypted_password, etc.)

        Returns:
            Updated UserGarminCredentials instance or None if not found
        """
        try:
            # Get existing credential
            credential = self.get_by_user_id_sync(user_id)
            if not credential:
                logger.warning(f"No credentials found to update for user {user_id}")
                return None

            # Update fields
            update_fields = {}
            if "garmin_username" in kwargs:
                credential.garmin_username = kwargs["garmin_username"]
                update_fields["garmin_username"] = kwargs["garmin_username"]

            if "encrypted_password" in kwargs:
                credential.encrypted_password = kwargs["encrypted_password"]
                update_fields["encrypted_password"] = "[ENCRYPTED]"

            if "encryption_version" in kwargs:
                credential.encryption_version = kwargs["encryption_version"]
                update_fields["encryption_version"] = kwargs["encryption_version"]

            # Update timestamp
            credential.updated_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(credential)

            logger.info(f"Updated credentials for user {user_id}: {update_fields}")
            return credential

        except Exception as e:
            logger.error(f"Failed to update credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    async def delete(self, user_id: uuid.UUID) -> bool:
        """
        Delete credential record.

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            credential = await self.get_by_user_id(user_id)
            if not credential:
                logger.warning(f"No credentials found to delete for user {user_id}")
                return False

            self.db.delete(credential)
            self.db.commit()

            logger.info(f"Deleted credentials for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    def delete_sync(self, user_id: uuid.UUID) -> bool:
        """
        Synchronous version of delete method.

        Args:
            user_id: User's UUID

        Returns:
            True if deleted, False if not found
        """
        try:
            credential = self.get_by_user_id_sync(user_id)
            if not credential:
                logger.warning(f"No credentials found to delete for user {user_id}")
                return False

            self.db.delete(credential)
            self.db.commit()

            logger.info(f"Deleted credentials for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete credentials for user {user_id}: {e}")
            self.db.rollback()
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get credential statistics.

        Returns:
            Dictionary with credential statistics
        """
        try:
            # Count total credentials
            total_stmt = select(UserGarminCredentials)
            total_result = self.db.exec(total_stmt)
            total_count = len(total_result.all())

            # Get recent credential creation count (last 30 days)
            thirty_days_ago = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            thirty_days_ago = thirty_days_ago.replace(day=thirty_days_ago.day - 30)

            recent_stmt = select(UserGarminCredentials).where(
                UserGarminCredentials.created_at >= thirty_days_ago
            )
            recent_result = self.db.exec(recent_stmt)
            recent_count = len(recent_result.all())

            stats = {
                "total_credentials": total_count,
                "recent_credentials_30_days": recent_count,
                "last_updated": datetime.now(timezone.utc).isoformat(),
            }

            logger.debug(f"Credential statistics: {stats}")
            return stats

        except Exception as e:
            logger.error(f"Failed to get credential statistics: {e}")
            raise
