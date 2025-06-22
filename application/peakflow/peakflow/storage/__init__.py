#!/usr/bin/env python3
"""
Storage Module - Storage layer abstraction and implementation
"""

from .interface import (
    StorageInterface, 
    DataType, 
    QueryFilter, 
    AggregationQuery, 
    IndexingResult,
    DataValidator,
    ValidationError,
    StorageError
)

from .elasticsearch import ElasticsearchStorage

__all__ = [
    'StorageInterface', 
    'DataType', 
    'QueryFilter', 
    'AggregationQuery', 
    'IndexingResult',
    'DataValidator',
    'ValidationError',
    'StorageError',
    'ElasticsearchStorage'
]
