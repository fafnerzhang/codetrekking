#!/usr/bin/env python3
"""
Training Stress Score (TSS) Algorithm Demo
==========================================

This demo shows how to use the TSS implementation for calculating training stress
based on power, heart rate, or pace data.

TSS provides a standardized way to quantify training load that takes into account
both the intensity and duration of a workout.
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, Any

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from peakflow.analytics.tss import TSSCalculator, TSSAnalyzer
from peakflow.analytics.interface import (
    AnalyticsFilter, TimeRange, MetricThresholds, AnalyticsType
)
from peakflow.storage.interface import StorageInterface


# Mock storage for demonstration
class MockStorage(StorageInterface):
    """Mock storage implementation for demonstration purposes"""
    
    def __init__(self):
        # Sample data for demonstration
        self.sample_records = {
            "activity_001": [
                {"power": 250, "heart_rate": 150, "speed": 8.5, "timestamp": datetime.now()},
                {"power": 260, "heart_rate": 155, "speed": 8.7, "timestamp": datetime.now()},
                {"power": 240, "heart_rate": 148, "speed": 8.3, "timestamp": datetime.now()},
                # ... would contain hundreds/thousands of records for a real activity
            ] * 1800,  # Simulate 30 minutes of data (1800 seconds)
            
            "activity_002": [
                {"power": 180, "heart_rate": 135, "speed": 6.2, "timestamp": datetime.now()},
                {"power": 190, "heart_rate": 140, "speed": 6.5, "timestamp": datetime.now()},
                {"power": 175, "heart_rate": 132, "speed": 6.0, "timestamp": datetime.now()},
            ] * 3600,  # Simulate 60 minutes of data
            
            "activity_003": [
                {"heart_rate": 160, "speed": 4.2, "timestamp": datetime.now()},  # Running at ~4:00/km pace
                {"heart_rate": 165, "speed": 4.0, "timestamp": datetime.now()},  # Running at ~4:10/km pace  
                {"heart_rate": 158, "speed": 4.5, "timestamp": datetime.now()},  # Running at ~3:42/km pace
            ] * 2700,  # Simulate 45 minutes of running data
        }
        
        self.sample_sessions = [
            {
                "activity_id": "activity_001",
                "user_id": "user_123",
                "sport": "cycling",
                "timestamp": datetime.now(),
                "total_timer_time": 1800,
                "total_distance": 15000,
                "enhanced_avg_speed": 8.5,
                "avg_heart_rate": 152
            },
            {
                "activity_id": "activity_002", 
                "user_id": "user_123",
                "sport": "cycling",
                "timestamp": datetime.now() - timedelta(days=1),
                "total_timer_time": 3600,
                "total_distance": 22000,
                "enhanced_avg_speed": 6.3,
                "avg_heart_rate": 137
            },
            {
                "activity_id": "activity_003",
                "user_id": "user_123", 
                "sport": "running",
                "timestamp": datetime.now() - timedelta(days=2),
                "total_timer_time": 2700,
                "total_distance": 10000,
                "enhanced_avg_speed": 4.2,
                "avg_heart_rate": 161
            }
        ]
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Mock initialize implementation"""
        return True
    
    def create_indices(self, force_recreate: bool = False) -> bool:
        """Mock create indices implementation"""
        return True
    
    def index_document(self, data_type, doc_id: str, document: Dict[str, Any]) -> bool:
        """Mock index document implementation"""
        return True
    
    def bulk_index(self, data_type, documents):
        """Mock bulk index implementation"""
        from peakflow.storage.interface import IndexingResult
        result = IndexingResult()
        result.add_success(len(documents))
        return result
    
    def search(self, data_type, query_filter):
        """Mock search implementation"""
        from peakflow.storage.interface import DataType
        
        if data_type == DataType.RECORD:
            activity_id = query_filter.filters.get("activity_id")
            if activity_id in self.sample_records:
                return self.sample_records[activity_id]
            return []
        elif data_type == DataType.SESSION:
            user_id = query_filter.filters.get("user_id")
            activity_id = query_filter.filters.get("activity_id")
            
            if activity_id:
                return [s for s in self.sample_sessions if s["activity_id"] == activity_id]
            elif user_id:
                return [s for s in self.sample_sessions if s["user_id"] == user_id]
            
        return []
    
    def aggregate(self, data_type, query_filter, agg_query):
        """Mock aggregate implementation"""
        return {"mock": "aggregation_result"}
    
    def get_by_id(self, data_type, doc_id: str):
        """Mock get by id implementation"""
        return None
    
    def delete_by_id(self, data_type, doc_id: str) -> bool:
        """Mock delete by id implementation"""
        return True
    
    def delete_by_query(self, data_type, query_filter) -> int:
        """Mock delete by query implementation"""
        return 0
    
    def get_stats(self, data_type) -> Dict[str, Any]:
        """Mock get stats implementation"""
        return {"total_documents": 100, "index_size": "1MB"}


