"""
Database models for PeakFlow Tasks.

This module defines database models used by PeakFlow Tasks, matching the schema
defined in Phase 2 of the Garmin credentials migration plan. 
Uses SQLModel for consistency with the api-service.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class UserGarminCredentials(SQLModel, table=True):
    """
    Encrypted Garmin credentials storage.
    
    This model matches the schema defined in Phase 2 of the migration plan:
    - Stores encrypted Garmin credentials for users
    - Supports encryption key rotation via version field
    - Links to users table via foreign key
    """
    __tablename__ = "user_garmin_credentials"
    __table_args__ = {'extend_existing': True}
    
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: Optional[uuid.UUID] = Field(
        default=None, 
        foreign_key="users.id", 
        index=True, 
        unique=True
    )
    garmin_username: str = Field(max_length=255)
    encrypted_password: str = Field()  # AES-256-GCM encrypted
    encryption_version: int = Field(default=1)  # Support key rotation
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    def __repr__(self) -> str:
        """String representation of the credential record."""
        return f"<UserGarminCredentials(user_id={self.user_id}, username={self.garmin_username})>"