#!/usr/bin/env python3
"""
HRV Processor using Garmin FIT SDK - Enhanced HRV processing with proper field definitions

This processor uses the official Garmin FIT SDK to properly decode HRV data fields
instead of relying on reverse-engineered "unknown_" field mappings.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

from garmin_fit_sdk import Decoder, Stream
from ..storage.interface import StorageInterface, IndexingResult
from ..utils import get_logger

logger = get_logger(__name__)


class GarminHRVProcessor:
    """
    HRV processor using official Garmin FIT SDK.
    
    Processes HRV data from FIT files using proper field definitions from
    the Garmin FIT SDK instead of reverse-engineered unknown field mappings.
    
    Supported HRV message types:
    - hrv (78): Heart rate variability time series data
    - hrv_status_summary (370): HRV summary statistics  
    - hrv_value (371): Individual 5-minute RMSSD measurements
    - beat_intervals (290): Raw beat-to-beat intervals
    """

    def __init__(self, storage: StorageInterface):
        self.storage = storage
        
        # HRV message types from Garmin FIT SDK (using _mesgs suffix as returned by SDK)
        self.hrv_message_types = {
            'hrv_mesgs',                    # Message 78: Time series HRV data
            'hrv_status_summary_mesgs',     # Message 370: HRV summary statistics  
            'hrv_value_mesgs',              # Message 371: Individual RMSSD measurements
            'beat_intervals_mesgs',         # Message 290: Raw R-R intervals
            '22',                           # Message 22: HRV metadata (not fully decoded)
        }

    async def process_fit_file(self, fit_file_path: str, user_id: str) -> bool:
        """
        Process HRV data from FIT file using Garmin FIT SDK.
        
        Args:
            fit_file_path: Path to the FIT file
            user_id: User identifier
            
        Returns:
            bool: True if processing succeeded, False otherwise
        """
        try:
            logger.debug(f"Processing HRV FIT file with Garmin SDK: {fit_file_path}")
            
            # Parse FIT file using Garmin SDK
            hrv_data = self._read_hrv_data_with_sdk(fit_file_path)
            
            if not hrv_data or not hrv_data.get('messages'):
                logger.warning(f"No HRV data found in file: {fit_file_path}")
                return False
            
            if 'error' in hrv_data:
                logger.error(f"FIT file parsing error: {hrv_data['error']}")
                return False

            # Extract and categorize HRV data
            hrv_summary_records = self._extract_hrv_summary_data(hrv_data, user_id, fit_file_path)
            hrv_measurement_records = self._extract_hrv_measurement_data(hrv_data, user_id, fit_file_path)
            hrv_timeseries_records = self._extract_hrv_timeseries_data(hrv_data, user_id, fit_file_path)
            beat_interval_records = self._extract_beat_interval_data(hrv_data, user_id, fit_file_path)
            
            # Store all HRV data
            results = []
            
            if hrv_summary_records:
                logger.info(f"Processing {len(hrv_summary_records)} HRV summary records")
                result = await self._store_hrv_data(hrv_summary_records, "hrv_summary")
                results.append(result)
            
            if hrv_measurement_records:
                logger.info(f"Processing {len(hrv_measurement_records)} HRV measurement records")
                result = await self._store_hrv_data(hrv_measurement_records, "hrv_measurements")
                results.append(result)
                
            if hrv_timeseries_records:
                logger.info(f"Processing {len(hrv_timeseries_records)} HRV timeseries records")
                result = await self._store_hrv_data(hrv_timeseries_records, "hrv_timeseries")
                results.append(result)
                
            if beat_interval_records:
                logger.info(f"Processing {len(beat_interval_records)} beat interval records")
                result = await self._store_hrv_data(beat_interval_records, "beat_intervals")
                results.append(result)
            
            # Return True if any data was successfully stored
            success = any(result.success_count > 0 for result in results)
            
            if success:
                logger.info(f"Successfully processed HRV data using Garmin SDK from: {fit_file_path}")
            else:
                logger.warning(f"No HRV data stored from file: {fit_file_path}")
                
            return success
            
        except Exception as e:
            logger.error(f"Failed to process HRV data with Garmin SDK from {fit_file_path}: {e}")
            return False

    def _read_hrv_data_with_sdk(self, fit_file_path: str) -> Dict[str, Any]:
        """
        Read HRV data from FIT file using Garmin FIT SDK.
        
        Args:
            fit_file_path: Path to FIT file
            
        Returns:
            Dictionary containing parsed HRV messages
        """
        try:
            logger.debug(f"Reading HRV data with Garmin SDK from: {fit_file_path}")
            
            # Create stream and decoder
            stream = Stream.from_file(fit_file_path)
            decoder = Decoder(stream)
            
            # Parse messages
            hrv_data = {
                'messages': [],
                'file_path': fit_file_path,
                'file_size': Path(fit_file_path).stat().st_size,
                'parsed_at': datetime.now(timezone.utc).isoformat()
            }
            
            message_count = 0
            hrv_message_count = 0
            
            messages, errors = decoder.read()
            
            if errors:
                logger.warning(f"FIT file parsing errors: {errors}")
            
            for message_type, message_list in messages.items():
                message_count += len(message_list)
                
                # Check if this is an HRV-related message type
                if message_type in self.hrv_message_types:
                    hrv_message_count += len(message_list)
                    logger.debug(f"Found {len(message_list)} {message_type} messages")
                    
                    for message_data in message_list:
                        # Convert message to our format
                        processed_message = self._convert_sdk_message(message_type, message_data)
                        if processed_message:
                            hrv_data['messages'].append(processed_message)
            
            hrv_data['total_messages'] = message_count
            hrv_data['hrv_messages'] = hrv_message_count
            
            logger.info(f"Processed {message_count} total messages, {hrv_message_count} HRV messages from {Path(fit_file_path).name}")
            
            return hrv_data
            
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
        Convert Garmin SDK message to our standardized format.
        
        Args:
            message_type: Type of message (hrv, hrv_status_summary, etc.)
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
                        # Handle array fields (e.g., time arrays in HRV messages)
                        converted_message[field_name] = field_value
                    else:
                        # Convert other types to string
                        converted_message[field_name] = str(field_value)
            
            return converted_message
            
        except Exception as e:
            logger.warning(f"Error converting SDK message {message_type}: {e}")
            return None

    def _extract_hrv_summary_data(self, hrv_data: Dict, user_id: str, file_path: str) -> List[Dict]:
        """
        Extract HRV summary data (hrv_status_summary_mesgs).
        
        Contains weekly averages, baselines, and status information.
        """
        summary_records = []
        
        try:
            messages = hrv_data.get('messages', [])
            
            for message in messages:
                if message.get('message_type') == 'hrv_status_summary_mesgs':
                    record = self._create_hrv_record(
                        user_id=user_id,
                        file_path=file_path,
                        hrv_data_type='summary',
                        message_type='hrv_status_summary',
                        data=message
                    )
                    summary_records.append(record)
                    
        except Exception as e:
            logger.error(f"Error extracting HRV summary data: {e}")
            
        return summary_records

    def _extract_hrv_measurement_data(self, hrv_data: Dict, user_id: str, file_path: str) -> List[Dict]:
        """
        Extract individual HRV measurements (hrv_value_mesgs).
        
        Contains 5-minute RMSSD values during monitoring periods.
        """
        measurement_records = []
        
        try:
            messages = hrv_data.get('messages', [])
            
            for message in messages:
                if message.get('message_type') == 'hrv_value_mesgs':
                    record = self._create_hrv_record(
                        user_id=user_id,
                        file_path=file_path,
                        hrv_data_type='measurement',
                        message_type='hrv_value',
                        data=message
                    )
                    measurement_records.append(record)
                    
        except Exception as e:
            logger.error(f"Error extracting HRV measurement data: {e}")
            
        return measurement_records

    def _extract_hrv_timeseries_data(self, hrv_data: Dict, user_id: str, file_path: str) -> List[Dict]:
        """
        Extract HRV time series data (hrv_mesgs).
        
        Contains arrays of time intervals between beats.
        """
        timeseries_records = []
        
        try:
            messages = hrv_data.get('messages', [])
            
            for message in messages:
                if message.get('message_type') == 'hrv_mesgs':
                    record = self._create_hrv_record(
                        user_id=user_id,
                        file_path=file_path,
                        hrv_data_type='timeseries',
                        message_type='hrv',
                        data=message
                    )
                    timeseries_records.append(record)
                    
        except Exception as e:
            logger.error(f"Error extracting HRV timeseries data: {e}")
            
        return timeseries_records

    def _extract_beat_interval_data(self, hrv_data: Dict, user_id: str, file_path: str) -> List[Dict]:
        """
        Extract raw beat interval data (beat_intervals_mesgs and message '22').
        
        Contains raw R-R interval measurements and metadata.
        """
        beat_records = []
        
        try:
            messages = hrv_data.get('messages', [])
            
            for message in messages:
                message_type = message.get('message_type')
                if message_type in ['beat_intervals_mesgs', '22']:
                    # Use appropriate data type for different message types
                    data_type = 'beat_intervals' if message_type == 'beat_intervals_mesgs' else 'metadata'
                    
                    record = self._create_hrv_record(
                        user_id=user_id,
                        file_path=file_path,
                        hrv_data_type=data_type,
                        message_type=message_type,
                        data=message
                    )
                    beat_records.append(record)
                    
        except Exception as e:
            logger.error(f"Error extracting beat interval data: {e}")
            
        return beat_records

    def _create_hrv_record(self, user_id: str, file_path: str, hrv_data_type: str, 
                          message_type: str, data: Dict) -> Dict:
        """
        Create an HRV record document using properly decoded field names.
        """
        # Extract timestamp (properly decoded from SDK)
        timestamp = self._extract_timestamp(data)
        
        # Create base record structure
        record = {
            'user_id': user_id,
            'file_type': 'hrv_status',
            'hrv_data_type': hrv_data_type,
            'message_type': message_type,
            'timestamp': timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
            'parsed_at': datetime.now(timezone.utc).isoformat(),
            'source_file': Path(file_path).name,
            'sdk_source': 'garmin_fit_sdk'
        }
        
        # Add all decoded fields directly
        for key, value in data.items():
            if key not in ['message_type', 'sdk_source'] and value is not None:
                record[key] = value
        
        return record

    def _extract_timestamp(self, message: Dict) -> datetime:
        """Extract timestamp from properly decoded message fields"""
        # Try standard timestamp field first (properly decoded)
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
                    dt = datetime.fromisoformat(timestamp_value.replace('Z', '+00:00'))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        
        # Fallback to current time if no valid timestamp found
        logger.warning("No valid timestamp found in SDK message, using current time")
        return datetime.now(timezone.utc)

    async def _store_hrv_data(self, records: List[Dict], data_category: str) -> IndexingResult:
        """
        Store HRV records to Elasticsearch using appropriate indices.
        """
        try:
            logger.info(f"Storing {len(records)} {data_category} records to Elasticsearch")
            
            # All HRV data goes to HRV_STATUS index for now
            from ..storage.interface import DataType
            
            result = self.storage.bulk_index(DataType.HRV_STATUS, records)
            
            if result.success_count > 0:
                logger.info(f"Successfully stored {result.success_count} {data_category} records")
            
            if result.failed_count > 0:
                logger.warning(f"Failed to store {result.failed_count} {data_category} records")
                for error in result.errors:
                    logger.error(f"Storage error: {error}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to store {data_category} records: {e}")
            result = IndexingResult()
            result.add_failure(len(records), str(e))
            return result

    def get_file_summary(self, fit_file_path: str) -> Dict[str, Any]:
        """
        Get a summary of HRV content in a FIT file using Garmin SDK.
        """
        try:
            stream = Stream.from_file(fit_file_path)
            decoder = Decoder(stream)
            
            messages, errors = decoder.read()
            
            hrv_message_types = {}
            total_messages = 0
            
            for message_type, message_list in messages.items():
                total_messages += len(message_list)
                if message_type in self.hrv_message_types:
                    hrv_message_types[message_type] = len(message_list)
            
            return {
                'file_path': fit_file_path,
                'file_size': Path(fit_file_path).stat().st_size,
                'total_messages': total_messages,
                'hrv_message_types': hrv_message_types,
                'is_hrv_file': len(hrv_message_types) > 0,
                'parsing_errors': errors,
                'sdk_source': 'garmin_fit_sdk'
            }
            
        except Exception as e:
            logger.error(f"Error getting SDK file summary for {fit_file_path}: {e}")
            return {
                'file_path': fit_file_path,
                'error': str(e),
                'is_hrv_file': self.is_hrv_file(fit_file_path),
                'sdk_source': 'garmin_fit_sdk'
            }

    def is_hrv_file(self, fit_file_path: str) -> bool:
        """
        Check if FIT file contains HRV data based on filename patterns.
        """
        filename = Path(fit_file_path).name.upper()
        
        hrv_indicators = [
            'HRV', 'HEART_RATE_VAR', 'HRV_STATUS', 'BEAT_INTERVALS'
        ]
        
        return any(indicator in filename for indicator in hrv_indicators)