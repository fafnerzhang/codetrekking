#!/usr/bin/env python3
"""
Pydantic Data Models for Fitness Activity Data

Provides flexible and extensible models for session, record, and lap data
that can handle unknown fields gracefully while maintaining validation for core fields.
"""

from datetime import datetime
from typing import Dict, Any, Optional, Union, List
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum


class LocationModel(BaseModel):
    """GPS location data model"""

    lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude in degrees")
    lon: Optional[float] = Field(
        None, ge=-180, le=180, description="Longitude in degrees"
    )

    model_config = ConfigDict(extra="allow")


class SportType(str, Enum):
    """Sport type enumeration"""

    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    WALKING = "walking"
    HIKING = "hiking"
    MOUNTAINEERING = "mountaineering"
    ROWING = "rowing"
    ELLIPTICAL = "elliptical"
    TENNIS = "tennis"
    BASKETBALL = "basketball"
    SOCCER = "soccer"
    GOLF = "golf"
    YOGA = "yoga"
    PILATES = "pilates"
    OTHER = "other"


class IntensityType(str, Enum):
    """Training intensity levels"""

    ACTIVE_RECOVERY = "active_recovery"
    EASY = "easy"
    MODERATE = "moderate"
    HARD = "hard"
    MAXIMUM = "maximum"


class LapTrigger(str, Enum):
    """Lap trigger types"""

    MANUAL = "manual"
    DISTANCE = "distance"
    TIME = "time"
    POSITION_START = "position_start"
    POSITION_LAP = "position_lap"
    POSITION_WAYPOINT = "position_waypoint"
    POSITION_MARKED = "position_marked"
    SESSION_END = "session_end"
    FITNESS_EQUIPMENT = "fitness_equipment"


class PowerFieldsModel(BaseModel):
    """Power-related fields model"""

    power: Optional[float] = Field(None, ge=0, description="Power in watts")
    normalized_power: Optional[float] = Field(
        None, ge=0, description="Normalized power in watts"
    )
    left_power: Optional[float] = Field(
        None, ge=0, description="Left leg power in watts"
    )
    right_power: Optional[float] = Field(
        None, ge=0, description="Right leg power in watts"
    )
    left_right_balance: Optional[float] = Field(
        None, ge=0, le=100, description="Left/right power balance percentage"
    )
    left_torque_effectiveness: Optional[float] = Field(
        None, ge=0, le=100, description="Left torque effectiveness percentage"
    )
    right_torque_effectiveness: Optional[float] = Field(
        None, ge=0, le=100, description="Right torque effectiveness percentage"
    )
    left_pedal_smoothness: Optional[float] = Field(
        None, ge=0, le=100, description="Left pedal smoothness percentage"
    )
    right_pedal_smoothness: Optional[float] = Field(
        None, ge=0, le=100, description="Right pedal smoothness percentage"
    )
    combined_pedal_smoothness: Optional[float] = Field(
        None, ge=0, le=100, description="Combined pedal smoothness percentage"
    )
    functional_threshold_power: Optional[float] = Field(
        None, ge=0, description="FTP in watts"
    )
    training_stress_score: Optional[float] = Field(
        None, ge=0, description="Training Stress Score"
    )

    model_config = ConfigDict(extra="allow")


class RunningDynamicsModel(BaseModel):
    """Running dynamics fields model"""

    vertical_oscillation: Optional[float] = Field(
        None, ge=0, description="Vertical oscillation in mm"
    )
    stance_time: Optional[float] = Field(
        None, ge=0, description="Ground contact time in ms"
    )
    step_length: Optional[float] = Field(None, ge=0, description="Step length in mm")
    vertical_ratio: Optional[float] = Field(
        None, ge=0, description="Vertical ratio percentage"
    )
    ground_contact_time: Optional[float] = Field(
        None, ge=0, description="Ground contact time in ms"
    )
    form_power: Optional[float] = Field(None, ge=0, description="Form power in watts")
    leg_spring_stiffness: Optional[float] = Field(
        None, ge=0, description="Leg spring stiffness in kN/m"
    )
    stance_time_percent: Optional[float] = Field(
        None, ge=0, le=100, description="Stance time percentage"
    )
    vertical_oscillation_percent: Optional[float] = Field(
        None, ge=0, description="Vertical oscillation percentage"
    )

    model_config = ConfigDict(extra="allow")


class CyclingFieldsModel(BaseModel):
    """Cycling-specific fields model"""

    left_pco: Optional[float] = Field(None, description="Left power center offset")
    right_pco: Optional[float] = Field(None, description="Right power center offset")
    left_power_phase: Optional[float] = Field(
        None, description="Left power phase angle"
    )
    right_power_phase: Optional[float] = Field(
        None, description="Right power phase angle"
    )
    left_power_phase_peak: Optional[float] = Field(
        None, description="Left power phase peak angle"
    )
    right_power_phase_peak: Optional[float] = Field(
        None, description="Right power phase peak angle"
    )
    gear_change_data: Optional[str] = Field(None, description="Gear change information")

    model_config = ConfigDict(extra="allow")


class SwimmingFieldsModel(BaseModel):
    """Swimming-specific fields model"""

    pool_length: Optional[float] = Field(
        None, ge=0, description="Pool length in meters"
    )
    lengths: Optional[int] = Field(None, ge=0, description="Number of pool lengths")
    stroke_count: Optional[int] = Field(None, ge=0, description="Number of strokes")
    strokes: Optional[int] = Field(None, ge=0, description="Total strokes")
    swolf: Optional[int] = Field(None, ge=0, description="SWOLF score (time + strokes)")

    model_config = ConfigDict(extra="allow")


