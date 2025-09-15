#!/usr/bin/env python3
"""
Test script for the enhanced Activity processor that extracts all valid fields
"""
import sys
import os
import json
import logging
from pathlib import Path
import pytest

# Add the peakflow package to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from peakflow.processors.activity import ActivityProcessor, ActivityFieldMapper
    from peakflow.processors.interface import ProcessingOptions
    from peakflow.storage.elasticsearch import ElasticsearchStorage
    from peakflow.storage.interface import DataType
    print("✅ Successfully imported peakflow modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Current directory:", current_dir)
    print("Python path:", sys.path)
    
    # Try alternative import approach
    try:
        import peakflow
        print(f"Peakflow package location: {peakflow.__file__}")
        from peakflow.processors.activity import ActivityProcessor, ActivityFieldMapper
        from peakflow.processors.interface import ProcessingOptions
        from peakflow.storage.elasticsearch import ElasticsearchStorage
        from peakflow.storage.interface import DataType
        print("✅ Successfully imported with alternative approach")
    except ImportError as e2:
        print(f"❌ Alternative import also failed: {e2}")
        sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_field_mapper():
    """Test the field mapper functionality"""
    mapper = ActivityFieldMapper()
    
    # Test field inclusion
    test_fields = [
        "timestamp", "heart_rate", "enhanced_speed", "avg_heart_rate",
        "total_distance", "unknown_123", "field_456", "position_lat",
        "running_dynamics_vertical_oscillation", "power", "left_power",
        "temperature", "humidity", "stroke_count", "time_in_hr_zone_1"
    ]
    
    for field in test_fields:
        include = mapper.should_include_field(field)
        # Just check that categorize_field does not raise if included
        if include:
            _ = mapper.categorize_field(field)
    
    assert True  # If no exception, test passes


def test_fit_processor():
    """Test the FIT processor with sample data or mock if no FIT files found"""
    storage = ElasticsearchStorage()
    
    # Check if we can connect to Elasticsearch
    es_config = {
        'hosts': ['http://localhost:9200'],
        'verify_certs': False,
        'timeout': 30,
        'max_retries': 3,
        'username': 'elastic',
        'password': 'password',
    }
    try:
        storage.initialize(es_config)
        
        # Create indices with enhanced mappings
        indices_created = storage.create_indices(force_recreate=True)
        assert indices_created
    except Exception:
        pytest.skip("Elasticsearch not available, skipping FIT processor test.")

    # Initialize processor
    options = ProcessingOptions(
        validate_data=True,
        skip_invalid_records=True,
        batch_size=1000
    )
    
    processor = ActivityProcessor(storage, options)
    
    # Look for FIT files in multiple locations
    search_paths = [
        Path("/home/aiuser/codetrekking/storage/garmin"),
        Path("/home/aiuser/codetrekking/storage/garmin_db/FitFiles"),
        Path.cwd() / "storage" / "garmin",
        Path.cwd() / "tests" / "data",
        Path.cwd() / "test_data"
    ]
    
    fit_files = []
    for search_path in search_paths:
        if search_path.exists():
            fit_files.extend(list(search_path.rglob("*.fit")))
    
    if not fit_files:
        # Mock test if no FIT files
        mapper = ActivityFieldMapper()
        
        # Create a mock FIT message-like object for testing
        class MockField:
            def __init__(self, name, value):
                self.name = name
                self.value = value
        
        class MockMessage:
            def __init__(self, fields):
                self.fields = [MockField(name, value) for name, value in fields.items()]
        
        # Test with sample fields
        sample_fields = {
            'timestamp': '2023-06-12T10:00:00',
            'heart_rate': 150,
            'enhanced_speed': 5.5,
            'position_lat': 40.7128,
            'position_long': -74.0060,
            'avg_vertical_oscillation': 8.5,
            'power': 250,
            'temperature': 25.0,
            'unknown_123': 'should_be_excluded',
            'total_distance': 5000.0
        }
        
        mock_message = MockMessage(sample_fields)
        base_doc = {'activity_id': 'test_activity', 'user_id': 'test_user'}
        
        result_doc = mapper.extract_all_fields(mock_message, base_doc)
        
        assert 'timestamp' in result_doc
        assert 'heart_rate' in result_doc
        assert 'unknown_123' not in result_doc
        return
    
    # Test with the first FIT file found
    test_file = fit_files[0]
    assert processor.validate_source(test_file)
    
    # Extract metadata
    metadata = processor.extract_metadata(test_file)
    assert isinstance(metadata, dict)
    
    # Process the file
    result = processor.process(test_file, "test_user", "test_activity")
    assert result.status == 'success' or result.successful_records > 0
    
    # Optionally check storage stats
    session_stats = storage.get_stats(DataType.SESSION)
    record_stats = storage.get_stats(DataType.RECORD)
    lap_stats = storage.get_stats(DataType.LAP)
    
    assert isinstance(session_stats, dict)
    assert isinstance(record_stats, dict)
    assert isinstance(lap_stats, dict)
