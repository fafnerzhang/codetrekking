"""
Request logging middleware.
"""

import time
import uuid
from typing import Dict, Any
from fastapi import Request
import structlog

logger = structlog.get_logger(__name__)


async def logging_middleware(request: Request, call_next):
    """Request/response logging middleware."""

    # Generate request ID
    request_id = str(uuid.uuid4())

    # Add request ID to request state
    request.state.request_id = request_id

    # Start timing
    start_time = time.time()

    # Extract request information
    request_info = {
        "request_id": request_id,
        "method": request.method,
        "url": str(request.url),
        "path": request.url.path,
        "query_params": dict(request.query_params),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "content_type": request.headers.get("content-type"),
        "content_length": request.headers.get("content-length"),
    }

    # Try to get user info if authenticated
    user_info = getattr(request.state, "user", None)
    if user_info:
        request_info["user_id"] = user_info.get("user_id")
        request_info["username"] = user_info.get("username")

    # Log request start
    logger.info("Request started", **request_info)

    try:
        # Process request
        response = await call_next(request)

        # Calculate processing time
        processing_time = time.time() - start_time

        # Extract response information
        response_info = {
            "request_id": request_id,
            "status_code": response.status_code,
            "processing_time_ms": round(processing_time * 1000, 2),
            "response_size": response.headers.get("content-length", "unknown"),
        }

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

        # Log response
        if response.status_code >= 400:
            logger.warning(
                "Request completed with error", **{**request_info, **response_info}
            )
        else:
            logger.info(
                "Request completed successfully", **{**request_info, **response_info}
            )

        return response

    except Exception as e:
        # Calculate processing time for failed requests
        processing_time = time.time() - start_time

        # Log error
        logger.error(
            "Request failed with exception",
            **{
                **request_info,
                "processing_time_ms": round(processing_time * 1000, 2),
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        # Re-raise the exception
        raise


class AuditLogger:
    """Audit logger for important operations."""

    def __init__(self):
        self.audit_logger = structlog.get_logger("audit")

    def log_user_action(
        self,
        request: Request,
        action: str,
        user_id: str,
        details: Dict[str, Any] = None,
    ):
        """Log user action for audit trail."""

        audit_entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "action": action,
            "user_id": user_id,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "endpoint": request.url.path,
            "method": request.method,
            "details": details or {},
        }

        self.audit_logger.info("User action", **audit_entry)

    def log_authentication(
        self,
        request: Request,
        auth_type: str,
        user_id: str = None,
        username: str = None,
        success: bool = True,
        failure_reason: str = None,
    ):
        """Log authentication attempts."""

        auth_entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "auth_type": auth_type,
            "user_id": user_id,
            "username": username,
            "success": success,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "failure_reason": failure_reason,
        }

        if success:
            self.audit_logger.info("Authentication successful", **auth_entry)
        else:
            self.audit_logger.warning("Authentication failed", **auth_entry)

    def log_task_creation(
        self,
        request: Request,
        user_id: str,
        task_type: str,
        task_id: str,
        priority: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log task creation for audit trail."""

        task_entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "action": "task_created",
            "user_id": user_id,
            "task_type": task_type,
            "task_id": task_id,
            "priority": priority,
            "ip_address": request.client.host if request.client else "unknown",
            "details": details or {},
        }

        self.audit_logger.info("Task created", **task_entry)

    def log_data_access(
        self,
        request: Request,
        user_id: str,
        data_type: str,
        operation: str,
        resource_id: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log data access for compliance."""

        access_entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "action": "data_access",
            "user_id": user_id,
            "data_type": data_type,
            "operation": operation,
            "resource_id": resource_id,
            "ip_address": request.client.host if request.client else "unknown",
            "details": details or {},
        }

        self.audit_logger.info("Data access", **access_entry)


# Global audit logger instance
audit_logger = AuditLogger()


class SecurityLogger:
    """Security-focused logging for suspicious activities."""

    def __init__(self):
        self.security_logger = structlog.get_logger("security")

    def log_suspicious_activity(
        self,
        request: Request,
        activity_type: str,
        severity: str = "medium",
        details: Dict[str, Any] = None,
    ):
        """Log suspicious activity."""

        security_entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "activity_type": activity_type,
            "severity": severity,
            "ip_address": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown"),
            "endpoint": request.url.path,
            "method": request.method,
            "details": details or {},
        }

        if severity == "high":
            self.security_logger.error("High severity security event", **security_entry)
        elif severity == "medium":
            self.security_logger.warning(
                "Medium severity security event", **security_entry
            )
        else:
            self.security_logger.info("Low severity security event", **security_entry)

    def log_rate_limit_exceeded(
        self,
        request: Request,
        user_id: str = None,
        limit_type: str = "general",
        details: Dict[str, Any] = None,
    ):
        """Log rate limit violations."""

        self.log_suspicious_activity(
            request,
            activity_type="rate_limit_exceeded",
            severity="medium",
            details={"user_id": user_id, "limit_type": limit_type, **(details or {})},
        )

    def log_authentication_failure(
        self,
        request: Request,
        failure_type: str,
        attempted_user: str = None,
        details: Dict[str, Any] = None,
    ):
        """Log authentication failures."""

        self.log_suspicious_activity(
            request,
            activity_type="authentication_failure",
            severity="medium",
            details={
                "failure_type": failure_type,
                "attempted_user": attempted_user,
                **(details or {}),
            },
        )


# Global security logger instance
security_logger = SecurityLogger()
