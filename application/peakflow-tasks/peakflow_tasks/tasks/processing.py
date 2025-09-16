"""
FIT file processing tasks for PeakFlow Tasks.

This module contains Celery tasks for processing FIT files and storing
the extracted data in Elasticsearch.
"""

import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# from ..base_tasks import BaseProcessingTask  # Temporarily disabled
from ..exceptions import FitProcessingError, StorageError, ValidationError
from ..celery_app import celery_app
from ..config import get_elasticsearch_config
# Import PeakFlow modules
try:
    from peakflow.processors.activity import ActivityProcessor
    from peakflow.processors.health import HealthProcessor
    from peakflow.storage.elasticsearch import ElasticsearchStorage
    from peakflow.processors.interface import ProcessingStatus
    from peakflow.storage import DataType
    from peakflow.storage.elasticsearch import QueryFilter
except ImportError as e:
    raise ImportError(f"Failed to import PeakFlow modules: {e}")

logger = logging.getLogger(__name__)


def detect_fit_file_type(file_path: str) -> str:
    """
    Detect FIT file type based on filename patterns.
    
    Args:
        file_path: Path to FIT file
        
    Returns:
        'health' or 'activity'
    """
    filename = Path(file_path).name.upper()
    health_indicators = [
        'WELLNESS', 'SLEEP', 'HRV', 'METRICS', 'MONITORING',
        'BODY_BATTERY', 'STRESS', 'HEALTH'
    ]
    
    is_health_file = any(indicator in filename for indicator in health_indicators)
    return 'health' if is_health_file else 'activity'


def process_fit_file_helper(file_path: str, user_id: str, activity_id: str = None,
                           validate_only: bool = False, auto_detect_type: bool = True):
    """
    Helper function to route FIT file processing to appropriate task without blocking.
    Returns the appropriate task signature for async execution.
    
    Args:
        file_path: Path to FIT file
        user_id: User identifier
        activity_id: Activity identifier (optional for health files)
        validate_only: Only validate, don't store data
        auto_detect_type: Auto-detect file type (health vs activity)
        
    Returns:
        Celery signature for the appropriate processing task
    """
    # Check if file exists first
    if not Path(file_path).exists():
        raise FileNotFoundError(f"FIT file not found: {file_path}")
    
    if auto_detect_type:
        file_type = detect_fit_file_type(file_path)
        
        if file_type == 'health':
            logger.info(f"Detected health file: {file_path}")
            return process_health_fit_file.s(file_path, user_id)
        else:
            logger.info(f"Detected activity file: {file_path}")
            # Require activity_id for activity files
            if not activity_id:
                raise FitProcessingError("Activity ID is required for activity FIT files")
            return process_activity_fit_file.s(file_path, user_id, activity_id, validate_only)
    else:
        # Default to activity processing if auto-detection is disabled
        if not activity_id:
            raise FitProcessingError("Activity ID is required when auto-detection is disabled")
        return process_activity_fit_file.s(file_path, user_id, activity_id, validate_only)


# Task configuration
TASK_CONFIG = {
    "process_activity_fit_file": {
        "time_limit": 300,   # 5 minutes
        "soft_time_limit": 240,
        "retry_delay": 30,
        "max_retries": 2
    },
    "process_health_fit_file": {
        "time_limit": 300,   # 5 minutes
        "soft_time_limit": 240,
        "retry_delay": 30,
        "max_retries": 2
    },
    "process_fit_file_batch": {
        "time_limit": 1800,  # 30 minutes
        "soft_time_limit": 1500,
        "retry_delay": 60,
        "max_retries": 2
    },
    "validate_processed_data": {
        "time_limit": 120,   # 2 minutes
        "soft_time_limit": 90,
        "retry_delay": 15,
        "max_retries": 3
    }
}


