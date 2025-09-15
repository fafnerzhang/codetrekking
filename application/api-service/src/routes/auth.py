"""
Authentication routes with PostgreSQL backend.

This module provides secure authentication endpoints including:
- User registration with validation
- Login with JWT token generation
- Token refresh and session management
- Password change and profile management
- Session management and revocation

Security Features:
- Password policy enforcement
- Account lockout protection
- Comprehensive audit logging
- Session-based JWT tokens
- Rate limiting protection
"""

from typing import Dict, Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
import structlog

from ..database import get_db, User
from ..models.requests import UserCreateRequest, LoginRequest, PasswordChangeRequest
from ..models.responses import (
    TokenResponse,
    RefreshTokenResponse,
    UserResponse,
    SessionResponse,
    BaseResponse,
)
from ..services import (
    UserService,
    JWTService,
    SessionService,
    PasswordPolicyError,
    AccountLockoutError,
    TokenValidationError,
    SessionNotFoundError,
)
from ..middleware.auth import get_current_user
from ..middleware.logging import audit_logger, security_logger

# Configure structured logging
logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def get_client_info(request: Request) -> Dict[str, Optional[str]]:
    """Extract client information from request."""
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "device_id": request.headers.get("x-device-id"),
        "device_name": request.headers.get("x-device-name"),
    }


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(
    request: Request, user_data: UserCreateRequest, db: Session = Depends(get_db)
):
    """
    Register new user account.

    Creates a new user account with secure password hashing and validation.
    Requires email verification before account can be fully activated.
    """
    try:
        client_info = get_client_info(request)
        user_service = UserService(db)

        # Create user account
        user_response = user_service.create_user(user_data)

        # Log successful registration
        audit_logger.log_authentication(
            request=request,
            auth_type="registration",
            username=user_data.email,
            success=True,
        )

        logger.info(
            "User registration successful",
            user_id=str(user_response.id),
            email=user_data.email,
            ip_address=client_info["ip_address"],
        )

        return user_response

    except PasswordPolicyError as e:
        # Log password policy violation
        security_logger.log_authentication_failure(
            request=request,
            failure_type="password_policy_violation",
            attempted_user=user_data.email,
            details=str(e),
        )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except ValueError as e:
        # Log registration failure (duplicate email/username)
        audit_logger.log_authentication(
            request=request,
            auth_type="registration",
            username=user_data.email,
            success=False,
            failure_reason=str(e),
        )

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    except Exception as e:
        logger.error("User registration failed", email=user_data.email, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed",
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(
    request: Request, login_data: LoginRequest, db: Session = Depends(get_db)
):
    """
    Authenticate user and create session.

    Validates credentials and creates JWT tokens with session binding
    for secure API access.
    """
    try:
        client_info = get_client_info(request)

        # Initialize services
        user_service = UserService(db)
        session_service = SessionService(db)
        jwt_service = JWTService(db)

        # Authenticate user
        user = user_service.authenticate_user(
            username=login_data.username,
            password=login_data.password,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        if not user:
            # Log failed authentication
            audit_logger.log_authentication(
                request=request,
                auth_type="password",
                username=login_data.username,
                success=False,
                failure_reason="Invalid credentials",
            )

            security_logger.log_authentication_failure(
                request=request,
                failure_type="invalid_credentials",
                attempted_user=login_data.username,
            )

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )

        # Create user session
        session = session_service.create_session(
            user=user,
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
            device_id=client_info["device_id"],
            device_name=client_info["device_name"],
        )

        # Generate JWT tokens
        access_token = jwt_service.create_access_token(user, session.id)
        refresh_token = jwt_service.create_refresh_token(user, session.id)

        # Update session with refresh token
        session.refresh_token = refresh_token
        db.commit()

        # Log successful authentication
        audit_logger.log_authentication(
            request=request,
            auth_type="password",
            username=login_data.username,
            success=True,
        )

        logger.info(
            "User login successful",
            user_id=str(user.id),
            session_id=str(session.id),
            ip_address=client_info["ip_address"],
        )

        # Create user response (exclude sensitive data)
        user_response = UserResponse(
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

        return TokenResponse(
            success=True,
            message="Login successful",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=user_response,
        )

    except AccountLockoutError as e:
        # Log account lockout
        security_logger.log_authentication_failure(
            request=request,
            failure_type="account_locked",
            attempted_user=login_data.username,
            details=str(e),
        )

        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=str(e))

    except Exception as e:
        logger.error("Login failed", username=login_data.username, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login_at=current_user.last_login_at,
    )


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: Request, refresh_token: str, db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    Validates refresh token and creates new access token while
    maintaining session continuity.
    """
    try:
        client_info = get_client_info(request)
        jwt_service = JWTService(db)
        session_service = SessionService(db)

        # Validate refresh token and get new access token
        result = jwt_service.refresh_access_token(refresh_token)

        # Update session activity
        session_service.update_session_activity(
            session_id=result["session_id"],
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"],
        )

        logger.info(
            "Token refresh successful",
            user_id=str(result["user_id"]),
            session_id=str(result["session_id"]),
        )

        return RefreshTokenResponse(
            access_token=result["access_token"],
            token_type="bearer",
            expires_in=jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    except TokenValidationError as e:
        security_logger.log_authentication_failure(
            request=request, failure_type="invalid_refresh_token", details=str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    except SessionNotFoundError as e:
        security_logger.log_authentication_failure(
            request=request, failure_type="session_not_found", details=str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )

    except Exception as e:
        logger.error("Token refresh failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        )


@router.post("/logout", response_model=BaseResponse)
async def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Logout user and revoke session.

    Invalidates current session and optionally all user sessions.
    """
    try:
        # Get session ID from JWT token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )

        token = authorization.split(" ")[1]
        jwt_service = JWTService(db)
        session_service = SessionService(db)

        # Extract session ID from token
        payload = jwt_service.verify_token(token)
        session_id = UUID(payload.get("session_id"))

        # Revoke session
        session_service.revoke_session(session_id)

        # Log logout
        audit_logger.log_authentication(
            request=request,
            auth_type="logout",
            username=current_user.username,
            success=True,
        )

        logger.info(
            "User logout successful",
            user_id=str(current_user.id),
            session_id=str(session_id),
        )

        return BaseResponse(success=True, message="Successfully logged out")

    except Exception as e:
        logger.error("Logout failed", user_id=str(current_user.id), error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Logout failed"
        )


@router.post("/change-password", response_model=BaseResponse)
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Change user password.

    Validates current password and updates to new password with
    policy enforcement.
    """
    try:
        user_service = UserService(db)

        # Change password
        user_service.change_password(
            user=current_user,
            old_password=password_data.old_password,
            new_password=password_data.new_password,
        )

        # Log password change
        audit_logger.log_user_action(
            request=request,
            user=current_user,
            action="password_change",
            details="User changed password",
        )

        logger.info("Password change successful", user_id=str(current_user.id))

        return BaseResponse(success=True, message="Password changed successfully")

    except PasswordPolicyError as e:
        security_logger.log_authentication_failure(
            request=request,
            failure_type="password_policy_violation",
            attempted_user=current_user.username,
            details=str(e),
        )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except ValueError:
        security_logger.log_authentication_failure(
            request=request,
            failure_type="invalid_current_password",
            attempted_user=current_user.username,
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid current password"
        )

    except Exception as e:
        logger.error(
            "Password change failed", user_id=str(current_user.id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed",
        )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Get all active sessions for current user."""
    try:
        session_service = SessionService(db)
        sessions = session_service.get_user_sessions(current_user.id)

        return [
            SessionResponse(
                id=session.id,
                user_id=session.user_id,
                device_id=session.device_id,
                device_name=session.device_name,
                ip_address=session.ip_address,
                user_agent=session.user_agent,
                created_at=session.created_at,
                last_activity_at=session.last_activity_at,
                is_active=session.is_active,
            )
            for session in sessions
        ]

    except Exception as e:
        logger.error(
            "Failed to get user sessions", user_id=str(current_user.id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve sessions",
        )


@router.delete("/sessions/{session_id}", response_model=BaseResponse)
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke a specific session."""
    try:
        session_service = SessionService(db)

        # Verify session belongs to current user
        session = session_service.get_session(session_id)
        if not session or session.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Revoke session
        session_service.revoke_session(session_id)

        logger.info(
            "Session revoked", user_id=str(current_user.id), session_id=str(session_id)
        )

        return BaseResponse(success=True, message="Session revoked successfully")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to revoke session",
            user_id=str(current_user.id),
            session_id=str(session_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session",
        )


@router.post("/sessions/revoke-all", response_model=BaseResponse)
async def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Revoke all sessions for current user except current one."""
    try:
        # Get current session ID from token
        authorization = request.headers.get("Authorization")
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authorization header",
            )

        token = authorization.split(" ")[1]
        jwt_service = JWTService(db)
        payload = jwt_service.verify_token(token)
        current_session_id = UUID(payload.get("session_id"))

        session_service = SessionService(db)

        # Revoke all other sessions
        revoked_count = session_service.revoke_user_sessions(
            user_id=current_user.id, exclude_session_id=current_session_id
        )

        # Log session revocation
        audit_logger.log_user_action(
            request=request,
            user=current_user,
            action="revoke_all_sessions",
            details=f"Revoked {revoked_count} sessions",
        )

        logger.info(
            "All sessions revoked",
            user_id=str(current_user.id),
            revoked_count=revoked_count,
        )

        return BaseResponse(
            success=True, message=f"Successfully revoked {revoked_count} sessions"
        )

    except Exception as e:
        logger.error(
            "Failed to revoke all sessions", user_id=str(current_user.id), error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke sessions",
        )
