#!/usr/bin/env python3
"""
Tests for Power Zone Analytics Module

This module contains comprehensive tests for power zone calculations
including all supported methodologies.
"""

import pytest
from datetime import datetime
from typing import List, Dict, Any

from peakflow.analytics.power_zones import (
    PowerZoneMethod, PowerZone, PowerZoneResult,
    PowerZoneCalculator, PowerZoneAnalyzer,
    StevePalladinoCalculator, StrydRunningCalculator, 
    CriticalPowerCalculator
)
from peakflow.analytics.interface import AnalyticsType, InvalidParameterError


class TestPowerZone:
    """Test PowerZone dataclass"""
    
    def test_power_zone_creation(self):
        """Test creating a PowerZone instance"""
        zone = PowerZone(
            zone_number=1,
            zone_name="Recovery",
            power_range=(100.0, 150.0),
            percentage_range=(50, 75),
            description="Easy recovery zone",
            purpose="Recovery and base building"
        )
        
        assert zone.zone_number == 1
        assert zone.zone_name == "Recovery"
        assert zone.power_range == (100.0, 150.0)
        assert zone.percentage_range == (50, 75)
        assert zone.description == "Easy recovery zone"
        assert zone.purpose == "Recovery and base building"


class TestPowerZoneResult:
    """Test PowerZoneResult dataclass"""
    
    def create_sample_zones(self) -> List[PowerZone]:
        """Create sample power zones for testing"""
        return [
            PowerZone(1, "Zone 1", (100, 150), (50, 75), "Easy", "Recovery"),
            PowerZone(2, "Zone 2", (150, 200), (75, 100), "Moderate", "Base")
        ]
    
    def test_power_zone_result_creation(self):
        """Test creating a PowerZoneResult instance"""
        zones = self.create_sample_zones()
        
        result = PowerZoneResult(
            method=PowerZoneMethod.STEVE_PALLADINO,
            zones=zones,
            threshold_power=200.0,
            normalized_power=2.5,
            analytics_type=AnalyticsType.POWER_ANALYSIS,
            timestamp=datetime.utcnow()
        )
        
        assert result.method == PowerZoneMethod.STEVE_PALLADINO
        assert len(result.zones) == 2
        assert result.threshold_power == 200.0
        assert result.normalized_power == 2.5
        assert result.analytics_type == AnalyticsType.POWER_ANALYSIS
    
    def test_power_zone_result_empty_zones_error(self):
        """Test that empty zones list raises error"""
        with pytest.raises(InvalidParameterError):
            PowerZoneResult(
                method=PowerZoneMethod.STEVE_PALLADINO,
                zones=[],
                threshold_power=200.0,
                normalized_power=2.5,
                analytics_type=AnalyticsType.POWER_ANALYSIS,
                timestamp=datetime.utcnow()
            )


class TestStevePalladinoCalculator:
    """Test Steve Palladino power zone calculator"""
    
    def setup_method(self):
        """Setup test method"""
        self.calculator = StevePalladinoCalculator()
    
    def test_calculate_zones_basic(self):
        """Test basic zone calculation"""
        zones = self.calculator.calculate_zones(200.0)
        
        assert len(zones) == 7
        assert zones[0].zone_name == "Easy Running"
        assert zones[0].power_range == (100.0, 160.0)  # 50-80% of 200W
        assert zones[0].percentage_range == (50, 80)
        
        assert zones[6].zone_name == "Sprint / Maximal Power"
        assert zones[6].power_range == (302.0, 600.0)  # 151-300% of 200W
        assert zones[6].percentage_range == (151, 300)
    
    def test_calculate_zones_with_body_weight(self):
        """Test zone calculation with body weight"""
        zones = self.calculator.calculate_zones(200.0, body_weight=70.0)
        
        # Zones should be the same regardless of body weight
        # (body weight is for normalization in results, not zone calculation)
        assert len(zones) == 7
        assert zones[0].power_range == (100.0, 160.0)
    
    def test_calculate_zones_invalid_power(self):
        """Test zone calculation with invalid threshold power"""
        with pytest.raises(InvalidParameterError):
            self.calculator.calculate_zones(0.0)
        
        with pytest.raises(InvalidParameterError):
            self.calculator.calculate_zones(-100.0)
    
    def test_get_method_name(self):
        """Test getting method name"""
        assert self.calculator.get_method_name() == PowerZoneMethod.STEVE_PALLADINO
    
    def test_get_method_description(self):
        """Test getting method description"""
        description = self.calculator.get_method_description()
        assert "Steve Palladino" in description
        assert "7-zone" in description
        assert "running" in description.lower()
    
    def test_zone_details(self):
        """Test that all zones have required details"""
        zones = self.calculator.calculate_zones(200.0)
        
        for zone in zones:
            assert zone.zone_number > 0
            assert zone.zone_name
            assert zone.power_range[0] >= 0
            assert zone.power_range[1] > zone.power_range[0]
            assert zone.percentage_range[0] >= 0
            assert zone.percentage_range[1] > zone.percentage_range[0]
            assert zone.description
            assert zone.purpose
            assert zone.physiological_adaptations
            assert zone.duration_guidance
            assert zone.effort_level


