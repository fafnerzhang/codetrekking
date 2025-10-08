"""
Repository for workout plan CRUD operations.
"""

import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
import structlog

from .models import TrainingPhase, TrainingWeek, WorkoutPlan

logger = structlog.get_logger(__name__)


# ============================================================================
# TrainingPhase CRUD
# ============================================================================


def create_training_phase_with_weeks(
    db: Session,
    user_id: UUID,
    phase_id: str,
    name: str,
    tag: str,
    description: str,
    workout_focus: List[str],
    weeks_data: List[Dict[str, Any]],
) -> TrainingPhase:
    """Create training phase with weeks (bulk insert for Mastra workflow)."""

    # Calculate start/end dates from weeks
    start_date = weeks_data[0].get('start_date') if weeks_data else None
    end_date = weeks_data[-1].get('end_date') if weeks_data else None

    # Create phase - use type.ts aligned fields directly
    phase = TrainingPhase(
        user_id=user_id,
        phase_id=phase_id,
        name=name,
        tag=tag,
        description=description,
        workout_focus=json.dumps(workout_focus),
        coach_id=None,
        phase_type=tag,  # Legacy field, duplicate of tag for backward compat
        start_date=start_date,
        end_date=end_date,
        critical_workouts=None,  # Legacy field, not used
        notes=None,  # Additional notes field
    )

    db.add(phase)
    db.flush()  # Ensure phase exists before adding weeks

    # Create weeks - use type.ts aligned fields directly
    for index, week_data in enumerate(weeks_data):
        critical_workouts_json = json.dumps(week_data.get("critical_workouts", []))

        week = TrainingWeek(
            user_id=user_id,
            phase_id=phase_id,
            week_id=week_data["week_id"],
            week_number=index + 1,
            start_date=week_data.get("start_date"),
            end_date=week_data.get("end_date"),
            description=week_data.get("description"),
            weekly_mileage=week_data.get("weekly_mileage"),
            critical_workouts=critical_workouts_json,
            # Legacy fields for backward compat
            weekly_tss_target=None,
            focus=week_data.get("description"),  # Duplicate description to focus for legacy
            notes=None,
        )
        db.add(week)

    db.commit()
    db.refresh(phase)

    logger.info(
        f"Created training phase with weeks",
        user_id=str(user_id),
        phase_id=phase_id,
        week_count=len(weeks_data),
    )

    return phase


def get_training_phase(
    db: Session, user_id: UUID, phase_id: str, include_weeks: bool = True
) -> Optional[TrainingPhase]:
    """Get training phase by ID."""

    query = select(TrainingPhase).where(
        TrainingPhase.user_id == user_id, TrainingPhase.phase_id == phase_id
    )

    if include_weeks:
        query = query.options(
            selectinload(TrainingPhase.weeks).selectinload(TrainingWeek.workouts)
        )

    phase = db.exec(query).first()

    return phase


def list_training_phases(db: Session, user_id: UUID) -> List[TrainingPhase]:
    """List all training phases for a user."""

    query = select(TrainingPhase).where(TrainingPhase.user_id == user_id)
    phases = db.exec(query).all()

    return list(phases)


def delete_training_phase(db: Session, user_id: UUID, phase_id: str) -> bool:
    """Delete training phase (cascade deletes weeks and workouts)."""

    phase = db.exec(
        select(TrainingPhase).where(
            TrainingPhase.user_id == user_id, TrainingPhase.phase_id == phase_id
        )
    ).first()

    if not phase:
        return False

    db.delete(phase)
    db.commit()

    logger.info(f"Deleted training phase", user_id=str(user_id), phase_id=phase_id)

    return True


# ============================================================================
# TrainingWeek CRUD
# ============================================================================


def get_training_week(
    db: Session, user_id: UUID, phase_id: str, week_id: str, include_workouts: bool = True
) -> Optional[TrainingWeek]:
    """Get training week by ID."""

    query = select(TrainingWeek).where(
        TrainingWeek.user_id == user_id,
        TrainingWeek.phase_id == phase_id,
        TrainingWeek.week_id == week_id,
    )

    if include_workouts:
        query = query.options(selectinload(TrainingWeek.workouts))

    week = db.exec(query).first()

    return week


