"""
Analytics routes for user activity and health data analysis.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
import structlog

from ..models.responses import (
    WeeklyActivitySummary,
    ActivityDetailResponse,
    ZonePercentage,
    HealthMetrics,
    LapData,
)
from ..middleware.auth import get_current_user
from ..middleware.logging import audit_logger
from ..settings import get_settings
from ..database import User
from peakflow import ElasticsearchStorage, DataType, QueryFilter
from peakflow.analytics.power_zones import (
    PowerZoneMethod,
    StevePalladinoCalculator,
    StrydRunningCalculator,
    CriticalPowerCalculator,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


def get_elasticsearch_storage() -> ElasticsearchStorage:
    """Initialize and return Elasticsearch storage."""
    settings = get_settings()
    
    # Construct hosts with authentication if credentials are provided
    hosts = [settings.elasticsearch_host]
    if settings.elasticsearch_user and settings.elasticsearch_password:
        # Add authentication to the host URL
        import urllib.parse
        parsed = urllib.parse.urlparse(settings.elasticsearch_host)
        auth_host = f"{parsed.scheme}://{settings.elasticsearch_user}:{settings.elasticsearch_password}@{parsed.netloc}{parsed.path}"
        hosts = [auth_host]
    
    storage_config = {
        'hosts': hosts,
        'request_timeout': 30,
        'max_retries': 3,
        'retry_on_timeout': True,
        'verify_certs': False,
    }
    
    storage = ElasticsearchStorage()
    if not storage.initialize(storage_config):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Elasticsearch"
        )
    
    return storage


def get_user_threshold(storage: ElasticsearchStorage, user_id: str) -> Optional[float]:
    """Get user's threshold power/pace from user indicators."""
    try:
        threshold_query = QueryFilter()
        threshold_query.add_term_filter("user_id", user_id)
        threshold_query.add_exists_filter("threshold_power")
        # Remove sort to avoid field mapping issues
        threshold_query.set_pagination(limit=1)
        
        indicators = storage.search(DataType.USER_INDICATOR, threshold_query)
        
        if indicators:
            return indicators[0].get("threshold_power")
            
        # Fallback: try to find critical power
        cp_query = QueryFilter()
        cp_query.add_term_filter("user_id", user_id)
        cp_query.add_exists_filter("critical_power")
        # Remove sort to avoid field mapping issues
        cp_query.set_pagination(limit=1)
        
        cp_indicators = storage.search(DataType.USER_INDICATOR, cp_query)
        
        if cp_indicators:
            return cp_indicators[0].get("critical_power")
            
        return None
        
    except Exception as e:
        logger.error(f"Failed to get user threshold for {user_id}: {str(e)}")
        return None


def calculate_zone_percentages(power_data: List[float], zones: List, threshold_power: float) -> ZonePercentage:
    """Calculate time spent in each zone."""
    if not power_data or not zones:
        return ZonePercentage(zone_1=0, zone_2=0, zone_3=0, zone_4=0, zone_5=0)
    
    zone_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    total_points = len(power_data)
    
    for power in power_data:
        if power is None or power <= 0:
            continue
            
        # Find which zone this power value belongs to
        for zone in zones[:5]:  # Only use first 5 zones
            zone_min, zone_max = zone.power_range
            if zone_min <= power <= zone_max:
                zone_counts[zone.zone_number] += 1
                break
    
    # Convert to percentages
    return ZonePercentage(
        zone_1=round((zone_counts[1] / total_points) * 100, 1) if total_points > 0 else 0,
        zone_2=round((zone_counts[2] / total_points) * 100, 1) if total_points > 0 else 0,
        zone_3=round((zone_counts[3] / total_points) * 100, 1) if total_points > 0 else 0,
        zone_4=round((zone_counts[4] / total_points) * 100, 1) if total_points > 0 else 0,
        zone_5=round((zone_counts[5] / total_points) * 100, 1) if total_points > 0 else 0,
    )