class EnvironmentalModel(BaseModel):
    """Environmental conditions model"""

    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    humidity: Optional[float] = Field(
        None, ge=0, le=100, description="Humidity percentage"
    )
    pressure: Optional[float] = Field(None, ge=0, description="Atmospheric pressure")
    wind_speed: Optional[float] = Field(None, ge=0, description="Wind speed")
    wind_direction: Optional[float] = Field(
        None, ge=0, le=360, description="Wind direction in degrees"
    )
    air_pressure: Optional[float] = Field(None, ge=0, description="Air pressure")
    barometric_pressure: Optional[float] = Field(
        None, ge=0, description="Barometric pressure"
    )

    model_config = ConfigDict(extra="allow")


class ZoneFieldsModel(BaseModel):
    """Zone-related fields model"""

    hr_zone: Optional[int] = Field(
        None, ge=1, le=5, description="Heart rate zone (1-5)"
    )
    power_zone: Optional[int] = Field(None, ge=1, le=7, description="Power zone (1-7)")
    pace_zone: Optional[int] = Field(None, ge=1, le=5, description="Pace zone (1-5)")
    cadence_zone: Optional[int] = Field(
        None, ge=1, le=5, description="Cadence zone (1-5)"
    )

    # Time in zone fields
    time_in_hr_zone_1: Optional[float] = Field(
        None, ge=0, description="Time in HR zone 1 (seconds)"
    )
    time_in_hr_zone_2: Optional[float] = Field(
        None, ge=0, description="Time in HR zone 2 (seconds)"
    )
    time_in_hr_zone_3: Optional[float] = Field(
        None, ge=0, description="Time in HR zone 3 (seconds)"
    )
    time_in_hr_zone_4: Optional[float] = Field(
        None, ge=0, description="Time in HR zone 4 (seconds)"
    )
    time_in_hr_zone_5: Optional[float] = Field(
        None, ge=0, description="Time in HR zone 5 (seconds)"
    )

    time_in_power_zone_1: Optional[float] = Field(
        None, ge=0, description="Time in power zone 1 (seconds)"
    )
    time_in_power_zone_2: Optional[float] = Field(
        None, ge=0, description="Time in power zone 2 (seconds)"
    )
    time_in_power_zone_3: Optional[float] = Field(
        None, ge=0, description="Time in power zone 3 (seconds)"
    )
    time_in_power_zone_4: Optional[float] = Field(
        None, ge=0, description="Time in power zone 4 (seconds)"
    )
    time_in_power_zone_5: Optional[float] = Field(
        None, ge=0, description="Time in power zone 5 (seconds)"
    )
    time_in_power_zone_6: Optional[float] = Field(
        None, ge=0, description="Time in power zone 6 (seconds)"
    )

    model_config = ConfigDict(extra="allow")


class BaseActivityModel(BaseModel):
    """Base model for all activity data types"""

    # Required core fields
    activity_id: str = Field(..., description="Unique activity identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="Timestamp of the data point")

    # Optional ID field for database operations (using alias to avoid underscore)
    doc_id: Optional[str] = Field(
        None, alias="_id", description="Document ID for storage"
    )

    model_config = ConfigDict(
        extra="allow",  # Allow additional fields not defined in the model
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True,  # Allow both field name and alias
    )


class SessionModel(BaseActivityModel):
    """
    Session data model - represents summary data for an entire workout/activity.

    This model is flexible and allows unknown fields while validating core session data.
    """

    # Optional core session fields
    start_time: Optional[datetime] = Field(None, description="Activity start time")
    sport: Optional[SportType] = Field(None, description="Sport/activity type")
    sub_sport: Optional[str] = Field(None, description="Sub-sport category")

    # Duration and distance metrics
    total_timer_time: Optional[float] = Field(
        None, ge=0, description="Total timer time in seconds"
    )
    total_elapsed_time: Optional[float] = Field(
        None, ge=0, description="Total elapsed time in seconds"
    )
    total_distance: Optional[float] = Field(
        None, ge=0, description="Total distance in meters"
    )

    # Speed and pace metrics
    enhanced_avg_speed: Optional[float] = Field(
        None, ge=0, description="Average speed in m/s"
    )
    enhanced_max_speed: Optional[float] = Field(
        None, ge=0, description="Maximum speed in m/s"
    )
    avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")

    # Heart rate metrics
    avg_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Average heart rate in bpm"
    )
    max_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Maximum heart rate in bpm"
    )
    min_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Minimum heart rate in bpm"
    )

    # Calorie and energy metrics
    total_calories: Optional[int] = Field(
        None, ge=0, description="Total calories burned"
    )
    total_fat_calories: Optional[int] = Field(
        None, ge=0, description="Fat calories burned"
    )

    # Elevation metrics
    total_ascent: Optional[float] = Field(
        None, ge=0, description="Total ascent in meters"
    )
    total_descent: Optional[float] = Field(
        None, ge=0, description="Total descent in meters"
    )
    enhanced_avg_altitude: Optional[float] = Field(
        None, description="Average altitude in meters"
    )
    enhanced_max_altitude: Optional[float] = Field(
        None, description="Maximum altitude in meters"
    )
    enhanced_min_altitude: Optional[float] = Field(
        None, description="Minimum altitude in meters"
    )

    # Cadence metrics
    avg_cadence: Optional[float] = Field(None, ge=0, description="Average cadence")
    max_cadence: Optional[float] = Field(None, ge=0, description="Maximum cadence")

    # Location data
    start_position_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Start latitude"
    )
    start_position_long: Optional[float] = Field(
        None, ge=-180, le=180, description="Start longitude"
    )
    end_position_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="End latitude"
    )
    end_position_long: Optional[float] = Field(
        None, ge=-180, le=180, description="End longitude"
    )

    # Optional structured location data
    start_location: Optional[LocationModel] = Field(
        None, description="Start location coordinates"
    )
    end_location: Optional[LocationModel] = Field(
        None, description="End location coordinates"
    )

    # Training metrics
    intensity: Optional[IntensityType] = Field(
        None, description="Training intensity level"
    )
    training_stress_score: Optional[float] = Field(
        None, ge=0, description="Training Stress Score"
    )
    normalized_power: Optional[float] = Field(
        None, ge=0, description="Normalized power in watts"
    )

    # Equipment and device info
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    product: Optional[str] = Field(None, description="Device product name")

    # Nested complex field groups (optional for backwards compatibility)
    power_fields: Optional[PowerFieldsModel] = Field(
        None, description="Power-related metrics"
    )
    running_dynamics: Optional[RunningDynamicsModel] = Field(
        None, description="Running dynamics data"
    )
    cycling_fields: Optional[CyclingFieldsModel] = Field(
        None, description="Cycling-specific data"
    )
    swimming_fields: Optional[SwimmingFieldsModel] = Field(
        None, description="Swimming-specific data"
    )
    environmental: Optional[EnvironmentalModel] = Field(
        None, description="Environmental conditions"
    )
    zone_fields: Optional[ZoneFieldsModel] = Field(
        None, description="Zone-based metrics"
    )

    # Catch-all for additional fields not covered above
    additional_fields: Optional[Dict[str, Any]] = Field(
        None, description="Additional dynamic fields"
    )

    @validator("total_distance")
    def validate_total_distance(cls, v):
        if v is not None and v < 0:
            raise ValueError("total_distance cannot be negative")
        return v

    @validator("avg_heart_rate", "max_heart_rate", "min_heart_rate")
    def validate_heart_rate(cls, v):
        if v is not None and not (30 <= v <= 220):
            raise ValueError("Heart rate must be between 30-220 bpm")
        return v


