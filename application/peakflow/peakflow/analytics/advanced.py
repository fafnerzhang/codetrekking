#!/usr/bin/env python3
"""
Statistical Support Classes - Provides advanced statistical analysis functionality
with Training Stress Score (TSS) integration
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from ..storage.interface import (
    StorageInterface, DataType, QueryFilter, AggregationQuery
)
from .interface import (
    CompositeAnalyzer, AnalyticsType, AnalyticsFilter, AnalyticsResult,
    AggregationLevel, TimeRange, MetricThresholds,
    InsufficientDataError, CalculationError
)
from .tss import TSSCalculator, TSSAnalyzer
from ..utils import get_logger


logger = get_logger(__name__)


class AdvancedStatistics(CompositeAnalyzer):
    """Advanced statistical analysis class with TSS integration"""
    
    def __init__(self, storage: StorageInterface, thresholds: Optional[MetricThresholds] = None):
        super().__init__(storage, thresholds)
        # Initialize TSS calculator and analyzer
        self.tss_calculator = TSSCalculator(storage, thresholds)
        self.tss_analyzer = TSSAnalyzer(storage, thresholds)
    
    def get_activity_distribution(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Get activity distribution statistics"""
        start_date = datetime.now() - timedelta(days=days)
        
        query_filter = (QueryFilter()
                       .add_term_filter("user_id", user_id)
                       .add_date_range("timestamp", start=start_date))
        
        agg_query = (AggregationQuery()
                    .add_terms("by_sport", "sport", 10)
                    .add_terms("by_sub_sport", "sub_sport", 10)
                    .add_date_histogram("daily_distribution", "timestamp", "day"))
        
        return self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
    
    def get_heart_rate_analysis(self, user_id: str, activity_id: str = None) -> Dict[str, Any]:
        """Heart rate analysis"""
        query_filter = QueryFilter().add_term_filter("user_id", user_id)
        
        if activity_id:
            query_filter.add_term_filter("activity_id", activity_id)
        
        # Session level heart rate statistics
        session_agg = (AggregationQuery()
                      .add_metric("avg_hr", "avg", "avg_heart_rate")
                      .add_metric("max_hr", "max", "max_heart_rate")
                      .add_metric("min_hr", "min", "avg_heart_rate"))
        
        session_stats = self.storage.aggregate(DataType.SESSION, query_filter, session_agg)
        
        # Record level heart rate distribution
        record_query = QueryFilter().add_term_filter("user_id", user_id)
        if activity_id:
            record_query.add_term_filter("activity_id", activity_id)
        
        # Heart rate zone statistics
        hr_zones = self._calculate_heart_rate_zones(user_id, activity_id)
        
        return {
            "session_stats": session_stats,
            "heart_rate_zones": hr_zones,
            "analysis_date": datetime.now().isoformat()
        }
    
    def get_performance_trends(self, user_id: str, sport: str = None, months: int = 6) -> Dict[str, Any]:
        """Exercise performance trend analysis"""
        start_date = datetime.now() - timedelta(days=months*30)
        
        query_filter = (QueryFilter()
                       .add_term_filter("user_id", user_id)
                       .add_date_range("timestamp", start=start_date)
                       .add_sort("timestamp", ascending=True))
        
        if sport:
            query_filter.add_term_filter("sport", sport)
        
        agg_query = (AggregationQuery()
                    .add_date_histogram("monthly_trend", "timestamp", "month")
                    .add_metric("avg_speed", "avg", "enhanced_avg_speed")
                    .add_metric("avg_distance", "avg", "total_distance")
                    .add_metric("avg_heart_rate", "avg", "avg_heart_rate")
                    .add_metric("total_activities", "value_count", "activity_id"))
        
        trends = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
        
        # Calculate improvement trends
        improvement_analysis = self._analyze_improvement_trends(trends)
        
        return {
            "trends": trends,
            "improvement_analysis": improvement_analysis,
            "sport_filter": sport,
            "analysis_period_months": months
        }
    
    def get_lap_performance_analysis(self, activity_id: str) -> Dict[str, Any]:
        """Lap performance analysis"""
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_sort("lap_number", ascending=True))
        
        laps = self.storage.search(DataType.LAP, query_filter)
        
        if not laps:
            return {"error": "No lap data found"}
        
        # Lap statistics
        lap_stats = {
            "total_laps": len(laps),
            "consistency_analysis": self._analyze_lap_consistency(laps),
            "speed_progression": self._analyze_speed_progression(laps),
            "heart_rate_progression": self._analyze_hr_progression(laps),
            "best_lap": self._find_best_lap(laps),
            "worst_lap": self._find_worst_lap(laps)
        }
        
        return lap_stats
    
    def get_geographic_analysis(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """Geographic activity analysis"""
        start_date = datetime.now() - timedelta(days=days)
        
        # Get records with GPS data
        query_filter = (QueryFilter()
                       .add_term_filter("user_id", user_id)
                       .add_date_range("timestamp", start=start_date)
                       .set_pagination(10000))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        
        # Analyze GPS tracks
        geo_analysis = {
            "total_gps_points": len([r for r in records if 'location' in r]),
            "activity_areas": self._analyze_activity_areas(records),
            "elevation_profile": self._analyze_elevation_profile(records),
            "speed_distribution": self._analyze_speed_distribution(records)
        }
        
        return geo_analysis
    
    def get_training_load_analysis(self, user_id: str, weeks: int = 4) -> Dict[str, Any]:
        """Training load analysis with TSS integration"""
        start_date = datetime.now() - timedelta(weeks=weeks)
        
        query_filter = (QueryFilter()
                       .add_term_filter("user_id", user_id)
                       .add_date_range("timestamp", start=start_date))
        
        agg_query = (AggregationQuery()
                    .add_date_histogram("weekly_load", "timestamp", "week")
                    .add_metric("total_time", "sum", "total_timer_time")
                    .add_metric("total_distance", "sum", "total_distance")
                    .add_metric("total_calories", "sum", "total_calories")
                    .add_metric("activity_count", "value_count", "activity_id"))
        
        load_data = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
        
        # Calculate training load metrics
        training_metrics = self._calculate_training_metrics(load_data)
        
        # Add TSS analysis
        tss_analysis = self.get_tss_analysis(user_id, weeks * 7)
        
        return {
            "weekly_load": load_data,
            "training_metrics": training_metrics,
            "tss_analysis": tss_analysis,
            "recommendations": self._generate_training_recommendations(training_metrics, tss_analysis)
        }
    
    # ====== TSS-related methods ======
    
    def get_tss_analysis(self, user_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get Training Stress Score analysis for a user over a specified period
        
        Args:
            user_id: User identifier
            days: Number of days to analyze (default: 30)
            
        Returns:
            Dictionary containing TSS analysis results
        """
        try:
            # Create analytics filter for TSS analysis
            time_range = TimeRange(days=days)
            filter_criteria = AnalyticsFilter(
                user_id=user_id,
                time_range=time_range
            )
            
            # Get TSS analysis
            tss_result = self.tss_analyzer.analyze_training_stress(filter_criteria)
            
            return tss_result.data
            
        except Exception as e:
            logger.error(f"Error in TSS analysis for user {user_id}: {str(e)}")
            return {"error": f"TSS analysis failed: {str(e)}"}
    
    def get_activity_tss(self, activity_id: str, **kwargs) -> Dict[str, Any]:
        """
        Calculate Training Stress Score for a specific activity
        
        Args:
            activity_id: Activity identifier
            **kwargs: Optional parameters (ftp, threshold_hr, max_hr, threshold_pace)
            
        Returns:
            Dictionary containing TSS calculation results
        """
        try:
            return self.tss_calculator.calculate_composite_tss(activity_id, **kwargs)
        except Exception as e:
            logger.error(f"Error calculating TSS for activity {activity_id}: {str(e)}")
            return {"error": f"TSS calculation failed: {str(e)}"}
    
    def get_weekly_tss_summary(self, user_id: str, week_start: datetime = None) -> Dict[str, Any]:
        """
        Get weekly TSS summary for a user
        
        Args:
            user_id: User identifier
            week_start: Start date of the week (default: current week)
            
        Returns:
            Dictionary containing weekly TSS summary
        """
        if week_start is None:
            # Get start of current week (Monday)
            today = datetime.now().date()
            week_start = datetime.combine(
                today - timedelta(days=today.weekday()), 
                datetime.min.time()
            )
        
        try:
            return self.tss_calculator.calculate_weekly_tss(user_id, week_start)
        except Exception as e:
            logger.error(f"Error calculating weekly TSS for user {user_id}: {str(e)}")
            return {"error": f"Weekly TSS calculation failed: {str(e)}"}
    
    def get_power_tss(self, activity_id: str, ftp: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate power-based TSS for an activity
        
        Args:
            activity_id: Activity identifier
            ftp: Functional Threshold Power (optional)
            
        Returns:
            Dictionary containing power TSS results
        """
        try:
            return self.tss_calculator.calculate_power_tss(activity_id, ftp)
        except Exception as e:
            logger.error(f"Error calculating power TSS for activity {activity_id}: {str(e)}")
            return {"error": f"Power TSS calculation failed: {str(e)}"}
    
    def get_hr_tss(self, activity_id: str, threshold_hr: Optional[int] = None, 
                   max_hr: Optional[int] = None) -> Dict[str, Any]:
        """
        Calculate heart rate-based TSS for an activity
        
        Args:
            activity_id: Activity identifier
            threshold_hr: Lactate threshold heart rate (optional)
            max_hr: Maximum heart rate (optional)
            
        Returns:
            Dictionary containing heart rate TSS results
        """
        try:
            return self.tss_calculator.calculate_hr_tss(activity_id, threshold_hr, max_hr)
        except Exception as e:
            logger.error(f"Error calculating HR TSS for activity {activity_id}: {str(e)}")
            return {"error": f"HR TSS calculation failed: {str(e)}"}
    
    def get_pace_tss(self, activity_id: str, threshold_pace: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate pace-based TSS for a running activity
        
        Args:
            activity_id: Activity identifier
            threshold_pace: Functional threshold pace in seconds per meter (optional)
            
        Returns:
            Dictionary containing pace TSS results
        """
        try:
            return self.tss_calculator.calculate_pace_tss(activity_id, threshold_pace)
        except Exception as e:
            logger.error(f"Error calculating pace TSS for activity {activity_id}: {str(e)}")
            return {"error": f"Pace TSS calculation failed: {str(e)}"}
    
    def get_tss_trends(self, user_id: str, weeks: int = 12) -> Dict[str, Any]:
        """
        Analyze TSS trends over multiple weeks
        
        Args:
            user_id: User identifier
            weeks: Number of weeks to analyze (default: 12)
            
        Returns:
            Dictionary containing TSS trend analysis
        """
        try:
            end_date = datetime.now()
            weekly_summaries = []
            
            for week_offset in range(weeks):
                week_start = end_date - timedelta(weeks=week_offset + 1)
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                
                weekly_tss = self.tss_calculator.calculate_weekly_tss(user_id, week_start)
                weekly_summaries.append({
                    'week_start': week_start.isoformat(),
                    'week_number': weeks - week_offset,
                    'tss': weekly_tss.get('weekly_tss', 0),
                    'activity_count': weekly_tss.get('activity_count', 0)
                })
            
            # Reverse to get chronological order
            weekly_summaries.reverse()
            
            # Calculate trend metrics
            tss_values = [w['tss'] for w in weekly_summaries if w['tss'] > 0]
            
            trend_analysis = {
                'weekly_summaries': weekly_summaries,
                'avg_weekly_tss': round(sum(tss_values) / len(tss_values), 1) if tss_values else 0,
                'max_weekly_tss': max(tss_values) if tss_values else 0,
                'min_weekly_tss': min(tss_values) if tss_values else 0,
                'trend': self._calculate_tss_trend(tss_values),
                'total_weeks_analyzed': weeks,
                'active_weeks': len(tss_values)
            }
            
            return trend_analysis
            
        except Exception as e:
            logger.error(f"Error calculating TSS trends for user {user_id}: {str(e)}")
            return {"error": f"TSS trend analysis failed: {str(e)}"}
    
    # ====== Activity comparison with TSS ======
    
    def compare_activities(self, activity_ids: List[str], metrics: List[str] = None) -> AnalyticsResult:
        """Compare activities implementation with TSS"""
        activities = []
        
        for activity_id in activity_ids:
            query_filter = QueryFilter().add_term_filter("activity_id", activity_id)
            activity_data = self.storage.search(DataType.SESSION, query_filter)
            if activity_data:
                activity = activity_data[0]
                # Add TSS to activity data
                try:
                    tss_data = self.get_activity_tss(activity_id)
                    activity['tss'] = tss_data.get('tss', 0)
                    activity['tss_method'] = tss_data.get('primary_method', 'unknown')
                except:
                    activity['tss'] = 0
                    activity['tss_method'] = 'error'
                activities.append(activity)
        
        if len(activities) < 2:
            return AnalyticsResult(
                analytics_type=AnalyticsType.COMPARISON,
                data={"error": "Need at least 2 activities to compare"},
                metadata={},
                generated_at=datetime.now()
            )
        
        comparison = {
            "activities": activities,
            "metrics_comparison": self._compare_activity_metrics(activities),
            "performance_ranking": self._rank_activities(activities),
            "tss_comparison": self._compare_tss_metrics(activities)
        }
        
        return AnalyticsResult(
            analytics_type=AnalyticsType.COMPARISON,
            data=comparison,
            metadata={},
            generated_at=datetime.now()
        )
    
    def compare_activities_legacy(self, activity_ids: List[str]) -> Dict[str, Any]:
        """Legacy compare activities method for backward compatibility"""
        result = self.compare_activities(activity_ids, [])
        if "error" in result.data:
            return result.data
        return result.data
    
    # ====== Abstract method implementations ======
    
    # Abstract method implementations from FitnessAnalyzer
    def analyze_performance(self, filter_criteria, aggregation_level=None):
        """Performance analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.PERFORMANCE,
            data={"message": "Performance analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def analyze_heart_rate(self, filter_criteria):
        """Heart rate analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.HEART_RATE,
            data={"message": "Heart rate analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def analyze_training_load(self, filter_criteria, aggregation_level=None):
        """Training load analysis implementation using TSS"""
        try:
            return self.tss_analyzer.analyze_training_stress(filter_criteria)
        except Exception as e:
            return AnalyticsResult(
                analytics_type=AnalyticsType.TRAINING_LOAD,
                data={"error": f"Training load analysis failed: {str(e)}"},
                metadata={},
                generated_at=datetime.now()
            )
    
    def analyze_trends(self, filter_criteria, metrics, aggregation_level=None):
        """Trend analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.PERFORMANCE,
            data={"message": "Trend analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    # Abstract method implementations from PowerAnalyzer
    def analyze_power_distribution(self, filter_criteria):
        """Power distribution analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.POWER,
            data={"message": "Power distribution analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def calculate_ftp_estimate(self, filter_criteria):
        """Calculate FTP estimate implementation"""
        return None
    
    def analyze_power_zones(self, filter_criteria):
        """Power zone analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.POWER,
            data={"message": "Power zone analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    # Abstract method implementations from RunningDynamicsAnalyzer
    def analyze_cadence(self, filter_criteria):
        """Cadence analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.RUNNING_DYNAMICS,
            data={"message": "Cadence analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def analyze_stride_metrics(self, filter_criteria):
        """Stride metrics analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.RUNNING_DYNAMICS,
            data={"message": "Stride metrics analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def analyze_vertical_oscillation(self, filter_criteria):
        """Vertical oscillation analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.RUNNING_DYNAMICS,
            data={"message": "Vertical oscillation analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def analyze_ground_contact_time(self, filter_criteria):
        """Ground contact time analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.RUNNING_DYNAMICS,
            data={"message": "Ground contact time analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    # Abstract method implementations from TrajectoryAnalyzer
    def analyze_route_efficiency(self, activity_id):
        """Route efficiency analysis implementation"""
        return {"message": "Route efficiency analysis not yet implemented"}
    
    def detect_segments(self, activity_id, segment_type="climb"):
        """Segment detection implementation"""
        return []
    
    def calculate_elevation_profile(self, activity_id):
        """Elevation profile calculation implementation"""
        return {"message": "Elevation profile calculation not yet implemented"}
    
    def get_route_statistics(self, activity_id):
        """Route statistics implementation"""
        return {"message": "Route statistics not yet implemented"}
    
    # Abstract method implementations from RecoveryAnalyzer
    def calculate_recovery_score(self, filter_criteria):
        """Calculate recovery score implementation"""
        return {"message": "Recovery score calculation not yet implemented"}
    
    def analyze_resting_heart_rate_trend(self, filter_criteria):
        """Resting heart rate trend analysis implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.HEART_RATE,
            data={"message": "Resting heart rate trend analysis not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def estimate_recovery_time(self, activity_id):
        """Estimate recovery time implementation"""
        return None
    
    # Abstract method implementations from ComparisonAnalyzer
    def compare_time_periods(self, user_id, period1, period2, metrics):
        """Time period comparison implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.COMPARISON,
            data={"message": "Time period comparison not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    def compare_users(self, user_ids, filter_criteria, metrics):
        """User comparison implementation"""
        return AnalyticsResult(
            analytics_type=AnalyticsType.COMPARISON,
            data={"message": "User comparison not yet implemented"},
            metadata={},
            generated_at=datetime.now()
        )
    
    # Abstract method implementations from CompositeAnalyzer
    def generate_comprehensive_report(self, filter_criteria):
        """Generate comprehensive report implementation"""
        return {"message": "Comprehensive report generation not yet implemented"}
    
    def get_personalized_insights(self, user_id, days=30):
        """Personalized insights implementation"""
        return []
    
    def detect_anomalies(self, filter_criteria):
        """Anomaly detection implementation"""
        return []

    # ====== Helper methods ======
    
    def _calculate_heart_rate_zones(self, user_id: str, activity_id: str = None) -> Dict[str, Any]:
        """Calculate heart rate zone distribution"""
        query_filter = QueryFilter().add_term_filter("user_id", user_id)
        if activity_id:
            query_filter.add_term_filter("activity_id", activity_id)
        
        # Assume max heart rate is 190 (can be obtained from user profile or calculated)
        max_hr = 190
        zones = {
            "zone_1": {"min": int(max_hr * 0.5), "max": int(max_hr * 0.6), "count": 0},
            "zone_2": {"min": int(max_hr * 0.6), "max": int(max_hr * 0.7), "count": 0},
            "zone_3": {"min": int(max_hr * 0.7), "max": int(max_hr * 0.8), "count": 0},
            "zone_4": {"min": int(max_hr * 0.8), "max": int(max_hr * 0.9), "count": 0},
            "zone_5": {"min": int(max_hr * 0.9), "max": max_hr, "count": 0}
        }
        
        records = self.storage.search(DataType.RECORD, query_filter)
        total_records = 0
        
        for record in records:
            if 'heart_rate' in record and record['heart_rate']:
                hr = record['heart_rate']
                total_records += 1
                
                for zone_data in zones.values():
                    if zone_data["min"] <= hr < zone_data["max"]:
                        zone_data["count"] += 1
                        break
        
        # Calculate percentage
        for zone_data in zones.values():
            zone_data["percentage"] = (zone_data["count"] / total_records * 100) if total_records > 0 else 0
        
        return zones
    
    def _analyze_improvement_trends(self, trends_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze improvement trends"""
        if "monthly_trend" not in trends_data or not trends_data["monthly_trend"].get("buckets"):
            return {"error": "Insufficient data for trend analysis"}
        
        buckets = trends_data["monthly_trend"]["buckets"]
        
        # Calculate trend for each metric
        speed_trend = self._calculate_trend([b.get("avg_speed", {}).get("value") for b in buckets])
        distance_trend = self._calculate_trend([b.get("avg_distance", {}).get("value") for b in buckets])
        
        return {
            "speed_improvement": speed_trend,
            "distance_improvement": distance_trend,
            "overall_trend": "improving" if (speed_trend["slope"] > 0 or distance_trend["slope"] > 0) else "declining"
        }
    
    def _calculate_trend(self, values: List[float]) -> Dict[str, Any]:
        """Calculate trend slope"""
        valid_values = [v for v in values if v is not None]
        if len(valid_values) < 2:
            return {"slope": 0, "trend": "insufficient_data"}
        
        # Simple linear trend calculation
        n = len(valid_values)
        x_sum = sum(range(n))
        y_sum = sum(valid_values)
        xy_sum = sum(i * v for i, v in enumerate(valid_values))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        return {
            "slope": slope,
            "trend": "improving" if slope > 0 else "declining",
            "confidence": min(n / 6, 1.0)  # Confidence based on data points
        }
    
    def _analyze_lap_consistency(self, laps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze lap consistency"""
        speeds = [lap.get("enhanced_avg_speed", 0) for lap in laps if lap.get("enhanced_avg_speed")]
        
        if len(speeds) < 2:
            return {"consistency": "insufficient_data"}
        
        avg_speed = sum(speeds) / len(speeds)
        variance = sum((s - avg_speed) ** 2 for s in speeds) / len(speeds)
        cv = (variance ** 0.5) / avg_speed if avg_speed > 0 else 0
        
        consistency_level = "excellent" if cv < 0.05 else "good" if cv < 0.1 else "moderate" if cv < 0.15 else "poor"
        
        return {
            "coefficient_of_variation": cv,
            "consistency": consistency_level,
            "speed_range": {"min": min(speeds), "max": max(speeds), "avg": avg_speed}
        }
    
    def _analyze_speed_progression(self, laps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze speed progression"""
        progression = []
        for i, lap in enumerate(laps):
            speed = lap.get("enhanced_avg_speed", 0)
            progression.append({
                "lap_number": i + 1,
                "speed": speed,
                "relative_change": ((speed - laps[0].get("enhanced_avg_speed", 0)) / 
                                  laps[0].get("enhanced_avg_speed", 1)) * 100 if i > 0 else 0
            })
        return progression
    
    def _analyze_hr_progression(self, laps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Analyze heart rate progression"""
        progression = []
        for i, lap in enumerate(laps):
            hr = lap.get("avg_heart_rate", 0)
            progression.append({
                "lap_number": i + 1,
                "heart_rate": hr,
                "relative_change": ((hr - laps[0].get("avg_heart_rate", 0)) / 
                                  laps[0].get("avg_heart_rate", 1)) * 100 if i > 0 else 0
            })
        return progression
    
    def _find_best_lap(self, laps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find best lap"""
        if not laps:
            return {}
        
        best_lap = max(laps, key=lambda x: x.get("enhanced_avg_speed", 0))
        return {
            "lap_number": best_lap.get("lap_number"),
            "speed": best_lap.get("enhanced_avg_speed"),
            "time": best_lap.get("total_timer_time"),
            "heart_rate": best_lap.get("avg_heart_rate")
        }
    
    def _find_worst_lap(self, laps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Find worst lap"""
        if not laps:
            return {}
        
        worst_lap = min(laps, key=lambda x: x.get("enhanced_avg_speed", float('inf')))
        return {
            "lap_number": worst_lap.get("lap_number"),
            "speed": worst_lap.get("enhanced_avg_speed"),
            "time": worst_lap.get("total_timer_time"),
            "heart_rate": worst_lap.get("avg_heart_rate")
        }
    
    def _analyze_activity_areas(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze activity areas"""
        gps_points = [r['location'] for r in records if 'location' in r and r['location']]
        
        if not gps_points:
            return {"error": "No GPS data available"}
        
        lats = [p['lat'] for p in gps_points if 'lat' in p]
        lons = [p['lon'] for p in gps_points if 'lon' in p]
        
        if not lats or not lons:
            return {"error": "Invalid GPS coordinates"}
        
        return {
            "bounding_box": {
                "north": max(lats),
                "south": min(lats),
                "east": max(lons),
                "west": min(lons)
            },
            "center_point": {
                "lat": sum(lats) / len(lats),
                "lon": sum(lons) / len(lons)
            },
            "gps_point_count": len(gps_points)
        }
    
    def _analyze_elevation_profile(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze elevation profile"""
        elevations = [r.get('altitude') for r in records if r.get('altitude') is not None]
        
        if not elevations:
            return {"error": "No elevation data available"}
        
        return {
            "max_elevation": max(elevations),
            "min_elevation": min(elevations),
            "elevation_gain": max(elevations) - min(elevations),
            "avg_elevation": sum(elevations) / len(elevations)
        }
    
    def _analyze_speed_distribution(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze speed distribution"""
        speeds = [r.get('speed') for r in records if r.get('speed') is not None and r.get('speed') > 0]
        
        if not speeds:
            return {"error": "No speed data available"}
        
        speeds.sort()
        n = len(speeds)
        
        return {
            "max_speed": max(speeds),
            "min_speed": min(speeds),
            "avg_speed": sum(speeds) / n,
            "median_speed": speeds[n//2],
            "percentile_90": speeds[int(n * 0.9)],
            "percentile_10": speeds[int(n * 0.1)]
        }
    
    def _calculate_training_metrics(self, load_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate training metrics"""
        if "weekly_load" not in load_data:
            return {}
        
        buckets = load_data["weekly_load"].get("buckets", [])
        
        weekly_times = [b.get("total_time", {}).get("value", 0) for b in buckets]
        weekly_distances = [b.get("total_distance", {}).get("value", 0) for b in buckets]
        
        return {
            "avg_weekly_time": sum(weekly_times) / len(weekly_times) if weekly_times else 0,
            "avg_weekly_distance": sum(weekly_distances) / len(weekly_distances) if weekly_distances else 0,
            "training_consistency": len([t for t in weekly_times if t > 0]) / len(weekly_times) if weekly_times else 0,
            "load_progression": self._calculate_trend(weekly_times)
        }
    
    def _generate_training_recommendations(self, metrics: Dict[str, Any], tss_analysis: Dict[str, Any] = None) -> List[str]:
        """Generate training recommendations based on metrics and TSS analysis"""
        recommendations = []
        
        consistency = metrics.get("training_consistency", 0)
        if consistency < 0.5:
            recommendations.append("It is recommended to maintain a more regular training frequency")
        
        load_trend = metrics.get("load_progression", {}).get("trend")
        if load_trend == "declining":
            recommendations.append("Consider gradually increasing training load")
        elif load_trend == "improving":
            recommendations.append("Maintain current training intensity growth")
        
        # Add TSS-based recommendations
        if tss_analysis:
            weekly_tss = tss_analysis.get("avg_weekly_tss", 0)
            load_category = tss_analysis.get("training_load_category", "low")
            
            if load_category == "low":
                recommendations.append("Your training stress is low - consider adding more training volume or intensity")
            elif load_category == "very_high":
                recommendations.append("Your training stress is very high - consider adding recovery days or reducing intensity")
            elif load_category == "high":
                recommendations.append("Your training stress is high - monitor recovery and avoid overtraining")
            
            activity_count = tss_analysis.get("activity_count", 0)
            if activity_count > 0:
                avg_tss_per_activity = tss_analysis.get("total_tss", 0) / activity_count
                if avg_tss_per_activity < 50:
                    recommendations.append("Consider longer or more intense training sessions for better adaptation")
                elif avg_tss_per_activity > 150:
                    recommendations.append("High intensity sessions detected - ensure adequate recovery between workouts")
        
        return recommendations
    
    def _compare_activity_metrics(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare activity metrics"""
        metrics = ["total_distance", "total_timer_time", "enhanced_avg_speed", "avg_heart_rate"]
        comparison = {}
        
        for metric in metrics:
            values = [a.get(metric) for a in activities if a.get(metric) is not None]
            if values:
                comparison[metric] = {
                    "max": max(values),
                    "min": min(values),
                    "avg": sum(values) / len(values),
                    "range": max(values) - min(values)
                }
        
        return comparison
    
    def _compare_tss_metrics(self, activities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compare TSS metrics between activities"""
        tss_values = [a.get('tss', 0) for a in activities if a.get('tss', 0) > 0]
        
        if not tss_values:
            return {"error": "No TSS data available for comparison"}
        
        return {
            "max_tss": max(tss_values),
            "min_tss": min(tss_values),
            "avg_tss": round(sum(tss_values) / len(tss_values), 1),
            "tss_range": max(tss_values) - min(tss_values),
            "activities_with_tss": len(tss_values),
            "tss_methods": [a.get('tss_method', 'unknown') for a in activities if a.get('tss', 0) > 0]
        }
    
    def _rank_activities(self, activities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Rank activities"""
        # Rank by TSS if available, otherwise by speed
        def sort_key(activity):
            if activity.get('tss', 0) > 0:
                return activity['tss']
            return activity.get("enhanced_avg_speed", 0)
        
        ranked = sorted(activities, key=sort_key, reverse=True)
        
        for i, activity in enumerate(ranked):
            activity["rank"] = i + 1
            activity["score"] = self._calculate_activity_score(activity)
        
        return ranked
    
    def _calculate_activity_score(self, activity: Dict[str, Any]) -> float:
        """Calculate activity score including TSS"""
        # Enhanced scoring system with TSS
        speed_score = (activity.get("enhanced_avg_speed", 0) * 10)
        distance_score = (activity.get("total_distance", 0) / 1000)
        hr_efficiency = 100 - (activity.get("avg_heart_rate", 150) - 120)  # Heart rate efficiency
        tss_score = activity.get("tss", 0) * 0.5  # TSS contributes to overall score
        
        return speed_score + distance_score + hr_efficiency + tss_score
    
    def _calculate_tss_trend(self, tss_values: List[float]) -> Dict[str, Any]:
        """Calculate TSS trend using linear regression"""
        if len(tss_values) < 2:
            return {"trend": "insufficient_data", "slope": 0}
        
        n = len(tss_values)
        x_values = list(range(n))
        
        # Simple linear regression
        x_sum = sum(x_values)
        y_sum = sum(tss_values)
        xy_sum = sum(x * y for x, y in zip(x_values, tss_values))
        x2_sum = sum(x * x for x in x_values)
        
        if n * x2_sum - x_sum * x_sum == 0:
            return {"trend": "no_trend", "slope": 0}
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        
        trend_direction = "increasing" if slope > 1.0 else "decreasing" if slope < -1.0 else "stable"
        
        return {
            "trend": trend_direction,
            "slope": round(slope, 2),
            "weekly_change": round(slope, 1)
        }
