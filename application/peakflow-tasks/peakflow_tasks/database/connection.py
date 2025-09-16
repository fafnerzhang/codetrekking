"""
Database connection utilities for PeakFlow Tasks.

This module provides database connection and session management for PeakFlow Tasks
to access the shared PostgreSQL database. Uses SQLModel for consistency with api-service.
"""

import logging
from typing import Generator
from sqlmodel import create_engine, Session
from sqlalchemy.pool import StaticPool

from ..config import get_database_config

logger = logging.getLogger(__name__)

# Global engine and session factory - initialized on first use
_engine = None


def get_engine():
    """Get or create the database engine."""
    global _engine
    
    if _engine is None:
        db_config = get_database_config()
        database_url = db_config.get('url')
        
        if not database_url:
            # Build URL from components
            host = db_config.get('host', 'localhost')
            port = db_config.get('port', 5432)
            database = db_config.get('database', 'codetrekking')
            username = db_config.get('username', 'codetrekking')
            password = db_config.get('password', 'ChangeMe')
            database_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        
        # Create engine with connection pooling
        _engine = create_engine(
            database_url,
            poolclass=StaticPool,
            pool_pre_ping=True,
            pool_recycle=3600,  # Recycle connections every hour
            echo=False  # Set to True for SQL debug logging
        )
        logger.info(f"Created database engine for PeakFlow Tasks")
    
    return _engine


def get_database_session() -> Generator[Session, None, None]:
    """
    Get a database session for dependency injection.
    
    Yields:
        Session: SQLModel database session
        
    Usage:
        with get_database_session() as db:
            # Use db session
            pass
    """
    engine = get_engine()
    with Session(engine) as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            session.rollback()
            raise


def get_database() -> Session:
    """
    Get a database session for direct use in Celery tasks.
    
    Returns:
        Session: SQLModel database session
        
    Note: Caller is responsible for closing the session
    """
    engine = get_engine()
    return Session(engine)