#!/usr/bin/env python3
"""
Health Processor - Processes FIT files for wellness/health data using Garmin FIT SDK

Enhanced health data processing module that handles:
- Health data extraction using official Garmin FIT SDK
- Wellness, HRV, sleep, stress, and monitoring data processing
- Storage to Elasticsearch health indices with proper field names
- Support for all health-related message types from Garmin devices
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

from garmin_fit_sdk import Decoder, Stream
from ..storage.interface import StorageInterface, IndexingResult, DataType
from ..utils import get_logger

logger = get_logger(__name__)


class HealthProcessor:
    """
    Enhanced health processor using Garmin FIT SDK.
    
    Processes comprehensive health data from FIT files including wellness,
    HRV, sleep, stress levels, and monitoring data with proper field names.
    """

    def __init__(self, storage: StorageInterface):
        self.storage = storage
        
        # Health-related message types from Garmin FIT SDK
        self.health_message_types = {
            # HRV and heart rate variability data
            'hrv_mesgs': DataType.HRV_STATUS,
            'hrv_status_summary_mesgs': DataType.HRV_STATUS,
            'hrv_value_mesgs': DataType.HRV_STATUS,
            'beat_intervals_mesgs': DataType.HRV_STATUS,
            
            # Sleep data
            'sleep_mesgs': DataType.SLEEP_DATA,
            'sleep_data_mesgs': DataType.SLEEP_DATA,
            'sleep_level_mesgs': DataType.SLEEP_DATA,
            'sleep_assessment_mesgs': DataType.SLEEP_DATA,
            
            # Wellness and monitoring data
            'wellness_mesgs': DataType.WELLNESS,
            'monitoring_mesgs': DataType.WELLNESS,
            'daily_summary_mesgs': DataType.WELLNESS,
            'stress_level_mesgs': DataType.WELLNESS,
            'body_battery_mesgs': DataType.WELLNESS,
            'health_snapshot_mesgs': DataType.WELLNESS,
            
            # General metrics
            'metrics_mesgs': DataType.METRICS,
            'user_profile_mesgs': DataType.METRICS,
            
            # Partially decoded messages (still in development)
            '22': DataType.HRV_STATUS,  # HRV metadata
            '227': DataType.WELLNESS,   # Stress level data
        }

    async def process_fit_file(self, fit_file_path: str, user_id: str) -> bool:
        """
        Extract and store health data from FIT file using Garmin FIT SDK.
        
        Args:
            fit_file_path: Path to the FIT file
            user_id: User identifier
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            logger.debug(f"Processing health FIT file with Garmin SDK: {fit_file_path}")
            
            # Parse FIT file using Garmin SDK
            health_data = self._read_health_data_with_sdk(fit_file_path)
            
            if not health_data or not health_data.get('messages'):
                logger.warning(f"No health data found in file: {fit_file_path}")
                return False
            
            if 'error' in health_data:
                logger.error(f"FIT file parsing error: {health_data['error']}")
                return False

            # Process health data by category
            processing_results = []
            
            # Process HRV data
            hrv_results = await self._process_hrv_data(health_data, user_id, fit_file_path)
            processing_results.extend(hrv_results)
            
            # Process sleep data
            sleep_results = await self._process_sleep_data(health_data, user_id, fit_file_path)
            processing_results.extend(sleep_results)
            
            # Process wellness/monitoring data
            wellness_results = await self._process_wellness_data(health_data, user_id, fit_file_path)
            processing_results.extend(wellness_results)
            
            # Process metrics data
            metrics_results = await self._process_metrics_data(health_data, user_id, fit_file_path)
            processing_results.extend(metrics_results)
            
            # Return True if any data was successfully stored
            success = any(result.success_count > 0 for result in processing_results)
            
            if success:
                total_stored = sum(result.success_count for result in processing_results)
                logger.info(f"Successfully processed {total_stored} health records from: {fit_file_path}")
            else:
                logger.warning(f"No health data stored from file: {fit_file_path}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to process health data from FIT file {fit_file_path}: {e}")
            return False

    def _read_health_data_with_sdk(self, fit_file_path: str) -> Dict[str, Any]:
        """
        Read health data from FIT file using Garmin FIT SDK.
        
        Args:
            fit_file_path: Path to FIT file
            
        Returns:
            Dictionary containing parsed health messages
        """
        try:
            logger.debug(f"Reading health data with Garmin SDK from: {fit_file_path}")
            
            # Create stream and decoder
            stream = Stream.from_file(fit_file_path)
            decoder = Decoder(stream)
            
            # Parse messages
            health_data = {
                'messages': [],
                'file_path': fit_file_path,
                'file_size': Path(fit_file_path).stat().st_size,
                'parsed_at': datetime.now(timezone.utc).isoformat()
            }
            
            message_count = 0
            health_message_count = 0
            
            messages, errors = decoder.read()
            
            if errors:
                logger.warning(f"FIT file parsing errors: {errors}")
            
            for message_type, message_list in messages.items():
                message_count += len(message_list)
                
                # Check if this is a health-related message type
                if message_type in self.health_message_types:
                    health_message_count += len(message_list)
                    logger.debug(f"Found {len(message_list)} {message_type} messages")
                    
                    for message_data in message_list:
                        # Convert message to our format
                        processed_message = self._convert_sdk_message(message_type, message_data)
                        if processed_message:
                            health_data['messages'].append(processed_message)
            
            health_data['total_messages'] = message_count
            health_data['health_messages'] = health_message_count
            
            logger.info(f"Processed {message_count} total messages, {health_message_count} health messages from {Path(fit_file_path).name}")
            
            return health_data
            
        except Exception as e:
            logger.error(f"Failed to read FIT file with Garmin SDK {fit_file_path}: {e}")
            return {
                'messages': [],
                'error': str(e),
                'file_path': fit_file_path,
                'parsed_at': datetime.now(timezone.utc).isoformat()
            }

    def _convert_sdk_message(self, message_type: str, message_data: Dict) -> Optional[Dict[str, Any]]:
        """
        Convert Garmin SDK message to standardized format.
        
        Args:
            message_type: Type of message from SDK
            message_data: Raw message data from SDK
            
        Returns:
            Standardized message dictionary
        """
        try:
            # Create standardized message
            converted_message = {
                'message_type': message_type,
                'sdk_source': 'garmin_fit_sdk'
            }
            
            # Process all fields in the message
            for field_name, field_value in message_data.items():
                if field_value is not None:
                    # Handle different field types
                    if isinstance(field_value, datetime):
                        converted_message[field_name] = field_value.isoformat()
                    elif isinstance(field_value, (int, float, str, bool)):
                        converted_message[field_name] = field_value
                    elif isinstance(field_value, list):
                        # Handle array fields
                        converted_message[field_name] = field_value
                    else:
                        # Convert other types to string
                        converted_message[field_name] = str(field_value)
            
            return converted_message
            
        except Exception as e:
            logger.warning(f"Error converting SDK message {message_type}: {e}")
            return None

    async def _process_hrv_data(self, health_data: Dict, user_id: str, file_path: str) -> List[IndexingResult]:
        """Process HRV-related messages."""
        hrv_message_types = ['hrv_mesgs', 'hrv_status_summary_mesgs', 'hrv_value_mesgs', 'beat_intervals_mesgs', '22']
        results = []
        
        for msg_type in hrv_message_types:
            records = self._extract_messages_by_type(health_data, msg_type, user_id, file_path, 'hrv_data')
            if records:
                logger.info(f"Processing {len(records)} {msg_type} records")
                result = await self._store_health_data(records, DataType.HRV_STATUS, msg_type)
                results.append(result)
        
        return results

    async def _process_sleep_data(self, health_data: Dict, user_id: str, file_path: str) -> List[IndexingResult]:
        """Process sleep-related messages."""
        sleep_message_types = ['sleep_mesgs', 'sleep_data_mesgs', 'sleep_level_mesgs', 'sleep_assessment_mesgs']
        results = []
        
        for msg_type in sleep_message_types:
            records = self._extract_messages_by_type(health_data, msg_type, user_id, file_path, 'sleep_data')
            if records:
                logger.info(f"Processing {len(records)} {msg_type} records")
                result = await self._store_health_data(records, DataType.SLEEP_DATA, msg_type)
                results.append(result)
        
        return results

    async def _process_wellness_data(self, health_data: Dict, user_id: str, file_path: str) -> List[IndexingResult]:
        """Process wellness and monitoring messages."""
        wellness_message_types = [
            'wellness_mesgs', 'monitoring_mesgs', 'daily_summary_mesgs', 
            'stress_level_mesgs', 'body_battery_mesgs', 'health_snapshot_mesgs', '227'
        ]
        results = []
        
        for msg_type in wellness_message_types:
            records = self._extract_messages_by_type(health_data, msg_type, user_id, file_path, 'wellness')
            if records:
                logger.info(f"Processing {len(records)} {msg_type} records")
                result = await self._store_health_data(records, DataType.WELLNESS, msg_type)
                results.append(result)
        
        return results

    async def _process_metrics_data(self, health_data: Dict, user_id: str, file_path: str) -> List[IndexingResult]:
        """Process general health metrics messages."""
        metrics_message_types = ['metrics_mesgs', 'user_profile_mesgs']
        results = []
        
        for msg_type in metrics_message_types:
            records = self._extract_messages_by_type(health_data, msg_type, user_id, file_path, 'metrics')
            if records:
                logger.info(f"Processing {len(records)} {msg_type} records")
                result = await self._store_health_data(records, DataType.METRICS, msg_type)
                results.append(result)
        
        return results

    def _extract_messages_by_type(self, health_data: Dict, message_type: str, user_id: str, 
                                 file_path: str, health_category: str) -> List[Dict]:
        """Extract messages of a specific type and create health records."""
        records = []
        
        try:
            messages = health_data.get('messages', [])
            
            for message in messages:
                if message.get('message_type') == message_type:
                    record = self._create_health_record(
                        user_id=user_id,
                        file_path=file_path,
                        health_category=health_category,
                        message_type=message_type,
                        data=message
                    )
                    records.append(record)
                    
        except Exception as e:
            logger.error(f"Error extracting {message_type} data: {e}")
            
        return records

    def _create_health_record(self, user_id: str, file_path: str, health_category: str, 
                             message_type: str, data: Dict) -> Dict:
        """Create a health record document with proper field mapping."""
        # Extract timestamp from properly decoded SDK data
        timestamp = self._extract_timestamp(data)
        
        # Create base record structure
        record = {
            'user_id': user_id,
            'file_type': 'health_data',
            'health_category': health_category,
            'message_type': message_type,
            'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            'parsed_at': datetime.now(timezone.utc).isoformat(),
            'source_file': Path(file_path).name,
            'sdk_source': 'garmin_fit_sdk'
        }
        
        # Add specific classification based on message type
        if 'hrv' in message_type.lower():
            if 'summary' in message_type.lower():
                record['hrv_data_type'] = 'summary'
            elif 'value' in message_type.lower():
                record['hrv_data_type'] = 'measurement'
            elif 'beat' in message_type.lower():
                record['hrv_data_type'] = 'beat_intervals'
            else:
                record['hrv_data_type'] = 'timeseries'
        
        # Add all decoded fields from SDK
        for key, value in data.items():
            if key not in ['message_type', 'sdk_source'] and value is not None:
                # Clean field values
                cleaned_value = self._clean_field_value(value)
                if cleaned_value is not None:
                    record[key] = cleaned_value
        
        return record

    def _extract_timestamp(self, message: Dict) -> datetime:
        """Extract timestamp from properly decoded SDK message fields."""
        # Try standard timestamp field first (properly decoded by SDK)
        if 'timestamp' in message and message['timestamp'] is not None:
            timestamp_value = message['timestamp']
            
            if isinstance(timestamp_value, datetime):
                # Ensure timezone-aware datetime
                if timestamp_value.tzinfo is None:
                    return timestamp_value.replace(tzinfo=timezone.utc)
                return timestamp_value
            elif isinstance(timestamp_value, str):
                # Parse ISO format timestamp
                try:
                    # Handle various ISO format variations
                    clean_timestamp = timestamp_value.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(clean_timestamp)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    # Try parsing as standard datetime formats
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                        try:
                            dt = datetime.strptime(timestamp_value, fmt)
                            return dt.replace(tzinfo=timezone.utc)
                        except ValueError:
                            continue
                    logger.debug(f"Failed to parse timestamp string: {timestamp_value}")
            elif isinstance(timestamp_value, (int, float)):
                # Handle numeric timestamp (Garmin epoch)
                try:
                    garmin_epoch_offset = 631065600  # seconds from 1970-01-01 to 1989-12-31
                    unix_timestamp = timestamp_value + garmin_epoch_offset
                    return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                except (ValueError, OSError, OverflowError):
                    logger.debug(f"Failed to convert Garmin timestamp {timestamp_value}")
        
        # Try other common timestamp fields from Garmin SDK
        timestamp_fields = [
            'local_timestamp', 'time_created', 'system_timestamp', 
            'start_time', 'end_time', 'creation_time',
            'stress_level_time', 'hrv_time', 'sleep_time', 'body_battery_time',
            'timestamp_16'
        ]
        for field in timestamp_fields:
            if field in message and message[field] is not None:
                timestamp_value = message[field]
                if isinstance(timestamp_value, datetime):
                    if timestamp_value.tzinfo is None:
                        return timestamp_value.replace(tzinfo=timezone.utc)
                    return timestamp_value
                elif isinstance(timestamp_value, str):
                    # Parse ISO format timestamp for secondary fields
                    try:
                        clean_timestamp = timestamp_value.replace('Z', '+00:00')
                        dt = datetime.fromisoformat(clean_timestamp)
                        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                    except ValueError:
                        # Try parsing as standard datetime formats
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d']:
                            try:
                                dt = datetime.strptime(timestamp_value, fmt)
                                return dt.replace(tzinfo=timezone.utc)
                            except ValueError:
                                continue
                        logger.debug(f"Failed to parse {field} timestamp string: {timestamp_value}")
                elif isinstance(timestamp_value, (int, float)):
                    try:
                        garmin_epoch_offset = 631065600
                        unix_timestamp = timestamp_value + garmin_epoch_offset
                        return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                    except (ValueError, OSError, OverflowError):
                        logger.debug(f"Failed to convert {field} timestamp {timestamp_value}")
        
        # For numeric timestamp fields using Garmin field IDs
        timestamp_field_ids = ['253', '1', '2', '3', '4']  # 253=standard timestamp, 1=legacy, 2-4=stress/wellness specific
        for field_id in timestamp_field_ids:
            # Check both string and integer keys
            field_keys = [field_id, int(field_id)]
            for key in field_keys:
                if key in message and isinstance(message[key], (int, float)):
                    timestamp_value = message[key]
                    try:
                        # Handle different epoch bases
                        if timestamp_value > 1000000000:  # Likely Unix timestamp
                            return datetime.fromtimestamp(timestamp_value, tz=timezone.utc)
                        else:  # Likely Garmin epoch
                            garmin_epoch_offset = 631065600
                            unix_timestamp = timestamp_value + garmin_epoch_offset
                            return datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                    except (ValueError, OSError, OverflowError):
                        logger.debug(f"Failed to convert field {key} timestamp {timestamp_value}")
                    break  # Found a valid field, stop checking other keys for this field_id
        
        # Try to extract date information from other fields and combine with midnight time
        date_fields = ['date', 'day', 'activity_date']
        for field in date_fields:
            if field in message and message[field] is not None:
                date_value = message[field]
                try:
                    if isinstance(date_value, datetime):
                        return date_value.replace(tzinfo=timezone.utc) if date_value.tzinfo is None else date_value
                    elif isinstance(date_value, str):
                        # Try parsing various date formats
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']:
                            try:
                                parsed_date = datetime.strptime(date_value, fmt)
                                return parsed_date.replace(tzinfo=timezone.utc)
                            except ValueError:
                                continue
                except (ValueError, TypeError):
                    logger.debug(f"Failed to parse date field {field}: {date_value}")
        
        # Check if this is monitoring data that might have a default pattern
        message_type = message.get('message_type', '')
        if any(term in message_type.lower() for term in ['monitoring', 'wellness', 'daily']):
            # For daily wellness data, try to use midnight of a reasonable date
            # Look for any numeric fields that might represent days since epoch
            for key, value in message.items():
                if isinstance(value, (int, float)) and 10000 < value < 50000:  # Reasonable range for days since 1970
                    try:
                        base_date = datetime(1970, 1, 1, tzinfo=timezone.utc)
                        calculated_date = base_date + timedelta(days=int(value))
                        if 2020 <= calculated_date.year <= 2030:  # Sanity check
                            logger.debug(f"Using calculated date from field {key}: {calculated_date}")
                            return calculated_date
                    except (ValueError, OverflowError):
                        continue
        
        # Last resort: use current time but log more details for debugging
        logger.warning(f"No valid timestamp found in SDK message (type: {message.get('message_type', 'unknown')}, keys: {list(message.keys())[:10]}), using current time")
        return datetime.now(timezone.utc)

    def _clean_field_value(self, value: Any) -> Any:
        """Clean and validate field values for storage."""
        if value is None:
            return None
            
        # Convert datetime objects to ISO format
        if isinstance(value, datetime):
            return value.isoformat()
        
        # Validate numeric values
        elif isinstance(value, (int, float)):
            # Avoid NaN and infinite values
            if str(value).lower() in ['nan', 'inf', '-inf']:
                return None
            return value
        
        # Clean strings
        elif isinstance(value, str):
            cleaned_value = value.replace('\x00', '').strip()
            return cleaned_value if cleaned_value else None
        
        # Keep boolean values as-is
        elif isinstance(value, bool):
            return value
        
        # Keep lists as-is (for array fields)
        elif isinstance(value, list):
            return value
        
        # Convert other types to string
        else:
            str_value = str(value).replace('\x00', '').strip()
            return str_value if str_value and str_value not in ['None', 'null'] else None

    async def _store_health_data(self, records: List[Dict], data_type: DataType, 
                                message_type: str) -> IndexingResult:
        """Store health records to appropriate Elasticsearch index."""
        try:
            logger.info(f"Storing {len(records)} {message_type} records to Elasticsearch")
            
            result = self.storage.bulk_index(data_type, records)
            
            if result.success_count > 0:
                logger.info(f"Successfully stored {result.success_count} {message_type} records")
            
            if result.failed_count > 0:
                logger.warning(f"Failed to store {result.failed_count} {message_type} records")
                for error in result.errors:
                    logger.error(f"Storage error: {error}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to store {message_type} records: {e}")
            result = IndexingResult()
            result.add_failure(len(records), str(e))
            return result

    def get_file_summary(self, fit_file_path: str) -> Dict[str, Any]:
        """Get a summary of health content in a FIT file using Garmin SDK."""
        try:
            stream = Stream.from_file(fit_file_path)
            decoder = Decoder(stream)
            
            messages, errors = decoder.read()
            
            health_message_types = {}
            total_messages = 0
            
            for message_type, message_list in messages.items():
                total_messages += len(message_list)
                if message_type in self.health_message_types:
                    health_message_types[message_type] = len(message_list)
            
            return {
                'file_path': fit_file_path,
                'file_size': Path(fit_file_path).stat().st_size,
                'total_messages': total_messages,
                'health_message_types': health_message_types,
                'is_health_file': len(health_message_types) > 0,
                'parsing_errors': errors,
                'sdk_source': 'garmin_fit_sdk'
            }
            
        except Exception as e:
            logger.error(f"Error getting SDK file summary for {fit_file_path}: {e}")
            return {
                'file_path': fit_file_path,
                'error': str(e),
                'is_health_file': self.is_health_file(fit_file_path),
                'sdk_source': 'garmin_fit_sdk'
            }

    def is_health_file(self, fit_file_path: str) -> bool:
        """Check if FIT file contains health data based on filename patterns."""
        filename = Path(fit_file_path).name.upper()
        
        health_indicators = [
            'WELLNESS', 'SLEEP', 'HRV', 'METRICS', 'MONITORING',
            'BODY_BATTERY', 'STRESS', 'HEALTH', 'DAILY_SUMMARY'
        ]
        
        return any(indicator in filename for indicator in health_indicators)