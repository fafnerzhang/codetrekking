#!/usr/bin/env python3
"""
Activity Processor - Processes FIT files for fitness/workout activity data (sessions, laps, records)
"""
import re
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, IO
from pathlib import Path
import time

# Import garmin_fit_sdk only
try:
    from garmin_fit_sdk import Decoder, Stream
    GARMIN_FIT_SDK_AVAILABLE = True
except ImportError:
    GARMIN_FIT_SDK_AVAILABLE = False
    raise ImportError("garmin_fit_sdk is required. Install with: uv add garmin-fit-sdk")

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
            'time_in_', 'percent_', 'raw_', 'filtered_', 'smoothed_',
            # Environmental prefixes discovered in the data
            'baseline_', 'stryd_', 'air_'
        }
        
        self.known_suffixes = {
            '_time', '_distance', '_speed', '_pace', '_power', '_heart_rate',
            '_cadence', '_temperature', '_altitude', '_ascent', '_descent',
            '_calories', '_lat', '_long', '_oscillation', '_ratio', '_length',
            '_stiffness', '_data', '_zone', '_threshold', '_effectiveness',
            '_smoothness', '_balance', '_phase', '_peak', '_count', '_accuracy',
            '_grade', '_resistance', '_expenditure', '_uptake', '_stroke',
            '_strokes', '_lengths', '_pool', '_percent', '_pco', '_change',
            '_direction', '_pressure', '_humidity', '_wind', '_air', '_barometric',
            # Environmental suffixes
            '_elevation'
        }
        
        # Specific environmental field names discovered in the data
        self.environmental_field_names = {
            # Direct field name mappings (case-insensitive)
            'baseline temperature': 'baseline_temperature',
            'baseline humidity': 'baseline_humidity', 
            'baseline elevation': 'baseline_elevation',
            'air power': 'air_power',
            'stryd temperature': 'stryd_temperature',
            'stryd humidity': 'stryd_humidity',
            'avg_temperature': 'avg_temperature',
            'max_temperature': 'max_temperature',
            'min_temperature': 'min_temperature',
            'temperature': 'temperature',
            'humidity': 'humidity',
            'pressure': 'pressure',
            'wind_speed': 'wind_speed',
            'wind_direction': 'wind_direction',
            'barometric_pressure': 'barometric_pressure',
            'air_pressure': 'air_pressure'
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
            'running_dynamics': [
                # Standard Garmin running dynamics
                'vertical_oscillation', 'stance_time', 'step_length', 'vertical_ratio',
                'ground_contact_time', 'stance_time_percent', 'vertical_oscillation_percent',
                'avg_ground_contact_time', 'avg_vertical_oscillation',
                'avg_stance_time', 'avg_step_length', 'avg_vertical_ratio',
                # Stryd running dynamics and biomechanics
                'ground_time', 'impact_loading_rate', 'leg_spring_stiffness',
                'duty_factor', 'flight_time', 'form_power',
                # Advanced cadence and efficiency metrics
                'cadence', 'step_frequency', 'stride_frequency',
                # Gait and efficiency ratios
                'vertical_ratio', 'form_power_ratio',
                # Additional biomechanical metrics
                'ground_contact_balance', 'left_right_balance', 'efficiency_score'
            ],
            'power_fields': ['power', 'normalized_power', 'left_power', 'right_power', 'left_right_balance',
                           'left_torque_effectiveness', 'right_torque_effectiveness',
                           'left_pedal_smoothness', 'right_pedal_smoothness', 'combined_pedal_smoothness',
                           'functional_threshold_power', 'training_stress_score', 'air_power',
                           # Developer power fields (using original FIT field names)
                           'cp', 'form_power', 'lap_power'],
            'environmental': [
                # Standard environmental fields
                'temperature', 'humidity', 'pressure', 'wind_speed', 'wind_direction',
                'air_pressure', 'barometric_pressure', 'avg_temperature', 'max_temperature', 'min_temperature',
                # Developer environmental fields (using original FIT field names)
                'baseline_temperature', 'baseline_humidity', 'baseline_elevation',
                'stryd_temperature', 'stryd_humidity', 'impact_loading_rate',
                # User characteristics (from developer fields)
                'weight', 'height'
            ],
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
        
        # Exclude fields matching unknown patterns
        for pattern in self.unknown_patterns:
            if re.match(pattern, field_name.lower()):
                return False
        
        # Normalize field name for comparison (handle spaces and mixed case)
        normalized_name = field_name.lower().replace(' ', '_')
        
        # Check if it's a known environmental field
        if field_name.lower() in self.environmental_field_names:
            return True
        if normalized_name in self.environmental_field_names.values():
            return True
        
        # Include fields with known prefixes/suffixes
        field_lower = normalized_name
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
        
        # Check for environmental patterns (even if not explicitly listed)
        environmental_patterns = ['temperature', 'humidity', 'pressure', 'wind', 'air', 'baseline', 'stryd']
        for pattern in environmental_patterns:
            if pattern.lower() in field_lower:
                return True
        
        # Include simple alphanumeric field names (no strange patterns)
        if re.match(r'^[a-zA-Z][a-zA-Z0-9_\s]*$', field_name) and len(field_name) <= 50:
            return True
        
        return False
        
        return False
    
    def categorize_field(self, field_name: str) -> str:
        """Categorize a field based on its name"""
        # Normalize field name for comparison (handle spaces and mixed case)
        normalized_name = field_name.lower().replace(' ', '_')
        
        # Check power fields first (before environmental to avoid conflicts)
        power_patterns = [
            'power', 'watt', 'torque', 'effectiveness', 'smoothness', 'balance', 'phase'
        ]
        for pattern in power_patterns:
            if pattern.lower() in normalized_name:
                return 'power_fields'
        
        # Check if it's a known environmental field 
        if field_name.lower() in self.environmental_field_names:
            return 'environmental'
        if normalized_name in self.environmental_field_names.values():
            return 'environmental'
        
        # Check environmental patterns (but exclude power-related fields)
        if 'power' not in normalized_name:  # Avoid categorizing power fields as environmental
            environmental_patterns = [
                'temperature', 'humidity', 'pressure', 'wind', 'air', 'baseline', 'stryd',
                'barometric', 'elevation'
            ]
            for pattern in environmental_patterns:
                if pattern.lower() in normalized_name:
                    return 'environmental'
        
        # Check field categories
        for category, fields in self.field_categories.items():
            if normalized_name in [f.lower() for f in fields]:
                return category
        
        # Check prefixes and suffixes for categorization
        if any(normalized_name.startswith(prefix.lower()) for prefix in ['avg_', 'max_', 'min_']):
            if any(normalized_name.endswith(suffix.lower()) for suffix in ['_heart_rate', '_hr']):
                return 'heart_rate_metrics'
            elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_power']):
                return 'power_fields'
            elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_speed', '_pace']):
                return 'speed_metrics'
            elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_cadence']):
                return 'cadence_metrics'
            elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_temperature', '_humidity', '_pressure']):
                return 'environmental'
        
        # Categorize by suffix patterns
        if any(normalized_name.endswith(suffix.lower()) for suffix in ['_oscillation', '_stance', '_contact', '_stiffness']):
            return 'running_dynamics'
        elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_power', '_effectiveness', '_smoothness', '_balance']):
            return 'power_fields'
        elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_zone']):
            return 'zone_fields'
        elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_time']) and 'zone' in normalized_name:
            return 'time_fields'
        elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_stroke', '_strokes', '_length', '_pool']):
            return 'swimming_fields'
        elif any(normalized_name.endswith(suffix.lower()) for suffix in ['_humidity', '_pressure', '_wind', '_air', '_elevation']):
            return 'environmental'
        elif any(normalized_name.startswith(prefix.lower()) for prefix in ['left_', 'right_']) and 'power' in normalized_name:
            return 'power_fields'
        elif any(normalized_name.startswith(prefix.lower()) for prefix in ['left_', 'right_']) and any(x in normalized_name for x in ['pco', 'phase']):
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
            
            # Normalize field name for environmental mapping
            normalized_field_name = self._normalize_field_name(field_name)
            
            # Process different field types
            processed_value = self._process_field_value(field_name, field_value)
            category = self.categorize_field(field_name)
            
            if category in ['time_fields', 'gps_fields', 'numeric_fields', 'categorical_fields']:
                # Direct mapping to document root
                if category == 'time_fields' and hasattr(processed_value, 'isoformat'):
                    doc[normalized_field_name] = processed_value.isoformat()
                elif category == 'gps_fields':
                    self._handle_gps_field(doc, normalized_field_name, processed_value)
                else:
                    doc[normalized_field_name] = processed_value
            elif category == 'general':
                # Store general fields in additional_fields to preserve all valid data
                additional_fields[normalized_field_name] = processed_value
            else:
                # Group into categories
                if category not in categorized_fields:
                    categorized_fields[category] = {}
                categorized_fields[category][normalized_field_name] = processed_value
        
        # Add categorized fields to document
        for category, fields in categorized_fields.items():
            if fields:  # Only add non-empty categories
                doc[category] = fields
        
        # Add general fields to document root for better accessibility
        if additional_fields:
            doc['additional_fields'] = additional_fields
        
        return doc
    
    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field name for consistent mapping"""
        # Check if it's a known environmental field that needs mapping
        field_lower = field_name.lower()
        if field_lower in self.environmental_field_names:
            return self.environmental_field_names[field_lower]
        
        # Convert spaces to underscores and make lowercase for consistency
        normalized = field_name.lower().replace(' ', '_')
        return normalized
    
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

    def aggregate_record_power_data(self, fit_file, session_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate power data from record messages to enhance session data"""
        try:
            records = list(fit_file.get_messages('record'))
            if not records:
                return session_doc
            
            # Collect power values from records
            power_data = {
                'air_power': [],
                'power': [],
                'form_power': []
            }
            
            for record in records:
                for field in record.fields:
                    if field.value is not None:
                        field_name_lower = field.name.lower().replace(' ', '_')
                        
                        if field_name_lower in power_data and field.value > 0:
                            power_data[field_name_lower].append(field.value)
            
            # Calculate statistics for each power type
            power_stats = {}
            for power_type, values in power_data.items():
                if values:
                    power_stats[power_type] = {
                        f'avg_{power_type}': sum(values) / len(values),
                        f'max_{power_type}': max(values),
                        f'min_{power_type}': min(values)
                    }
            
            # Add power statistics to session document
            if power_stats:
                if 'power_fields' not in session_doc:
                    session_doc['power_fields'] = {}
                
                # Flatten the power stats into power_fields
                for power_type, stats in power_stats.items():
                    session_doc['power_fields'].update(stats)
                
                # Also add to additional_fields for reference
                if 'additional_fields' not in session_doc:
                    session_doc['additional_fields'] = {}
                session_doc['additional_fields']['record_power_aggregated'] = True
                session_doc['additional_fields']['power_record_count'] = len(records)
            
            return session_doc
            
        except Exception as e:
            # Don't fail the entire extraction if power aggregation fails
            return session_doc


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
            fit = self._parse_fit_file(source)
            
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
            
            # Try to parse with Garmin SDK
            fit = self._parse_fit_file(source)
            
            # Validate by checking if we can get messages
            try:
                messages_iter = fit.get_messages()
                next(messages_iter)
            except (StopIteration, AttributeError):
                # File is valid but might be empty, which is okay
                pass
            
            return True
        except Exception as e:
            logger.warning(f"Fitness FIT file validation failed: {e}")
            return False
    
    def _parse_fit_file(self, source: Union[str, Path, IO]):
        """Parse FIT file using Garmin SDK only"""
        if not GARMIN_FIT_SDK_AVAILABLE:
            raise RuntimeError("garmin_fit_sdk is required. Install with: uv add garmin-fit-sdk")
        
        return self._parse_with_garmin_sdk(source)
    
    def _parse_with_garmin_sdk(self, source: Union[str, Path, IO]):
        """Parse FIT file with garmin_fit_sdk"""
        if isinstance(source, (str, Path)):
            stream = Stream.from_file(str(source))
        else:
            # For file-like objects, read the content
            content = source.read()
            source.seek(0)  # Reset position for potential future reads
            stream = Stream.from_byte_array(content)
        
        decoder = Decoder(stream)
        messages, errors = decoder.read()
        
        if errors:
            logger.warning(f"Garmin FIT SDK parsing errors: {errors}")
        
        # Create a precise wrapper for Garmin SDK messages
        class GarminSDKWrapper:
            def __init__(self, messages_dict):
                self.messages_dict = messages_dict
                self.all_messages = []
                
                # Process each message type from Garmin SDK
                for key, value in messages_dict.items():
                    if key.endswith('_mesgs') and isinstance(value, list):
                        # Extract message type name (remove '_mesgs' suffix)
                        msg_type = key[:-6]  # Remove '_mesgs'
                        
                        for msg_data in value:
                            if isinstance(msg_data, dict):
                                wrapped_msg = GarminMessage(msg_type, msg_data)
                                self.all_messages.append(wrapped_msg)
            
            def get_messages(self, message_type=None):
                """Get messages, optionally filtered by type"""
                if message_type is None:
                    return iter(self.all_messages)
                
                # Filter by message type
                filtered = []
                for msg in self.all_messages:
                    if msg.name == message_type:
                        filtered.append(msg)
                return iter(filtered)
        
        class GarminMessage:
            """Wrapper for Garmin SDK message to match expected interface"""
            def __init__(self, name, data):
                self.name = name
                self.fields = []
                self.developer_fields = {}
                
                # Convert message data to field objects
                if isinstance(data, dict):
                    for field_name, field_value in data.items():
                        if field_value is not None:
                            # Handle developer fields specially
                            if field_name == 'developer_fields' and isinstance(field_value, dict):
                                self.developer_fields = field_value
                                # Also add developer fields as regular fields with meaningful names
                                self._add_developer_fields_as_fields(field_value)
                            else:
                                field = GarminField(field_name, field_value)
                                self.fields.append(field)
            
            def _add_developer_fields_as_fields(self, developer_fields):
                """Add developer fields as regular fields with meaningful names"""
                # Build field mapping based on field definitions found in FIT file
                # Using original field names from FIT specification (cleaner, without units)
                # Based on actual FIT file analysis with complete Stryd field mapping
                developer_field_mapping = {
                    # Session developer fields (from field definitions)
                    0: 'cp',                     # CP (Critical Power)
                    1: 'baseline_humidity',      # Baseline Humidity
                    2: 'baseline_temperature',   # Baseline Temperature  
                    3: 'baseline_elevation',     # Baseline Elevation
                    4: 'weight',                 # Weight
                    5: 'height',                 # Height
                    
                    # Record developer fields (from field definitions analysis)
                    6: 'lap_power',              # Lap Power
                    7: 'stryd_humidity',         # Stryd Humidity (dynamic reading)
                    8: 'stryd_temperature',      # Stryd Temperature (dynamic reading)
                    9: 'air_power',              # Air Power
                    10: 'form_power',            # Form Power
                    11: 'power',                 # Power (primary power reading)
                    12: 'power_field_unknown',   # Unknown power-related field (always 0)
                    13: 'vertical_oscillation',  # Vertical Oscillation
                    14: 'ground_time',           # Ground Time / Ground Contact Time
                    15: 'leg_spring_stiffness',  # Leg Spring Stiffness
                    16: 'impact_loading_rate'    # Impact Loading Rate
                }
                
                for dev_field_id, dev_field_value in developer_fields.items():
                    if dev_field_value is not None:
                        # Get meaningful name or fallback to ID-based name
                        if dev_field_id in developer_field_mapping:
                            field_name = developer_field_mapping[dev_field_id]
                        else:
                            field_name = f'developer_field_{dev_field_id}'
                        
                        # Add as a regular field so it gets processed by field mapper
                        field = GarminField(field_name, dev_field_value)
                        self.fields.append(field)
        
        class GarminField:
            """Wrapper for Garmin SDK field to match expected interface"""
            def __init__(self, name, value):
                self.name = str(name) if name is not None else ""
                self.value = value
        
        return GarminSDKWrapper(messages)


    def extract_metadata(self, source: Union[str, Path, IO]) -> Dict[str, Any]:
        """Extract fitness FIT file metadata"""
        metadata = {}
        
        try:
            fit = self._parse_fit_file(source)
            
            if isinstance(source, (str, Path)):
                metadata["file_path"] = str(source)
                metadata["file_size"] = Path(source).stat().st_size
            
            # Extract file information using Garmin SDK format
            file_id_messages = list(fit.get_messages('file_id'))
            if file_id_messages:
                file_id = file_id_messages[0]
                # Handle Garmin SDK message format
                if hasattr(file_id, 'fields'):
                    for field in file_id.fields:
                        if field.value is not None:
                            metadata[f"file_{field.name}"] = field.value
            
            # Count message types using Garmin SDK
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
