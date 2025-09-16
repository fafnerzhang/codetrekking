"""
Rate limiting middleware.
"""

import time
from typing import Dict, Optional
from fastapi import Request, HTTPException, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

logger = structlog.get_logger(__name__)


class RateLimitConfig:
    """Rate limiting configuration."""

    # Default rate limits per endpoint
    DEFAULT_LIMITS = {
        # Authentication endpoints
        "/api/v1/auth/login": "5/minute",
        "/api/v1/auth/token": "5/minute",
        "/api/v1/auth/refresh": "10/minute",
        # Task creation endpoints (higher limits)
        "/api/v1/garmin/setup-user": "3/minute",
        "/api/v1/garmin/download-data": "10/minute",
        "/api/v1/garmin/process-fit": "20/minute",
        "/api/v1/garmin/analyze": "15/minute",
        # Query endpoints (higher limits)
        "/api/v1/garmin/check-existing": "50/minute",
        "/api/v1/tasks/*": "100/minute",
        # Health and system endpoints
        "/health": "60/minute",
        "/api/v1/health": "60/minute",
        # Default for all other endpoints
        "default": "30/minute",
    }

    # User-specific limits (can be customized per user)
    USER_LIMITS = {
        # Premium users might have higher limits
        "premium": "2x",  # 2x the default limits
        "enterprise": "5x",  # 5x the default limits
        "admin": "unlimited",
    }


def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from authenticated request."""

    # Try to get from JWT token first
    user = getattr(request.state, "user", None)
    if user and "user_id" in user:
        return user["user_id"]

    # Fall back to IP address for unauthenticated requests
    return get_remote_address(request)


def get_rate_limit_key(request: Request) -> str:
    """Generate rate limit key for request."""

    user_id = get_user_id_from_request(request)
    endpoint = request.url.path

    # Create composite key
    return f"{user_id}:{endpoint}"


# Initialize limiter
limiter = Limiter(key_func=get_rate_limit_key, default_limits=["100/minute"])


class CustomRateLimiter:
    """Custom rate limiter with per-user and per-endpoint configuration."""

    def __init__(self):
        self.config = RateLimitConfig()
        self.user_limits_cache = {}  # Cache for user-specific limits

    def get_limit_for_endpoint(self, endpoint: str) -> str:
        """Get rate limit for specific endpoint."""

        # Check for exact match
        if endpoint in self.config.DEFAULT_LIMITS:
            return self.config.DEFAULT_LIMITS[endpoint]

        # Check for pattern matches
        for pattern, limit in self.config.DEFAULT_LIMITS.items():
            if pattern.endswith("*") and endpoint.startswith(pattern[:-1]):
                return limit

        # Return default
        return self.config.DEFAULT_LIMITS["default"]

    def get_user_tier(self, user_id: str) -> str:
        """Get user tier for rate limiting (would query database in production)."""

        # This would be a database lookup in production
        # For now, return default
        return "standard"

    def apply_user_multiplier(self, base_limit: str, user_tier: str) -> str:
        """Apply user tier multiplier to base limit."""

        if user_tier == "admin":
            return "unlimited"

        multiplier_str = self.config.USER_LIMITS.get(user_tier, "1x")

        if multiplier_str == "unlimited":
            return "unlimited"

        # Parse multiplier (e.g., "2x" -> 2)
        if multiplier_str.endswith("x"):
            try:
                multiplier = float(multiplier_str[:-1])
            except ValueError:
                multiplier = 1.0
        else:
            multiplier = 1.0

        # Apply multiplier to base limit
        if multiplier == 1.0:
            return base_limit

        # Parse base limit (e.g., "30/minute" -> 30, "minute")
        parts = base_limit.split("/")
        if len(parts) == 2:
            try:
                count = int(parts[0])
                period = parts[1]
                new_count = int(count * multiplier)
                return f"{new_count}/{period}"
            except ValueError:
                pass

        return base_limit

    async def check_rate_limit(
        self, request: Request, user_id: Optional[str] = None
    ) -> bool:
        """Check if request is within rate limits."""

        endpoint = request.url.path

        # Get user ID
        if not user_id:
            user_id = get_user_id_from_request(request)

        # Get base limit for endpoint
        base_limit = self.get_limit_for_endpoint(endpoint)

        # Get user tier and apply multiplier
        user_tier = self.get_user_tier(user_id)
        final_limit = self.apply_user_multiplier(base_limit, user_tier)

        # Check for unlimited access
        if final_limit == "unlimited":
            return True

        # Use slowapi to check the actual rate limit
        # This is a simplified check - in production you'd use Redis or similar

        logger.debug(
            "Rate limit check",
            user_id=user_id,
            endpoint=endpoint,
            limit=final_limit,
            user_tier=user_tier,
        )

        return True  # Simplified - actual implementation would check Redis/cache


# Global rate limiter instance
custom_limiter = CustomRateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    """Rate limiting middleware."""

    start_time = time.time()

    try:
        # Check rate limit
        user_id = get_user_id_from_request(request)

        # Skip rate limiting for health checks from localhost
        if request.url.path in ["/health", "/"] and request.client.host in [
            "127.0.0.1",
            "localhost",
        ]:
            response = await call_next(request)
            return response

        # Check custom rate limits
        if not await custom_limiter.check_rate_limit(request, user_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": "See documentation",
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Endpoint"] = request.url.path
        response.headers["X-RateLimit-User"] = (
            user_id[:8] + "..." if len(user_id) > 8 else user_id
        )

        processing_time = time.time() - start_time
        response.headers["X-Processing-Time"] = f"{processing_time:.3f}s"

        return response

    except RateLimitExceeded as e:
        logger.warning(
            "Rate limit exceeded",
            user_id=get_user_id_from_request(request),
            endpoint=request.url.path,
            limit=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {e}",
            headers={"Retry-After": "60"},
        )
    except Exception as e:
        logger.error(
            "Error in rate limiting middleware", error=str(e), endpoint=request.url.path
        )
        # Don't block request on rate limiting errors
        response = await call_next(request)
        return response


def get_rate_limit_status(user_id: str, endpoint: str) -> Dict[str, any]:
    """Get current rate limit status for user and endpoint."""

    base_limit = custom_limiter.get_limit_for_endpoint(endpoint)
    user_tier = custom_limiter.get_user_tier(user_id)
    final_limit = custom_limiter.apply_user_multiplier(base_limit, user_tier)

    return {
        "user_id": user_id,
        "endpoint": endpoint,
        "user_tier": user_tier,
        "base_limit": base_limit,
        "effective_limit": final_limit,
        "remaining": "N/A",  # Would need Redis to track actual usage
        "reset_time": "N/A",
    }
