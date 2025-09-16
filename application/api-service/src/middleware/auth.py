"""
Authentication middleware for JWT token validation.

Provides secure authentication middleware for protecting API endpoints
with JWT token validation and user context injection.
"""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session
import structlog

from ..database import get_db, User
from ..services import JWTService, SessionService
from ..services.jwt_service import TokenValidationError
from ..services.session_service import SessionNotFoundError

# Configure structured logging
logger = structlog.get_logger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate JWT token to get current user.

    This dependency validates the JWT token and returns the authenticated
    user. It also validates that the session is still active.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        User: The authenticated user

    Raises:
        HTTPException: If token is invalid or user is not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Extract token
        token = credentials.credentials

        # Initialize services
        jwt_service = JWTService(db)
        session_service = SessionService(db)

        # Verify token and extract payload
        payload = jwt_service.verify_token(token)
        user_id: str = payload.get("sub")
        session_id: str = payload.get("session_id")

        if user_id is None or session_id is None:
            raise credentials_exception

        # Convert to UUIDs
        user_uuid = UUID(user_id)
        session_uuid = UUID(session_id)

        # Validate session is still active
        session = session_service.get_session(session_uuid)
        if not session or not session.is_active or session.user_id != user_uuid:
            logger.warning(
                "Invalid or inactive session", user_id=user_id, session_id=session_id
            )
            raise credentials_exception

        # Get user from database
        user = db.query(User).filter(User.id == user_uuid).first()
        if user is None:
            logger.warning("User not found for valid token", user_id=user_id)
            raise credentials_exception

        # Check if user is still active
        if not user.is_active:
            logger.warning("Inactive user attempted access", user_id=user_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
            )

        return user

    except TokenValidationError as e:
        logger.warning("Token validation failed", error=str(e))
        raise credentials_exception

    except SessionNotFoundError as e:
        logger.warning("Session not found", error=str(e))
        raise credentials_exception

    except ValueError as e:
        logger.warning("Invalid UUID in token", error=str(e))
        raise credentials_exception

    except Exception as e:
        logger.error("Unexpected error in authentication", error=str(e))
        raise credentials_exception


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current active user (additional check for user status).

    This is a stricter dependency that ensures the user is both
    authenticated and active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is disabled"
        )
    return current_user


async def get_current_verified_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current verified user (additional check for email verification).

    This dependency ensures the user is authenticated, active, and
    has verified their email address.
    """
    if not current_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Email verification required"
        )
    return current_user


def optional_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Optional authentication that returns None if no valid token provided.

    This is useful for endpoints that can work with or without authentication,
    providing different functionality based on authentication status.

    Args:
        credentials: Optional HTTP Bearer token credentials
        db: Database session

    Returns:
        Optional[User]: The authenticated user or None
    """
    if not credentials:
        return None

    try:
        # Use the same logic as get_current_user but return None on failure
        token = credentials.credentials

        jwt_service = JWTService(db)
        session_service = SessionService(db)

        payload = jwt_service.verify_token(token)
        user_id: str = payload.get("sub")
        session_id: str = payload.get("session_id")

        if user_id is None or session_id is None:
            return None

        user_uuid = UUID(user_id)
        session_uuid = UUID(session_id)

        session = session_service.get_session(session_uuid)
        if not session or not session.is_active or session.user_id != user_uuid:
            return None

        user = db.query(User).filter(User.id == user_uuid).first()
        if user is None or not user.is_active:
            return None

        return user

    except Exception:
        # Log the exception but don't raise it for optional auth
        return None