class TestStrydRunningCalculator:
    """Test Stryd running power zone calculator"""
    
    def setup_method(self):
        """Setup test method"""
        self.calculator = StrydRunningCalculator()
    
    def test_calculate_zones_basic(self):
        """Test basic zone calculation"""
        zones = self.calculator.calculate_zones(250.0)
        
        assert len(zones) == 5  # Stryd has 5 zones
        assert zones[0].zone_name == "Easy"
        assert zones[0].power_range == (162.5, 200.0)  # 65-80% of 250W
        
        assert zones[4].zone_name == "Repetition"
        assert zones[4].power_range == (287.5, 325.0)  # 115-130% of 250W
    
    def test_get_method_name(self):
        """Test getting method name"""
        assert self.calculator.get_method_name() == PowerZoneMethod.STRYD_RUNNING
    
    def test_get_method_description(self):
        """Test getting method description"""
        description = self.calculator.get_method_description()
        assert "Stryd" in description
        assert "running" in description.lower()


class TestCriticalPowerCalculator:
    """Test Critical Power model zone calculator"""
    
    def setup_method(self):
        """Setup test method"""
        self.calculator = CriticalPowerCalculator()
    
    def test_calculate_zones_basic(self):
        """Test basic zone calculation"""
        zones = self.calculator.calculate_zones(280.0)
        
        assert len(zones) == 7
        assert zones[0].zone_name == "Recovery"
        assert zones[4].zone_name == "Critical Power"
        assert zones[4].power_range == (280.0, 294.0)  # 100-105% of CP
    
    def test_calculate_zones_with_w_prime(self):
        """Test zone calculation with W' parameter"""
        calculator = CriticalPowerCalculator(w_prime=25.0)
        zones = calculator.calculate_zones(280.0)
        
        assert len(zones) == 7
        assert calculator.w_prime == 25.0
    
    def test_get_method_name(self):
        """Test getting method name"""
        assert self.calculator.get_method_name() == PowerZoneMethod.CRITICAL_POWER