def demo_power_tss():
    """Demonstrate power-based TSS calculation"""
    print("=== Power-based TSS Demo ===")
    
    # Initialize storage and TSS calculator
    storage = MockStorage()
    
    # Set up thresholds
    thresholds = MetricThresholds(
        power_zones={
            "zone_1": (0, 140),      # Active recovery
            "zone_2": (140, 200),    # Endurance
            "zone_3": (200, 250),    # Tempo
            "zone_4": (250, 300),    # Lactate threshold
            "zone_5": (300, 400)     # VO2 max
        }
    )
    
    calculator = TSSCalculator(storage, thresholds)
    
    # Calculate TSS for a cycling activity
    ftp = 275  # Functional Threshold Power in watts
    result = calculator.calculate_power_tss("activity_001", ftp=ftp)
    
    print(f"Activity: activity_001")
    print(f"FTP: {ftp}W")
    print(f"TSS: {result['tss']}")
    print(f"Normalized Power: {result['normalized_power']}W")
    print(f"Intensity Factor: {result['intensity_factor']}")
    print(f"Duration: {result['duration_hours']} hours")
    print(f"Average Power: {result['avg_power']}W")
    print()


def demo_hr_tss():
    """Demonstrate heart rate-based TSS calculation"""
    print("=== Heart Rate-based TSS Demo ===")
    
    storage = MockStorage()
    
    thresholds = MetricThresholds(
        heart_rate_zones={
            "zone_1": (100, 130),    # Active recovery
            "zone_2": (130, 150),    # Endurance
            "zone_3": (150, 170),    # Aerobic
            "zone_4": (170, 180),    # Lactate threshold
            "zone_5": (180, 200)     # Neuromuscular
        }
    )
    
    calculator = TSSCalculator(storage, thresholds)
    
    # Calculate hrTSS
    threshold_hr = 175  # Lactate threshold heart rate
    max_hr = 195
    result = calculator.calculate_hr_tss("activity_001", threshold_hr=threshold_hr, max_hr=max_hr)
    
    print(f"Activity: activity_001")
    print(f"Threshold HR: {threshold_hr} bpm")
    print(f"Max HR: {max_hr} bpm")
    print(f"hrTSS: {result['tss']}")
    print(f"Intensity Factor: {result['intensity_factor']}")
    print(f"Average HR: {result['avg_hr']} bpm")
    print(f"Duration: {result['duration_hours']} hours")
    print()


