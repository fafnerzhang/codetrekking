"""
Session management service for authentication system.

This module provides comprehensive session management functionality including:
- Session creation and lifecycle management
- Device tracking and session metadata
- Session cleanup and security controls
- Multi-device session management
- Session analytics and monitoring

Dependencies:
- sqlalchemy: Database session management
- structlog: Structured logging

Security Features:
- Session binding to devices and IP addresses
- Configurable concurrent session limits
- Session timeout and cleanup
- Suspicious activity detection
- Comprehensive audit logging
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID

from sqlmodel import Session, select, update, delete
from sqlalchemy.exc import IntegrityError
import structlog

from ..database import User, UserSession, AuditLog
from ..models.responses import SessionResponse

# Configure structured logging
logger = structlog.get_logger(__name__)


class SessionLimitExceededError(Exception):
    """Raised when user exceeds maximum concurrent sessions."""

    pass


class SessionNotFoundError(Exception):
    """Raised when a session is not found."""

    pass


class SessionService:
    """
    Service class for user session management.

    Provides secure session lifecycle management with device tracking,
    security controls, and comprehensive monitoring for the authentication system.
    """

    # Session configuration constants
    MAX_CONCURRENT_SESSIONS: int = 5
    SESSION_INACTIVITY_TIMEOUT_HOURS: int = 24
    CLEANUP_BATCH_SIZE: int = 1000

    def __init__(self, db: Session):
        """
        Initialize session service with database session.

        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db

    def create_session(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_id: Optional[str] = None,
        device_name: Optional[str] = None,
    ) -> UserSession:
        """
        Create new user session with device tracking.

        Creates a new authenticated session for the user with comprehensive
        metadata tracking for security and analytics purposes.

        Args:
            user (User): Authenticated user object
            ip_address (Optional[str]): Client IP address
            user_agent (Optional[str]): Client user agent string
            device_id (Optional[str]): Unique device identifier
            device_name (Optional[str]): Human-readable device name

        Returns:
            UserSession: Created session object

        Raises:
            SessionLimitExceededError: If user exceeds concurrent session limit
        """
        try:
            # Check concurrent session limit
            active_sessions_count = self._get_active_sessions_count(user.id)
            if active_sessions_count >= self.MAX_CONCURRENT_SESSIONS:
                logger.warning(
                    "Session limit exceeded",
                    user_id=str(user.id),
                    active_sessions=active_sessions_count,
                    limit=self.MAX_CONCURRENT_SESSIONS,
                )

                # Optionally cleanup oldest session instead of failing
                self._cleanup_oldest_session(user.id)

            # Generate secure refresh token
            refresh_token = self._generate_refresh_token()
            refresh_token_expires = datetime.utcnow() + timedelta(days=30)

            # Create session record
            session = UserSession(
                user_id=user.id,
                refresh_token=refresh_token,
                refresh_token_expires=refresh_token_expires,
                ip_address=ip_address,
                user_agent=user_agent,
                device_id=device_id,
                device_name=device_name or self._extract_device_name(user_agent),
                is_active=True,
                last_accessed_at=datetime.utcnow(),
            )

            # Add to database
            self.db.add(session)
            self.db.commit()

            # Log session creation
            self._log_session_event(
                session_id=session.id,
                user_id=user.id,
                event_type="session_created",
                event_description="New user session created",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={
                    "device_id": device_id,
                    "device_name": session.device_name,
                    "active_sessions": active_sessions_count + 1,
                },
            )

            logger.info(
                "Session created successfully",
                session_id=str(session.id),
                user_id=str(user.id),
                ip_address=ip_address,
                device_name=session.device_name,
            )

            return session

        except IntegrityError as e:
            self.db.rollback()
            logger.error(
                "Session creation failed - integrity error",
                user_id=str(user.id),
                error=str(e),
            )
            # Retry with new refresh token
            return self.create_session(
                user, ip_address, user_agent, device_id, device_name
            )

        except Exception as e:
            self.db.rollback()
            logger.error("Session creation failed", user_id=str(user.id), error=str(e))
            raise

    def get_session_by_id(self, session_id: UUID) -> Optional[UserSession]:
        """
        Retrieve session by ID.

        Args:
            session_id (UUID): Session unique identifier

        Returns:
            Optional[UserSession]: Session object or None if not found
        """
        try:
            return self.db.exec(
                select(UserSession).where(UserSession.id == session_id)
            ).first()
        except Exception as e:
            logger.error(
                "Error retrieving session by ID",
                session_id=str(session_id),
                error=str(e),
            )
            return None

    def get_session(self, session_id: UUID) -> Optional[UserSession]:
        """
        Retrieve session by ID (alias for get_session_by_id for backward compatibility).

        Args:
            session_id (UUID): Session unique identifier

        Returns:
            Optional[UserSession]: Session object or None if not found
        """
        return self.get_session_by_id(session_id)

    def get_session_by_refresh_token(self, refresh_token: str) -> Optional[UserSession]:
        """
        Retrieve session by refresh token.

        Args:
            refresh_token (str): Refresh token string

        Returns:
            Optional[UserSession]: Session object or None if not found
        """
        try:
            return self.db.exec(
                select(UserSession).where(
                    UserSession.refresh_token == refresh_token,
                    UserSession.is_active,
                )
            ).first()
        except Exception as e:
            logger.error("Error retrieving session by refresh token", error=str(e))
            return None

    def get_user_sessions(
        self, user_id: UUID, active_only: bool = True
    ) -> List[SessionResponse]:
        """
        Get all sessions for a user.

        Args:
            user_id (UUID): User's unique identifier
            active_only (bool): Whether to return only active sessions

        Returns:
            List[SessionResponse]: List of user sessions
        """
        try:
            stmt = select(UserSession).where(UserSession.user_id == user_id)

            if active_only:
                stmt = stmt.where(UserSession.is_active)

            sessions = self.db.exec(
                stmt.order_by(UserSession.last_accessed_at.desc())
            ).all()

            # Get current session (most recently accessed active session)
            current_session_id = None
            if sessions:
                current_session_id = sessions[0].id

            return [
                SessionResponse(
                    id=session.id,
                    device_name=session.device_name,
                    ip_address=session.ip_address,
                    user_agent=session.user_agent,
                    created_at=session.created_at,
                    last_accessed_at=session.last_accessed_at,
                    is_current=(session.id == current_session_id),
                )
                for session in sessions
            ]

        except Exception as e:
            logger.error(
                "Error retrieving user sessions", user_id=str(user_id), error=str(e)
            )
            return []

    def update_session_activity(
        self,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> bool:
        """
        Update session last activity timestamp and metadata.

        Args:
            session_id (UUID): Session identifier
            ip_address (Optional[str]): Current IP address
            user_agent (Optional[str]): Current user agent

        Returns:
            bool: True if session updated successfully
        """
        try:
            session = self.get_session_by_id(session_id)
            if not session or not session.is_active:
                return False

            # Update activity timestamp
            session.last_accessed_at = datetime.utcnow()

            # Update IP address if provided and different
            if ip_address and session.ip_address != ip_address:
                # Log IP address change for security monitoring
                self._log_session_event(
                    session_id=session.id,
                    user_id=session.user_id,
                    event_type="session_ip_changed",
                    event_description=f"Session IP address changed from {session.ip_address} to {ip_address}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={"old_ip": session.ip_address, "new_ip": ip_address},
                )

                session.ip_address = ip_address

            # Update user agent if provided and different
            if user_agent and session.user_agent != user_agent:
                session.user_agent = user_agent

            self.db.commit()
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Error updating session activity",
                session_id=str(session_id),
                error=str(e),
            )
            return False

    def update_session_access(
        self, session_id: UUID, ip_address: Optional[str] = None
    ) -> bool:
        """
        Update session access time and IP address (alias for update_session_activity).

        Args:
            session_id (UUID): Session identifier
            ip_address (Optional[str]): Current IP address

        Returns:
            bool: True if session updated successfully
        """
        return self.update_session_activity(session_id, ip_address)

    def revoke_session(
        self,
        session_id: UUID,
        reason: str = "user_logout",
        revoked_by: Optional[UUID] = None,
    ) -> bool:
        """
        Revoke (invalidate) a user session.

        Args:
            session_id (UUID): Session identifier to revoke
            reason (str): Reason for revocation
            revoked_by (Optional[UUID]): User ID who initiated revocation

        Returns:
            bool: True if session revoked successfully
        """
        try:
            session = self.get_session_by_id(session_id)
            if not session:
                return False

            # Revoke session
            session.is_active = False
            session.revoked_at = datetime.utcnow()
            session.revoked_reason = reason

            self.db.commit()

            # Log session revocation
            self._log_session_event(
                session_id=session.id,
                user_id=session.user_id,
                event_type="session_revoked",
                event_description=f"Session revoked: {reason}",
                metadata={
                    "reason": reason,
                    "revoked_by": str(revoked_by) if revoked_by else None,
                },
            )

            logger.info(
                "Session revoked",
                session_id=str(session_id),
                user_id=str(session.user_id),
                reason=reason,
                revoked_by=str(revoked_by) if revoked_by else None,
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Error revoking session", session_id=str(session_id), error=str(e)
            )
            return False

    def revoke_all_user_sessions(
        self,
        user_id: UUID,
        reason: str = "security_action",
        except_session_id: Optional[UUID] = None,
    ) -> int:
        """
        Revoke all active sessions for a user.

        Args:
            user_id (UUID): User identifier
            reason (str): Reason for revocation
            except_session_id (Optional[UUID]): Session ID to exclude from revocation

        Returns:
            int: Number of sessions revoked
        """
        try:
            stmt = select(UserSession).where(
                UserSession.user_id == user_id, UserSession.is_active
            )

            if except_session_id:
                stmt = stmt.where(UserSession.id != except_session_id)

            sessions_to_revoke = self.db.exec(stmt).all()
            revoked_count = 0

            for session in sessions_to_revoke:
                session.is_active = False
                session.revoked_at = datetime.utcnow()
                session.revoked_reason = reason
                revoked_count += 1

            self.db.commit()

            # Log bulk session revocation
            self._log_session_event(
                session_id=None,
                user_id=user_id,
                event_type="sessions_bulk_revoked",
                event_description=f"Bulk session revocation: {reason}",
                metadata={
                    "reason": reason,
                    "sessions_revoked": revoked_count,
                    "except_session_id": (
                        str(except_session_id) if except_session_id else None
                    ),
                },
            )

            logger.info(
                "User sessions revoked",
                user_id=str(user_id),
                sessions_revoked=revoked_count,
                reason=reason,
            )

            return revoked_count

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Error revoking user sessions", user_id=str(user_id), error=str(e)
            )
            return 0

    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired and inactive sessions from database.

        This method should be run periodically as a maintenance task
        to clean up old session records and maintain database performance.

        Returns:
            int: Number of sessions cleaned up
        """
        try:
            # Calculate cutoff time for inactive sessions
            inactivity_cutoff = datetime.utcnow() - timedelta(
                hours=self.SESSION_INACTIVITY_TIMEOUT_HOURS
            )

            # Find sessions to cleanup
            sessions_to_delete = self.db.exec(
                select(UserSession)
                .where(
                    (UserSession.refresh_token_expires < datetime.utcnow())  # Expired
                    | (not UserSession.is_active)  # Already revoked
                    | (UserSession.last_accessed_at < inactivity_cutoff)  # Inactive
                )
                .limit(self.CLEANUP_BATCH_SIZE)
            ).all()

            cleanup_count = len(sessions_to_delete)

            if cleanup_count > 0:
                # Delete sessions in batch
                for session in sessions_to_delete:
                    self.db.delete(session)

                self.db.commit()

                logger.info(
                    "Session cleanup completed",
                    sessions_cleaned=cleanup_count,
                    cutoff_time=inactivity_cutoff.isoformat(),
                )

            return cleanup_count

        except Exception as e:
            self.db.rollback()
            logger.error("Session cleanup failed", error=str(e))
            return 0

    def rotate_refresh_token(self, session: UserSession) -> str:
        """
        Rotate refresh token for enhanced security.

        Args:
            session (UserSession): Session to rotate token for

        Returns:
            str: New refresh token
        """
        try:
            # Generate new refresh token
            new_refresh_token = self._generate_refresh_token()

            # Update session
            old_token = session.refresh_token
            session.refresh_token = new_refresh_token
            session.last_accessed_at = datetime.utcnow()

            self.db.commit()

            # Log token rotation
            self._log_session_event(
                session_id=session.id,
                user_id=session.user_id,
                event_type="refresh_token_rotated",
                event_description="Refresh token rotated for security",
                metadata={"old_token_prefix": old_token[:8] if old_token else None},
            )

            logger.debug(
                "Refresh token rotated",
                session_id=str(session.id),
                user_id=str(session.user_id),
            )

            return new_refresh_token

        except Exception as e:
            self.db.rollback()
            logger.error(
                "Error rotating refresh token", session_id=str(session.id), error=str(e)
            )
            raise

    # Private helper methods

    def _get_active_sessions_count(self, user_id: UUID) -> int:
        """Get count of active sessions for user."""
        try:
            stmt = select(UserSession).where(
                UserSession.user_id == user_id, UserSession.is_active
            )
            return len(self.db.exec(stmt).all())
        except Exception:
            return 0

    def _cleanup_oldest_session(self, user_id: UUID) -> None:
        """Remove oldest active session for user."""
        try:
            oldest_session = self.db.exec(
                select(UserSession)
                .where(UserSession.user_id == user_id, UserSession.is_active)
                .order_by(UserSession.last_accessed_at.asc())
            ).first()

            if oldest_session:
                self.revoke_session(oldest_session.id, reason="session_limit_exceeded")
        except Exception as e:
            logger.error(
                "Error cleaning up oldest session", user_id=str(user_id), error=str(e)
            )

    def _generate_refresh_token(self) -> str:
        """Generate cryptographically secure refresh token."""
        return secrets.token_urlsafe(64)

    def _extract_device_name(self, user_agent: Optional[str]) -> Optional[str]:
        """Extract device name from user agent string."""
        if not user_agent:
            return None

        # Simple device name extraction (can be enhanced with more sophisticated parsing)
        user_agent = user_agent.lower()

        if "mobile" in user_agent or "android" in user_agent:
            return "Mobile Device"
        elif "iphone" in user_agent or "ipad" in user_agent:
            return "iOS Device"
        elif "chrome" in user_agent:
            return "Chrome Browser"
        elif "firefox" in user_agent:
            return "Firefox Browser"
        elif "safari" in user_agent:
            return "Safari Browser"
        elif "edge" in user_agent:
            return "Edge Browser"
        else:
            return "Unknown Device"

    def _log_session_event(
        self,
        event_type: str,
        event_description: str,
        user_id: UUID,
        session_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log session-related events for audit purposes."""
        try:
            audit_log = AuditLog(
                user_id=user_id,
                event_type=event_type,
                event_category="session",
                event_description=event_description,
                ip_address=ip_address,
                user_agent=user_agent,
                status="success",
                metadata=str(metadata) if metadata else None,
            )

            self.db.add(audit_log)

        except Exception as e:
            logger.error(
                "Error logging session event",
                event_type=event_type,
                user_id=str(user_id),
                error=str(e),
            )
