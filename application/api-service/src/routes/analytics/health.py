"""
Health metrics analytics endpoints.
"""

from datetime import datetime, timezone, date, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
import structlog

from ...models.responses import (
    HealthMetricsResponse,
    HealthMetricsSummary,
    DailyHealthMetrics,
)
from ...models.requests import HealthMetricsRequest
from ...middleware.auth import get_current_user
from ...middleware.logging import audit_logger
from ...database import User
from ...database import get_elasticsearch_storage
from peakflow import DataType, QueryFilter

logger = structlog.get_logger(__name__)

router = APIRouter()


def convert_utc_to_taipei_time(dt: datetime) -> datetime:
    """Convert UTC datetime to Taipei timezone (+8 hours)."""
    try:
        from zoneinfo import ZoneInfo
        taipei_tz = ZoneInfo('Asia/Taipei')
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(taipei_tz)
    except ImportError:
        # Fallback: manual UTC+8 conversion
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt + timedelta(hours=8)


def is_night_time(dt: datetime) -> bool:
    """
    Check if datetime falls within night hours (23:00-06:00) in local time.
    Expects datetime to already be in local timezone.
    """
    hour = dt.hour
    # Night hours: 23:00-23:59 and 00:00-05:59 (06:00 is start of day)
    return hour >= 23 or hour < 6


def get_health_data_for_period(
    storage, 
    user_id: str, 
    start_date: date, 
    end_date: date
) -> Dict[str, List[Dict]]:
    """Get health data from Elasticsearch for the specified date range."""
    
    # Convert dates to UTC datetime range
    start_datetime = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_datetime = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)
    
    logger.info(f"Fetching health data for user {user_id} from {start_date} to {end_date}")
    
    # Get HRV data
    hrv_query = QueryFilter()
    hrv_query.add_term_filter("user_id", user_id)
    hrv_query.add_date_range("timestamp", start=start_datetime, end=end_datetime)
    hrv_query.add_sort("timestamp", ascending=True)
    hrv_query.set_pagination(limit=10000)
    
    hrv_records = storage.search(DataType.HRV_STATUS, hrv_query)
    logger.info(f"Found {len(hrv_records)} HRV records")
    
    # Get wellness data (includes heart rate)
    wellness_query = QueryFilter()
    wellness_query.add_term_filter("user_id", user_id)
    wellness_query.add_date_range("timestamp", start=start_datetime, end=end_datetime)
    wellness_query.add_sort("timestamp", ascending=True)
    wellness_query.set_pagination(limit=10000)
    
    wellness_records = storage.search(DataType.WELLNESS, wellness_query)
    logger.info(f"Found {len(wellness_records)} wellness records")
    
    # Get metrics data (may include battery status)
    metrics_query = QueryFilter()
    metrics_query.add_term_filter("user_id", user_id)
    metrics_query.add_date_range("timestamp", start=start_datetime, end=end_datetime)
    metrics_query.add_sort("timestamp", ascending=True)
    metrics_query.set_pagination(limit=10000)
    
    metrics_records = storage.search(DataType.METRICS, metrics_query)
    logger.info(f"Found {len(metrics_records)} metrics records")
    
    return {
        "hrv": hrv_records,
        "wellness": wellness_records,
        "metrics": metrics_records
    }


def process_hrv_data(records: List[Dict], target_date: date) -> Dict[str, Any]:
    """Process HRV records for a specific day."""
    day_data = {
        "hrv_values": [],
        "night_hrv_values": [],
        "stress_values": [],
        "night_stress_values": []
    }
    
    for record in records:
        timestamp = record.get('timestamp')
        if not timestamp:
            continue
            
        # Convert timestamp to datetime if it's a string
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                continue
        
        # Ensure timezone awareness
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Convert to Taipei time
        taipei_time = convert_utc_to_taipei_time(timestamp)
        
        # Check if this record is for the target date
        if taipei_time.date() != target_date:
            continue
        
        # Extract HRV values
        hrv_value = None
        for field in ['rmssd', 'hrv_rmssd', 'weekly_average', 'last_night_average', 'value']:
            if field in record and record[field] is not None:
                try:
                    value = float(record[field])
                    if 0 < value < 300:  # Reasonable HRV range
                        hrv_value = value
                        break
                except (ValueError, TypeError):
                    continue
        
        # Extract stress values
        stress_value = None
        for field in ['stress_score', 'stress_level', 'stress']:
            if field in record and record[field] is not None:
                try:
                    value = float(record[field])
                    if 0 <= value <= 100:
                        stress_value = value
                        break
                except (ValueError, TypeError):
                    continue
        
        # Categorize by time of day
        is_night = is_night_time(taipei_time)
        
        if hrv_value is not None:
            day_data["hrv_values"].append(hrv_value)
            if is_night:
                day_data["night_hrv_values"].append(hrv_value)
        
        if stress_value is not None:
            day_data["stress_values"].append(stress_value)
            if is_night:
                day_data["night_stress_values"].append(stress_value)
    
    return day_data