def update_training_week(
    db: Session,
    user_id: UUID,
    phase_id: str,
    week_id: str,
    weekly_tss_target: Optional[float] = None,
    focus: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[TrainingWeek]:
    """Update training week."""

    week = db.exec(
        select(TrainingWeek).where(
            TrainingWeek.user_id == user_id,
            TrainingWeek.phase_id == phase_id,
            TrainingWeek.week_id == week_id,
        )
    ).first()

    if not week:
        return None

    if weekly_tss_target is not None:
        week.weekly_tss_target = weekly_tss_target
    if focus is not None:
        week.focus = focus
    if notes is not None:
        week.notes = notes

    week.updated_at = datetime.now(timezone.utc)

    db.add(week)
    db.commit()
    db.refresh(week)

    logger.info(
        f"Updated training week",
        user_id=str(user_id),
        phase_id=phase_id,
        week_id=week_id,
    )

    return week


# ============================================================================
# WorkoutPlan CRUD
# ============================================================================


def create_workout_plan(
    db: Session,
    user_id: UUID,
    phase_id: str,
    week_id: str,
    name: str,
    day_of_week: int,
    workout_type: str,
    segments: Optional[List[Dict[str, Any]]] = None,
    workout_metadata: Optional[Dict[str, Any]] = None,
) -> WorkoutPlan:
    """Create a single workout plan (for Mastra generateDetailedWorkout)."""

    workout = WorkoutPlan(
        user_id=user_id,
        phase_id=phase_id,
        week_id=week_id,
        name=name,
        day_of_week=day_of_week,
        workout_type=workout_type,
        segments=json.dumps(segments) if segments else None,
        workout_metadata=json.dumps(workout_metadata) if workout_metadata else None,
    )

    db.add(workout)
    db.commit()
    db.refresh(workout)

    logger.info(
        f"Created workout plan",
        user_id=str(user_id),
        phase_id=phase_id,
        week_id=week_id,
        workout_id=str(workout.id),
        workout_name=name,
    )

    return workout


def get_workout_plan(db: Session, workout_id: UUID) -> Optional[WorkoutPlan]:
    """Get workout plan by ID."""

    workout = db.exec(select(WorkoutPlan).where(WorkoutPlan.id == workout_id)).first()

    # Parse JSON fields
    if workout:
        if workout.segments:
            try:
                workout.segments_parsed = json.loads(workout.segments)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse segments for workout {workout_id}")
                workout.segments_parsed = None

        if workout.workout_metadata:
            try:
                workout.workout_metadata_parsed = json.loads(workout.workout_metadata)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse workout_metadata for workout {workout_id}"
                )
                workout.workout_metadata_parsed = None

    return workout


def update_workout_plan(
    db: Session,
    workout_id: UUID,
    name: Optional[str] = None,
    day_of_week: Optional[int] = None,
    workout_type: Optional[str] = None,
    segments: Optional[List[Dict[str, Any]]] = None,
    workout_metadata: Optional[Dict[str, Any]] = None,
) -> Optional[WorkoutPlan]:
    """Update workout plan."""

    workout = db.exec(select(WorkoutPlan).where(WorkoutPlan.id == workout_id)).first()

    if not workout:
        return None

    if name is not None:
        workout.name = name
    if day_of_week is not None:
        workout.day_of_week = day_of_week
    if workout_type is not None:
        workout.workout_type = workout_type
    if segments is not None:
        workout.segments = json.dumps(segments)
    if workout_metadata is not None:
        workout.workout_metadata = json.dumps(workout_metadata)

    workout.updated_at = datetime.now(timezone.utc)

    db.add(workout)
    db.commit()
    db.refresh(workout)

    logger.info(f"Updated workout plan", workout_id=str(workout_id))

    return workout


def delete_workout_plan(db: Session, workout_id: UUID) -> bool:
    """Delete workout plan."""

    workout = db.exec(select(WorkoutPlan).where(WorkoutPlan.id == workout_id)).first()

    if not workout:
        return False

    db.delete(workout)
    db.commit()

    logger.info(f"Deleted workout plan", workout_id=str(workout_id))

    return True


def list_workouts_for_week(
    db: Session, user_id: UUID, phase_id: str, week_id: str
) -> List[WorkoutPlan]:
    """List all workouts for a specific week."""

    query = select(WorkoutPlan).where(
        WorkoutPlan.user_id == user_id,
        WorkoutPlan.phase_id == phase_id,
        WorkoutPlan.week_id == week_id,
    ).order_by(WorkoutPlan.day_of_week)

    workouts = db.exec(query).all()

    return list(workouts)
