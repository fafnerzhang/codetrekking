#!/usr/bin/env python3
"""
Activity Processor - Processes FIT files for fitness/workout activity data (sessions, laps, records)
"""
import fitparse
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, IO
from pathlib import Path
import time

from ..storage.interface import (
    DataType, QueryFilter, AggregationQuery,
    ValidationError, StorageError
)
from .interface import (
    FitnessFileProcessor, DataSourceType, ProcessingResult, ProcessingStatus,
    ProcessingOptions, DataValidator, DataTransformer,
    UnsupportedFormatError, TransformationError
)
from ..utils import get_logger


logger = get_logger(__name__)


class ActivityFieldMapper:
    """Activity field mapper that handles fitness/workout fields without unknown prefixes/suffixes"""
    
    def __init__(self):
        # Known field prefixes and suffixes that should be preserved
        self.known_prefixes = {
            'enhanced_', 'total_', 'avg_', 'max_', 'min_', 'start_', 'end_',
            'first_', 'last_', 'best_', 'worst_', 'accumulated_', 'left_', 'right_',
            'combined_', 'normalized_', 'functional_', 'threshold_', 'zone_',
            'time_in_', 'percent_', 'raw_', 'filtered_', 'smoothed_'
        }
        
        self.known_suffixes = {
            '_time', '_distance', '_speed', '_pace', '_power', '_heart_rate',
            '_cadence', '_temperature', '_altitude', '_ascent', '_descent',
            '_calories', '_lat', '_long', '_oscillation', '_ratio', '_length',
            '_stiffness', '_data', '_zone', '_threshold', '_effectiveness',
            '_smoothness', '_balance', '_phase', '_peak', '_count', '_accuracy',
            '_grade', '_resistance', '_expenditure', '_uptake', '_stroke',
            '_strokes', '_lengths', '_pool', '_percent', '_pco', '_change',
            '_direction', '_pressure', '_humidity', '_wind', '_air', '_barometric'
        }
        
        # Field categories for better organization
        self.field_categories = {
            'time_fields': ['timestamp', 'start_time', 'total_timer_time', 'total_elapsed_time', 
                           'start_time_in_hr_zones', 'time_in_hr_zone_1', 'time_in_hr_zone_2',
                           'time_in_hr_zone_3', 'time_in_hr_zone_4', 'time_in_hr_zone_5',
                           'time_in_power_zone_1', 'time_in_power_zone_2', 'time_in_power_zone_3',
                           'time_in_power_zone_4', 'time_in_power_zone_5', 'time_in_power_zone_6'],
            'gps_fields': ['position_lat', 'position_long', 'start_position_lat', 'start_position_long',
                          'end_position_lat', 'end_position_long', 'gps_accuracy'],
            'numeric_fields': ['distance', 'speed', 'altitude', 'heart_rate', 'cadence', 'power',
                             'temperature', 'calories', 'ascent', 'descent', 'grade', 'resistance',
                             'energy_expenditure', 'oxygen_uptake', 'treadmill_grade'],
            'categorical_fields': ['sport', 'sub_sport', 'intensity', 'lap_trigger', 'event', 'event_type',
                                 'swim_stroke', 'activity_type', 'manufacturer', 'product'],
            'running_dynamics': ['vertical_oscillation', 'stance_time', 'step_length', 'vertical_ratio',
                                'ground_contact_time', 'form_power', 'leg_spring_stiffness',
                                'stance_time_percent', 'vertical_oscillation_percent',
                                'avg_ground_contact_time', 'avg_vertical_oscillation',
                                'avg_stance_time', 'avg_step_length', 'avg_vertical_ratio'],
            'power_fields': ['power', 'normalized_power', 'left_power', 'right_power', 'left_right_balance',
                           'left_torque_effectiveness', 'right_torque_effectiveness',
                           'left_pedal_smoothness', 'right_pedal_smoothness', 'combined_pedal_smoothness',
                           'functional_threshold_power', 'training_stress_score'],
            'environmental': ['temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction',
                            'air_pressure', 'barometric_pressure'],
            'cycling_fields': ['left_pco', 'right_pco', 'left_power_phase', 'right_power_phase',
                             'left_power_phase_peak', 'right_power_phase_peak', 'gear_change_data'],
            'swimming_fields': ['pool_length', 'lengths', 'stroke_count', 'strokes', 'swolf'],
            'zone_fields': ['hr_zone', 'power_zone', 'pace_zone', 'cadence_zone'],
        }
        
        # Unknown field patterns to exclude
        self.unknown_patterns = [
            r'^unknown_\d+$',           # unknown_123
            r'^field_\d+$',             # field_123  
            r'^data_\d+$',              # data_123
            r'.*_unknown_.*',           # any_unknown_field
            r'.*_\d+_\d+$',            # field_12_34
        ]
    
    def should_include_field(self, field_name: str) -> bool:
        """Determine if a field should be included based on name patterns"""
        import re
        
        # Exclude fields matching unknown patterns
        for pattern in self.unknown_patterns:
            if re.match(pattern, field_name.lower()):
                return False
        
        # Include fields with known prefixes/suffixes
        field_lower = field_name.lower()
        for prefix in self.known_prefixes:
            if field_lower.startswith(prefix.lower()):
                return True
        
        for suffix in self.known_suffixes:
            if field_lower.endswith(suffix.lower()):
                return True
        
        # Include fields that are in known categories
        for category, fields in self.field_categories.items():
            if field_lower in [f.lower() for f in fields]:
                return True
        
        # Include simple alphanumeric field names (no strange patterns)
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', field_name) and len(field_name) <= 50:
            return True
        
        return False
    
    def categorize_field(self, field_name: str) -> str:
        """Categorize a field based on its name"""
        field_lower = field_name.lower()
        
        for category, fields in self.field_categories.items():
            if field_lower in [f.lower() for f in fields]:
                return category
        
        # Check prefixes and suffixes for categorization
        if any(field_lower.startswith(prefix.lower()) for prefix in ['avg_', 'max_', 'min_']):
            if any(field_lower.endswith(suffix.lower()) for suffix in ['_heart_rate', '_hr']):
                return 'heart_rate_metrics'
            elif any(field_lower.endswith(suffix.lower()) for suffix in ['_power']):
                return 'power_fields'
            elif any(field_lower.endswith(suffix.lower()) for suffix in ['_speed', '_pace']):
                return 'speed_metrics'
            elif any(field_lower.endswith(suffix.lower()) for suffix in ['_cadence']):
                return 'cadence_metrics'
            elif any(field_lower.endswith(suffix.lower()) for suffix in ['_temperature']):
                return 'environmental'
        
        # Categorize by suffix patterns
        if any(field_lower.endswith(suffix.lower()) for suffix in ['_oscillation', '_stance', '_contact', '_stiffness']):
            return 'running_dynamics'
        elif any(field_lower.endswith(suffix.lower()) for suffix in ['_power', '_effectiveness', '_smoothness', '_balance']):
            return 'power_fields'
        elif any(field_lower.endswith(suffix.lower()) for suffix in ['_zone']):
            return 'zone_fields'
        elif any(field_lower.endswith(suffix.lower()) for suffix in ['_time']) and 'zone' in field_lower:
            return 'time_fields'
        elif any(field_lower.endswith(suffix.lower()) for suffix in ['_stroke', '_strokes', '_length', '_pool']):
            return 'swimming_fields'
        elif any(field_lower.endswith(suffix.lower()) for suffix in ['_humidity', '_pressure', '_wind', '_air']):
            return 'environmental'
        elif any(field_lower.startswith(prefix.lower()) for prefix in ['left_', 'right_']) and 'power' in field_lower:
            return 'power_fields'
        elif any(field_lower.startswith(prefix.lower()) for prefix in ['left_', 'right_']) and any(x in field_lower for x in ['pco', 'phase']):
            return 'cycling_fields'
        
        return 'general'
    
    def extract_all_fields(self, fit_message, base_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Extract all valid fields from a FIT message"""
        doc = base_doc.copy()
        categorized_fields = {}
        additional_fields = {}
        
        for field in fit_message.fields:
            if field.value is None:
                continue
            
            field_name = field.name
            field_value = field.value
            
            # Skip fields that shouldn't be included
            if not self.should_include_field(field_name):
                continue
            
            # Process different field types
            processed_value = self._process_field_value(field_name, field_value)
            category = self.categorize_field(field_name)
            
            if category in ['time_fields', 'gps_fields', 'numeric_fields', 'categorical_fields']:
                # Direct mapping to document root
                if category == 'time_fields' and hasattr(processed_value, 'isoformat'):
                    doc[field_name] = processed_value.isoformat()
                elif category == 'gps_fields':
                    self._handle_gps_field(doc, field_name, processed_value)
                else:
                    doc[field_name] = processed_value
            elif category == 'general':
                # Store general fields in additional_fields to preserve all valid data
                additional_fields[field_name] = processed_value
            else:
                # Group into categories
                if category not in categorized_fields:
                    categorized_fields[category] = {}
                categorized_fields[category][field_name] = processed_value
        
        # Add categorized fields to document
        for category, fields in categorized_fields.items():
            if fields:  # Only add non-empty categories
                doc[category] = fields
        
        # Add general fields to document root for better accessibility
        if additional_fields:
            doc['additional_fields'] = additional_fields
        
        return doc
    
    def _process_field_value(self, field_name: str, field_value: Any) -> Any:
        """Process field value based on field type"""
        # Handle datetime objects
        if hasattr(field_value, 'isoformat'):
            return field_value
        
        # Handle enum values
        if hasattr(field_value, 'name'):
            return str(field_value)
        
        # Handle numeric values
        if isinstance(field_value, (int, float)):
            return field_value
        
        # Handle string values
        if isinstance(field_value, str):
            return field_value
        
        # Convert other types to string
        return str(field_value)
    
    def _handle_gps_field(self, doc: Dict[str, Any], field_name: str, field_value: Any) -> None:
        """Handle GPS coordinate fields"""
        if 'lat' in field_name.lower():
            location_key = 'location'
            if 'start' in field_name.lower():
                location_key = 'start_location'
            elif 'end' in field_name.lower():
                location_key = 'end_location'
            
            if location_key not in doc:
                doc[location_key] = {}
            
            # Convert from semicircles to degrees if needed
            coord = field_value * (180 / 2**31) if isinstance(field_value, int) and abs(field_value) > 180 else field_value
            doc[location_key]['lat'] = coord
            
        elif 'long' in field_name.lower() or 'lon' in field_name.lower():
            location_key = 'location'
            if 'start' in field_name.lower():
                location_key = 'start_location'
            elif 'end' in field_name.lower():
                location_key = 'end_location'
            
            if location_key not in doc:
                doc[location_key] = {}
            
            # Convert from semicircles to degrees if needed
            coord = field_value * (180 / 2**31) if isinstance(field_value, int) and abs(field_value) > 180 else field_value
            doc[location_key]['lon'] = coord


class ActivityValidator(DataValidator):
    """Activity data validator for fitness/workout data"""
    
    def validate_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate session data"""
        required_fields = ["activity_id", "user_id", "timestamp"]
        
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate numeric ranges
        if "total_distance" in data and data["total_distance"] is not None:
            if data["total_distance"] < 0 or data["total_distance"] > 1000000:  # 1000km
                raise ValidationError("Invalid total_distance value")
        
        if "avg_heart_rate" in data and data["avg_heart_rate"] is not None:
            if data["avg_heart_rate"] < 30 or data["avg_heart_rate"] > 250:
                raise ValidationError("Invalid avg_heart_rate value")
        
        return data
    
    def validate_record_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate record data"""
        required_fields = ["activity_id", "user_id", "timestamp", "sequence"]
        
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")
        
        # Validate GPS coordinates
        if "location" in data and data["location"]:
            lat = data["location"].get("lat")
            lon = data["location"].get("lon")
            if lat is not None and lon is not None:
                if not self.validate_gps_coordinates(lat, lon):
                    raise ValidationError("Invalid GPS coordinates")
        
        # Validate heart rate
        if "heart_rate" in data and data["heart_rate"] is not None:
            if not self.validate_heart_rate(data["heart_rate"]):
                raise ValidationError("Invalid heart_rate value")
        
        return data
    
    def validate_lap_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate lap data"""
        required_fields = ["activity_id", "user_id", "timestamp", "lap_number"]
        
        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")
        
        return data
    
    def validate_gps_coordinates(self, lat: float, lon: float) -> bool:
        """Validate GPS coordinates"""
        return -90 <= lat <= 90 and -180 <= lon <= 180
    
    def validate_heart_rate(self, hr: int, context: Dict[str, Any] = None) -> bool:
        """Validate heart rate data"""
        return 30 <= hr <= 250


class ActivityTransformer(DataTransformer):
    """Activity data transformer for fitness/workout data"""
    
    def transform_coordinates(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Coordinate transformation"""
        if "location" in data and data["location"]:
            # FIT file coordinates need conversion
            lat = data["location"].get("lat")
            lon = data["location"].get("lon")
            
            if lat is not None and isinstance(lat, int):
                data["location"]["lat"] = lat * (180 / 2**31)
            if lon is not None and isinstance(lon, int):
                data["location"]["lon"] = lon * (180 / 2**31)
        
        return data
    
    def normalize_units(self, data: Dict[str, Any], target_system: str = "metric") -> Dict[str, Any]:
        """Unit normalization"""
        # FIT files are usually already in standard units, can add special conversion logic here
        return data
    
    def apply_smoothing(self, data: List[Dict[str, Any]], 
                       fields: List[str], 
                       method: str = "moving_average") -> List[Dict[str, Any]]:
        """Data smoothing"""
        if method == "moving_average":
            window_size = 5
            for field in fields:
                values = [record.get(field) for record in data if record.get(field) is not None]
                if len(values) >= window_size:
                    smoothed_values = []
                    for i in range(len(values)):
                        start_idx = max(0, i - window_size // 2)
                        end_idx = min(len(values), i + window_size // 2 + 1)
                        window_values = values[start_idx:end_idx]
                        smoothed_values.append(sum(window_values) / len(window_values))
                    
                    # Write smoothed values back to data
                    value_idx = 0
                    for i, record in enumerate(data):
                        if record.get(field) is not None:
                            if value_idx < len(smoothed_values):
                                record[f"smoothed_{field}"] = smoothed_values[value_idx]
                                value_idx += 1
        
        return data
    
    def detect_outliers(self, data: List[Dict[str, Any]], 
                       field: str, 
                       method: str = "iqr") -> List[int]:
        """Detect outliers in the data"""
        if not data:
            return []
        
        # Extract field values
        values = []
        indices = []
        for i, record in enumerate(data):
            if record.get(field) is not None:
                try:
                    value = float(record[field])
                    values.append(value)
                    indices.append(i)
                except (ValueError, TypeError):
                    continue
        
        if len(values) < 4:  # Need at least 4 values for IQR
            return []
        
        outlier_indices = []
        
        if method == "iqr":
            # Interquartile Range method
            values_sorted = sorted(values)
            n = len(values_sorted)
            q1 = values_sorted[n // 4]
            q3 = values_sorted[3 * n // 4]
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            for i, value in enumerate(values):
                if value < lower_bound or value > upper_bound:
                    outlier_indices.append(indices[i])
        
        elif method == "zscore":
            # Z-score method
            import statistics
            mean = statistics.mean(values)
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            
            if stdev > 0:
                threshold = 3.0  # 3 standard deviations
                for i, value in enumerate(values):
                    zscore = abs(value - mean) / stdev
                    if zscore > threshold:
                        outlier_indices.append(indices[i])
        
        return outlier_indices


class ActivityProcessor(FitnessFileProcessor):
    """Activity processor for fitness/workout FIT files (sessions, laps, records)"""
    
    def __init__(self, storage, options: Optional[ProcessingOptions] = None):
        super().__init__(storage, options)
        self.validator = ActivityValidator()
        self.transformer = ActivityTransformer()
        self.field_mapper = ActivityFieldMapper()
    
    def process(self, source: Union[str, Path, IO], 
               user_id: str, 
               activity_id: Optional[str] = None) -> ProcessingResult:
        """Process fitness FIT file for activity/workout data"""
        start_time = time.time()
        
        if activity_id is None:
            activity_id = f"activity_{user_id}_{int(datetime.now().timestamp())}"
        
        result = ProcessingResult(
            status=ProcessingStatus.PROCESSING,
            metadata={"activity_id": activity_id, "user_id": user_id}
        )
        
        try:
            # Validate file
            if not self.validate_source(source):
                result.status = ProcessingStatus.FAILED
                result.add_error("Invalid fitness FIT file format")
                return result
            
            # Process fitness FIT file
            if isinstance(source, (str, Path)):
                fit_file_path = str(source)
                if not Path(fit_file_path).exists():
                    result.status = ProcessingStatus.FAILED
                    result.add_error(f"Fitness FIT file not found: {fit_file_path}")
                    return result
                
                fit = fitparse.FitFile(fit_file_path)
            else:
                fit = fitparse.FitFile(source)
            
            # Process different data types
            session_result = self.process_session_data(fit, activity_id, user_id)
            record_result = self.process_record_data(fit, activity_id, user_id)
            lap_result = self.process_lap_data(fit, activity_id, user_id)
            
            # Aggregate results
            result.successful_records = (session_result.successful_records + 
                                       record_result.successful_records + 
                                       lap_result.successful_records)
            result.failed_records = (session_result.failed_records + 
                                   record_result.failed_records + 
                                   lap_result.failed_records)
            result.total_records = result.successful_records + result.failed_records
            result.errors.extend(session_result.errors)
            result.errors.extend(record_result.errors)
            result.errors.extend(lap_result.errors)
            result.warnings.extend(session_result.warnings)
            result.warnings.extend(record_result.warnings)
            
            result.metadata.update({
                "sessions": session_result.successful_records,
                "records": record_result.successful_records,
                "laps": lap_result.successful_records
            })
            
            # Set status
            if result.failed_records == 0:
                result.status = ProcessingStatus.COMPLETED
            elif result.successful_records > 0:
                result.status = ProcessingStatus.PARTIALLY_COMPLETED
            else:
                result.status = ProcessingStatus.FAILED
            
            result.processing_time = time.time() - start_time
            logger.info(f"✅ Fitness FIT file processed: {result.successful_records} successful, {result.failed_records} failed")
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.add_error(f"Fitness FIT file processing failed: {e}")
            result.processing_time = time.time() - start_time
            logger.error(f"❌ Fitness FIT file processing failed: {e}")
        
        return result
    
    def validate_source(self, source: Union[str, Path, IO]) -> bool:
        """Validate fitness FIT file format"""
        try:
            if isinstance(source, (str, Path)):
                if not Path(source).exists():
                    return False
                
                # Check file extension
                if not str(source).lower().endswith('.fit'):
                    return False
                
                # Try to open file
                fit = fitparse.FitFile(str(source))
                # Try to read one message to validate
                try:
                    next(fit.get_messages())
                except StopIteration:
                    # File is valid but empty, which is okay
                    pass
            else:
                fit = fitparse.FitFile(source)
                # Try to read one message to validate
                try:
                    next(fit.get_messages())
                except StopIteration:
                    # File is valid but empty, which is okay
                    pass
            
            return True
        except Exception as e:
            logger.warning(f"Fitness FIT file validation failed: {e}")
            return False
    
    def extract_metadata(self, source: Union[str, Path, IO]) -> Dict[str, Any]:
        """Extract fitness FIT file metadata"""
        metadata = {}
        
        try:
            if isinstance(source, (str, Path)):
                fit = fitparse.FitFile(str(source))
                metadata["file_path"] = str(source)
                metadata["file_size"] = Path(source).stat().st_size
            else:
                fit = fitparse.FitFile(source)
            
            # Extract file information
            file_id_messages = list(fit.get_messages('file_id'))
            if file_id_messages:
                file_id = file_id_messages[0]
                for field in file_id.fields:
                    if field.value is not None:
                        metadata[f"file_{field.name}"] = field.value
            
            # Count message types
            message_counts = {}
            for message in fit.get_messages():
                msg_type = message.name
                message_counts[msg_type] = message_counts.get(msg_type, 0) + 1
            
            metadata["message_counts"] = message_counts
            metadata["extraction_time"] = datetime.now().isoformat()
            
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")
            metadata["extraction_error"] = str(e)
        
        return metadata
    
    def process_session_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process session data"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)
        
        try:
            sessions = list(raw_data.get_messages('session'))
            
            if not sessions:
                result.add_warning("No session data found in FIT file")
                result.status = ProcessingStatus.COMPLETED
                return result
            
            documents = []
            for session in sessions:
                try:
                    doc = self._extract_session_data(session, activity_id, user_id)
                    if doc:
                        validated_doc = self.validator.validate_session_data(doc)
                        validated_doc['_id'] = f"{activity_id}_session"
                        documents.append(validated_doc)
                        result.successful_records += 1
                except (ValidationError, TransformationError) as e:
                    result.add_error(f"Session validation failed: {e}")
                    logger.warning(f"Session validation failed: {e}")
            
            # Bulk indexing
            if documents:
                try:
                    bulk_result = self.storage.bulk_index(DataType.SESSION, documents)
                    if hasattr(bulk_result, 'failed_count') and bulk_result.failed_count > 0:
                        result.failed_records += bulk_result.failed_count
                        result.errors.extend(getattr(bulk_result, 'errors', []))
                except Exception as e:
                    result.add_error(f"Session indexing failed: {e}")
                    logger.error(f"Session indexing failed: {e}")
            
            result.status = ProcessingStatus.COMPLETED
            result.total_records = result.successful_records + result.failed_records
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.add_error(f"Session processing error: {e}")
            logger.error(f"Session processing failed: {e}")
        
        return result
    
    def process_record_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process record data"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)
        
        try:
            records = list(raw_data.get_messages('record'))
            
            if not records:
                result.add_warning("No record data found in FIT file")
                result.status = ProcessingStatus.COMPLETED
                return result
            
            documents = []
            sequence = 0
            
            for record in records:
                try:
                    doc = self._extract_record_data(record, activity_id, user_id, sequence)
                    if doc:
                        validated_doc = self.validator.validate_record_data(doc)
                        validated_doc['_id'] = f"{activity_id}_record_{sequence}"
                        documents.append(validated_doc)
                        result.successful_records += 1
                        sequence += 1
                except (ValidationError, TransformationError) as e:
                    result.add_error(f"Record validation failed: {e}")
                    logger.debug(f"Record validation failed: {e}")
                    sequence += 1
            
            # Batch process large numbers of records
            if documents:
                batch_size = self.options.batch_size
                for i in range(0, len(documents), batch_size):
                    batch = documents[i:i + batch_size]
                    try:
                        bulk_result = self.storage.bulk_index(DataType.RECORD, batch)
                        if hasattr(bulk_result, 'failed_count') and bulk_result.failed_count > 0:
                            result.failed_records += bulk_result.failed_count
                            result.errors.extend(getattr(bulk_result, 'errors', []))
                    except Exception as e:
                        result.add_error(f"Record batch indexing failed: {e}")
                        logger.error(f"Record batch indexing failed: {e}")
            
            result.status = ProcessingStatus.COMPLETED
            result.total_records = result.successful_records + result.failed_records
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.add_error(f"Record processing error: {e}")
            logger.error(f"Record processing failed: {e}")
        
        return result
    
    def process_lap_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process lap data"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)
        
        try:
            laps = list(raw_data.get_messages('lap'))
            
            if not laps:
                result.add_warning("No lap data found in FIT file")
                result.status = ProcessingStatus.COMPLETED
                return result
            
            documents = []
            lap_number = 1
            
            for lap in laps:
                try:
                    doc = self._extract_lap_data(lap, activity_id, user_id, lap_number)
                    if doc:
                        validated_doc = self.validator.validate_lap_data(doc)
                        validated_doc['_id'] = f"{activity_id}_lap_{lap_number}"
                        documents.append(validated_doc)
                        result.successful_records += 1
                        lap_number += 1
                except (ValidationError, TransformationError) as e:
                    result.add_error(f"Lap validation failed: {e}")
                    logger.warning(f"Lap validation failed: {e}")
                    lap_number += 1
            
            # Bulk indexing
            if documents:
                try:
                    bulk_result = self.storage.bulk_index(DataType.LAP, documents)
                    if hasattr(bulk_result, 'failed_count') and bulk_result.failed_count > 0:
                        result.failed_records += bulk_result.failed_count
                        result.errors.extend(getattr(bulk_result, 'errors', []))
                except Exception as e:
                    result.add_error(f"Lap indexing failed: {e}")
                    logger.error(f"Lap indexing failed: {e}")
            
            result.status = ProcessingStatus.COMPLETED
            result.total_records = result.successful_records + result.failed_records
            
        except Exception as e:
            result.status = ProcessingStatus.FAILED
            result.add_error(f"Lap processing error: {e}")
            logger.error(f"Lap processing failed: {e}")
        
        return result
    
    def get_activity_summary(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """Get activity summary"""
        try:
            query_filter = QueryFilter().add_term_filter("activity_id", activity_id)
            results = self.storage.search(DataType.SESSION, query_filter)
            return results[0] if results else None
        except Exception as e:
            logger.error(f"Failed to get activity summary: {e}")
            return None
    
    def get_supported_sports(self) -> List[str]:
        """Get supported sport types"""
        return [
            "running", "cycling", "swimming", "walking", "hiking",
            "mountaineering", "rowing", "elliptical", "tennis",
            "basketball", "soccer", "golf", "yoga", "pilates"
        ]
    
    def get_performance_analytics(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get user performance analytics"""
        try:
            start_date = datetime.now() - timedelta(days=days)
            query_filter = (QueryFilter()
                           .add_term_filter("user_id", user_id)
                           .add_date_range("timestamp", start=start_date))
            
            agg_query = (AggregationQuery()
                        .add_metric("total_activities", "value_count", "activity_id")
                        .add_metric("total_distance", "sum", "total_distance")
                        .add_metric("total_calories", "sum", "total_calories")
                        .add_metric("avg_speed", "avg", "enhanced_avg_speed")
                        .add_metric("avg_heart_rate", "avg", "avg_heart_rate"))
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            return results
        except Exception as e:
            logger.error(f"Failed to get performance analytics: {e}")
            return {}
    
    def search_activities(self, user_id: str, filters: dict = None) -> List[Dict[str, Any]]:
        """Search user activities"""
        try:
            query_filter = QueryFilter().add_term_filter("user_id", user_id)
            
            if filters:
                if "sport" in filters:
                    query_filter.add_term_filter("sport", filters["sport"])
                if "start_date" in filters:
                    query_filter.add_date_range("timestamp", start=filters["start_date"])
                if "end_date" in filters:
                    query_filter.add_date_range("timestamp", end=filters["end_date"])
            
            results = self.storage.search(DataType.SESSION, query_filter)
            return results
        except Exception as e:
            logger.error(f"Failed to search activities: {e}")
            return []
    
    def get_gps_trajectory(self, activity_id: str) -> List[Dict[str, Any]]:
        """Get GPS trajectory for an activity"""
        try:
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .add_sort("sequence", ascending=True)
                           .set_pagination(10000))
            
            records = self.storage.search(DataType.RECORD, query_filter)
            trajectory = []
            
            for record in records:
                if 'location' in record and record['location']:
                    trajectory.append({
                        'timestamp': record.get('timestamp'),
                        'lat': record['location'].get('lat'),
                        'lon': record['location'].get('lon'),
                        'altitude': record.get('altitude'),
                        'speed': record.get('speed'),
                        'heart_rate': record.get('heart_rate')
                    })
            
            return trajectory
        except Exception as e:
            logger.error(f"Failed to get GPS trajectory: {e}")
            return []

    # Data extraction methods remain unchanged, copied from original fit.py...
    def _extract_session_data(self, session, activity_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Extract data from Session message"""
        base_doc = {
            "activity_id": activity_id,
            "user_id": user_id
        }
        
        # Use the comprehensive field mapper to extract all valid fields
        doc = self.field_mapper.extract_all_fields(session, base_doc)
        
        # Ensure we have a timestamp
        return doc if 'timestamp' in doc else None
    
    def _extract_record_data(self, record, activity_id: str, user_id: str, sequence: int) -> Optional[Dict[str, Any]]:
        """Extract data from Record message"""
        base_doc = {
            "activity_id": activity_id,
            "user_id": user_id,
            "sequence": sequence
        }
        
        # Use the comprehensive field mapper to extract all valid fields
        doc = self.field_mapper.extract_all_fields(record, base_doc)
        
        # Ensure we have a timestamp
        return doc if 'timestamp' in doc else None
    
    def _extract_lap_data(self, lap, activity_id: str, user_id: str, lap_number: int) -> Optional[Dict[str, Any]]:
        """Extract data from Lap message"""
        base_doc = {
            "activity_id": activity_id,
            "user_id": user_id,
            "lap_number": lap_number
        }
        
        # Use the comprehensive field mapper to extract all valid fields
        doc = self.field_mapper.extract_all_fields(lap, base_doc)
        
        # Ensure we have a timestamp
        return doc if 'timestamp' in doc else None
