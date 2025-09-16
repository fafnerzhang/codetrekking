"""
Data validation utilities for PeakFlow Tasks.

This module provides validation functions for task inputs, configuration,
and data integrity checks.
"""

import re
import os
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json

from pydantic import BaseModel, Field, validator
from pydantic_settings import BaseSettings

from peakflow_tasks.exceptions import ValidationError


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format.
    
    Args:
        user_id: User identifier string
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If user ID is invalid
    """
    if not user_id or not isinstance(user_id, str):
        raise ValidationError("User ID must be a non-empty string")
    
    # Check for valid characters (alphanumeric, underscore, hyphen, dot)
    if not re.match(r'^[a-zA-Z0-9._-]+$', user_id):
        raise ValidationError(
            "User ID must contain only alphanumeric characters, underscores, hyphens, and dots"
        )
    
    # Check length
    if len(user_id) < 3 or len(user_id) > 50:
        raise ValidationError("User ID must be between 3 and 50 characters long")
    
    return True


def validate_date_string(date_str: str, format_str: str = "%Y-%m-%d") -> date:
    """
    Validate and parse date string.
    
    Args:
        date_str: Date string to validate
        format_str: Expected date format
        
    Returns:
        Parsed date object
        
    Raises:
        ValidationError: If date string is invalid
    """
    if not date_str or not isinstance(date_str, str):
        raise ValidationError("Date must be a non-empty string")
    
    try:
        parsed_date = datetime.strptime(date_str, format_str).date()
    except ValueError as e:
        raise ValidationError(f"Invalid date format. Expected {format_str}: {e}")
    
    # Check if date is reasonable (not too far in past or future)
    today = date.today()
    min_date = date(2000, 1, 1)  # Garmin Connect started around 2007
    max_date = date(today.year + 1, 12, 31)  # Allow up to next year
    
    if parsed_date < min_date or parsed_date > max_date:
        raise ValidationError(
            f"Date must be between {min_date} and {max_date}"
        )
    
    return parsed_date


def validate_file_path(file_path: str, must_exist: bool = True, extensions: Optional[List[str]] = None) -> Path:
    """
    Validate file path.
    
    Args:
        file_path: Path to validate
        must_exist: Whether file must exist
        extensions: Allowed file extensions (e.g., ['.fit', '.tcx'])
        
    Returns:
        Path object
        
    Raises:
        ValidationError: If path is invalid
    """
    if not file_path or not isinstance(file_path, str):
        raise ValidationError("File path must be a non-empty string")
    
    path = Path(file_path)
    
    # Check if file exists when required
    if must_exist and not path.exists():
        raise ValidationError(f"File does not exist: {file_path}")
    
    # Check if it's a file (not directory)
    if must_exist and not path.is_file():
        raise ValidationError(f"Path is not a file: {file_path}")
    
    # Check file extension
    if extensions:
        if path.suffix.lower() not in [ext.lower() for ext in extensions]:
            raise ValidationError(
                f"File must have one of these extensions: {extensions}. "
                f"Got: {path.suffix}"
            )
    
    # Check if file is readable when it exists
    if must_exist and not os.access(path, os.R_OK):
        raise ValidationError(f"File is not readable: {file_path}")
    
    return path


def validate_activity_id(activity_id: str) -> bool:
    """
    Validate Garmin activity ID format.
    
    Args:
        activity_id: Activity ID to validate
        
    Returns:
        True if valid
        
    Raises:
        ValidationError: If activity ID is invalid
    """
    if not activity_id or not isinstance(activity_id, str):
        raise ValidationError("Activity ID must be a non-empty string")
    
    # Garmin activity IDs are typically numeric
    if not re.match(r'^\d+$', activity_id):
        raise ValidationError("Activity ID must be numeric")
    
    # Check reasonable length (Garmin IDs are usually 10-15 digits)
    if len(activity_id) < 8 or len(activity_id) > 20:
        raise ValidationError("Activity ID must be between 8 and 20 digits long")
    
    return True


def validate_json_config(config_path: str) -> Dict[str, Any]:
    """
    Validate and load JSON configuration file.
    
    Args:
        config_path: Path to JSON config file
        
    Returns:
        Loaded configuration dictionary
        
    Raises:
        ValidationError: If config is invalid
    """
    path = validate_file_path(config_path, must_exist=True, extensions=['.json'])
    
    try:
        with open(path, 'r') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in config file {config_path}: {e}")
    except IOError as e:
        raise ValidationError(f"Cannot read config file {config_path}: {e}")
    
    if not isinstance(config, dict):
        raise ValidationError("Configuration must be a JSON object")
    
    return config


def validate_garmin_config(user_id: str, config_dir: str = "/storage/garmin") -> bool:
    """
    Validate Garmin configuration for user.
    
    Args:
        user_id: User identifier
        config_dir: Garmin configuration directory
        
    Returns:
        True if configuration is valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    validate_user_id(user_id)
    
    config_path = Path(config_dir) / user_id / "GarminConnectConfig.json"
    
    if not config_path.exists():
        raise ValidationError(f"Garmin configuration not found for user {user_id}")
    
    config = validate_json_config(str(config_path))
    
    # Check required fields
    required_fields = ['username', 'password']
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"Missing required field '{field}' in Garmin config")
    
    return True


