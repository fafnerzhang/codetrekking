#!/usr/bin/env python3
"""
TSS Service - High-level service for TSS calculation and indexing

This service provides a convenient interface to calculate and manage
Training Stress Score (TSS) data for activities stored in Elasticsearch.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime

from ..analytics.tss import TSSCalculator
from ..storage.interface import (
    StorageInterface, DataType, QueryFilter
)
from ..utils import get_logger

logger = get_logger(__name__)


class TSSService:
    """High-level service for TSS calculation and indexing"""
    
    def __init__(self, storage: StorageInterface):
        """
        Initialize TSS service
        
        Args:
            storage: Storage interface implementation (e.g., ElasticsearchStorage)
        """
        self.storage = storage
        self.calculator = TSSCalculator(storage)
    
    def calculate_tss_for_activity(self, activity_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Calculate and index TSS for a single activity
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier
            **kwargs: TSS calculation parameters (ftp, threshold_hr, max_hr, threshold_pace)
            
        Returns:
            TSS calculation results with indexing status
        """
        try:
            logger.info(f"🧮 Calculating TSS for activity {activity_id} (user: {user_id})")
            
            result = self.calculator.calculate_and_index_tss(activity_id, user_id, **kwargs)
            
            if 'error' not in result:
                primary_tss = result.get('tss', 0)
                method = result.get('primary_method', 'unknown')
                logger.info(f"✅ TSS calculated: {primary_tss:.1f} (method: {method})")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to calculate TSS for activity {activity_id}: {str(e)}")
            return {
                'error': str(e),
                'activity_id': activity_id,
                'user_id': user_id,
                'indexing_status': 'failed'
            }
    
    def calculate_tss_for_user_activities(self, user_id: str, limit: int = 100, **kwargs) -> Dict[str, Any]:
        """
        Calculate TSS for all activities of a user that don't have TSS calculated yet
        
        Args:
            user_id: User identifier
            limit: Maximum number of activities to process
            **kwargs: TSS calculation parameters
            
        Returns:
            Batch processing results
        """
        try:
            logger.info(f"🧮 Processing TSS for user {user_id} activities (limit: {limit})")
            
            # Get activities without TSS
            activities_without_tss = self._get_activities_without_tss(user_id, limit)
            
            if not activities_without_tss:
                logger.info(f"📋 No activities without TSS found for user {user_id}")
                return {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'details': [],
                    'message': 'No activities without TSS found'
                }
            
            logger.info(f"📋 Found {len(activities_without_tss)} activities without TSS")
            
            # Batch calculate TSS
            activities_data = [
                {'activity_id': act['activity_id'], 'user_id': user_id}
                for act in activities_without_tss
            ]
            
            result = self.calculator.batch_calculate_and_index_tss(activities_data, **kwargs)
            
            logger.info(f"✅ Batch TSS processing completed: {result['successful']}/{result['total']} successful")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed batch TSS calculation for user {user_id}: {str(e)}")
            return {
                'error': str(e),
                'user_id': user_id,
                'total': 0,
                'successful': 0,
                'failed': 1
            }
    
    def get_tss_for_activity(self, activity_id: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """
        Retrieve TSS data for an activity
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier (optional)
            
        Returns:
            TSS data if found, None otherwise
        """
        return self.calculator.get_tss_by_activity(activity_id, user_id)
    
    def get_user_tss_summary(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get TSS summary for a user over a specified period
        
        Args:
            user_id: User identifier
            days: Number of days to look back (default: 30)
            
        Returns:
            TSS summary statistics
        """
        try:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            start_date = start_date.replace(day=start_date.day - days) if start_date.day > days else start_date.replace(month=start_date.month - 1, day=start_date.day + 30 - days)
            
            tss_history = self.calculator.get_user_tss_history(
                user_id, 
                start_date=start_date,
                limit=1000
            )
            
            if not tss_history:
                return {
                    'user_id': user_id,
                    'period_days': days,
                    'total_activities': 0,
                    'total_tss': 0,
                    'avg_tss': 0,
                    'max_tss': 0,
                    'methods_used': [],
                    'activities_by_sport': {}
                }
            
            # Calculate summary statistics
            total_tss = sum(record.get('primary_tss', 0) for record in tss_history)
            avg_tss = total_tss / len(tss_history) if tss_history else 0
            max_tss = max((record.get('primary_tss', 0) for record in tss_history), default=0)
            
            # Analyze methods used
            methods = [record.get('primary_method', 'unknown') for record in tss_history]
            methods_count = {}
            for method in methods:
                methods_count[method] = methods_count.get(method, 0) + 1
            
            # Activities by sport
            sports_count = {}
            for record in tss_history:
                sport = record.get('sport', 'unknown')
                sports_count[sport] = sports_count.get(sport, 0) + 1
            
            return {
                'user_id': user_id,
                'period_days': days,
                'total_activities': len(tss_history),
                'total_tss': round(total_tss, 1),
                'avg_tss': round(avg_tss, 1),
                'max_tss': round(max_tss, 1),
                'methods_used': methods_count,
                'activities_by_sport': sports_count,
                'latest_activity': tss_history[0].get('timestamp') if tss_history else None
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get TSS summary for user {user_id}: {str(e)}")
            return {
                'error': str(e),
                'user_id': user_id,
                'period_days': days
            }
    
    def _get_activities_without_tss(self, user_id: str, limit: int) -> List[Dict[str, Any]]:
        """
        Find activities that don't have TSS calculated yet
        
        Args:
            user_id: User identifier
            limit: Maximum number of activities to return
            
        Returns:
            List of activities without TSS
        """
        try:
            # Get all activities for user
            activities_query = (QueryFilter()
                               .add_term_filter("user_id", user_id)
                               .add_sort("timestamp", ascending=False)
                               .set_pagination(limit))
            
            activities = self.storage.search(DataType.SESSION, activities_query)
            
            if not activities:
                return []
            
            # Get existing TSS records for user
            tss_query = (QueryFilter()
                        .add_term_filter("user_id", user_id)
                        .set_pagination(10000))  # Get all TSS records
            
            tss_records = self.storage.search(DataType.TSS, tss_query)
            tss_activity_ids = {record['activity_id'] for record in tss_records}
            
            # Filter activities that don't have TSS
            activities_without_tss = [
                activity for activity in activities
                if activity.get('activity_id') not in tss_activity_ids
            ]
            
            return activities_without_tss
            
        except Exception as e:
            logger.error(f"❌ Failed to find activities without TSS: {str(e)}")
            return []
    
    def recalculate_tss(self, activity_id: str, user_id: str, **kwargs) -> Dict[str, Any]:
        """
        Recalculate TSS for an activity (overwrites existing TSS)
        
        Args:
            activity_id: Activity identifier
            user_id: User identifier
            **kwargs: TSS calculation parameters
            
        Returns:
            TSS calculation results
        """
        try:
            logger.info(f"🔄 Recalculating TSS for activity {activity_id}")
            
            # Delete existing TSS record if it exists
            doc_id = f"{user_id}_{activity_id}"
            self.storage.delete_by_id(DataType.TSS, doc_id)
            
            # Calculate new TSS
            result = self.calculator.calculate_and_index_tss(activity_id, user_id, **kwargs)
            
            if 'error' not in result:
                logger.info(f"✅ TSS recalculated successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to recalculate TSS: {str(e)}")
            return {
                'error': str(e),
                'activity_id': activity_id,
                'user_id': user_id,
                'indexing_status': 'failed'
            }
    
    def create_tss_index(self, force_recreate: bool = False) -> bool:
        """
        Create the TSS index in Elasticsearch
        
        Args:
            force_recreate: Whether to recreate the index if it already exists
            
        Returns:
            True if successful, False otherwise
        """
        try:
            return self.storage.create_indices(force_recreate=force_recreate)
        except Exception as e:
            logger.error(f"❌ Failed to create TSS index: {str(e)}")
            return False
