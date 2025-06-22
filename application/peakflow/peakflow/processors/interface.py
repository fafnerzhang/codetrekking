#!/usr/bin/env python3
"""
Processors Abstract Interface - Defines standard interfaces for all data processors
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, IO
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from pathlib import Path


class DataSourceType(Enum):
    """Data source type enumeration"""
    FIT_FILE = "fit_file"
    GPX_FILE = "gpx_file"
    TCX_FILE = "tcx_file"
    CSV_FILE = "csv_file"
    JSON_FILE = "json_file"
    API_STREAM = "api_stream"
    DATABASE = "database"


class ProcessingStatus(Enum):
    """Processing status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


@dataclass
class ProcessingOptions:
    """Processing options"""
    validate_data: bool = True
    skip_invalid_records: bool = True
    batch_size: int = 1000
    enable_compression: bool = False
    custom_mappings: Optional[Dict[str, str]] = None
    transformation_rules: Optional[Dict[str, Any]] = None


@dataclass
class ProcessingResult:
    """Processing result"""
    status: ProcessingStatus
    total_records: int = 0
    successful_records: int = 0
    failed_records: int = 0
    errors: List[str] = None
    warnings: List[str] = None
    metadata: Dict[str, Any] = None
    processing_time: Optional[float] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def success_rate(self) -> float:
        """Success rate"""
        if self.total_records == 0:
            return 0.0
        return (self.successful_records / self.total_records) * 100
    
    def add_error(self, error: str):
        """Add error"""
        self.errors.append(error)
        self.failed_records += 1
    
    def add_warning(self, warning: str):
        """Add warning"""
        self.warnings.append(warning)


@dataclass
class ValidationRule:
    """Validation rule"""
    field_name: str
    rule_type: str  # required, range, format, custom
    parameters: Dict[str, Any]
    error_message: Optional[str] = None


class DataProcessor(ABC):
    """Data processor abstract base class"""
    
    def __init__(self, storage, options: Optional[ProcessingOptions] = None):
        self.storage = storage
        self.options = options or ProcessingOptions()
        self.validation_rules: List[ValidationRule] = []
    
    @abstractmethod
    def process(self, source: Union[str, Path, IO], 
               user_id: str, 
               activity_id: Optional[str] = None) -> ProcessingResult:
        """Process data source"""
        pass
    
    @abstractmethod
    def validate_source(self, source: Union[str, Path, IO]) -> bool:
        """Validate data source format"""
        pass
    
    @abstractmethod
    def extract_metadata(self, source: Union[str, Path, IO]) -> Dict[str, Any]:
        """Extract metadata"""
        pass
    
    def add_validation_rule(self, rule: ValidationRule):
        """Add validation rule"""
        self.validation_rules.append(rule)
    
    def remove_validation_rule(self, field_name: str):
        """Remove validation rule"""
        self.validation_rules = [r for r in self.validation_rules if r.field_name != field_name]


class FitnessFileProcessor(DataProcessor):
    """Fitness file processor abstract base class"""
    
    @abstractmethod
    def process_session_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process session data"""
        pass
    
    @abstractmethod
    def process_record_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process record data"""
        pass
    
    @abstractmethod
    def process_lap_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process lap data"""
        pass
    
    @abstractmethod
    def get_activity_summary(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """Get activity summary"""
        pass
    
    @abstractmethod
    def get_supported_sports(self) -> List[str]:
        """Get supported sport types"""
        pass


class StreamProcessor(DataProcessor):
    """Stream data processor abstract base class"""
    
    @abstractmethod
    def process_stream(self, stream: IO, 
                      user_id: str,
                      activity_id: Optional[str] = None,
                      chunk_size: int = 1024) -> ProcessingResult:
        """Process stream data"""
        pass
    
    @abstractmethod
    def handle_real_time_data(self, data_point: Dict[str, Any], 
                            user_id: str, 
                            activity_id: str) -> bool:
        """Handle real-time data point"""
        pass


class BatchProcessor(DataProcessor):
    """Batch processor abstract base class"""
    
    @abstractmethod
    def process_batch(self, sources: List[Union[str, Path]], 
                     user_id: str,
                     parallel: bool = True) -> List[ProcessingResult]:
        """Batch process multiple data sources"""
        pass
    
    @abstractmethod
    def get_processing_status(self, batch_id: str) -> Dict[str, Any]:
        """Get batch processing status"""
        pass


class DataTransformer(ABC):
    """Data transformer abstract base class"""
    
    @abstractmethod
    def transform_coordinates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate transformation"""
        pass
    
    @abstractmethod
    def normalize_units(self, data: Dict[str, Any], target_system: str = "metric") -> Dict[str, Any]:
        """Unit normalization"""
        pass
    
    @abstractmethod
    def apply_smoothing(self, data: List[Dict[str, Any]], 
                       fields: List[str], 
                       method: str = "moving_average") -> List[Dict[str, Any]]:
        """Data smoothing"""
        pass
    
    @abstractmethod
    def detect_outliers(self, data: List[Dict[str, Any]], 
                       field: str, 
                       method: str = "iqr") -> List[int]:
        """Outlier detection"""
        pass


class DataValidator(ABC):
    """Data validator abstract base class"""
    
    @abstractmethod
    def validate_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate session data"""
        pass
    
    @abstractmethod
    def validate_record_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate record data"""
        pass
    
    @abstractmethod
    def validate_lap_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate lap data"""
        pass
    
    @abstractmethod
    def validate_gps_coordinates(self, lat: float, lon: float) -> bool:
        """Validate GPS coordinates"""
        pass
    
    @abstractmethod
    def validate_heart_rate(self, hr: int, context: Dict[str, Any] = None) -> bool:
        """Validate heart rate data"""
        pass


class CompositeProcessor(FitnessFileProcessor, StreamProcessor, BatchProcessor):
    """Composite processor - supports multiple processing modes"""
    
    @abstractmethod
    def auto_detect_format(self, source: Union[str, Path, IO]) -> DataSourceType:
        """Auto-detect data format"""
        pass
    
    @abstractmethod
    def get_processing_statistics(self, user_id: Optional[str] = None, 
                                days: int = 30) -> Dict[str, Any]:
        """Get processing statistics"""
        pass
    
    @abstractmethod
    def cleanup_failed_processing(self, older_than_days: int = 7) -> int:
        """Clean up failed processing records"""
        pass


# Exception classes
class ProcessingError(Exception):
    """Processing error base class"""
    pass


class UnsupportedFormatError(ProcessingError):
    """Unsupported format error"""
    pass


class ValidationError(ProcessingError):
    """Validation error"""
    pass


class TransformationError(ProcessingError):
    """Transformation error"""
    pass


class StorageError(ProcessingError):
    """Storage error"""
    pass
