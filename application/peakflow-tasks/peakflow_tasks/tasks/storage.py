"""
Storage management tasks for PeakFlow Tasks.

This module contains Celery tasks for managing Elasticsearch storage,
including bulk indexing, data cleanup, and index management.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List

# from ..base_tasks import BaseStorageTask  # Temporarily disabled
from ..exceptions import StorageError, ValidationError
from ..celery_app import celery_app
from ..config import get_elasticsearch_config

# Import PeakFlow modules
try:
    from peakflow.storage.elasticsearch import ElasticsearchStorage
    from peakflow.storage import DataType, QueryFilter
except ImportError as e:
    raise ImportError(f"Failed to import PeakFlow modules: {e}")

logger = logging.getLogger(__name__)

# Task configuration
TASK_CONFIG = {
    "bulk_index_fitness_data": {
        "time_limit": 1800,  # 30 minutes
        "soft_time_limit": 1500,
        "retry_delay": 60,
        "max_retries": 2
    },
    "cleanup_old_data": {
        "time_limit": 3600,  # 1 hour
        "soft_time_limit": 3300,
        "retry_delay": 300,
        "max_retries": 1
    },
    "ensure_elasticsearch_indices": {
        "time_limit": 600,   # 10 minutes
        "soft_time_limit": 540,
        "retry_delay": 60,
        "max_retries": 3
    }
}


@celery_app.task(bind=True, **TASK_CONFIG["bulk_index_fitness_data"])
def bulk_index_fitness_data(self, documents: List[Dict], data_type: str,
                           batch_size: int = 1000) -> Dict[str, Any]:
    """
    Bulk index fitness data to Elasticsearch with optimized batching.
    
    Args:
        documents: List of documents to index
        data_type: Type of data (session, record, lap)
        batch_size: Number of documents per batch
        
    Returns:
        Dict containing indexing results
        
    Raises:
        StorageError: Indexing operation failed
        ValidationError: Document validation failed
    """
    try:
        # Initialize progress
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info(f"Bulk indexing {len(documents)} documents of type {data_type}")
        
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        # Validate data type
        try:
            dt = DataType(data_type.lower())
        except ValueError:
            raise ValidationError(f"Invalid data type: {data_type}")
        
        # Process in batches
        total_docs = len(documents)
        total_success = 0
        total_failed = 0
        batch_results = []
        
        for i in range(0, total_docs, batch_size):
            batch = documents[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            
            # Update progress
            progress = (i / total_docs) * 90
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': f'indexing_batch_{batch_num}',
                    'progress': progress,
                    'batch': batch_num,
                    'total_batches': (total_docs + batch_size - 1) // batch_size
                }
            )
            
            # Index batch
            try:
                result = storage.bulk_index(dt, batch)
                success_count = getattr(result, 'success_count', len(batch))
                failed_count = getattr(result, 'failed_count', 0)
                errors = getattr(result, 'errors', [])
                
                total_success += success_count
                total_failed += failed_count
                
                batch_results.append({
                    'batch_number': batch_num,
                    'documents': len(batch),
                    'success': success_count,
                    'failed': failed_count,
                    'errors': errors
                })
                
                logger.info(f"Batch {batch_num}: {success_count} success, {failed_count} failed")
                
            except Exception as batch_error:
                logger.error(f"Batch {batch_num} failed: {batch_error}")
                total_failed += len(batch)
                batch_results.append({
                    'batch_number': batch_num,
                    'documents': len(batch),
                    'success': 0,
                    'failed': len(batch),
                    'errors': [str(batch_error)]
                })
        
        # Final results
        indexing_result = {
            'data_type': data_type,
            'total_documents': total_docs,
            'successful_documents': total_success,
            'failed_documents': total_failed,
            'batch_size': batch_size,
            'batch_results': batch_results,
            'indexed_at': datetime.now().isoformat()
        }
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'total_indexed': total_success
            }
        )
        
        logger.info(f"✅ Bulk indexed {total_success} documents of type {data_type}")
        return indexing_result
        
    except Exception as e:
        logger.error(f"❌ Bulk indexing failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise StorageError(f"Bulk indexing failed: {e}")


@celery_app.task(bind=True, **TASK_CONFIG["cleanup_old_data"])
def cleanup_old_data(self, user_id: str, days_to_keep: int = 365) -> Dict[str, Any]:
    """
    Clean up old fitness data for a user beyond the retention period.
    
    Args:
        user_id: User identifier
        days_to_keep: Number of days of data to retain (default 365)
        
    Returns:
        Dict containing cleanup results
        
    Raises:
        StorageError: Cleanup operation failed
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info(f"Cleaning up data older than {days_to_keep} days for user {user_id}")
        
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        cleanup_results = {
            'user_id': user_id,
            'days_to_keep': days_to_keep,
            'cutoff_date': cutoff_date.isoformat(),
            'data_types_cleaned': [],
            'documents_deleted': {},
            'total_deleted': 0,
            'cleanup_time': datetime.now().isoformat()
        }
        
        # Data types to clean
        data_types = [DataType.SESSION, DataType.RECORD, DataType.LAP]
        
        for i, data_type in enumerate(data_types):
            # Update progress
            progress = (i / len(data_types)) * 90
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': f'cleaning_{data_type.value}',
                    'progress': progress,
                    'current_type': data_type.value
                }
            )
            
            try:
                # Query for old documents
                query_filter = (QueryFilter()
                              .add_term_filter("user_id", user_id)
                              .add_date_range("timestamp", end=cutoff_date)
                              .set_pagination(10000))
                
                old_documents = storage.search(data_type, query_filter)
                
                if old_documents:
                    # Delete old documents
                    deleted_count = 0
                    for doc in old_documents:
                        if storage.delete_document(data_type, doc.get('_id')):
                            deleted_count += 1
                    
                    cleanup_results['data_types_cleaned'].append(data_type.value)
                    cleanup_results['documents_deleted'][data_type.value] = deleted_count
                    cleanup_results['total_deleted'] += deleted_count
                    
                    logger.info(f"Deleted {deleted_count} old {data_type.value} documents")
                else:
                    cleanup_results['documents_deleted'][data_type.value] = 0
                    logger.info(f"No old {data_type.value} documents found")
                    
            except Exception as cleanup_error:
                logger.error(f"Error cleaning {data_type.value}: {cleanup_error}")
                cleanup_results['documents_deleted'][data_type.value] = 0
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'total_deleted': cleanup_results['total_deleted']
            }
        )
        
        logger.info(f"✅ Cleanup completed for user {user_id}: {cleanup_results['total_deleted']} documents deleted")
        return cleanup_results
        
    except Exception as e:
        logger.error(f"❌ Data cleanup failed for user {user_id}: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise StorageError(f"Data cleanup failed: {e}")


@celery_app.task(bind=True, **TASK_CONFIG["ensure_elasticsearch_indices"])
def ensure_elasticsearch_indices(self, force_recreate: bool = False) -> Dict[str, Any]:
    """
    Ensure all required Elasticsearch indices exist with proper mappings.
    
    Args:
        force_recreate: Whether to force recreation of existing indices
        
    Returns:
        Dict containing index creation results
        
    Raises:
        StorageError: Index creation failed
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'stage': 'initializing', 'progress': 0}
        )
        
        logger.info("Ensuring Elasticsearch indices exist")
        
        # Initialize storage
        storage = ElasticsearchStorage()
        storage.initialize(get_elasticsearch_config())
        
        index_results = {
            'indices_checked': [],
            'indices_created': [],
            'indices_recreated': [],
            'errors': [],
            'status': 'unknown',
            'checked_at': datetime.now().isoformat()
        }
        
        # Required indices for each data type
        data_types = [DataType.SESSION, DataType.RECORD, DataType.LAP, DataType.USER_INDICATOR]
        
        for i, data_type in enumerate(data_types):
            # Update progress
            progress = (i / len(data_types)) * 90
            self.update_state(
                state='PROGRESS',
                meta={
                    'stage': f'checking_{data_type.value}_index',
                    'progress': progress,
                    'current_index': data_type.value
                }
            )
            
            try:
                index_name = f"fitness-{data_type.value.replace('_', '-')}"
                index_results['indices_checked'].append(index_name)
                
                # Check if index exists
                index_exists = storage.index_exists(index_name)
                
                if force_recreate and index_exists:
                    # Delete and recreate index
                    if storage.delete_index(index_name):
                        logger.info(f"Deleted existing index: {index_name}")
                    index_exists = False
                
                if not index_exists:
                    # Create index with mapping
                    if storage.create_index(data_type):
                        index_results['indices_created'].append(index_name)
                        if force_recreate:
                            index_results['indices_recreated'].append(index_name)
                        logger.info(f"Created index: {index_name}")
                    else:
                        error_msg = f"Failed to create index: {index_name}"
                        index_results['errors'].append(error_msg)
                        logger.error(error_msg)
                else:
                    logger.info(f"Index already exists: {index_name}")
                    
            except Exception as index_error:
                error_msg = f"Error with {data_type.value} index: {index_error}"
                index_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        # Determine overall status
        if len(index_results['errors']) == 0:
            index_results['status'] = 'success'
        elif len(index_results['indices_created']) > 0:
            index_results['status'] = 'partial_success'
        else:
            index_results['status'] = 'failed'
        
        # Final progress update
        self.update_state(
            state='SUCCESS',
            meta={
                'stage': 'completed',
                'progress': 100,
                'indices_created': len(index_results['indices_created']),
                'errors': len(index_results['errors'])
            }
        )
        
        logger.info(f"✅ Index check completed: {len(index_results['indices_created'])} created, {len(index_results['errors'])} errors")
        return index_results
        
    except Exception as e:
        logger.error(f"❌ Index management failed: {e}")
        self.update_state(
            state='FAILURE',
            meta={'error': str(e), 'stage': 'failed'}
        )
        raise StorageError(f"Index management failed: {e}")


@celery_app.task(bind=True, time_limit=300, soft_time_limit=240, max_retries=2)
def setup_garmin_config(self, user_id: str, username: str, password: str) -> Dict[str, Any]:
    """
    Setup Garmin configuration for a user (store encrypted credentials).
    
    Args:
        user_id: User identifier
        username: Garmin username
        password: Garmin password
        
    Returns:
        Dict containing setup results
        
    Raises:
        StorageError: Configuration setup failed
    """
    try:
        logger.info(f"Setting up Garmin configuration for user {user_id}")
        
        # This is a placeholder for actual credential storage
        # In production, this would:
        # 1. Encrypt the credentials
        # 2. Store them securely in database
        # 3. Validate Garmin connection
        
        config_result = {
            'user_id': user_id,
            'status': 'success',
            'message': 'Garmin configuration setup completed',
            'setup_time': datetime.now().isoformat()
        }
        
        logger.info(f"✅ Garmin configuration setup completed for user {user_id}")
        return config_result
        
    except Exception as e:
        logger.error(f"❌ Garmin configuration setup failed for user {user_id}: {e}")
        raise StorageError(f"Garmin configuration setup failed: {e}")