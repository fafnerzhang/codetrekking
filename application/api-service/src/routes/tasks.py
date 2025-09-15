"""
Task management routes.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import structlog

from ..models.tasks import TaskStatus, TaskType, TaskPriority
from ..models.responses import (
    TaskStatusResponse,
    TaskResultResponse,
    BaseResponse,
    TaskProgress,
    TaskArtifact,
    PaginatedResponse,
    PaginationInfo,
)
from ..middleware.auth import get_current_user
from ..database import User
from ..middleware.logging import audit_logger

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


# Mock task storage (in production, this would be a database)
MOCK_TASKS = {}

# Import actual Celery app from peakflow-tasks
try:
    import sys
    sys.path.append('/home/aiuser/codetrekking/application/peakflow-tasks')
    from peakflow_tasks.celery_app import celery_app
except ImportError:
    celery_app = None


def get_mock_task_status(task_id: str, user_id: str) -> Dict[str, Any]:
    """Get mock task status (in production, query from database)."""

    # Generate mock data based on task_id pattern
    if task_id.endswith("1"):
        # Completed task
        return {
            "task_id": task_id,
            "status": TaskStatus.COMPLETED,
            "progress": TaskProgress(
                current_step="Completed",
                progress_percentage=100.0,
                items_processed=10,
                items_total=10,
            ),
            "started_at": datetime.now(timezone.utc) - timedelta(minutes=5),
            "completed_at": datetime.now(timezone.utc) - timedelta(minutes=1),
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }
    elif task_id.endswith("2"):
        # Processing task
        return {
            "task_id": task_id,
            "status": TaskStatus.PROCESSING,
            "progress": TaskProgress(
                current_step="Processing FIT file 3 of 5",
                progress_percentage=60.0,
                items_processed=3,
                items_total=5,
            ),
            "started_at": datetime.now(timezone.utc) - timedelta(minutes=3),
            "completed_at": None,
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }
    elif task_id.endswith("3"):
        # Failed task
        return {
            "task_id": task_id,
            "status": TaskStatus.FAILED,
            "progress": TaskProgress(
                current_step="Failed during data validation",
                progress_percentage=25.0,
                items_processed=1,
                items_total=4,
            ),
            "started_at": datetime.now(timezone.utc) - timedelta(minutes=10),
            "completed_at": datetime.now(timezone.utc) - timedelta(minutes=8),
            "error": "Invalid FIT file format: missing required fields",
            "retry_count": 2,
            "max_retries": 3,
        }
    else:
        # Queued task
        return {
            "task_id": task_id,
            "status": TaskStatus.QUEUED,
            "progress": None,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "retry_count": 0,
            "max_retries": 3,
        }


def get_mock_task_result(task_id: str, user_id: str) -> Dict[str, Any]:
    """Get mock task result (in production, query from database)."""

    # Only return results for completed tasks
    if not task_id.endswith("1"):
        return None

    return {
        "task_id": task_id,
        "status": TaskStatus.COMPLETED,
        "result": {
            "files_processed": 4,
            "records_created": 12500,
            "analytics_generated": 3,
            "elasticsearch_documents": 12500,
            "processing_time_seconds": 45.2,
            "success_rate": 1.0,
            "data_quality_score": 0.95,
        },
        "artifacts": [
            TaskArtifact(
                type="analytics_report",
                url=f"/api/v1/reports/{task_id}.json",
                size_bytes=2048,
                metadata={"format": "json", "compressed": False},
            ),
            TaskArtifact(
                type="processing_log",
                url=f"/api/v1/logs/{task_id}.log",
                size_bytes=8192,
                metadata={"format": "text", "level": "info"},
            ),
        ],
        "processing_time_seconds": 45.2,
        "started_at": datetime.now(timezone.utc) - timedelta(minutes=5),
        "completed_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }


@router.get("/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(
    request: Request, task_id: str, current_user: User = Depends(get_current_user)
):
    """Get task status and progress information."""

    try:
        # Get task status (mock implementation)
        task_data = get_mock_task_status(task_id, current_user.id)

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="task_status",
            operation="read",
            resource_id=task_id,
        )

        return TaskStatusResponse(
            success=True, message="Task status retrieved", **task_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get task status error",
            task_id=task_id,
            user_id=current_user.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task status",
        )


@router.get("/{task_id}/result", response_model=TaskResultResponse)
async def get_task_result(
    request: Request, task_id: str, current_user: User = Depends(get_current_user)
):
    """Get task result and artifacts."""

    try:
        # Get task result (mock implementation)
        result_data = get_mock_task_result(task_id, current_user.id)

        if not result_data:
            # Check if task exists but not completed
            task_data = get_mock_task_status(task_id, current_user.id)
            if task_data:
                if task_data["status"] in [TaskStatus.QUEUED, TaskStatus.PROCESSING]:
                    raise HTTPException(
                        status_code=status.HTTP_202_ACCEPTED,
                        detail="Task is still processing",
                    )
                elif task_data["status"] == TaskStatus.FAILED:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Task failed - no result available",
                    )

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task or result not found"
            )

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="task_result",
            operation="read",
            resource_id=task_id,
        )

        return TaskResultResponse(
            success=True, message="Task result retrieved", **result_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get task result error",
            task_id=task_id,
            user_id=current_user.id,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task result",
        )


@router.delete("/{task_id}")
async def cancel_task(
    request: Request, task_id: str, current_user: User = Depends(get_current_user)
):
    """Cancel a queued or processing task."""

    try:
        # Get current task status
        task_data = get_mock_task_status(task_id, current_user.id)

        if not task_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
            )

        # Check if task can be cancelled
        if task_data["status"] in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel task with status: {task_data['status']}",
            )

        # Mock cancellation (in production, send cancellation message to queue)
        logger.info(
            "Task cancellation requested",
            task_id=task_id,
            user_id=current_user.id,
            current_status=task_data["status"],
        )

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="task_cancelled",
            user_id=current_user.id,
            details={"task_id": task_id, "previous_status": task_data["status"]},
        )

        return BaseResponse(success=True, message="Task cancellation requested")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Cancel task error", task_id=task_id, user_id=current_user.id, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel task",
        )


@router.get("", response_model=PaginatedResponse)
async def list_tasks(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    task_type: Optional[TaskType] = Query(None, description="Filter by task type"),
    status: Optional[TaskStatus] = Query(None, description="Filter by status"),
    priority: Optional[TaskPriority] = Query(None, description="Filter by priority"),
    created_after: Optional[datetime] = Query(
        None, description="Created after timestamp"
    ),
    created_before: Optional[datetime] = Query(
        None, description="Created before timestamp"
    ),
    current_user: User = Depends(get_current_user),
):
    """List user's tasks with filtering and pagination."""

    try:
        # Generate mock task list (in production, query from database)
        mock_tasks = []

        for i in range(1, 51):  # Generate 50 mock tasks
            task_id = f"task_{current_user.id}_{i}"

            # Vary task types
            task_types = list(TaskType)
            task_type_idx = i % len(task_types)

            # Vary statuses
            statuses = list(TaskStatus)
            status_idx = i % len(statuses)

            # Vary priorities
            priorities = list(TaskPriority)
            priority_idx = i % len(priorities)

            mock_task = {
                "task_id": task_id,
                "task_type": task_types[task_type_idx],
                "status": statuses[status_idx],
                "priority": priorities[priority_idx],
                "created_at": datetime.now(timezone.utc) - timedelta(hours=i),
                "started_at": (
                    datetime.now(timezone.utc) - timedelta(hours=i - 1)
                    if i % 3 != 0
                    else None
                ),
                "completed_at": (
                    datetime.now(timezone.utc) - timedelta(hours=i - 2)
                    if i % 4 == 0
                    else None
                ),
            }

            mock_tasks.append(mock_task)

        # Apply filters
        filtered_tasks = mock_tasks

        if task_type:
            filtered_tasks = [t for t in filtered_tasks if t["task_type"] == task_type]

        if status:
            filtered_tasks = [t for t in filtered_tasks if t["status"] == status]

        if priority:
            filtered_tasks = [t for t in filtered_tasks if t["priority"] == priority]

        if created_after:
            filtered_tasks = [
                t for t in filtered_tasks if t["created_at"] >= created_after
            ]

        if created_before:
            filtered_tasks = [
                t for t in filtered_tasks if t["created_at"] <= created_before
            ]

        # Apply pagination
        total_items = len(filtered_tasks)
        total_pages = (total_items + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page

        page_items = filtered_tasks[start_idx:end_idx]

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="task_list",
            operation="read",
            details={
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "filters": {
                    "task_type": task_type.value if task_type else None,
                    "status": status.value if status else None,
                    "priority": priority.value if priority else None,
                },
            },
        )

        return PaginatedResponse(
            success=True,
            message="Tasks retrieved",
            pagination=PaginationInfo(
                page=page,
                per_page=per_page,
                total_items=total_items,
                total_pages=total_pages,
                has_next=page < total_pages,
                has_prev=page > 1,
            ),
            items=page_items,
        )

    except Exception as e:
        logger.error("List tasks error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list tasks",
        )