def demo_pace_tss():
    """Demonstrate running pace-based TSS calculation"""
    print("=== Running Pace-based TSS Demo ===")
    
    storage = MockStorage()
    
    thresholds = MetricThresholds(
        pace_zones={
            "zone_1": (5.5, 6.5),      # Easy pace (5:30-6:30 min/km)
            "zone_2": (4.8, 5.5),      # Aerobic pace (4:48-5:30 min/km) 
            "zone_3": (4.2, 4.8),      # Tempo pace (4:12-4:48 min/km)
            "zone_4": (3.8, 4.2),      # Lactate threshold (3:48-4:12 min/km)
            "zone_5": (3.0, 3.8)       # VO2 max pace (3:00-3:48 min/km)
        }
    )
    
    calculator = TSSCalculator(storage, thresholds)
    
    # Calculate running pace TSS
    threshold_pace = 4.0  # 4:00 min/km threshold pace (240 seconds per km)
    result = calculator.calculate_running_pace_tss("activity_003", threshold_pace=threshold_pace)
    
    print(f"Activity: activity_003 (Running)")
    print(f"Threshold Pace: {result['threshold_pace_formatted']} min/km")
    print(f"Running Pace TSS: {result['tss']}")
    print(f"Normalized Graded Pace: {result['normalized_pace_formatted']} min/km")
    print(f"Intensity Factor: {result['intensity_factor']}")
    print(f"  (IF = threshold_pace / normalized_pace)")
    print(f"  (IF = {threshold_pace:.2f} / {result['normalized_pace']:.2f} = {result['intensity_factor']:.3f})")
    print(f"Average Pace: {result['avg_pace_formatted']} min/km")
    print(f"Best Pace: {result['best_pace_formatted']} min/km")
    print(f"Duration: {result['duration_hours']} hours")
    print(f"Formula Used: (seconds × NGP × IF) / (FTP × 3600) × 100")
    
    # Demonstrate pace format conversion
    print(f"\nPace Format Conversions:")
    pace_examples = [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]
    for pace in pace_examples:
        formatted = calculator.format_pace(pace)
        print(f"  {pace:.1f} min/km = {formatted} min/km")
    print()


def demo_composite_tss():
    """Demonstrate automatic TSS calculation using best available method"""
    print("=== Composite TSS Demo ===")
    
    storage = MockStorage()
    
    # Provide comprehensive thresholds for all methods
    thresholds = MetricThresholds(
        power_zones={
            "zone_1": (0, 140),      # Active recovery
            "zone_2": (140, 200),    # Endurance
            "zone_3": (200, 250),    # Tempo
            "zone_4": (250, 300),    # Lactate threshold (FTP = 250W)
            "zone_5": (300, 400)     # VO2 max
        },
        heart_rate_zones={
            "zone_1": (100, 130),    # Active recovery
            "zone_2": (130, 150),    # Endurance
            "zone_3": (150, 170),    # Aerobic
            "zone_4": (170, 180),    # Lactate threshold (LTHR = 170 bpm)
            "zone_5": (180, 200)     # Neuromuscular
        },
        pace_zones={
            "zone_1": (5.5, 6.5),      # Easy pace (5:30-6:30 min/km)
            "zone_2": (4.8, 5.5),      # Aerobic pace (4:48-5:30 min/km)
            "zone_3": (4.2, 4.8),      # Tempo pace (4:12-4:48 min/km)
            "zone_4": (3.8, 4.2),      # Lactate threshold (3:48-4:12 min/km)
            "zone_5": (3.0, 3.8)       # VO2 max pace (3:00-3:48 min/km)
        }
    )
    
    calculator = TSSCalculator(storage, thresholds)
    
    # Calculate TSS using the best available method
    result = calculator.calculate_composite_tss("activity_001")
    
    print(f"Activity: activity_001")
    print(f"Primary Method: {result['primary_method']}")
    print(f"TSS: {result['tss']}")
    
    # Show all calculated methods
    if 'power_tss' in result:
        print(f"Power TSS: {result['power_tss']['tss']} (FTP: {result['power_tss']['ftp']}W)")
    if 'hr_tss' in result:
        print(f"HR TSS: {result['hr_tss']['tss']} (LTHR: {result['hr_tss']['threshold_hr']} bpm)")
    if 'pace_tss' in result:
        print(f"Running Pace TSS: {result['pace_tss']['tss']} (Threshold: {result['pace_tss']['threshold_pace_formatted']} min/km)")
    
    print()


