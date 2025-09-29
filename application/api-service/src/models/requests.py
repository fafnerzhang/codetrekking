"""
API request models and schemas.
"""

from datetime import date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, field_validator
from enum import Enum


# Authentication and User Management Models


class UserCreateRequest(BaseModel):
    """Request model for user registration."""

    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, description="Secure password")
    first_name: Optional[str] = Field(
        None, max_length=50, description="User's first name"
    )
    last_name: Optional[str] = Field(
        None, max_length=50, description="User's last name"
    )

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        """Validate username format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )
        return v


class UserUpdateRequest(BaseModel):
    """Request model for user profile updates."""

    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    email: Optional[EmailStr] = None


class LoginRequest(BaseModel):
    """User login request."""

    username: str = Field(..., description="Username or email address")
    password: str = Field(..., description="User password")


class PasswordChangeRequest(BaseModel):
    """Request to change user password."""

    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(..., min_length=8, description="New secure password")


class PasswordResetRequest(BaseModel):
    """Request to initiate password reset."""

    email: EmailStr = Field(..., description="Email address for password reset")


class PasswordResetConfirmRequest(BaseModel):
    """Request to confirm password reset with token."""

    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New secure password")


# Task Management Models


class TaskPriority(str, Enum):
    """Task priority levels."""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class DataType(str, Enum):
    """Garmin data types."""

    ACTIVITIES = "activities"
    SLEEP = "sleep"
    HEALTH = "health"
    MONITORING = "monitoring"


# Analytics types removed


class AggregationLevel(str, Enum):
    """Data aggregation levels."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# User Setup Requests
class GarminSetupRequest(BaseModel):
    """Request to setup Garmin user credentials."""

    username: str = Field(..., description="Garmin Connect username")
    password: str = Field(..., description="Garmin Connect password")
    config_options: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional configuration options"
    )


class ConfigOptions(BaseModel):
    """Garmin user configuration options."""

    data_retention_days: int = Field(default=365, ge=1, le=3650)
    auto_download: bool = Field(default=True)
    preferred_formats: List[str] = Field(default=["fit", "gpx"])


# Data Download Requests
class DateRange(BaseModel):
    """Date range specification."""

    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="End date (YYYY-MM-DD)")


class DownloadRequest(BaseModel):
    """Request to download Garmin data."""

    user_id: str = Field(..., description="User identifier")
    date_range: Optional[DateRange] = Field(None, description="Date range to download")
    start_date: Optional[date] = Field(
        None, description="Start date (alternative to date_range)"
    )
    days: Optional[int] = Field(
        None, ge=1, le=365, description="Number of days from start_date"
    )
    data_types: List[DataType] = Field(
        default=[DataType.ACTIVITIES, DataType.SLEEP, DataType.HEALTH],
        description="Types of data to download",
    )
    overwrite_existing: bool = Field(
        default=False, description="Overwrite existing files"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )


class CompleteSyncRequest(BaseModel):
    """Request to perform complete Garmin sync workflow."""

    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    days: int = Field(..., ge=1, le=365, description="Number of days to sync")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )


# FIT Processing Requests
class ProcessingOptions(BaseModel):
    """FIT file processing options."""

    validate_data: bool = Field(default=True, description="Validate data with Pydantic")
    skip_invalid_records: bool = Field(default=True, description="Skip invalid records")
    check_existing_in_elasticsearch: bool = Field(
        default=True, description="Check if data already exists in Elasticsearch"
    )
    skip_if_exists: bool = Field(
        default=True, description="Skip processing if data exists"
    )
    atomic_operation: bool = Field(
        default=True, description="Ensure atomic file processing"
    )
    process_individually: bool = Field(
        default=True, description="Create separate tasks for each file"
    )
    create_separate_tasks: bool = Field(
        default=True, description="Create individual tasks per activity"
    )


class ProcessFitRequest(BaseModel):
    """Request to process FIT files."""

    user_id: str = Field(..., description="User identifier")
    activity_ids: Optional[List[str]] = Field(
        None, description="Specific activity IDs to process"
    )
    file_paths: Optional[List[str]] = Field(
        None, description="Specific file paths to process"
    )
    processing_options: ProcessingOptions = Field(
        default_factory=ProcessingOptions, description="Processing configuration"
    )
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )


# Analytics Requests
class TimeRange(BaseModel):
    """Time range for analytics."""

    start_date: Optional[date] = Field(None, description="Start date")
    end_date: Optional[date] = Field(None, description="End date")
    days: Optional[int] = Field(
        None, ge=1, le=365, description="Number of days from today"
    )


# AnalyticsRequest removed


# Check Existing Data Requests
class CheckExistingRequest(BaseModel):
    """Request to check existing data in Elasticsearch."""

    user_id: str = Field(..., description="User identifier")
    activity_ids: List[str] = Field(..., description="Activity IDs to check")
    verify_data_completeness: bool = Field(
        default=True, description="Verify data completeness"
    )
    check_processing_status: bool = Field(
        default=True, description="Check processing status"
    )
    include_file_metadata: bool = Field(
        default=True, description="Include file metadata in response"
    )


# Authentication Requests


class TokenRequest(BaseModel):
    """API token request."""

    grant_type: str = Field(default="password", description="Grant type")
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")
    scope: str = Field(default="", description="Token scope")


class APIKeyRequest(BaseModel):
    """API key creation request."""

    name: str = Field(..., description="API key name")
    expires_in_days: Optional[int] = Field(
        default=90, ge=1, le=365, description="Expiration in days"
    )
    scopes: List[str] = Field(default=[], description="API key scopes")


# Garmin Credential Management Requests (Phase 5)


