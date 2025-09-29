"""
API response models and schemas.
"""

from datetime import datetime, date as Date
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from enum import Enum


# Authentication and User Management Response Models


class UserResponse(BaseModel):
    """User profile response model (excludes sensitive data)."""

    id: UUID = Field(..., description="User's unique identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    is_active: bool = Field(..., description="Whether account is active")
    is_verified: bool = Field(..., description="Whether email is verified")
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last profile update timestamp")
    last_login_at: Optional[datetime] = Field(None, description="Last login timestamp")


class RefreshTokenResponse(BaseModel):
    """Token refresh response."""

    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiry in seconds")
    refresh_token: Optional[str] = Field(
        None, description="New refresh token (if rotated)"
    )


class SessionResponse(BaseModel):
    """User session information."""

    id: UUID = Field(..., description="Session identifier")
    device_name: Optional[str] = Field(None, description="Device name")
    ip_address: Optional[str] = Field(None, description="IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    created_at: datetime = Field(..., description="Session creation time")
    last_accessed_at: datetime = Field(..., description="Last access time")
    is_current: bool = Field(..., description="Whether this is the current session")


class APIKeyResponse(BaseModel):
    """API key information response."""

    id: UUID = Field(..., description="API key identifier")
    name: str = Field(..., description="API key name")
    key_prefix: str = Field(..., description="API key prefix (first 8 characters)")
    permissions: List[str] = Field(..., description="Associated permissions")
    created_at: datetime = Field(..., description="Creation timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiry timestamp")


# Task Management Response Models


class TaskStatus(str, Enum):
    """Task execution status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


# Base Response Models
class BaseResponse(BaseModel):
    """Base response model."""

    success: bool = Field(..., description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Response message")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


class TaskResponse(BaseResponse):
    """Response for task creation."""

    task_id: str = Field(..., description="Unique task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time"
    )


class MultiTaskResponse(BaseResponse):
    """Response for multiple task creation."""

    task_ids: List[str] = Field(..., description="List of task identifiers")
    status: TaskStatus = Field(..., description="Initial status for all tasks")
    total_tasks: int = Field(..., description="Total number of tasks created")
    estimated_completion: Optional[datetime] = Field(
        None, description="Estimated completion time for all tasks"
    )


# Task Status and Results
class TaskProgress(BaseModel):
    """Task progress information."""

    current_step: str = Field(..., description="Current processing step")
    progress_percentage: float = Field(
        ..., ge=0, le=100, description="Progress percentage"
    )
    items_processed: int = Field(default=0, description="Number of items processed")
    items_total: int = Field(default=0, description="Total number of items")


class TaskStatusResponse(BaseResponse):
    """Detailed task status response."""

    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Current task status")
    progress: Optional[TaskProgress] = Field(None, description="Task progress details")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    error: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(default=0, description="Number of retries attempted")
    max_retries: int = Field(default=3, description="Maximum number of retries")


class TaskArtifact(BaseModel):
    """Task result artifact."""

    type: str = Field(..., description="Artifact type")
    url: str = Field(..., description="Artifact URL")
    size_bytes: Optional[int] = Field(None, description="Artifact size in bytes")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TaskResultResponse(BaseResponse):
    """Task result response."""

    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Final task status")
    result: Dict[str, Any] = Field(..., description="Task result data")
    artifacts: List[TaskArtifact] = Field(default=[], description="Result artifacts")
    processing_time_seconds: Optional[float] = Field(
        None, description="Total processing time in seconds"
    )
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")


# Garmin Setup Responses
class GarminSetupResponse(TaskResponse):
    """Response for Garmin user setup."""

    user_id: str = Field(..., description="User identifier")
    credential_status: str = Field(..., description="Credential validation status")


# Download Responses
class DownloadEstimate(BaseModel):
    """Download estimation details."""

    estimated_files: int = Field(..., description="Estimated number of files")
    estimated_size_bytes: int = Field(..., description="Estimated total size")
    date_range_days: int = Field(..., description="Number of days in range")


class DownloadResponse(TaskResponse):
    """Response for download request."""

    user_id: str = Field(..., description="User identifier")
    download_estimate: DownloadEstimate = Field(..., description="Download estimation")
    data_types: List[str] = Field(..., description="Data types to download")


# Processing Responses
class ProcessingEstimate(BaseModel):
    """Processing estimation details."""

    files_to_process: int = Field(..., description="Number of files to process")
    estimated_records: int = Field(..., description="Estimated number of records")
    individual_tasks: bool = Field(
        ..., description="Whether files are processed individually"
    )


class ProcessingResponse(MultiTaskResponse):
    """Response for FIT processing request."""

    user_id: str = Field(..., description="User identifier")
    processing_estimate: ProcessingEstimate = Field(
        ..., description="Processing estimation"
    )


# Analytics responses removed


# AnalyticsResponse removed


# Check Existing Data Responses
class FileMetadata(BaseModel):
    """File metadata information."""

    file_size: Optional[int] = Field(None, description="File size in bytes")
    checksum: Optional[str] = Field(None, description="File checksum")
    file_path: Optional[str] = Field(None, description="File path")


class ActivityStatus(BaseModel):
    """Activity data status."""

    activity_id: str = Field(..., description="Activity identifier")
    exists: bool = Field(..., description="Whether activity exists in Elasticsearch")
    data_complete: Optional[bool] = Field(None, description="Whether data is complete")
    processing_status: Optional[str] = Field(None, description="Processing status")
    last_updated: Optional[datetime] = Field(None, description="Last update timestamp")
    file_metadata: Optional[FileMetadata] = Field(None, description="File metadata")


class CheckExistingResponse(BaseResponse):
    """Response for checking existing data."""

    user_id: str = Field(..., description="User identifier")
    total_checked: int = Field(..., description="Total activities checked")
    existing_activities: List[ActivityStatus] = Field(
        ..., description="Status of checked activities"
    )
    exclude_activity_list: List[str] = Field(
        ..., description="Activities that should be excluded from download"
    )
    needs_processing: List[str] = Field(
        ..., description="Activities that need processing"
    )
    response_time_ms: float = Field(..., description="Response time in milliseconds")


# Authentication Responses
class TokenResponse(BaseResponse):
    """Authentication token response."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user information")


class UserInfo(BaseModel):
    """User information."""

    user_id: str = Field(..., description="User identifier")
    username: str = Field(..., description="Username")
    email: Optional[str] = Field(None, description="Email address")
    created_at: datetime = Field(..., description="Account creation time")
    last_login: Optional[datetime] = Field(None, description="Last login time")


class APIKeyInfo(BaseModel):
    """API key information."""

    key_id: str = Field(..., description="API key identifier")
    name: str = Field(..., description="API key name")
    created_at: datetime = Field(..., description="Creation time")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")
    last_used: Optional[datetime] = Field(None, description="Last usage time")
    scopes: List[str] = Field(default=[], description="API key scopes")




# Health and System Responses
class ComponentHealth(BaseModel):
    """Component health status."""

    name: str = Field(..., description="Component name")
    status: str = Field(..., description="Component status")
    last_check: datetime = Field(..., description="Last health check time")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class HealthResponse(BaseResponse):
    """System health response."""

    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="Service version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    components: List[ComponentHealth] = Field(
        ..., description="Component health status"
    )


