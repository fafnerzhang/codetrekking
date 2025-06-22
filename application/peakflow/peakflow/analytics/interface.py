#!/usr/bin/env python3
"""
Analytics Abstract Interface - Defines standard interfaces for all analytics functionality
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass


class AnalyticsType(Enum):
    """Analytics type enumeration"""
    PERFORMANCE = "performance"
    HEART_RATE = "heart_rate"
    POWER = "power"
    RUNNING_DYNAMICS = "running_dynamics"
    TRAJECTORY = "trajectory"
    TRAINING_LOAD = "training_load"
    RECOVERY = "recovery"
    COMPARISON = "comparison"


class AggregationLevel(Enum):
    """Aggregation level enumeration"""
    ACTIVITY = "activity"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class TimeRange:
    """Time range"""
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    days: Optional[int] = None
    
    def to_dates(self) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Convert to start and end dates"""
        if self.days:
            end_date = self.end or datetime.now()
            start_date = end_date - timedelta(days=self.days)
            return start_date, end_date
        return self.start, self.end


@dataclass
class AnalyticsFilter:
    """Analytics filter"""
    user_id: str
    activity_ids: Optional[List[str]] = None
    time_range: Optional[TimeRange] = None
    sport_types: Optional[List[str]] = None
    intensity_levels: Optional[List[str]] = None
    min_distance: Optional[float] = None
    max_distance: Optional[float] = None
    min_duration: Optional[int] = None
    max_duration: Optional[int] = None


@dataclass
class MetricThresholds:
    """Metric thresholds"""
    heart_rate_zones: Optional[Dict[str, Tuple[int, int]]] = None
    power_zones: Optional[Dict[str, Tuple[int, int]]] = None
    pace_zones: Optional[Dict[str, Tuple[float, float]]] = None
    training_stress_threshold: Optional[float] = None


@dataclass
class AnalyticsResult:
    """Analytics result"""
    analytics_type: AnalyticsType
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    generated_at: datetime
    
    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now()


class FitnessAnalyzer(ABC):
    """Fitness data analyzer abstract base class"""
    
    def __init__(self, storage, thresholds: Optional[MetricThresholds] = None):
        self.storage = storage
        self.thresholds = thresholds or MetricThresholds()
    
    @abstractmethod
    def analyze_performance(self, filter_criteria: AnalyticsFilter, 
                          aggregation_level: AggregationLevel = AggregationLevel.ACTIVITY) -> AnalyticsResult:
        """Performance analysis"""
        pass
    
    @abstractmethod
    def analyze_heart_rate(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Heart rate analysis"""
        pass
    
    @abstractmethod
    def analyze_training_load(self, filter_criteria: AnalyticsFilter, 
                            aggregation_level: AggregationLevel = AggregationLevel.WEEKLY) -> AnalyticsResult:
        """Training load analysis"""
        pass
    
    @abstractmethod
    def analyze_trends(self, filter_criteria: AnalyticsFilter, 
                      metrics: List[str], 
                      aggregation_level: AggregationLevel = AggregationLevel.WEEKLY) -> AnalyticsResult:
        """Trend analysis"""
        pass


class PowerAnalyzer(ABC):
    """Power analyzer abstract base class"""
    
    @abstractmethod
    def analyze_power_distribution(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Power distribution analysis"""
        pass
    
    @abstractmethod
    def calculate_ftp_estimate(self, filter_criteria: AnalyticsFilter) -> Optional[float]:
        """Calculate Functional Threshold Power (FTP) estimate"""
        pass
    
    @abstractmethod
    def analyze_power_zones(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Power zone analysis"""
        pass


class RunningDynamicsAnalyzer(ABC):
    """Running dynamics analyzer abstract base class"""
    
    @abstractmethod
    def analyze_cadence(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Cadence analysis"""
        pass
    
    @abstractmethod
    def analyze_stride_metrics(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Stride metrics analysis"""
        pass
    
    @abstractmethod
    def analyze_vertical_oscillation(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Vertical oscillation analysis"""
        pass
    
    @abstractmethod
    def analyze_ground_contact_time(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Ground contact time analysis"""
        pass


class TrajectoryAnalyzer(ABC):
    """Trajectory analyzer abstract base class"""
    
    @abstractmethod
    def analyze_route_efficiency(self, activity_id: str) -> Dict[str, Any]:
        """Route efficiency analysis"""
        pass
    
    @abstractmethod
    def detect_segments(self, activity_id: str, segment_type: str = "climb") -> List[Dict[str, Any]]:
        """Segment detection (climbs, descents, flats, etc.)"""
        pass
    
    @abstractmethod
    def calculate_elevation_profile(self, activity_id: str) -> Dict[str, Any]:
        """Elevation profile calculation"""
        pass
    
    @abstractmethod
    def get_route_statistics(self, activity_id: str) -> Dict[str, Any]:
        """Route statistics"""
        pass


class RecoveryAnalyzer(ABC):
    """Recovery analyzer abstract base class"""
    
    @abstractmethod
    def calculate_recovery_score(self, filter_criteria: AnalyticsFilter) -> Dict[str, Any]:
        """Calculate recovery score"""
        pass
    
    @abstractmethod
    def analyze_resting_heart_rate_trend(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Resting heart rate trend analysis"""
        pass
    
    @abstractmethod
    def estimate_recovery_time(self, activity_id: str) -> Optional[int]:
        """Estimate recovery time (hours)"""
        pass


class ComparisonAnalyzer(ABC):
    """Comparison analyzer abstract base class"""
    
    @abstractmethod
    def compare_activities(self, activity_ids: List[str], metrics: List[str]) -> AnalyticsResult:
        """Activity comparison"""
        pass
    
    @abstractmethod
    def compare_time_periods(self, user_id: str, period1: TimeRange, 
                           period2: TimeRange, metrics: List[str]) -> AnalyticsResult:
        """Time period comparison"""
        pass
    
    @abstractmethod
    def compare_users(self, user_ids: List[str], filter_criteria: AnalyticsFilter, 
                     metrics: List[str]) -> AnalyticsResult:
        """User comparison (anonymized)"""
        pass


class CompositeAnalyzer(FitnessAnalyzer, PowerAnalyzer, RunningDynamicsAnalyzer, 
                       TrajectoryAnalyzer, RecoveryAnalyzer, ComparisonAnalyzer):
    """Composite analyzer - complete implementation with all analytics features"""
    
    @abstractmethod
    def generate_comprehensive_report(self, filter_criteria: AnalyticsFilter) -> Dict[str, AnalyticsResult]:
        """Generate comprehensive analytics report"""
        pass
    
    @abstractmethod
    def get_personalized_insights(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """Personalized insights"""
        pass
    
    @abstractmethod
    def detect_anomalies(self, filter_criteria: AnalyticsFilter) -> List[Dict[str, Any]]:
        """Anomaly detection"""
        pass


# Exception classes
class AnalyticsError(Exception):
    """Analytics error base class"""
    pass


class InsufficientDataError(AnalyticsError):
    """Insufficient data error"""
    pass


class InvalidParameterError(AnalyticsError):
    """Invalid parameter error"""
    pass


class CalculationError(AnalyticsError):
    """Calculation error"""
    pass