class CreateGarminCredentialsRequest(BaseModel):
    """Request model for creating Garmin credentials."""

    garmin_username: str = Field(
        ..., min_length=1, max_length=255, description="Garmin Connect username"
    )
    garmin_password: str = Field(
        ..., min_length=1, max_length=255, description="Garmin Connect password"
    )


class UpdateGarminCredentialsRequest(BaseModel):
    """Request model for updating Garmin credentials."""

    garmin_username: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Garmin Connect username"
    )
    garmin_password: Optional[str] = Field(
        None, min_length=1, max_length=255, description="Garmin Connect password"
    )


# Zone Method Enums for Analytics
class PowerZoneMethod(str, Enum):
    """Power zone calculation methods."""

    STEVE_PALLADINO = "steve_palladino"
    STRYD_RUNNING = "stryd_running"
    THRESHOLD_POWER = "threshold_power"


class PaceZoneMethod(str, Enum):
    """Pace zone calculation methods."""

    JOE_FRIEL_RUNNING = "joe_friel_running"
    JACK_DANIELS = "jack_daniels"
    PZI = "pzi"


class HeartRateZoneMethod(str, Enum):
    """Heart rate zone calculation methods."""

    JOE_FRIEL = "joe_friel"
    SALLY_EDWARDS = "sally_edwards"
    TIMEX = "timex"


class WeeklyActivitySummaryRequest(BaseModel):
    """Request for weekly activity summary with custom date range and zone methods."""

    start_date: date = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date (YYYY-MM-DD)")
    power_zone_method: PowerZoneMethod = Field(
        default=PowerZoneMethod.STEVE_PALLADINO,
        description="Power zone calculation method"
    )
    pace_zone_method: PaceZoneMethod = Field(
        default=PaceZoneMethod.JOE_FRIEL_RUNNING,
        description="Pace zone calculation method"
    )
    heart_rate_zone_method: HeartRateZoneMethod = Field(
        default=HeartRateZoneMethod.JOE_FRIEL,
        description="Heart rate zone calculation method"
    )


class UserIndicatorsUpdateRequest(BaseModel):
    """Request to update user fitness indicators and thresholds."""

    # Threshold values
    threshold_power: Optional[int] = Field(None, ge=50, le=2000, description="Threshold power in watts")
    threshold_heart_rate: Optional[int] = Field(None, ge=100, le=220, description="Threshold heart rate in BPM")
    threshold_pace: Optional[float] = Field(None, ge=2.0, le=15.0, description="Threshold pace in minutes per km")

    # Max values
    max_heart_rate: Optional[int] = Field(None, ge=120, le=220, description="Maximum heart rate in BPM")
    max_power: Optional[int] = Field(None, ge=100, le=3000, description="Maximum power in watts")
    max_pace: Optional[float] = Field(None, ge=2.0, le=10.0, description="Maximum pace in minutes per km")

    # Critical thresholds (legacy - use threshold_power instead)
    critical_speed: Optional[float] = Field(None, ge=1.0, le=30.0, description="Critical speed in m/s")

    # VO2 and fitness metrics
    vo2max: Optional[float] = Field(None, ge=20.0, le=100.0, description="VO2 max in ml/kg/min")
    vdot: Optional[float] = Field(None, ge=20.0, le=100.0, description="VDOT running performance")

    # Physiological data
    resting_heart_rate: Optional[int] = Field(None, ge=30, le=100, description="Resting heart rate in BPM")
    weight: Optional[float] = Field(None, ge=30.0, le=300.0, description="Body weight in kg")
    height: Optional[float] = Field(None, ge=120.0, le=250.0, description="Height in cm")

    # Personal information
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$", description="Gender")
    birth_date: Optional[date] = Field(None, description="Birth date (YYYY-MM-DD)")
    age: Optional[int] = Field(None, ge=10, le=120, description="Age in years")

    # Body composition
    body_fat_percentage: Optional[float] = Field(None, ge=3.0, le=50.0, description="Body fat percentage")
    muscle_mass: Optional[float] = Field(None, ge=10.0, le=100.0, description="Muscle mass in kg")

    # Training metrics
    training_stress_score: Optional[float] = Field(None, ge=0.0, le=1000.0, description="Current TSS")
    power_to_weight_ratio: Optional[float] = Field(None, ge=1.0, le=10.0, description="Power to weight ratio")

    # Efficiency metrics
    running_economy: Optional[float] = Field(None, ge=100.0, le=300.0, description="Running economy")
    cycling_efficiency: Optional[float] = Field(None, ge=15.0, le=30.0, description="Cycling efficiency percentage")
    stride_length: Optional[float] = Field(None, ge=0.5, le=3.0, description="Stride length in meters")
    cadence: Optional[float] = Field(None, ge=120.0, le=220.0, description="Cadence in steps/min")

    # Health metrics
    hydration_level: Optional[float] = Field(None, ge=50.0, le=100.0, description="Hydration level percentage")
    anaerobic_threshold: Optional[float] = Field(None, ge=100.0, le=220.0, description="Anaerobic threshold heart rate")
    aerobic_threshold: Optional[float] = Field(None, ge=100.0, le=200.0, description="Aerobic threshold heart rate")


class HealthMetricsRequest(BaseModel):
    """Request model for health metrics data within a date range."""

    start_date: date = Field(..., description="Start date for health metrics (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date for health metrics (YYYY-MM-DD)")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        """Validate that end_date is after start_date and within reasonable limits."""
        if info.data and "start_date" in info.data:
            start_date = info.data["start_date"]
            if v < start_date:
                raise ValueError("End date must be after start date")

            # Limit to 30 days max for performance
            days_diff = (v - start_date).days
            if days_diff > 30:
                raise ValueError("Date range cannot exceed 30 days")
                
        return v
