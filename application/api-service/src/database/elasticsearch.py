"""
Elasticsearch connection management for the application.
"""

import urllib.parse
from typing import Optional
from fastapi import HTTPException, status
import structlog

from peakflow import ElasticsearchStorage
from ..config import get_settings

logger = structlog.get_logger(__name__)


def get_elasticsearch_storage() -> ElasticsearchStorage:
    """Initialize and return Elasticsearch storage instance using main application settings."""
    settings = get_settings()
    
    # Construct hosts with authentication if credentials are provided
    hosts = [settings.elasticsearch_host]
    if settings.elasticsearch_user and settings.elasticsearch_password:
        # Add authentication to the host URL
        parsed = urllib.parse.urlparse(settings.elasticsearch_host)
        auth_host = f"{parsed.scheme}://{settings.elasticsearch_user}:{settings.elasticsearch_password}@{parsed.netloc}{parsed.path}"
        hosts = [auth_host]
    
    storage_config = {
        'hosts': hosts,
        'request_timeout': 30,  # Default timeout
        'max_retries': 3,       # Default retries
        'retry_on_timeout': True,
        'verify_certs': False,
    }
    
    logger.info(f"Initializing Elasticsearch with host: {settings.elasticsearch_host}")
    if settings.elasticsearch_user:
        logger.info(f"Using Elasticsearch authentication for user: {settings.elasticsearch_user}")
    
    storage = ElasticsearchStorage()
    if not storage.initialize(storage_config):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to connect to Elasticsearch"
        )
    
    return storage


# Global storage instance for reuse
_elasticsearch_storage: Optional[ElasticsearchStorage] = None


def get_elasticsearch_instance() -> ElasticsearchStorage:
    """Get or create a singleton Elasticsearch storage instance."""
    global _elasticsearch_storage
    
    if _elasticsearch_storage is None:
        _elasticsearch_storage = get_elasticsearch_storage()
        logger.info("Elasticsearch connection established")
    
    return _elasticsearch_storage


def check_elasticsearch_connection() -> bool:
    """Check if Elasticsearch connection is healthy."""
    try:
        storage = get_elasticsearch_instance()
        # Try a simple operation to test the connection
        return storage.es.ping()
    except Exception as e:
        logger.error(f"Elasticsearch connection check failed: {e}")
        return False


def get_elasticsearch_settings():
    """Get Elasticsearch settings from main application settings."""
    return get_settings()
