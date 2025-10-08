"""
Zone calculation endpoints - calculate training zones from thresholds.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
import structlog
import math

from ...middleware.auth import get_current_user
from ...database import User, get_elasticsearch_storage
from .utils import get_user_thresholds
from peakflow.analytics import (
    PowerZoneAnalyzer,
    PaceZoneAnalyzer,
    HeartRateZoneAnalyzer,
    PowerZoneMethod,
    PaceZoneMethod,
    HeartRateZoneMethod,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


def sanitize_float(value: float) -> Optional[float]:
    """
    Sanitize float values for JSON serialization.
    Replace inf, -inf, and NaN with None.
    """
    if math.isinf(value) or math.isnan(value):
        return None
    return value


class ZoneInfo(BaseModel):
    """Single zone information."""
    zone_number: int = Field(description="Zone number")
    zone_name: str = Field(description="Zone name")
    range_min: Optional[float] = Field(description="Minimum value for this zone")
    range_max: Optional[float] = Field(description="Maximum value for this zone")
    range_unit: str = Field(description="Unit of measurement")
    description: str = Field(description="Zone description")
    purpose: str = Field(description="Training purpose")


class ZoneRanges(BaseModel):
    """Zone ranges for a specific metric."""
    zone_type: str = Field(description="Type of zone (power, pace, heart_rate)")
    threshold_value: Optional[float] = Field(description="Threshold value used for calculation")
    method: str = Field(description="Calculation method used")
    zones: List[ZoneInfo] = Field(description="List of zones with ranges")


class UserZonesResponse(BaseModel):
    """Response containing user's training zones."""
    power_zones: Optional[ZoneRanges] = Field(description="Power zone ranges")
    pace_zones: Optional[ZoneRanges] = Field(description="Pace zone ranges")
    heart_rate_zones: Optional[ZoneRanges] = Field(description="Heart rate zone ranges")


@router.get(
    "/user-zones",
    response_model=UserZonesResponse,
    operation_id="get_user_zones",
    tags=["analytics", "zones"],
    description="Get user's training zones calculated from their threshold values"
)
async def get_user_zones(
    current_user: User = Depends(get_current_user),
) -> UserZonesResponse:
    """
    Calculate and return user's training zones based on their indicators.

    Uses peakflow zone calculators with user's threshold values.
    """
    try:
        es_storage = get_elasticsearch_storage()

        # Get user thresholds
        user_thresholds = get_user_thresholds(es_storage, current_user.id)

        power_zones = None
        pace_zones = None
        hr_zones = None

        # Calculate power zones if threshold available
        if user_thresholds.get("threshold_power"):
            threshold_power = user_thresholds["threshold_power"]
            analyzer = PowerZoneAnalyzer()
            zones = analyzer.calculate_zones(
                method=PowerZoneMethod.STEVE_PALLADINO,
                threshold_power=threshold_power
            )

            power_zones = ZoneRanges(
                zone_type="power",
                threshold_value=threshold_power,
                method="Steve Palladino 7-zone",
                zones=[
                    ZoneInfo(
                        zone_number=z.zone_number,
                        zone_name=z.zone_name,
                        range_min=sanitize_float(z.power_range[0]),
                        range_max=sanitize_float(z.power_range[1]),
                        range_unit="watts",
                        description=z.description,
                        purpose=z.purpose
                    )
                    for z in zones
                ]
            )

        # Calculate pace zones if threshold available
        if user_thresholds.get("threshold_pace"):
            threshold_pace = user_thresholds["threshold_pace"]
            # threshold_pace is in min/km, convert to sec/km for calculator
            threshold_pace_sec = threshold_pace * 60
            analyzer = PaceZoneAnalyzer()
            zones = analyzer.calculate_zones(
                method=PaceZoneMethod.JOE_FRIEL,
                threshold_pace=threshold_pace_sec
            )

            pace_zones = ZoneRanges(
                zone_type="pace",
                threshold_value=threshold_pace,
                method="Joe Friel",
                zones=[
                    ZoneInfo(
                        zone_number=z.zone_number,
                        zone_name=z.zone_name,
                        range_min=sanitize_float(z.pace_range[0] / 60),  # Convert to min/km
                        range_max=sanitize_float(z.pace_range[1] / 60),
                        range_unit="min/km",
                        description=z.description,
                        purpose=z.purpose
                    )
                    for z in zones
                ]
            )

        # Calculate HR zones if threshold available
        if user_thresholds.get("threshold_heart_rate"):
            threshold_hr = user_thresholds["threshold_heart_rate"]
            max_hr = user_thresholds.get("max_heart_rate")
            analyzer = HeartRateZoneAnalyzer()
            zones = analyzer.calculate_zones(
                method=HeartRateZoneMethod.JOE_FRIEL,
                lthr=int(threshold_hr),
                max_heart_rate=int(max_hr) if max_hr else None
            )

            hr_zones = ZoneRanges(
                zone_type="heart_rate",
                threshold_value=threshold_hr,
                method="Joe Friel",
                zones=[
                    ZoneInfo(
                        zone_number=z.zone_number,
                        zone_name=z.zone_name,
                        range_min=sanitize_float(z.heart_rate_range[0]),
                        range_max=sanitize_float(z.heart_rate_range[1]),
                        range_unit="BPM",
                        description=z.description,
                        purpose=z.purpose
                    )
                    for z in zones
                ]
            )

        return UserZonesResponse(
            power_zones=power_zones,
            pace_zones=pace_zones,
            heart_rate_zones=hr_zones
        )

    except Exception as e:
        logger.error(
            "Zone calculation error",
            user_id=getattr(current_user, 'id', 'unknown'),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate zones: {str(e)}",
        )