# Error Responses
class ErrorDetail(BaseModel):
    """Error detail information."""

    type: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    field: Optional[str] = Field(None, description="Field that caused the error")
    code: Optional[str] = Field(None, description="Error code")


class ErrorResponse(BaseResponse):
    """Error response model."""

    success: bool = Field(default=False, description="Always false for errors")
    error_type: str = Field(..., description="Error type")
    error_code: Optional[int] = Field(None, description="Error code")
    details: List[ErrorDetail] = Field(default=[], description="Error details")
    request_id: Optional[str] = Field(
        None, description="Request identifier for debugging"
    )


# Pagination
class PaginationInfo(BaseModel):
    """Pagination information."""

    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=1000, description="Items per page")
    total_items: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class PaginatedResponse(BaseResponse):
    """Paginated response base."""

    pagination: PaginationInfo = Field(..., description="Pagination information")
    items: List[Any] = Field(..., description="Page items")


# Garmin Credential Management Responses (Phase 5)


class GarminCredentialResponse(BaseModel):
    """Response model for Garmin credential operations."""

    user_id: UUID = Field(..., description="User identifier")
    garmin_username: str = Field(..., description="Garmin Connect username")
    has_credentials: bool = Field(
        ..., description="Whether user has stored credentials"
    )
    created_at: Optional[datetime] = Field(
        None, description="Credential creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None, description="Last credential update timestamp"
    )
    last_tested: Optional[datetime] = Field(
        None, description="Last credential test timestamp"
    )
    test_status: Optional[str] = Field(
        None, description="Last test result (success, failed, pending)"
    )


class GarminCredentialTestResponse(BaseModel):
    """Response model for Garmin credential testing."""

    success: bool = Field(..., description="Test result")
    message: str = Field(..., description="Test result message")
    test_timestamp: datetime = Field(..., description="When the test was performed")
    error_details: Optional[str] = Field(
        None, description="Error details if test failed"
    )


