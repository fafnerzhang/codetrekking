"""
Services package for authentication system.

This package contains business logic services for the authentication system:
- UserService: User management and authentication
- JWTService: JWT token generation and validation
- SessionService: Session lifecycle management
- GarminCredentialService: Garmin credential management (Phase 5)
"""

from .user_service import UserService, PasswordPolicyError, AccountLockoutError
from .jwt_service import JWTService, TokenValidationError
from .session_service import (
    SessionService,
    SessionLimitExceededError,
    SessionNotFoundError,
)
from .garmin_service import GarminCredentialService

__all__ = [
    # User Service
    "UserService",
    "PasswordPolicyError",
    "AccountLockoutError",
    # JWT Service
    "JWTService",
    "TokenValidationError",
    "SessionNotFoundError",
    # Session Service
    "SessionService",
    "SessionLimitExceededError",
    # Garmin Credential Service (Phase 5)
    "GarminCredentialService",
]
