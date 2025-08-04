#!/usr/bin/env python3
"""
Pydantic Data Models for Fitness Activity Data

Provides flexible and extensible models for session, record, and lap data 
that can handle unknown fields gracefully while maintaining validation for core fields.
"""

from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum


class LocationModel(BaseModel):
    """GPS location data model"""
    lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude in degrees")
    lon: Optional[float] = Field(None, ge=-180, le=180, description="Longitude in degrees")
    
    model_config = ConfigDict(extra='allow')


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
    normalized_power: Optional[float] = Field(None, ge=0, description="Normalized power in watts")
    left_power: Optional[float] = Field(None, ge=0, description="Left leg power in watts")
    right_power: Optional[float] = Field(None, ge=0, description="Right leg power in watts")
    left_right_balance: Optional[float] = Field(None, ge=0, le=100, description="Left/right power balance percentage")
    left_torque_effectiveness: Optional[float] = Field(None, ge=0, le=100, description="Left torque effectiveness percentage")
    right_torque_effectiveness: Optional[float] = Field(None, ge=0, le=100, description="Right torque effectiveness percentage")
    left_pedal_smoothness: Optional[float] = Field(None, ge=0, le=100, description="Left pedal smoothness percentage")
    right_pedal_smoothness: Optional[float] = Field(None, ge=0, le=100, description="Right pedal smoothness percentage")
    combined_pedal_smoothness: Optional[float] = Field(None, ge=0, le=100, description="Combined pedal smoothness percentage")
    functional_threshold_power: Optional[float] = Field(None, ge=0, description="FTP in watts")
    training_stress_score: Optional[float] = Field(None, ge=0, description="Training Stress Score")
    
    model_config = ConfigDict(extra='allow')


class RunningDynamicsModel(BaseModel):
    """Running dynamics fields model"""
    vertical_oscillation: Optional[float] = Field(None, ge=0, description="Vertical oscillation in mm")
    stance_time: Optional[float] = Field(None, ge=0, description="Ground contact time in ms")
    step_length: Optional[float] = Field(None, ge=0, description="Step length in mm")
    vertical_ratio: Optional[float] = Field(None, ge=0, description="Vertical ratio percentage")
    ground_contact_time: Optional[float] = Field(None, ge=0, description="Ground contact time in ms")
    form_power: Optional[float] = Field(None, ge=0, description="Form power in watts")
    leg_spring_stiffness: Optional[float] = Field(None, ge=0, description="Leg spring stiffness in kN/m")
    stance_time_percent: Optional[float] = Field(None, ge=0, le=100, description="Stance time percentage")
    vertical_oscillation_percent: Optional[float] = Field(None, ge=0, description="Vertical oscillation percentage")
    
    model_config = ConfigDict(extra='allow')


class CyclingFieldsModel(BaseModel):
    """Cycling-specific fields model"""
    left_pco: Optional[float] = Field(None, description="Left power center offset")
    right_pco: Optional[float] = Field(None, description="Right power center offset")
    left_power_phase: Optional[float] = Field(None, description="Left power phase angle")
    right_power_phase: Optional[float] = Field(None, description="Right power phase angle")
    left_power_phase_peak: Optional[float] = Field(None, description="Left power phase peak angle")
    right_power_phase_peak: Optional[float] = Field(None, description="Right power phase peak angle")
    gear_change_data: Optional[str] = Field(None, description="Gear change information")
    
    model_config = ConfigDict(extra='allow')


class SwimmingFieldsModel(BaseModel):
    """Swimming-specific fields model"""
    pool_length: Optional[float] = Field(None, ge=0, description="Pool length in meters")
    lengths: Optional[int] = Field(None, ge=0, description="Number of pool lengths")
    stroke_count: Optional[int] = Field(None, ge=0, description="Number of strokes")
    strokes: Optional[int] = Field(None, ge=0, description="Total strokes")
    swolf: Optional[int] = Field(None, ge=0, description="SWOLF score (time + strokes)")
    
    model_config = ConfigDict(extra='allow')


class EnvironmentalModel(BaseModel):
    """Environmental conditions model"""
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    humidity: Optional[float] = Field(None, ge=0, le=100, description="Humidity percentage")
    pressure: Optional[float] = Field(None, ge=0, description="Atmospheric pressure")
    wind_speed: Optional[float] = Field(None, ge=0, description="Wind speed")
    wind_direction: Optional[float] = Field(None, ge=0, le=360, description="Wind direction in degrees")
    air_pressure: Optional[float] = Field(None, ge=0, description="Air pressure")
    barometric_pressure: Optional[float] = Field(None, ge=0, description="Barometric pressure")
    
    model_config = ConfigDict(extra='allow')