def demo_weekly_tss():
    """Demonstrate weekly TSS calculation"""
    print("=== Weekly TSS Demo ===")
    
    storage = MockStorage()
    
    # Provide comprehensive thresholds so TSS can be calculated
    thresholds = MetricThresholds(
        power_zones={
            "zone_4": (250, 300),    # FTP = 250W
        },
        heart_rate_zones={
            "zone_4": (170, 180),    # LTHR = 170 bpm
        }
    )
    
    calculator = TSSCalculator(storage, thresholds)
    
    # Calculate weekly TSS for a user
    week_start = datetime.now() - timedelta(days=7)
    result = calculator.calculate_weekly_tss("user_123", week_start)
    
    print(f"User: user_123")
    print(f"Week starting: {week_start.strftime('%Y-%m-%d')}")
    print(f"Total Weekly TSS: {result['weekly_tss']}")
    print(f"Activity Count: {result['activity_count']}")
    print(f"Average Daily TSS: {result['avg_daily_tss']}")
    print(f"Daily Breakdown: {result['daily_tss']}")
    if result['activity_details']:
        print("Activity Details:")
        for activity in result['activity_details']:
            print(f"  - {activity['activity_id']}: {activity['tss']} TSS ({activity['method']})")
    print()


def demo_tss_analyzer():
    """Demonstrate the high-level TSS analyzer"""
    print("=== TSS Analyzer Demo ===")
    
    storage = MockStorage()
    
    # Provide comprehensive thresholds
    thresholds = MetricThresholds(
        power_zones={
            "zone_4": (250, 300),    # FTP = 250W
        },
        heart_rate_zones={
            "zone_4": (170, 180),    # LTHR = 170 bpm
        }
    )
    
    analyzer = TSSAnalyzer(storage, thresholds)
    
    # Create filter criteria
    time_range = TimeRange(days=30)
    filter_criteria = AnalyticsFilter(
        user_id="user_123",
        time_range=time_range
    )
    
    # Analyze training stress
    result = analyzer.analyze_training_stress(filter_criteria)
    
    print(f"Analysis Type: {result.analytics_type}")
    print(f"Total TSS: {result.data['total_tss']}")
    print(f"Average Weekly TSS: {result.data['avg_weekly_tss']}")
    print(f"Training Load Category: {result.data['training_load_category']}")
    print(f"Activity Count: {result.data['activity_count']}")
    print(f"Sport Breakdown: {result.data['sport_breakdown']}")
    if result.data['activity_tss']:
        print("Recent Activities:")
        for activity in result.data['activity_tss'][:3]:  # Show first 3
            print(f"  - {activity['activity_id']}: {activity['tss']} TSS ({activity['method']})")
    print()


def demo_running_tss_comparison():
    """Demonstrate comparison of running TSS calculation methods"""
    print("=== Running TSS Formula Comparison ===")
    
    storage = MockStorage()
    calculator = TSSCalculator(storage)
    
    # Test with the running activity
    activity_id = "activity_003"
    threshold_pace = 3.50  # 4:00/km threshold pace
    
    try:
        result = calculator.calculate_running_pace_tss(activity_id, threshold_pace=threshold_pace)
        
        print(f"Running Activity Analysis (activity_003):")
        print(f"Threshold Pace: {result['threshold_pace_formatted']} min/km")
        print(f"Duration: {result['duration_seconds']} seconds ({result['duration_hours']:.2f} hours)")
        print()
        
        print("New Formula Components:")
        print(f"- Normalized Graded Pace (NGP): {result['normalized_pace_formatted']} min/km")
        print(f"- Intensity Factor (IF): {result['intensity_factor']:.3f}")
        print(f"- Duration in seconds: {result['duration_seconds']}")
        print(f"- Threshold Pace (FTP equiv): {result['threshold_pace']:.2f} min/km")
        print()
        
        print("Formula Calculation:")
        duration_sec = result['duration_seconds']
        ngp = result['normalized_pace']
        if_val = result['intensity_factor']
        ftp = result['threshold_pace']
        
        calculated_tss = (duration_sec * ngp * if_val) / (ftp * 3600) * 100
        print(f"TSS = ({duration_sec} × {ngp:.2f} × {if_val:.3f}) / ({ftp:.2f} × 3600) × 100")
        print(f"TSS = {calculated_tss:.1f}")
        print(f"Actual Result: {result['tss']}")
        print()
        
    except Exception as e:
        print(f"Error calculating running TSS: {str(e)}")
        print()


