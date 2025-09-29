"""
Workout TSS estimation endpoints.

This module provides endpoints for estimating Training Stress Score (TSS) for planned workouts.
Designed for LLM integration to help with workout planning and analysis.
"""

from typing import Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, Field
import structlog

from ...models.responses import WorkoutTSSEstimate, WorkoutSegmentTSS
from ...middleware.auth import get_current_user
from ...middleware.logging import audit_logger
from ...database import User
from ...database import get_elasticsearch_storage
from .utils import get_user_thresholds
from peakflow.analytics.tss import TSSCalculator, WorkoutPlan, WorkoutPlanSegment

logger = structlog.get_logger(__name__)

router = APIRouter()


class SimpleSegmentTSSRequest(BaseModel):
    """Simple request model for single segment TSS estimation - LLM friendly."""

    duration_minutes: float = Field(..., gt=0, description="Duration in minutes")
    intensity_metric: Literal['power', 'heart_rate', 'pace'] = Field(..., description="Type of intensity (power, heart_rate, pace)")
    target_value: float = Field(..., gt=0, description="Target intensity value (watts, bpm, or min/km)")

    # Optional threshold overrides
    threshold_power: Optional[float] = Field(None, gt=0, description="Power threshold in watts")
    threshold_hr: Optional[int] = Field(None, gt=0, le=250, description="Heart rate threshold in bpm")
    max_hr: Optional[int] = Field(None, gt=0, le=250, description="Maximum heart rate in bpm")
    threshold_pace: Optional[float] = Field(None, gt=0, description="Pace threshold in min/km")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "duration_minutes": 30,
                    "intensity_metric": "power",
                    "target_value": 250,
                    "threshold_power": 280
                },
                {
                    "duration_minutes": 45,
                    "intensity_metric": "heart_rate",
                    "target_value": 165,
                    "threshold_hr": 175,
                    "max_hr": 195
                },
                {
                    "duration_minutes": 20,
                    "intensity_metric": "pace",
                    "target_value": 4.5,
                    "threshold_pace": 4.0
                }
            ]
        }


class SimpleSegmentTSSResponse(BaseModel):
    """Simple TSS response for single segment - LLM friendly."""

    estimated_tss: float = Field(..., description="Estimated TSS for the segment")
    duration_minutes: float = Field(..., description="Segment duration")
    intensity_metric: str = Field(..., description="Intensity type used")
    target_value: float = Field(..., description="Target intensity value")
    target_formatted: str = Field(..., description="Human readable target (e.g. '4:30' for pace)")
    intensity_factor: float = Field(..., description="Intensity factor (1.0 = threshold)")
    threshold_used: float = Field(..., description="Threshold value used in calculation")
    calculation_method: str = Field(..., description="TSS calculation method")


class WorkoutTSSRequest(BaseModel):
    """Request model for workout TSS estimation."""

    workout_plan: Optional[WorkoutPlan] = Field(None, description="Complete workout plan with multiple segments")
    workout_segment: Optional[WorkoutPlanSegment] = Field(None, description="Single workout segment")

    # Optional threshold overrides
    threshold_power: Optional[float] = Field(None, gt=0, description="Running power threshold in watts")
    ftp: Optional[float] = Field(None, gt=0, description="Cycling power threshold (FTP) in watts")
    threshold_hr: Optional[int] = Field(None, gt=0, le=250, description="Lactate threshold heart rate in bpm")
    max_hr: Optional[int] = Field(None, gt=0, le=250, description="Maximum heart rate in bpm")
    threshold_pace: Optional[float] = Field(None, gt=0, description="Threshold pace in minutes per kilometer")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "workout_plan": {
                        "name": "5x5min Threshold Intervals",
                        "description": "Lactate threshold intervals with recovery",
                        "segments": [
                            {"duration_minutes": 10, "intensity_metric": "power", "target_value": 200},
                            {"duration_minutes": 5, "intensity_metric": "power", "target_value": 300},
                            {"duration_minutes": 3, "intensity_metric": "power", "target_value": 150},
                            {"duration_minutes": 5, "intensity_metric": "power", "target_value": 300},
                            {"duration_minutes": 10, "intensity_metric": "power", "target_value": 180}
                        ]
                    },
                    "threshold_power": 280
                },
                {
                    "workout_segment": {
                        "duration_minutes": 30,
                        "intensity_metric": "heart_rate",
                        "target_value": 165
                    },
                    "threshold_hr": 175,
                    "max_hr": 195
                }
            ]
        }