class ZoneFieldsModel(BaseModel):
    """Zone-related fields model"""
    hr_zone: Optional[int] = Field(None, ge=1, le=5, description="Heart rate zone (1-5)")
    power_zone: Optional[int] = Field(None, ge=1, le=7, description="Power zone (1-7)")
    pace_zone: Optional[int] = Field(None, ge=1, le=5, description="Pace zone (1-5)")
    cadence_zone: Optional[int] = Field(None, ge=1, le=5, description="Cadence zone (1-5)")
    
    # Time in zone fields
    time_in_hr_zone_1: Optional[float] = Field(None, ge=0, description="Time in HR zone 1 (seconds)")
    time_in_hr_zone_2: Optional[float] = Field(None, ge=0, description="Time in HR zone 2 (seconds)")
    time_in_hr_zone_3: Optional[float] = Field(None, ge=0, description="Time in HR zone 3 (seconds)")
    time_in_hr_zone_4: Optional[float] = Field(None, ge=0, description="Time in HR zone 4 (seconds)")
    time_in_hr_zone_5: Optional[float] = Field(None, ge=0, description="Time in HR zone 5 (seconds)")
    
    time_in_power_zone_1: Optional[float] = Field(None, ge=0, description="Time in power zone 1 (seconds)")
    time_in_power_zone_2: Optional[float] = Field(None, ge=0, description="Time in power zone 2 (seconds)")
    time_in_power_zone_3: Optional[float] = Field(None, ge=0, description="Time in power zone 3 (seconds)")
    time_in_power_zone_4: Optional[float] = Field(None, ge=0, description="Time in power zone 4 (seconds)")
    time_in_power_zone_5: Optional[float] = Field(None, ge=0, description="Time in power zone 5 (seconds)")
    time_in_power_zone_6: Optional[float] = Field(None, ge=0, description="Time in power zone 6 (seconds)")
    
    model_config = ConfigDict(extra='allow')


