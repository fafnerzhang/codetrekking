"""
Middleware package initialization.
"""

from .auth import (
    get_current_user,
)

from .rate_limit import (
    RateLimitConfig,
    CustomRateLimiter,
    rate_limit_middleware,
    custom_limiter,
    get_rate_limit_status,
)

from .logging import (
    logging_middleware,
    AuditLogger,
    SecurityLogger,
    audit_logger,
    security_logger,
)

__all__ = [
    # Authentication
    "JWTAuth",
    "APIKeyAuth",
    "get_current_user",
    "get_optional_user",
    "get_api_key_user",
    "jwt_auth",
    "api_key_auth",
    # Rate limiting
    "RateLimitConfig",
    "CustomRateLimiter",
    "rate_limit_middleware",
    "custom_limiter",
    "get_rate_limit_status",
    # Logging
    "logging_middleware",
    "AuditLogger",
    "SecurityLogger",
    "audit_logger",
    "security_logger",
]
