"""
Training plan CRUD endpoints for Mastra workflows.
"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlmodel import Session
import structlog

from ..database import get_db
from ..database.workout_plan_repository import (
    create_training_phase_with_weeks,
    get_training_phase,
    list_training_phases,
    delete_training_phase,
    get_training_week,
    update_training_week,
    create_workout_plan,
    get_workout_plan,
    update_workout_plan,
    delete_workout_plan,
    list_workouts_for_week,
)
from ..models.workout_plans import (
    TrainingPhaseCreateRequest,
    TrainingPhaseResponse,
    TrainingPhaseSummaryResponse,
    TrainingWeekResponse,
    TrainingWeekUpdateRequest,
    WorkoutPlanCreateRequest,
    WorkoutPlanResponse,
    WorkoutPlanUpdateRequest,
)
from ..middleware.auth import get_current_user
from ..middleware.logging import audit_logger
from ..database.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()


# ============================================================================
# TrainingPhase Endpoints
# ============================================================================


@router.post(
    "/training-plans/phases/bulk",
    response_model=TrainingPhaseResponse,
    operation_id="create_training_phase_bulk",
    tags=["training-plans"],
    summary="Create training phase with weeks (bulk insert)",
    description="""
Create a complete training phase with all weeks in one transaction.

**Designed for Mastra phase workflow**: This endpoint allows the phase workflow
to insert both the phase and all its weeks atomically.

**Input**:
- Phase metadata (name, coach_id, phase_type, dates, critical_workouts, notes)
- Array of weeks with week metadata (week_id, week_number, TSS target, focus, notes)
- user_id (optional) - if not provided, uses current authenticated user

**Returns**: Complete phase with nested weeks

**Use Case**: Called by Mastra phase workflow after generating training phase structure
""",
)
async def create_training_phase_bulk(
    request: Request,
    phase_request: TrainingPhaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPhaseResponse:
    """Create training phase with weeks (bulk insert for Mastra workflow)."""

    try:
        # If user_id not provided, use current authenticated user
        user_id = phase_request.user_id if phase_request.user_id else current_user.id

        # Verify user_id matches current user (security check)
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create phase for another user",
            )

        # Check if phase already exists
        existing_phase = get_training_phase(
            db, user_id, phase_request.phase_id, include_weeks=False
        )
        if existing_phase:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Phase '{phase_request.phase_id}' already exists for user",
            )

        # Convert weeks to dict format
        weeks_data = [week.model_dump() for week in phase_request.weeks]

        # Create phase with weeks (matching type.ts structure)
        phase = create_training_phase_with_weeks(
            db=db,
            user_id=user_id,
            phase_id=phase_request.phase_id,
            name=phase_request.name,
            tag=phase_request.tag,
            description=phase_request.description,
            workout_focus=phase_request.workout_focus,
            weeks_data=weeks_data,
        )

        # Get complete phase with weeks
        phase = get_training_phase(
            db, user_id, phase_request.phase_id, include_weeks=True
        )

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="training_phase_created",
            user_id=current_user.id,
            details={
                "phase_id": phase_request.phase_id,
                "phase_name": phase_request.name,
                "week_count": len(phase_request.weeks),
            },
        )

        logger.info(
            f"Created training phase via bulk endpoint",
            user_id=str(current_user.id),
            phase_id=phase_request.phase_id,
        )

        # Convert to response with parsed JSON
        return _convert_phase_to_response(phase)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating training phase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create training phase",
        )


@router.get(
    "/training-plans/phases",
    response_model=List[TrainingPhaseSummaryResponse],
    operation_id="list_training_phases",
    tags=["training-plans"],
    summary="List all training phases for authenticated user",
)
async def list_phases(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[TrainingPhaseSummaryResponse]:
    """List all training phases for the authenticated user."""

    try:
        phases = list_training_phases(db, current_user.id)
        return [_convert_phase_to_summary(p) for p in phases]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing training phases: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list training phases",
        )


@router.get(
    "/training-plans/phases/{phase_id}",
    response_model=TrainingPhaseResponse,
    operation_id="get_training_phase",
    tags=["training-plans"],
    summary="Get training phase with weeks and workouts",
)
async def get_phase(
    request: Request,
    phase_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingPhaseResponse:
    """Get complete training phase with nested weeks and workouts for authenticated user."""

    try:
        phase = get_training_phase(db, current_user.id, phase_id, include_weeks=True)

        if not phase:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found",
            )

        return _convert_phase_to_response(phase)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting training phase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get training phase",
        )


@router.delete(
    "/training-plans/phases/{phase_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_training_phase",
    tags=["training-plans"],
    summary="Delete training phase (cascades to weeks and workouts)",
)
async def delete_phase(
    request: Request,
    phase_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete training phase (cascade deletes weeks and workouts) for authenticated user."""

    try:
        deleted = delete_training_phase(db, current_user.id, phase_id)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Phase '{phase_id}' not found",
            )

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="training_phase_deleted",
            user_id=current_user.id,
            details={"phase_id": phase_id},
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting training phase: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete training phase",
        )


