"""
System monitoring and health check routes.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
import structlog
import asyncio
import time

from ..models.responses import BaseResponse
from peakflow_tasks.api import TaskManager
from ..middleware.auth import get_current_user
from ..database import User
from ..middleware.logging import audit_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])


async def check_rabbitmq_health() -> Dict[str, Any]:
    """Check RabbitMQ connection and queue health."""
    try:
        task_manager = TaskManager()

        # Test connection with health check task
        start_time = time.time()
        health_task_id = task_manager.trigger_health_check()
        response_time = (time.time() - start_time) * 1000  # ms

        # For now, assume healthy if task was created successfully
        connection_status = True if health_task_id else False

        return {
            "service": "rabbitmq",
            "status": "healthy" if connection_status else "unhealthy",
            "response_time_ms": round(response_time, 2),
            "timestamp": datetime.utcnow(),
            "details": {
                "connection": "ok" if connection_status else "failed",
                "queues_accessible": connection_status,
                "health_task_id": health_task_id,
            },
        }
    except Exception as e:
        return {
            "service": "rabbitmq",
            "status": "unhealthy",
            "response_time_ms": None,
            "timestamp": datetime.utcnow(),
            "error": str(e),
            "details": {"connection": "failed", "queues_accessible": False},
        }


async def check_elasticsearch_health() -> Dict[str, Any]:
    """Check Elasticsearch cluster health."""
    try:
        # Mock Elasticsearch health check (in production, use actual ES client)
        start_time = time.time()

        # Simulate network call
        await asyncio.sleep(0.1)

        response_time = (time.time() - start_time) * 1000  # ms

        # Mock healthy response
        return {
            "service": "elasticsearch",
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "timestamp": datetime.utcnow(),
            "details": {
                "cluster_status": "green",
                "number_of_nodes": 1,
                "active_primary_shards": 15,
                "active_shards": 15,
                "relocating_shards": 0,
                "initializing_shards": 0,
                "unassigned_shards": 0,
            },
        }
    except Exception as e:
        return {
            "service": "elasticsearch",
            "status": "unhealthy",
            "response_time_ms": None,
            "timestamp": datetime.utcnow(),
            "error": str(e),
            "details": {"cluster_status": "red", "connection": "failed"},
        }


async def check_database_health() -> Dict[str, Any]:
    """Check database connection health."""
    try:
        # Mock database health check (in production, use actual DB client)
        start_time = time.time()

        # Simulate database query
        await asyncio.sleep(0.05)

        response_time = (time.time() - start_time) * 1000  # ms

        return {
            "service": "database",
            "status": "healthy",
            "response_time_ms": round(response_time, 2),
            "timestamp": datetime.utcnow(),
            "details": {
                "connection_pool": "ok",
                "active_connections": 5,
                "max_connections": 100,
                "database_size_mb": 1024,
            },
        }
    except Exception as e:
        return {
            "service": "database",
            "status": "unhealthy",
            "response_time_ms": None,
            "timestamp": datetime.utcnow(),
            "error": str(e),
            "details": {"connection": "failed"},
        }


def get_system_metrics() -> Dict[str, Any]:
    """Get system resource metrics."""
    try:
        # Mock system metrics (in production, use psutil or similar)
        return {
            "cpu": {"usage_percent": 25.5, "load_average": [1.2, 1.4, 1.1]},
            "memory": {
                "usage_percent": 68.2,
                "used_mb": 2048,
                "available_mb": 1024,
                "total_mb": 3072,
            },
            "disk": {
                "usage_percent": 45.8,
                "used_gb": 23.5,
                "free_gb": 27.8,
                "total_gb": 51.3,
            },
            "network": {
                "bytes_sent": 1024000,
                "bytes_received": 2048000,
                "packets_sent": 1500,
                "packets_received": 2200,
            },
            "timestamp": datetime.utcnow(),
        }
    except Exception as e:
        logger.error("Failed to get system metrics", error=str(e))
        return {
            "error": "Failed to retrieve system metrics",
            "timestamp": datetime.utcnow(),
        }


@router.get("/health")
async def health_check(request: Request):
    """Basic health check endpoint."""

    try:
        return {
            "status": "healthy",
            "service": "api-service",
            "timestamp": datetime.utcnow(),
            "version": "1.0.0",
            "uptime_seconds": 3600,  # Mock uptime
            "environment": "production",
        }

    except Exception as e:
        logger.error("Health check error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed",
        )


@router.get("/health/detailed")
async def detailed_health_check(
    request: Request, current_user: User = Depends(get_current_user)
):
    """Detailed health check including external dependencies."""

    try:
        # Run all health checks concurrently
        health_checks = await asyncio.gather(
            check_rabbitmq_health(),
            check_elasticsearch_health(),
            check_database_health(),
            return_exceptions=True,
        )

        rabbitmq_health, elasticsearch_health, database_health = health_checks

        # Determine overall system health
        services = [rabbitmq_health, elasticsearch_health, database_health]
        healthy_services = sum(
            1 for s in services if isinstance(s, dict) and s.get("status") == "healthy"
        )
        total_services = len(services)

        overall_status = (
            "healthy"
            if healthy_services == total_services
            else ("degraded" if healthy_services > 0 else "unhealthy")
        )

        # Log health check access (admin only)
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="system_health",
            operation="read",
        )

        return {
            "status": overall_status,
            "service": "api-service",
            "timestamp": datetime.utcnow(),
            "version": "1.0.0",
            "healthy_services": healthy_services,
            "total_services": total_services,
            "services": {
                "rabbitmq": rabbitmq_health,
                "elasticsearch": elasticsearch_health,
                "database": database_health,
            },
            "system_metrics": get_system_metrics(),
        }

    except Exception as e:
        logger.error(
            "Detailed health check error", user_id=current_user.id, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detailed health check failed",
        )


@router.get("/metrics")
async def get_system_metrics_endpoint(
    request: Request, current_user: User = Depends(get_current_user)
):
    """Get system performance metrics."""

    try:
        metrics = get_system_metrics()

        # Add API-specific metrics
        api_metrics = {
            "requests": {
                "total_requests": 12450,
                "requests_per_minute": 25.6,
                "average_response_time_ms": 145.2,
                "error_rate_percent": 2.1,
            },
            "authentication": {
                "active_sessions": 87,
                "successful_logins_24h": 156,
                "failed_logins_24h": 12,
            },
            "tasks": {
                "queued_tasks": 15,
                "processing_tasks": 8,
                "completed_tasks_24h": 342,
                "failed_tasks_24h": 18,
            },
        }

        # Log metrics access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="system_metrics",
            operation="read",
        )

        return {
            "success": True,
            "message": "System metrics retrieved",
            "timestamp": datetime.utcnow(),
            "system": metrics,
            "api": api_metrics,
        }

    except Exception as e:
        logger.error("Get system metrics error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system metrics",
        )


@router.get("/logs")
async def get_system_logs(
    request: Request,
    level: str = "INFO",
    lines: int = 100,
    service: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get recent system logs (admin only)."""

    try:
        # Check if user has admin privileges (in production, check actual permissions)
        if not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

        # Mock log entries (in production, read from actual log files)
        mock_logs = []
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        services = ["api-service", "worker", "rabbitmq", "elasticsearch"]

        for i in range(lines):
            log_level = log_levels[i % len(log_levels)]
            log_service = services[i % len(services)]

            # Skip if filtering by service
            if service and log_service != service:
                continue

            # Skip if log level is below requested level
            level_priority = {"DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3}
            if level_priority.get(log_level, 0) < level_priority.get(level, 1):
                continue

            mock_logs.append(
                {
                    "timestamp": datetime.utcnow() - timedelta(minutes=i),
                    "level": log_level,
                    "service": log_service,
                    "message": f"Sample log message {i} from {log_service}",
                    "context": {
                        "request_id": f"req_{i:06d}",
                        "user_id": f"user_{i % 10}",
                        "component": "router" if i % 2 == 0 else "middleware",
                    },
                }
            )

        # Sort by timestamp (newest first)
        mock_logs.sort(key=lambda x: x["timestamp"], reverse=True)

        # Log admin access
        audit_logger.log_user_action(
            request=request,
            action="logs_accessed",
            user_id=current_user.id,
            details={"level": level, "lines": lines, "service": service},
        )

        return {
            "success": True,
            "message": "System logs retrieved",
            "timestamp": datetime.utcnow(),
            "filters": {"level": level, "lines": lines, "service": service},
            "logs": mock_logs[:lines],  # Limit to requested number of lines
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get system logs error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system logs",
        )


@router.get("/alerts")
async def get_system_alerts(
    request: Request,
    active_only: bool = True,
    severity: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """Get system alerts and notifications."""

    try:
        # Mock system alerts (in production, read from alerting system)
        mock_alerts = [
            {
                "alert_id": "alert_001",
                "severity": "WARNING",
                "service": "elasticsearch",
                "title": "High disk usage",
                "description": "Elasticsearch data directory is 85% full",
                "created_at": datetime.utcnow() - timedelta(hours=2),
                "resolved_at": None,
                "is_active": True,
            },
            {
                "alert_id": "alert_002",
                "severity": "INFO",
                "service": "api-service",
                "title": "High request volume",
                "description": "API request rate is above normal baseline",
                "created_at": datetime.utcnow() - timedelta(hours=1),
                "resolved_at": None,
                "is_active": True,
            },
            {
                "alert_id": "alert_003",
                "severity": "ERROR",
                "service": "worker",
                "title": "Task processing failure",
                "description": "Multiple FIT file processing tasks have failed",
                "created_at": datetime.utcnow() - timedelta(hours=6),
                "resolved_at": datetime.utcnow() - timedelta(hours=4),
                "is_active": False,
            },
        ]

        # Apply filters
        filtered_alerts = mock_alerts

        if active_only:
            filtered_alerts = [a for a in filtered_alerts if a["is_active"]]

        if severity:
            filtered_alerts = [
                a for a in filtered_alerts if a["severity"] == severity.upper()
            ]

        # Log alert access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="system_alerts",
            operation="read",
            details={
                "active_only": active_only,
                "severity": severity,
                "alert_count": len(filtered_alerts),
            },
        )

        return {
            "success": True,
            "message": "System alerts retrieved",
            "timestamp": datetime.utcnow(),
            "filters": {"active_only": active_only, "severity": severity},
            "alert_count": len(filtered_alerts),
            "alerts": filtered_alerts,
        }

    except Exception as e:
        logger.error("Get system alerts error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get system alerts",
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(
    request: Request, alert_id: str, current_user: User = Depends(get_current_user)
):
    """Resolve a system alert (admin only)."""

    try:
        # Check admin privileges
        if not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required",
            )

        # Mock alert resolution (in production, update alerting system)
        logger.info(
            "Alert resolution requested", alert_id=alert_id, user_id=current_user.id
        )

        # Log admin action
        audit_logger.log_user_action(
            request=request,
            action="alert_resolved",
            user_id=current_user.id,
            details={"alert_id": alert_id},
        )

        return BaseResponse(
            success=True, message=f"Alert {alert_id} resolved successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Resolve alert error",
            alert_id=alert_id,
            user_id=current_user.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert",
        )