class TestPowerZoneAnalyzer:
    """Test PowerZoneAnalyzer"""
    
    def setup_method(self):
        """Setup test method"""
        self.analyzer = PowerZoneAnalyzer()
    
    def test_calculate_power_zones_default(self):
        """Test calculating power zones with default method"""
        result = self.analyzer.calculate_power_zones(200.0)
        
        assert isinstance(result, PowerZoneResult)
        assert result.method == PowerZoneMethod.STEVE_PALLADINO
        assert len(result.zones) == 7
        assert result.threshold_power == 200.0
        assert result.analytics_type == AnalyticsType.POWER_ANALYSIS
    
    def test_calculate_power_zones_all_methods(self):
        """Test calculating zones with all supported methods"""
        methods = [
            PowerZoneMethod.STEVE_PALLADINO,
            PowerZoneMethod.STRYD_RUNNING,
            PowerZoneMethod.CRITICAL_POWER
        ]
        
        expected_zone_counts = {
            PowerZoneMethod.STEVE_PALLADINO: 7,
            PowerZoneMethod.STRYD_RUNNING: 5,
            PowerZoneMethod.CRITICAL_POWER: 7
        }
        
        for method in methods:
            result = self.analyzer.calculate_power_zones(250.0, method=method)
            assert result.method == method
            assert len(result.zones) == expected_zone_counts[method]
            assert result.threshold_power == 250.0
    
    def test_calculate_power_zones_with_body_weight(self):
        """Test calculating zones with body weight for normalization"""
        result = self.analyzer.calculate_power_zones(200.0, body_weight=70.0)
        
        expected_normalized = 200.0 / 70.0  # W/kg
        assert abs(result.normalized_power - expected_normalized) < 0.01
        assert result.calculation_metadata["body_weight"] == 70.0
        assert result.calculation_metadata["normalized_power_w_per_kg"] == expected_normalized
    
    def test_calculate_power_zones_critical_power_with_w_prime(self):
        """Test calculating Critical Power zones with W' parameter"""
        result = self.analyzer.calculate_power_zones(
            threshold_power=280.0,
            method=PowerZoneMethod.CRITICAL_POWER,
            w_prime=22.0
        )
        
        assert result.method == PowerZoneMethod.CRITICAL_POWER
        assert result.calculation_metadata["w_prime_kj"] == 22.0
    
    def test_calculate_power_zones_invalid_power(self):
        """Test error handling for invalid threshold power"""
        with pytest.raises(InvalidParameterError):
            self.analyzer.calculate_power_zones(0.0)
        
        with pytest.raises(InvalidParameterError):
            self.analyzer.calculate_power_zones(-100.0)
    
    def test_analyze_method(self):
        """Test analyze method with data dictionary"""
        data = {
            "threshold_power": 220.0,
            "method": "stryd_running",
            "body_weight": 65.0
        }
        
        from peakflow.analytics.interface import AnalyticsFilter, TimeRange
        filters = AnalyticsFilter(
            user_id="test_user",
            time_range=TimeRange()
        )
        
        result = self.analyzer.analyze(data, filters)
        
        assert isinstance(result, PowerZoneResult)
        assert result.method == PowerZoneMethod.STRYD_RUNNING
        assert result.threshold_power == 220.0
    
    def test_analyze_method_missing_threshold_power(self):
        """Test analyze method error when threshold power is missing"""
        data = {"method": "steve_palladino"}
        
        from peakflow.analytics.interface import AnalyticsFilter, TimeRange
        filters = AnalyticsFilter(
            user_id="test_user",
            time_range=TimeRange()
        )
        
        with pytest.raises(InvalidParameterError):
            self.analyzer.analyze(data, filters)
    
    def test_get_supported_methods(self):
        """Test getting list of supported methods"""
        methods = self.analyzer.get_supported_methods()
        
        assert PowerZoneMethod.STEVE_PALLADINO in methods
        assert PowerZoneMethod.STRYD_RUNNING in methods
        assert PowerZoneMethod.CRITICAL_POWER in methods
        assert len(methods) == 3
    
    def test_get_method_description(self):
        """Test getting method descriptions"""
        for method in self.analyzer.get_supported_methods():
            description = self.analyzer.get_method_description(method)
            assert isinstance(description, str)
            assert len(description) > 0
    
    def test_get_method_description_invalid(self):
        """Test error for invalid method description request"""
        with pytest.raises(InvalidParameterError):
            self.analyzer.get_method_description("invalid_method")


class TestPowerZoneIntegration:
    """Integration tests for power zone functionality"""
    
    def setup_method(self):
        """Setup test method"""
        self.analyzer = PowerZoneAnalyzer()
    
    def test_realistic_running_power_values(self):
        """Test with realistic running power values for different athlete levels"""
        test_cases = [
            (180, "Recreational runner"),
            (220, "Club-level runner"),
            (260, "Competitive runner"), 
            (300, "Elite runner"),
            (350, "World-class runner")
        ]
        
        for power, description in test_cases:
            result = self.analyzer.calculate_power_zones(power, PowerZoneMethod.STRYD_RUNNING)
            
            # Verify zone progression makes sense
            for i in range(len(result.zones) - 1):
                current_zone = result.zones[i]
                next_zone = result.zones[i + 1]
                
                # Each zone should have higher power than the previous
                assert current_zone.power_range[1] <= next_zone.power_range[0]
    
    def test_power_to_weight_ratios(self):
        """Test power-to-weight ratio calculations"""
        test_cases = [
            (200, 80, 2.5),   # 200W, 80kg = 2.5 W/kg
            (250, 70, 3.57),  # 250W, 70kg ≈ 3.57 W/kg
            (300, 75, 4.0)    # 300W, 75kg = 4.0 W/kg
        ]
        
        for power, weight, expected_ratio in test_cases:
            result = self.analyzer.calculate_power_zones(
                threshold_power=power,
                body_weight=weight
            )
            
            assert abs(result.normalized_power - expected_ratio) < 0.1
            assert result.calculation_metadata["normalized_power_w_per_kg"] == result.normalized_power
    
    def test_metadata_completeness(self):
        """Test that calculation metadata is complete and useful"""
        result = self.analyzer.calculate_power_zones(
            threshold_power=275.0,
            method=PowerZoneMethod.STEVE_PALLADINO,
            body_weight=68.0
        )
        
        metadata = result.calculation_metadata
        
        # Check required metadata fields
        assert "method_description" in metadata
        assert "calculation_timestamp" in metadata
        assert "body_weight" in metadata
        assert "normalized_power_w_per_kg" in metadata
        
        # Verify timestamp format
        timestamp = datetime.fromisoformat(metadata["calculation_timestamp"])
        assert isinstance(timestamp, datetime)
        
        # Verify method description is informative
        assert len(metadata["method_description"]) > 20


if __name__ == "__main__":
    pytest.main([__file__])
