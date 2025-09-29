#!/usr/bin/env python3
"""
Comprehensive test suite for TSS (Training Stress Score) calculations.

This test suite covers all TSS calculation methods:
- Power-based TSS
- Heart Rate-based TSS (hrTSS)
- Running Pace-based TSS (rTSS)
- Composite TSS calculation
- Batch processing and indexing
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import numpy as np
from statistics import mean

# Import modules under test
from peakflow.analytics.tss import TSSCalculator, TSSAnalyzer, WorkoutPlanSegment, WorkoutPlan
from peakflow.analytics.interface import (
    MetricThresholds, AnalyticsFilter, TimeRange, AnalyticsType,
    InsufficientDataError, CalculationError
)
from peakflow.storage.interface import StorageInterface, DataType
from pydantic import ValidationError


class MockStorageInterface:
    """Mock storage interface for testing TSS calculations without Elasticsearch dependency"""

    def __init__(self):
        self.documents = {}
        self.search_results = {}
        self.index_success = True

    def search(self, data_type: DataType, query_filter) -> List[Dict[str, Any]]:
        """Mock search method"""
        key = f"{data_type.value}_{query_filter}"
        return self.search_results.get(key, [])

    def get_by_id(self, data_type: DataType, doc_id: str) -> Optional[Dict[str, Any]]:
        """Mock get by ID method"""
        return self.documents.get(f"{data_type.value}_{doc_id}")

    def index_document(self, data_type: DataType, doc_id: str, document: Dict[str, Any]) -> bool:
        """Mock index document method"""
        self.documents[f"{data_type.value}_{doc_id}"] = document
        return self.index_success

    def bulk_index(self, data_type: DataType, documents: List[Dict[str, Any]]) -> object:
        """Mock bulk index method"""
        result = Mock()
        result.success_count = len(documents) if self.index_success else 0
        result.failed_count = 0 if self.index_success else len(documents)
        result.errors = [] if self.index_success else ["Mock error"]
        return result


@pytest.fixture
def mock_storage():
    """Fixture providing mock storage interface"""
    return MockStorageInterface()


@pytest.fixture
def sample_thresholds():
    """Fixture providing sample metric thresholds for testing"""
    return MetricThresholds(
        power_zones={
            "zone_1": (0, 150),
            "zone_2": (150, 200),
            "zone_3": (200, 250),
            "zone_4": (250, 300),
            "zone_5": (300, 400)
        },
        heart_rate_zones={
            "zone_1": (60, 120),
            "zone_2": (120, 140),
            "zone_3": (140, 160),
            "zone_4": (160, 180),
            "zone_5": (180, 200)
        },
        pace_zones={
            "zone_1": (5.0, 6.0),
            "zone_2": (4.5, 5.0),
            "zone_3": (4.0, 4.5),
            "zone_4": (3.5, 4.0),
            "zone_5": (3.0, 3.5)
        },
        functional_threshold_power=250.0,
        lactate_threshold_heart_rate=170,
        critical_pace=4.0,
        max_heart_rate=190,
        resting_heart_rate=60
    )


@pytest.fixture
def tss_calculator(mock_storage, sample_thresholds):
    """Fixture providing configured TSS calculator"""
    return TSSCalculator(mock_storage, sample_thresholds)


@pytest.fixture
def sample_power_data():
    """Fixture providing sample power data for testing"""
    # Simulate 1-hour workout with varying power
    base_power = 200
    data = []
    for i in range(3600):  # 1 hour of data
        # Add some variation to make it realistic
        variation = 20 * np.sin(i / 300) + 10 * np.random.random()
        power = max(0, base_power + variation)
        data.append(power)
    return data


@pytest.fixture
def sample_hr_data():
    """Fixture providing sample heart rate data for testing"""
    # Simulate 1-hour workout with varying HR
    base_hr = 150
    data = []
    for i in range(3600):  # 1 hour of data
        # Add some variation
        variation = 15 * np.sin(i / 200) + 5 * np.random.random()
        hr = max(60, int(base_hr + variation))
        data.append(hr)
    return data


@pytest.fixture
def sample_speed_data():
    """Fixture providing sample speed data for testing (in m/s)"""
    # Simulate 1-hour run at varying pace (around 4:00-5:00 min/km)
    base_speed = 4.17  # ~4:00 min/km
    data = []
    for i in range(3600):  # 1 hour of data
        # Add some variation
        variation = 0.5 * np.sin(i / 400) + 0.2 * np.random.random()
        speed = max(2.0, base_speed + variation)  # Don't go below walking pace
        data.append(speed)
    return data


@pytest.fixture
def sample_raw_records(sample_power_data, sample_hr_data, sample_speed_data):
    """Fixture providing sample raw record data"""
    records = []
    for i, (power, hr, speed) in enumerate(zip(sample_power_data, sample_hr_data, sample_speed_data)):
        record = {
            'timestamp': datetime.now() + timedelta(seconds=i),
            'power': power,
            'heart_rate': hr,
            'speed': speed,
            'enhanced_speed': speed,
            'activity_id': 'test_activity_123'
        }
        records.append(record)
    return records


class TestTSSCalculatorBasics:
    """Test basic TSS calculator functionality"""

    def test_pace_conversion_methods(self, tss_calculator):
        """Test pace conversion utility methods"""
        # Test speed to pace conversion
        speed_ms = 4.17  # ~4:00 min/km
        pace = tss_calculator.speed_to_pace_per_km(speed_ms)
        assert abs(pace - 4.0) < 0.1, f"Expected ~4.0 min/km, got {pace}"

        # Test pace to speed conversion
        pace_min_km = 4.0
        speed = tss_calculator.pace_per_km_to_speed(pace_min_km)
        assert abs(speed - 4.17) < 0.1, f"Expected ~4.17 m/s, got {speed}"

        # Test roundtrip conversion
        original_speed = 5.0
        converted_pace = tss_calculator.speed_to_pace_per_km(original_speed)
        converted_back_speed = tss_calculator.pace_per_km_to_speed(converted_pace)
        assert abs(original_speed - converted_back_speed) < 0.01, "Roundtrip conversion failed"

        # Test edge cases
        assert tss_calculator.speed_to_pace_per_km(0) == float('inf')
        assert tss_calculator.pace_per_km_to_speed(0) == 0.0

    def test_pace_formatting_and_parsing(self, tss_calculator):
        """Test pace formatting and parsing methods"""
        # Test formatting
        pace = 4.5  # 4:30 min/km
        formatted = tss_calculator.format_pace(pace)
        assert formatted == "4:30", f"Expected '4:30', got '{formatted}'"

        # Test parsing
        parsed = tss_calculator.parse_pace("4:30")
        assert abs(parsed - 4.5) < 0.01, f"Expected 4.5, got {parsed}"

        # Test parsing decimal format
        parsed_decimal = tss_calculator.parse_pace("4.5")
        assert abs(parsed_decimal - 4.5) < 0.01, f"Expected 4.5, got {parsed_decimal}"

        # Test edge cases
        assert tss_calculator.format_pace(float('inf')) == "∞:∞"

        with pytest.raises(ValueError):
            tss_calculator.parse_pace("invalid")


class TestPowerTSS:
    """Test power-based TSS calculations"""

    def test_calculate_power_tss_with_raw_data(self, tss_calculator, sample_raw_records):
        """Test power TSS calculation with raw data"""
        result = tss_calculator.calculate_power_tss(
            raw_data=sample_raw_records,
            ftp=250.0
        )

        # Verify result structure
        assert 'tss' in result
        assert 'normalized_power' in result
        assert 'intensity_factor' in result
        assert 'ftp' in result
        assert 'duration_seconds' in result
        assert 'duration_hours' in result
        assert 'avg_power' in result
        assert 'max_power' in result
        assert result['calculation_method'] == 'power'

        # Verify values are reasonable
        assert result['tss'] > 0, "TSS should be positive"
        assert result['intensity_factor'] > 0, "IF should be positive"
        assert result['ftp'] == 250.0, "FTP should match input"
        assert result['duration_hours'] == 1.0, "Should be 1 hour of data"

    def test_calculate_power_tss_without_ftp(self, tss_calculator, sample_raw_records):
        """Test power TSS calculation without explicit FTP (should estimate)"""
        result = tss_calculator.calculate_power_tss(raw_data=sample_raw_records)

        assert 'tss' in result
        assert result['ftp'] == 250.0, "Should use estimated FTP from thresholds"

    def test_calculate_power_tss_insufficient_data(self, tss_calculator):
        """Test power TSS calculation with insufficient data"""
        with pytest.raises(CalculationError):
            tss_calculator.calculate_power_tss(raw_data=[])

    def test_calculate_power_tss_missing_activity_and_data(self, tss_calculator):
        """Test power TSS calculation with missing activity ID and raw data"""
        with pytest.raises(CalculationError):
            tss_calculator.calculate_power_tss()

    def test_normalized_power_calculation(self, tss_calculator):
        """Test normalized power calculation specifically"""
        # Test with constant power
        constant_power = [200] * 3600
        np_result = tss_calculator._calculate_normalized_power(constant_power)
        assert abs(np_result - 200) < 1, "NP should equal constant power"

        # Test with variable power
        variable_power = [150] * 1800 + [250] * 1800  # 30min easy, 30min hard
        np_result = tss_calculator._calculate_normalized_power(variable_power)
        assert np_result > 200, "NP should be higher than average due to harder efforts"

        # Test with short data (less than 30 seconds)
        short_power = [200] * 10
        np_result = tss_calculator._calculate_normalized_power(short_power)
        assert np_result == 200, "Should return average for short data"


class TestHeartRateTSS:
    """Test heart rate-based TSS calculations"""

    def test_calculate_hr_tss_with_raw_data(self, tss_calculator, sample_raw_records):
        """Test HR TSS calculation with raw data"""
        result = tss_calculator.calculate_hr_tss(
            raw_data=sample_raw_records,
            threshold_hr=170,
            max_hr=190
        )

        # Verify result structure
        assert 'tss' in result
        assert 'intensity_factor' in result
        assert 'threshold_hr' in result
        assert 'max_hr' in result
        assert 'avg_hr' in result
        assert 'duration_hours' in result
        assert result['calculation_method'] == 'heart_rate'

        # Verify values are reasonable
        assert result['tss'] > 0, "hrTSS should be positive"
        assert result['intensity_factor'] > 0, "IF should be positive"
        assert result['threshold_hr'] == 170, "Threshold HR should match input"
        assert result['max_hr'] == 190, "Max HR should match input"

    def test_calculate_hr_tss_without_thresholds(self, tss_calculator, sample_raw_records):
        """Test HR TSS calculation without explicit thresholds (should estimate)"""
        result = tss_calculator.calculate_hr_tss(raw_data=sample_raw_records)

        assert 'tss' in result
        assert result['threshold_hr'] == 160, "Should use estimated threshold HR from zones (zone 3 upper bound)"

    def test_calculate_hr_tss_insufficient_data(self, tss_calculator):
        """Test HR TSS calculation with insufficient data"""
        with pytest.raises(CalculationError):
            tss_calculator.calculate_hr_tss(raw_data=[])

    def test_hr_intensity_factor_calculation(self, tss_calculator):
        """Test HR intensity factor calculation"""
        # Test with data at threshold
        threshold_hr_data = [170] * 3600
        if_result = tss_calculator._calculate_hr_intensity_factor(threshold_hr_data, 170, 190)
        assert abs(if_result - 1.0) < 0.1, "IF should be ~1.0 at threshold"

        # Test with data below threshold
        easy_hr_data = [140] * 3600
        if_result = tss_calculator._calculate_hr_intensity_factor(easy_hr_data, 170, 190)
        assert if_result < 1.0, "IF should be < 1.0 below threshold"

        # Test with data above threshold
        hard_hr_data = [180] * 3600
        if_result = tss_calculator._calculate_hr_intensity_factor(hard_hr_data, 170, 190)
        assert if_result > 1.0, "IF should be > 1.0 above threshold"


class TestRunningPaceTSS:
    """Test running pace-based TSS calculations"""

    def test_calculate_running_pace_tss_with_raw_data(self, tss_calculator, sample_raw_records):
        """Test running pace TSS calculation with raw data"""
        result = tss_calculator.calculate_running_pace_tss(
            raw_data=sample_raw_records,
            threshold_pace=4.0
        )

        # Verify result structure
        assert 'tss' in result
        assert 'normalized_pace' in result
        assert 'normalized_pace_formatted' in result
        assert 'intensity_factor' in result
        assert 'threshold_pace' in result
        assert 'threshold_pace_formatted' in result
        assert 'avg_pace' in result
        assert 'avg_pace_formatted' in result
        assert 'best_pace' in result
        assert 'best_pace_formatted' in result
        assert result['calculation_method'] == 'pace'

        # Verify values are reasonable
        assert result['tss'] > 0, "rTSS should be positive"
        assert result['intensity_factor'] > 0, "IF should be positive"
        assert result['threshold_pace'] == 4.0, "Threshold pace should match input"

    def test_calculate_running_pace_tss_without_threshold(self, tss_calculator, sample_raw_records):
        """Test running pace TSS calculation without explicit threshold (should estimate)"""
        result = tss_calculator.calculate_running_pace_tss(raw_data=sample_raw_records)

        assert 'tss' in result
        assert result['threshold_pace'] == 4.0, "Should use estimated threshold pace from zones"

    def test_calculate_running_pace_tss_insufficient_data(self, tss_calculator):
        """Test running pace TSS calculation with insufficient data"""
        with pytest.raises(CalculationError):
            tss_calculator.calculate_running_pace_tss(raw_data=[])

    def test_calculate_pace_tss_backward_compatibility(self, tss_calculator, sample_raw_records):
        """Test backward compatibility method"""
        result = tss_calculator.calculate_pace_tss(
            raw_data=sample_raw_records,
            threshold_pace=4.0
        )

        assert 'tss' in result
        assert result['calculation_method'] == 'pace'

    def test_normalized_pace_calculation(self, tss_calculator):
        """Test normalized pace calculation specifically"""
        # Create pace data (convert from speed)
        constant_speed = [4.17] * 3600  # ~4:00 min/km
        pace_data = [tss_calculator.speed_to_pace_per_km(s) for s in constant_speed]

        np_result = tss_calculator._calculate_normalized_pace(pace_data)
        assert abs(np_result - 4.0) < 0.1, "Normalized pace should be close to constant pace"


class TestCompositeTSS:
    """Test composite TSS calculation"""

    def test_calculate_composite_tss_with_all_data(self, tss_calculator, sample_raw_records):
        """Test composite TSS calculation with all data types available"""
        result = tss_calculator.calculate_composite_tss(
            raw_data=sample_raw_records,
            user_id="test_user",
            ftp=250.0,
            threshold_hr=170,
            max_hr=190,
            threshold_pace=4.0
        )

        # Should prioritize power TSS
        assert result['primary_method'] == 'power'
        assert 'power_tss' in result
        assert 'hr_tss' in result
        assert 'pace_tss' in result
        assert 'tss' in result
        assert result['tss'] == result['power_tss']['tss']

    def test_calculate_composite_tss_hr_only(self, tss_calculator):
        """Test composite TSS calculation with only HR data"""
        hr_only_records = [
            {'heart_rate': 150 + i % 20, 'timestamp': datetime.now() + timedelta(seconds=i)}
            for i in range(3600)
        ]

        result = tss_calculator.calculate_composite_tss(
            raw_data=hr_only_records,
            threshold_hr=170,
            max_hr=190
        )

        # Should use HR TSS as primary
        assert result['primary_method'] == 'heart_rate'
        assert 'hr_tss' in result
        assert 'power_tss' not in result
        assert 'pace_tss' not in result

    def test_calculate_composite_tss_no_data(self, tss_calculator):
        """Test composite TSS calculation with no suitable data"""
        with pytest.raises(InsufficientDataError):
            tss_calculator.calculate_composite_tss(raw_data=[])

    def test_calculate_composite_tss_with_user_thresholds(self, tss_calculator, sample_raw_records):
        """Test composite TSS calculation using stored user thresholds"""
        # Mock user thresholds retrieval
        with patch.object(tss_calculator, '_get_user_thresholds') as mock_get_thresholds:
            mock_get_thresholds.return_value = {
                'ftp': 275.0,
                'threshold_hr': 175,
                'max_hr': 195,
                'threshold_pace': 3.8
            }

            result = tss_calculator.calculate_composite_tss(
                raw_data=sample_raw_records,
                user_id="test_user"
            )

            assert 'thresholds_used' in result
            assert result['thresholds_used']['ftp'] == 275.0
            assert result['thresholds_used']['source'] == 'user_indicators'


class TestTSSIndexingAndRetrieval:
    """Test TSS indexing and retrieval functionality"""

    def test_calculate_and_index_tss(self, tss_calculator, mock_storage):
        """Test TSS calculation and indexing"""
        # Mock activity context
        mock_storage.search_results['session_activity_123'] = [{
            'sport': 'cycling',
            'sub_sport': 'road',
            'total_distance': 40000,  # 40km
            'total_timer_time': 3600,  # 1 hour
            'total_calories': 800,
            'timestamp': datetime.now().isoformat(),
            'start_time': datetime.now().isoformat()
        }]

        # Mock power data retrieval
        with patch.object(tss_calculator, '_get_power_data') as mock_get_power:
            mock_get_power.return_value = [200] * 3600  # 1 hour at 200W

            result = tss_calculator.calculate_and_index_tss(
                activity_id="activity_123",
                user_id="user_456",
                ftp=250.0
            )

            assert result['indexing_status'] == 'success'
            assert 'doc_id' in result
            assert result['doc_id'] == "user_456_activity_123"

    def test_batch_calculate_and_index_tss(self, tss_calculator, mock_storage):
        """Test batch TSS calculation and indexing"""
        activities = [
            {'activity_id': 'act_1', 'user_id': 'user_1'},
            {'activity_id': 'act_2', 'user_id': 'user_1'},
            {'activity_id': 'act_3', 'user_id': 'user_2'}
        ]

        # Mock data retrieval for all activities
        with patch.object(tss_calculator, '_get_power_data') as mock_get_power, \
             patch.object(tss_calculator, '_get_activity_context') as mock_get_context:

            mock_get_power.return_value = [200] * 3600
            mock_get_context.return_value = {
                'sport': 'cycling',
                'total_distance': 40000,
                'total_duration': 3600,
                'timestamp': datetime.now().isoformat()
            }

            result = tss_calculator.batch_calculate_and_index_tss(
                activities,
                ftp=250.0
            )

            assert result['total'] == 3
            assert result['successful'] == 3
            assert result['failed'] == 0
            assert 'indexing_result' in result

    def test_get_tss_by_activity(self, tss_calculator, mock_storage):
        """Test TSS retrieval by activity"""
        # Store mock TSS document
        tss_doc = {
            'activity_id': 'activity_123',
            'user_id': 'user_456',
            'primary_tss': 100.0,
            'primary_method': 'power'
        }
        mock_storage.documents['tss_user_456_activity_123'] = tss_doc

        result = tss_calculator.get_tss_by_activity("activity_123", "user_456")

        assert result == tss_doc

    def test_get_user_tss_history(self, tss_calculator, mock_storage):
        """Test user TSS history retrieval"""
        # Mock search results
        mock_storage.search_results['tss_user_456'] = [
            {'activity_id': 'act_1', 'primary_tss': 80.0, 'timestamp': '2024-01-01'},
            {'activity_id': 'act_2', 'primary_tss': 100.0, 'timestamp': '2024-01-02'},
            {'activity_id': 'act_3', 'primary_tss': 120.0, 'timestamp': '2024-01-03'}
        ]

        with patch.object(mock_storage, 'search') as mock_search:
            mock_search.return_value = mock_storage.search_results['tss_user_456']

            result = tss_calculator.get_user_tss_history("user_456")

            assert len(result) == 3
            assert all('primary_tss' in r for r in result)


class TestTSSAnalyzer:
    """Test TSS analyzer functionality"""

    def test_analyze_training_stress(self, mock_storage, sample_thresholds):
        """Test training stress analysis"""
        analyzer = TSSAnalyzer(mock_storage, sample_thresholds)

        # Mock activity data
        activities = [
            {
                'activity_id': 'act_1',
                'sport': 'cycling',
                'timestamp': datetime.now() - timedelta(days=1)
            },
            {
                'activity_id': 'act_2',
                'sport': 'running',
                'timestamp': datetime.now() - timedelta(days=2)
            }
        ]

        with patch.object(mock_storage, 'search') as mock_search, \
             patch.object(analyzer.calculator, 'calculate_composite_tss') as mock_calc_tss:

            mock_search.return_value = activities
            mock_calc_tss.side_effect = [
                {'tss': 100.0, 'primary_method': 'power'},
                {'tss': 80.0, 'primary_method': 'heart_rate'}
            ]

            filter_criteria = AnalyticsFilter(
                user_id="user_123",
                time_range=TimeRange(days=7)
            )

            result = analyzer.analyze_training_stress(filter_criteria)

            assert result.analytics_type == AnalyticsType.TRAINING_LOAD
            assert result.data['total_tss'] == 180.0
            assert result.data['activity_count'] == 2
            assert 'sport_breakdown' in result.data

    def test_categorize_training_load(self, mock_storage, sample_thresholds):
        """Test training load categorization"""
        analyzer = TSSAnalyzer(mock_storage, sample_thresholds)

        assert analyzer._categorize_training_load(100) == "low"
        assert analyzer._categorize_training_load(250) == "moderate"
        assert analyzer._categorize_training_load(400) == "high"
        assert analyzer._categorize_training_load(500) == "very_high"


class TestTSSDataExtraction:
    """Test data extraction methods"""

    def test_extract_power_value(self, tss_calculator):
        """Test power value extraction from various record formats"""
        # Standard power field
        record1 = {'power': 200.0}
        assert tss_calculator._extract_power_value(record1) == 200.0

        # Enhanced power field
        record2 = {'enhanced_power': 250.0}
        assert tss_calculator._extract_power_value(record2) == 250.0

        # Nested power fields
        record3 = {'power_fields': {'power': 275.0}}
        assert tss_calculator._extract_power_value(record3) == 275.0

        # No power data
        record4 = {'heart_rate': 150}
        assert tss_calculator._extract_power_value(record4) is None

        # Zero power (should be ignored)
        record5 = {'power': 0}
        assert tss_calculator._extract_power_value(record5) is None

    def test_extract_speed_value(self, tss_calculator):
        """Test speed value extraction from various record formats"""
        # Standard speed field
        record1 = {'speed': 4.17}
        assert tss_calculator._extract_speed_value(record1) == 4.17

        # Enhanced speed field
        record2 = {'enhanced_speed': 5.0}
        assert tss_calculator._extract_speed_value(record2) == 5.0

        # Nested additional fields
        record3 = {'additional_fields': {'enhanced_speed': 3.5}}
        assert tss_calculator._extract_speed_value(record3) == 3.5

        # Nested speed metrics
        record4 = {'speed_metrics': {'avg_speed': 4.0}}
        assert tss_calculator._extract_speed_value(record4) == 4.0

        # No speed data
        record5 = {'heart_rate': 150}
        assert tss_calculator._extract_speed_value(record5) is None


class TestTSSEdgeCases:
    """Test edge cases and error conditions"""

    def test_tss_calculation_with_extreme_values(self, tss_calculator):
        """Test TSS calculation with extreme values"""
        # Very high power data
        extreme_power_records = [
            {'power': 1000, 'timestamp': datetime.now() + timedelta(seconds=i)}
            for i in range(3600)
        ]

        result = tss_calculator.calculate_power_tss(
            raw_data=extreme_power_records,
            ftp=250.0
        )

        # Should handle extreme values gracefully
        assert result['tss'] > 0
        assert result['intensity_factor'] > 3.0  # Very high intensity

    def test_tss_calculation_with_missing_timestamps(self, tss_calculator):
        """Test TSS calculation with missing timestamp data"""
        records_no_timestamps = [
            {'power': 200 + i % 50}
            for i in range(3600)
        ]

        # Should still work (duration based on record count)
        result = tss_calculator.calculate_power_tss(
            raw_data=records_no_timestamps,
            ftp=250.0
        )

        assert result['tss'] > 0
        assert result['duration_seconds'] == 3600

    def test_threshold_estimation_fallbacks(self, mock_storage):
        """Test threshold estimation fallbacks"""
        # Calculator without predefined thresholds
        calculator = TSSCalculator(mock_storage, MetricThresholds())

        # Should use default fallback values
        ftp = calculator._estimate_ftp("test_activity")
        assert ftp == 250.0, "Should use default FTP fallback"

        threshold_hr = calculator._estimate_threshold_hr()
        assert threshold_hr == 170, "Should use default threshold HR fallback"

        threshold_pace = calculator._estimate_threshold_pace("test_activity")
        assert threshold_pace == 4.0, "Should use default threshold pace fallback"


# Integration test with mocked Elasticsearch
class TestTSSElasticsearchIntegration:
    """Test TSS functionality with Elasticsearch integration (mocked)"""

    @pytest.fixture
    def es_mock(self):
        """Mock Elasticsearch client"""
        with patch('elasticsearch.Elasticsearch') as mock_es:
            mock_client = Mock()
            mock_client.ping.return_value = True
            mock_client.search.return_value = {
                'hits': {'hits': []}
            }
            mock_client.index.return_value = {'result': 'created'}
            mock_es.return_value = mock_client
            yield mock_client

    def test_tss_with_elasticsearch_storage(self, es_mock, sample_thresholds):
        """Test TSS calculation with Elasticsearch storage backend"""
        # This would test integration with actual storage interface
        # For now, we verify that our TSS calculations work independently
        # of the storage backend

        calculator = TSSCalculator(MockStorageInterface(), sample_thresholds)

        # Create sample data
        sample_records = [
            {
                'power': 200 + (i % 100),
                'heart_rate': 150 + (i % 30),
                'speed': 4.0 + (i % 10) * 0.1,
                'timestamp': datetime.now() + timedelta(seconds=i)
            }
            for i in range(3600)
        ]

        # Test all TSS calculation methods
        power_tss = calculator.calculate_power_tss(raw_data=sample_records, ftp=250.0)
        hr_tss = calculator.calculate_hr_tss(raw_data=sample_records, threshold_hr=170, max_hr=190)
        pace_tss = calculator.calculate_running_pace_tss(raw_data=sample_records, threshold_pace=4.0)

        # All should succeed
        assert all(result['tss'] > 0 for result in [power_tss, hr_tss, pace_tss])

        # Composite calculation should work
        composite = calculator.calculate_composite_tss(
            raw_data=sample_records,
            ftp=250.0,
            threshold_hr=170,
            max_hr=190,
            threshold_pace=4.0
        )

        assert composite['primary_method'] == 'power'
        assert composite['tss'] == power_tss['tss']


class TestWorkoutPlanDataStructures:
    """Test Pydantic data structures for workout plans"""

    def test_workout_plan_segment_validation(self):
        """Test WorkoutPlanSegment validation"""
        # Valid segment
        segment = WorkoutPlanSegment(
            duration_minutes=30.0,
            intensity_metric='power',
            target_value=250.0
        )
        assert segment.duration_minutes == 30.0
        assert segment.intensity_metric == 'power'
        assert segment.target_value == 250.0
        assert segment.duration_hours() == 0.5

        # Test validation errors
        with pytest.raises(ValidationError, match="Input should be greater than 0"):
            WorkoutPlanSegment(duration_minutes=-10, intensity_metric='power', target_value=250)

        with pytest.raises(ValidationError, match="Input should be greater than 0"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=-100)

        with pytest.raises(ValidationError):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='invalid', target_value=250)

    def test_workout_plan_segment_target_value_validation(self):
        """Test target value validation based on intensity metric"""
        # Valid power segment
        power_segment = WorkoutPlanSegment(
            duration_minutes=30.0,
            intensity_metric='power',
            target_value=300.0
        )
        assert power_segment.target_value == 300.0

        # Invalid power - too high
        with pytest.raises(ValidationError, match="Power target seems unreasonably high"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=3000)

        # Valid HR segment
        hr_segment = WorkoutPlanSegment(
            duration_minutes=30.0,
            intensity_metric='heart_rate',
            target_value=160.0
        )
        assert hr_segment.target_value == 160.0

        # Invalid HR - too high
        with pytest.raises(ValidationError, match="Heart rate target should be between 30-250 bpm"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='heart_rate', target_value=300)

        # Invalid HR - too low
        with pytest.raises(ValidationError, match="Heart rate target should be between 30-250 bpm"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='heart_rate', target_value=20)

        # Valid pace segment
        pace_segment = WorkoutPlanSegment(
            duration_minutes=30.0,
            intensity_metric='pace',
            target_value=4.5
        )
        assert pace_segment.target_value == 4.5

        # Invalid pace - too fast
        with pytest.raises(ValidationError, match="Pace target should be between 1:00-20:00 min/km"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='pace', target_value=0.5)

        # Invalid pace - too slow
        with pytest.raises(ValidationError, match="Pace target should be between 1:00-20:00 min/km"):
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='pace', target_value=25.0)

    def test_workout_plan_validation(self):
        """Test WorkoutPlan validation"""
        segments = [
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='power', target_value=150),
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=250),
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='power', target_value=150)
        ]

        # Valid workout plan
        plan = WorkoutPlan(segments=segments, name="Test Workout")
        assert len(plan.segments) == 3
        assert plan.name == "Test Workout"
        assert plan.total_duration_minutes() == 50.0
        assert plan.total_duration_hours() == 50.0 / 60.0

        # Empty segments should fail
        with pytest.raises(ValidationError, match="List should have at least 1 item"):
            WorkoutPlan(segments=[])


class TestWorkoutPlanTSSEstimation:
    """Test workout plan TSS estimation functionality"""

    def test_estimate_power_workout_plan_tss(self, tss_calculator):
        """Test TSS estimation for power-based workout plan"""
        # Create a power-based workout plan: 10min easy + 20min threshold + 10min easy
        segments = [
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='power', target_value=150),  # Easy
            WorkoutPlanSegment(duration_minutes=20, intensity_metric='power', target_value=250),  # Threshold
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='power', target_value=150)   # Easy
        ]
        workout_plan = WorkoutPlan(segments=segments, name="Power Workout")

        result = tss_calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            ftp=250.0
        )

        # Verify result structure
        assert 'estimated_tss' in result
        assert 'total_duration_minutes' in result
        assert 'total_duration_hours' in result
        assert 'segment_count' in result
        assert 'primary_method' in result
        assert 'segments' in result
        assert 'thresholds_used' in result
        assert result['calculation_method'] == 'workout_plan_estimation'

        # Verify values
        assert result['total_duration_minutes'] == 40.0
        assert result['segment_count'] == 3
        assert result['primary_method'] == 'power'
        assert result['estimated_tss'] > 0
        assert len(result['segments']) == 3

        # Verify segment details
        for i, segment_result in enumerate(result['segments']):
            assert segment_result['intensity_metric'] == 'power'
            assert segment_result['duration_minutes'] == segments[i].duration_minutes
            assert segment_result['target_value'] == segments[i].target_value
            assert 'estimated_tss' in segment_result
            assert 'intensity_factor' in segment_result
            assert 'normalized_power' in segment_result

    def test_estimate_hr_workout_plan_tss(self, tss_calculator):
        """Test TSS estimation for heart rate-based workout plan"""
        segments = [
            WorkoutPlanSegment(duration_minutes=15, intensity_metric='heart_rate', target_value=140),  # Zone 2
            WorkoutPlanSegment(duration_minutes=20, intensity_metric='heart_rate', target_value=170),  # Threshold
            WorkoutPlanSegment(duration_minutes=15, intensity_metric='heart_rate', target_value=140)   # Zone 2
        ]
        workout_plan = WorkoutPlan(segments=segments, name="HR Workout")

        result = tss_calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            threshold_hr=170,
            max_hr=190
        )

        assert result['primary_method'] == 'heart_rate'
        assert result['total_duration_minutes'] == 50.0
        assert result['estimated_tss'] > 0
        assert len(result['segments']) == 3

        # Verify HR-specific segment details
        for segment_result in result['segments']:
            assert segment_result['intensity_metric'] == 'heart_rate'
            assert 'estimated_tss' in segment_result
            assert 'intensity_factor' in segment_result
            assert 'avg_hr' in segment_result

    def test_estimate_pace_workout_plan_tss(self, tss_calculator):
        """Test TSS estimation for pace-based workout plan"""
        segments = [
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='pace', target_value=5.0),   # Easy
            WorkoutPlanSegment(duration_minutes=15, intensity_metric='pace', target_value=4.0),   # Threshold
            WorkoutPlanSegment(duration_minutes=20, intensity_metric='pace', target_value=3.5),   # Fast
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='pace', target_value=5.0)    # Easy
        ]
        workout_plan = WorkoutPlan(segments=segments, name="Running Workout")

        result = tss_calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            threshold_pace=4.0
        )

        assert result['primary_method'] == 'pace'
        assert result['total_duration_minutes'] == 55.0
        assert result['estimated_tss'] > 0
        assert len(result['segments']) == 4

        # Verify pace-specific segment details
        for segment_result in result['segments']:
            assert segment_result['intensity_metric'] == 'pace'
            assert 'estimated_tss' in segment_result
            assert 'intensity_factor' in segment_result
            assert 'target_pace_formatted' in segment_result
            assert 'normalized_pace' in segment_result

    def test_estimate_mixed_workout_plan_tss(self, tss_calculator):
        """Test TSS estimation for mixed metric workout plan"""
        segments = [
            WorkoutPlanSegment(duration_minutes=10, intensity_metric='power', target_value=200),
            WorkoutPlanSegment(duration_minutes=15, intensity_metric='heart_rate', target_value=160),
            WorkoutPlanSegment(duration_minutes=20, intensity_metric='pace', target_value=4.2)
        ]
        workout_plan = WorkoutPlan(segments=segments, name="Mixed Workout")

        result = tss_calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            ftp=250.0,
            threshold_hr=170,
            max_hr=190,
            threshold_pace=4.0
        )

        # Should prioritize power as primary method
        assert result['primary_method'] == 'power'
        assert result['total_duration_minutes'] == 45.0
        assert result['estimated_tss'] > 0
        assert len(result['segments']) == 3

        # Verify mixed segments have different metrics
        power_segments = [s for s in result['segments'] if s['intensity_metric'] == 'power']
        hr_segments = [s for s in result['segments'] if s['intensity_metric'] == 'heart_rate']
        pace_segments = [s for s in result['segments'] if s['intensity_metric'] == 'pace']

        assert len(power_segments) == 1
        assert len(hr_segments) == 1
        assert len(pace_segments) == 1

    def test_estimate_workout_plan_tss_with_threshold_estimation(self, tss_calculator):
        """Test workout plan TSS estimation using threshold estimation"""
        segments = [
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=250)
        ]
        workout_plan = WorkoutPlan(segments=segments)

        # Don't provide explicit thresholds - should use estimation from MetricThresholds
        result = tss_calculator.estimate_workout_plan_tss(workout_plan=workout_plan)

        assert result['estimated_tss'] > 0
        # Should use estimated FTP from the thresholds in the calculator
        assert result['thresholds_used']['ftp'] == 250.0  # Estimated from thresholds

    def test_estimate_workout_plan_tss_insufficient_data(self, tss_calculator):
        """Test workout plan TSS estimation error handling"""
        # Empty workout plan
        with pytest.raises(InsufficientDataError, match="Workout plan must contain at least one segment"):
            empty_plan = WorkoutPlan(segments=[WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=250)])
            empty_plan.segments = []  # Bypass Pydantic validation for test
            tss_calculator.estimate_workout_plan_tss(workout_plan=empty_plan)

    def test_estimate_workout_plan_tss_missing_thresholds(self, mock_storage):
        """Test workout plan TSS estimation with missing thresholds"""
        # Calculator without thresholds
        calculator = TSSCalculator(mock_storage, MetricThresholds())

        segments = [
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=250)
        ]
        workout_plan = WorkoutPlan(segments=segments)

        # Should still work using default estimations
        result = calculator.estimate_workout_plan_tss(workout_plan=workout_plan)
        assert result['estimated_tss'] > 0

    def test_workout_plan_segment_tss_calculation_methods(self, tss_calculator):
        """Test individual segment TSS calculation methods"""
        # Test power segment calculation
        power_segments = [WorkoutPlanSegment(duration_minutes=20, intensity_metric='power', target_value=300)]
        power_result = tss_calculator._estimate_power_segments_tss(power_segments, ftp=250.0)

        assert power_result['total_tss'] > 0
        assert len(power_result['segments']) == 1
        assert power_result['segments'][0]['intensity_factor'] > 1.0  # Above threshold

        # Test HR segment calculation
        hr_segments = [WorkoutPlanSegment(duration_minutes=30, intensity_metric='heart_rate', target_value=180)]
        hr_result = tss_calculator._estimate_hr_segments_tss(hr_segments, threshold_hr=170, max_hr=190)

        assert hr_result['total_tss'] > 0
        assert len(hr_result['segments']) == 1
        assert hr_result['segments'][0]['intensity_factor'] > 1.0  # Above threshold

        # Test pace segment calculation
        pace_segments = [WorkoutPlanSegment(duration_minutes=25, intensity_metric='pace', target_value=3.8)]
        pace_result = tss_calculator._estimate_pace_segments_tss(pace_segments, threshold_pace=4.0)

        assert pace_result['total_tss'] > 0
        assert len(pace_result['segments']) == 1
        assert pace_result['segments'][0]['intensity_factor'] > 1.0  # Faster than threshold

    def test_determine_primary_method(self, tss_calculator):
        """Test primary method determination logic"""
        power_segments = [WorkoutPlanSegment(duration_minutes=20, intensity_metric='power', target_value=250)]
        hr_segments = [WorkoutPlanSegment(duration_minutes=20, intensity_metric='heart_rate', target_value=160)]
        pace_segments = [WorkoutPlanSegment(duration_minutes=20, intensity_metric='pace', target_value=4.0)]

        # Power has highest priority
        assert tss_calculator._determine_primary_method(power_segments, hr_segments, pace_segments) == 'power'

        # HR has second priority
        assert tss_calculator._determine_primary_method([], hr_segments, pace_segments) == 'heart_rate'

        # Pace has lowest priority
        assert tss_calculator._determine_primary_method([], [], pace_segments) == 'pace'

        # No segments
        assert tss_calculator._determine_primary_method([], [], []) == 'unknown'


class TestWorkoutPlanIntegration:
    """Test workout plan integration with existing TSS functionality"""

    def test_workout_plan_vs_actual_data_comparison(self, tss_calculator):
        """Test comparing workout plan estimates with actual workout data"""
        # Create a simple workout plan
        segments = [
            WorkoutPlanSegment(duration_minutes=30, intensity_metric='power', target_value=250)
        ]
        workout_plan = WorkoutPlan(segments=segments)

        # Estimate TSS
        estimated_result = tss_calculator.estimate_workout_plan_tss(
            workout_plan=workout_plan,
            ftp=250.0
        )

        # Create simulated actual data matching the plan
        actual_records = [
            {'power': 250, 'timestamp': datetime.now() + timedelta(seconds=i)}
            for i in range(1800)  # 30 minutes
        ]

        # Calculate actual TSS
        actual_result = tss_calculator.calculate_power_tss(
            raw_data=actual_records,
            ftp=250.0
        )

        # Results should be very close (within 5%) since we're simulating perfect execution
        tss_difference = abs(estimated_result['estimated_tss'] - actual_result['tss'])
        assert tss_difference / actual_result['tss'] < 0.05, "Estimated and actual TSS should be very close"

    def test_workout_plan_with_user_thresholds_integration(self, tss_calculator):
        """Test workout plan estimation with user threshold integration"""
        segments = [
            WorkoutPlanSegment(duration_minutes=20, intensity_metric='power', target_value=275),
            WorkoutPlanSegment(duration_minutes=15, intensity_metric='heart_rate', target_value=175)
        ]
        workout_plan = WorkoutPlan(segments=segments, name="Mixed Training")

        # Mock user thresholds similar to composite TSS
        with patch.object(tss_calculator, '_get_user_thresholds') as mock_get_thresholds:
            mock_get_thresholds.return_value = {
                'ftp': 275.0,
                'threshold_hr': 175,
                'max_hr': 195
            }

            result = tss_calculator.estimate_workout_plan_tss(workout_plan=workout_plan, user_id="test_user")

            assert result['thresholds_used']['ftp'] == 275.0
            assert result['thresholds_used']['threshold_hr'] == 175
            assert result['thresholds_used']['source'] == 'user_indicators'
            assert result['estimated_tss'] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])