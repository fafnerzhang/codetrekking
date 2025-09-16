"""
User management service for authentication system.

This module provides comprehensive user management functionality including:
- User registration and profile management
- Password hashing and verification using bcrypt
- Account security features (lockout, password policies)
- Session management and tracking
- Audit logging for security events

Dependencies:
- passlib[bcrypt]: Secure password hashing
- sqlalchemy: Database ORM
- structlog: Structured logging
"""

import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID

from passlib.context import CryptContext
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
import structlog

from ..database import User, UserSession, AuditLog, Role
from ..models.requests import UserCreateRequest, UserUpdateRequest
from ..models.responses import UserResponse

# Configure structured logging
logger = structlog.get_logger(__name__)

# Password hashing context using bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordPolicyError(Exception):
    """Raised when password doesn't meet security policy requirements."""

    pass


class AccountLockoutError(Exception):
    """Raised when account is locked due to security policies."""

    pass


class UserService:
    """
    Service class for user management operations.

    Provides secure user management functionality with comprehensive
    security features including password policies, account lockout,
    and audit logging.
    """

    # Security configuration constants
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 15
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_HISTORY_COUNT: int = 5

    def __init__(self, db: Session):
        """
        Initialize user service with database session.

        Args:
            db (Session): SQLAlchemy database session
        """
        self.db = db

    def create_user(
        self, user_data: UserCreateRequest, created_by: Optional[UUID] = None
    ) -> UserResponse:
        """
        Create a new user account with security validations.

        Performs comprehensive validation including:
        - Email format validation
        - Username uniqueness check
        - Password policy enforcement
        - Secure password hashing
        - Default role assignment

        Args:
            user_data (UserCreateRequest): User registration data
            created_by (Optional[UUID]): ID of user creating this account

        Returns:
            UserResponse: Created user information (without sensitive data)

        Raises:
            PasswordPolicyError: If password doesn't meet security requirements
            IntegrityError: If username or email already exists
        """
        try:
            # Validate password policy
            self._validate_password_policy(user_data.password)

            # Validate email format
            self._validate_email_format(user_data.email)

            # Hash password securely
            hashed_password = self._hash_password(user_data.password)

            # Create user instance
            user = User(
                username=user_data.username,
                email=user_data.email.lower(),  # Normalize email to lowercase
                hashed_password=hashed_password,
                first_name=user_data.first_name,
                last_name=user_data.last_name,
                is_active=True,
                is_verified=False,  # Require email verification
                password_changed_at=datetime.utcnow(),
            )

            # Add to database
            self.db.add(user)
            self.db.flush()  # Get user ID without committing

            # Assign default role
            self._assign_default_role(user.id)

            # Commit transaction
            self.db.commit()

            # Log user creation
            self._log_audit_event(
                user_id=user.id,
                event_type="user_created",
                event_category="user",
                event_description=f"User account created: {user.email}",
                metadata={"created_by": str(created_by) if created_by else None},
            )

            logger.info(
                "User created successfully",
                user_id=str(user.id),
                email=user.email,
                created_by=str(created_by) if created_by else None,
            )

            return self._user_to_response(user)

        except IntegrityError as e:
            self.db.rollback()
            logger.warning(
                "User creation failed - duplicate data",
                email=user_data.email,
                username=user_data.username,
                error=str(e),
            )
            raise ValueError("Username or email already exists")

        except Exception as e:
            self.db.rollback()
            logger.error("User creation failed", email=user_data.email, error=str(e))
            raise

    def authenticate_user(
        self,
        username: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[User]:
        """
        Authenticate user credentials with security controls.

        Implements comprehensive authentication security including:
        - Account lockout after failed attempts
        - Failed login attempt tracking
        - Audit logging for security events
        - Password verification using bcrypt

        Args:
            username (str): Username or email address
            password (str): Plain text password
            ip_address (Optional[str]): Client IP address for logging
            user_agent (Optional[str]): Client user agent for logging

        Returns:
            Optional[User]: Authenticated user or None if authentication fails

        Raises:
            AccountLockoutError: If account is locked due to failed attempts
        """
        try:
            # Find user by username or email
            user = self._get_user_by_username_or_email(username)

            if not user:
                # Log failed authentication attempt
                self._log_audit_event(
                    user_id=None,
                    event_type="login_failed",
                    event_category="security",
                    event_description=f"Authentication failed - user not found: {username}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="failure",
                )
                return None

            # Check if account is locked
            if self._is_account_locked(user):
                logger.warning(
                    "Authentication attempt on locked account",
                    user_id=str(user.id),
                    email=user.email,
                    ip_address=ip_address,
                )
                raise AccountLockoutError(
                    f"Account is locked until {user.locked_until}. "
                    f"Please try again later or contact support."
                )

            # Check if account is active
            if not user.is_active:
                self._log_audit_event(
                    user_id=user.id,
                    event_type="login_failed",
                    event_category="security",
                    event_description="Authentication failed - account inactive",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status="failure",
                )
                return None

            # Verify password
            if not self._verify_password(password, user.hashed_password):
                # Increment failed login attempts
                self._handle_failed_login(user, ip_address, user_agent)
                return None

            # Authentication successful - reset failed attempts
            user.failed_login_attempts = 0
            user.locked_until = None
            user.last_login_at = datetime.utcnow()

            self.db.commit()

            # Log successful authentication
            self._log_audit_event(
                user_id=user.id,
                event_type="login_success",
                event_category="auth",
                event_description="User successfully authenticated",
                ip_address=ip_address,
                user_agent=user_agent,
                status="success",
            )

            logger.info(
                "User authenticated successfully",
                user_id=str(user.id),
                email=user.email,
                ip_address=ip_address,
            )

            return user

        except AccountLockoutError:
            # Re-raise lockout errors to be handled by the caller
            raise

        except Exception as e:
            logger.error(
                "Authentication error",
                username=username,
                error=str(e),
                ip_address=ip_address,
            )
            return None

    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Retrieve user by ID.

        Args:
            user_id (UUID): User's unique identifier

        Returns:
            Optional[User]: User object or None if not found
        """
        try:
            return self.db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(
                "Error retrieving user by ID", user_id=str(user_id), error=str(e)
            )
            return None

    def update_user(
        self,
        user_id: UUID,
        update_data: UserUpdateRequest,
        updated_by: Optional[UUID] = None,
    ) -> Optional[UserResponse]:
        """
        Update user profile information.

        Args:
            user_id (UUID): User's unique identifier
            update_data (UserUpdateRequest): Updated user data
            updated_by (Optional[UUID]): ID of user making the update

        Returns:
            Optional[UserResponse]: Updated user information or None if not found
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return None

            # Update allowed fields
            if update_data.first_name is not None:
                user.first_name = update_data.first_name
            if update_data.last_name is not None:
                user.last_name = update_data.last_name
            if update_data.email is not None:
                self._validate_email_format(update_data.email)
                user.email = update_data.email.lower()

            user.updated_at = datetime.utcnow()

            self.db.commit()

            # Log profile update
            self._log_audit_event(
                user_id=user.id,
                event_type="profile_updated",
                event_category="user",
                event_description="User profile updated",
                metadata={
                    "updated_by": str(updated_by) if updated_by else None,
                    "fields_updated": [
                        k for k, v in update_data.dict().items() if v is not None
                    ],
                },
            )

            logger.info(
                "User profile updated",
                user_id=str(user.id),
                updated_by=str(updated_by) if updated_by else None,
            )

            return self._user_to_response(user)

        except Exception as e:
            self.db.rollback()
            logger.error("User update failed", user_id=str(user_id), error=str(e))
            raise

    def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> bool:
        """
        Change user password with security validations.

        Args:
            user_id (UUID): User's unique identifier
            current_password (str): Current password for verification
            new_password (str): New password to set

        Returns:
            bool: True if password changed successfully

        Raises:
            PasswordPolicyError: If new password doesn't meet requirements
            ValueError: If current password is incorrect
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                raise ValueError("User not found")

            # Verify current password
            if not self._verify_password(current_password, user.hashed_password):
                raise ValueError("Current password is incorrect")

            # Validate new password policy
            self._validate_password_policy(new_password)

            # Hash new password
            new_hashed_password = self._hash_password(new_password)

            # Update password
            user.hashed_password = new_hashed_password
            user.password_changed_at = datetime.utcnow()

            # Invalidate all user sessions (force re-login for security)
            self._invalidate_user_sessions(user_id)

            self.db.commit()

            # Log password change
            self._log_audit_event(
                user_id=user.id,
                event_type="password_changed",
                event_category="security",
                event_description="User password changed successfully",
            )

            logger.info("Password changed successfully", user_id=str(user.id))

            return True

        except Exception as e:
            self.db.rollback()
            logger.error("Password change failed", user_id=str(user_id), error=str(e))
            raise

    def deactivate_user(
        self, user_id: UUID, deactivated_by: Optional[UUID] = None
    ) -> bool:
        """
        Deactivate user account and invalidate all sessions.

        Args:
            user_id (UUID): User's unique identifier
            deactivated_by (Optional[UUID]): ID of admin deactivating the account

        Returns:
            bool: True if user deactivated successfully
        """
        try:
            user = self.get_user_by_id(user_id)
            if not user:
                return False

            # Deactivate account
            user.is_active = False
            user.updated_at = datetime.utcnow()

            # Invalidate all sessions
            self._invalidate_user_sessions(user_id)

            self.db.commit()

            # Log account deactivation
            self._log_audit_event(
                user_id=user.id,
                event_type="account_deactivated",
                event_category="admin",
                event_description="User account deactivated",
                metadata={
                    "deactivated_by": str(deactivated_by) if deactivated_by else None
                },
            )

            logger.info(
                "User account deactivated",
                user_id=str(user_id),
                deactivated_by=str(deactivated_by) if deactivated_by else None,
            )

            return True

        except Exception as e:
            self.db.rollback()
            logger.error("User deactivation failed", user_id=str(user_id), error=str(e))
            return False

    # Private helper methods

    def _validate_password_policy(self, password: str) -> None:
        """
        Validate password against security policy.

        Security requirements:
        - Minimum 8 characters
        - Contains uppercase letter
        - Contains lowercase letter
        - Contains digit
        - Contains special character

        Args:
            password (str): Password to validate

        Raises:
            PasswordPolicyError: If password doesn't meet requirements
        """
        if len(password) < self.PASSWORD_MIN_LENGTH:
            raise PasswordPolicyError(
                f"Password must be at least {self.PASSWORD_MIN_LENGTH} characters long"
            )

        if not re.search(r"[A-Z]", password):
            raise PasswordPolicyError(
                "Password must contain at least one uppercase letter"
            )

        if not re.search(r"[a-z]", password):
            raise PasswordPolicyError(
                "Password must contain at least one lowercase letter"
            )

        if not re.search(r"\d", password):
            raise PasswordPolicyError("Password must contain at least one digit")

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            raise PasswordPolicyError(
                "Password must contain at least one special character"
            )

    def _validate_email_format(self, email: str) -> None:
        """
        Validate email format using regex.

        Args:
            email (str): Email address to validate

        Raises:
            ValueError: If email format is invalid
        """
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_pattern, email):
            raise ValueError("Invalid email format")

    def _hash_password(self, password: str) -> str:
        """
        Hash password using bcrypt with 12 rounds.

        Args:
            password (str): Plain text password

        Returns:
            str: Hashed password
        """
        return pwd_context.hash(password)

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            plain_password (str): Plain text password
            hashed_password (str): Stored password hash

        Returns:
            bool: True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)

    def _get_user_by_username_or_email(self, identifier: str) -> Optional[User]:
        """
        Find user by username or email address.

        Args:
            identifier (str): Username or email address

        Returns:
            Optional[User]: User object or None if not found
        """
        return (
            self.db.query(User)
            .filter((User.username == identifier) | (User.email == identifier.lower()))
            .first()
        )

    def _is_account_locked(self, user: User) -> bool:
        """
        Check if user account is currently locked.

        Args:
            user (User): User object to check

        Returns:
            bool: True if account is locked
        """
        if user.locked_until is None:
            return False
        return datetime.utcnow() < user.locked_until

    def _handle_failed_login(
        self,
        user: User,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Handle failed login attempt with progressive lockout.

        Args:
            user (User): User who failed authentication
            ip_address (Optional[str]): Client IP address
            user_agent (Optional[str]): Client user agent
        """
        user.failed_login_attempts += 1

        # Lock account after max attempts
        if user.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
            lockout_duration = timedelta(minutes=self.LOCKOUT_DURATION_MINUTES)
            user.locked_until = datetime.utcnow() + lockout_duration

            # Log account lockout
            self._log_audit_event(
                user_id=user.id,
                event_type="account_locked",
                event_category="security",
                event_description=f"Account locked after {self.MAX_LOGIN_ATTEMPTS} failed attempts",
                ip_address=ip_address,
                user_agent=user_agent,
                status="warning",
            )

            logger.warning(
                "Account locked due to failed login attempts",
                user_id=str(user.id),
                email=user.email,
                failed_attempts=user.failed_login_attempts,
                locked_until=user.locked_until.isoformat(),
            )

        # Log failed attempt
        self._log_audit_event(
            user_id=user.id,
            event_type="login_failed",
            event_category="security",
            event_description="Authentication failed - invalid password",
            ip_address=ip_address,
            user_agent=user_agent,
            status="failure",
            metadata={"failed_attempts": user.failed_login_attempts},
        )

        self.db.commit()

    def _assign_default_role(self, user_id: UUID) -> None:
        """
        Assign default 'user' role to new account.

        Args:
            user_id (UUID): User's unique identifier
        """
        # Find default user role
        user_role = self.db.query(Role).filter(Role.name == "user").first()
        if user_role:
            # Import here to avoid circular import
            from ..database.models import UserRoleLink

            # Create user-role association using SQLModel
            user_role_link = UserRoleLink(user_id=user_id, role_id=user_role.id)
            self.db.add(user_role_link)
            self.db.commit()

    def _invalidate_user_sessions(self, user_id: UUID) -> None:
        """
        Invalidate all active sessions for user.

        Args:
            user_id (UUID): User's unique identifier
        """
        self.db.query(UserSession).filter(
            UserSession.user_id == user_id, UserSession.is_active
        ).update(
            {
                "is_active": False,
                "revoked_at": datetime.utcnow(),
                "revoked_reason": "password_changed",
            }
        )

    def _log_audit_event(
        self,
        event_type: str,
        event_category: str,
        event_description: str,
        user_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        status: str = "success",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Log security and user management events for auditing.

        Args:
            event_type (str): Type of event (login, logout, password_change, etc.)
            event_category (str): Event category (auth, user, admin, security)
            event_description (str): Human-readable event description
            user_id (Optional[UUID]): Associated user ID
            ip_address (Optional[str]): Client IP address
            user_agent (Optional[str]): Client user agent
            status (str): Event status (success, failure, warning)
            metadata (Optional[Dict]): Additional event data
        """
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_category=event_category,
            event_description=event_description,
            ip_address=ip_address,
            user_agent=user_agent,
            status=status,
            metadata=str(metadata) if metadata else None,
        )

        self.db.add(audit_log)

    def _user_to_response(self, user: User) -> UserResponse:
        """
        Convert User model to UserResponse (excluding sensitive data).

        Args:
            user (User): User database model

        Returns:
            UserResponse: Safe user data for API responses
        """
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at,
        )
