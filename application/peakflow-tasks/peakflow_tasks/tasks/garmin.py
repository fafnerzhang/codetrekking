"""
Garmin download tasks for PeakFlow Tasks.

This module contains Celery tasks for downloading data from Garmin Connect,
including activities, sleep data, and monitoring data.
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from celery import Task

# from ..base_tasks import BaseGarminTask  # Temporarily disabled
from ..exceptions import (
    GarminAuthenticationError,
    GarminDownloadError,
    ConfigurationError
)
from ..celery_app import celery_app
from ..config import get_elasticsearch_config
from ..utils.validation import validate_garmin_config

# Import PeakFlow modules
try:
    from peakflow.providers.garmin import GarminClient
    from peakflow.storage.elasticsearch import ElasticsearchStorage
    from peakflow.storage import DataType, QueryFilter
    from peakflow.utils import create_garmin_client_from_credentials
except ImportError as e:
    raise ImportError(f"Failed to import PeakFlow modules: {e}")

# Import database components
try:
    from ..database.connection import get_database
    from ..services.garmin_credential_service import GarminCredentialService
except ImportError as e:
    raise ImportError(f"Failed to import database components: {e}")

logger = logging.getLogger(__name__)

# Import processing task for use in tests and workflows
try:
    from .processing import process_fit_file_helper
except ImportError:
    process_fit_file = None

# Task configuration
TASK_CONFIG = {
    "download_garmin_daily_data": {
        "time_limit": 1800,  # 30 minutes
        "soft_time_limit": 1500,
        "retry_delay": 60,
        "max_retries": 3
    }
}


@celery_app.task(bind=True, **TASK_CONFIG["download_garmin_daily_data"])
def download_garmin_daily_data(self, user_id: str, start_date: str, days: int, 
                              exclude_activity_ids: Optional[List[str]] = None,
                              overwrite: bool = False) -> Dict[str, Any]:
    """
    Download Garmin daily data including activities, sleep, and monitoring data.
    
    Args:
        user_id: Garmin user identifier
        start_date: Start date in YYYY-MM-DD format
        days: Number of days to download
        exclude_activity_ids: Activity IDs to skip
        overwrite: Whether to overwrite existing files
        
    Returns:
        Dict containing download results and metadata
        
    Raises:
        GarminAuthenticationError: Authentication failed
        GarminDownloadError: Download operation failed
        ConfigurationError: Invalid configuration
    """
    try:
        # Initialize progress tracking
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info(f"Starting Garmin download for user {user_id}, date {start_date}, days {days}")
        
        # Retrieve encrypted credentials from database
        try:
            db = get_database()
            credential_service = GarminCredentialService(db)
            username, password = credential_service.get_credentials_sync(user_id)
            
            if not username or not password:
                raise ConfigurationError(f"No Garmin credentials found for user {user_id}")
        except Exception as cred_error:
            logger.error(f"Failed to retrieve credentials for user {user_id}: {cred_error}")
            raise ConfigurationError(f"Failed to retrieve Garmin credentials: {cred_error}")
        finally:
            if 'db' in locals():
                db.close()
        
        # Query Elasticsearch for existing activity IDs to exclude (if not provided)
        if exclude_activity_ids is None:
            exclude_activity_ids = _get_existing_activity_ids(user_id, start_date, days)
            logger.info(f"Found {len(exclude_activity_ids)} existing activities to exclude")
        
        # Create Garmin client using PeakFlow's credential-based function
        client = create_garmin_client_from_credentials(user_id, username, password)
        
        # Parse start date
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        # Update progress
        self.update_state(
            state='PROGRESS', 
            meta={'stage': 'downloading', 'progress': 10}
        )
        
        # Download data with progress tracking - use configurable base directory
        garmin_base = os.getenv('DEFAULT_GARMIN_CONFIG_DIR', '/home/aiuser/storage/garmin')
        output_dir = f"{garmin_base}/{user_id}/downloads"
        os.makedirs(output_dir, exist_ok=True)
        
        results = {
            'user_id': user_id,
            'start_date': start_date,
            'days': days,
            'activities': [],
            'download_time': datetime.now().isoformat(),
            'status': 'in_progress'
        }
        
        # Download activities with metadata yielding
        activity_count = 0
        try:
            for activity_metadata in client.download_daily_data(
                output_dir, start_date_obj, days, overwrite, exclude_activity_ids
            ):
                if 'error' in activity_metadata:
                    logger.warning(f"Activity download error: {activity_metadata['error']}")
                else:
                    # Queue processing task for each FIT file
                    if process_fit_file_helper:
                        # Get appropriate task signature and execute it
                        try:
                            task_sig = process_fit_file_helper(
                                activity_metadata['file_path'],
                                user_id, 
                                activity_metadata['activity_id']
                            )
                            task_sig.delay()
                        except Exception as proc_error:
                            logger.warning(f"Failed to queue processing for {activity_metadata['activity_id']}: {proc_error}")
                    
                results['activities'].append(activity_metadata)
                activity_count += 1
                
                # Update progress
                progress = min(10 + (activity_count / max(days, 1)) * 80, 90)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': 'downloading',
                        'progress': progress,
                        'activities_processed': activity_count
                    }
                )
        except Exception as download_error:
            logger.error(f"Download error: {download_error}")
            raise GarminDownloadError(f"Download failed: {download_error}")
        
        results['status'] = 'completed'
        results['total_activities'] = len(results['activities'])
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'total_activities': results['total_activities']
            }
        )
        
        logger.info(f"✅ Downloaded {len(results['activities'])} activities for user {user_id}")
        return results
        
    except Exception as e:
        logger.error(f"❌ Garmin download failed for user {user_id}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise GarminDownloadError(f"Download failed: {e}")



def _get_existing_activity_ids(user_id: str, start_date: str, days: int) -> List[str]:
    """
    Query Elasticsearch to get existing activity IDs for incremental download.
    
    Args:
        user_id: User identifier
        start_date: Start date in YYYY-MM-DD format
        days: Number of days to check
        
    Returns:
        List of existing activity IDs to exclude from download
    """
    try:
        # Initialize Elasticsearch storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        # Parse date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = start_dt + timedelta(days=days)
        
        # Query for existing sessions in date range
        query_filter = (QueryFilter()
                       .add_term_filter("user_id", user_id)
                       .add_date_range("timestamp", start=start_dt, end=end_dt)
                       .set_pagination(10000))  # Get all activities in range
        
        existing_sessions = storage.search(DataType.SESSION, query_filter)
        
        # Extract activity IDs
        activity_ids = [session.get('activity_id') for session in existing_sessions 
                       if session.get('activity_id')]
        
        logger.info(f"Found {len(activity_ids)} existing activities for user {user_id} in date range")
        return activity_ids
        
    except Exception as e:
        logger.warning(f"Failed to query existing activities: {e}")
        return []  # Return empty list if query fails, will download all