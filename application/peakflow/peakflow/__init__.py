#!/usr/bin/env python3
"""
PeakFlow - Fitness Data Analytics and Storage Abstraction Layer
Provides unified interface supporting multiple storage backends (Elasticsearch, RDBMS, etc.)
"""

# Setup logging first
from .utils import setup_peakflow_logging
setup_peakflow_logging()

# Storage interfaces and implementations
from .storage.interface import (
    StorageInterface,
    DataType, QueryFilter, AggregationQuery, IndexingResult,
    DataValidator, ValidationError, StorageError
)
from .storage.elasticsearch import ElasticsearchStorage

# Data processors
from .processors.fit import FitFileProcessor

# Analytics and statistics
from .analytics.advanced import AdvancedStatistics

__version__ = "0.1.0"

__all__ = [
    # Storage interfaces
    'StorageInterface',
    'DataType', 'QueryFilter', 'AggregationQuery', 'IndexingResult',
    'DataValidator', 'ValidationError', 'StorageError',
    
    # Storage implementations
    'ElasticsearchStorage',
    
    # Data processors
    'FitFileProcessor',
    
    # Analytics
    'AdvancedStatistics',
]