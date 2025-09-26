#!/usr/bin/env python3
"""
Direct FIT file processor using fitparse with Global FIT Profile - eliminate Garmin SDK dependency for parsing
"""
from fitparse import FitFile
from fitparse.profile import MESSAGE_TYPES
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone
import logging

try:
    from dateutil.parser import parse as parse_datetime
except ImportError:
    # Fallback if dateutil is not available
    def parse_datetime(date_string):
        return datetime.fromisoformat(date_string.replace('Z', '+00:00'))

logger = logging.getLogger(__name__)


class FitParseProcessor:
    """Process FIT files directly using fitparse library"""

    # Comprehensive whitelisted fields for processing
    ALLOWED_POWER_FIELDS = {
        # Basic power fields
        'power', 'form_power', 'air_power', 'lap_power',
        'enhanced_power', 'normalized_power',
        # Power zones and thresholds
        'functional_threshold_power', 'threshold_power', 'cp',
        # Left/right power
        'left_power', 'right_power', 'left_right_balance',
        # Power effectiveness and smoothness
        'left_torque_effectiveness', 'right_torque_effectiveness',
        'left_pedal_smoothness', 'right_pedal_smoothness', 'combined_pedal_smoothness',
        # Training metrics
        'training_stress_score', 'tss', 'intensity_factor'
    }
    
    ALLOWED_RUNNING_DYNAMICS_FIELDS = {
        # Ground contact and stance
        'ground_time', 'ground_contact_time', 'stance_time', 'stance_time_percent',
        'stance_time_balance', 'ground_contact_balance',
        # Vertical movement
        'vertical_oscillation', 'vertical_ratio', 'vertical_oscillation_percent',
        # Step and stride
        'step_length', 'stride_frequency', 'step_frequency',
        # Impact and stiffness
        'impact_loading_rate', 'leg_spring_stiffness',
        # Advanced dynamics
        'duty_factor', 'flight_time', 'form_power_ratio',
        # Balance and efficiency
        'left_right_balance', 'efficiency_score'
    }

    def __init__(self):
        self.power_sources = []
        self.developer_field_defs = {}
        self.session_data = {}
        self.record_data = []
        self.lap_data = []
        # Cache Global FIT Profile message types for performance
        self.global_profile_cache = {
            'session': MESSAGE_TYPES.get(18),  # Session message
            'record': MESSAGE_TYPES.get(20),   # Record message
            'lap': MESSAGE_TYPES.get(19)       # Lap message
        }

    def process_fit_file(self, fit_file_path: str, activity_id: str, user_id: str) -> Dict[str, Any]:
        """Process FIT file and extract all data without Garmin SDK"""
        try:
            # Parse FIT file with fitparse
            fitfile = FitFile(fit_file_path)

            # Step 1: Extract metadata and device information
            self._extract_file_metadata(fitfile)
            self._extract_device_info(fitfile)
            self._extract_developer_field_definitions(fitfile)

            # Step 2: Process main data messages
            session_doc = self._extract_session_data(fitfile, activity_id, user_id)
            record_docs = self._extract_record_data(fitfile, activity_id, user_id)
            lap_docs = self._extract_lap_data(fitfile, activity_id, user_id, record_docs)

            # Step 3: Enhance with power analysis
            session_doc = self._enhance_with_power_analysis(session_doc, record_docs)

            return {
                'session': session_doc,
                'records': record_docs,
                'laps': lap_docs,
                'metadata': {
                    'power_sources': self.power_sources,
                    # 'developer_fields': len(self.developer_field_defs),  # Skip to reduce metadata
                    'processed_at': datetime.now(timezone.utc).isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Failed to process FIT file {fit_file_path}: {e}")
            raise

    def _extract_file_metadata(self, fitfile: FitFile):
        """Extract file-level metadata"""
        try:
            for record in fitfile.get_messages('file_id'):
                for field in record.fields:
                    if field.value is not None:
                        self.session_data[field.name] = field.value
        except Exception as e:
            logger.debug(f"Could not extract file metadata: {e}")

    def _extract_device_info(self, fitfile: FitFile):
        """Extract device information to identify power sources"""
        self.power_sources = []

        try:
            for record in fitfile.get_messages('device_info'):
                device_info = {}
                for field in record.fields:
                    if field.value is not None:
                        device_info[field.name] = field.value

                # Identify potential power sources
                if self._is_potential_power_source(device_info):
                    self.power_sources.append(device_info)

        except Exception as e:
            logger.debug(f"Could not extract device info: {e}")

    def _is_potential_power_source(self, device_info: Dict[str, Any]) -> bool:
        """Check if device can provide power data"""
        # Check ANT+ device types
        device_type = device_info.get('device_type')
        if device_type in ['bike_power', 'stride_speed_distance']:
            return True

        # Check manufacturer for known power providers
        manufacturer = str(device_info.get('manufacturer', '')).lower()
        if manufacturer in ['stryd', 'stages', 'powertap', 'srm', 'quarq']:
            return True

        # Check product name for power indicators
        product_name = str(device_info.get('product_name', '')).lower()
        if any(keyword in product_name for keyword in ['power', 'stryd', 'powermeter']):
            return True

        return False

    def _extract_developer_field_definitions(self, fitfile: FitFile):
        """Extract developer field definitions for proper field mapping"""
        self.developer_field_defs = {}

        try:
            for record in fitfile.get_messages('developer_data_id'):
                dev_data_id = None
                for field in record.fields:
                    if field.name == 'developer_data_index':
                        dev_data_id = field.value
                        break

                if dev_data_id is not None:
                    self.developer_field_defs[dev_data_id] = {}

            # Extract field descriptions
            for record in fitfile.get_messages('field_description'):
                field_info = {}
                for field in record.fields:
                    if field.value is not None:
                        field_info[field.name] = field.value

                dev_data_index = field_info.get('developer_data_index')
                field_definition_number = field_info.get('field_definition_number')
                field_name = field_info.get('field_name')

                if all(x is not None for x in [dev_data_index, field_definition_number, field_name]):
                    if dev_data_index not in self.developer_field_defs:
                        self.developer_field_defs[dev_data_index] = {}
                    self.developer_field_defs[dev_data_index][field_definition_number] = {
                        'name': field_name,
                        'units': field_info.get('units'),
                        'native_field_num': field_info.get('native_field_num')
                    }

        except Exception as e:
            logger.debug(f"Could not extract developer field definitions: {e}")

    def _extract_session_data(self, fitfile: FitFile, activity_id: str, user_id: str) -> Dict[str, Any]:
        """Extract session-level data"""
        session_doc = {
            'activity_id': activity_id,
            'user_id': user_id,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        try:
            for record in fitfile.get_messages('session'):
                # Process all fields using clean fitparse approach
                for field_data in record.fields:
                    if field_data.value is not None:
                        # Get field name, processed value, and metadata
                        field_name, processed_value, metadata = self._process_field_with_metadata(field_data)
                        
                        if processed_value is not None:
                            # Store the field value
                            session_doc[field_name] = processed_value
                            
                            # Skip storing metadata for unknown and developer fields to reduce index size
                            # if metadata['is_unknown'] or metadata['is_developer']:
                            #     if 'field_metadata' not in session_doc:
                            #         session_doc['field_metadata'] = {}
                            #     session_doc['field_metadata'][field_name] = metadata

        except Exception as e:
            logger.error(f"Failed to extract session data: {e}")

        # Categorize fields into logical groups
        return self._categorize_session_fields(session_doc)

    def _extract_record_data(self, fitfile: FitFile, activity_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Extract record-level data with power field handling"""
        records = []
        sequence = 0

        try:
            for record in fitfile.get_messages('record'):
                record_doc = {
                    'activity_id': activity_id,
                    'user_id': user_id,
                    'sequence': sequence
                }

                # Process all fields using clean fitparse approach
                for field_data in record.fields:
                    if field_data.value is not None:
                        # Get field name, processed value, and metadata
                        field_name, processed_value, metadata = self._process_field_with_metadata(field_data)
                        
                        if processed_value is not None:
                            # Store the field value
                            record_doc[field_name] = processed_value
                            
                            # Skip storing metadata for unknown and developer fields to reduce index size
                            # if (metadata['is_unknown'] or metadata['is_developer']) and sequence < 10:
                            #     if 'field_metadata' not in record_doc:
                            #         record_doc['field_metadata'] = {}
                            #     record_doc['field_metadata'][field_name] = metadata

                # Categorize and add to records
                categorized_record = self._categorize_record_fields(record_doc)
                records.append(categorized_record)
                sequence += 1

        except Exception as e:
            logger.error(f"Failed to extract record data: {e}")

        return records

    def _extract_lap_data(self, fitfile: FitFile, activity_id: str, user_id: str, record_docs: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Extract lap-level data"""
        laps = []
        lap_number = 1

        try:
            for record in fitfile.get_messages('lap'):
                lap_doc = {
                    'activity_id': activity_id,
                    'user_id': user_id,
                    'lap_number': lap_number
                }

                # Process all fields using clean fitparse approach
                for field_data in record.fields:
                    if field_data.value is not None:
                        # Get field name, processed value, and metadata
                        field_name, processed_value, metadata = self._process_field_with_metadata(field_data)
                        
                        if processed_value is not None:
                            # Store the field value
                            lap_doc[field_name] = processed_value
                # Categorize and add to laps
                categorized_lap = self._categorize_lap_fields(lap_doc)
                
                # Enhance lap with power statistics from records in this lap
                enhanced_lap = self._enhance_lap_with_power_analysis(categorized_lap, record_docs or [])
                
                laps.append(enhanced_lap)
                lap_number += 1

        except Exception as e:
            logger.error(f"Failed to extract lap data: {e}")

        return laps

    def _is_developer_field(self, field_data) -> bool:
        """Check if a FieldData object represents a developer field"""
        try:
            # Import the DevFieldDefinition class
            from fitparse.records import DevFieldDefinition

            # Check if the field_def attribute is a DevFieldDefinition
            return (hasattr(field_data, 'field_def') and
                    field_data.field_def is not None and
                    isinstance(field_data.field_def, DevFieldDefinition))
        except Exception:
            return False

    def _resolve_developer_field(self, field_data) -> tuple[Optional[str], Any]:
        """Resolve developer field to meaningful name and value"""
        try:
            # Get the field name and value from the FieldData object
            field_name = field_data.name if hasattr(field_data, 'name') else None
            field_value = field_data.value if hasattr(field_data, 'value') else None

            # If we have a proper field name (not unknown_dev_*), use it
            if field_name and not field_name.startswith('unknown_dev_'):
                return field_name, field_value

            # Try to resolve from field_def if it's a DevFieldDefinition
            if hasattr(field_data, 'field_def') and field_data.field_def:
                dev_data_index = getattr(field_data.field_def, 'dev_data_index', None)
                field_definition_number = getattr(field_data.field_def, 'def_num', None)

                if dev_data_index is not None and field_definition_number is not None:
                    # Look up field definition in our cached definitions
                    if (dev_data_index in self.developer_field_defs and
                        field_definition_number in self.developer_field_defs[dev_data_index]):

                        field_info = self.developer_field_defs[dev_data_index][field_definition_number]
                        resolved_name = field_info['name']
                        return resolved_name, field_value

                    # Fallback to generic name
                    return f'dev_field_{dev_data_index}_{field_definition_number}', field_value

            # Fallback to the field name even if it's unknown_dev_*
            return field_name, field_value

        except Exception as e:
            logger.debug(f"Could not resolve developer field: {e}")
            return None, None

    def _normalize_field_name(self, field_name: str) -> str:
        """Normalize field names for consistency"""
        # Handle developer field names with spaces first
        if ' ' in field_name:
            # Convert spaces to underscores and lowercase
            normalized = field_name.lower().replace(' ', '_').replace('-', '_')
            
            # Handle special cases for common developer field names
            if normalized == 'form_power':
                return 'form_power'
            elif normalized == 'air_power':
                return 'air_power'
            elif normalized == 'leg_spring_stiffness':
                return 'leg_spring_stiffness'
            elif normalized == 'ground_time':
                return 'ground_time'
            elif normalized == 'impact_loading_rate':
                return 'impact_loading_rate'
                
        return field_name.lower().replace(' ', '_').replace('-', '_')

    def _format_field_name_for_display(self, field_name: str) -> str:
        """Format field name for snake_case output in categorized data"""
        # Convert to snake_case format for consistent API output
        field_mappings = {
            'power': 'power',
            'form_power': 'form_power',
            'air_power': 'air_power',
            'enhanced_power': 'enhanced_power',
            'normalized_power': 'normalized_power',
            'avg_power': 'power',
            'max_power': 'max_power',

            # Running dynamics - snake_case
            'ground_time': 'ground_time',
            'ground_contact_time': 'ground_contact_time',
            'stance_time': 'stance_time',
            'vertical_oscillation': 'vertical_oscillation',
            'vertical_ratio': 'vertical_ratio',
            'step_length': 'step_length',
            'impact_loading_rate': 'impact_loading_rate',
            'leg_spring_stiffness': 'leg_spring_stiffness',
            'avg_ground_time': 'ground_time',
            'avg_vertical_oscillation': 'vertical_oscillation',
            'avg_vertical_ratio': 'vertical_ratio',
            'avg_step_length': 'step_length',
            'avg_stance_time': 'stance_time'
        }

        normalized_name = self._normalize_field_name(field_name)
        mapped_name = field_mappings.get(normalized_name, normalized_name)
        return self._convert_to_snake_case(mapped_name)

    def _convert_to_snake_case(self, field_name: str) -> str:
        """Convert camelCase and space-separated field names to snake_case"""
        import re
        # First handle space-separated words
        normalized = field_name.replace(' ', '_').lower()
        # Handle camelCase conversion
        normalized = re.sub('([a-z0-9])([A-Z])', r'\1_\2', normalized).lower()
        # Clean up any double underscores
        normalized = re.sub('_+', '_', normalized)
        return normalized

    def _resolve_field_using_global_profile(self, field_data, message_type: str) -> tuple[str, Dict[str, Any]]:
        """Resolve field name using Global FIT Profile definitions"""
        field_name = field_data.name
        field_number = None
        profile_info = {}
        
        # Get field number from fitparse field definition
        if hasattr(field_data, 'field_def') and field_data.field_def:
            try:
                field_number = getattr(field_data.field_def, 'field_def_num', None) or getattr(field_data.field_def, 'def_num', None)
            except Exception:
                field_number = None
        
        # If field is unknown and we have a field number, check Global FIT Profile
        if field_name.startswith('unknown_') and field_number is not None:
            # Try to resolve using Global FIT Profile
            profile_info['field_number'] = field_number
            profile_info['resolved_from_profile'] = False
            
            # For now, we don't have full Global FIT Profile integration
            # Just return the original name
            return field_name, profile_info
        
        # Return original name if not resolved
        profile_info['resolved_from_profile'] = False
        return field_name, profile_info

    def _get_field_metadata(self, field_data, message_type: str = None) -> Dict[str, Any]:
        """Extract comprehensive field metadata including Global FIT Profile information"""
        # Resolve field name using Global FIT Profile
        resolved_name, profile_info = self._resolve_field_using_global_profile(field_data, message_type)
        
        metadata = {
            'original_field_name': field_data.name,
            'resolved_field_name': resolved_name,
            'field_number': None,
            'base_type': None,
            'type_info': None,
            'scale': None,
            'offset': None,
            'units': None,
            'size': None,
            'is_unknown': field_data.name.startswith('unknown_'),
            'is_developer': self._is_developer_field(field_data),
            'profile_info': profile_info
        }
        
        # Extract field definition metadata from fitparse
        if hasattr(field_data, 'field_def') and field_data.field_def:
            field_def = field_data.field_def
            
            # Get field number (the official FIT protocol field number)
            metadata['field_number'] = getattr(field_def, 'def_num', None)
            
            # Get type information
            if hasattr(field_def, 'base_type'):
                metadata['base_type'] = str(field_def.base_type)
            if hasattr(field_def, 'type'):
                metadata['type_info'] = str(field_def.type)
            
            # Get scaling and offset information
            metadata['scale'] = getattr(field_def, 'scale', None)
            metadata['offset'] = getattr(field_def, 'offset', None)
            
            # Get units if available
            metadata['units'] = getattr(field_def, 'units', None)
            
            # Get field size
            metadata['size'] = getattr(field_def, 'size', None)
        
        # Prefer profile information when available
        if profile_info.get('resolved_from_profile'):
            metadata['units'] = profile_info.get('profile_units') or metadata['units']
            metadata['scale'] = profile_info.get('profile_scale') or metadata['scale']
            metadata['offset'] = profile_info.get('profile_offset') or metadata['offset']
        
        return metadata

    def _process_field_with_metadata(self, field_data, message_type: str = None) -> tuple[str, Any, Dict[str, Any]]:
        """Process field and return resolved name, value, and metadata using Global FIT Profile"""
        # Get comprehensive field metadata including Global FIT Profile resolution
        metadata = self._get_field_metadata(field_data, message_type)
        
        # Use the resolved field name from Global FIT Profile
        field_name = metadata['resolved_field_name']
        
        # Process the field value (basic validation only)
        processed_value = self._process_field_value(field_name, field_data.value)
        
        return field_name, processed_value, metadata

    def _process_field_value(self, field_name: str, field_value: Any) -> Any:
        """Process and validate field values"""
        # Skip invalid/sentinel values
        if field_value in [0xFFFF, 0xFF, 65535, 65534, 255]:
            return None

        # Handle timestamp fields
        if 'timestamp' in field_name.lower():
            if hasattr(field_value, 'isoformat'):
                return field_value.isoformat()
            elif isinstance(field_value, (int, float)):
                try:
                    return datetime.fromtimestamp(field_value).isoformat()
                except (ValueError, OSError):
                    return field_value

        # Handle position fields (convert from semicircles to degrees)
        if 'position' in field_name.lower() and isinstance(field_value, int):
            if abs(field_value) > 180:  # Likely in semicircles
                return field_value * (180 / 2**31)

        # Validate power ranges
        if 'power' in field_name.lower() and isinstance(field_value, (int, float)):
            if not (0 <= field_value <= 2000):  # Reasonable power range
                return None

        # Validate heart rate ranges
        if 'heart_rate' in field_name.lower() and isinstance(field_value, (int, float)):
            if not (30 <= field_value <= 220):  # Reasonable HR range
                return None

        return field_value

    def _categorize_session_fields(self, session_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize session fields into logical groups"""
        categorized = {
            'activity_id': session_doc.get('activity_id'),
            'user_id': session_doc.get('user_id'),
            'timestamp': session_doc.get('timestamp'),
            'start_time': session_doc.get('start_time'),
            'sport': session_doc.get('sport'),
            'sub_sport': session_doc.get('sub_sport')
        }

        # Categorize fields
        power_fields = {}
        running_dynamics = {}
        environmental = {}
        additional_fields = {}

        for field_name, field_value in session_doc.items():
            if field_name in ['activity_id', 'user_id', 'timestamp', 'start_time', 'sport', 'sub_sport']:
                continue

            if self._is_power_field(field_name):
                display_name = self._format_field_name_for_display(field_name)
                power_fields[display_name] = field_value
            elif self._is_running_dynamics_field(field_name):
                display_name = self._format_field_name_for_display(field_name)
                running_dynamics[display_name] = field_value
            elif self._is_environmental_field(field_name):
                environmental[field_name] = field_value
            elif self._is_essential_session_field(field_name):
                # Keep essential session fields in main document
                categorized[field_name] = field_value
            else:
                # Other fields go into additional_fields to avoid clutter
                additional_fields[field_name] = field_value

        # Add non-empty categories
        if power_fields:
            categorized['power_fields'] = power_fields
        if running_dynamics:
            categorized['running_dynamics'] = running_dynamics
        if environmental:
            categorized['environmental'] = environmental
        if additional_fields:
            categorized['additional_fields'] = additional_fields

        return categorized

    def _categorize_record_fields(self, record_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize record fields into logical groups"""
        # Similar logic to session categorization but for record-level data
        categorized = {
            'activity_id': record_doc.get('activity_id'),
            'user_id': record_doc.get('user_id'),
            'sequence': record_doc.get('sequence'),
            'timestamp': record_doc.get('timestamp'),
            'elapsed_time': record_doc.get('elapsed_time'),
            'distance': record_doc.get('distance'),
            'speed': record_doc.get('speed') or record_doc.get('enhanced_speed'),
            'heart_rate': record_doc.get('heart_rate'),
            'power': record_doc.get('power')
        }

        # Handle location data
        if 'position_lat' in record_doc and 'position_long' in record_doc:
            categorized['location'] = {
                'lat': record_doc['position_lat'],
                'lon': record_doc['position_long']
            }

        # Categorize other fields
        power_fields = {}
        running_dynamics = {}
        environmental = {}
        # additional_fields = {}  # Skip metadata fields to reduce index size

        for field_name, field_value in record_doc.items():
            if field_name in categorized or field_name.startswith('position_'):
                continue

            if self._is_power_field(field_name) and field_name != 'power':
                display_name = self._format_field_name_for_display(field_name)
                power_fields[display_name] = field_value
            elif self._is_running_dynamics_field(field_name):
                display_name = self._format_field_name_for_display(field_name)
                running_dynamics[display_name] = field_value
            elif self._is_environmental_field(field_name):
                environmental[field_name] = field_value
            # else:
            #     additional_fields[field_name] = field_value  # Skip to reduce index size

        # Add non-empty categories
        if power_fields:
            categorized['power_fields'] = power_fields
        if running_dynamics:
            categorized['running_dynamics'] = running_dynamics
        if environmental:
            categorized['environmental'] = environmental
        # if additional_fields:  # Skip to reduce index size
        #     categorized['additional_fields'] = additional_fields

        return categorized

    def _categorize_lap_fields(self, lap_doc: Dict[str, Any]) -> Dict[str, Any]:
        """Categorize lap fields into logical groups"""
        categorized = {
            'activity_id': lap_doc.get('activity_id'),
            'user_id': lap_doc.get('user_id'),
            'timestamp': lap_doc.get('timestamp'),
            'start_time': lap_doc.get('start_time'),
            'sport': lap_doc.get('sport'),
            'sub_sport': lap_doc.get('sub_sport'),
            'lap_number': lap_doc.get('lap_number')  # Keep lap_number
        }

        # Categorize fields
        power_fields = {}
        running_dynamics = {}
        environmental = {}
        additional_fields = {}

        for field_name, field_value in lap_doc.items():
            if field_name in ['activity_id', 'user_id', 'timestamp', 'start_time', 'sport', 'sub_sport', 'lap_number']:
                continue

            if self._is_power_field(field_name):
                display_name = self._format_field_name_for_display(field_name)
                power_fields[display_name] = field_value
            elif self._is_running_dynamics_field(field_name):
                display_name = self._format_field_name_for_display(field_name)
                running_dynamics[display_name] = field_value
            elif self._is_environmental_field(field_name):
                environmental[field_name] = field_value
            elif self._is_essential_session_field(field_name):
                # Keep essential fields in main document for laps too
                categorized[field_name] = field_value
            else:
                additional_fields[field_name] = field_value

        # Add non-empty categories
        if power_fields:
            categorized['power_fields'] = power_fields
        if running_dynamics:
            categorized['running_dynamics'] = running_dynamics
        if environmental:
            categorized['environmental'] = environmental
        if additional_fields:
            categorized['additional_fields'] = additional_fields

        return categorized

    def _is_power_field(self, field_name: str) -> bool:
        """Check if field is power-related and in our whitelist"""
        field_normalized = self._normalize_field_name(field_name)
        
        # Handle avg_ prefixed fields by removing the prefix for checking
        if field_normalized.startswith('avg_'):
            base_field_name = field_normalized[4:]  # Remove 'avg_' prefix
            return base_field_name in self.ALLOWED_POWER_FIELDS
            
        # Handle max_ prefixed fields by removing the prefix for checking  
        if field_normalized.startswith('max_'):
            base_field_name = field_normalized[4:]  # Remove 'max_' prefix
            return base_field_name in self.ALLOWED_POWER_FIELDS
            
        # Check for power-related keywords even if not in whitelist
        if 'power' in field_normalized and field_normalized not in ['power_position', 'max_power_position', 'avg_power_position']:
            return True
            
        return field_normalized in self.ALLOWED_POWER_FIELDS

    def _is_running_dynamics_field(self, field_name: str) -> bool:
        """Check if field is running dynamics related and in our whitelist"""
        field_normalized = self._normalize_field_name(field_name)
        
        # Handle avg_ prefixed fields by removing the prefix for checking
        if field_normalized.startswith('avg_'):
            base_field_name = field_normalized[4:]  # Remove 'avg_' prefix
            return base_field_name in self.ALLOWED_RUNNING_DYNAMICS_FIELDS
            
        # Handle max_ prefixed fields by removing the prefix for checking
        if field_normalized.startswith('max_'):
            base_field_name = field_normalized[4:]  # Remove 'max_' prefix  
            return base_field_name in self.ALLOWED_RUNNING_DYNAMICS_FIELDS
        
        # Check for running dynamics keywords
        running_dynamics_keywords = [
            'oscillation', 'stance', 'ground', 'contact', 'vertical', 'step_length', 
            'loading', 'stiffness', 'flight', 'form_power'
        ]
        
        # Exclude position, distance, strides and certain other non-dynamics fields
        excluded_fields = [
            'cadence_position', 'max_cadence_position', 'avg_cadence_position',
            'total_distance', 'distance', 'total_strides', 'strides',
            'wkt_step_index', 'message_index', 'fractional_cadence',
            'running_cadence', 'max_running_cadence', 'avg_running_cadence'
        ]
        if field_normalized in excluded_fields:
            return False
            
        # Check if field contains running dynamics keywords
        if any(keyword in field_normalized for keyword in running_dynamics_keywords):
            return True
            
        # Check for specific running dynamics patterns
        if field_normalized in ['step_length', 'avg_step_length', 'max_step_length']:
            return True
        
        return field_normalized in self.ALLOWED_RUNNING_DYNAMICS_FIELDS

    def _is_essential_session_field(self, field_name: str) -> bool:
        """Check if field is essential session information that should be at top level"""
        field_lower = field_name.lower()
        essential_indicators = [
            'distance', 'total_distance', 
            'elapsed_time', 'total_elapsed_time', 'timer_time',
            'calories', 'total_calories',
            'avg_speed', 'max_speed',
            'avg_heart_rate', 'max_heart_rate',
            'total_ascent', 'total_descent',
            'avg_cadence', 'max_cadence',
            'training_stress_score', 'tss',
            'normalized_power', 'np',
            'intensity_factor', 'if',
            'threshold_power', 'ftp'
        ]
        return any(indicator in field_lower for indicator in essential_indicators)

    def _is_environmental_field(self, field_name: str) -> bool:
        """Check if field is environmental data"""
        field_lower = field_name.lower()
        env_indicators = [
            # Standard FIT fields (underscores)
            'temperature', 'humidity', 'pressure', 'wind', 'air', 'baseline', 'stryd_temp',
            'stryd_hum', 'elevation',
            # Developer field names (spaces and variations)
            'stryd temperature', 'stryd humidity', 'baseline temperature', 
            'baseline humidity', 'baseline elevation'
        ]
        return any(indicator in field_lower for indicator in env_indicators)
        return any(indicator in field_lower for indicator in env_indicators)

    def _enhance_with_power_analysis(self, session_doc: Dict[str, Any], record_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance session with comprehensive power and running dynamics analysis from records"""
        if not record_docs:
            return session_doc

        # Collect power and running dynamics data from records
        power_data = {}
        running_dynamics_data = {}
        
        for record in record_docs:
            # Collect main power field if whitelisted
            if 'power' in record and record['power'] is not None:
                if 'power' in self.ALLOWED_POWER_FIELDS:
                    if 'power' not in power_data:
                        power_data['power'] = []
                    power_data['power'].append(record['power'])

            # Collect power fields from categorized data
            if 'power_fields' in record:
                for power_field, value in record['power_fields'].items():
                    if value is not None and self._is_power_field(power_field):
                        if power_field not in power_data:
                            power_data[power_field] = []
                        power_data[power_field].append(value)

            # Collect running dynamics fields
            if 'running_dynamics' in record:
                for rd_field, value in record['running_dynamics'].items():
                    if value is not None and self._is_running_dynamics_field(rd_field):
                        if rd_field not in running_dynamics_data:
                            running_dynamics_data[rd_field] = []
                        running_dynamics_data[rd_field].append(value)

        # Calculate power statistics (avg, min, max)
        if power_data:
            if 'power_fields' not in session_doc:
                session_doc['power_fields'] = {}

            for power_type, values in power_data.items():
                if values:
                    session_doc['power_fields'][f'avg_{power_type}'] = round(sum(values) / len(values), 2)
                    session_doc['power_fields'][f'max_{power_type}'] = max(values)
                    session_doc['power_fields'][f'min_{power_type}'] = min(values)

        # Calculate running dynamics statistics (avg, min, max)
        if running_dynamics_data:
            if 'running_dynamics' not in session_doc:
                session_doc['running_dynamics'] = {}

            for rd_type, values in running_dynamics_data.items():
                if values:
                    session_doc['running_dynamics'][f'avg_{rd_type}'] = round(sum(values) / len(values), 2)
                    session_doc['running_dynamics'][f'max_{rd_type}'] = max(values)
                    session_doc['running_dynamics'][f'min_{rd_type}'] = min(values)

        return session_doc

    def _enhance_lap_with_power_analysis(self, lap_doc: Dict[str, Any], record_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Enhance lap with comprehensive power and running dynamics analysis from records within the lap timeframe"""
        if not record_docs or not lap_doc:
            return lap_doc

        # Get lap timeframe - properly calculate end time
        lap_start_time = lap_doc.get('start_time')
        total_elapsed_time = lap_doc.get('total_elapsed_time')
        lap_end_time = None
        
        # Calculate lap end time properly
        if lap_start_time and total_elapsed_time:
            try:
                # Handle different timestamp formats
                if isinstance(lap_start_time, str):
                    # Parse ISO format string to datetime
                    lap_start_dt = parse_datetime(lap_start_time)
                elif hasattr(lap_start_time, 'isoformat'):
                    # Already a datetime object
                    lap_start_dt = lap_start_time
                else:
                    lap_start_dt = None
                
                if lap_start_dt and isinstance(total_elapsed_time, (int, float)):
                    # Calculate end time by adding elapsed time
                    lap_end_dt = lap_start_dt + timedelta(seconds=total_elapsed_time)
                    lap_end_time = lap_end_dt.isoformat() if hasattr(lap_end_dt, 'isoformat') else str(lap_end_dt)
            except Exception as e:
                logger.debug(f"Could not calculate lap end time: {e}")
                lap_end_time = None
        
        # If we don't have proper lap timing, try to use lap number to estimate record range
        lap_number = lap_doc.get('lap_number', 1)
        
        # Collect power and running dynamics data from records within this lap timeframe
        lap_power_data = {}
        lap_running_dynamics_data = {}
        
        # If we have proper timestamps, filter by time
        if lap_start_time and lap_end_time:
            try:
                # Convert all timestamps to datetime objects for proper comparison
                if isinstance(lap_start_time, str):
                    lap_start_dt = parse_datetime(lap_start_time)
                elif hasattr(lap_start_time, 'isoformat'):
                    lap_start_dt = lap_start_time
                else:
                    lap_start_dt = None
                
                if isinstance(lap_end_time, str):
                    lap_end_dt = parse_datetime(lap_end_time)
                elif hasattr(lap_end_time, 'isoformat'):
                    lap_end_dt = lap_end_time
                else:
                    lap_end_dt = None
                
                if lap_start_dt and lap_end_dt:
                    for record in record_docs:
                        record_time = record.get('timestamp')
                        if record_time:
                            try:
                                # Convert record timestamp to datetime object
                                if isinstance(record_time, str):
                                    record_dt = parse_datetime(record_time)
                                elif hasattr(record_time, 'isoformat'):
                                    record_dt = record_time
                                else:
                                    continue
                                
                                # Use proper datetime comparison instead of string comparison
                                if lap_start_dt <= record_dt <= lap_end_dt:
                                    self._collect_data_from_record(record, lap_power_data, lap_running_dynamics_data)
                            except Exception as e:
                                logger.debug(f"Could not parse record timestamp {record_time}: {e}")
                                continue
            except Exception as e:
                logger.debug(f"Could not parse lap timestamps for comparison: {e}")
                # Fallback to estimation method if timestamp parsing fails
                lap_number = lap_doc.get('lap_number', 1)
                records_per_lap = len(record_docs) // max(1, lap_number) if lap_number > 0 else len(record_docs)
                start_idx = (lap_number - 1) * records_per_lap
                end_idx = min(lap_number * records_per_lap, len(record_docs))
                
                for record in record_docs[start_idx:end_idx]:
                    self._collect_data_from_record(record, lap_power_data, lap_running_dynamics_data)
        else:
            # Fallback: estimate records for this lap (rough approximation)
            records_per_lap = len(record_docs) // max(1, lap_number) if lap_number > 0 else len(record_docs)
            start_idx = (lap_number - 1) * records_per_lap
            end_idx = min(lap_number * records_per_lap, len(record_docs))
            
            for record in record_docs[start_idx:end_idx]:
                self._collect_data_from_record(record, lap_power_data, lap_running_dynamics_data)

        # Calculate power statistics (avg, min, max)
        if lap_power_data:
            if 'power_fields' not in lap_doc:
                lap_doc['power_fields'] = {}

            for power_type, values in lap_power_data.items():
                if values:
                    lap_doc['power_fields'][f'avg_{power_type}'] = round(sum(values) / len(values), 2)
                    lap_doc['power_fields'][f'max_{power_type}'] = max(values)
                    lap_doc['power_fields'][f'min_{power_type}'] = min(values)

        # Calculate running dynamics statistics (avg, min, max)
        if lap_running_dynamics_data:
            if 'running_dynamics' not in lap_doc:
                lap_doc['running_dynamics'] = {}

            for rd_type, values in lap_running_dynamics_data.items():
                if values:
                    lap_doc['running_dynamics'][f'avg_{rd_type}'] = round(sum(values) / len(values), 2)
                    lap_doc['running_dynamics'][f'max_{rd_type}'] = max(values)
                    lap_doc['running_dynamics'][f'min_{rd_type}'] = min(values)

        return lap_doc

    def _collect_data_from_record(self, record: Dict[str, Any], power_data: Dict[str, List[float]], running_dynamics_data: Dict[str, List[float]]) -> None:
        """Helper function to collect power and running dynamics data from a single record"""
        # Collect main power field if whitelisted
        if 'power' in record and record['power'] is not None:
            if 'power' in self.ALLOWED_POWER_FIELDS:
                if 'power' not in power_data:
                    power_data['power'] = []
                power_data['power'].append(record['power'])

        # Collect power fields from categorized data
        if 'power_fields' in record:
            for power_field, value in record['power_fields'].items():
                if value is not None and self._is_power_field(power_field):
                    if power_field not in power_data:
                        power_data[power_field] = []
                    power_data[power_field].append(value)

        # Collect running dynamics fields
        if 'running_dynamics' in record:
            for rd_field, value in record['running_dynamics'].items():
                if value is not None and self._is_running_dynamics_field(rd_field):
                    if rd_field not in running_dynamics_data:
                        running_dynamics_data[rd_field] = []
                    running_dynamics_data[rd_field].append(value)

    def _collect_power_data_from_record(self, record: Dict[str, Any], power_data: Dict[str, List[float]]) -> None:
        """Helper function to collect power data from a single record (deprecated - use _collect_data_from_record)"""
        # Collect main power field
        if 'power' in record and record['power'] is not None:
            if 'power' not in power_data:
                power_data['power'] = []
            power_data['power'].append(record['power'])

        # Collect power fields from categorized data
        if 'power_fields' in record:
            for power_field, value in record['power_fields'].items():
                if value is not None:
                    if power_field not in power_data:
                        power_data[power_field] = []
                    power_data[power_field].append(value)