@router.post("/workout/simple-tss",
            response_model=SimpleSegmentTSSResponse,
            operation_id="estimate_simple_segment_tss",
            tags=["mcp", "tss"],
            summary="Simple TSS estimation for single segment",
            description="""
Estimate Training Stress Score (TSS) for a single workout segment.

**Designed for LLM convenience**: Simple input/output format ideal for AI integration.

**Quick Usage**:
1. Specify duration, intensity type, and target value
2. Optionally provide thresholds (or use stored user values)
3. Get immediate TSS estimate with key metrics

**Examples**:
- 30min at 250W with 280W threshold → ~32 TSS
- 45min at 165bpm with 175bpm threshold → ~35 TSS
- 20min at 4:30/km with 4:00/km threshold → ~28 TSS

**Perfect for**: LLM workout planning, quick TSS checks, interval planning
""")
async def estimate_simple_segment_tss(
    request: Request,
    tss_request: SimpleSegmentTSSRequest,
    current_user: User = Depends(get_current_user),
) -> SimpleSegmentTSSResponse:
    """Estimate TSS for a single workout segment - LLM friendly."""

    try:
        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)

        # Get user thresholds from storage
        user_thresholds = get_user_thresholds(storage, user_id)
        logger.info(f"Retrieved user thresholds for simple TSS: {user_thresholds}")

        # Initialize TSS calculator
        calculator = TSSCalculator(storage)

        # Create workout segment from request
        workout_segment = WorkoutPlanSegment(
            duration_minutes=tss_request.duration_minutes,
            intensity_metric=tss_request.intensity_metric,
            target_value=tss_request.target_value
        )

        # Convert to single-segment workout plan
        workout_plan = WorkoutPlan(
            segments=[workout_segment],
            name="Simple Segment",
            description=f"{tss_request.duration_minutes}min {tss_request.intensity_metric} segment"
        )

        # Estimate TSS using the calculator
        result = calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            ftp=None,  # Use threshold_power terminology
            threshold_power=tss_request.threshold_power,
            threshold_hr=tss_request.threshold_hr,
            max_hr=tss_request.max_hr,
            threshold_pace=tss_request.threshold_pace,
            user_id=user_id
        )

        # Extract segment result (should be only one)
        segment_result = result['segments'][0] if result['segments'] else {}

        # Determine which threshold was used
        thresholds_used = result['thresholds_used']
        if tss_request.intensity_metric == 'power':
            threshold_used = thresholds_used.get('threshold_power', 0)
        elif tss_request.intensity_metric == 'heart_rate':
            threshold_used = thresholds_used.get('threshold_hr', 0)
        else:  # pace
            threshold_used = thresholds_used.get('threshold_pace', 0)

        # Format target value for display
        if tss_request.intensity_metric == 'pace':
            target_formatted = calculator.format_pace(tss_request.target_value)
        elif tss_request.intensity_metric == 'heart_rate':
            target_formatted = f"{int(tss_request.target_value)} bpm"
        else:  # power
            target_formatted = f"{int(tss_request.target_value)}W"

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="simple_segment_tss_estimated",
            user_id=current_user.id,
            details={
                "estimated_tss": result['estimated_tss'],
                "duration_minutes": tss_request.duration_minutes,
                "intensity_metric": tss_request.intensity_metric,
                "target_value": tss_request.target_value
            }
        )

        logger.info(f"Successfully estimated simple TSS for user {user_id}: {result['estimated_tss']}")

        return SimpleSegmentTSSResponse(
            estimated_tss=result['estimated_tss'],
            duration_minutes=tss_request.duration_minutes,
            intensity_metric=tss_request.intensity_metric,
            target_value=tss_request.target_value,
            target_formatted=target_formatted,
            intensity_factor=segment_result.get('intensity_factor', 0),
            threshold_used=threshold_used,
            calculation_method=result['primary_method']
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in simple TSS estimation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error estimating simple TSS for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to estimate segment TSS"
        )


