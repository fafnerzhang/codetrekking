#!/usr/bin/env python3
"""
Advanced Analytics Implementation - Complete fitness data analysis functionality
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from ..storage.interface import (
    StorageInterface, DataType, QueryFilter, AggregationQuery
)
from .interface import (
    CompositeAnalyzer, AnalyticsType, AnalyticsFilter, AnalyticsResult,
    AggregationLevel, TimeRange, MetricThresholds,
    InsufficientDataError, CalculationError, InvalidParameterError
)
from ..utils import get_logger


logger = get_logger(__name__)


class ElasticsearchAnalytics(CompositeAnalyzer):
    """Elasticsearch-based analytics implementation"""
    
    def __init__(self, storage: StorageInterface, thresholds: Optional[MetricThresholds] = None):
        super().__init__(storage, thresholds)
        self._setup_default_thresholds()
    
    def _setup_default_thresholds(self):
        """Set default thresholds"""
        if not self.thresholds.heart_rate_zones:
            self.thresholds.heart_rate_zones = {
                "zone_1": (50, 120),
                "zone_2": (120, 140),
                "zone_3": (140, 160),
                "zone_4": (160, 180),
                "zone_5": (180, 220)
            }
        
        if not self.thresholds.pace_zones:
            self.thresholds.pace_zones = {
                "easy": (6.0, 8.0),      # min/km
                "moderate": (5.0, 6.0),
                "threshold": (4.0, 5.0),
                "interval": (3.0, 4.0),
                "fast": (2.5, 3.0)
            }
    
    # FitnessAnalyzer implementation
    def analyze_performance(self, filter_criteria: AnalyticsFilter, 
                          aggregation_level: AggregationLevel = AggregationLevel.ACTIVITY) -> AnalyticsResult:
        """Exercise performance analysis"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            
            # Set time interval based on aggregation level
            interval_map = {
                AggregationLevel.DAILY: "day",
                AggregationLevel.WEEKLY: "week",
                AggregationLevel.MONTHLY: "month",
                AggregationLevel.YEARLY: "year"
            }
            
            agg_query = AggregationQuery()
            
            if aggregation_level != AggregationLevel.ACTIVITY:
                interval = interval_map[aggregation_level]
                agg_query.add_date_histogram("time_series", "timestamp", interval)
            
            # Add basic metrics
            agg_query.add_metric("total_distance", "sum", "total_distance")
            agg_query.add_metric("total_time", "sum", "total_timer_time")
            agg_query.add_metric("avg_speed", "avg", "enhanced_avg_speed")
            agg_query.add_metric("avg_heart_rate", "avg", "avg_heart_rate")
            agg_query.add_metric("total_calories", "sum", "total_calories")
            agg_query.add_metric("activity_count", "value_count", "activity_id")
            
            # Sport type distribution
            agg_query.add_terms("sport_distribution", "sport", 10)
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.PERFORMANCE,
                data=results,
                metadata={
                    "aggregation_level": aggregation_level.value,
                    "filter_criteria": filter_criteria.__dict__
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Performance analysis failed: {e}")
            raise CalculationError(f"Performance analysis failed: {e}")
    
    def analyze_heart_rate(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """Heart rate analysis"""
        try:
            # Session level analysis
            session_query = self._build_query_filter(filter_criteria)
            session_agg = (AggregationQuery()
                          .add_metric("avg_hr", "avg", "avg_heart_rate")
                          .add_metric("max_hr", "max", "max_heart_rate")
                          .add_metric("min_hr", "min", "avg_heart_rate"))
            
            session_stats = self.storage.aggregate(DataType.SESSION, session_query, session_agg)
            
            # Record level heart rate zone analysis
            if filter_criteria.activity_ids and len(filter_criteria.activity_ids) == 1:
                hr_zones = self._calculate_heart_rate_zones_for_activity(filter_criteria.activity_ids[0])
            else:
                hr_zones = self._calculate_heart_rate_zones_for_user(filter_criteria.user_id, filter_criteria.time_range)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.HEART_RATE,
                data={
                    "session_statistics": session_stats,
                    "heart_rate_zones": hr_zones,
                    "thresholds": self.thresholds.heart_rate_zones
                },
                metadata={"filter_criteria": filter_criteria.__dict__},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Heart rate analysis failed: {e}")
            raise CalculationError(f"Heart rate analysis failed: {e}")
    
    def analyze_training_load(self, filter_criteria: AnalyticsFilter, 
                            aggregation_level: AggregationLevel = AggregationLevel.WEEKLY) -> AnalyticsResult:
        """Training load analysis"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            
            interval_map = {
                AggregationLevel.DAILY: "day",
                AggregationLevel.WEEKLY: "week",
                AggregationLevel.MONTHLY: "month"
            }
            
            agg_query = (AggregationQuery()
                        .add_date_histogram("training_load_timeline", "timestamp", interval_map[aggregation_level])
                        .add_metric("total_duration", "sum", "total_timer_time")
                        .add_metric("total_distance", "sum", "total_distance")
                        .add_metric("activity_count", "value_count", "activity_id")
                        .add_metric("avg_intensity", "avg", "avg_heart_rate"))
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            
            # Calculate training load metrics
            training_load_metrics = self._calculate_training_load_metrics(results)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.TRAINING_LOAD,
                data={
                    "timeline_data": results,
                    "training_load_metrics": training_load_metrics
                },
                metadata={
                    "aggregation_level": aggregation_level.value,
                    "calculation_method": "duration_intensity_based"
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Training load analysis failed: {e}")
            raise CalculationError(f"Training load analysis failed: {e}")
    
    def analyze_trends(self, filter_criteria: AnalyticsFilter, 
                      metrics: List[str], 
                      aggregation_level: AggregationLevel = AggregationLevel.WEEKLY) -> AnalyticsResult:
        """Trend analysis"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            
            interval_map = {
                AggregationLevel.DAILY: "day",
                AggregationLevel.WEEKLY: "week",
                AggregationLevel.MONTHLY: "month"
            }
            
            agg_query = AggregationQuery()
            agg_query.add_date_histogram("timeline", "timestamp", interval_map[aggregation_level])
            
            # Dynamically add metrics
            metric_mapping = {
                "distance": ("avg", "total_distance"),
                "speed": ("avg", "enhanced_avg_speed"),
                "heart_rate": ("avg", "avg_heart_rate"),
                "duration": ("avg", "total_timer_time"),
                "calories": ("avg", "total_calories")
            }
            
            for metric in metrics:
                if metric in metric_mapping:
                    agg_type, field = metric_mapping[metric]
                    agg_query.add_metric(f"trend_{metric}", agg_type, field)
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            
            # Calculate trend statistics
            trend_analysis = self._calculate_trend_statistics(results, metrics)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.PERFORMANCE,
                data={
                    "timeline_data": results,
                    "trend_statistics": trend_analysis
                },
                metadata={
                    "metrics": metrics,
                    "aggregation_level": aggregation_level.value
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            raise CalculationError(f"Trend analysis failed: {e}")
    
    # PowerAnalyzer 實現
    def analyze_power_distribution(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """功率分布分析"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_exists_filter("power_data.power")
            
            # 獲取功率數據
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError("No power data found")
            
            power_values = [r.get("power_data", {}).get("power", 0) for r in records if r.get("power_data", {}).get("power")]
            
            if not power_values:
                raise InsufficientDataError("No valid power values found")
            
            # 計算功率分布
            power_distribution = self._calculate_power_distribution(power_values)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.POWER,
                data=power_distribution,
                metadata={"total_power_points": len(power_values)},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Power distribution analysis failed: {e}")
            raise CalculationError(f"Power distribution analysis failed: {e}")
    
    def calculate_ftp_estimate(self, filter_criteria: AnalyticsFilter) -> Optional[float]:
        """Estimate Functional Threshold Power (FTP)"""
        try:
            # Find recent long-duration activities (>20 minutes)
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_range_filter("total_timer_time", min_value=1200)  # 20 minutes
            query_filter.add_exists_filter("power_data.power")
            query_filter.add_sort("timestamp", ascending=False)
            query_filter.set_pagination(10)  # Latest 10 activities
            
            sessions = self.storage.search(DataType.SESSION, query_filter)
            
            if not sessions:
                return None
            
            ftp_estimates = []
            for session in sessions:
                activity_id = session.get("activity_id")
                if activity_id:
                    # 計算該活動的20分鐘最大平均功率
                    twenty_min_power = self._calculate_20min_max_power(activity_id)
                    if twenty_min_power:
                        ftp_estimates.append(twenty_min_power * 0.95)  # FTP = 95% of 20min power
            
            return max(ftp_estimates) if ftp_estimates else None
            
        except Exception as e:
            logger.error(f"FTP estimation failed: {e}")
            return None
    
    def analyze_power_zones(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """功率區間分析"""
        try:
            ftp = self.calculate_ftp_estimate(filter_criteria)
            if not ftp:
                raise InsufficientDataError("Cannot calculate FTP for power zone analysis")
            
            # 定義功率區間
            power_zones = {
                "active_recovery": (0, 0.55 * ftp),
                "endurance": (0.55 * ftp, 0.75 * ftp),
                "tempo": (0.75 * ftp, 0.90 * ftp),
                "threshold": (0.90 * ftp, 1.05 * ftp),
                "vo2_max": (1.05 * ftp, 1.20 * ftp),
                "anaerobic": (1.20 * ftp, 1.50 * ftp),
                "neuromuscular": (1.50 * ftp, float('inf'))
            }
            
            # 分析時間分布
            zone_distribution = self._calculate_power_zone_distribution(filter_criteria, power_zones)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.POWER,
                data={
                    "ftp": ftp,
                    "power_zones": power_zones,
                    "zone_distribution": zone_distribution
                },
                metadata={"ftp_calculation_method": "20min_test"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Power zone analysis failed: {e}")
            raise CalculationError(f"Power zone analysis failed: {e}")
    
    # RunningDynamicsAnalyzer 實現
    def analyze_cadence(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """步頻分析"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            
            agg_query = (AggregationQuery()
                        .add_metric("avg_cadence", "avg", "avg_cadence")
                        .add_metric("max_cadence", "max", "max_cadence")
                        .add_terms("cadence_distribution", "avg_cadence", 20))
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            
            # 詳細步頻分析
            cadence_analysis = self._analyze_cadence_patterns(filter_criteria)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.RUNNING_DYNAMICS,
                data={
                    "session_statistics": results,
                    "cadence_patterns": cadence_analysis
                },
                metadata={"analysis_type": "cadence"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Cadence analysis failed: {e}")
            raise CalculationError(f"Cadence analysis failed: {e}")
    
    def analyze_stride_metrics(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """步幅指標分析"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_exists_filter("running_dynamics")
            
            # 獲取包含跑步動態的記錄
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError("No running dynamics data found")
            
            stride_analysis = self._analyze_stride_metrics(records)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.RUNNING_DYNAMICS,
                data=stride_analysis,
                metadata={"total_records": len(records)},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Stride metrics analysis failed: {e}")
            raise CalculationError(f"Stride metrics analysis failed: {e}")
    
    def analyze_vertical_oscillation(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """垂直振幅分析"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_exists_filter("running_dynamics.vertical_oscillation")
            
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError("No vertical oscillation data found")
            
            vo_analysis = self._analyze_vertical_oscillation(records)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.RUNNING_DYNAMICS,
                data=vo_analysis,
                metadata={"analysis_type": "vertical_oscillation"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Vertical oscillation analysis failed: {e}")
            raise CalculationError(f"Vertical oscillation analysis failed: {e}")
    
    def analyze_ground_contact_time(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """著地時間分析"""
        try:
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_exists_filter("running_dynamics.stance_time")
            
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError("No ground contact time data found")
            
            gct_analysis = self._analyze_ground_contact_time(records)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.RUNNING_DYNAMICS,
                data=gct_analysis,
                metadata={"analysis_type": "ground_contact_time"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Ground contact time analysis failed: {e}")
            raise CalculationError(f"Ground contact time analysis failed: {e}")
    
    # TrajectoryAnalyzer 實現
    def analyze_route_efficiency(self, activity_id: str) -> Dict[str, Any]:
        """路線效率分析"""
        try:
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .add_exists_filter("location")
                           .add_sort("timestamp", ascending=True))
            
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError(f"No GPS data found for activity {activity_id}")
            
            return self._calculate_route_efficiency(records)
            
        except Exception as e:
            logger.error(f"Route efficiency analysis failed: {e}")
            raise CalculationError(f"Route efficiency analysis failed: {e}")
    
    def detect_segments(self, activity_id: str, segment_type: str = "climb") -> List[Dict[str, Any]]:
        """路段識別"""
        try:
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .add_exists_filter("altitude")
                           .add_sort("timestamp", ascending=True))
            
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError(f"No altitude data found for activity {activity_id}")
            
            if segment_type == "climb":
                return self._detect_climb_segments(records)
            elif segment_type == "descent":
                return self._detect_descent_segments(records)
            else:
                return self._detect_flat_segments(records)
            
        except Exception as e:
            logger.error(f"Segment detection failed: {e}")
            raise CalculationError(f"Segment detection failed: {e}")
    
    def calculate_elevation_profile(self, activity_id: str) -> Dict[str, Any]:
        """高度剖面計算"""
        try:
            query_filter = (QueryFilter()
                           .add_term_filter("activity_id", activity_id)
                           .add_exists_filter("altitude")
                           .add_sort("timestamp", ascending=True))
            
            records = self.storage.search(DataType.RECORD, query_filter)
            
            if not records:
                raise InsufficientDataError(f"No altitude data found for activity {activity_id}")
            
            return self._calculate_elevation_profile(records)
            
        except Exception as e:
            logger.error(f"Elevation profile calculation failed: {e}")
            raise CalculationError(f"Elevation profile calculation failed: {e}")
    
    def get_route_statistics(self, activity_id: str) -> Dict[str, Any]:
        """路線統計"""
        try:
            # 獲取基本活動信息
            session_query = QueryFilter().add_term_filter("activity_id", activity_id)
            sessions = self.storage.search(DataType.SESSION, session_query)
            
            if not sessions:
                raise InsufficientDataError(f"No session data found for activity {activity_id}")
            
            session = sessions[0]
            
            # 獲取詳細路線數據
            route_efficiency = self.analyze_route_efficiency(activity_id)
            elevation_profile = self.calculate_elevation_profile(activity_id)
            
            return {
                "basic_stats": {
                    "total_distance": session.get("total_distance"),
                    "total_time": session.get("total_timer_time"),
                    "avg_speed": session.get("enhanced_avg_speed"),
                    "max_speed": session.get("enhanced_max_speed")
                },
                "route_efficiency": route_efficiency,
                "elevation_profile": elevation_profile
            }
            
        except Exception as e:
            logger.error(f"Route statistics calculation failed: {e}")
            raise CalculationError(f"Route statistics calculation failed: {e}")
    
    # Helper methods (繼續在下一部分...)
    def _build_query_filter(self, filter_criteria: AnalyticsFilter) -> QueryFilter:
        """構建查詢過濾器"""
        query_filter = QueryFilter().add_term_filter("user_id", filter_criteria.user_id)
        
        if filter_criteria.activity_ids:
            if len(filter_criteria.activity_ids) == 1:
                query_filter.add_term_filter("activity_id", filter_criteria.activity_ids[0])
            else:
                query_filter.add_terms_filter("activity_id", filter_criteria.activity_ids)
        
        if filter_criteria.time_range:
            start_date, end_date = filter_criteria.time_range.to_dates()
            if start_date or end_date:
                query_filter.add_date_range("timestamp", start=start_date, end=end_date)
        
        if filter_criteria.sport_types:
            if len(filter_criteria.sport_types) == 1:
                query_filter.add_term_filter("sport", filter_criteria.sport_types[0])
            else:
                query_filter.add_terms_filter("sport", filter_criteria.sport_types)
        
        if filter_criteria.min_distance:
            query_filter.add_range_filter("total_distance", min_value=filter_criteria.min_distance)
        
        if filter_criteria.max_distance:
            query_filter.add_range_filter("total_distance", max_value=filter_criteria.max_distance)
        
        if filter_criteria.min_duration:
            query_filter.add_range_filter("total_timer_time", min_value=filter_criteria.min_duration)
        
        if filter_criteria.max_duration:
            query_filter.add_range_filter("total_timer_time", max_value=filter_criteria.max_duration)
        
        return query_filter
    
    # RecoveryAnalyzer 實現
    def calculate_recovery_score(self, filter_criteria: AnalyticsFilter) -> Dict[str, Any]:
        """計算恢復評分"""
        try:
            # 獲取最近幾天的活動數據
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_sort("timestamp", ascending=False)
            query_filter.set_pagination(20)  # 最近20次活動
            
            sessions = self.storage.search(DataType.SESSION, query_filter)
            
            if len(sessions) < 5:
                raise InsufficientDataError("Insufficient data for recovery analysis")
            
            # 簡化的恢復評分計算
            recovery_factors = {
                "training_load_balance": self._calculate_training_load_balance(sessions),
                "intensity_distribution": self._calculate_intensity_distribution(sessions),
                "rest_day_ratio": self._calculate_rest_day_ratio(sessions),
                "heart_rate_trend": self._calculate_hr_recovery_trend(sessions)
            }
            
            # 綜合恢復評分 (0-100)
            overall_score = (
                recovery_factors["training_load_balance"] * 0.3 +
                recovery_factors["intensity_distribution"] * 0.3 +
                recovery_factors["rest_day_ratio"] * 0.2 +
                recovery_factors["heart_rate_trend"] * 0.2
            )
            
            return {
                "overall_recovery_score": round(overall_score, 1),
                "recovery_factors": recovery_factors,
                "recommendation": self._get_recovery_recommendation(overall_score)
            }
            
        except Exception as e:
            logger.error(f"Recovery score calculation failed: {e}")
            raise CalculationError(f"Recovery score calculation failed: {e}")
    
    def analyze_resting_heart_rate_trend(self, filter_criteria: AnalyticsFilter) -> AnalyticsResult:
        """靜息心率趨勢分析"""
        try:
            # 由於 FIT 文件通常不包含靜息心率，我們使用活動中的最低心率作為代理
            query_filter = self._build_query_filter(filter_criteria)
            
            agg_query = (AggregationQuery()
                        .add_date_histogram("daily_rhr", "timestamp", "day")
                        .add_metric("min_hr", "min", "avg_heart_rate"))
            
            results = self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
            
            # 提取趨勢數據
            rhr_trend = self._extract_rhr_trend_data(results)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.RECOVERY,
                data={
                    "resting_heart_rate_trend": rhr_trend,
                    "trend_analysis": self._analyze_rhr_trend(rhr_trend)
                },
                metadata={"analysis_type": "resting_heart_rate_trend"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"RHR trend analysis failed: {e}")
            raise CalculationError(f"RHR trend analysis failed: {e}")
    
    def estimate_recovery_time(self, activity_id: str) -> Optional[int]:
        """估算恢復時間（小時）"""
        try:
            # 獲取活動數據
            session_query = QueryFilter().add_term_filter("activity_id", activity_id)
            sessions = self.storage.search(DataType.SESSION, session_query)
            
            if not sessions:
                return None
            
            session = sessions[0]
            duration = session.get("total_timer_time", 0)  # 秒
            avg_hr = session.get("avg_heart_rate", 140)
            intensity = session.get("intensity", "moderate")
            
            # 簡化的恢復時間估算
            base_recovery = duration / 3600  # 基礎恢復時間（小時）
            
            # 強度係數
            intensity_factor = {
                "active": 0.5,
                "easy": 0.8,
                "moderate": 1.0,
                "hard": 1.5,
                "maximum": 2.0
            }.get(str(intensity).lower(), 1.0)
            
            # 心率係數
            hr_factor = max(0.5, min(2.0, avg_hr / 150.0))
            
            estimated_recovery = base_recovery * intensity_factor * hr_factor
            
            return max(6, min(72, int(estimated_recovery)))  # 6-72小時範圍
            
        except Exception as e:
            logger.warning(f"Recovery time estimation failed: {e}")
            return None
    
    # ComparisonAnalyzer 實現
    def compare_activities(self, activity_ids: List[str], metrics: List[str]) -> AnalyticsResult:
        """活動比較"""
        try:
            if len(activity_ids) < 2:
                raise InvalidParameterError("At least 2 activities required for comparison")
            
            query_filter = QueryFilter().add_terms_filter("activity_id", activity_ids)
            sessions = self.storage.search(DataType.SESSION, query_filter)
            
            if len(sessions) < 2:
                raise InsufficientDataError("Insufficient activity data for comparison")
            
            comparison_data = {}
            for session in sessions:
                activity_id = session.get("activity_id")
                comparison_data[activity_id] = {}
                
                for metric in metrics:
                    comparison_data[activity_id][metric] = session.get(metric)
            
            # 計算比較統計
            comparison_stats = self._calculate_comparison_statistics(comparison_data, metrics)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.COMPARISON,
                data={
                    "activities": comparison_data,
                    "comparison_statistics": comparison_stats,
                    "metrics_analyzed": metrics
                },
                metadata={"comparison_type": "activities"},
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Activity comparison failed: {e}")
            raise CalculationError(f"Activity comparison failed: {e}")
    
    def compare_time_periods(self, user_id: str, period1: TimeRange, 
                           period2: TimeRange, metrics: List[str]) -> AnalyticsResult:
        """時間段比較"""
        try:
            # 獲取兩個時間段的數據
            filter1 = AnalyticsFilter(user_id=user_id, time_range=period1)
            filter2 = AnalyticsFilter(user_id=user_id, time_range=period2)
            
            query1 = self._build_query_filter(filter1)
            query2 = self._build_query_filter(filter2)
            
            # 構建聚合查詢
            agg_query = AggregationQuery()
            for metric in metrics:
                metric_field_map = {
                    "distance": "total_distance",
                    "duration": "total_timer_time",
                    "heart_rate": "avg_heart_rate",
                    "speed": "enhanced_avg_speed",
                    "calories": "total_calories"
                }
                
                field = metric_field_map.get(metric, metric)
                agg_query.add_metric(f"avg_{metric}", "avg", field)
                agg_query.add_metric(f"sum_{metric}", "sum", field)
                agg_query.add_metric(f"count_{metric}", "value_count", field)
            
            period1_data = self.storage.aggregate(DataType.SESSION, query1, agg_query)
            period2_data = self.storage.aggregate(DataType.SESSION, query2, agg_query)
            
            # 計算比較結果
            comparison_results = self._compare_periods(period1_data, period2_data, metrics)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.COMPARISON,
                data={
                    "period1": period1_data,
                    "period2": period2_data,
                    "comparison": comparison_results
                },
                metadata={
                    "comparison_type": "time_periods",
                    "period1_range": period1.__dict__,
                    "period2_range": period2.__dict__
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Time period comparison failed: {e}")
            raise CalculationError(f"Time period comparison failed: {e}")
    
    def compare_users(self, user_ids: List[str], filter_criteria: AnalyticsFilter, 
                     metrics: List[str]) -> AnalyticsResult:
        """用戶比較（匿名化）"""
        try:
            if len(user_ids) < 2:
                raise InvalidParameterError("At least 2 users required for comparison")
            
            user_data = {}
            
            for i, user_id in enumerate(user_ids):
                # 匿名化用戶ID
                anonymous_id = f"User_{chr(65 + i)}"  # User_A, User_B, etc.
                
                user_filter = AnalyticsFilter(
                    user_id=user_id,
                    time_range=filter_criteria.time_range,
                    sport_types=filter_criteria.sport_types
                )
                
                query = self._build_query_filter(user_filter)
                
                agg_query = AggregationQuery()
                for metric in metrics:
                    field = self._get_field_name_for_metric(metric)
                    agg_query.add_metric(f"avg_{metric}", "avg", field)
                    agg_query.add_metric(f"total_{metric}", "sum", field)
                
                user_stats = self.storage.aggregate(DataType.SESSION, query, agg_query)
                user_data[anonymous_id] = user_stats
            
            # 計算用戶比較統計
            comparison_stats = self._calculate_user_comparison_stats(user_data, metrics)
            
            return AnalyticsResult(
                analytics_type=AnalyticsType.COMPARISON,
                data={
                    "users": user_data,
                    "comparison_statistics": comparison_stats
                },
                metadata={
                    "comparison_type": "users",
                    "user_count": len(user_ids),
                    "anonymized": True
                },
                generated_at=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"User comparison failed: {e}")
            raise CalculationError(f"User comparison failed: {e}")
    
    # CompositeAnalyzer 實現
    def generate_comprehensive_report(self, filter_criteria: AnalyticsFilter) -> Dict[str, AnalyticsResult]:
        """生成綜合分析報告"""
        try:
            report = {}
            
            # 基礎運動表現分析
            try:
                report["performance"] = self.analyze_performance(filter_criteria, AggregationLevel.WEEKLY)
            except Exception as e:
                logger.warning(f"Performance analysis failed in comprehensive report: {e}")
            
            # 心率分析
            try:
                report["heart_rate"] = self.analyze_heart_rate(filter_criteria)
            except Exception as e:
                logger.warning(f"Heart rate analysis failed in comprehensive report: {e}")
            
            # 訓練負荷分析
            try:
                report["training_load"] = self.analyze_training_load(filter_criteria, AggregationLevel.WEEKLY)
            except Exception as e:
                logger.warning(f"Training load analysis failed in comprehensive report: {e}")
            
            # 趨勢分析
            try:
                trend_metrics = ["distance", "speed", "heart_rate", "duration"]
                report["trends"] = self.analyze_trends(filter_criteria, trend_metrics, AggregationLevel.WEEKLY)
            except Exception as e:
                logger.warning(f"Trend analysis failed in comprehensive report: {e}")
            
            # 恢復分析
            try:
                report["recovery"] = self.analyze_resting_heart_rate_trend(filter_criteria)
            except Exception as e:
                logger.warning(f"Recovery analysis failed in comprehensive report: {e}")
            
            return report
            
        except Exception as e:
            logger.error(f"Comprehensive report generation failed: {e}")
            raise CalculationError(f"Comprehensive report generation failed: {e}")
    
    def get_personalized_insights(self, user_id: str, days: int = 30) -> List[Dict[str, Any]]:
        """個性化洞察"""
        try:
            insights = []
            
            filter_criteria = AnalyticsFilter(
                user_id=user_id,
                time_range=TimeRange(days=days)
            )
            
            # 活動頻率洞察
            performance_data = self.analyze_performance(filter_criteria, AggregationLevel.DAILY)
            if performance_data.data:
                activity_count = self._extract_activity_count(performance_data.data)
                if activity_count < days * 0.2:  # 少於20%的日子有運動
                    insights.append({
                        "type": "activity_frequency",
                        "level": "suggestion",
                        "message": "考慮增加運動頻率，建議每週至少運動3-4次以維持健康",
                        "data": {"current_frequency": activity_count, "target_frequency": days * 0.4}
                    })
            
            # 心率區間洞察
            hr_analysis = self.analyze_heart_rate(filter_criteria)
            if hr_analysis.data and "heart_rate_zones" in hr_analysis.data:
                # 分析心率區間分布並提供建議
                zone_insights = self._analyze_hr_zone_distribution(hr_analysis.data["heart_rate_zones"])
                insights.extend(zone_insights)
            
            # 恢復建議
            try:
                recovery_score = self.calculate_recovery_score(filter_criteria)
                if recovery_score["overall_recovery_score"] < 70:
                    insights.append({
                        "type": "recovery",
                        "level": "warning",
                        "message": "恢復評分較低，建議增加休息日或降低訓練強度",
                        "data": recovery_score
                    })
            except Exception:
                pass
            
            return insights
            
        except Exception as e:
            logger.error(f"Personalized insights generation failed: {e}")
            return []
    
    def detect_anomalies(self, filter_criteria: AnalyticsFilter) -> List[Dict[str, Any]]:
        """異常檢測"""
        try:
            anomalies = []
            
            # 獲取歷史數據
            query_filter = self._build_query_filter(filter_criteria)
            query_filter.add_sort("timestamp", ascending=False)
            query_filter.set_pagination(100)
            
            sessions = self.storage.search(DataType.SESSION, query_filter)
            
            if len(sessions) < 10:
                return anomalies  # 數據不足以進行異常檢測
            
            # 檢測異常的運動時長
            durations = [s.get("total_timer_time", 0) for s in sessions if s.get("total_timer_time")]
            duration_anomalies = self._detect_statistical_anomalies(durations, "duration")
            anomalies.extend(duration_anomalies)
            
            # 檢測異常的心率
            heart_rates = [s.get("avg_heart_rate", 0) for s in sessions if s.get("avg_heart_rate")]
            hr_anomalies = self._detect_statistical_anomalies(heart_rates, "heart_rate")
            anomalies.extend(hr_anomalies)
            
            # 檢測異常的距離
            distances = [s.get("total_distance", 0) for s in sessions if s.get("total_distance")]
            distance_anomalies = self._detect_statistical_anomalies(distances, "distance")
            anomalies.extend(distance_anomalies)
            
            return anomalies
            
        except Exception as e:
            logger.error(f"Anomaly detection failed: {e}")
            return []
