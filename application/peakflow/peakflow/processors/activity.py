#!/usr/bin/env python3
"""
Activity Processor - Processes FIT files for fitness/workout activity data (sessions, laps, records)
"""
import re
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, IO
from pathlib import Path
import time

# fitparse is used instead of garmin_fit_sdk for direct FIT file processing

from ..storage.interface import (
    DataType, QueryFilter, AggregationQuery,
    ValidationError, StorageError
)
from .interface import (
    FitnessFileProcessor, ProcessingResult, ProcessingStatus,
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

        # Power field name mappings for common camelCase/space-separated variations
        self.power_field_mappings = {
            'lap power': 'lap_power',
            'form power': 'form_power',
            'air power': 'air_power',
            'power': 'power'
        }

        # Running dynamics field name mappings
        self.running_dynamics_mappings = {
            'vertical oscillation': 'vertical_oscillation',
            'stance time': 'stance_time',
            'step length': 'step_length',
            'vertical ratio': 'vertical_ratio',
            'ground time': 'ground_time',
            'impact loading rate': 'impact_loading_rate',
            'leg spring stiffness': 'leg_spring_stiffness'
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
        
        # Minimal unknown field patterns to exclude (very restrictive due to updated Global FIT Profile)
        # We now preserve most unknown fields with metadata instead of filtering them out
        self.unknown_patterns = [
            r'^unknown_\d+_\d+$',       # unknown_123_456 (nested unknown fields)
            r'^field_\d+_\d+$',         # field_123_456 (nested field patterns)
            r'^data_\d+_\d+$',          # data_123_456 (nested data patterns)
            # Removed: r'^unknown_\d+$' - preserve these with metadata for complete data coverage
            # Removed: r'^field_\d+$' - preserve these with metadata
            # Removed: r'^data_\d+$' - preserve these with metadata
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
        field_lower = field_name.lower()

        # Check specific mappings first
        if field_lower in self.environmental_field_names:
            return self.environmental_field_names[field_lower]
        if field_lower in self.power_field_mappings:
            return self.power_field_mappings[field_lower]
        if field_lower in self.running_dynamics_mappings:
            return self.running_dynamics_mappings[field_lower]

        # Convert camelCase and space-separated names to snake_case
        normalized = self._convert_to_snake_case(field_name)
        return normalized

    def _convert_to_snake_case(self, field_name: str) -> str:
        """Convert camelCase and space-separated field names to snake_case"""
        import re

        # First handle space-separated words (like "Lap Power", "Form Power", etc.)
        # Convert spaces to underscores and make lowercase
        normalized = field_name.replace(' ', '_').lower()

        # Handle camelCase conversion (if any camelCase remains)
        # Insert underscore before uppercase letters that follow lowercase letters
        normalized = re.sub('([a-z0-9])([A-Z])', r'\1_\2', normalized).lower()

        # Clean up any double underscores
        normalized = re.sub('_+', '_', normalized)

        return normalized
    
    def _process_field_value(self, field_name: str, field_value: Any) -> Any:
        """Process field value based on field type"""
        # Handle datetime objects
        if hasattr(field_value, 'isoformat'):
            return field_value

        # Handle enum values
        if hasattr(field_value, 'name'):
            return str(field_value)

        # Handle numeric values with NaN/infinity sanitization
        if isinstance(field_value, (int, float)):
            if isinstance(field_value, float):
                import math
                if math.isnan(field_value) or math.isinf(field_value):
                    return None  # Convert NaN/infinity to None (null in JSON)

            # Validate numeric fields - filter out invalid sentinel values
            if any(keyword in field_name.lower() for keyword in ['power', 'speed', 'pace', 'heart_rate', 'respiration']):
                # Common invalid/sentinel values in FIT files
                if field_value in [65535, 65534, 255, -1, 0xFFFF, 0xFF]:
                    return None

                # Field-specific range validation
                if 'power' in field_name.lower():
                    # Reasonable power range (watts)
                    if field_value > 2000 or field_value < 0:
                        return None
                elif 'speed' in field_name.lower():
                    # Reasonable speed range (m/s) - max ~50 km/h for running
                    if field_value > 15 or field_value < 0:
                        return None
                elif 'heart_rate' in field_name.lower():
                    # Reasonable heart rate range (bpm)
                    if field_value > 220 or field_value < 30:
                        return None
                elif 'respiration' in field_name.lower():
                    # Reasonable respiration rate (breaths per minute)
                    if field_value > 60 or field_value < 5:
                        return None

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
        """Enhanced power data aggregation with proper developer field handling"""
        try:
            records = list(fit_file.get_messages('record'))
            if not records:
                return session_doc

            # Get power source information from device_info messages
            power_sources = self._identify_power_sources(fit_file)

            # Dynamically discover power fields from developer field definitions
            power_field_definitions = self._get_power_field_definitions(fit_file)

            # Collect power values from records with source tracking
            power_data = {}
            power_metadata = {
                'sources': power_sources,
                'field_definitions': power_field_definitions,
                'record_count': len(records)
            }

            for record in records:
                # Process standard power fields
                for field in record.fields:
                    if field.value is not None and self._is_power_field(field.name):
                        field_name = self._normalize_power_field_name(field.name)
                        if field.value > 0 and field.value < 2000:  # Valid power range
                            if field_name not in power_data:
                                power_data[field_name] = []
                            power_data[field_name].append(field.value)

                # Process developer power fields with field definition lookup
                if hasattr(record, 'developer_fields'):
                    for dev_field_id, dev_field_value in record.developer_fields.items():
                        if dev_field_value is not None:
                            field_name = power_field_definitions.get(dev_field_id)
                            if field_name and self._is_power_field(field_name):
                                normalized_name = self._normalize_power_field_name(field_name)
                                if dev_field_value > 0 and dev_field_value < 2000:
                                    if normalized_name not in power_data:
                                        power_data[normalized_name] = []
                                    power_data[normalized_name].append(dev_field_value)

            # Calculate comprehensive power statistics with avg, min, max for each field
            if 'power_fields' not in session_doc:
                session_doc['power_fields'] = {}

            for power_type, values in power_data.items():
                if values:
                    session_doc['power_fields'][f'avg_{power_type}'] = round(sum(values) / len(values), 2)
                    session_doc['power_fields'][f'max_{power_type}'] = max(values)
                    session_doc['power_fields'][f'min_{power_type}'] = min(values)

            # Add power metadata for debugging and analysis
            if power_data:
                if 'power_data_availability' not in session_doc:
                    session_doc['power_data_availability'] = {}

                session_doc['power_data_availability'].update({
                    'has_power_data': bool(power_data),
                    'power_values_count': sum(len(values) for values in power_data.values()),
                    'power_metrics_available': list(power_data.keys()),
                    'power_sources': [source.get('manufacturer', 'unknown') for source in power_sources],
                    'developer_field_count': len(power_field_definitions)
                })

                # Enhanced metadata in additional_fields
                if 'additional_fields' not in session_doc:
                    session_doc['additional_fields'] = {}
                session_doc['additional_fields']['record_power_aggregated'] = True
                session_doc['additional_fields']['power_metadata'] = power_metadata

            return session_doc

        except Exception as e:
            logger.warning(f"Power aggregation failed: {e}")
            return session_doc

    def _identify_power_sources(self, fit_file) -> List[Dict[str, Any]]:
        """Identify devices that can provide power data"""
        power_sources = []
        try:
            for device_info in fit_file.get_messages('device_info'):
                device_data = {}
                for field in device_info.fields:
                    if field.value is not None:
                        device_data[field.name] = field.value

                # Check if device can provide power (ANT+ power meter, Stryd, etc.)
                if (device_data.get('device_type') in ['bike_power', 'stride_speed_distance'] or
                    device_data.get('manufacturer') in ['stryd', 'garmin'] or
                    'power' in str(device_data.get('product_name', '')).lower()):
                    power_sources.append(device_data)
        except Exception as e:
            logger.debug(f"Could not identify power sources: {e}")

        return power_sources

    def _get_power_field_definitions(self, fit_file) -> Dict[int, str]:
        """Extract power-related field definitions from developer fields"""
        power_field_defs = {}
        try:
            for field_def in fit_file.get_messages('field_definition'):
                field_data = {}
                for field in field_def.fields:
                    if field.value is not None:
                        field_data[field.name] = field.value

                field_name = field_data.get('field_name', '').lower()
                if self._is_power_field(field_name):
                    field_num = field_data.get('field_definition_number')
                    if field_num is not None:
                        power_field_defs[field_num] = field_name
        except Exception as e:
            logger.debug(f"Could not extract field definitions: {e}")

        return power_field_defs

    def _is_power_field(self, field_name: str) -> bool:
        """Check if field name indicates a power-related metric"""
        field_lower = field_name.lower()
        power_indicators = ['power', 'watt', 'form_power', 'air_power', 'lap_power']
        return any(indicator in field_lower for indicator in power_indicators)

    def _normalize_power_field_name(self, field_name: str) -> str:
        """Normalize power field names for consistency"""
        normalized = field_name.lower().replace(' ', '_').replace('-', '_')

        # Map common variations to standard names
        power_name_mapping = {
            'power': 'power',
            'total_power': 'power',
            'air_power': 'air_power',
            'form_power': 'form_power',
            'lap_power': 'lap_power'
        }

        return power_name_mapping.get(normalized, normalized)

    def aggregate_record_running_dynamics_data(self, fit_file, session_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate running dynamics static fields (avg, min, max) from record data"""
        try:
            records = list(fit_file.get_messages('record'))
            if not records:
                return session_doc

            # Collect running dynamics values from records
            running_dynamics_data = {}

            for record in records:
                # Process standard running dynamics fields
                for field in record.fields:
                    if field.value is not None and self._is_running_dynamics_field(field.name):
                        field_name = self._normalize_running_dynamics_field_name(field.name)
                        processed_value = self._process_running_dynamics_value(field.name, field.value)
                        if processed_value is not None:
                            if field_name not in running_dynamics_data:
                                running_dynamics_data[field_name] = []
                            running_dynamics_data[field_name].append(processed_value)

            # Calculate comprehensive running dynamics statistics with avg, min, max for each field
            if 'running_dynamics' not in session_doc:
                session_doc['running_dynamics'] = {}

            for dynamics_type, values in running_dynamics_data.items():
                if values:
                    session_doc['running_dynamics'][f'avg_{dynamics_type}'] = round(sum(values) / len(values), 2)
                    session_doc['running_dynamics'][f'max_{dynamics_type}'] = max(values)
                    session_doc['running_dynamics'][f'min_{dynamics_type}'] = min(values)

            # Add running dynamics metadata for debugging and analysis
            if running_dynamics_data:
                if 'running_dynamics_data_availability' not in session_doc:
                    session_doc['running_dynamics_data_availability'] = {}

                session_doc['running_dynamics_data_availability'].update({
                    'has_running_dynamics_data': bool(running_dynamics_data),
                    'running_dynamics_values_count': sum(len(values) for values in running_dynamics_data.values()),
                    'running_dynamics_metrics_available': list(running_dynamics_data.keys())
                })

                # Enhanced metadata in additional_fields
                if 'additional_fields' not in session_doc:
                    session_doc['additional_fields'] = {}
                session_doc['additional_fields']['record_running_dynamics_aggregated'] = True

            return session_doc

        except Exception as e:
            logger.warning(f"Running dynamics aggregation failed: {e}")
            return session_doc

    def _is_running_dynamics_field(self, field_name: str) -> bool:
        """Check if field name indicates a running dynamics metric"""
        field_lower = field_name.lower()
        running_dynamics_indicators = [
            'vertical_oscillation', 'stance_time', 'step_length', 'vertical_ratio',
            'ground_contact_time', 'ground_time', 'impact_loading_rate', 'leg_spring_stiffness',
            'stance_time_percent', 'vertical_oscillation_percent', 'ground_contact_balance',
            'left_right_balance', 'duty_factor', 'flight_time', 'form_power_ratio',
            'efficiency_score', 'stride_frequency', 'step_frequency'
        ]
        return any(indicator in field_lower for indicator in running_dynamics_indicators)

    def _normalize_running_dynamics_field_name(self, field_name: str) -> str:
        """Normalize running dynamics field names for consistency"""
        normalized = field_name.lower().replace(' ', '_').replace('-', '_')

        # Map common variations to standard names
        running_dynamics_name_mapping = {
            'vertical_oscillation': 'vertical_oscillation',
            'stance_time': 'stance_time',
            'step_length': 'step_length',
            'vertical_ratio': 'vertical_ratio',
            'ground_contact_time': 'ground_contact_time',
            'ground_time': 'ground_time',
            'impact_loading_rate': 'impact_loading_rate',
            'leg_spring_stiffness': 'leg_spring_stiffness',
            'stance_time_percent': 'stance_time_percent',
            'vertical_oscillation_percent': 'vertical_oscillation_percent',
            'ground_contact_balance': 'ground_contact_balance',
            'left_right_balance': 'left_right_balance',
            'duty_factor': 'duty_factor',
            'flight_time': 'flight_time',
            'form_power_ratio': 'form_power_ratio',
            'efficiency_score': 'efficiency_score',
            'stride_frequency': 'stride_frequency',
            'step_frequency': 'step_frequency'
        }

        return running_dynamics_name_mapping.get(normalized, normalized)

    def _process_running_dynamics_value(self, field_name: str, field_value: Any) -> Any:
        """Process running dynamics field value with validation"""
        if not isinstance(field_value, (int, float)):
            return None

        # Apply range validation for running dynamics
        field_lower = field_name.lower()

        # Common invalid/sentinel values in FIT files
        if field_value in [65535, 65534, 255, -1, 0xFFFF, 0xFF]:
            return None

        # Field-specific range validation
        if 'vertical_oscillation' in field_lower:
            # Vertical oscillation in mm (20-150 mm is reasonable)
            if field_value > 150 or field_value <= 0:
                return None
        elif 'stance_time' in field_lower:
            # Stance time in ms (150-400 ms is reasonable)
            if field_value > 400 or field_value < 100:
                return None
        elif 'step_length' in field_lower:
            # Step length in mm (600-3000 mm is reasonable)
            if field_value > 3000 or field_value < 200:
                return None
        elif 'vertical_ratio' in field_lower:
            # Vertical ratio in % (2-50% is reasonable)
            if field_value > 50 or field_value <= 0:
                return None
        elif 'ground_contact' in field_lower or 'ground_time' in field_lower:
            # Ground contact time in ms (similar to stance time)
            if field_value > 400 or field_value < 100:
                return None
        elif 'impact_loading_rate' in field_lower:
            # Impact loading rate (10-100 BW/s is reasonable)
            if field_value > 100 or field_value <= 0:
                return None
        elif 'leg_spring_stiffness' in field_lower:
            # Leg spring stiffness (5-25 kN/m is reasonable)
            if field_value > 25 or field_value <= 0:
                return None
        elif any(x in field_lower for x in ['balance', 'percent']):
            # Balance and percentage fields (0-100%)
            if field_value > 100 or field_value < 0:
                return None
        elif 'frequency' in field_lower:
            # Step/stride frequency (120-220 steps/min is reasonable)
            if field_value > 300 or field_value <= 0:
                return None
        elif field_value < 0:
            # For other fields, just filter negatives
            return None

        return field_value


class StrydMetricsAggregator:
    """Unified Stryd metrics aggregator - eliminate special cases"""
    
    # All Stryd metrics that can be aggregated from records
    STRYD_METRICS = {
        # Power metrics (actual FIT field names)
        'power', 'enhanced_power', 'air_power', 'form_power', 'lap_power',
        # Biomechanics metrics (actual FIT field names found in data)
        'vertical_oscillation', 'vertical_ratio',
        'stance_time', 'stance_time_balance', 'stance_time_percent',
        'ground_time', 'step_length',
        'leg_spring_stiffness', 'impact_loading_rate',
        # Environmental metrics
        'stryd_temperature', 'stryd_humidity',
        # Static/baseline metrics
        'baseline_temperature', 'baseline_humidity', 'baseline_elevation',
        'weight', 'height'
    }
    
    # Metrics that should use first/last value instead of aggregation
    STATIC_METRICS = {
        'baseline_temperature', 'baseline_humidity', 'baseline_elevation',
        'weight', 'height'
    }
    
    def __init__(self):
        self.logger = get_logger(__name__)

    def _process_field_value(self, field_name: str, field_value: Any) -> Any:
        """Apply same field validation as ActivityProcessor to filter sentinel values"""
        # Handle numeric values with NaN/infinity sanitization
        if isinstance(field_value, (int, float)):
            if isinstance(field_value, float):
                import math
                if math.isnan(field_value) or math.isinf(field_value):
                    return None
            # Validate numeric fields - filter out invalid sentinel values
            if any(keyword in field_name.lower() for keyword in ['power', 'speed', 'pace', 'heart_rate', 'respiration', 'stryd', 'vertical', 'stance', 'step', 'stiffness', 'impact', 'humidity', 'temperature']):
                if field_value in [65535, 65534, 255, -1, 0xFFFF, 0xFF]:
                    return None
        return field_value

    def aggregate_for_session(self, fit_file, session_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate all Stryd metrics for the entire session"""
        try:
            records = list(fit_file.get_messages('record'))
            if not records:
                return {}
            
            return self._aggregate_stryd_metrics(records, session_doc.get('timestamp'))
            
        except Exception as e:
            self.logger.warning(f"Session Stryd aggregation failed: {e}")
            return {}
    
    def aggregate_for_time_range(self, records: List, start_time, end_time) -> Dict[str, Any]:
        """Aggregate Stryd metrics for a specific time range (lap)"""
        try:
            if not records or not start_time:
                return {}
            
            # Filter records within time range
            filtered_records = []
            for record in records:
                record_time = self._get_record_timestamp(record)
                if record_time and start_time <= record_time <= end_time:
                    filtered_records.append(record)
            
            if not filtered_records:
                return {}
            
            return self._aggregate_stryd_metrics(filtered_records, start_time)
            
        except Exception as e:
            self.logger.warning(f"Time range Stryd aggregation failed: {e}")
            return {}
    
    def _aggregate_stryd_metrics(self, records: List, base_timestamp) -> Dict[str, Any]:
        """Core aggregation logic for Stryd metrics"""
        stryd_data = {metric: [] for metric in self.STRYD_METRICS}
        
        # Collect Stryd values from all records
        for record in records:
            for field in record.fields:
                if field.value is not None and field.name in self.STRYD_METRICS:
                    # Apply same validation as _process_field_value to filter sentinel values
                    processed_value = self._process_field_value(field.name, field.value)
                    if processed_value is None:
                        continue

                    # Only collect valid numeric values, exclude 0 for most metrics
                    if isinstance(processed_value, (int, float)):
                        # For most Stryd metrics, 0 is invalid data
                        if field.name in ['power', 'enhanced_power', 'air_power', 'form_power', 'lap_power',
                                        'vertical_oscillation', 'impact_loading_rate', 'leg_spring_stiffness']:
                            # These metrics should never be 0 during active movement
                            if processed_value > 0:
                                stryd_data[field.name].append(processed_value)
                        elif field.name in ['stryd_temperature', 'stryd_humidity']:
                            # Environmental metrics: 0 is invalid for temperature/humidity
                            if processed_value > 0:
                                stryd_data[field.name].append(processed_value)
                        elif field.name in ['vertical_ratio']:
                            # Vertical ratio should be > 0 (percentage)
                            if processed_value > 0:
                                stryd_data[field.name].append(processed_value)
                        else:
                            # For time/stance metrics, very small values might be invalid
                            if field.name in ['stance_time', 'ground_time']:
                                # Stance time should be reasonable (> 100ms)
                                if processed_value >= 100:
                                    stryd_data[field.name].append(processed_value)
                            elif field.name in ['step_length']:
                                # Step length should be reasonable (> 200mm)
                                if processed_value >= 200:
                                    stryd_data[field.name].append(processed_value)
                            else:
                                # For other metrics, just filter negatives
                                if processed_value >= 0:
                                    stryd_data[field.name].append(processed_value)

        # Debug: Log what we collected
        collected_fields = {k: len(v) for k, v in stryd_data.items() if v}
        if collected_fields:
            self.logger.info(f"Collected Stryd fields: {collected_fields}")
        
        # Calculate statistics
        aggregated_metrics = {}
        
        for metric, values in stryd_data.items():
            if not values:
                continue
                
            if metric in self.STATIC_METRICS:
                # For static metrics, use first available value
                aggregated_metrics[f'avg_{metric}'] = values[0]
            else:
                # For dynamic metrics, calculate full statistics
                import math
                avg_val = sum(values) / len(values)
                max_val = max(values)
                min_val = min(values)

                # Sanitize NaN/infinity values
                if not (math.isnan(avg_val) or math.isinf(avg_val)):
                    aggregated_metrics[f'avg_{metric}'] = avg_val
                if not (math.isnan(max_val) or math.isinf(max_val)):
                    aggregated_metrics[f'max_{metric}'] = max_val
                if not (math.isnan(min_val) or math.isinf(min_val)):
                    aggregated_metrics[f'min_{metric}'] = min_val
        
        # Structure the results with power data availability flags
        if aggregated_metrics:
            # Check if power-related metrics were found
            power_metrics = ['power', 'enhanced_power', 'air_power', 'form_power', 'lap_power']
            power_data_available = any(
                any(f'_{metric}' in key for key in aggregated_metrics.keys())
                for metric in power_metrics
            )

            # Count actual power values collected
            power_values_count = sum(len(stryd_data.get(metric, [])) for metric in power_metrics)

            result = {
                'stryd_metrics': aggregated_metrics,
                'power_data_availability': {
                    'has_power_data': power_data_available,
                    'power_values_count': power_values_count,
                    'power_metrics_available': [
                        metric for metric in power_metrics
                        if any(f'_{metric}' in key for key in aggregated_metrics.keys())
                    ]
                },
                'stryd_aggregation_metadata': {
                    'record_count': len(records),
                    'metrics_extracted': list(aggregated_metrics.keys()),
                    'aggregation_timestamp': base_timestamp.isoformat() if hasattr(base_timestamp, 'isoformat') else str(base_timestamp)
                }
            }
            return result
        
        return {}
    
    def _get_record_timestamp(self, record):
        """Extract timestamp from a record"""
        for field in record.fields:
            if field.name == 'timestamp' and field.value is not None:
                return field.value
        return None
    
    def validate_stryd_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Stryd metrics ranges"""
        if 'stryd_metrics' not in data:
            return data
            
        stryd_ranges = {
            # Power metrics (watts)
            'avg_power': (0, 2000), 'max_power': (0, 2000), 'min_power': (0, 2000),
            'avg_enhanced_power': (0, 2000), 'max_enhanced_power': (0, 2000), 'min_enhanced_power': (0, 2000),
            'avg_air_power': (0, 1000), 'max_air_power': (0, 1000), 'min_air_power': (0, 1000),
            'avg_form_power': (0, 100), 'max_form_power': (0, 100), 'min_form_power': (0, 100),
            'avg_lap_power': (0, 2000), 'max_lap_power': (0, 2000), 'min_lap_power': (0, 2000),

            # Biomechanics metrics (actual field names from FIT files)
            'avg_vertical_oscillation': (20, 150), 'max_vertical_oscillation': (20, 150), 'min_vertical_oscillation': (20, 150),  # mm
            'avg_vertical_ratio': (2, 50), 'max_vertical_ratio': (2, 50), 'min_vertical_ratio': (2, 50),  # %
            'avg_stance_time': (150, 400), 'max_stance_time': (150, 400), 'min_stance_time': (150, 400),  # ms
            'avg_stance_time_balance': (30, 70), 'max_stance_time_balance': (30, 70), 'min_stance_time_balance': (30, 70),  # %
            'avg_stance_time_percent': (10, 60), 'max_stance_time_percent': (10, 60), 'min_stance_time_percent': (10, 60),  # %
            'avg_ground_time': (150, 400), 'max_ground_time': (150, 400), 'min_ground_time': (150, 400),  # ms
            'avg_step_length': (600, 3000), 'max_step_length': (600, 3000), 'min_step_length': (600, 3000),  # mm
            'avg_leg_spring_stiffness': (5, 25), 'max_leg_spring_stiffness': (5, 25), 'min_leg_spring_stiffness': (5, 25),  # kN/m
            'avg_impact_loading_rate': (10, 100), 'max_impact_loading_rate': (10, 100), 'min_impact_loading_rate': (10, 100),  # BW/s

            # Environmental metrics (wider ranges, might be Fahrenheit or unusual values)
            'avg_stryd_temperature': (-20, 200), 'max_stryd_temperature': (-20, 200), 'min_stryd_temperature': (-20, 200),  # Mixed units
            'avg_stryd_humidity': (10, 500), 'max_stryd_humidity': (10, 500), 'min_stryd_humidity': (10, 500),  # Might have unusual scaling

            # User metrics (0 values allowed for missing data)
            'avg_weight': (0, 200), 'avg_height': (0, 250),  # kg, cm
        }
        
        stryd_metrics = data['stryd_metrics']
        invalid_metrics = []
        filtered_metrics = {}

        for metric_name, metric_value in stryd_metrics.items():
            if metric_name in stryd_ranges:
                min_val, max_val = stryd_ranges[metric_name]
                if min_val <= metric_value <= max_val:
                    # Keep valid values
                    filtered_metrics[metric_name] = metric_value
                else:
                    # Filter out invalid values and log them
                    invalid_metrics.append(f"{metric_name}: {metric_value} not in range [{min_val}, {max_val}]")
            else:
                # Keep metrics without validation ranges
                filtered_metrics[metric_name] = metric_value

        if invalid_metrics:
            self.logger.warning(f"Filtered out invalid Stryd metrics: {invalid_metrics}")

        # Update data with filtered metrics
        data['stryd_metrics'] = filtered_metrics
        return data


class ActivityValidator(DataValidator):
    """Activity data validator for fitness/workout data"""
    
    def __init__(self):
        self.stryd_aggregator = StrydMetricsAggregator()
    
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
        
        # Validate metrics ranges if present
        data = self.stryd_aggregator.validate_stryd_metrics(data)
        
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
        
        # Validate metrics ranges if present
        data = self.stryd_aggregator.validate_stryd_metrics(data)
        
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

    def transform_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform session data"""
        # Apply coordinate transformation if location data exists
        data = self.transform_coordinates(data)

        # Normalize units
        data = self.normalize_units(data)

        # Ensure timestamp is in proper format
        if 'start_time' in data and isinstance(data['start_time'], str):
            # Ensure start_time is properly formatted
            if not data['start_time'].endswith('Z') and '+' not in data['start_time']:
                data['start_time'] = data['start_time'] + 'Z'

        return data

    def transform_record_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform record data"""
        # Apply coordinate transformation if location data exists
        data = self.transform_coordinates(data)

        # Normalize units
        data = self.normalize_units(data)

        return data

    def transform_lap_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform lap data"""
        # Apply coordinate transformation if location data exists
        data = self.transform_coordinates(data)

        # Normalize units
        data = self.normalize_units(data)

        return data


class ActivityProcessor(FitnessFileProcessor):
    """Activity processor for fitness/workout FIT files (sessions, laps, records) using fitparse"""

    def __init__(self, storage, options: Optional[ProcessingOptions] = None):
        super().__init__(storage, options)
        self.validator = ActivityValidator()
        self.transformer = ActivityTransformer()
        self.field_mapper = ActivityFieldMapper()
        self.stryd_aggregator = StrydMetricsAggregator()
        # Import and initialize the fitparse processor
        from .fitparse_processor import FitParseProcessor
        self.fitparse_processor = FitParseProcessor()
        # Store current fit data and records for lap processing
        self.current_fit_data = None
        self.current_records = None
    
    def process(self, source: Union[str, Path, IO],
               user_id: str,
               activity_id: Optional[str] = None) -> ProcessingResult:
        """Process fitness FIT file for activity/workout data using fitparse"""
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

            # Convert source to file path string if needed
            file_path = str(source) if isinstance(source, (str, Path)) else source

            # Process fitness FIT file using fitparse
            fit_data = self.fitparse_processor.process_fit_file(file_path, activity_id, user_id)

            # Store processed data for compatibility with existing code
            self.current_fit_data = fit_data
            self.current_records = fit_data.get('records', [])

            # Process different data types using the fitparse results
            session_result = self._process_fitparse_session_data(fit_data['session'])
            record_result = self._process_fitparse_record_data(fit_data['records'])
            lap_result = self._process_fitparse_lap_data(fit_data['laps'])

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
                "laps": lap_result.successful_records,
                "power_sources": fit_data.get('metadata', {}).get('power_sources', [])
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
            logger.error(f"❌ Fitness FIT processing error: {e}")

        return result

    def _process_fitparse_session_data(self, session_data: Dict[str, Any]) -> ProcessingResult:
        """Process session data from fitparse processor"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)

        try:
            if not session_data:
                result.add_warning("No session data found")
                result.status = ProcessingStatus.COMPLETED
                return result

            # Validate and transform session data
            validated_doc = self.validator.validate_session_data(session_data)
            transformed_doc = self.transformer.transform_session_data(validated_doc)

            # Store to storage
            success = self.storage.index_document(
                DataType.SESSION,
                session_data['activity_id'],
                transformed_doc
            )

            if success:
                result.successful_records = 1
                logger.debug(f"✅ Session data stored for activity {session_data['activity_id']}")
            else:
                result.failed_records = 1
                result.add_error("Failed to store session data")

            result.status = ProcessingStatus.COMPLETED

        except Exception as e:
            result.failed_records = 1
            result.add_error(f"Session processing failed: {e}")
            logger.error(f"❌ Session processing failed: {e}")

        return result

    def _process_fitparse_record_data(self, records_data: List[Dict[str, Any]]) -> ProcessingResult:
        """Process record data from fitparse processor"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)

        try:
            if not records_data:
                result.add_warning("No record data found")
                result.status = ProcessingStatus.COMPLETED
                return result

            # Prepare documents for bulk indexing
            documents = []
            for record in records_data:
                try:
                    validated_doc = self.validator.validate_record_data(record)
                    transformed_doc = self.transformer.transform_record_data(validated_doc)
                    transformed_doc['_id'] = f"{record['activity_id']}_{record['sequence']}"
                    documents.append(transformed_doc)
                except Exception as e:
                    result.failed_records += 1
                    result.add_error(f"Record {record.get('sequence', 'unknown')} validation failed: {e}")

            # Bulk index documents
            if documents:
                indexing_result = self.storage.bulk_index(DataType.RECORD, documents)
                result.successful_records = indexing_result.success_count
                result.failed_records += indexing_result.failed_count

                if indexing_result.errors:
                    result.errors.extend(indexing_result.errors)

            result.status = ProcessingStatus.COMPLETED
            logger.debug(f"✅ Processed {len(records_data)} records: {result.successful_records} successful")

        except Exception as e:
            result.add_error(f"Record processing failed: {e}")
            logger.error(f"❌ Record processing failed: {e}")

        return result

    def _process_fitparse_lap_data(self, laps_data: List[Dict[str, Any]]) -> ProcessingResult:
        """Process lap data from fitparse processor"""
        result = ProcessingResult(status=ProcessingStatus.PROCESSING)

        try:
            if not laps_data:
                result.add_warning("No lap data found")
                result.status = ProcessingStatus.COMPLETED
                return result

            # Prepare documents for bulk indexing
            documents = []
            for lap in laps_data:
                try:
                    validated_doc = self.validator.validate_lap_data(lap)
                    transformed_doc = self.transformer.transform_lap_data(validated_doc)
                    transformed_doc['_id'] = f"{lap['activity_id']}_lap_{lap.get('lap_number', len(documents) + 1)}"
                    documents.append(transformed_doc)
                except Exception as e:
                    result.failed_records += 1
                    result.add_error(f"Lap {lap.get('lap_number', 'unknown')} validation failed: {e}")

            # Bulk index documents
            if documents:
                indexing_result = self.storage.bulk_index(DataType.LAP, documents)
                result.successful_records = indexing_result.success_count
                result.failed_records += indexing_result.failed_count

                if indexing_result.errors:
                    result.errors.extend(indexing_result.errors)

            result.status = ProcessingStatus.COMPLETED
            logger.debug(f"✅ Processed {len(laps_data)} laps: {result.successful_records} successful")

        except Exception as e:
            result.add_error(f"Lap processing failed: {e}")
            logger.error(f"❌ Lap processing failed: {e}")

        return result

    def validate_source(self, source: Union[str, Path, IO]) -> bool:
        """Validate fitness FIT file format using fitparse"""
        try:
            if isinstance(source, (str, Path)):
                if not Path(source).exists():
                    return False

                # Check file extension
                if not str(source).lower().endswith('.fit'):
                    return False

                # Try to parse with fitparse
                from fitparse import FitFile
                fit = FitFile(str(source))

                # Validate by checking if we can get messages
                try:
                    messages = list(fit.get_messages())
                    return len(messages) > 0
                except Exception:
                    return False
            else:
                # For file-like objects, more complex validation needed
                return True  # Skip validation for IO objects for now

        except Exception as e:
            logger.warning(f"Fitness FIT file validation failed: {e}")
            return False

    def extract_metadata(self, source: Union[str, Path, IO]) -> Dict[str, Any]:
        """Extract metadata from FIT file"""
        try:
            file_path = str(source) if isinstance(source, (str, Path)) else source
            fit_data = self.fitparse_processor.process_fit_file(file_path, "metadata", "system")
            return fit_data.get('metadata', {})
        except Exception as e:
            logger.warning(f"Failed to extract metadata: {e}")
            return {}

    def process_session_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process session data - compatibility method"""
        # This method maintains compatibility but the actual processing is done in process()
        result = ProcessingResult(status=ProcessingStatus.COMPLETED)
        result.add_warning("Use process() method instead of process_session_data()")
        return result

    def process_record_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process record data - compatibility method"""
        # This method maintains compatibility but the actual processing is done in process()
        result = ProcessingResult(status=ProcessingStatus.COMPLETED)
        result.add_warning("Use process() method instead of process_record_data()")
        return result

    def process_lap_data(self, raw_data: Any, activity_id: str, user_id: str) -> ProcessingResult:
        """Process lap data - compatibility method"""
        # This method maintains compatibility but the actual processing is done in process()
        result = ProcessingResult(status=ProcessingStatus.COMPLETED)
        result.add_warning("Use process() method instead of process_lap_data()")
        return result

    def get_activity_summary(self, activity_id: str) -> Optional[Dict[str, Any]]:
        """Get activity summary from storage"""
        try:
            query_filter = QueryFilter()
            query_filter.add_term_filter('activity_id', activity_id)
            sessions = self.storage.search(DataType.SESSION, query_filter)
            return sessions[0] if sessions else None
        except Exception as e:
            logger.warning(f"Failed to get activity summary: {e}")
            return None

    def get_supported_sports(self) -> List[str]:
        """Get supported sport types"""
        return [
            'running', 'cycling', 'swimming', 'walking', 'hiking',
            'triathlon', 'generic', 'fitness_equipment', 'training'
        ]