class RecordModel(BaseActivityModel):
    """
    Record data model - represents real-time data points during activity.

    This model handles second-by-second or high-frequency measurements.
    """

    # Required for records
    sequence: int = Field(..., ge=0, description="Sequence number for ordering")

    # Distance and position
    distance: Optional[float] = Field(
        None, ge=0, description="Cumulative distance in meters"
    )
    position_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Latitude in degrees"
    )
    position_long: Optional[float] = Field(
        None, ge=-180, le=180, description="Longitude in degrees"
    )

    # Optional structured location data
    location: Optional[LocationModel] = Field(None, description="GPS coordinates")

    # Speed and movement
    enhanced_speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    enhanced_altitude: Optional[float] = Field(None, description="Altitude in meters")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    grade: Optional[float] = Field(None, description="Grade/slope percentage")

    # Physiological metrics
    heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Heart rate in bpm"
    )
    cadence: Optional[float] = Field(
        None, ge=0, description="Cadence (steps/min or rpm)"
    )

    # Power metrics
    power: Optional[float] = Field(None, ge=0, description="Power in watts")
    left_power: Optional[float] = Field(
        None, ge=0, description="Left leg/arm power in watts"
    )
    right_power: Optional[float] = Field(
        None, ge=0, description="Right leg/arm power in watts"
    )

    # Environmental conditions
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")

    # Running dynamics (inline for quick access)
    vertical_oscillation: Optional[float] = Field(
        None, ge=0, description="Vertical oscillation in mm"
    )
    stance_time: Optional[float] = Field(
        None, ge=0, description="Ground contact time in ms"
    )
    step_length: Optional[float] = Field(None, ge=0, description="Step length in mm")

    # Cycling-specific
    left_right_balance: Optional[float] = Field(
        None, ge=0, le=100, description="Left/right power balance"
    )
    left_torque_effectiveness: Optional[float] = Field(
        None, ge=0, le=100, description="Left torque effectiveness"
    )
    right_torque_effectiveness: Optional[float] = Field(
        None, ge=0, le=100, description="Right torque effectiveness"
    )

    # Zones
    hr_zone: Optional[int] = Field(
        None, ge=1, le=5, description="Current heart rate zone"
    )
    power_zone: Optional[int] = Field(
        None, ge=1, le=7, description="Current power zone"
    )

    # GPS accuracy and quality
    gps_accuracy: Optional[float] = Field(
        None, ge=0, description="GPS accuracy in meters"
    )

    # Nested complex field groups (optional)
    power_fields: Optional[PowerFieldsModel] = Field(
        None, description="Detailed power metrics"
    )
    running_dynamics: Optional[RunningDynamicsModel] = Field(
        None, description="Detailed running dynamics"
    )
    cycling_fields: Optional[CyclingFieldsModel] = Field(
        None, description="Detailed cycling metrics"
    )
    environmental: Optional[EnvironmentalModel] = Field(
        None, description="Environmental data"
    )

    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(
        None, description="Additional dynamic fields"
    )

    @validator("heart_rate")
    def validate_heart_rate(cls, v):
        if v is not None and not (30 <= v <= 220):
            raise ValueError("Heart rate must be between 30-220 bpm")
        return v

    @validator("position_lat")
    def validate_latitude(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Invalid latitude")
        return v

    @validator("position_long")
    def validate_longitude(cls, v):
        if v is not None and not (-180 <= v <= 180):
            raise ValueError("Invalid longitude")
        return v


class LapModel(BaseActivityModel):
    """
    Lap data model - represents data for activity segments (laps/splits).

    Laps can be triggered manually, by distance, time, or position markers.
    """

    # Required for laps
    lap_number: int = Field(..., ge=1, description="Lap number (starting from 1)")

    # Lap timing
    start_time: Optional[datetime] = Field(None, description="Lap start time")
    total_timer_time: Optional[float] = Field(
        None, ge=0, description="Lap timer time in seconds"
    )
    total_elapsed_time: Optional[float] = Field(
        None, ge=0, description="Lap elapsed time in seconds"
    )

    # Lap distance and position
    total_distance: Optional[float] = Field(
        None, ge=0, description="Lap distance in meters"
    )
    start_position_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Lap start latitude"
    )
    start_position_long: Optional[float] = Field(
        None, ge=-180, le=180, description="Lap start longitude"
    )
    end_position_lat: Optional[float] = Field(
        None, ge=-90, le=90, description="Lap end latitude"
    )
    end_position_long: Optional[float] = Field(
        None, ge=-180, le=180, description="Lap end longitude"
    )

    # Optional structured location data
    start_location: Optional[LocationModel] = Field(
        None, description="Lap start coordinates"
    )
    end_location: Optional[LocationModel] = Field(
        None, description="Lap end coordinates"
    )

    # Speed metrics
    enhanced_avg_speed: Optional[float] = Field(
        None, ge=0, description="Average speed in m/s"
    )
    enhanced_max_speed: Optional[float] = Field(
        None, ge=0, description="Maximum speed in m/s"
    )
    avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")

    # Heart rate metrics
    avg_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Average heart rate in bpm"
    )
    max_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Maximum heart rate in bpm"
    )
    min_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Minimum heart rate in bpm"
    )

    # Power metrics
    avg_power: Optional[float] = Field(None, ge=0, description="Average power in watts")
    max_power: Optional[float] = Field(None, ge=0, description="Maximum power in watts")
    normalized_power: Optional[float] = Field(
        None, ge=0, description="Normalized power in watts"
    )

    # Cadence metrics
    avg_cadence: Optional[float] = Field(None, ge=0, description="Average cadence")
    max_cadence: Optional[float] = Field(None, ge=0, description="Maximum cadence")

    # Elevation metrics
    total_ascent: Optional[float] = Field(
        None, ge=0, description="Total ascent in meters"
    )
    total_descent: Optional[float] = Field(
        None, ge=0, description="Total descent in meters"
    )

    # Calories
    total_calories: Optional[int] = Field(
        None, ge=0, description="Calories burned in lap"
    )

    # Lap trigger information
    lap_trigger: Optional[LapTrigger] = Field(
        None, description="What triggered this lap"
    )
    intensity: Optional[IntensityType] = Field(None, description="Lap intensity level")

    # Sport-specific metrics
    # Running
    avg_vertical_oscillation: Optional[float] = Field(
        None, ge=0, description="Average vertical oscillation"
    )
    avg_stance_time: Optional[float] = Field(
        None, ge=0, description="Average stance time"
    )
    avg_step_length: Optional[float] = Field(
        None, ge=0, description="Average step length"
    )

    # Swimming
    total_strokes: Optional[int] = Field(None, ge=0, description="Total strokes in lap")
    avg_stroke_distance: Optional[float] = Field(
        None, ge=0, description="Average distance per stroke"
    )

    # Nested complex field groups (optional)
    power_fields: Optional[PowerFieldsModel] = Field(
        None, description="Detailed power metrics"
    )
    running_dynamics: Optional[RunningDynamicsModel] = Field(
        None, description="Running dynamics averages"
    )
    cycling_fields: Optional[CyclingFieldsModel] = Field(
        None, description="Cycling-specific metrics"
    )
    swimming_fields: Optional[SwimmingFieldsModel] = Field(
        None, description="Swimming-specific metrics"
    )
    environmental: Optional[EnvironmentalModel] = Field(
        None, description="Environmental conditions"
    )
    zone_fields: Optional[ZoneFieldsModel] = Field(
        None, description="Time in zones for this lap"
    )

    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(
        None, description="Additional dynamic fields"
    )

    @validator("lap_number")
    def validate_lap_number(cls, v):
        if v < 1:
            raise ValueError("lap_number must be positive")
        return v

    @validator("total_distance")
    def validate_total_distance(cls, v):
        if v is not None and v < 0:
            raise ValueError("total_distance cannot be negative")
        return v

    @validator("avg_heart_rate", "max_heart_rate", "min_heart_rate")
    def validate_heart_rate(cls, v):
        if v is not None and not (30 <= v <= 220):
            raise ValueError("Heart rate must be between 30-220 bpm")
        return v


