"""
Request and response models for workout plan CRUD operations.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from uuid import UUID


# ============================================================================
# Request Models
# ============================================================================


class CriticalWorkoutCreate(BaseModel):
    """Critical workout structure matching type.ts."""

    id: str = Field(..., description="Unique identifier for the critical workout")
    description: str = Field(..., description="Brief description of the critical workout type and purpose")


class TrainingWeekCreate(BaseModel):
    """Training week creation data matching type.ts TrainingWeekSchema."""

    week_id: str = Field(..., description="Week identifier (e.g., 'week-1', 'base-week-3')")
    phase_id: str = Field(..., description="Identifier of the parent training phase")
    start_date: datetime = Field(..., description="Week start date (typically Monday)")
    end_date: datetime = Field(..., description="Week end date (typically Sunday)")
    description: str = Field(..., description="Weekly focus and training objectives")
    weekly_mileage: Optional[float] = Field(None, description="Planned total weekly mileage in kilometers")
    critical_workouts: List[CriticalWorkoutCreate] = Field(..., description="Key workouts for this week (typically 2-3)")


class TrainingPhaseCreateRequest(BaseModel):
    """Request model matching type.ts TrainingPhaseSchema exactly."""

    user_id: Optional[UUID] = Field(None, description="User ID (optional, defaults to authenticated user)")
    phase_id: str = Field(..., description="Unique identifier for the training phase")
    name: str = Field(..., description="Phase name (e.g., 'Base Building', 'Specific Preparation')")
    tag: str = Field(..., description="Short tag/label for the phase (e.g., 'base', 'build', 'peak', 'taper')")
    description: str = Field(..., description="Phase objectives and training focus")
    weeks: List[TrainingWeekCreate] = Field(..., description="Week-by-week breakdown for this phase")
    workout_focus: List[str] = Field(..., min_length=1, description="Primary training focus areas for the phase")

    class Config:
        json_schema_extra = {
            "example": {
                "phase_id": "base-phase-1",
                "name": "Base Building",
                "tag": "base",
                "description": "Build aerobic foundation with progressive volume",
                "workout_focus": ["aerobic base", "easy volume"],
                "weeks": [
                    {
                        "week_id": "week-1",
                        "phase_id": "base-phase-1",
                        "start_date": "2025-01-06T00:00:00Z",
                        "end_date": "2025-01-12T00:00:00Z",
                        "description": "Easy aerobic running, recovery week",
                        "weekly_mileage": 40.0,
                        "critical_workouts": [
                            {"id": "long-run-1", "description": "60-minute easy long run"},
                            {"id": "tempo-1", "description": "30-minute steady state"}
                        ]
                    },
                    {
                        "week_id": "week-2",
                        "phase_id": "base-phase-1",
                        "start_date": "2025-01-13T00:00:00Z",
                        "end_date": "2025-01-19T00:00:00Z",
                        "description": "Build volume gradually",
                        "weekly_mileage": 50.0,
                        "critical_workouts": [
                            {"id": "long-run-2", "description": "75-minute easy long run"},
                            {"id": "tempo-2", "description": "40-minute steady state"}
                        ]
                    }
                ]
            }
        }


class WorkoutPlanCreateRequest(BaseModel):
    """Request model for creating a single workout (for Mastra generateDetailedWorkout)."""

    user_id: Optional[UUID] = Field(None, description="User ID (optional, defaults to authenticated user)")
    phase_id: str = Field(..., max_length=100, description="Phase identifier")
    week_id: str = Field(..., max_length=100, description="Week identifier")
    name: str = Field(..., max_length=200, description="Workout name")
    day_of_week: int = Field(..., ge=0, le=6, description="Day of week (0=Monday, 6=Sunday)")
    workout_type: str = Field(..., max_length=50, description="Workout type (threshold, intervals, long_run, recovery, etc.)")
    segments: Optional[List[Dict[str, Any]]] = Field(None, description="Workout segments (from WorkoutPlanSegment)")
    workout_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional workout metadata (TSS, duration, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "phase_id": "base_phase_1",
                "week_id": "week_1",
                "name": "5x5min Threshold Intervals",
                "day_of_week": 2,
                "workout_type": "threshold",
                "segments": [
                    {"duration_minutes": 10, "intensity_metric": "power", "target_value": 200},
                    {"duration_minutes": 5, "intensity_metric": "power", "target_value": 300},
                    {"duration_minutes": 3, "intensity_metric": "power", "target_value": 150}
                ],
                "workout_metadata": {
                    "estimated_tss": 75,
                    "total_duration_minutes": 60,
                    "intensity_factor": 0.85
                }
            }
        }


class WorkoutPlanUpdateRequest(BaseModel):
    """Request model for updating an existing workout."""

    name: Optional[str] = Field(None, max_length=200, description="Workout name")
    day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week")
    workout_type: Optional[str] = Field(None, max_length=50, description="Workout type")
    segments: Optional[List[Dict[str, Any]]] = Field(None, description="Workout segments")
    workout_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional workout metadata")


class TrainingWeekUpdateRequest(BaseModel):
    """Request model for updating a training week."""

    weekly_tss_target: Optional[float] = Field(None, ge=0, description="Target TSS for this week")
    focus: Optional[str] = Field(None, max_length=200, description="Week focus")
    notes: Optional[str] = Field(None, description="Week notes")


# ============================================================================
# Response Models
# ============================================================================


class WorkoutPlanResponse(BaseModel):
    """Response model for a single workout."""

    id: UUID
    user_id: UUID
    phase_id: str
    week_id: str
    name: str
    day_of_week: int
    workout_type: str
    segments: Optional[List[Dict[str, Any]]]
    workout_metadata: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrainingWeekResponse(BaseModel):
    """Response model for a training week."""

    user_id: UUID
    phase_id: str
    week_id: str
    week_number: int
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    description: Optional[str]
    weekly_mileage: Optional[float]
    critical_workouts: Optional[List[Dict[str, Any]]]

    # Legacy fields
    weekly_tss_target: Optional[float]
    focus: Optional[str]
    notes: Optional[str]

    created_at: datetime
    updated_at: datetime
    workouts: List[WorkoutPlanResponse] = []

    class Config:
        from_attributes = True


class TrainingPhaseResponse(BaseModel):
    """Response model for a training phase."""

    user_id: UUID
    phase_id: str
    name: str
    tag: Optional[str]
    description: Optional[str]
    workout_focus: Optional[List[str]]

    # Metadata
    coach_id: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]

    # Legacy fields
    phase_type: Optional[str]
    critical_workouts: Optional[Dict[str, Any]]
    notes: Optional[str]

    created_at: datetime
    updated_at: datetime
    weeks: List[TrainingWeekResponse] = []

    class Config:
        from_attributes = True


class TrainingPhaseSummaryResponse(BaseModel):
    """Summary response for listing phases (without nested weeks/workouts)."""

    user_id: UUID
    phase_id: str
    name: str
    tag: Optional[str]
    description: Optional[str]
    workout_focus: Optional[List[str]]

    coach_id: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]

    # Legacy
    phase_type: Optional[str]

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