@router.get("/summary")
async def get_task_summary(
    request: Request, current_user: User = Depends(get_current_user)
):
    """Get task summary statistics for the user."""

    try:
        # Generate mock summary (in production, aggregate from database)
        summary = {
            "total_tasks": 47,
            "by_status": {
                TaskStatus.COMPLETED: 32,
                TaskStatus.PROCESSING: 3,
                TaskStatus.QUEUED: 5,
                TaskStatus.FAILED: 6,
                TaskStatus.CANCELLED: 1,
            },
            "by_type": {
                TaskType.DOWNLOAD_GARMIN_DATA: 15,
                TaskType.PROCESS_FIT_FILE: 20,
                TaskType.ADVANCED_ANALYTICS: 8,
                TaskType.SETUP_GARMIN_USER: 2,
                TaskType.CHECK_EXISTING_DATA: 2,
            },
            "by_priority": {
                TaskPriority.HIGH: 5,
                TaskPriority.NORMAL: 35,
                TaskPriority.LOW: 7,
            },
            "avg_processing_time": 127.5,  # seconds
            "success_rate": 0.85,  # 85%
            "last_activity": datetime.now(timezone.utc) - timedelta(minutes=15),
        }

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="task_summary",
            operation="read",
        )

        return {
            "success": True,
            "message": "Task summary retrieved",
            "user_id": current_user.id,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc),
        }

    except Exception as e:
        logger.error("Get task summary error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get task summary",
        )


@router.post("/garmin-sync")
async def trigger_garmin_sync(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days to sync"),
    current_user: User = Depends(get_current_user),
):
    """Trigger Garmin sync workflow for the authenticated user."""
    
    try:
        if not celery_app:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Task queue service unavailable"
            )
        
        # Trigger Garmin sync task
        from peakflow_tasks.tasks.workflows import garmin_sync_workflow
        task = garmin_sync_workflow.delay(current_user.id, days)
        
        # Log task creation
        audit_logger.log_user_action(
            request=request,
            action="garmin_sync_triggered",
            user_id=current_user.id,
            details={"task_id": task.id, "days": days}
        )
        
        logger.info(
            "Garmin sync task triggered",
            task_id=task.id,
            user_id=current_user.id,
            days=days
        )
        
        return {
            "success": True,
            "message": "Garmin sync task started",
            "task_id": task.id,
            "user_id": current_user.id,
            "days": days,
            "started_at": datetime.now(timezone.utc),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Garmin sync trigger error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger Garmin sync",
        )