def process_wellness_data(records: List[Dict], target_date: date) -> Dict[str, Any]:
    """Process wellness records for a specific day."""
    day_data = {
        "hr_values": [],
        "night_hr_values": [],
        "rhr_values": [],
        "night_rhr_values": []
    }
    
    for record in records:
        timestamp = record.get('timestamp')
        if not timestamp:
            continue
            
        # Convert timestamp to datetime if it's a string
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                continue
        
        # Ensure timezone awareness
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Convert to Taipei time
        taipei_time = convert_utc_to_taipei_time(timestamp)
        
        # Check if this record is for the target date
        if taipei_time.date() != target_date:
            continue
        
        # Extract heart rate values
        hr_value = None
        for field in ['heart_rate', 'resting_heart_rate', 'rhr', 'value']:
            if field in record and record[field] is not None:
                try:
                    value = float(record[field])
                    if 25 <= value <= 250:  # Reasonable HR range
                        hr_value = value
                        
                        # Categorize as resting HR if field name suggests it
                        if 'resting' in field.lower() or 'rhr' in field.lower():
                            day_data["rhr_values"].append(hr_value)
                            if is_night_time(taipei_time):
                                day_data["night_rhr_values"].append(hr_value)
                        else:
                            day_data["hr_values"].append(hr_value)
                            if is_night_time(taipei_time):
                                day_data["night_hr_values"].append(hr_value)
                        break
                except (ValueError, TypeError):
                    continue
    
    return day_data


def process_battery_data(records: List[Dict], target_date: date) -> Dict[str, Any]:
    """Process metrics records for battery data on a specific day."""
    day_data = {
        "battery_values": []
    }
    
    for record in records:
        timestamp = record.get('timestamp')
        if not timestamp:
            continue
            
        # Convert timestamp to datetime if it's a string
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            except:
                continue
        
        # Ensure timezone awareness
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        
        # Convert to Taipei time
        taipei_time = convert_utc_to_taipei_time(timestamp)
        
        # Check if this record is for the target date
        if taipei_time.date() != target_date:
            continue
        
        # Look for battery-related fields
        battery_value = None
        for field in ['battery_level', 'battery', 'battery_percentage', 'power_level']:
            if field in record and record[field] is not None:
                try:
                    value = float(record[field])
                    if 0 <= value <= 100:  # Battery percentage
                        battery_value = value
                        break
                except (ValueError, TypeError):
                    continue
        
        if battery_value is not None:
            day_data["battery_values"].append(battery_value)
    
    return day_data


def calculate_trend(values: List[float]) -> str:
    """Calculate trend from a list of daily averages."""
    if len(values) < 3:
        return "stable"
    
    # Simple trend calculation: compare first and last thirds
    third = len(values) // 3
    first_third_avg = sum(values[:third]) / third if third > 0 else values[0]
    last_third_avg = sum(values[-third:]) / third if third > 0 else values[-1]
    
    diff_percent = ((last_third_avg - first_third_avg) / first_third_avg) * 100
    
    if diff_percent > 5:
        return "improving"
    elif diff_percent < -5:
        return "declining"
    else:
        return "stable"


@router.post("/health/summary", response_model=HealthMetricsResponse,
             operation_id="get_health_metrics",
             description="Get user health metrics (HRV, heart rate, battery status) for a date range with night averages.")