def demo_pace_intensity_factor():
    """Demonstrate how intensity factor works with running pace"""
    print("=== Running Pace Intensity Factor Demo ===")
    
    storage = MockStorage()
    calculator = TSSCalculator(storage)
    
    threshold_pace = 3.50  # 4:00/km threshold pace
    
    print(f"Threshold Pace: {calculator.format_pace(threshold_pace)} min/km")
    print("\nIntensity Factor Examples:")
    print("(Remember: Faster pace = lower time = higher intensity)")
    print()
    
    # Test different pace scenarios
    pace_scenarios = [
        (3.0, "Very fast (3:00/km) - VO2 max effort"),
        (3.5, "Fast (3:30/km) - 5K race pace"),
        (4.0, "Threshold (4:00/km) - threshold pace"),
        (4.5, "Moderate (4:30/km) - tempo pace"),
        (5.0, "Easy (5:00/km) - easy aerobic"),
        (5.5, "Recovery (5:30/km) - recovery pace")
    ]
    
    for pace, description in pace_scenarios:
        intensity_factor = threshold_pace / pace
        pace_formatted = calculator.format_pace(pace)
        
        print(f"{pace_formatted} min/km - {description}")
        print(f"  IF = {threshold_pace:.1f} / {pace:.1f} = {intensity_factor:.3f}")
        
        if intensity_factor > 1.2:
            effort_level = "Very Hard"
        elif intensity_factor > 1.0:
            effort_level = "Hard"
        elif intensity_factor > 0.9:
            effort_level = "Moderate"
        else:
            effort_level = "Easy"
        
        print(f"  Effort Level: {effort_level}")
        print()
    
    print("Key Points:")
    print("- IF = 1.0 means running exactly at threshold pace")
    print("- IF > 1.0 means running faster than threshold (harder)")
    print("- IF < 1.0 means running slower than threshold (easier)")
    print("- The new TSS formula accounts for both intensity and duration")
    print()


def demo_tss_interpretation():
    """Demonstrate TSS interpretation and guidelines"""
    print("=== TSS Interpretation Guidelines ===")
    
    print("Power-based TSS:")
    print("- TSS = (Duration × NP × IF) / (FTP × 3600) × 100")
    print("- NP = Normalized Power (30-second rolling average)")
    print("- IF = Intensity Factor (NP / FTP)")
    print()
    
    print("Heart Rate-based TSS:")
    print("- hrTSS = Duration × IF² × 100")
    print("- IF based on TRIMP method with heart rate zones")
    print()
    
    print("Running Pace-based TSS:")
    print("- Running TSS = (seconds × Normalized Graded Pace × IF) / (FTP × 3600) × 100")
    print("- NGP = Normalized Graded Pace (similar to Normalized Power for running)")
    print("- IF = Intensity Factor (threshold_pace / NGP)")
    print("- FTP equivalent = threshold_pace for running")
    print("- Note: For running, faster pace = lower time, so IF > 1.0 means faster than threshold")
    print()
    
    print("TSS Guidelines:")
    print("- < 150 TSS/week: Low training load")
    print("- 150-300 TSS/week: Moderate training load")
    print("- 300-450 TSS/week: High training load")
    print("- > 450 TSS/week: Very high training load")
    print()
    
    print("Single Session TSS:")
    print("- < 50: Easy recovery session")
    print("- 50-100: Moderate endurance session")
    print("- 100-150: Hard training session")
    print("- > 150: Very hard/race effort")
    print()


def main():
    """Run all TSS demos"""
    print("Training Stress Score (TSS) Algorithm Demonstration")
    print("=" * 60)
    print()
    
    try:
        demo_power_tss()
        demo_hr_tss()
        demo_pace_tss()
        demo_running_tss_comparison()
        demo_composite_tss()
        demo_weekly_tss()
        demo_tss_analyzer()
        demo_tss_interpretation()
        demo_pace_intensity_factor()
        
        print("Demo completed successfully!")
        print()
        print("Integration Notes:")
        print("- TSS calculations are now integrated into AdvancedStatistics class")
        print("- Use get_activity_tss() for single activity TSS calculation")
        print("- Use get_tss_analysis() for comprehensive TSS analysis")
        print("- Use get_weekly_tss_summary() for weekly TSS summaries")
        print("- Use get_tss_trends() for long-term TSS trend analysis")
        
    except Exception as e:
        print(f"Error running demo: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