def get_health_metrics(storage: ElasticsearchStorage, user_id: str, start_date: datetime, end_date: datetime) -> HealthMetrics:
    """Get aggregated health metrics for date range."""
    try:
        # Get HRV data
        hrv_query = QueryFilter()
        hrv_query.add_term_filter("user_id", user_id)
        hrv_query.add_date_range("timestamp", start=start_date, end=end_date)
        hrv_query.set_pagination(limit=1000)
        
        hrv_records = storage.search(DataType.HRV_STATUS, hrv_query)
        
        # Get wellness data (includes resting heart rate)
        wellness_query = QueryFilter()
        wellness_query.add_term_filter("user_id", user_id)
        wellness_query.add_date_range("timestamp", start=start_date, end=end_date)
        wellness_query.set_pagination(limit=1000)
        
        wellness_records = storage.search(DataType.WELLNESS, wellness_query)
        
        # Get health metrics
        health_query = QueryFilter()
        health_query.add_term_filter("user_id", user_id)
        health_query.add_date_range("timestamp", start=start_date, end=end_date)
        health_query.set_pagination(limit=1000)
        
        health_records = storage.search(DataType.METRICS, health_query)
        
        # Calculate averages
        avg_hrv = None
        if hrv_records:
            hrv_values = [r.get("hrv_score") or r.get("rmssd") for r in hrv_records if r.get("hrv_score") or r.get("rmssd")]
            avg_hrv = sum(hrv_values) / len(hrv_values) if hrv_values else None
        
        avg_rhr = None
        if wellness_records:
            rhr_values = [r.get("resting_heart_rate") for r in wellness_records if r.get("resting_heart_rate")]
            avg_rhr = int(sum(rhr_values) / len(rhr_values)) if rhr_values else None
        
        avg_health_score = None
        avg_stress = None
        avg_sleep = None
        if health_records:
            health_scores = [r.get("health_score") for r in health_records if r.get("health_score")]
            stress_scores = [r.get("stress_score") for r in health_records if r.get("stress_score")]
            sleep_scores = [r.get("sleep_score") for r in health_records if r.get("sleep_score")]
            
            avg_health_score = sum(health_scores) / len(health_scores) if health_scores else None
            avg_stress = sum(stress_scores) / len(stress_scores) if stress_scores else None
            avg_sleep = sum(sleep_scores) / len(sleep_scores) if sleep_scores else None
        
        return HealthMetrics(
            avg_hrv=round(avg_hrv, 1) if avg_hrv else None,
            avg_resting_heart_rate=avg_rhr,
            avg_health_score=round(avg_health_score, 1) if avg_health_score else None,
            stress_score=round(avg_stress, 1) if avg_stress else None,
            sleep_score=round(avg_sleep, 1) if avg_sleep else None,
        )
        
    except Exception as e:
        logger.error(f"Failed to get health metrics: {str(e)}")
        return HealthMetrics()