# Analytics Response Models


class ZoneDistribution(BaseModel):
    """Zone distribution with both time and percentage."""

    zone_1_seconds: int = Field(default=0, description="Time in zone 1 (seconds)")
    zone_1_percentage: float = Field(default=0.0, description="Percentage of time in zone 1")
    zone_2_seconds: int = Field(default=0, description="Time in zone 2 (seconds)")
    zone_2_percentage: float = Field(default=0.0, description="Percentage of time in zone 2")
    zone_3_seconds: int = Field(default=0, description="Time in zone 3 (seconds)")
    zone_3_percentage: float = Field(default=0.0, description="Percentage of time in zone 3")
    zone_4_seconds: int = Field(default=0, description="Time in zone 4 (seconds)")
    zone_4_percentage: float = Field(default=0.0, description="Percentage of time in zone 4")
    zone_5_seconds: int = Field(default=0, description="Time in zone 5 (seconds)")
    zone_5_percentage: float = Field(default=0.0, description="Percentage of time in zone 5")
    zone_6_seconds: int = Field(default=0, description="Time in zone 6 (seconds)")
    zone_6_percentage: float = Field(default=0.0, description="Percentage of time in zone 6")
    zone_7_seconds: int = Field(default=0, description="Time in zone 7 (seconds)")
    zone_7_percentage: float = Field(default=0.0, description="Percentage of time in zone 7")


class ZoneDefinition(BaseModel):
    """Zone definition with descriptive information."""
    zone_number: int = Field(..., description="Zone number")
    zone_name: str = Field(..., description="Zone name")
    range_min: float = Field(..., description="Zone minimum value")
    range_max: float = Field(..., description="Zone maximum value")
    range_unit: str = Field(..., description="Unit of measurement (watts, min/km, bpm)")
    percentage_min: Optional[float] = Field(None, description="Minimum percentage of threshold")
    percentage_max: Optional[float] = Field(None, description="Maximum percentage of threshold")
    description: str = Field(default="", description="Zone description")
    purpose: str = Field(default="", description="Training purpose")
    benefits: List[str] = Field(default_factory=list, description="Training benefits")
    duration_guidance: str = Field(default="", description="Recommended duration")
    intensity_feel: str = Field(default="", description="Subjective intensity feel")
    seconds: int = Field(default=0, description="Time spent in this zone (seconds)")
    percentage: float = Field(default=0.0, description="Percentage of total time in this zone")


class ZonesWithDefinitions(BaseModel):
    """Zone data with both definitions and time distributions."""
    zones: List[ZoneDefinition] = Field(default_factory=list, description="Zone definitions and time data")
    method: str = Field(..., description="Calculation method used")
    method_description: Optional[str] = Field(None, description="Description of the calculation method")
    threshold_value: Optional[float] = Field(None, description="Threshold value used for calculations")
    threshold_unit: Optional[str] = Field(None, description="Unit of threshold value")


class ZonePercentage(BaseModel):
    """Power/pace zone percentage breakdown (legacy for compatibility)."""

    zone_1: float = Field(..., description="Percentage of time in zone 1")
    zone_2: float = Field(..., description="Percentage of time in zone 2")
    zone_3: float = Field(..., description="Percentage of time in zone 3")
    zone_4: float = Field(..., description="Percentage of time in zone 4")
    zone_5: float = Field(..., description="Percentage of time in zone 5")


class HealthMetrics(BaseModel):
    """Health metrics summary."""

    avg_hrv: Optional[float] = Field(None, description="Average HRV")
    avg_resting_heart_rate: Optional[int] = Field(None, description="Average resting heart rate")
    avg_health_score: Optional[float] = Field(None, description="Average health score")
    stress_score: Optional[float] = Field(None, description="Average stress score")
    sleep_score: Optional[float] = Field(None, description="Average sleep score")


class WeeklyActivitySummary(BaseModel):
    """Enhanced activity summary response with multi-zone analysis."""

    user_id: str = Field(..., description="User identifier")
    total_distance: float = Field(..., description="Total distance in km")
    total_tss: float = Field(..., description="Total Training Stress Score")
    total_time: str = Field(..., description="Total activity time (HH:MM format)")
    activity_count: int = Field(..., description="Number of activities")

    # Legacy zone distributions for backward compatibility
    power_zone_distribution: ZoneDistribution = Field(..., description="Power zone distribution")
    pace_zone_distribution: ZoneDistribution = Field(..., description="Pace zone distribution")
    heart_rate_zone_distribution: ZoneDistribution = Field(..., description="Heart rate zone distribution")

    # Enhanced zone definitions with descriptions
    power_zones: ZonesWithDefinitions = Field(..., description="Power zones with definitions")
    pace_zones: ZonesWithDefinitions = Field(..., description="Pace zones with definitions")
    heart_rate_zones: ZonesWithDefinitions = Field(..., description="Heart rate zones with definitions")

    date_range: Dict[str, str] = Field(..., description="Date range of data")
    zone_methods: Dict[str, str] = Field(..., description="Zone calculation methods used")