class UserIndicatorModel(BaseActivityModel):
    """
    User indicator/metric model - represents personal metrics and indicators.

    This can include things like body weight, resting heart rate, sleep data, etc.
    """

    # Metric identification
    metric_type: str = Field(
        ..., description="Type of metric (weight, rhr, sleep, etc.)"
    )
    metric_name: str = Field(..., description="Human-readable metric name")

    # Metric value(s)
    value: Union[float, int, str, bool] = Field(..., description="Primary metric value")
    unit: Optional[str] = Field(None, description="Unit of measurement")

    # Additional metric data
    secondary_values: Optional[Dict[str, Union[float, int, str, bool]]] = Field(
        None, description="Additional related values"
    )

    # Context and metadata
    source: Optional[str] = Field(
        None, description="Data source (device, manual entry, etc.)"
    )
    quality_score: Optional[float] = Field(
        None, ge=0, le=1, description="Data quality score (0-1)"
    )
    notes: Optional[str] = Field(None, description="Additional notes or context")

    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(
        None, description="Additional dynamic fields"
    )


class HealthDataModel(BaseModel):
    """
    Health data model for FIT file health metrics - Enhanced implementation.

    Represents raw health data extracted from FIT files including wellness,
    sleep, HRV, and general health metrics using the official Garmin FIT SDK.
    """

    # Core identification fields (required)
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="Timestamp of the health data point")
    message_type: str = Field(..., description="FIT SDK message type")
    
    # Health data classification
    file_type: str = Field(
        default="health_data", description="Health file type (health_data, wellness, sleep_data, hrv_status, metrics)"
    )
    health_category: Optional[str] = Field(
        None, description="Health category (wellness, hrv_data, sleep_data, metrics)"
    )
    
    # Processing metadata
    parsed_at: datetime = Field(..., description="When the data was parsed")
    source_file: Optional[str] = Field(None, description="Source FIT file name")
    sdk_source: str = Field(default="garmin_fit_sdk", description="SDK used for parsing")

    # Device information (common to all health data)
    serial_number: Optional[float] = Field(None, description="Device serial number")
    time_created: Optional[float] = Field(None, description="Device creation timestamp")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    garmin_product: Optional[float] = Field(None, description="Garmin product ID")
    software_version: Optional[float] = Field(None, description="Software version")
    product: Optional[str] = Field(None, description="Product name")
    
    # Timestamp fields from SDK
    local_timestamp: Optional[float] = Field(None, description="Local timestamp")
    timestamp_16: Optional[float] = Field(None, description="16-bit timestamp")
    system_timestamp: Optional[float] = Field(None, description="System timestamp")
    
    # Hardware and battery information
    hardware_version: Optional[str] = Field(None, description="Hardware version")
    battery_voltage: Optional[str] = Field(None, description="Battery voltage")
    battery_status: Optional[str] = Field(None, description="Battery status")

    model_config = ConfigDict(
        extra="allow", validate_assignment=True, str_strip_whitespace=True
    )


