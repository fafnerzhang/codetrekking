#!/usr/bin/env python3
"""
Analytics interface definitions and data structures.

This module defines the common interfaces and data structures used across
the analytics package for fitness data analysis.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
import uuid


class AnalyticsType(Enum):
    """Types of analytics that can be performed"""
    POWER_ANALYSIS = "power_analysis"
    HEART_RATE_ANALYSIS = "heart_rate_analysis"
    HEART_RATE_ZONES = "heart_rate_zones"
    PACE_ANALYSIS = "pace_analysis"
    PACE_ZONES = "pace_zones"
    TRAINING_LOAD = "training_load"
    RECOVERY_ANALYSIS = "recovery_analysis"
    PERFORMANCE_TRENDS = "performance_trends"
    COMPARISON = "comparison"


class AggregationLevel(Enum):
    """Levels of data aggregation"""
    RAW = "raw"
    SECOND = "second"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


@dataclass
class TimeRange:
    """Time range specification for analytics queries"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    days: Optional[int] = None
    weeks: Optional[int] = None
    months: Optional[int] = None
    
    def to_dates(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Convert time range specification to start and end dates"""
        if self.start_date and self.end_date:
            return self.start_date, self.end_date
        
        now = datetime.now()
        
        if self.days:
            start = now - timedelta(days=self.days)
            return start, now
        elif self.weeks:
            start = now - timedelta(weeks=self.weeks)
            return start, now
        elif self.months:
            start = now - timedelta(days=self.months * 30)
            return start, now
        
        return self.start_date, self.end_date


@dataclass
class MetricThresholds:
    """Training zone thresholds and limits for different metrics"""
    power_zones: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    heart_rate_zones: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    pace_zones: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    speed_zones: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    
    # Threshold values
    functional_threshold_power: Optional[float] = None
    lactate_threshold_heart_rate: Optional[int] = None
    critical_pace: Optional[float] = None
    vo2_max: Optional[float] = None
    resting_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None


@dataclass
class AnalyticsFilter:
    """Filter criteria for analytics queries"""
    user_id: str
    time_range: TimeRange
    sport_types: List[str] = field(default_factory=list)
    activity_ids: List[str] = field(default_factory=list)
    equipment_ids: List[str] = field(default_factory=list)
    min_duration: Optional[int] = None  # Minimum duration in seconds
    max_duration: Optional[int] = None  # Maximum duration in seconds
    min_distance: Optional[float] = None  # Minimum distance in meters
    max_distance: Optional[float] = None  # Maximum distance in meters
    tags: List[str] = field(default_factory=list)
    
    # Advanced filters
    power_range: Optional[Tuple[float, float]] = None
    heart_rate_range: Optional[Tuple[int, int]] = None
    pace_range: Optional[Tuple[float, float]] = None


@dataclass
class AnalyticsResult:
    """Result container for analytics operations"""
    analytics_type: AnalyticsType
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary format"""
        return {
            'result_id': self.result_id,
            'analytics_type': self.analytics_type.value,
            'data': self.data,
            'metadata': self.metadata,
            'generated_at': self.generated_at.isoformat()
        }


# Exception classes
class AnalyticsError(Exception):
    """Base exception for analytics operations"""
    pass


class InsufficientDataError(AnalyticsError):
    """Raised when there is insufficient data for analysis"""
    pass


class InvalidParameterError(AnalyticsError):
    """Raised when invalid parameters are provided"""
    pass


class CalculationError(AnalyticsError):
    """Raised when calculation fails"""
    pass


# Abstract analyzer interfaces
class FitnessAnalyzer(ABC):
    """Abstract base class for fitness data analyzers"""
    
    @abstractmethod
    def analyze(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Perform fitness analysis based on filter criteria"""
        pass


class PowerAnalyzer(ABC):
    """Abstract base class for power data analysis"""
    
    @abstractmethod
    def calculate_normalized_power(self, power_data: List[float]) -> float:
        """Calculate normalized power from power data"""
        pass
    
    @abstractmethod
    def calculate_intensity_factor(self, power_data: List[float], ftp: float) -> float:
        """Calculate intensity factor"""
        pass
    
    @abstractmethod
    def analyze_power_curve(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze power curve over time"""
        pass


class RunningDynamicsAnalyzer(ABC):
    """Abstract base class for running dynamics analysis"""
    
    @abstractmethod
    def analyze_cadence(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze running cadence patterns"""
        pass
    
    @abstractmethod
    def analyze_stride_metrics(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze stride length and frequency"""
        pass


class TrajectoryAnalyzer(ABC):
    """Abstract base class for GPS trajectory analysis"""
    
    @abstractmethod
    def analyze_route_efficiency(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze route efficiency and smoothness"""
        pass
    
    @abstractmethod
    def detect_segments(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Detect and analyze route segments"""
        pass


class RecoveryAnalyzer(ABC):
    """Abstract base class for recovery analysis"""
    
    @abstractmethod
    def analyze_heart_rate_variability(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze heart rate variability for recovery insights"""
        pass
    
    @abstractmethod
    def calculate_recovery_metrics(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Calculate recovery metrics"""
        pass


class HeartRateZoneAnalyzer(ABC):
    """Abstract base class for heart rate zone analysis"""
    
    @abstractmethod
    def calculate_heart_rate_zones(self, max_heart_rate: Optional[int] = None, 
                                 age: Optional[int] = None, method: str = "bcf_abcc_wcpp_revised") -> AnalyticsResult:
        """Calculate heart rate zones using specified method"""
        pass
    
    @abstractmethod
    def analyze_time_in_zones(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze time spent in different heart rate zones"""
        pass
    
    @abstractmethod
    def compare_zone_methods(self, max_heart_rate: Optional[int] = None, 
                           age: Optional[int] = None) -> AnalyticsResult:
        """Compare different heart rate zone calculation methods"""
        pass


class ComparisonAnalyzer(ABC):
    """Abstract base class for comparative analysis"""
    
    @abstractmethod
    def compare_activities(self, activity_ids: List[str]) -> AnalyticsResult:
        """Compare multiple activities"""
        pass
    
    @abstractmethod
    def compare_time_periods(self, period1: TimeRange, period2: TimeRange, user_id: str) -> AnalyticsResult:
        """Compare performance across time periods"""
        pass


class CompositeAnalyzer(ABC):
    """Abstract base class for composite analysis combining multiple metrics"""
    
    @abstractmethod
    def generate_fitness_summary(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Generate comprehensive fitness summary"""
        pass
    
    @abstractmethod
    def analyze_training_distribution(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Analyze training intensity distribution"""
        pass