class LapData(BaseModel):
    """Single lap data."""

    lap_number: int = Field(..., description="Lap number")
    distance: float = Field(..., description="Lap distance in km")
    time: int = Field(..., description="Lap time in seconds")
    avg_power: Optional[float] = Field(None, description="Average power in watts")
    avg_pace: Optional[float] = Field(None, description="Average pace in min/km")
    avg_heart_rate: Optional[int] = Field(None, description="Average heart rate")
    zone: Optional[int] = Field(None, description="Primary zone for this lap")


class UserIndicatorsResponse(BaseModel):
    """User fitness indicators response."""

    user_id: str = Field(..., description="User identifier")
    updated_at: datetime = Field(..., description="Last update timestamp")

    # Threshold values
    threshold_power: Optional[int] = Field(None, description="Threshold power in watts")
    threshold_heart_rate: Optional[int] = Field(None, description="Threshold heart rate in BPM")
    threshold_pace: Optional[float] = Field(None, description="Threshold pace in minutes per km")

    # Max values
    max_heart_rate: Optional[int] = Field(None, description="Maximum heart rate in BPM")
    max_power: Optional[int] = Field(None, description="Maximum power in watts")
    max_pace: Optional[float] = Field(None, description="Maximum pace in minutes per km")

    # Critical thresholds (legacy - use threshold_power instead)
    critical_speed: Optional[float] = Field(None, description="Critical speed in m/s")

    # VO2 and fitness metrics
    vo2max: Optional[float] = Field(None, description="VO2 max in ml/kg/min")
    vdot: Optional[float] = Field(None, description="VDOT running performance")

    # Physiological data
    resting_heart_rate: Optional[int] = Field(None, description="Resting heart rate in BPM")
    weight: Optional[float] = Field(None, description="Body weight in kg")
    height: Optional[float] = Field(None, description="Height in cm")

    # Personal information
    gender: Optional[str] = Field(None, description="Gender")
    birth_date: Optional[Date] = Field(None, description="Birth date")
    age: Optional[int] = Field(None, description="Age in years")

    # Body composition
    body_fat_percentage: Optional[float] = Field(None, description="Body fat percentage")
    muscle_mass: Optional[float] = Field(None, description="Muscle mass in kg")

    # Training metrics
    training_stress_score: Optional[float] = Field(None, description="Current TSS")
    power_to_weight_ratio: Optional[float] = Field(None, description="Power to weight ratio")

    # Efficiency metrics
    running_economy: Optional[float] = Field(None, description="Running economy")
    cycling_efficiency: Optional[float] = Field(None, description="Cycling efficiency percentage")
    stride_length: Optional[float] = Field(None, description="Stride length in meters")
    cadence: Optional[float] = Field(None, description="Cadence in steps/min")

    # Health metrics
    hydration_level: Optional[float] = Field(None, description="Hydration level percentage")
    anaerobic_threshold: Optional[float] = Field(None, description="Anaerobic threshold heart rate")
    aerobic_threshold: Optional[float] = Field(None, description="Aerobic threshold heart rate")


# Health Metrics Response Models


class DailyHealthMetrics(BaseModel):
    """Daily health metrics summary."""

    date: Date = Field(..., description="Date for this day's metrics")
    
    # HRV metrics
    hrv_rmssd_avg: Optional[float] = Field(None, description="Average HRV RMSSD for the day (ms)")
    hrv_rmssd_night_avg: Optional[float] = Field(None, description="Average HRV RMSSD during night hours (ms)")
    hrv_rmssd_min: Optional[float] = Field(None, description="Minimum HRV RMSSD for the day (ms)")
    hrv_rmssd_max: Optional[float] = Field(None, description="Maximum HRV RMSSD for the day (ms)")
    hrv_data_points: int = Field(default=0, description="Number of HRV data points for the day")
    hrv_night_data_points: int = Field(default=0, description="Number of HRV data points during night hours")
    
    # Heart rate metrics
    resting_hr_avg: Optional[float] = Field(None, description="Average resting heart rate for the day (BPM)")
    resting_hr_night_avg: Optional[float] = Field(None, description="Average resting heart rate during night hours (BPM)")
    resting_hr_min: Optional[float] = Field(None, description="Minimum resting heart rate for the day (BPM)")
    resting_hr_max: Optional[float] = Field(None, description="Maximum resting heart rate for the day (BPM)")
    hr_data_points: int = Field(default=0, description="Number of heart rate data points for the day")
    hr_night_data_points: int = Field(default=0, description="Number of heart rate data points during night hours")
    
    # Battery/Device status
    battery_level_avg: Optional[float] = Field(None, description="Average battery level for the day (%)")
    battery_level_min: Optional[float] = Field(None, description="Minimum battery level for the day (%)")
    battery_level_max: Optional[float] = Field(None, description="Maximum battery level for the day (%)")
    battery_data_points: int = Field(default=0, description="Number of battery data points for the day")
    
    # Stress metrics (if available)
    stress_score_avg: Optional[float] = Field(None, description="Average stress score for the day (0-100)")
    stress_score_night_avg: Optional[float] = Field(None, description="Average stress score during night hours (0-100)")