class WellnessDataModel(HealthDataModel):
    """
    Wellness data model with proper Garmin FIT SDK fields.

    Enhanced model supporting wellness, monitoring, stress, and body battery data
    from official Garmin FIT SDK message definitions.
    """

    # Override file_type for wellness
    file_type: str = Field(default="wellness", description="Wellness data file type")
    
    # Wellness classification
    health_category: Optional[str] = Field(
        None, description="Health category: wellness, monitoring, stress, body_battery"
    )

    # Stress level fields (from stress_level_mesgs)
    stress_level_value: Optional[float] = Field(
        None, ge=0, le=100, description="Stress level 0-100"
    )
    stress_level_time: Optional[datetime] = Field(
        None, description="Timestamp when stress measured"
    )
    stress_qualifier: Optional[str] = Field(
        None, description="Stress measurement qualifier (calm, low, medium, high)"
    )
    
    # Numeric field IDs from FIT SDK (partially decoded messages)
    field_2: Optional[float] = Field(None, description="Numeric field 2 from FIT")
    field_3: Optional[float] = Field(None, description="Numeric field 3 from FIT")
    field_4: Optional[float] = Field(None, description="Numeric field 4 from FIT")
    field_35: Optional[float] = Field(None, description="Numeric field 35 from FIT")
    field_36: Optional[float] = Field(None, description="Numeric field 36 from FIT")
    field_37: Optional[float] = Field(None, description="Numeric field 37 from FIT")
    field_38: Optional[float] = Field(None, description="Numeric field 38 from FIT")
    field_7: Optional[float] = Field(None, description="Numeric field 7 from FIT")

    # Wellness fields (from wellness_mesgs)
    wellness_value: Optional[float] = Field(
        None, description="General wellness metric value"
    )
    wellness_type: Optional[str] = Field(
        None, description="Type of wellness measurement"
    )

    # Body Battery fields (from body_battery_mesgs)
    body_battery_level: Optional[int] = Field(
        None, ge=0, le=100, description="Current body battery level"
    )
    body_battery_charged: Optional[int] = Field(
        None, ge=0, le=100, description="Body battery charge gained"
    )
    body_battery_drained: Optional[int] = Field(
        None, ge=0, le=100, description="Body battery drain amount"
    )

    # Monitoring fields (from monitoring_mesgs and monitoring_info_mesgs)
    activity_type: Optional[str] = Field(
        None, description="Current activity type"
    )
    activity_subtype: Optional[str] = Field(
        None, description="Activity subtype classification"
    )
    activity_level: Optional[float] = Field(
        None, description="Activity intensity level"
    )
    cycles_to_calories: Optional[float] = Field(
        None, description="Cycles to calories conversion factor"
    )
    cycles_to_distance: Optional[float] = Field(
        None, description="Cycles to distance conversion factor"
    )
    resting_metabolic_rate: Optional[float] = Field(
        None, description="Resting metabolic rate"
    )
    current_day_resting_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Current day resting heart rate"
    )
    
    # Heart rate monitoring
    heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Current heart rate in bpm"
    )
    resting_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Resting heart rate in bpm"
    )
    heart_rate_variability: Optional[float] = Field(
        None, description="Real-time HRV measurement"
    )

    # Respiratory metrics
    respiration_rate: Optional[int] = Field(
        None, ge=0, description="Respiration rate (breaths per minute)"
    )
    pulse_ox: Optional[float] = Field(
        None, ge=0, le=100, description="Pulse oximeter SpO2 percentage"
    )

    # Daily summary fields (from daily_summary_mesgs)
    total_calories: Optional[int] = Field(
        None, ge=0, description="Total calories burned"
    )
    active_calories: Optional[int] = Field(
        None, ge=0, description="Active calories burned"
    )
    bmr_calories: Optional[int] = Field(
        None, ge=0, description="Basal metabolic rate calories"
    )
    steps: Optional[int] = Field(
        None, ge=0, description="Step count"
    )
    distance: Optional[float] = Field(
        None, ge=0, description="Distance traveled (meters)"
    )
    floors_climbed: Optional[int] = Field(
        None, ge=0, description="Floors climbed"
    )
    
    # Activity time breakdowns
    active_time: Optional[float] = Field(
        None, ge=0, description="Total active time in seconds"
    )
    sedentary_time: Optional[float] = Field(
        None, ge=0, description="Sedentary time in seconds"
    )
    sleep_time: Optional[float] = Field(
        None, ge=0, description="Sleep time in seconds"
    )
    
    # Intensity minutes
    moderate_activity_minutes: Optional[int] = Field(
        None, ge=0, description="Moderate intensity activity minutes"
    )
    vigorous_activity_minutes: Optional[int] = Field(
        None, ge=0, description="Vigorous intensity activity minutes"
    )
    
    # Legacy fields (for backward compatibility)
    intensity: Optional[float] = Field(None, description="Activity intensity")
    current_activity_type_intensity: Optional[str] = Field(
        None, description="Activity type intensity"
    )
    cycles: Optional[float] = Field(None, description="Activity cycles")
    ascent: Optional[float] = Field(None, description="Elevation ascent")
    descent: Optional[float] = Field(None, description="Elevation descent")
    duration_min: Optional[float] = Field(None, description="Duration in minutes")
    resting_metabolic_rate: Optional[float] = Field(
        None, description="Resting metabolic rate"
    )
    
    # Body Battery legacy fields
    bb_charged: Optional[int] = Field(
        None, ge=0, le=100, description="Body battery charge level (legacy)"
    )
    bb_max: Optional[int] = Field(
        None, ge=0, le=100, description="Max body battery level (legacy)"
    )
    bb_min: Optional[int] = Field(
        None, ge=0, le=100, description="Min body battery level (legacy)"
    )