class BaseActivityModel(BaseModel):
    """Base model for all activity data types"""
    # Required core fields
    activity_id: str = Field(..., description="Unique activity identifier")
    user_id: str = Field(..., description="User identifier")
    timestamp: datetime = Field(..., description="Timestamp of the data point")
    
    # Optional ID field for database operations (using alias to avoid underscore)
    doc_id: Optional[str] = Field(None, alias="_id", description="Document ID for storage")
    
    model_config = ConfigDict(
        extra='allow',  # Allow additional fields not defined in the model
        validate_assignment=True,
        str_strip_whitespace=True,
        populate_by_name=True  # Allow both field name and alias
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
    total_timer_time: Optional[float] = Field(None, ge=0, description="Total timer time in seconds")
    total_elapsed_time: Optional[float] = Field(None, ge=0, description="Total elapsed time in seconds")
    total_distance: Optional[float] = Field(None, ge=0, description="Total distance in meters")
    
    # Speed and pace metrics
    enhanced_avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    enhanced_max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")
    avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")
    
    # Heart rate metrics
    avg_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Average heart rate in bpm")
    max_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Maximum heart rate in bpm")
    min_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Minimum heart rate in bpm")
    
    # Calorie and energy metrics
    total_calories: Optional[int] = Field(None, ge=0, description="Total calories burned")
    total_fat_calories: Optional[int] = Field(None, ge=0, description="Fat calories burned")
    
    # Elevation metrics
    total_ascent: Optional[float] = Field(None, ge=0, description="Total ascent in meters")
    total_descent: Optional[float] = Field(None, ge=0, description="Total descent in meters")
    enhanced_avg_altitude: Optional[float] = Field(None, description="Average altitude in meters")
    enhanced_max_altitude: Optional[float] = Field(None, description="Maximum altitude in meters")
    enhanced_min_altitude: Optional[float] = Field(None, description="Minimum altitude in meters")
    
    # Cadence metrics
    avg_cadence: Optional[float] = Field(None, ge=0, description="Average cadence")
    max_cadence: Optional[float] = Field(None, ge=0, description="Maximum cadence")
    
    # Location data
    start_position_lat: Optional[float] = Field(None, ge=-90, le=90, description="Start latitude")
    start_position_long: Optional[float] = Field(None, ge=-180, le=180, description="Start longitude")
    end_position_lat: Optional[float] = Field(None, ge=-90, le=90, description="End latitude")
    end_position_long: Optional[float] = Field(None, ge=-180, le=180, description="End longitude")
    
    # Optional structured location data
    start_location: Optional[LocationModel] = Field(None, description="Start location coordinates")
    end_location: Optional[LocationModel] = Field(None, description="End location coordinates")
    
    # Training metrics
    intensity: Optional[IntensityType] = Field(None, description="Training intensity level")
    training_stress_score: Optional[float] = Field(None, ge=0, description="Training Stress Score")
    normalized_power: Optional[float] = Field(None, ge=0, description="Normalized power in watts")
    
    # Equipment and device info
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    product: Optional[str] = Field(None, description="Device product name")
    
    # Nested complex field groups (optional for backwards compatibility)
    power_fields: Optional[PowerFieldsModel] = Field(None, description="Power-related metrics")
    running_dynamics: Optional[RunningDynamicsModel] = Field(None, description="Running dynamics data")
    cycling_fields: Optional[CyclingFieldsModel] = Field(None, description="Cycling-specific data")
    swimming_fields: Optional[SwimmingFieldsModel] = Field(None, description="Swimming-specific data")
    environmental: Optional[EnvironmentalModel] = Field(None, description="Environmental conditions")
    zone_fields: Optional[ZoneFieldsModel] = Field(None, description="Zone-based metrics")
    
    # Catch-all for additional fields not covered above
    additional_fields: Optional[Dict[str, Any]] = Field(None, description="Additional dynamic fields")
    
    @validator('total_distance')
    def validate_total_distance(cls, v):
        if v is not None and v < 0:
            raise ValueError("total_distance cannot be negative")
        return v
    
    @validator('avg_heart_rate', 'max_heart_rate', 'min_heart_rate')
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
    distance: Optional[float] = Field(None, ge=0, description="Cumulative distance in meters")
    position_lat: Optional[float] = Field(None, ge=-90, le=90, description="Latitude in degrees")
    position_long: Optional[float] = Field(None, ge=-180, le=180, description="Longitude in degrees")
    
    # Optional structured location data
    location: Optional[LocationModel] = Field(None, description="GPS coordinates")
    
    # Speed and movement
    enhanced_speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    enhanced_altitude: Optional[float] = Field(None, description="Altitude in meters")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    grade: Optional[float] = Field(None, description="Grade/slope percentage")
    
    # Physiological metrics
    heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Heart rate in bpm")
    cadence: Optional[float] = Field(None, ge=0, description="Cadence (steps/min or rpm)")
    
    # Power metrics
    power: Optional[float] = Field(None, ge=0, description="Power in watts")
    left_power: Optional[float] = Field(None, ge=0, description="Left leg/arm power in watts")
    right_power: Optional[float] = Field(None, ge=0, description="Right leg/arm power in watts")
    
    # Environmental conditions
    temperature: Optional[float] = Field(None, description="Temperature in Celsius")
    
    # Running dynamics (inline for quick access)
    vertical_oscillation: Optional[float] = Field(None, ge=0, description="Vertical oscillation in mm")
    stance_time: Optional[float] = Field(None, ge=0, description="Ground contact time in ms")
    step_length: Optional[float] = Field(None, ge=0, description="Step length in mm")
    
    # Cycling-specific
    left_right_balance: Optional[float] = Field(None, ge=0, le=100, description="Left/right power balance")
    left_torque_effectiveness: Optional[float] = Field(None, ge=0, le=100, description="Left torque effectiveness")
    right_torque_effectiveness: Optional[float] = Field(None, ge=0, le=100, description="Right torque effectiveness")
    
    # Zones
    hr_zone: Optional[int] = Field(None, ge=1, le=5, description="Current heart rate zone")
    power_zone: Optional[int] = Field(None, ge=1, le=7, description="Current power zone")
    
    # GPS accuracy and quality
    gps_accuracy: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    
    # Nested complex field groups (optional)
    power_fields: Optional[PowerFieldsModel] = Field(None, description="Detailed power metrics")
    running_dynamics: Optional[RunningDynamicsModel] = Field(None, description="Detailed running dynamics")
    cycling_fields: Optional[CyclingFieldsModel] = Field(None, description="Detailed cycling metrics")
    environmental: Optional[EnvironmentalModel] = Field(None, description="Environmental data")
    
    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(None, description="Additional dynamic fields")
    
    @validator('heart_rate')
    def validate_heart_rate(cls, v):
        if v is not None and not (30 <= v <= 220):
            raise ValueError("Heart rate must be between 30-220 bpm")
        return v
    
    @validator('position_lat')
    def validate_latitude(cls, v):
        if v is not None and not (-90 <= v <= 90):
            raise ValueError("Invalid latitude")
        return v
    
    @validator('position_long')
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
    total_timer_time: Optional[float] = Field(None, ge=0, description="Lap timer time in seconds")
    total_elapsed_time: Optional[float] = Field(None, ge=0, description="Lap elapsed time in seconds")
    
    # Lap distance and position
    total_distance: Optional[float] = Field(None, ge=0, description="Lap distance in meters")
    start_position_lat: Optional[float] = Field(None, ge=-90, le=90, description="Lap start latitude")
    start_position_long: Optional[float] = Field(None, ge=-180, le=180, description="Lap start longitude")
    end_position_lat: Optional[float] = Field(None, ge=-90, le=90, description="Lap end latitude")
    end_position_long: Optional[float] = Field(None, ge=-180, le=180, description="Lap end longitude")
    
    # Optional structured location data
    start_location: Optional[LocationModel] = Field(None, description="Lap start coordinates")
    end_location: Optional[LocationModel] = Field(None, description="Lap end coordinates")
    
    # Speed metrics
    enhanced_avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    enhanced_max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")
    avg_speed: Optional[float] = Field(None, ge=0, description="Average speed in m/s")
    max_speed: Optional[float] = Field(None, ge=0, description="Maximum speed in m/s")
    
    # Heart rate metrics
    avg_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Average heart rate in bpm")
    max_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Maximum heart rate in bpm")
    min_heart_rate: Optional[int] = Field(None, ge=30, le=220, description="Minimum heart rate in bpm")
    
    # Power metrics
    avg_power: Optional[float] = Field(None, ge=0, description="Average power in watts")
    max_power: Optional[float] = Field(None, ge=0, description="Maximum power in watts")
    normalized_power: Optional[float] = Field(None, ge=0, description="Normalized power in watts")
    
    # Cadence metrics
    avg_cadence: Optional[float] = Field(None, ge=0, description="Average cadence")
    max_cadence: Optional[float] = Field(None, ge=0, description="Maximum cadence")
    
    # Elevation metrics
    total_ascent: Optional[float] = Field(None, ge=0, description="Total ascent in meters")
    total_descent: Optional[float] = Field(None, ge=0, description="Total descent in meters")
    
    # Calories
    total_calories: Optional[int] = Field(None, ge=0, description="Calories burned in lap")
    
    # Lap trigger information
    lap_trigger: Optional[LapTrigger] = Field(None, description="What triggered this lap")
    intensity: Optional[IntensityType] = Field(None, description="Lap intensity level")
    
    # Sport-specific metrics
    # Running
    avg_vertical_oscillation: Optional[float] = Field(None, ge=0, description="Average vertical oscillation")
    avg_stance_time: Optional[float] = Field(None, ge=0, description="Average stance time")
    avg_step_length: Optional[float] = Field(None, ge=0, description="Average step length")
    
    # Swimming
    total_strokes: Optional[int] = Field(None, ge=0, description="Total strokes in lap")
    avg_stroke_distance: Optional[float] = Field(None, ge=0, description="Average distance per stroke")
    
    # Nested complex field groups (optional)
    power_fields: Optional[PowerFieldsModel] = Field(None, description="Detailed power metrics")
    running_dynamics: Optional[RunningDynamicsModel] = Field(None, description="Running dynamics averages")
    cycling_fields: Optional[CyclingFieldsModel] = Field(None, description="Cycling-specific metrics")
    swimming_fields: Optional[SwimmingFieldsModel] = Field(None, description="Swimming-specific metrics")
    environmental: Optional[EnvironmentalModel] = Field(None, description="Environmental conditions")
    zone_fields: Optional[ZoneFieldsModel] = Field(None, description="Time in zones for this lap")
    
    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(None, description="Additional dynamic fields")
    
    @validator('lap_number')
    def validate_lap_number(cls, v):
        if v < 1:
            raise ValueError("lap_number must be positive")
        return v
    
    @validator('total_distance')
    def validate_total_distance(cls, v):
        if v is not None and v < 0:
            raise ValueError("total_distance cannot be negative")
        return v
    
    @validator('avg_heart_rate', 'max_heart_rate', 'min_heart_rate')
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
    metric_type: str = Field(..., description="Type of metric (weight, rhr, sleep, etc.)")
    metric_name: str = Field(..., description="Human-readable metric name")
    
    # Metric value(s)
    value: Union[float, int, str, bool] = Field(..., description="Primary metric value")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    
    # Additional metric data
    secondary_values: Optional[Dict[str, Union[float, int, str, bool]]] = Field(
        None, description="Additional related values"
    )
    
    # Context and metadata
    source: Optional[str] = Field(None, description="Data source (device, manual entry, etc.)")
    quality_score: Optional[float] = Field(None, ge=0, le=1, description="Data quality score (0-1)")
    notes: Optional[str] = Field(None, description="Additional notes or context")
    
    # Catch-all for additional fields
    additional_fields: Optional[Dict[str, Any]] = Field(None, description="Additional dynamic fields")


# Export all models for easy importing
__all__ = [
    'SessionModel',
    'RecordModel', 
    'LapModel',
    'UserIndicatorModel',
    'LocationModel',
    'PowerFieldsModel',
    'RunningDynamicsModel',
    'CyclingFieldsModel',
    'SwimmingFieldsModel',
    'EnvironmentalModel',
    'ZoneFieldsModel',
    'SportType',
    'IntensityType', 
    'LapTrigger'
]
