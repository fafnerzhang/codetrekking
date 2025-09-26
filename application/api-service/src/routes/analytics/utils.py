"""
Shared utility functions for analytics endpoints.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import structlog

from ...models.responses import (
    ZoneDistribution,
    ZonesWithDefinitions,
    ZoneDefinition,
)
from ...models.requests import (
    PowerZoneMethod,
    PaceZoneMethod,
    HeartRateZoneMethod,
)
from peakflow import ElasticsearchStorage, DataType, QueryFilter
from peakflow.analytics import (
    PowerZoneMethod as PFPowerZoneMethod,
    PaceZoneMethod as PFPaceZoneMethod,
    HeartRateZoneMethod as PFHeartRateZoneMethod,
)

logger = structlog.get_logger(__name__)


def get_user_thresholds(storage: ElasticsearchStorage, user_id: str) -> Dict[str, Optional[float]]:
    """Get user's thresholds for power, pace, and heart rate from user indicators."""
    thresholds = {
        "threshold_power": None,
        "threshold_pace": None,
        "threshold_heart_rate": None,
        "max_heart_rate": None
    }

    try:
        # Get all user indicators
        threshold_query = QueryFilter()
        threshold_query.add_term_filter("user_id", user_id)
        threshold_query.set_pagination(limit=10)

        indicators = storage.search(DataType.USER_INDICATOR, threshold_query)

        for indicator in indicators:
            # Power thresholds
            if indicator.get("threshold_power"):
                thresholds["threshold_power"] = indicator.get("threshold_power")
            elif indicator.get("critical_power"):
                thresholds["threshold_power"] = indicator.get("critical_power")

            # Pace threshold (typically in min/km)
            if indicator.get("threshold_pace"):
                thresholds["threshold_pace"] = indicator.get("threshold_pace")

            # Heart rate thresholds
            if indicator.get("threshold_heart_rate"):
                thresholds["threshold_heart_rate"] = indicator.get("threshold_heart_rate")
            if indicator.get("max_heart_rate"):
                thresholds["max_heart_rate"] = indicator.get("max_heart_rate")

        return thresholds

    except Exception as e:
        logger.error(f"Failed to get user thresholds for {user_id}: {str(e)}")
        return thresholds


def get_zone_method_mapping() -> Dict[str, Dict]:
    """Map request zone methods to peakflow zone methods."""
    return {
        "power": {
            PowerZoneMethod.STEVE_PALLADINO: PFPowerZoneMethod.STEVE_PALLADINO,
            PowerZoneMethod.STRYD_RUNNING: PFPowerZoneMethod.STRYD_RUNNING,
            PowerZoneMethod.CRITICAL_POWER: PFPowerZoneMethod.CRITICAL_POWER,
        },
        "pace": {
            PaceZoneMethod.JOE_FRIEL_RUNNING: PFPaceZoneMethod.JOE_FRIEL,
            PaceZoneMethod.JACK_DANIELS: PFPaceZoneMethod.JACK_DANIELS,
            PaceZoneMethod.PZI: PFPaceZoneMethod.PZI,
        },
        "heart_rate": {
            HeartRateZoneMethod.JOE_FRIEL: PFHeartRateZoneMethod.JOE_FRIEL,
            HeartRateZoneMethod.SALLY_EDWARDS: PFHeartRateZoneMethod.SALLY_EDWARDS,
            HeartRateZoneMethod.TIMEX: PFHeartRateZoneMethod.TIMEX,
        }
    }


def create_zones_with_definitions(zones, zone_distribution: ZoneDistribution, method: str, threshold_value: float = None, threshold_unit: str = None) -> ZonesWithDefinitions:
    """Convert zone objects with distribution data to ZonesWithDefinitions format."""
    zone_definitions = []

    # Map distribution data to zones
    distribution_dict = {}
    for i in range(1, 8):
        seconds_attr = f"zone_{i}_seconds"
        percentage_attr = f"zone_{i}_percentage"
        if hasattr(zone_distribution, seconds_attr):
            distribution_dict[i] = {
                'seconds': getattr(zone_distribution, seconds_attr),
                'percentage': getattr(zone_distribution, percentage_attr)
            }

    for zone in zones:
        zone_num = zone.zone_number if hasattr(zone, 'zone_number') else 0

        # Get zone range values and determine unit
        if hasattr(zone, 'power_range'):
            range_min, range_max = zone.power_range
            range_unit = "watts"
        elif hasattr(zone, 'pace_range'):
            range_min, range_max = zone.pace_range
            # Convert from sec/km to min/km for display
            range_min, range_max = range_min / 60, range_max / 60
            range_unit = "min/km"
        elif hasattr(zone, 'heart_rate_range'):
            range_min, range_max = zone.heart_rate_range
            range_unit = "bpm"
        else:
            range_min, range_max = 0, 0
            range_unit = "unknown"

        # Handle infinity values for JSON compliance
        if range_min == float('inf') or range_min != range_min:  # Check for inf or NaN
            range_min = 0
        if range_max == float('inf') or range_max != range_max:  # Check for inf or NaN
            range_max = 999999  # Use a large but finite number

        # Get percentage range if available
        percentage_min = percentage_max = None
        if hasattr(zone, 'percentage_range') and zone.percentage_range:
            percentage_min, percentage_max = zone.percentage_range

        # Get time distribution data
        distribution_data = distribution_dict.get(zone_num, {'seconds': 0, 'percentage': 0.0})

        # Handle infinity values for JSON compliance
        if percentage_min == float('inf') or percentage_min != percentage_min:
            percentage_min = 0
        if percentage_max == float('inf') or percentage_max != percentage_max:
            percentage_max = None

        zone_def = ZoneDefinition(
            zone_number=zone_num,
            zone_name=getattr(zone, 'zone_name', f"Zone {zone_num}"),
            range_min=range_min,
            range_max=range_max,
            range_unit=range_unit,
            percentage_min=percentage_min,
            percentage_max=percentage_max,
            description=getattr(zone, 'description', ''),
            purpose=getattr(zone, 'purpose', ''),
            benefits=getattr(zone, 'training_benefits', []) or getattr(zone, 'benefits', []),
            duration_guidance=getattr(zone, 'duration_guidelines', '') or getattr(zone, 'duration_guidance', ''),
            intensity_feel=getattr(zone, 'intensity_feel', '') or getattr(zone, 'effort_level', ''),
            seconds=distribution_data['seconds'],
            percentage=distribution_data['percentage']
        )
        zone_definitions.append(zone_def)

    return ZonesWithDefinitions(
        zones=zone_definitions,
        method=method,
        threshold_value=threshold_value,
        threshold_unit=threshold_unit
    )


