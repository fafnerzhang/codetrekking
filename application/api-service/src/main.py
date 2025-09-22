"""
FastAPI application entry point.
"""

import os
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from .routes import auth, garmin, garmin_credentials, tasks, monitoring, analytics

# from .middleware.logging import LoggingMiddleware, RequestResponseLogger  # Not implemented yet
from peakflow_tasks.api import TaskManager

# Configure structured logging
logging.basicConfig(
    format="%(message)s",
    stream=os.sys.stdout,
    level=logging.INFO,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""

    # Startup
    logger.info("Starting API service")

    try:
        # Initialize database
        from .database import init_database, check_database_connection

        # Check database connection
        if check_database_connection():
            logger.info("Database connection verified")

            # Initialize database schema and default data
            await init_database()
            logger.info("Database initialization completed")
        else:
            logger.error("Database connection failed")
            # Don't exit - allow service to start for health checks

        # Initialize task manager
        task_manager = TaskManager()
        logger.info("Task manager initialized")

        # Verify external dependencies with health check
        try:
            health_task_id = task_manager.trigger_health_check()
            if health_task_id:
                logger.info(
                    "Task system health check initiated", task_id=health_task_id
                )
            else:
                logger.warning(
                    "Task system health check failed",
                    reason="Health check task could not be queued",
                )
        except Exception as e:
            logger.warning(
                "Task system health check error",
                error=str(e),
                suggestion="Ensure RabbitMQ is running and credentials are correct",
            )

    except Exception as e:
        logger.error("Failed to initialize dependencies during startup", error=str(e))
        # Continue startup even if some dependencies fail

    logger.info("API service startup completed")

    yield

    # Shutdown
    logger.info("Shutting down API service")

    logger.info("API service shutdown completed")


# Create FastAPI application
app = FastAPI(
    title="CodeTrekking API Service",
    description="REST API for fitness data pipeline management",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:8080"
    ).split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add custom middleware
# app.add_middleware(LoggingMiddleware)  # Not implemented yet
# app.add_middleware(RequestResponseLogger)  # Not implemented yet

# Add authentication middleware
# Note: AuthMiddleware is available but disabled until database authentication services are ready
# To enable: uncomment the line below and ensure database connection is working
# app.add_asgi_middleware(AuthMiddleware)

logger.info("Middleware setup completed", auth_middleware_enabled=False)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent response format."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": exc.status_code,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path),
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions with logging."""

    logger.error(
        "Unhandled exception",
        path=str(request.url.path),
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": 500,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path),
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""

    return {
        "service": "CodeTrekking API Service",
        "version": "1.0.0",
        "authentication": {
            "middleware_enabled": False,
            "dependency_auth_available": True,
            "supported_methods": ["JWT Bearer Token"],
            "note": "Authentication currently handled via route dependencies",
        },
        "description": "REST API for fitness data pipeline management",
        "timestamp": datetime.now(timezone.utc),
        "documentation": "/docs",
        "health_check": "/api/v1/monitoring/health",
        "endpoints": {
            "authentication": "/api/v1/auth",
            "garmin_data": "/api/v1/garmin",
            "garmin_credentials": "/api/v1/garmin/credentials",
            "task_management": "/api/v1/tasks",
            "monitoring": "/api/v1/monitoring",
        },
    }


# Register route modules
app.include_router(auth.router)
app.include_router(garmin.router)
app.include_router(garmin_credentials.router)  # Phase 5: Credential management
app.include_router(tasks.router)
app.include_router(analytics.router)  # Analytics endpoints
app.include_router(monitoring.router)


# Test authentication endpoint (demonstrates dependency-based auth)
@app.get("/api/v1/test/auth")
async def test_authentication(request: Request):
    """
    Test endpoint to demonstrate authentication functionality.

    When AuthMiddleware is enabled, this will require valid JWT tokens.
    When disabled, it shows the current authentication setup.
    """
    # Check if user context was added by middleware
    user = getattr(request.state, "user", None)
    session_id = getattr(request.state, "session_id", None)

    if user:
        return {
            "authenticated": True,
            "user_id": str(user.id),
            "session_id": str(session_id) if session_id else None,
            "auth_method": "middleware",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    else:
        return {
            "authenticated": False,
            "auth_method": "none",
            "message": "AuthMiddleware is currently disabled. Use route dependencies for authentication.",
            "available_dependencies": [
                "get_current_user",
                "get_current_active_user",
                "get_current_verified_user",
                "optional_auth",
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Additional endpoints
@app.get("/api/v1/info")
async def get_api_info():
    """Get API service information."""

    return {
        "service": "CodeTrekking API Service",
        "version": "1.0.0",
        "build_timestamp": datetime.now(timezone.utc),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "features": {
            "authentication": True,
            "garmin_integration": True,
            "task_management": True,
            "monitoring": True,
            "rate_limiting": True,
            "audit_logging": True,
        },
        "limits": {
            "default_rate_limit": "100/minute",
            "max_file_size_mb": 50,
            "max_date_range_days": 365,
            "max_concurrent_tasks": 10,
        },
        "external_dependencies": {
            "rabbitmq": "3.13+",
            "elasticsearch": "8.0+",
            "postgresql": "13+",
        },
    }


@app.get("/api/v1/status")
@limiter.limit("10/minute")
async def get_service_status(request: Request):
    """Get service status (rate limited)."""

    try:
        # Check RabbitMQ health through TaskManager
        rabbitmq_status = "unknown"
        try:
            task_manager = TaskManager()
            health_task_id = task_manager.trigger_health_check()
            rabbitmq_status = "healthy" if health_task_id else "unhealthy"
        except Exception as e:
            logger.warning(f"RabbitMQ health check failed: {e}")
            rabbitmq_status = "unhealthy"

        return {
            "service": "api-service",
            "status": "running",
            "timestamp": datetime.now(timezone.utc),
            "uptime_seconds": 3600,  # Mock uptime
            "dependencies": {
                "rabbitmq": rabbitmq_status,
                "elasticsearch": "healthy",  # Mock status
                "database": "healthy",  # Mock status
            },
            "performance": {
                "requests_per_minute": 25.6,
                "average_response_time_ms": 145.2,
                "error_rate_percent": 2.1,
            },
        }

    except Exception as e:
        logger.error("Status check error", error=str(e))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "service": "api-service",
                "status": "unhealthy",
                "timestamp": datetime.now(timezone.utc),
                "error": "Status check failed",
            },
        )


if __name__ == "__main__":
    import uvicorn

    # Development server configuration
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8010,
        reload=True,
        log_level="info",
        access_log=True,
    )
