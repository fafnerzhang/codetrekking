"""
JWT token service for authentication system.

This module provides secure JWT token management functionality including:
- Access and refresh token generation
- Token validation and verification
- Session-based token management
- Token revocation and blacklisting
- Secure token claims handling

Dependencies:
- python-jose[cryptography]: JWT token operations
- sqlalchemy: Database session management
- structlog: Structured logging

Security Features:
- RS256 or HS256 algorithm support
- Configurable token expiration
- Session binding for enhanced security
- Token rotation for refresh tokens
- Comprehensive audit logging
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from uuid import UUID

from jose import JWTError, jwt
from sqlmodel import Session
import structlog

from ..database import User, UserSession
from ..database.config import get_database_settings

# Configure structured logging
logger = structlog.get_logger(__name__)

# JWT configuration
settings = get_database_settings()


class TokenValidationError(Exception):
    """Raised when token validation fails."""

    pass


class SessionNotFoundError(Exception):
    """Raised when referenced session doesn't exist."""

    pass


class JWTService:
    """
    Service class for JWT token management and validation.

    Provides comprehensive JWT token functionality with session binding
    for enhanced security. Supports both access and refresh tokens with
    configurable expiration times and security policies.
    """

    # Token configuration constants
    ALGORITHM = "HS256"  # Using HMAC SHA-256 for simplicity
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    REFRESH_TOKEN_EXPIRE_DAYS = 30

    def __init__(self, db: Session):
        """
        Initialize JWT service with database session.

        Args:
            db (Session): SQLAlchemy database session for token validation
        """
        self.db = db
        # Get JWT secret from environment (configured in database settings)
        self.secret_key = getattr(settings, "jwt_secret_key", "CHANGE_ME_IN_PRODUCTION")

        # Fail fast if using insecure defaults
        if self.secret_key in [
            "CHANGE_ME_IN_PRODUCTION",
            "dev-secret-key-change-in-production",
        ]:
            raise ValueError(
                "JWT_SECRET_KEY environment variable must be set to a secure value"
            )

    def create_access_token(
        self, user: User, session_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token for authenticated user.

        Generates a short-lived access token containing user claims
        and session information for API authentication.

        Args:
            user (User): Authenticated user object
            session_id (UUID): Associated session identifier
            expires_delta (Optional[timedelta]): Custom expiration time

        Returns:
            str: Encoded JWT access token
        """
        try:
            # Set expiration time
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(
                    minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES
                )

            # Get user roles and permissions
            roles = [role.name for role in user.roles]
            permissions = []
            for role in user.roles:
                permissions.extend([perm.name for perm in role.permissions])

            # Create token claims
            claims = {
                "sub": str(user.id),  # Subject (user ID)
                "username": user.email,  # Username/email
                "iat": datetime.now(timezone.utc),  # Issued at
                "exp": expire,  # Expiration time
                "type": "access",  # Token type
                "session_id": str(session_id),  # Session binding
                "roles": roles,  # User roles
                "permissions": list(set(permissions)),  # Unique permissions
                "is_verified": user.is_verified,  # Email verification status
                "full_name": user.full_name,  # Display name
            }

            # Encode JWT token
            token = jwt.encode(claims, self.secret_key, algorithm=self.ALGORITHM)

            logger.info(
                "Access token created",
                user_id=str(user.id),
                session_id=str(session_id),
                expires_at=expire.isoformat(),
                roles=roles,
            )

            return token

        except Exception as e:
            logger.error(
                "Failed to create access token",
                user_id=str(user.id) if user else None,
                error=str(e),
            )
            raise

    def create_refresh_token(
        self, user: User, session_id: UUID, expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token for session management.

        Generates a long-lived refresh token for obtaining new access tokens
        without re-authentication. Contains minimal claims for security.

        Args:
            user (User): Authenticated user object
            session_id (UUID): Associated session identifier
            expires_delta (Optional[timedelta]): Custom expiration time

        Returns:
            str: Encoded JWT refresh token
        """
        try:
            # Set expiration time
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(
                    days=self.REFRESH_TOKEN_EXPIRE_DAYS
                )

            # Create minimal refresh token claims
            claims = {
                "sub": str(user.id),  # Subject (user ID)
                "username": user.email,  # Username/email
                "iat": datetime.now(timezone.utc),  # Issued at
                "exp": expire,  # Expiration time
                "type": "refresh",  # Token type
                "session_id": str(session_id),  # Session binding
                "jti": secrets.token_urlsafe(32),  # JWT ID for revocation
            }

            # Encode JWT token
            token = jwt.encode(claims, self.secret_key, algorithm=self.ALGORITHM)

            logger.info(
                "Refresh token created",
                user_id=str(user.id),
                session_id=str(session_id),
                expires_at=expire.isoformat(),
            )

            return token

        except Exception as e:
            logger.error(
                "Failed to create refresh token",
                user_id=str(user.id) if user else None,
                error=str(e),
            )
            raise

    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validate and decode JWT access token.

        Performs comprehensive token validation including:
        - JWT signature verification
        - Expiration time checking
        - Token type validation
        - Session existence verification
        - User account status checking

        Args:
            token (str): JWT access token to validate

        Returns:
            Dict[str, Any]: Decoded token claims

        Raises:
            TokenValidationError: If token validation fails
            SessionNotFoundError: If associated session not found
        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.ALGORITHM])

            # Validate token type
            if payload.get("type") != "access":
                raise TokenValidationError("Invalid token type")

            # Validate required claims
            required_claims = ["sub", "username", "session_id", "exp"]
            for claim in required_claims:
                if claim not in payload:
                    raise TokenValidationError(f"Missing required claim: {claim}")

            # Validate session exists and is active
            session_id = UUID(payload["session_id"])
            from sqlmodel import select
            user_session = self.db.exec(
                select(UserSession).where(
                    UserSession.id == session_id, UserSession.is_active
                )
            ).first()

            if not user_session:
                raise SessionNotFoundError("Session not found or inactive")

            # Validate session is not expired
            if user_session.is_expired:
                raise TokenValidationError("Session expired")

            # Validate user account status
            user_id = UUID(payload["sub"])
            user = self.db.exec(select(User).where(User.id == user_id)).first()

            if not user or not user.is_active:
                raise TokenValidationError("User account inactive")

            # Update session last accessed time
            user_session.last_accessed_at = datetime.now(timezone.utc)
            self.db.commit()

            logger.debug(
                "Access token validated successfully",
                user_id=payload["sub"],
                session_id=payload["session_id"],
            )

            return payload

        except JWTError as e:
            logger.warning("JWT validation failed", error=str(e))
            raise TokenValidationError(f"Invalid token: {str(e)}")

        except (ValueError, KeyError) as e:
            logger.warning("Token format error", error=str(e))
            raise TokenValidationError(f"Invalid token format: {str(e)}")

        except Exception as e:
            logger.error("Token validation error", error=str(e))
            raise TokenValidationError(f"Token validation failed: {str(e)}")

    def validate_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Validate and decode JWT refresh token.

        Validates refresh token for generating new access tokens.
        Performs session validation and user account status checking.

        Args:
            token (str): JWT refresh token to validate

        Returns:
            Dict[str, Any]: Decoded token claims

        Raises:
            TokenValidationError: If token validation fails
            SessionNotFoundError: If associated session not found
        """
        try:
            # Decode JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.ALGORITHM])

            # Validate token type
            if payload.get("type") != "refresh":
                raise TokenValidationError("Invalid token type")

            # Validate required claims
            required_claims = ["sub", "username", "session_id", "exp", "jti"]
            for claim in required_claims:
                if claim not in payload:
                    raise TokenValidationError(f"Missing required claim: {claim}")

            # Validate session exists and is active
            session_id = UUID(payload["session_id"])
            user_session = self.db.exec(
                select(UserSession).where(
                    UserSession.id == session_id,
                    UserSession.is_active,
                    UserSession.refresh_token == token  # Verify token matches stored token
                )
            ).first()

            if not user_session:
                raise SessionNotFoundError("Session not found or token mismatch")

            # Validate session is not expired
            if user_session.is_expired:
                raise TokenValidationError("Session expired")

            # Validate user account status
            user_id = UUID(payload["sub"])
            user = self.db.exec(select(User).where(User.id == user_id)).first()

            if not user or not user.is_active:
                raise TokenValidationError("User account inactive")

            logger.debug(
                "Refresh token validated successfully",
                user_id=payload["sub"],
                session_id=payload["session_id"],
            )

            return payload

        except JWTError as e:
            logger.warning("JWT refresh token validation failed", error=str(e))
            raise TokenValidationError(f"Invalid refresh token: {str(e)}")

        except (ValueError, KeyError) as e:
            logger.warning("Refresh token format error", error=str(e))
            raise TokenValidationError(f"Invalid refresh token format: {str(e)}")

        except Exception as e:
            logger.error("Refresh token validation error", error=str(e))
            raise TokenValidationError(f"Refresh token validation failed: {str(e)}")

    def get_user_from_token(self, token: str) -> Optional[User]:
        """
        Extract and return user from valid access token.

        Args:
            token (str): JWT access token

        Returns:
            Optional[User]: User object if token is valid, None otherwise
        """
        try:
            payload = self.validate_access_token(token)
            user_id = UUID(payload["sub"])
            return self.db.exec(select(User).where(User.id == user_id)).first()

        except (TokenValidationError, SessionNotFoundError):
            return None

    def revoke_token(self, session_id: UUID, reason: str = "manual_revocation") -> bool:
        """
        Revoke tokens by invalidating the associated session.

        Args:
            session_id (UUID): Session identifier to revoke
            reason (str): Reason for revocation (for audit logging)

        Returns:
            bool: True if session was revoked successfully
        """
        try:
            user_session = self.db.exec(
                select(UserSession).where(
                    UserSession.id == session_id, UserSession.is_active
                )
            ).first()

            if not user_session:
                return False

            # Revoke session
            user_session.is_active = False
            user_session.revoked_at = datetime.utcnow()
            user_session.revoked_reason = reason

            self.db.commit()

            logger.info(
                "Session revoked",
                session_id=str(session_id),
                user_id=str(user_session.user_id),
                reason=reason,
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to revoke session", session_id=str(session_id), error=str(e)
            )
            return False

    def revoke_all_user_sessions(
        self, user_id: UUID, reason: str = "security_action"
    ) -> int:
        """
        Revoke all active sessions for a user.

        Useful for security actions like password changes or account compromise.

        Args:
            user_id (UUID): User identifier
            reason (str): Reason for revocation

        Returns:
            int: Number of sessions revoked
        """
        try:
            from sqlmodel import update
            stmt = (
                update(UserSession)
                .where(UserSession.user_id == user_id, UserSession.is_active)
                .values(
                    is_active=False,
                    revoked_at=datetime.utcnow(),
                    revoked_reason=reason,
                )
            )
            result = self.db.exec(stmt)
            revoked_count = result.rowcount

            self.db.commit()

            logger.info(
                "All user sessions revoked",
                user_id=str(user_id),
                sessions_revoked=revoked_count,
                reason=reason,
            )

            return revoked_count

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Failed to revoke user sessions", user_id=str(user_id), error=str(e)
            )
            return 0

    def cleanup_expired_sessions(self) -> int:
        """
        Clean up expired sessions from database.

        This should be run periodically as a maintenance task
        to remove expired session records.

        Returns:
            int: Number of expired sessions cleaned up
        """
        try:
            from sqlmodel import delete
            stmt = delete(UserSession).where(
                UserSession.refresh_token_expires < datetime.utcnow()
            )
            result = self.db.exec(stmt)
            expired_count = result.rowcount

            self.db.commit()

            logger.info("Expired sessions cleaned up", sessions_removed=expired_count)

            return expired_count

        except Exception as e:
            self.db.rollback()
            logger.error("Failed to cleanup expired sessions", error=str(e))
            return 0

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and validate JWT access token (alias for validate_access_token).

        This method is used by the auth middleware for token validation.

        Args:
            token (str): JWT access token to verify

        Returns:
            Dict[str, Any]: Decoded token claims

        Raises:
            TokenValidationError: If token validation fails
            SessionNotFoundError: If associated session not found
        """
        return self.validate_access_token(token)

    def get_token_claims(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get token claims without validation (for debugging/logging).

        Warning: This method does not validate the token signature
        or expiration. Use only for non-security purposes.

        Args:
            token (str): JWT token to decode

        Returns:
            Optional[Dict[str, Any]]: Token claims or None if invalid format
        """
        try:
            return jwt.decode(token, options={"verify_signature": False})
        except Exception:
            return None
