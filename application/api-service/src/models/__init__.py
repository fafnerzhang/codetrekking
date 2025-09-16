"""
API models package initialization.
"""

from .requests import (
    GarminSetupRequest,
    DownloadRequest,
    ProcessFitRequest,
    CheckExistingRequest,
    LoginRequest,
    TokenRequest,
    APIKeyRequest,
    TaskPriority,
    DataType,
    AggregationLevel,
)

from .responses import (
    BaseResponse,
    TaskResponse,
    MultiTaskResponse,
    TaskStatusResponse,
    TaskResultResponse,
    GarminSetupResponse,
    DownloadResponse,
    ProcessingResponse,
    CheckExistingResponse,
    TokenResponse,
    APIKeyResponse,
    HealthResponse,
    ErrorResponse,
    TaskStatus,
)

from .tasks import (
    TaskMessage,
    TaskResult,
    TaskStorage,
    TaskType,
    QueueConfig,
    GarminSetupTask,
    DownloadTask,
    ProcessingTask,
    TaskFilter,
    TaskSummary,
    TaskBatch,
)

__all__ = [
    # Request models
    "GarminSetupRequest",
    "DownloadRequest",
    "ProcessFitRequest",
    "AnalyticsRequest",
    "CheckExistingRequest",
    "LoginRequest",
    "TokenRequest",
    "APIKeyRequest",
    # Response models
    "BaseResponse",
    "TaskResponse",
    "MultiTaskResponse",
    "TaskStatusResponse",
    "TaskResultResponse",
    "GarminSetupResponse",
    "DownloadResponse",
    "ProcessingResponse",
    "AnalyticsResponse",
    "CheckExistingResponse",
    "TokenResponse",
    "APIKeyResponse",
    "HealthResponse",
    "ErrorResponse",
    # Task models
    "TaskMessage",
    "TaskResult",
    "TaskStorage",
    "QueueConfig",
    "GarminSetupTask",
    "DownloadTask",
    "ProcessingTask",
    "AnalyticsTask",
    "TaskFilter",
    "TaskSummary",
    "TaskBatch",
    # Enums
    "TaskType",
    "TaskStatus",
    "TaskPriority",
    "DataType",
    "AnalyticsType",
    "AggregationLevel",
]