class SleepDataModel(HealthDataModel):
    """
    Sleep data model with proper Garmin FIT SDK fields.

    Enhanced model supporting sleep stages, assessments, and quality metrics
    from official Garmin FIT SDK message definitions.
    """

    # Override file_type for sleep
    file_type: str = Field(default="sleep_data", description="Sleep data file type")
    
    # Sleep classification
    health_category: Optional[str] = Field(
        None, description="Sleep category: sleep_data, sleep_assessment, sleep_level"
    )

    # Sleep stage fields (from sleep_level_mesgs)
    sleep_level: Optional[str] = Field(
        None, description="Sleep stage: awake, light, deep, rem"
    )
    sleep_level_value: Optional[int] = Field(
        None, description="Numeric sleep stage value"
    )
    
    # Sleep assessment fields (from sleep_assessment_mesgs)
    combined_awake_score: Optional[int] = Field(
        None, ge=0, le=100, description="Combined awake score (0-100)"
    )
    awake_time_score: Optional[int] = Field(
        None, ge=0, le=100, description="Awake time score (0-100)"
    )
    awakenings_count_score: Optional[int] = Field(
        None, ge=0, le=100, description="Awakenings count score (0-100)"
    )
    deep_sleep_score: Optional[int] = Field(
        None, ge=0, le=100, description="Deep sleep score (0-100)"
    )
    sleep_duration_score: Optional[int] = Field(
        None, ge=0, le=100, description="Sleep duration score (0-100)"
    )
    light_sleep_score: Optional[int] = Field(
        None, ge=0, le=100, description="Light sleep score (0-100)"
    )
    overall_sleep_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall sleep quality score (0-100)"
    )
    sleep_quality_score: Optional[int] = Field(
        None, ge=0, le=100, description="Sleep quality assessment score (0-100)"
    )
    sleep_recovery_score: Optional[int] = Field(
        None, ge=0, le=100, description="Sleep recovery score (0-100)"
    )
    rem_sleep_score: Optional[int] = Field(
        None, ge=0, le=100, description="REM sleep score (0-100)"
    )
    sleep_restlessness_score: Optional[int] = Field(
        None, ge=0, le=100, description="Sleep restlessness score (0-100)"
    )
    awakenings_count: Optional[int] = Field(
        None, ge=0, description="Number of awakenings during sleep"
    )
    interruptions_score: Optional[int] = Field(
        None, ge=0, le=100, description="Sleep interruptions score (0-100)"
    )
    average_stress_during_sleep: Optional[float] = Field(
        None, ge=0, le=100, description="Average stress level during sleep"
    )

    # Sleep duration fields (from sleep_mesgs or sleep_data_mesgs)
    total_sleep_time: Optional[int] = Field(
        None, ge=0, description="Total sleep time in seconds"
    )
    deep_sleep_time: Optional[int] = Field(
        None, ge=0, description="Deep sleep duration in seconds"
    )
    light_sleep_time: Optional[int] = Field(
        None, ge=0, description="Light sleep duration in seconds"
    )
    rem_sleep_time: Optional[int] = Field(
        None, ge=0, description="REM sleep duration in seconds"
    )
    awake_time: Optional[int] = Field(
        None, ge=0, description="Time awake during sleep period in seconds"
    )
    
    # Sleep timing
    sleep_start_time: Optional[datetime] = Field(
        None, description="Sleep start timestamp"
    )
    sleep_end_time: Optional[datetime] = Field(
        None, description="Sleep end timestamp"
    )
    sleep_onset_time: Optional[int] = Field(
        None, ge=0, description="Time to fall asleep in minutes"
    )
    sleep_time: Optional[datetime] = Field(
        None, description="Sleep data timestamp"
    )
    
    # Sleep efficiency and quality
    sleep_efficiency: Optional[float] = Field(
        None, ge=0, le=100, description="Sleep efficiency percentage"
    )
    sleep_score: Optional[int] = Field(
        None, ge=0, le=100, description="Overall sleep score (0-100)"
    )
    
    # Legacy fields (for backward compatibility)
    deep_sleep: Optional[int] = Field(
        None, description="Deep sleep time in seconds (legacy)"
    )
    light_sleep: Optional[int] = Field(
        None, description="Light sleep time in seconds (legacy)"
    )
    rem_sleep: Optional[int] = Field(
        None, description="REM sleep time in seconds (legacy)"
    )
    awake: Optional[int] = Field(
        None, description="Awake time in seconds (legacy)"
    )
    wake_episodes: Optional[int] = Field(
        None, description="Number of wake episodes (legacy)"
    )
    
    # Sleep event data (legacy)
    event: Optional[float] = Field(None, description="Sleep event ID (legacy)")
    event_type: Optional[str] = Field(
        None, description="Sleep event type (start/stop) (legacy)"
    )
    event_group: Optional[str] = Field(
        None, description="Sleep event grouping (legacy)"
    )

    # Device status
    hardware_version: Optional[str] = Field(None, description="Hardware version")
    battery_voltage: Optional[str] = Field(None, description="Battery voltage")
    battery_status: Optional[str] = Field(None, description="Battery status")