@celery_app.task(bind=True, **TASK_CONFIG["process_activity_fit_file"])
def process_activity_fit_file(self, file_path: str, user_id: str, activity_id: str,
                             validate_only: bool = False) -> Dict[str, Any]:
    """
    Process a single activity FIT file and store results in Elasticsearch.
    
    Args:
        file_path: Path to activity FIT file
        user_id: User identifier  
        activity_id: Activity identifier
        validate_only: Only validate, don't store data
        
    Returns:
        Dict containing processing results
        
    Raises:
        FileNotFoundError: FIT file not found
        FitProcessingError: Processing failed
        StorageError: Storage operation failed
    """
    try:
        # Initialize progress
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'validating', 'progress': 0}
        )
        
        logger.info(f"Processing FIT file {file_path} for user {user_id}, activity {activity_id}")
        
        # Validate file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"FIT file not found: {file_path}")
            
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        # Initialize processor
        processor = ActivityProcessor(storage)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'processing', 'progress': 20}
        )
        
        # Process FIT file (this includes indexing to Elasticsearch)
        result = processor.process(file_path, user_id, activity_id)
        
        # Update progress
        self.update_state(
            state='PROGRESS', 
            meta={'stage': 'indexing_completed', 'progress': 80}
        )
        
        # Format results
        processing_result = {
            'file_path': file_path,
            'user_id': user_id,
            'activity_id': activity_id,
            'status': result.status.value if hasattr(result.status, 'value') else str(result.status),
            'successful_records': result.successful_records,
            'failed_records': result.failed_records,
            'total_records': result.total_records,
            'processing_time': result.processing_time,
            'errors': result.errors,
            'warnings': result.warnings,
            'metadata': result.metadata,
            'processed_at': datetime.now().isoformat()
        }
        
        # Queue analytics generation if processing successful (but not in validation-only mode)
        status_value = result.status.value if hasattr(result.status, 'value') else str(result.status)
        if not validate_only and status_value in ['completed', 'partially_completed']:
            # Activity summary generation removed
            pass
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'records_processed': result.successful_records
            }
        )
        
        logger.info(f"✅ Processed FIT file {file_path}: {result.successful_records} records")
        return processing_result
        
    except FileNotFoundError:
        # Re-raise FileNotFoundError as-is for proper test handling
        raise
    except Exception as e:
        logger.error(f"❌ FIT processing failed for {file_path}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise FitProcessingError(f"Processing failed: {e}")


@celery_app.task(bind=True, **TASK_CONFIG["process_health_fit_file"])
def process_health_fit_file(self, file_path: str, user_id: str) -> Dict[str, Any]:
    """
    Process a single health/wellness FIT file and store results in Elasticsearch.
    
    Args:
        file_path: Path to health FIT file
        user_id: User identifier
        
    Returns:
        Dict containing processing results
        
    Raises:
        FileNotFoundError: FIT file not found
        FitProcessingError: Processing failed
        StorageError: Storage operation failed
    """
    try:
        # Initialize progress
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'validating', 'progress': 0}
        )
        
        logger.info(f"Processing health FIT file {file_path} for user {user_id}")
        
        # Validate file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Health FIT file not found: {file_path}")
            
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        # Initialize health processor
        processor = HealthProcessor(storage)
        
        # Update progress
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'processing', 'progress': 20}
        )
        
        # Process health FIT file (run async method in sync context)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(processor.process_fit_file(file_path, user_id))
        finally:
            loop.close()
        
        # Update progress
        self.update_state(
            state='PROGRESS', 
            meta={'stage': 'indexing_completed', 'progress': 80}
        )
        
        # Create processing result compatible with interface
        if success:
            processing_result = {
                'file_path': file_path,
                'user_id': user_id,
                'status': ProcessingStatus.COMPLETED.value,
                'successful_records': 1,  # Health processor returns boolean, assume 1 record
                'failed_records': 0,
                'total_records': 1,
                'processing_time': None,
                'errors': [],
                'warnings': [],
                'metadata': {
                    'file_type': 'health',
                    'processor_type': 'health'
                },
                'processed_at': datetime.now().isoformat()
            }
        else:
            processing_result = {
                'file_path': file_path,
                'user_id': user_id,
                'status': ProcessingStatus.FAILED.value,
                'successful_records': 0,
                'failed_records': 1,
                'total_records': 1,
                'processing_time': None,
                'errors': ['Health data processing failed'],
                'warnings': [],
                'metadata': {
                    'file_type': 'health',
                    'processor_type': 'health'
                },
                'processed_at': datetime.now().isoformat()
            }
        
        # Final progress update
        self.update_state(
            state='SUCCESS' if success else 'FAILURE',
            meta={
                'stage': 'completed',
                'progress': 100,
                'records_processed': 1 if success else 0
            }
        )
        
        if success:
            logger.info(f"✅ Processed health FIT file {file_path}")
        else:
            logger.warning(f"⚠️ Failed to process health FIT file {file_path}")
        
        return processing_result
        
    except FileNotFoundError:
        # Re-raise FileNotFoundError as-is for proper test handling
        raise
    except Exception as e:
        logger.error(f"❌ Health FIT processing failed for {file_path}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise FitProcessingError(f"Health processing failed: {e}")


# process_fit_file task removed - it was causing synchronous blocking anti-pattern
# Use detect_fit_file_type helper and call process_activity_fit_file or process_health_fit_file directly


@celery_app.task(bind=True, **TASK_CONFIG["process_fit_file_batch"])
def process_fit_file_batch(self, file_metadata_list: List[Dict], user_id: str) -> Dict[str, Any]:
    """
    Process a batch of FIT files in parallel.
    
    Args:
        file_metadata_list: List of file metadata dicts with file_path and activity_id
        user_id: User identifier
        
    Returns:
        Dict containing batch processing results
        
    Raises:
        FitProcessingError: Batch processing failed
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info(f"Processing batch of {len(file_metadata_list)} FIT files for user {user_id}")
        
        batch_results = {
            'user_id': user_id,
            'total_files': len(file_metadata_list),
            'processed_files': 0,
            'successful_files': 0,
            'failed_files': 0,
            'results': [],
            'started_at': datetime.now().isoformat()
        }
        
        # Process each file
        for i, file_metadata in enumerate(file_metadata_list):
            file_path = file_metadata['file_path']
            activity_id = file_metadata['activity_id']
            
            # Update progress
            progress = (i / len(file_metadata_list)) * 90
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': f'processing_file_{i+1}',
                    'progress': progress,
                    'current_file': file_path,
                    'files_processed': i
                }
            )
            
            try:
                # Execute processing logic directly within batch context
                # This avoids creating subtasks within a task which can cause blocking issues
                file_result = self._process_file_directly(file_path, user_id, activity_id, False)
                
                batch_results['results'].append(file_result)
                batch_results['successful_files'] += 1
                
                logger.info(f"✅ Processed file {i+1}/{len(file_metadata_list)}: {file_path}")
                
            except Exception as file_error:
                error_result = {
                    'file_path': file_path,
                    'activity_id': activity_id,
                    'status': 'failed',
                    'error': str(file_error),
                    'processed_at': datetime.now().isoformat()
                }
                batch_results['results'].append(error_result)
                batch_results['failed_files'] += 1
                
                logger.error(f"❌ Failed to process file {i+1}/{len(file_metadata_list)}: {file_path} - {file_error}")
            
            batch_results['processed_files'] = i + 1
        
        batch_results['completed_at'] = datetime.now().isoformat()
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'successful_files': batch_results['successful_files'],
                'failed_files': batch_results['failed_files']
            }
        )
        
        logger.info(f"✅ Batch processing completed: {batch_results['successful_files']} successful, {batch_results['failed_files']} failed")
        return batch_results
        
    except Exception as e:
        logger.error(f"❌ Batch processing failed for user {user_id}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise FitProcessingError(f"Batch processing failed: {e}")


def _process_file_directly(file_path: str, user_id: str, activity_id: str, validate_only: bool = False) -> Dict[str, Any]:
    """
    Process a single FIT file directly without creating subtasks.
    
    This method executes the processing logic synchronously within the batch context,
    avoiding the need for subtask creation and .get() calls.
    """
    from peakflow.processors.activity import ActivityProcessor
    from peakflow.storage.elasticsearch import ElasticsearchStorage
    import os
    
    try:
        # Determine file type and validate
        if not os.path.exists(file_path):
            raise FitProcessingError(f"FIT file not found: {file_path}")
        
        # Initialize processor
        processor = ActivityProcessor()
        
        # Process the FIT file
        activity_data = processor.process_fit_file(file_path)
        
        if validate_only:
            return {
                'status': 'validated',
                'file_path': file_path,
                'activity_id': activity_id,
                'user_id': user_id,
                'validation_result': 'passed'
            }
        
        # Store in Elasticsearch
        storage = ElasticsearchStorage()
        storage.store_activity_data(user_id, activity_id, activity_data)
        
        return {
            'status': 'processed',
            'file_path': file_path,
            'activity_id': activity_id,
            'user_id': user_id,
            'processed_records': len(activity_data.get('records', [])),
            'processing_time': activity_data.get('processing_time', 0)
        }
        
    except Exception as e:
        logger.error(f"Direct processing failed for {file_path}: {e}")
        raise FitProcessingError(f"Direct processing failed: {e}")


@celery_app.task(bind=True, **TASK_CONFIG["validate_processed_data"])
def validate_processed_data(self, activity_id: str, user_id: str) -> Dict[str, Any]:
    """
    Validate that processed FIT file data is correctly stored in Elasticsearch.
    
    Args:
        activity_id: Activity identifier
        user_id: User identifier
        
    Returns:
        Dict containing validation results
        
    Raises:
        ValidationError: Data validation failed
        StorageError: Storage query failed
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info(f"Validating processed data for activity {activity_id}, user {user_id}")
        
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        validation_results = {
            'activity_id': activity_id,
            'user_id': user_id,
            'data_types_found': [],
            'record_counts': {},
            'validation_errors': [],
            'status': 'unknown',
            'validated_at': datetime.now().isoformat()
        }
        
        # Check for session data
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'checking_sessions', 'progress': 25}
        )
        
        try:
            session_filter = (QueryFilter()
                            .add_term_filter("activity_id", activity_id)
                            .add_term_filter("user_id", user_id))
            
            sessions = storage.search(DataType.SESSION, session_filter)
            if sessions:
                validation_results['data_types_found'].append('sessions')
                validation_results['record_counts']['sessions'] = len(sessions)
            else:
                validation_results['validation_errors'].append('No session data found')
        except Exception as e:
            validation_results['validation_errors'].append(f"Session validation error: {e}")
        
        # Check for record data
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'checking_records', 'progress': 50}
        )
        
        try:
            record_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .add_term_filter("user_id", user_id)
                           .set_pagination(1))  # Just check if any exist
            
            records = storage.search(DataType.RECORD, record_filter)
            if records:
                validation_results['data_types_found'].append('records')
                # Get count with larger pagination
                count_filter = (QueryFilter()
                              .add_term_filter("activity_id", activity_id)
                              .add_term_filter("user_id", user_id)
                              .set_pagination(10000))
                full_records = storage.search(DataType.RECORD, count_filter)
                validation_results['record_counts']['records'] = len(full_records)
            else:
                validation_results['validation_errors'].append('No record data found')
        except Exception as e:
            validation_results['validation_errors'].append(f"Record validation error: {e}")
        
        # Check for lap data
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'checking_laps', 'progress': 75}
        )
        
        try:
            lap_filter = (QueryFilter()
                        .add_term_filter("activity_id", activity_id)
                        .add_term_filter("user_id", user_id))
            
            laps = storage.search(DataType.LAP, lap_filter)
            if laps:
                validation_results['data_types_found'].append('laps')
                validation_results['record_counts']['laps'] = len(laps)
            else:
                validation_results['validation_errors'].append('No lap data found')
        except Exception as e:
            validation_results['validation_errors'].append(f"Lap validation error: {e}")
        
        # Determine overall status
        if len(validation_results['validation_errors']) == 0:
            validation_results['status'] = 'valid'
        elif len(validation_results['data_types_found']) > 0:
            validation_results['status'] = 'partially_valid'
        else:
            validation_results['status'] = 'invalid'
        
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'status': validation_results['status'],
                'data_types': len(validation_results['data_types_found'])
            }
        )
        
        logger.info(f"✅ Data validation completed for activity {activity_id}: {validation_results['status']}")
        return validation_results
        
    except Exception as e:
        logger.error(f"❌ Data validation failed for activity {activity_id}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise ValidationError(f"Data validation failed: {e}")