@router.post("/workout/estimate-tss",
            response_model=WorkoutTSSEstimate,
            operation_id="estimate_workout_tss",
            tags=["mcp", "tss"],
            summary="Estimate TSS for workout plan",
            description="""
Calculate Training Stress Score (TSS) for a planned workout before execution.

**For LLM Integration**: This endpoint helps AI systems estimate workout difficulty and training load.

**Input Options**:
- `workout_plan`: Complete workout with multiple segments (warmup, intervals, cooldown)
- `workout_segment`: Single workout segment for quick estimates

**Intensity Metrics Supported**:
- `power`: Target watts (requires threshold_power or ftp)
- `heart_rate`: Target BPM (requires threshold_hr and max_hr)
- `pace`: Target pace in min/km (requires threshold_pace)

**TSS Calculation**:
- Power TSS: Based on Normalized Power vs Threshold Power
- Heart Rate TSS: Based on intensity zones and TRIMP method
- Pace TSS: Based on normalized pace vs threshold pace

**Response**: Estimated TSS with segment-by-segment breakdown and threshold values used.
""")
async def estimate_workout_tss(
    request: Request,
    tss_request: WorkoutTSSRequest,
    current_user: User = Depends(get_current_user),
) -> WorkoutTSSEstimate:
    """Estimate TSS for a planned workout."""

    try:
        # Validate input - must have either workout_plan or workout_segment
        if not tss_request.workout_plan and not tss_request.workout_segment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either 'workout_plan' or 'workout_segment'"
            )

        if tss_request.workout_plan and tss_request.workout_segment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide only one of 'workout_plan' or 'workout_segment', not both"
            )

        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)

        # Get user thresholds from storage
        user_thresholds = get_user_thresholds(storage, user_id)
        logger.info(f"Retrieved user thresholds: {user_thresholds}")

        # Initialize TSS calculator
        calculator = TSSCalculator(storage)

        # Convert single segment to workout plan if needed
        if tss_request.workout_segment:
            workout_plan = WorkoutPlan(
                segments=[tss_request.workout_segment],
                name="Single Segment Workout",
                description="TSS estimation for single workout segment"
            )
        else:
            workout_plan = tss_request.workout_plan

        # Estimate TSS using the calculator
        result = calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            ftp=tss_request.ftp,
            threshold_power=tss_request.threshold_power,
            threshold_hr=tss_request.threshold_hr,
            max_hr=tss_request.max_hr,
            threshold_pace=tss_request.threshold_pace,
            user_id=user_id
        )

        # Convert segments to response format
        segment_estimates = []
        for seg in result['segments']:
            segment_estimates.append(WorkoutSegmentTSS(
                duration_minutes=seg['duration_minutes'],
                intensity_metric=seg['intensity_metric'],
                target_value=seg['target_value'],
                target_formatted=seg.get('target_pace_formatted', str(seg['target_value'])),
                estimated_tss=seg['estimated_tss'],
                intensity_factor=seg['intensity_factor']
            ))

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="workout_tss_estimated",
            user_id=current_user.id,
            details={
                "estimated_tss": result['estimated_tss'],
                "segment_count": result['segment_count'],
                "duration_minutes": result['total_duration_minutes'],
                "primary_method": result['primary_method']
            }
        )

        logger.info(f"Successfully estimated TSS for user {user_id}: {result['estimated_tss']}")

        return WorkoutTSSEstimate(
            estimated_tss=result['estimated_tss'],
            total_duration_minutes=result['total_duration_minutes'],
            total_duration_hours=result['total_duration_hours'],
            segment_count=result['segment_count'],
            primary_method=result['primary_method'],
            segments=segment_estimates,
            thresholds_used=result['thresholds_used'],
            calculation_method=result['calculation_method'],
            estimated_at=result['estimated_at']
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in TSS estimation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error estimating workout TSS for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to estimate workout TSS"
        )