class HRVDataModel(HealthDataModel):
    """
    HRV (Heart Rate Variability) data model with proper Garmin FIT SDK fields.

    Enhanced model based on official Garmin FIT SDK field definitions for
    HRV summary, measurements, and beat intervals data.
    """

    # Override file_type for HRV
    file_type: str = Field(default="hrv_status", description="HRV status file type")
    
    # HRV classification (set by health processor)
    hrv_data_type: Optional[str] = Field(
        None, description="HRV data type: summary, measurement, beat_intervals, timeseries"
    )
    
    # Common HRV timing fields
    hrv_time: Optional[datetime] = Field(
        None, description="HRV measurement timestamp"
    )

    # HRV Summary fields (from hrv_status_summary_mesgs)
    weekly_average: Optional[float] = Field(
        None, ge=0, description="7-day RMSSD average over sleep (ms)"
    )
    last_night_average: Optional[float] = Field(
        None, ge=0, description="Previous night's average RMSSD (ms)"
    )
    last_night_5_min_high: Optional[float] = Field(
        None, ge=0, description="Highest 5-minute reading from last night (ms)"
    )
    baseline_low_upper: Optional[float] = Field(
        None, ge=0, description="Upper boundary for low HRV status (ms)"
    )
    baseline_balanced_lower: Optional[float] = Field(
        None, ge=0, description="Lower boundary for balanced HRV status (ms)"
    )
    baseline_balanced_upper: Optional[float] = Field(
        None, ge=0, description="Upper boundary for balanced HRV status (ms)"
    )
    status: Optional[str] = Field(
        None, description="HRV status classification (balanced, low, high)"
    )

    # HRV Measurement fields (from hrv_value_mesgs)
    value: Optional[float] = Field(
        None, ge=0, description="5-minute RMSSD measurement (ms, scaled by 128)"
    )

    # Beat intervals fields (from beat_intervals_mesgs)
    time: Optional[List[int]] = Field(
        None, description="Array of millisecond times between beats"
    )
    timestamp_ms: Optional[int] = Field(
        None, description="Milliseconds past timestamp"
    )

    # Legacy HRV metrics (for backward compatibility)
    rmssd: Optional[float] = Field(
        None, ge=0, description="Root Mean Square of Successive Differences (ms)"
    )
    pnn50: Optional[float] = Field(
        None, ge=0, le=100, description="Percentage of successive NN intervals > 50ms"
    )
    heart_rate_baseline: Optional[int] = Field(
        None, ge=30, le=220, description="Baseline heart rate for HRV (bpm)"
    )

    # Timestamps
    system_timestamp: Optional[float] = Field(None, description="System timestamp")
    local_timestamp: Optional[float] = Field(None, description="Local timestamp")

    # Device status
    hardware_version: Optional[str] = Field(None, description="Hardware version")
    product: Optional[str] = Field(None, description="Product name")
    battery_voltage: Optional[str] = Field(None, description="Battery voltage")
    battery_status: Optional[str] = Field(None, description="Battery status")