async def get_health_metrics(
    request: Request,
    health_request: HealthMetricsRequest,
    current_user: User = Depends(get_current_user),
) -> HealthMetricsResponse:
    """Get user health metrics (HRV, heart rate, battery status) for a date range with night averages."""
    
    try:
        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)
        
        logger.info(f"Health metrics request for user {user_id} from {health_request.start_date} to {health_request.end_date}")
        
        # Get all health data for the period
        health_data = get_health_data_for_period(
            storage, user_id, health_request.start_date, health_request.end_date
        )
        
        # Process data day by day - SIMPLIFIED: Only HRV and Resting HR
        daily_metrics = []
        current_date = health_request.start_date

        # Collect period-wide data for trend analysis
        period_hrv_averages = []
        period_hr_averages = []

        while current_date <= health_request.end_date:
            # Process HRV data for this day
            hrv_data = process_hrv_data(health_data["hrv"], current_date)

            # Process wellness data for this day
            wellness_data = process_wellness_data(health_data["wellness"], current_date)

            # Skip battery data processing - not needed
            
            # Calculate daily metrics - SIMPLIFIED: Only HRV and Resting HR
            daily_metric = DailyHealthMetrics(
                date=current_date,

                # HRV metrics - Only average values
                hrv_rmssd_avg=sum(hrv_data["hrv_values"]) / len(hrv_data["hrv_values"]) if hrv_data["hrv_values"] else None,
                hrv_rmssd_night_avg=sum(hrv_data["night_hrv_values"]) / len(hrv_data["night_hrv_values"]) if hrv_data["night_hrv_values"] else None,
                hrv_rmssd_min=None,  # Removed detailed stats
                hrv_rmssd_max=None,  # Removed detailed stats
                hrv_data_points=len(hrv_data["hrv_values"]),
                hrv_night_data_points=len(hrv_data["night_hrv_values"]),

                # Heart rate metrics - Only resting HR average
                resting_hr_avg=sum(wellness_data["rhr_values"]) / len(wellness_data["rhr_values"]) if wellness_data["rhr_values"] else (
                    sum(wellness_data["hr_values"]) / len(wellness_data["hr_values"]) if wellness_data["hr_values"] else None
                ),
                resting_hr_night_avg=None,  # Removed night HR to simplify
                resting_hr_min=None,  # Removed detailed stats
                resting_hr_max=None,  # Removed detailed stats
                hr_data_points=len(wellness_data["rhr_values"]) + len(wellness_data["hr_values"]),
                hr_night_data_points=0,  # Simplified

                # Removed battery metrics entirely
                battery_level_avg=None,
                battery_level_min=None,
                battery_level_max=None,
                battery_data_points=0,

                # Removed stress metrics entirely
                stress_score_avg=None,
                stress_score_night_avg=None,
            )
            
            daily_metrics.append(daily_metric)
            
            # Collect for period trends - SIMPLIFIED: Only HRV and Resting HR
            if daily_metric.hrv_rmssd_avg is not None:
                period_hrv_averages.append(daily_metric.hrv_rmssd_avg)
            if daily_metric.resting_hr_avg is not None:
                period_hr_averages.append(daily_metric.resting_hr_avg)
            
            current_date += timedelta(days=1)
        
        # Calculate period summary
        total_days = (health_request.end_date - health_request.start_date).days + 1
        
        # Calculate simplified metrics - Only HRV and Resting HR
        all_night_hrv = []
        total_hrv_measurements = 0
        total_hr_measurements = 0

        for daily in daily_metrics:
            total_hrv_measurements += daily.hrv_data_points
            total_hr_measurements += daily.hr_data_points

            if daily.hrv_rmssd_night_avg is not None:
                all_night_hrv.extend([daily.hrv_rmssd_night_avg] * daily.hrv_night_data_points)

        summary = HealthMetricsSummary(
            start_date=health_request.start_date,
            end_date=health_request.end_date,
            total_days=total_days,

            # HRV summary - Simplified
            avg_hrv_rmssd=sum(period_hrv_averages) / len(period_hrv_averages) if period_hrv_averages else None,
            avg_hrv_rmssd_night=sum(all_night_hrv) / len(all_night_hrv) if all_night_hrv else None,
            hrv_trend=calculate_trend(period_hrv_averages),
            total_hrv_measurements=total_hrv_measurements,
            total_hrv_night_measurements=sum(d.hrv_night_data_points for d in daily_metrics),

            # Heart rate summary - Only resting HR
            avg_resting_hr=sum(period_hr_averages) / len(period_hr_averages) if period_hr_averages else None,
            avg_resting_hr_night=None,  # Simplified - removed night HR
            hr_trend=calculate_trend(period_hr_averages),
            total_hr_measurements=total_hr_measurements,
            total_hr_night_measurements=0,  # Simplified

            # Removed battery summary entirely
            avg_battery_level=None,
            battery_trend="stable",  # Default value
            total_battery_measurements=0,
        )
        
        # Log user action - SIMPLIFIED
        audit_logger.log_user_action(
            request=request,
            action="health_metrics_requested",
            user_id=current_user.id,
            details={
                "date_range": f"{health_request.start_date} to {health_request.end_date}",
                "total_days": total_days,
                "hrv_measurements": total_hrv_measurements,
                "hr_measurements": total_hr_measurements,
            },
        )

        logger.info(f"Simplified health metrics generated: {total_days} days, {total_hrv_measurements} HRV, {total_hr_measurements} HR measurements")
        
        return HealthMetricsResponse(
            user_id=user_id,
            summary=summary,
            daily_metrics=daily_metrics,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Health metrics error",
            user_id=getattr(current_user, 'id', 'unknown'),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health metrics",
        )