# ============================================================================
# TrainingWeek Endpoints
# ============================================================================


@router.get(
    "/training-plans/weeks/{user_id}/{phase_id}/{week_id}",
    response_model=TrainingWeekResponse,
    operation_id="get_training_week",
    tags=["training-plans"],
    summary="Get training week with workouts",
)
async def get_week(
    request: Request,
    user_id: UUID,
    phase_id: str,
    week_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingWeekResponse:
    """Get training week with nested workouts."""

    try:
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access another user's weeks",
            )

        week = get_training_week(db, user_id, phase_id, week_id, include_workouts=True)

        if not week:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Week '{week_id}' not found",
            )

        return _convert_week_to_response(week)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting training week: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get training week",
        )


@router.put(
    "/training-plans/weeks/{user_id}/{phase_id}/{week_id}",
    response_model=TrainingWeekResponse,
    operation_id="update_training_week",
    tags=["training-plans"],
    summary="Update training week",
)
async def update_week(
    request: Request,
    user_id: UUID,
    phase_id: str,
    week_id: str,
    week_update: TrainingWeekUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TrainingWeekResponse:
    """Update training week."""

    try:
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update another user's weeks",
            )

        week = update_training_week(
            db=db,
            user_id=user_id,
            phase_id=phase_id,
            week_id=week_id,
            weekly_tss_target=week_update.weekly_tss_target,
            focus=week_update.focus,
            notes=week_update.notes,
        )

        if not week:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Week '{week_id}' not found",
            )

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="training_week_updated",
            user_id=current_user.id,
            details={"phase_id": phase_id, "week_id": week_id},
        )

        return _convert_week_to_response(week)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating training week: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update training week",
        )


# ============================================================================
# WorkoutPlan Endpoints
# ============================================================================


@router.post(
    "/training-plans/workouts",
    response_model=WorkoutPlanResponse,
    operation_id="create_workout_plan",
    tags=["training-plans"],
    summary="Create single workout plan",
    description="""
Create a single workout within a training week.

**Designed for Mastra generateDetailedWorkout**: This endpoint allows the
workout generation workflow to insert individual workouts into an existing week.

**Input**:
- Foreign keys: user_id, phase_id, week_id
- Workout metadata: name, day_of_week, workout_type
- Workout structure: segments (JSON), workout_metadata (JSON)

**Returns**: Created workout with all fields

**Use Case**: Called by Mastra after generating detailed workout with segments
""",
)
async def create_workout(
    request: Request,
    workout_request: WorkoutPlanCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutPlanResponse:
    """Create single workout plan (for Mastra generateDetailedWorkout)."""

    try:
        # Use authenticated user if user_id not provided
        user_id = workout_request.user_id if workout_request.user_id else current_user.id

        # Verify user_id matches current user
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create workout for another user",
            )

        # Verify week exists
        week = get_training_week(
            db,
            user_id,
            workout_request.phase_id,
            workout_request.week_id,
            include_workouts=False,
        )
        if not week:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Week '{workout_request.week_id}' not found",
            )

        workout = create_workout_plan(
            db=db,
            user_id=user_id,
            phase_id=workout_request.phase_id,
            week_id=workout_request.week_id,
            name=workout_request.name,
            day_of_week=workout_request.day_of_week,
            workout_type=workout_request.workout_type,
            segments=workout_request.segments,
            workout_metadata=workout_request.workout_metadata,
        )

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="workout_plan_created",
            user_id=current_user.id,
            details={
                "workout_id": str(workout.id),
                "workout_name": workout_request.name,
                "phase_id": workout_request.phase_id,
                "week_id": workout_request.week_id,
            },
        )

        logger.info(
            f"Created workout plan",
            user_id=str(current_user.id),
            workout_id=str(workout.id),
        )

        return _convert_workout_to_response(workout)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workout plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create workout plan",
        )


@router.get(
    "/training-plans/workouts/{workout_id}",
    response_model=WorkoutPlanResponse,
    operation_id="get_workout_plan",
    tags=["training-plans"],
    summary="Get workout plan by ID",
)
async def get_workout(
    request: Request,
    workout_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutPlanResponse:
    """Get workout plan by ID."""

    try:
        workout = get_workout_plan(db, workout_id)

        if not workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workout '{workout_id}' not found",
            )

        # Verify access
        if workout.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot access another user's workouts",
            )

        return _convert_workout_to_response(workout)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workout plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get workout plan",
        )