class MetricsDataModel(HealthDataModel):
    """
    General health metrics data model for various health measurements.

    Enhanced model supporting METRICS.fit files with numeric message types
    and various fitness and health metrics from Garmin devices.
    """

    # Override file_type for metrics
    file_type: str = Field(default="metrics", description="General metrics file type")

    # Common metric fields (optional for backwards compatibility)
    vo2_max: Optional[float] = Field(None, ge=0, description="VO2 max measurement")
    fitness_age: Optional[int] = Field(None, ge=0, description="Fitness age")
    recovery_time: Optional[float] = Field(
        None, ge=0, description="Recovery time in hours"
    )
    
    # Raw numeric fields from METRICS.fit files (field IDs 0-20)
    field_0: Optional[float] = Field(None, description="Raw field 0 from metrics message")
    field_1: Optional[float] = Field(None, description="Raw field 1 from metrics message")
    field_2: Optional[float] = Field(None, description="Raw field 2 from metrics message")
    field_3: Optional[float] = Field(None, description="Raw field 3 from metrics message")
    field_4: Optional[float] = Field(None, description="Raw field 4 from metrics message")
    field_5: Optional[float] = Field(None, description="Raw field 5 from metrics message")
    field_6: Optional[float] = Field(None, description="Raw field 6 from metrics message")
    field_7: Optional[float] = Field(None, description="Raw field 7 from metrics message")
    field_8: Optional[float] = Field(None, description="Raw field 8 from metrics message")
    field_9: Optional[float] = Field(None, description="Raw field 9 from metrics message")
    field_10: Optional[float] = Field(None, description="Raw field 10 from metrics message")
    field_11: Optional[float] = Field(None, description="Raw field 11 from metrics message")
    field_12: Optional[float] = Field(None, description="Raw field 12 from metrics message")
    field_13: Optional[float] = Field(None, description="Raw field 13 from metrics message")
    field_14: Optional[float] = Field(None, description="Raw field 14 from metrics message")
    field_15: Optional[float] = Field(None, description="Raw field 15 from metrics message")
    field_16: Optional[float] = Field(None, description="Raw field 16 from metrics message")
    field_17: Optional[float] = Field(None, description="Raw field 17 from metrics message")
    field_18: Optional[float] = Field(None, description="Raw field 18 from metrics message")
    field_19: Optional[float] = Field(None, description="Raw field 19 from metrics message")
    field_20: Optional[float] = Field(None, description="Raw field 20 from metrics message")


class MonitoringDataModel(HealthDataModel):
    """
    Monitoring data model for continuous health monitoring from Garmin devices.
    
    Handles monitoring_mesgs and monitoring_info_mesgs from FIT SDK.
    """
    
    # Override file_type for monitoring
    file_type: str = Field(default="monitoring", description="Monitoring data file type")
    
    # Heart rate monitoring
    heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Current heart rate in bpm"
    )
    resting_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Resting heart rate in bpm"
    )
    current_day_resting_heart_rate: Optional[int] = Field(
        None, ge=30, le=220, description="Current day resting heart rate in bpm"
    )
    
    # Activity monitoring
    activity_type: Optional[str] = Field(
        None, description="Current activity type being monitored"
    )
    
    # Conversion factors and metabolic data
    cycles_to_calories: Optional[float] = Field(
        None, description="Cycles to calories conversion factor"
    )
    cycles_to_distance: Optional[float] = Field(
        None, description="Cycles to distance conversion factor"
    )
    resting_metabolic_rate: Optional[float] = Field(
        None, description="Resting metabolic rate"
    )
    
    # Timestamp fields specific to monitoring
    timestamp_16: Optional[float] = Field(
        None, description="16-bit timestamp from monitoring data"
    )


class StressLevelDataModel(HealthDataModel):
    """
    Stress level data model for stress measurements from Garmin devices.
    
    Handles stress_level_mesgs from FIT SDK with proper timestamp extraction.
    """
    
    # Override file_type for stress
    file_type: str = Field(default="stress_level", description="Stress level file type")
    
    # Stress measurement fields
    stress_level_value: Optional[float] = Field(
        None, ge=0, le=100, description="Stress level measurement (0-100)"
    )
    stress_level_time: Optional[datetime] = Field(
        None, description="Timestamp when stress was measured"
    )
    stress_qualifier: Optional[str] = Field(
        None, description="Stress measurement qualifier (calm, low, medium, high)"
    )
    
    # Raw numeric fields from FIT (may contain additional stress data)
    field_2: Optional[float] = Field(None, description="Raw field 2 from stress message")
    field_3: Optional[float] = Field(None, description="Raw field 3 from stress message")
    field_4: Optional[float] = Field(None, description="Raw field 4 from stress message")


# Export all models for easy importing
__all__ = [
    "SessionModel",
    "RecordModel",
    "LapModel",
    "UserIndicatorModel",
    "HealthDataModel",
    "WellnessDataModel",
    "SleepDataModel",
    "HRVDataModel",
    "MetricsDataModel",
    "MonitoringDataModel",
    "StressLevelDataModel",
    "LocationModel",
    "PowerFieldsModel",
    "RunningDynamicsModel",
    "CyclingFieldsModel",
    "SwimmingFieldsModel",
    "EnvironmentalModel",
    "ZoneFieldsModel",
    "SportType",
    "IntensityType",
    "LapTrigger",
]
