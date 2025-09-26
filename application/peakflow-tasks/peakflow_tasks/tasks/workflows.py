"""
Simplified Garmin sync workflow - follows Linus principles.

Single workflow: check existing data → download new → process → store.
No special cases, no unnecessary abstraction.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Set, Optional
from pathlib import Path

from ..celery_app import celery_app
from ..exceptions import WorkflowError
from ..config import get_settings

# Import PeakFlow modules
from peakflow import ElasticsearchStorage, ActivityProcessor, HealthProcessor
from peakflow.providers.garmin import GarminClient
from peakflow.storage.interface import QueryFilter, DataType

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, time_limit=3600, soft_time_limit=3000, max_retries=1)
def garmin_sync_workflow(self, user_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Complete Garmin sync: check existing → download new → process → store.
    
    Args:
        user_id: User identifier for authentication and data organization
        days: Number of days to sync (default: 30)
        
    Returns:
        Dict with sync results: activities_processed, health_files_processed, errors
    """
    start_time = datetime.utcnow()
    
    try:
        settings = get_settings()
        
        # Progress update
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 10}
        )
        
        # 1. Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize({
            'hosts': [settings.elasticsearch.host],
            'username': settings.elasticsearch.username,
            'password': settings.elasticsearch.password,
            'timeout': settings.elasticsearch.timeout,
            'verify_certs': settings.elasticsearch.verify_certs
        })
        
        # 2. Check existing activity IDs - simple ES query
        existing_activity_ids = _get_existing_activity_ids(storage, user_id, days)
        logger.info(f"Found {len(existing_activity_ids)} existing activities to skip")
        
        # Progress update  
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'downloading', 'progress': 20}
        )
        
        # 3. Get Garmin credentials and create client
        garmin_client = _create_garmin_client(user_id, settings)
        
        # 4. Download new data only
        start_date = (datetime.utcnow() - timedelta(days=days)).date()
        output_dir = settings.peakflow.garmin_data_path / user_id
        output_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_files = list(garmin_client.download_daily_data(
            output_dir=str(settings.peakflow.garmin_data_path),  # Pass base path, client will add user_id
            start_date=start_date,
            days=days,
            overwrite=False,
            exclude_activity_ids=existing_activity_ids
        ))
        
        if not downloaded_files:
            return {
                'status': 'completed',
                'message': 'No new data to process',
                'activities_processed': 0,
                'health_files_processed': 0,
                'duration_seconds': (datetime.utcnow() - start_time).total_seconds()
            }
        
        # Progress update
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'processing', 'progress': 50}
        )
        
        # 5. Process downloaded files
        activity_processor = ActivityProcessor(storage=storage)
        health_processor = HealthProcessor(storage=storage)
        
        activities_processed = 0
        health_files_processed = 0
        errors = []
        
        # Process activity files from generator
        for file_metadata in downloaded_files:
            if 'error' in file_metadata:
                errors.append(f"Download error: {file_metadata['error']}")
                continue
                
            file_path = file_metadata.get('file_path')
            activity_id = file_metadata.get('activity_id')
            
            if not file_path or not Path(file_path).exists():
                errors.append(f"File not found: {file_path}")
                continue
            
            try:
                if _is_activity_file(file_path):
                    result = activity_processor.process(file_path, user_id, activity_id)
                    if result.successful_records > 0:
                        activities_processed += 1
                    else:
                        errors.extend(result.errors)
                        
            except Exception as e:
                error_msg = f"Processing failed for {file_path}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Process health files from sleep and monitoring directories
        import asyncio
        health_files = _find_health_files(output_dir)
        for health_file in health_files:
            try:
                success = asyncio.run(health_processor.process_fit_file(str(health_file), user_id))
                if success:
                    health_files_processed += 1
                    logger.info(f"Processed health file: {health_file.name}")
                else:
                    errors.append(f"Health processing failed: {health_file}")
                    
            except Exception as e:
                error_msg = f"Health processing failed for {health_file}: {e}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Progress update
        self.update_state(
            state='PROGRESS', 
            meta={'stage': 'completing', 'progress': 90}
        )
        
        # 6. Return results
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        result = {
            'status': 'completed',
            'user_id': user_id,
            'days': days,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'activities_processed': activities_processed,
            'health_files_processed': health_files_processed,
            'total_files_downloaded': len(downloaded_files),
            'existing_activities_skipped': len(existing_activity_ids),
            'errors': errors,
            'duration_seconds': duration,
            'completed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Garmin sync completed for {user_id}: {activities_processed} activities, {health_files_processed} health files")
        return result
        
    except Exception as e:
        error_msg = f"Garmin sync workflow failed for {user_id}: {e}"
        logger.error(error_msg)
        
        self.update_state(
            state='FAILURE',
            meta={'error': error_msg, 'stage': 'failed'}
        )
        
        raise WorkflowError(error_msg)


def _get_existing_activity_ids(storage: ElasticsearchStorage, user_id: str, days: int) -> Set[str]:
    """Query ES for existing activity IDs - simple and direct."""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query_filter = QueryFilter()
        query_filter.add_term_filter('user_id', user_id)
        query_filter.add_date_range('start_time', start_date, end_date)
        query_filter.limit = 10000
        query_filter.set_source_fields(['activity_id'])  # Only return activity_id field

        sessions = storage.search(DataType.SESSION, query_filter)
        activity_ids = {
            session.get('activity_id') for session in sessions
            if session.get('activity_id')
        }

        return activity_ids
        
    except Exception as e:
        logger.warning(f"Failed to query existing activities: {e}")
        return set()


def _create_garmin_client(user_id: str, settings) -> GarminClient:
    """Create Garmin client from stored credentials using UUID for directory."""
    try:
        from ..database.connection import get_database
        from ..services.garmin_credential_service import GarminCredentialService
        
        db = get_database()
        credential_service = GarminCredentialService(db)
        username, password = credential_service.get_credentials_sync(user_id)
        db.close()
        
        if not username or not password:
            raise WorkflowError(f"No credentials found for user {user_id}")
        
        config_base_dir = str(settings.peakflow.garmin_config_path)
        return GarminClient.create_from_config(
            {'user': username, 'password': password},
            user_id=user_id,
            config_base_dir=config_base_dir
        )
        
    except Exception as e:
        raise WorkflowError(f"Failed to create Garmin client: {e}")


def _is_activity_file(file_path: str) -> bool:
    """Check if file contains activity data."""
    filename = Path(file_path).name.lower()
    return 'activity' in filename and filename.endswith('.fit')


def _is_health_file(file_path: str) -> bool:
    """Check if file contains health data."""
    filename = Path(file_path).name.lower()
    health_indicators = ['wellness', 'sleep', 'hrv', 'metrics', 'monitoring']
    return any(indicator in filename for indicator in health_indicators) and filename.endswith('.fit')


def _find_health_files(output_dir: Path) -> list[Path]:
    """Find all health FIT files in sleep and monitoring directories."""
    health_files = []
    
    # Check sleep directory
    sleep_dir = output_dir / "sleep"
    if sleep_dir.exists():
        health_files.extend(sleep_dir.glob("*.fit"))
    
    # Check monitoring directories (can be nested by year)
    monitoring_dir = output_dir / "monitoring"
    if monitoring_dir.exists():
        health_files.extend(monitoring_dir.rglob("*.fit"))
    
    # Filter to only health files
    return [f for f in health_files if _is_health_file(str(f))]