@router.put(
    "/training-plans/workouts/{workout_id}",
    response_model=WorkoutPlanResponse,
    operation_id="update_workout_plan",
    tags=["training-plans"],
    summary="Update workout plan",
)
async def update_workout(
    request: Request,
    workout_id: UUID,
    workout_update: WorkoutPlanUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkoutPlanResponse:
    """Update workout plan."""

    try:
        # Verify workout exists and user has access
        existing_workout = get_workout_plan(db, workout_id)
        if not existing_workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workout '{workout_id}' not found",
            )

        if existing_workout.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot update another user's workouts",
            )

        workout = update_workout_plan(
            db=db,
            workout_id=workout_id,
            name=workout_update.name,
            day_of_week=workout_update.day_of_week,
            workout_type=workout_update.workout_type,
            segments=workout_update.segments,
            workout_metadata=workout_update.workout_metadata,
        )

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="workout_plan_updated",
            user_id=current_user.id,
            details={"workout_id": str(workout_id)},
        )

        return _convert_workout_to_response(workout)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating workout plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update workout plan",
        )


@router.delete(
    "/training-plans/workouts/{workout_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    operation_id="delete_workout_plan",
    tags=["training-plans"],
    summary="Delete workout plan",
)
async def delete_workout(
    request: Request,
    workout_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete workout plan."""

    try:
        # Verify workout exists and user has access
        existing_workout = get_workout_plan(db, workout_id)
        if not existing_workout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Workout '{workout_id}' not found",
            )

        if existing_workout.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot delete another user's workouts",
            )

        deleted = delete_workout_plan(db, workout_id)

        # Log audit
        audit_logger.log_user_action(
            request=request,
            action="workout_plan_deleted",
            user_id=current_user.id,
            details={"workout_id": str(workout_id)},
        )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting workout plan: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete workout plan",
        )


# ============================================================================
# Helper Functions
# ============================================================================


def _convert_phase_to_response(phase) -> TrainingPhaseResponse:
    """Convert TrainingPhase to response format with parsed JSON."""
    import json

    return TrainingPhaseResponse(
        user_id=phase.user_id,
        phase_id=phase.phase_id,
        name=phase.name,
        tag=phase.tag,
        description=phase.description,
        workout_focus=json.loads(phase.workout_focus) if phase.workout_focus else None,
        coach_id=phase.coach_id,
        start_date=phase.start_date,
        end_date=phase.end_date,
        phase_type=phase.phase_type,
        critical_workouts=json.loads(phase.critical_workouts) if phase.critical_workouts else None,
        notes=phase.notes,
        created_at=phase.created_at,
        updated_at=phase.updated_at,
        weeks=[_convert_week_to_response(w) for w in phase.weeks] if phase.weeks else [],
    )


def _convert_phase_to_summary(phase) -> TrainingPhaseSummaryResponse:
    """Convert TrainingPhase to summary response (no nested weeks)."""
    import json

    return TrainingPhaseSummaryResponse(
        user_id=phase.user_id,
        phase_id=phase.phase_id,
        name=phase.name,
        tag=phase.tag,
        description=phase.description,
        workout_focus=json.loads(phase.workout_focus) if phase.workout_focus else None,
        coach_id=phase.coach_id,
        start_date=phase.start_date,
        end_date=phase.end_date,
        phase_type=phase.phase_type,
        created_at=phase.created_at,
        updated_at=phase.updated_at,
    )


def _convert_week_to_response(week) -> TrainingWeekResponse:
    """Convert TrainingWeek to response format with parsed JSON."""
    import json

    return TrainingWeekResponse(
        user_id=week.user_id,
        phase_id=week.phase_id,
        week_id=week.week_id,
        week_number=week.week_number,
        start_date=week.start_date,
        end_date=week.end_date,
        description=week.description,
        weekly_mileage=week.weekly_mileage,
        critical_workouts=json.loads(week.critical_workouts) if week.critical_workouts else None,
        weekly_tss_target=week.weekly_tss_target,
        focus=week.focus,
        notes=week.notes,
        created_at=week.created_at,
        updated_at=week.updated_at,
        workouts=[_convert_workout_to_response(w) for w in week.workouts] if week.workouts else [],
    )


def _convert_workout_to_response(workout) -> WorkoutPlanResponse:
    """Convert WorkoutPlan to response format with parsed JSON."""
    import json

    return WorkoutPlanResponse(
        id=workout.id,
        user_id=workout.user_id,
        phase_id=workout.phase_id,
        week_id=workout.week_id,
        name=workout.name,
        day_of_week=workout.day_of_week,
        workout_type=workout.workout_type,
        segments=json.loads(workout.segments) if workout.segments else None,
        workout_metadata=json.loads(workout.workout_metadata)
        if workout.workout_metadata
        else None,
        created_at=workout.created_at,
        updated_at=workout.updated_at,
    )