def calculate_zone_distribution_efficient(
    storage: ElasticsearchStorage,
    user_id: str,
    start_date: datetime,
    end_date: datetime,
    field_name: str,
    zones: List,
    total_records: int
) -> ZoneDistribution:
    """Calculate zone distribution using Elasticsearch range aggregations."""
    distribution = ZoneDistribution()

    if not zones or total_records == 0:
        return distribution

    try:
        # Build range aggregation for zones
        ranges = []
        for i, zone in enumerate(zones[:7]):
            # Try different zone range attributes
            zone_min, zone_max = None, None
            if hasattr(zone, 'power_range') and zone.power_range:
                zone_min, zone_max = zone.power_range
            elif hasattr(zone, 'pace_range') and zone.pace_range:
                zone_min, zone_max = zone.pace_range
            elif hasattr(zone, 'heart_rate_range') and zone.heart_rate_range:
                zone_min, zone_max = zone.heart_rate_range

            if zone_min is not None and zone_max is not None:
                # Handle infinity values
                if zone_max == float('inf'):
                    zone_max = 999999
                
                ranges.append({
                    "key": f"zone_{i+1}",
                    "from": zone_min,
                    "to": zone_max
                })

        if not ranges:
            return distribution

        # Build Elasticsearch aggregation query
        agg_query = {
            "size": 0,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": user_id}},
                        {"range": {"timestamp": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                        {"exists": {"field": field_name}},
                        {"range": {field_name: {"gt": 0}}}
                    ]
                }
            },
            "aggs": {
                "zone_ranges": {
                    "range": {
                        "field": field_name,
                        "ranges": ranges
                    }
                }
            }
        }

        es_client = storage.es
        index_name = storage._get_index_name(DataType.RECORD)

        response = es_client.search(index=index_name, body=agg_query)

        # Extract results
        if "aggregations" in response:
            buckets = response["aggregations"]["zone_ranges"]["buckets"]

            for bucket in buckets:
                zone_key = bucket["key"]
                count = bucket["doc_count"]
                percentage = round((count / total_records) * 100, 1) if total_records > 0 else 0.0

                setattr(distribution, f'{zone_key}_seconds', count)
                setattr(distribution, f'{zone_key}_percentage', percentage)

    except Exception as e:
        logger.error(f"Failed to calculate zone distribution efficiently: {e}")
        # Fallback to empty distribution

    return distribution


def get_total_records_count(
    storage: ElasticsearchStorage,
    user_id: str,
    start_date: datetime,
    end_date: datetime,
    field_name: str
) -> int:
    """Get total count of records with valid field values using Elasticsearch count API."""
    try:
        # Use direct Elasticsearch count API for efficiency
        count_query = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"user_id": user_id}},
                        {"range": {"timestamp": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}},
                        {"exists": {"field": field_name}},
                        {"range": {field_name: {"gt": 0}}}
                    ]
                }
            }
        }

        es_client = storage.es
        index_name = storage._get_index_name(DataType.RECORD)

        response = es_client.count(index=index_name, body=count_query)
        count = response.get("count", 0)

        logger.info(f"Records count for field {field_name}: {count}")
        return count

    except Exception as e:
        logger.error(f"Failed to get records count for {field_name}: {e}")
        return 0


def calculate_zone_distribution(data_values: List[float], zones: List, total_seconds: int) -> ZoneDistribution:
    """Calculate zone distribution with time and percentage (fallback method)."""
    distribution = ZoneDistribution()

    if not data_values or not zones or total_seconds == 0:
        return distribution

    # Each data point represents 1 second typically
    zone_counts = [0] * 7  # Support up to 7 zones

    for value in data_values:
        if value is None or value <= 0:
            continue

        # Find which zone this value belongs to
        for i, zone in enumerate(zones[:7]):  # Limit to 7 zones
            if hasattr(zone, 'power_range'):
                zone_min, zone_max = zone.power_range
            elif hasattr(zone, 'pace_range'):
                zone_min, zone_max = zone.pace_range
            elif hasattr(zone, 'heart_rate_range'):
                zone_min, zone_max = zone.heart_rate_range
            else:
                continue

            if zone_min <= value <= zone_max:
                zone_counts[i] += 1
                break

    # Convert to seconds and percentages
    for i in range(7):
        seconds = zone_counts[i]
        percentage = round((seconds / total_seconds) * 100, 1) if total_seconds > 0 else 0.0

        setattr(distribution, f'zone_{i+1}_seconds', seconds)
        setattr(distribution, f'zone_{i+1}_percentage', percentage)

    return distribution


def format_time_hhmm(total_seconds: int) -> str:
    """Format seconds to HH:MM format."""
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"