def validate_elasticsearch_config(config: Dict[str, Any]) -> bool:
    """
    Validate Elasticsearch configuration.
    
    Args:
        config: Elasticsearch configuration dictionary
        
    Returns:
        True if configuration is valid
        
    Raises:
        ValidationError: If configuration is invalid
    """
    required_fields = ['hosts']
    for field in required_fields:
        if field not in config:
            raise ValidationError(f"Missing required field '{field}' in Elasticsearch config")
    
    # Validate hosts
    hosts = config['hosts']
    if not isinstance(hosts, list) or not hosts:
        raise ValidationError("Elasticsearch hosts must be a non-empty list")
    
    for host in hosts:
        if not isinstance(host, str) or not host:
            raise ValidationError("Each Elasticsearch host must be a non-empty string")
    
    return True


class TaskInputValidator(BaseModel):
    """Base class for task input validation using Pydantic."""
    
    class Config:
        validate_assignment = True
        extra = "forbid"


class GarminDownloadInput(TaskInputValidator):
    """Validation model for Garmin download task inputs."""
    
    user_id: str = Field(..., min_length=3, max_length=50)
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    days: int = Field(..., ge=1, le=365)
    exclude_activity_ids: Optional[List[str]] = Field(default=None)
    overwrite: bool = Field(default=False)
    
    @validator('user_id')
    def validate_user_id(cls, v):
        validate_user_id(v)
        return v
    
    @validator('start_date')
    def validate_start_date(cls, v):
        validate_date_string(v)
        return v
    
    @validator('exclude_activity_ids')
    def validate_activity_ids(cls, v):
        if v is not None:
            for activity_id in v:
                validate_activity_id(activity_id)
        return v


class FitProcessingInput(TaskInputValidator):
    """Validation model for FIT processing task inputs."""
    
    file_path: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=3, max_length=50)
    activity_id: str = Field(..., min_length=8, max_length=20)
    validate_only: bool = Field(default=False)
    
    @validator('file_path')
    def validate_file_path(cls, v):
        validate_file_path(v, must_exist=True, extensions=['.fit'])
        return v
    
    @validator('user_id')
    def validate_user_id(cls, v):
        validate_user_id(v)
        return v
    
    @validator('activity_id')
    def validate_activity_id(cls, v):
        validate_activity_id(v)
        return v


class AnalyticsInput(TaskInputValidator):
    """Validation model for analytics task inputs."""
    
    user_id: str = Field(..., min_length=3, max_length=50)
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    metrics: Optional[List[str]] = Field(default=None)
    
    @validator('user_id')
    def validate_user_id(cls, v):
        validate_user_id(v)
        return v
    
    @validator('start_date', 'end_date')
    def validate_dates(cls, v):
        validate_date_string(v)
        return v
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values:
            start = validate_date_string(values['start_date'])
            end = validate_date_string(v)
            
            if end < start:
                raise ValueError("End date must be after start date")
            
            # Check reasonable range (max 1 year)
            if (end - start).days > 365:
                raise ValueError("Date range cannot exceed 365 days")
        
        return v


def validate_task_input(task_name: str, **kwargs) -> Dict[str, Any]:
    """
    Validate task input based on task name.
    
    Args:
        task_name: Name of the task
        **kwargs: Task input parameters
        
    Returns:
        Validated input dictionary
        
    Raises:
        ValidationError: If input is invalid
    """
    validators = {
        'download_garmin_daily_data': GarminDownloadInput,
        'process_fit_file': FitProcessingInput,
    }
    
    # Extract task name from full task path if needed
    simple_task_name = task_name.split('.')[-1] if '.' in task_name else task_name
    
    if simple_task_name not in validators:
        # No specific validator, just return kwargs
        return kwargs
    
    try:
        validator_class = validators[simple_task_name]
        validated = validator_class(**kwargs)
        return validated.dict()
    except Exception as e:
        raise ValidationError(f"Task input validation failed for {task_name}: {e}")


def validate_storage_indices(storage, required_indices: List[str]) -> bool:
    """
    Validate that required Elasticsearch indices exist.
    
    Args:
        storage: Elasticsearch storage instance
        required_indices: List of required index names
        
    Returns:
        True if all indices exist
        
    Raises:
        ValidationError: If indices are missing
    """
    try:
        if hasattr(storage, 'check_indices'):
            missing_indices = []
            for index in required_indices:
                if not storage.check_indices(index):
                    missing_indices.append(index)
            
            if missing_indices:
                raise ValidationError(f"Missing Elasticsearch indices: {missing_indices}")
        
        return True
    except Exception as e:
        raise ValidationError(f"Cannot validate storage indices: {e}")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to remove dangerous characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace dangerous characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip('. ')
    
    # Ensure filename is not empty
    if not sanitized:
        sanitized = 'unnamed_file'
    
    return sanitized