@router.get("/weekly-summary/{user_id}", response_model=WeeklyActivitySummary)
async def get_weekly_activity_summary(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> WeeklyActivitySummary:
    """Get 7-day user activities snapshot with aggregated metrics."""
    
    try:
        storage = get_elasticsearch_storage()
        
        # Calculate 7-day date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)
        
        # Get user threshold for zone calculations
        threshold_power = get_user_threshold(storage, user_id)
        if not threshold_power:
            logger.warning(f"No threshold power found for user {user_id}, using default")
            threshold_power = 250.0  # Default threshold for zone calculations
        
        # Initialize zone calculator (using Stryd 5-zone system)
        calculator = StrydRunningCalculator()
        zones = calculator.calculate_zones(threshold_power)
        
        # Get activities for the past 7 days
        activities_query = QueryFilter()
        activities_query.add_term_filter("user_id", user_id)
        activities_query.add_date_range("timestamp", start=start_date, end=end_date)
        activities_query.add_sort("timestamp", ascending=False)
        activities_query.set_pagination(limit=100)
        
        activities = storage.search(DataType.SESSION, activities_query)
        
        # Get TSS data for activities
        tss_query = QueryFilter()
        tss_query.add_term_filter("user_id", user_id)
        tss_query.add_date_range("timestamp", start=start_date, end=end_date)
        tss_query.set_pagination(limit=100)
        
        tss_records = storage.search(DataType.TSS, tss_query)
        tss_by_activity = {r.get("activity_id"): r.get("primary_tss", 0) for r in tss_records}
        
        # Aggregate metrics
        total_distance = 0.0
        total_tss = 0.0
        total_time = 0
        all_power_data = []
        
        for activity in activities:
            distance = activity.get("total_distance", 0)
            if distance:
                total_distance += distance / 1000  # Convert meters to km
            
            activity_time = activity.get("total_timer_time", 0) or activity.get("total_elapsed_time", 0)
            if activity_time:
                total_time += int(activity_time)
            
            # Get TSS for this activity
            activity_id = activity.get("activity_id")
            if activity_id in tss_by_activity:
                total_tss += tss_by_activity[activity_id]
            
            # Collect power data for zone calculation
            records = activity.get("records", [])
            for record in records:
                power = record.get("power")
                if power and power > 0:
                    all_power_data.append(power)
        
        # Calculate zone percentages
        zone_percentages = calculate_zone_percentages(all_power_data, zones, threshold_power)
        
        # Get health metrics
        health_metrics = get_health_metrics(storage, user_id, start_date, end_date)
        
        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="weekly_summary_requested",
            user_id=current_user.id,
            details={
                "target_user_id": user_id,
                "activities_found": len(activities),
                "date_range": f"{start_date.date()} to {end_date.date()}"
            },
        )
        
        return WeeklyActivitySummary(
            user_id=user_id,
            total_distance=round(total_distance, 2),
            total_tss=round(total_tss, 1),
            total_time=total_time,
            activity_count=len(activities),
            zone_percentages=zone_percentages,
            health_metrics=health_metrics,
            date_range={
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Weekly summary error", 
            user_id=user_id, 
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate weekly activity summary",
        )


@router.get("/activity/{activity_id}", response_model=ActivityDetailResponse)
async def get_activity_detail(
    request: Request,
    activity_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
) -> ActivityDetailResponse:
    """Get detailed single activity information with lap data and health metrics."""
    
    try:
        storage = get_elasticsearch_storage()
        
        # Get the specific activity
        activity_query = QueryFilter()
        activity_query.add_term_filter("user_id", user_id)
        activity_query.add_term_filter("activity_id", activity_id)
        
        activities = storage.search(DataType.SESSION, activity_query)
        
        if not activities:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Activity {activity_id} not found for user {user_id}"
            )
        
        activity = activities[0]
        
        # Get user threshold for zone calculations
        threshold_power = get_user_threshold(storage, user_id)
        if not threshold_power:
            threshold_power = 250.0  # Default threshold
        
        # Initialize zone calculator
        calculator = StrydRunningCalculator()
        zones = calculator.calculate_zones(threshold_power)
        
        # Get TSS for this activity
        tss_query = QueryFilter()
        tss_query.add_term_filter("user_id", user_id)
        tss_query.add_term_filter("activity_id", activity_id)
        
        tss_records = storage.search(DataType.TSS, tss_query)
        activity_tss = tss_records[0].get("primary_tss") if tss_records else None
        
        # Get lap data
        lap_query = QueryFilter()
        lap_query.add_term_filter("user_id", user_id)
        lap_query.add_term_filter("activity_id", activity_id)
        # Use lap_number instead of lap_index for sorting
        lap_query.add_sort("lap_number", ascending=True)
        
        lap_records = storage.search(DataType.LAP, lap_query)
        
        lap_data = []
        all_power_data = []
        
        for lap_record in lap_records:
            lap_distance = lap_record.get("total_distance", 0)
            lap_time = lap_record.get("total_timer_time", 0)
            avg_power = lap_record.get("avg_power")
            avg_hr = lap_record.get("avg_heart_rate")
            
            # Calculate average pace if distance and time are available
            avg_pace = None
            if lap_distance > 0 and lap_time > 0:
                pace_min_per_km = (lap_time / 60) / (lap_distance / 1000)
                avg_pace = pace_min_per_km
            
            # Determine primary zone for this lap
            zone = None
            if avg_power and avg_power > 0:
                for z in zones[:5]:
                    zone_min, zone_max = z.power_range
                    if zone_min <= avg_power <= zone_max:
                        zone = z.zone_number
                        break
                all_power_data.append(avg_power)
            
            lap_data.append(LapData(
                lap_number=lap_record.get("lap_number", 0),
                distance=round(lap_distance / 1000, 2) if lap_distance else 0,
                time=int(lap_time) if lap_time else 0,
                avg_power=round(avg_power, 1) if avg_power else None,
                avg_pace=round(avg_pace, 2) if avg_pace else None,
                avg_heart_rate=avg_hr,
                zone=zone
            ))
        
        # Calculate overall zone percentages
        records = activity.get("records", [])
        if records:
            power_data = [r.get("power") for r in records if r.get("power") and r.get("power") > 0]
            all_power_data.extend(power_data)
        
        zone_percentages = calculate_zone_percentages(all_power_data, zones, threshold_power)
        
        # Get previous night's health data
        activity_date = datetime.fromisoformat(activity.get("start_time", activity.get("timestamp", datetime.utcnow().isoformat())))
        night_start = (activity_date - timedelta(days=1)).replace(hour=18, minute=0, second=0)
        night_end = activity_date.replace(hour=12, minute=0, second=0)
        
        health_metrics = get_health_metrics(storage, user_id, night_start, night_end)
        
        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="activity_detail_requested",
            user_id=current_user.id,
            details={
                "target_user_id": user_id,
                "activity_id": activity_id,
                "laps_found": len(lap_data)
            },
        )
        
        return ActivityDetailResponse(
            activity_id=activity_id,
            user_id=user_id,
            name=activity.get("session_name", "Unknown Activity"),
            description=activity.get("description"),
            sport=activity.get("sport", "unknown"),
            distance=round((activity.get("total_distance", 0) / 1000), 2),
            time=int(activity.get("total_timer_time", 0) or activity.get("total_elapsed_time", 0) or 0),
            tss=round(activity_tss, 1) if activity_tss else None,
            zone_percentages=zone_percentages,
            lap_data=lap_data,
            last_night_hrv=health_metrics.avg_hrv,
            last_night_resting_hr=health_metrics.avg_resting_heart_rate,
            last_night_health_score=health_metrics.avg_health_score,
            timestamp=activity_date
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Activity detail error", 
            activity_id=activity_id,
            user_id=user_id,
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get activity details",
        )
