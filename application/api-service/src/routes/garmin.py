"""
Garmin data pipeline routes.
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Query
import structlog

from ..models.requests import (
    ProcessFitRequest,
    CompleteSyncRequest,
)
from ..models.responses import (
    ProcessingResponse,
    CheckExistingResponse,
    TaskResponse,
    ProcessingEstimate,
    ActivityStatus,
    FileMetadata,
)
from ..middleware.auth import get_current_user
from ..middleware.logging import audit_logger
from ..settings import get_settings
from ..database import User
from peakflow_tasks.api import TaskManager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/garmin", tags=["garmin"])


@router.post("/complete-sync", response_model=TaskResponse)
async def complete_garmin_sync(
    request: Request,
    sync_request: CompleteSyncRequest,
    current_user: User = Depends(get_current_user),
):
    """Trigger complete Garmin sync workflow (download + process + index)."""

    try:
        # Get task manager
        task_manager = TaskManager()

        # Trigger complete sync workflow
        task_id = task_manager.trigger_complete_sync(
            user_id=str(current_user.id),
            start_date=sync_request.start_date.strftime("%Y-%m-%d"),
            days=sync_request.days,
            priority=sync_request.priority.value,
        )

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="complete_sync_initiated",
            user_id=current_user.id,
            details={
                "start_date": sync_request.start_date.strftime("%Y-%m-%d"),
                "days": sync_request.days,
                "priority": sync_request.priority.value,
            },
        )

        # Calculate estimated completion time
        estimated_completion = datetime.utcnow() + timedelta(
            minutes=max(30, sync_request.days * 5)  # 5 minutes per day minimum
        )

        return TaskResponse(
            success=True,
            message="Complete Garmin sync workflow initiated",
            task_id=task_id,
            status="queued",
            user_id=str(current_user.id),
            estimated_completion=estimated_completion,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Complete sync initiation error", user_id=current_user.id, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate complete sync workflow",
        )


@router.post("/process-fit", response_model=ProcessingResponse)
async def process_fit_files(
    request: Request,
    process_request: ProcessFitRequest,
    current_user: User = Depends(get_current_user),
):
    """Process FIT files and upload to Elasticsearch."""

    try:
        # Determine files to process
        if process_request.activity_ids:
            files_to_process = len(process_request.activity_ids)
        elif process_request.file_paths:
            files_to_process = len(process_request.file_paths)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must specify either activity_ids or file_paths",
            )

        # Calculate processing estimate
        estimated_records = files_to_process * 2000  # ~2000 records per file estimate

        processing_estimate = ProcessingEstimate(
            files_to_process=files_to_process,
            estimated_records=estimated_records,
            individual_tasks=process_request.processing_options.process_individually,
        )

        # Get task manager
        task_manager = TaskManager()

        task_ids = []

        if process_request.processing_options.create_separate_tasks:
            # Create individual tasks for each file/activity

            if process_request.activity_ids:
                for activity_id in process_request.activity_ids:
                    task_id = task_manager.trigger_fit_processing(
                        user_id=str(current_user.id),
                        activity_id=activity_id,
                        fit_file_path=get_settings().get_fit_file_path(
                            str(current_user.id), activity_id, "fit"
                        ),
                        processing_options=process_request.processing_options.model_dump(),
                        priority=process_request.priority.value,
                    )
                    task_ids.append(task_id)

            elif process_request.file_paths:
                for file_path in process_request.file_paths:
                    # Extract activity ID from file path (simplified)
                    activity_id = file_path.split("/")[-1].replace(".fit", "")

                    task_id = task_manager.trigger_fit_processing(
                        user_id=str(current_user.id),
                        activity_id=activity_id,
                        fit_file_path=file_path,
                        processing_options=process_request.processing_options.model_dump(),
                        priority=process_request.priority.value,
                    )
                    task_ids.append(task_id)

        else:
            # Create single batch task
            fit_files = []
            if process_request.activity_ids:
                for activity_id in process_request.activity_ids:
                    fit_files.append(
                        {
                            "activity_id": activity_id,
                            "fit_file_path": get_settings().get_fit_file_path(
                                str(current_user.id), activity_id, "fit"
                            ),
                        }
                    )
            elif process_request.file_paths:
                for file_path in process_request.file_paths:
                    activity_id = file_path.split("/")[-1].replace(".fit", "")
                    fit_files.append(
                        {"activity_id": activity_id, "fit_file_path": file_path}
                    )

            task_id = task_manager.trigger_batch_fit_processing(
                user_id=str(current_user.id),
                fit_files=fit_files,
                processing_options=process_request.processing_options.model_dump(),
                priority=process_request.priority.value,
            )
            task_ids = [task_id]

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="fit_processing_initiated",
            user_id=current_user.id,
            details={
                "files_count": files_to_process,
                "individual_tasks": len(task_ids),
                "processing_options": process_request.processing_options.model_dump(),
            },
        )

        # Calculate estimated completion time
        estimated_completion = datetime.utcnow() + timedelta(
            minutes=max(10, files_to_process * 2)  # 2 minutes per file minimum
        )

        return ProcessingResponse(
            success=True,
            message="FIT file processing initiated",
            task_ids=task_ids,
            status="queued",
            total_tasks=len(task_ids),
            user_id=str(current_user.id),
            processing_estimate=processing_estimate,
            estimated_completion=estimated_completion,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "FIT processing initiation error", user_id=current_user.id, error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initiate FIT processing",
        )


# Analytics endpoint removed


@router.get("/check-existing", response_model=CheckExistingResponse)
async def check_existing_data(
    request: Request,
    user_id: Optional[str] = Query(
        None, description="User ID (defaults to current user)"
    ),
    activity_ids: str = Query(..., description="Comma-separated activity IDs"),
    verify_data_completeness: bool = Query(
        True, description="Verify data completeness"
    ),
    check_processing_status: bool = Query(True, description="Check processing status"),
    include_file_metadata: bool = Query(True, description="Include file metadata"),
    current_user: User = Depends(get_current_user),
):
    """Check existing data in Elasticsearch."""

    start_time = datetime.utcnow()

    try:
        # Use current user if not specified
        target_user_id = user_id or current_user.id

        # Parse activity IDs
        activity_id_list = [
            aid.strip() for aid in activity_ids.split(",") if aid.strip()
        ]

        if not activity_id_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one activity ID must be provided",
            )

        # Log data access
        audit_logger.log_data_access(
            request=request,
            user_id=current_user.id,
            data_type="activity_data",
            operation="check_existing",
            details={
                "target_user_id": target_user_id,
                "activity_count": len(activity_id_list),
            },
        )

        # Mock Elasticsearch check (in production, this would query Elasticsearch)
        existing_activities = []
        exclude_list = []
        needs_processing = []

        for activity_id in activity_id_list:
            # Simulate different states for demonstration
            if activity_id.endswith("1"):
                # Exists and complete
                status = ActivityStatus(
                    activity_id=activity_id,
                    exists=True,
                    data_complete=True,
                    processing_status="completed",
                    last_updated=datetime.utcnow() - timedelta(hours=1),
                    file_metadata=(
                        FileMetadata(
                            file_size=51200,
                            checksum="sha256:abc123...",
                            file_path=get_settings().get_fit_file_path(
                                str(target_user_id), activity_id, "fit"
                            ),
                        )
                        if include_file_metadata
                        else None
                    ),
                )
                exclude_list.append(activity_id)

            elif activity_id.endswith("2"):
                # Exists but incomplete
                status = ActivityStatus(
                    activity_id=activity_id,
                    exists=True,
                    data_complete=False,
                    processing_status="partial",
                    last_updated=datetime.utcnow() - timedelta(hours=6),
                )
                needs_processing.append(activity_id)

            else:
                # Does not exist
                status = ActivityStatus(activity_id=activity_id, exists=False)
                needs_processing.append(activity_id)

            existing_activities.append(status)

        # Calculate response time
        response_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return CheckExistingResponse(
            success=True,
            message="Data check completed",
            user_id=target_user_id,
            total_checked=len(activity_id_list),
            existing_activities=existing_activities,
            exclude_activity_list=exclude_list,
            needs_processing=needs_processing,
            response_time_ms=response_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Check existing data error", user_id=current_user.id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check existing data",
        )
