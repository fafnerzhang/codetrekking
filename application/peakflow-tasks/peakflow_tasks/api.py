"""
API interface for PeakFlow Tasks.

This module provides a simplified task management interface for the API service
without advanced analytics functionality.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

from .celery_app import celery_app
# download_garmin_daily_data import removed - use complete_garmin_sync workflow instead
from .tasks.processing import process_fit_file_helper, process_fit_file_batch, process_activity_fit_file, process_health_fit_file
try:
    from .tasks.workflows import garmin_sync_workflow
except ImportError as e:
    # Gracefully handle workflow import errors during development
    logger.warning(f"Workflow tasks not available: {e}")
    garmin_sync_workflow = None


class TaskManager:
    """Task manager for coordinating Celery tasks."""
    
    def __init__(self):
        """Initialize the task manager."""
        self.logger = logger
    
    
    # trigger_garmin_data_download method removed - use trigger_complete_sync instead
    
    def trigger_fit_processing(
        self,
        user_id: str,
        activity_id: str,
        fit_file_path: str,
        processing_options: Dict[str, Any],
        priority: str = "normal"
    ) -> str:
        """
        Trigger FIT file processing task.
        
        Args:
            user_id: User identifier
            activity_id: Activity identifier
            fit_file_path: Path to the FIT file
            processing_options: Processing configuration
            priority: Task priority
            
        Returns:
            Task ID
        """
        try:
            validate_only = processing_options.get('validate_only', False)
            
            # Use helper to get appropriate task signature and execute it
            task_signature = process_fit_file_helper(
                fit_file_path, user_id, activity_id, validate_only
            )
            task = task_signature.apply_async(
                priority=self._get_priority_value(priority)
            )
            
            self.logger.info(f"FIT processing task queued: {task.id} for activity {activity_id}")
            return task.id
            
        except Exception as e:
            self.logger.error(f"Failed to queue FIT processing task for activity {activity_id}: {e}")
            raise
    
    def trigger_batch_fit_processing(
        self,
        user_id: str,
        fit_files: List[Dict[str, str]],
        processing_options: Dict[str, Any],
        priority: str = "normal"
    ) -> str:
        """
        Trigger batch FIT file processing task.
        
        Args:
            user_id: User identifier
            fit_files: List of FIT files to process
            processing_options: Processing configuration
            priority: Task priority
            
        Returns:
            Task ID
        """
        try:
            # Convert fit_files to the expected format for batch processing
            file_metadata_list = []
            for f in fit_files:
                file_metadata_list.append({
                    'file_path': f['fit_file_path'],
                    'activity_id': f['activity_id'],
                })
            validate_only = processing_options.get('validate_only', False)
            
            task = process_fit_file_batch.apply_async(
                args=[file_metadata_list, user_id],
                kwargs={'validate_only': validate_only},
                priority=self._get_priority_value(priority)
            )
            
            self.logger.info(f"Batch FIT processing task queued: {task.id} for {len(fit_files)} files")
            return task.id
            
        except Exception as e:
            self.logger.error(f"Failed to queue batch FIT processing task: {e}")
            raise
    
    def trigger_garmin_sync(
        self,
        user_id: str,
        days: int = 30,
        priority: str = "normal"
    ) -> str:
        """
        Trigger Garmin sync workflow.
        
        Args:
            user_id: User identifier
            days: Number of days to sync
            priority: Task priority
            
        Returns:
            Task ID
        """
        try:
            if garmin_sync_workflow is None:
                raise ImportError("Garmin sync workflow not available")
                
            task = garmin_sync_workflow.apply_async(
                args=[user_id, days],
                priority=self._get_priority_value(priority)
            )
            
            self.logger.info(f"Garmin sync workflow queued: {task.id} for user {user_id}")
            return task.id
            
        except Exception as e:
            self.logger.error(f"Failed to queue Garmin sync workflow for user {user_id}: {e}")
            raise
    
    def trigger_complete_sync(
        self,
        user_id: str,
        start_date: str,
        days: int = 30,
        priority: str = "normal"
    ) -> str:
        """
        Trigger complete Garmin sync workflow (download + process + index).
        
        Args:
            user_id: User identifier
            start_date: Start date (YYYY-MM-DD format, currently ignored - uses days parameter)
            days: Number of days to sync
            priority: Task priority
            
        Returns:
            Task ID
        """
        # Use the existing garmin_sync_workflow which handles complete sync
        return self.trigger_garmin_sync(user_id, days, priority)
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and result.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status information
        """
        try:
            result = celery_app.AsyncResult(task_id)
            
            status_info = {
                'task_id': task_id,
                'status': result.state,
                'result': None,
                'error': None,
                'traceback': None
            }
            
            if result.successful():
                status_info['result'] = result.result
            elif result.failed():
                status_info['error'] = str(result.result)
                status_info['traceback'] = result.traceback
            elif result.state == 'PROGRESS':
                status_info['result'] = result.result
            
            return status_info
            
        except Exception as e:
            self.logger.error(f"Failed to get task status for {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': 'UNKNOWN',
                'error': str(e),
                'result': None,
                'traceback': None
            }
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """
        Revoke a running task.
        
        Args:
            task_id: Task identifier
            terminate: Whether to terminate the task
            
        Returns:
            True if successful
        """
        try:
            celery_app.control.revoke(task_id, terminate=terminate)
            self.logger.info(f"Task {task_id} revoked (terminate={terminate})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to revoke task {task_id}: {e}")
            return False
    
    def trigger_health_check(self) -> Optional[str]:
        """
        Trigger a health check task to verify system connectivity.
        
        Returns:
            Task ID if successful, None if failed
        """
        try:
            # Create a simple health check task that verifies basic functionality
            from .celery_app import celery_app
            
            task = celery_app.send_task(
                'celery.ping',  # Built-in Celery health check task
                priority=self._get_priority_value('high')
            )
            
            self.logger.info(f"Health check task queued: {task.id}")
            return task.id
            
        except Exception as e:
            self.logger.error(f"Failed to queue health check task: {e}")
            return None
    
    def _get_priority_value(self, priority: str) -> int:
        """Convert priority string to numeric value."""
        priority_map = {
            'low': 3,
            'normal': 6,
            'high': 9
        }
        return priority_map.get(priority.lower(), 6)