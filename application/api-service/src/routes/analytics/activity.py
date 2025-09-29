"""
Activity summary analytics endpoints.
"""

from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import PlainTextResponse
import structlog
from tabulate import tabulate

from ...models.responses import WeeklyActivitySummary, ZoneDistribution
from ...models.requests import WeeklyActivitySummaryRequest
from ...middleware.auth import get_current_user
from ...middleware.logging import audit_logger
from ...database import User
from ...database import get_elasticsearch_storage
from .utils import (
    get_user_thresholds,
    get_zone_method_mapping,
    create_zones_with_definitions,
    calculate_zone_distribution_efficient,
    get_total_records_count,
    calculate_zone_distribution,
    format_time_hhmm,
)
from peakflow import DataType, QueryFilter
from peakflow.analytics import (
    PowerZoneAnalyzer,
    PaceZoneAnalyzer,
    HeartRateZoneAnalyzer,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post("/activity/summary/markdown", response_class=PlainTextResponse,
            operation_id="get_activity_summary_markdown",
            tags=["mcp", "activity"],
            description="Get user activity summary in markdown format optimized for LLM consumption. Returns distance, time, TSS, and zone distributions in structured markdown.")
async def get_activity_summary_markdown(
    request: Request,
    summary_request: WeeklyActivitySummaryRequest,
    current_user: User = Depends(get_current_user),
) -> str:
    """Get user activity summary in markdown format optimized for LLM consumption."""

    # Get the structured data first
    activity_response = await get_summary(request, summary_request, current_user)

    # Convert to markdown
    markdown_content = []

    # Header
    markdown_content.append(f"# Activity Summary Report")
    markdown_content.append(f"**Period:** {activity_response.date_range['start']} to {activity_response.date_range['end']}")
    markdown_content.append("")

    # Summary metrics
    markdown_content.append("## Summary Metrics")
    markdown_content.append(f"- **Total Distance:** {activity_response.total_distance} km")
    markdown_content.append(f"- **Total Time:** {activity_response.total_time}")
    markdown_content.append(f"- **Total TSS:** {activity_response.total_tss}")
    markdown_content.append(f"- **Activity Count:** {activity_response.activity_count}")
    markdown_content.append("")

    # Zone methods
    markdown_content.append("## Zone Analysis Methods")
    markdown_content.append(f"- **Power Zones:** {activity_response.zone_methods['power']}")
    markdown_content.append(f"- **Pace Zones:** {activity_response.zone_methods['pace']}")
    markdown_content.append(f"- **Heart Rate Zones:** {activity_response.zone_methods['heart_rate']}")
    markdown_content.append("")

    # Power zone distribution using tabulate
    if activity_response.power_zones and activity_response.power_zones.zones:
        markdown_content.append("## Power Zone Distribution")
        power_data = []
        for zone in activity_response.power_zones.zones:
            # Convert seconds to MM:SS format
            time_str = f"{zone.seconds // 60}:{zone.seconds % 60:02d}" if zone.seconds else "0:00"
            pct_str = f"{zone.percentage:.1f}%" if zone.percentage else "0.0%"
            power_data.append([
                zone.zone_number,
                zone.description,
                time_str,
                pct_str
            ])

        if power_data:
            power_table = tabulate(
                power_data,
                headers=["Zone", "Description", "Time", "Percentage"],
                tablefmt="github"
            )
            markdown_content.append(power_table)
        markdown_content.append("")

    # Pace zone distribution using tabulate
    if activity_response.pace_zones and activity_response.pace_zones.zones:
        markdown_content.append("## Pace Zone Distribution")
        pace_data = []
        for zone in activity_response.pace_zones.zones:
            # Convert seconds to MM:SS format
            time_str = f"{zone.seconds // 60}:{zone.seconds % 60:02d}" if zone.seconds else "0:00"
            pct_str = f"{zone.percentage:.1f}%" if zone.percentage else "0.0%"
            pace_data.append([
                zone.zone_number,
                zone.description,
                time_str,
                pct_str
            ])

        if pace_data:
            pace_table = tabulate(
                pace_data,
                headers=["Zone", "Description", "Time", "Percentage"],
                tablefmt="github"
            )
            markdown_content.append(pace_table)
        markdown_content.append("")

    # Heart rate zone distribution using tabulate
    if activity_response.heart_rate_zones and activity_response.heart_rate_zones.zones:
        markdown_content.append("## Heart Rate Zone Distribution")
        hr_data = []
        for zone in activity_response.heart_rate_zones.zones:
            # Convert seconds to MM:SS format
            time_str = f"{zone.seconds // 60}:{zone.seconds % 60:02d}" if zone.seconds else "0:00"
            pct_str = f"{zone.percentage:.1f}%" if zone.percentage else "0.0%"
            hr_data.append([
                zone.zone_number,
                zone.description,
                time_str,
                pct_str
            ])

        if hr_data:
            hr_table = tabulate(
                hr_data,
                headers=["Zone", "Description", "Time", "Percentage"],
                tablefmt="presto"
            )
            markdown_content.append(hr_table)
        markdown_content.append("")

    # Key insights
    markdown_content.append("## Key Insights")

    if activity_response.total_distance > 0:
        avg_distance = activity_response.total_distance / activity_response.activity_count if activity_response.activity_count > 0 else 0
        markdown_content.append(f"- Average distance per activity: {avg_distance:.1f} km")

    if activity_response.total_tss > 0:
        avg_tss = activity_response.total_tss / activity_response.activity_count if activity_response.activity_count > 0 else 0
        markdown_content.append(f"- Average TSS per activity: {avg_tss:.1f}")

    # Zone distribution insights
    if activity_response.power_zones and activity_response.power_zones.zones:
        high_intensity_zones = [z for z in activity_response.power_zones.zones if z.zone_number >= 4 and z.percentage and z.percentage > 0]
        if high_intensity_zones:
            total_high_intensity = sum(z.percentage for z in high_intensity_zones)
            markdown_content.append(f"- High intensity power training (Zone 4+): {total_high_intensity:.1f}%")

    return "\n".join(markdown_content)


@router.post("/activity/summary", response_model=WeeklyActivitySummary,
            operation_id="get_activity_summary",
            tags=["mcp"],
            description="Get user activity summary for custom date range with multi-zone analysis.")
async def get_summary(
    request: Request,
    summary_request: WeeklyActivitySummaryRequest,
    current_user: User = Depends(get_current_user),
) -> WeeklyActivitySummary:
    """Get user activity summary for custom date range with multi-zone analysis."""

    try:
        storage = get_elasticsearch_storage()
        user_id = str(current_user.id)

        # Convert dates to datetime objects
        start_date = datetime.combine(summary_request.start_date, datetime.min.time())
        end_date = datetime.combine(summary_request.end_date, datetime.max.time())

        # Get user thresholds
        thresholds = get_user_thresholds(storage, user_id)
        logger.info(f"User thresholds: {thresholds}")

        # Add fallback thresholds for testing if none exist
        if not thresholds["threshold_power"]:
            thresholds["threshold_power"] = 250.0  # Default threshold power
            logger.info("Using default threshold power: 250W")

        if not thresholds["threshold_pace"]:
            thresholds["threshold_pace"] = 5.0  # Default threshold pace (5 min/km)
            logger.info("Using default threshold pace: 5 min/km")

        if not thresholds["max_heart_rate"]:
            thresholds["max_heart_rate"] = 190.0  # Default max HR
            logger.info("Using default max heart rate: 190 bpm")

        zone_mappings = get_zone_method_mapping()

        # Initialize zone analyzers
        power_analyzer = PowerZoneAnalyzer()
        pace_analyzer = PaceZoneAnalyzer()
        hr_analyzer = HeartRateZoneAnalyzer()

        # Set up zone methods
        power_method = zone_mappings["power"][summary_request.power_zone_method]
        pace_method = zone_mappings["pace"][summary_request.pace_zone_method]
        hr_method = zone_mappings["heart_rate"][summary_request.heart_rate_zone_method]

        # Debug logging
        logger.info(f"Weekly summary request for user {user_id}")
        logger.info(f"Date range: {start_date} to {end_date}")

        # Get record counts for efficient zone calculations (no data fetching)
        power_records_count = get_total_records_count(storage, user_id, start_date, end_date, "power_fields.power")
        speed_records_count = get_total_records_count(storage, user_id, start_date, end_date, "speed")
        hr_records_count = get_total_records_count(storage, user_id, start_date, end_date, "heart_rate")

        logger.info(f"Record counts - Power: {power_records_count}, Speed: {speed_records_count}, HR: {hr_records_count}")

        # Get session data for summary metrics
        sessions_query = QueryFilter()
        sessions_query.add_term_filter("user_id", user_id)
        sessions_query.add_date_range("timestamp", start=start_date, end=end_date)
        sessions_query.set_pagination(limit=100)

        sessions = storage.search(DataType.SESSION, sessions_query)
        logger.info(f"Sessions found: {len(sessions)}")

        # Get TSS data
        tss_query = QueryFilter()
        tss_query.add_term_filter("user_id", user_id)
        tss_query.add_date_range("timestamp", start=start_date, end=end_date)
        tss_query.set_pagination(limit=100)

        tss_records = storage.search(DataType.TSS, tss_query)
        logger.info(f"TSS records found: {len(tss_records)}")

        # Calculate summary metrics
        total_distance = 0.0
        total_tss = 0.0
        total_time_seconds = 0

        for session in sessions:
            # Distance (convert meters to km)
            distance = session.get("total_distance", 0)
            if distance:
                total_distance += distance / 1000

            # Time
            session_time = session.get("total_timer_time", 0) or session.get("total_elapsed_time", 0)
            if session_time:
                total_time_seconds += int(session_time)

        # Calculate total TSS
        for tss_record in tss_records:
            tss_value = tss_record.get("primary_tss", 0) or tss_record.get("tss", 0)
            if tss_value:
                total_tss += tss_value

        # Calculate zone distributions using efficient Elasticsearch aggregations
        power_zones = []
        pace_zones = []
        hr_zones = []

        # Power zones
        if thresholds["threshold_power"] and power_records_count > 0:
            try:
                power_zones = power_analyzer.calculate_zones(
                    power_method,
                    thresholds["threshold_power"]
                )
                logger.info(f"Calculated {len(power_zones)} power zones")
            except Exception as e:
                logger.warning(f"Power zone calculation failed: {e}")
        else:
            logger.info(f"Skipping power zones - threshold: {thresholds['threshold_power']}, records: {power_records_count}")

        # Pace zones (convert speed field to pace ranges)
        if thresholds["threshold_pace"] and speed_records_count > 0:
            try:
                # Convert threshold_pace from min/km to sec/km for the pace analyzer
                threshold_pace_sec_km = thresholds["threshold_pace"] * 60
                logger.info(f"Converting threshold pace: {thresholds['threshold_pace']} min/km -> {threshold_pace_sec_km} sec/km")

                pace_zones = pace_analyzer.calculate_zones(
                    pace_method,
                    threshold_pace_sec_km
                )
                logger.info(f"Calculated {len(pace_zones)} pace zones")
                # Convert pace zones to speed ranges for querying
                for zone in pace_zones:
                    if hasattr(zone, 'pace_range'):
                        pace_min, pace_max = zone.pace_range
                        # Convert pace (sec/km) to speed (m/s)
                        # pace_min/pace_max are in sec/km, speed should be m/s
                        # speed = 1000 / pace_in_seconds_per_km
                        # Note: Lower pace (faster) = higher speed, so min/max are flipped
                        if pace_max > 0 and pace_max != float('inf'):
                            speed_min = 1000 / pace_max  # Faster pace = higher speed
                        else:
                            speed_min = 0

                        if pace_min > 0 and pace_min != float('inf'):
                            speed_max = 1000 / pace_min  # Slower pace = lower speed
                        else:
                            speed_max = float('inf')

                        zone.speed_range = (speed_min, speed_max)
                        logger.debug(f"Zone {zone.zone_number}: pace {pace_min:.1f}-{pace_max:.1f} sec/km -> speed {speed_min:.2f}-{speed_max:.2f} m/s")
            except Exception as e:
                logger.warning(f"Pace zone calculation failed: {e}")
                pace_zones = []

        # Heart rate zones
        if thresholds["max_heart_rate"] and hr_records_count > 0:
            try:
                hr_zones = hr_analyzer.calculate_zones(
                    hr_method,
                    thresholds["max_heart_rate"],
                    None,  # age parameter
                    thresholds["threshold_heart_rate"]  # threshold_heart_rate parameter
                )
            except Exception as e:
                logger.warning(f"HR zone calculation failed: {e}")

        # Calculate zone distributions using efficient aggregations
        power_distribution = calculate_zone_distribution_efficient(
            storage, user_id, start_date, end_date, "power_fields.power", power_zones, power_records_count
        )

        # For pace, we need to use speed field with converted ranges
        pace_distribution = ZoneDistribution()
        if pace_zones and speed_records_count > 0:
            try:
                # Create temporary zones with speed ranges for aggregation
                speed_zones = []
                for zone in pace_zones:
                    if hasattr(zone, 'speed_range'):
                        speed_min, speed_max = zone.speed_range
                        # Skip zones with infinite or invalid ranges
                        if (speed_min is not None and speed_max is not None and
                            speed_min != float('inf') and speed_max != float('inf') and
                            speed_min < speed_max and speed_max > 0):

                            speed_zone = type('SpeedZone', (), {
                                'speed_range': (speed_min, speed_max)
                            })()
                            speed_zones.append(speed_zone)

                logger.info(f"Created {len(speed_zones)} speed zones for pace aggregation")

                if speed_zones:
                    pace_distribution = calculate_zone_distribution_efficient(
                        storage, user_id, start_date, end_date, "speed", speed_zones, speed_records_count
                    )
                    logger.info(f"Pace distribution calculated successfully")
                else:
                    logger.warning("No valid speed zones created from pace zones")
            except Exception as e:
                logger.error(f"Failed to calculate pace distribution: {e}")
        else:
            logger.info(f"Skipping pace zones - zones: {len(pace_zones) if pace_zones else 0}, records: {speed_records_count}")

        hr_distribution = calculate_zone_distribution_efficient(
            storage, user_id, start_date, end_date, "heart_rate", hr_zones, hr_records_count
        )

        # Format total time
        total_time_formatted = format_time_hhmm(total_time_seconds)

        # Log user action
        audit_logger.log_user_action(
            request=request,
            action="weekly_summary_requested",
            user_id=current_user.id,
            details={
                "activities_found": len(sessions),
                "date_range": f"{summary_request.start_date} to {summary_request.end_date}",
                "zone_methods": {
                    "power": summary_request.power_zone_method.value,
                    "pace": summary_request.pace_zone_method.value,
                    "heart_rate": summary_request.heart_rate_zone_method.value,
                }
            },
        )

        # Final debug log before return
        logger.info(f"Final results - Distance: {total_distance}, TSS: {total_tss}, Time: {total_time_formatted}")
        logger.info(f"Power zones calculated: {len(power_zones)}, Pace zones: {len(pace_zones)}, HR zones: {len(hr_zones)}")

        # Create enhanced zone definitions with descriptions
        power_zones_with_def = create_zones_with_definitions(
            power_zones, power_distribution, summary_request.power_zone_method.value,
            thresholds["threshold_power"], "watts"
        )

        pace_zones_with_def = create_zones_with_definitions(
            pace_zones, pace_distribution, summary_request.pace_zone_method.value,
            thresholds["threshold_pace"], "min/km"
        )

        hr_zones_with_def = create_zones_with_definitions(
            hr_zones, hr_distribution, summary_request.heart_rate_zone_method.value,
            thresholds["max_heart_rate"], "bpm"
        )

        return WeeklyActivitySummary(
            user_id=user_id,
            total_distance=round(total_distance, 2),
            total_tss=round(total_tss, 1),
            total_time=total_time_formatted,
            activity_count=len(sessions),
            power_zone_distribution=power_distribution,
            pace_zone_distribution=pace_distribution,
            heart_rate_zone_distribution=hr_distribution,
            power_zones=power_zones_with_def,
            pace_zones=pace_zones_with_def,
            heart_rate_zones=hr_zones_with_def,
            date_range={
                "start": summary_request.start_date.isoformat(),
                "end": summary_request.end_date.isoformat()
            },
            zone_methods={
                "power": summary_request.power_zone_method.value,
                "pace": summary_request.pace_zone_method.value,
                "heart_rate": summary_request.heart_rate_zone_method.value,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Weekly summary error",
            user_id=getattr(current_user, 'id', 'unknown'),
            error=str(e)
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate activity summary",
        )