class HealthMetricsSummary(BaseModel):
    """Overall health metrics summary for the requested period."""

    # Period summary
    start_date: Date = Field(..., description="Start date of the period")
    end_date: Date = Field(..., description="End date of the period")
    total_days: int = Field(..., description="Total number of days in the period")
    
    # Overall HRV metrics
    avg_hrv_rmssd: Optional[float] = Field(None, description="Average HRV RMSSD for the entire period (ms)")
    avg_hrv_rmssd_night: Optional[float] = Field(None, description="Average HRV RMSSD during night hours for the entire period (ms)")
    hrv_trend: Optional[str] = Field(None, description="HRV trend over the period (improving/stable/declining)")
    total_hrv_measurements: int = Field(default=0, description="Total HRV measurements in the period")
    total_hrv_night_measurements: int = Field(default=0, description="Total HRV measurements during night hours")
    
    # Overall heart rate metrics
    avg_resting_hr: Optional[float] = Field(None, description="Average resting heart rate for the entire period (BPM)")
    avg_resting_hr_night: Optional[float] = Field(None, description="Average resting heart rate during night hours for the entire period (BPM)")
    hr_trend: Optional[str] = Field(None, description="Heart rate trend over the period (improving/stable/declining)")
    total_hr_measurements: int = Field(default=0, description="Total heart rate measurements in the period")
    total_hr_night_measurements: int = Field(default=0, description="Total heart rate measurements during night hours")
    
    # Overall battery metrics
    avg_battery_level: Optional[float] = Field(None, description="Average battery level for the entire period (%)")
    battery_trend: Optional[str] = Field(None, description="Battery trend over the period (stable/declining)")
    total_battery_measurements: int = Field(default=0, description="Total battery measurements in the period")


class HealthMetricsResponse(BaseModel):
    """Complete health metrics response."""

    user_id: str = Field(..., description="User identifier")
    summary: HealthMetricsSummary = Field(..., description="Overall period summary")
    daily_metrics: List[DailyHealthMetrics] = Field(..., description="Daily breakdown of health metrics")
    
    # Metadata
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="When this report was generated")
    timezone: str = Field(default="Asia/Taipei", description="Timezone used for night period calculations")
    night_hours: str = Field(default="23:00-06:00", description="Hours considered as night period")


# Workout TSS Response Models


class WorkoutSegmentTSS(BaseModel):
    """TSS estimate for a single workout segment."""

    duration_minutes: float = Field(..., description="Segment duration in minutes")
    intensity_metric: str = Field(..., description="Type of intensity metric (power, heart_rate, pace)")
    target_value: float = Field(..., description="Target intensity value")
    target_formatted: str = Field(..., description="Human-readable target (e.g., '4:30' for pace)")
    estimated_tss: float = Field(..., description="Estimated TSS for this segment")
    intensity_factor: float = Field(..., description="Intensity factor relative to threshold")


class WorkoutTSSEstimate(BaseModel):
    """Complete workout TSS estimation response."""

    estimated_tss: float = Field(..., description="Total estimated TSS for the workout")
    total_duration_minutes: float = Field(..., description="Total workout duration in minutes")
    total_duration_hours: float = Field(..., description="Total workout duration in hours")
    segment_count: int = Field(..., description="Number of workout segments")
    primary_method: str = Field(..., description="Primary TSS calculation method (power/heart_rate/pace)")
    segments: List[WorkoutSegmentTSS] = Field(..., description="TSS breakdown by segment")
    thresholds_used: Dict[str, Any] = Field(..., description="Threshold values used in calculation")
    calculation_method: str = Field(..., description="Calculation method identifier")
    estimated_at: datetime = Field(..., description="When the estimate was calculated")