class AuthMiddleware:
    """
    Authentication middleware for FastAPI that validates JWT tokens
    and adds user context to requests.

    This middleware intercepts all incoming requests and validates JWT tokens
    for protected endpoints, adding user context to the request state.
    """

    def __init__(self, app):
        """
        Initialize the authentication middleware.

        Args:
            app: FastAPI application instance
        """
        self.app = app

        # Protected paths that require authentication
        self.protected_paths = [
            "/api/v1/garmin/",
            "/api/v1/analytics/",
            "/api/v1/tasks/",
            "/api/v1/admin/",
            "/api/v1/users/",
        ]

        # Public paths that don't require authentication
        self.public_paths = [
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/password-reset-request",
            "/api/v1/auth/password-reset-confirm",
            "/api/v1/auth/verify-email",
            "/health",
            "/api/v1/status",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        ]

    async def __call__(self, scope, receive, send):
        """
        ASGI middleware call method.

        Args:
            scope: ASGI scope
            receive: ASGI receive callable
            send: ASGI send callable
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Get request details
        path = scope["path"]
        method = scope["method"]
        headers = dict(scope.get("headers", []))

        # Check if this path requires authentication
        if self._is_public_path(path):
            await self.app(scope, receive, send)
            return

        # Check if this is a protected path
        if not self._is_protected_path(path):
            await self.app(scope, receive, send)
            return

        # Extract and validate JWT token
        auth_result = await self._validate_token(headers, scope)

        if auth_result["authenticated"]:
            # Add user context to scope
            scope["user"] = auth_result["user"]
            scope["session_id"] = auth_result.get("session_id")

            # Log successful authentication
            logger.info(
                "Request authenticated",
                user_id=str(auth_result["user"].id),
                path=path,
                method=method,
                ip_address=self._get_client_ip(scope),
            )

            await self.app(scope, receive, send)
        else:
            # Authentication failed - return 401
            await self._send_auth_error(send, auth_result["error"])

    def _is_public_path(self, path: str) -> bool:
        """Check if the path is public and doesn't require authentication."""
        return any(path.startswith(public_path) for public_path in self.public_paths)

    def _is_protected_path(self, path: str) -> bool:
        """Check if the path requires authentication."""
        return any(
            path.startswith(protected_path) for protected_path in self.protected_paths
        )

    async def _validate_token(self, headers: dict, scope: dict) -> dict:
        """
        Validate JWT token from request headers.

        Args:
            headers: Request headers
            scope: ASGI scope

        Returns:
            Dictionary with authentication result
        """
        try:
            # Extract Authorization header
            auth_header = None
            for name, value in headers.items():
                if name == b"authorization":
                    auth_header = value.decode("utf-8")
                    break

            if not auth_header:
                return {"authenticated": False, "error": "Missing Authorization header"}

            # Validate Bearer token format
            if not auth_header.startswith("Bearer "):
                return {
                    "authenticated": False,
                    "error": "Invalid Authorization header format",
                }

            token = auth_header.split(" ", 1)[1]

            # Create a database session for token validation
            from ..database import SessionLocal

            db = SessionLocal()

            try:
                # Initialize services
                jwt_service = JWTService(db)
                session_service = SessionService(db)

                # Verify token and extract payload
                payload = jwt_service.verify_token(token)
                user_id = payload.get("sub")
                session_id = payload.get("session_id")

                if not user_id or not session_id:
                    return {"authenticated": False, "error": "Invalid token payload"}

                # Convert to UUIDs
                user_uuid = UUID(user_id)
                session_uuid = UUID(session_id)

                # Validate session is still active
                session = session_service.get_session(session_uuid)
                if not session or not session.is_active or session.user_id != user_uuid:
                    return {
                        "authenticated": False,
                        "error": "Invalid or inactive session",
                    }

                # Get user from database
                user = db.query(User).filter(User.id == user_uuid).first()
                if not user:
                    return {"authenticated": False, "error": "User not found"}

                # Check if user is active
                if not user.is_active:
                    return {"authenticated": False, "error": "User account is disabled"}

                # Update session last accessed time (if method exists)
                try:
                    session_service.update_session_access(
                        session_uuid, self._get_client_ip(scope)
                    )
                except AttributeError:
                    # Method doesn't exist yet, skip for now
                    pass

                return {
                    "authenticated": True,
                    "user": user,
                    "session_id": session_uuid,
                    "token_payload": payload,
                }

            finally:
                db.close()

        except TokenValidationError as e:
            logger.warning("Token validation failed", error=str(e))
            return {"authenticated": False, "error": "Token validation failed"}
        except ValueError as e:
            logger.warning("Invalid UUID in token", error=str(e))
            return {"authenticated": False, "error": "Invalid token format"}
        except Exception as e:
            logger.error("Unexpected authentication error", error=str(e))
            return {"authenticated": False, "error": "Authentication service error"}

    def _get_client_ip(self, scope: dict) -> str:
        """Extract client IP address from ASGI scope."""
        client = scope.get("client")
        if client:
            return client[0]

        # Check for forwarded headers
        headers = dict(scope.get("headers", []))
        for name, value in headers.items():
            if name == b"x-forwarded-for":
                return value.decode("utf-8").split(",")[0].strip()
            elif name == b"x-real-ip":
                return value.decode("utf-8")

        return "unknown"

    async def _send_auth_error(self, send, error_message: str):
        """Send authentication error response."""
        response_body = {
            "detail": "Could not validate credentials",
            "error": error_message,
            "type": "authentication_error",
        }

        import json

        body = json.dumps(response_body).encode()

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"www-authenticate", b"Bearer"],
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
