"""
Task-related models and schemas.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaskType(str, Enum):
    """Types of tasks that can be executed."""

    SETUP_GARMIN_USER = "setup_garmin_user"
    DOWNLOAD_GARMIN_DATA = "download_garmin_data"
    PROCESS_FIT_FILE = "process_fit_file"
    CHECK_EXISTING_DATA = "check_existing_data"
    HEALTH_CHECK = "health_check"


class TaskPriority(str, Enum):
    """Task priority levels."""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class TaskStatus(str, Enum):
    """Task execution status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskMessage(BaseModel):
    """Task message for RabbitMQ."""

    task_id: str = Field(..., description="Unique task identifier")
    task_type: TaskType = Field(..., description="Type of task to execute")
    user_id: str = Field(..., description="User identifier")
    priority: TaskPriority = Field(
        default=TaskPriority.NORMAL, description="Task priority"
    )
    payload: Dict[str, Any] = Field(..., description="Task-specific data")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Task creation time"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted")
    max_retries: int = Field(default=3, description="Maximum number of retries")


class TaskResult(BaseModel):
    """Task execution result."""

    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Task execution status")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result data")
    error: Optional[str] = Field(None, description="Error message if failed")
    started_at: Optional[datetime] = Field(None, description="Task start time")
    completed_at: Optional[datetime] = Field(None, description="Task completion time")
    processing_time_seconds: Optional[float] = Field(
        None, description="Processing time in seconds"
    )
    artifacts: List[Dict[str, Any]] = Field(default=[], description="Result artifacts")


class TaskStorage(BaseModel):
    """Task storage model for database."""

    task_id: str = Field(..., description="Task identifier")
    task_type: TaskType = Field(..., description="Task type")
    user_id: str = Field(..., description="User identifier")
    status: TaskStatus = Field(..., description="Current status")
    priority: TaskPriority = Field(..., description="Task priority")
    payload: Dict[str, Any] = Field(..., description="Task payload")
    result: Optional[Dict[str, Any]] = Field(None, description="Task result")
    error: Optional[str] = Field(None, description="Error message")
    created_at: datetime = Field(..., description="Creation time")
    started_at: Optional[datetime] = Field(None, description="Start time")
    completed_at: Optional[datetime] = Field(None, description="Completion time")
    retry_count: int = Field(default=0, description="Retry count")
    max_retries: int = Field(default=3, description="Max retries")
    worker_id: Optional[str] = Field(None, description="Worker that processed the task")


# Queue Configuration
class QueueConfig(BaseModel):
    """Queue configuration for task routing."""

    queue_name: str = Field(..., description="Queue name")
    exchange: str = Field(..., description="Exchange name")
    routing_key: str = Field(..., description="Routing key")
    priority_levels: List[TaskPriority] = Field(
        default=[TaskPriority.HIGH, TaskPriority.NORMAL, TaskPriority.LOW],
        description="Supported priority levels",
    )
    max_retries: int = Field(default=3, description="Default max retries")
    message_ttl: int = Field(default=3600, description="Message TTL in seconds")


# Task Templates
class GarminSetupTask(BaseModel):
    """Garmin user setup task payload."""

    username: str = Field(..., description="Garmin username")
    password: str = Field(..., description="Garmin password")
    config_options: Dict[str, Any] = Field(
        default_factory=dict, description="Configuration options"
    )


class DownloadTask(BaseModel):
    """Data download task payload."""

    user_id: str = Field(..., description="User identifier")
    start_date: str = Field(..., description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., description="End date (YYYY-MM-DD)")
    data_types: List[str] = Field(..., description="Data types to download")
    overwrite_existing: bool = Field(
        default=False, description="Overwrite existing files"
    )
    exclude_activity_ids: List[str] = Field(
        default=[], description="Activity IDs to exclude"
    )
    check_elasticsearch_before_download: bool = Field(
        default=True, description="Check Elasticsearch before downloading"
    )


class ProcessingTask(BaseModel):
    """FIT file processing task payload."""

    user_id: str = Field(..., description="User identifier")
    fit_file_path: str = Field(..., description="Path to FIT file")
    activity_id: str = Field(..., description="Activity identifier")
    processing_options: Dict[str, Any] = Field(
        default_factory=dict, description="Processing options"
    )
    file_metadata: Optional[Dict[str, Any]] = Field(None, description="File metadata")


# Task Management
class TaskFilter(BaseModel):
    """Task filtering options."""

    user_id: Optional[str] = Field(None, description="Filter by user ID")
    task_type: Optional[TaskType] = Field(None, description="Filter by task type")
    status: Optional[TaskStatus] = Field(None, description="Filter by status")
    priority: Optional[TaskPriority] = Field(None, description="Filter by priority")
    created_after: Optional[datetime] = Field(
        None, description="Created after timestamp"
    )
    created_before: Optional[datetime] = Field(
        None, description="Created before timestamp"
    )


class TaskSummary(BaseModel):
    """Task summary statistics."""

    total_tasks: int = Field(..., description="Total number of tasks")
    by_status: Dict[TaskStatus, int] = Field(..., description="Tasks by status")
    by_type: Dict[TaskType, int] = Field(..., description="Tasks by type")
    by_priority: Dict[TaskPriority, int] = Field(..., description="Tasks by priority")
    avg_processing_time: Optional[float] = Field(
        None, description="Average processing time in seconds"
    )
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")


class TaskBatch(BaseModel):
    """Batch task operations."""

    task_ids: List[str] = Field(..., description="Task IDs in batch")
    operation: str = Field(..., description="Batch operation type")
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="Operation parameters"
    )
