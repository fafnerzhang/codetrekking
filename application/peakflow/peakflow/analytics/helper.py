#!/usr/bin/env python3
"""
Elasticsearch Analytics Helper Methods - Auxiliary calculation methods
"""
from typing import Dict, List, Any, Optional
import numpy as np
from datetime import datetime, timedelta
from ..storage import QueryFilter, AggregationQuery, DataType
from ..utils import get_logger

logger = get_logger(__name__)


class AnalyticsHelperMethods:
    """Analytics helper methods class"""
    
    def _calculate_heart_rate_zones_for_activity(self, activity_id: str) -> Dict[str, Any]:
        """Calculate heart rate zones for a single activity"""
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_exists_filter("heart_rate")
                       .add_sort("timestamp", ascending=True)
                       .set_pagination(10000))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        
        if not records:
            return {}
        
        hr_zones = {}
        total_time = 0
        
        for zone_name, (min_hr, max_hr) in self.thresholds.heart_rate_zones.items():
            zone_time = 0
            for record in records:
                hr = record.get("heart_rate")
                if hr and min_hr <= hr < max_hr:
                    zone_time += 1  # 假設每筆記錄為1秒
            
            hr_zones[zone_name] = {
                "min_hr": min_hr,
                "max_hr": max_hr,
                "time_seconds": zone_time,
                "percentage": 0.0
            }
            total_time += zone_time
        
        # 計算百分比
        if total_time > 0:
            for zone_data in hr_zones.values():
                zone_data["percentage"] = round((zone_data["time_seconds"] / total_time) * 100, 1)
        
        return {
            "zones": hr_zones,
            "total_time_seconds": total_time,
            "analysis_date": datetime.now().isoformat()
        }
    
    def _calculate_heart_rate_zones_for_user(self, user_id: str, time_range: Optional[TimeRange]) -> Dict[str, Any]:
        """計算用戶的心率區間統計"""
        query_filter = QueryFilter().add_term_filter("user_id", user_id)
        
        if time_range:
            start_date, end_date = time_range.to_dates()
            if start_date or end_date:
                query_filter.add_date_range("timestamp", start=start_date, end=end_date)
        
        # 使用 Session 級別的心率統計
        agg_query = (AggregationQuery()
                    .add_metric("avg_hr", "avg", "avg_heart_rate")
                    .add_metric("max_hr", "max", "max_heart_rate")
                    .add_metric("min_hr", "min", "avg_heart_rate")
                    .add_histogram("hr_distribution", "avg_heart_rate", 5))
        
        return self.storage.aggregate(DataType.SESSION, query_filter, agg_query)
    
    def _calculate_training_load_metrics(self, timeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """計算訓練負荷指標"""
        metrics = {
            "total_training_time": 0,
            "average_weekly_load": 0,
            "load_progression": [],
            "intensity_distribution": {},
            "recovery_ratio": 0.0
        }
        
        try:
            # 從時間線數據計算訓練負荷
            if "aggregations" in timeline_data and "training_load_timeline" in timeline_data["aggregations"]:
                buckets = timeline_data["aggregations"]["training_load_timeline"]["buckets"]
                
                weekly_loads = []
                for bucket in buckets:
                    duration = bucket.get("total_duration", {}).get("value", 0)
                    intensity = bucket.get("avg_intensity", {}).get("value", 0)
                    
                    # 簡單的訓練負荷計算：時間 * 強度係數
                    load = duration * (intensity / 150.0) if intensity > 0 else duration * 0.5
                    weekly_loads.append(load)
                
                metrics["load_progression"] = weekly_loads
                metrics["average_weekly_load"] = np.mean(weekly_loads) if weekly_loads else 0
                metrics["total_training_time"] = sum(bucket.get("total_duration", {}).get("value", 0) for bucket in buckets)
        
        except Exception as e:
            logger.warning(f"Training load calculation partial failure: {e}")
        
        return metrics
    
    def _calculate_trend_statistics(self, timeline_data: Dict[str, Any], metrics: List[str]) -> Dict[str, Any]:
        """計算趨勢統計"""
        trend_stats = {}
        
        try:
            if "aggregations" in timeline_data and "timeline" in timeline_data["aggregations"]:
                buckets = timeline_data["aggregations"]["timeline"]["buckets"]
                
                for metric in metrics:
                    metric_key = f"trend_{metric}"
                    values = []
                    
                    for bucket in buckets:
                        if metric_key in bucket and "value" in bucket[metric_key]:
                            values.append(bucket[metric_key]["value"])
                    
                    if len(values) >= 2:
                        # 計算線性趨勢
                        x = np.arange(len(values))
                        slope, intercept = np.polyfit(x, values, 1)
                        
                        trend_stats[metric] = {
                            "values": values,
                            "trend_slope": slope,
                            "trend_direction": "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable",
                            "improvement_rate": slope / np.mean(values) * 100 if np.mean(values) != 0 else 0,
                            "r_squared": np.corrcoef(x, values)[0, 1] ** 2 if len(values) > 1 else 0
                        }
        
        except Exception as e:
            logger.warning(f"Trend statistics calculation failed: {e}")
        
        return trend_stats
    
    def _calculate_power_distribution(self, power_values: List[float]) -> Dict[str, Any]:
        """計算功率分布"""
        power_array = np.array(power_values)
        
        return {
            "mean_power": float(np.mean(power_array)),
            "max_power": float(np.max(power_array)),
            "percentiles": {
                "p25": float(np.percentile(power_array, 25)),
                "p50": float(np.percentile(power_array, 50)),
                "p75": float(np.percentile(power_array, 75)),
                "p90": float(np.percentile(power_array, 90)),
                "p95": float(np.percentile(power_array, 95))
            },
            "histogram": self._create_power_histogram(power_array),
            "critical_power_curve": self._calculate_critical_power_curve(power_values)
        }
    
    def _create_power_histogram(self, power_array: np.ndarray, bins: int = 20) -> Dict[str, Any]:
        """創建功率直方圖"""
        hist, bin_edges = np.histogram(power_array, bins=bins)
        
        return {
            "bins": bins,
            "counts": hist.tolist(),
            "bin_edges": bin_edges.tolist()
        }
    
    def _calculate_critical_power_curve(self, power_values: List[float]) -> Dict[str, float]:
        """計算臨界功率曲線"""
        # 簡化版本，計算不同時間段的最大平均功率
        durations = [5, 10, 30, 60, 300, 600, 1200, 3600]  # 秒
        cp_curve = {}
        
        for duration in durations:
            if len(power_values) >= duration:
                max_avg = 0
                for i in range(len(power_values) - duration + 1):
                    window_avg = np.mean(power_values[i:i+duration])
                    max_avg = max(max_avg, window_avg)
                cp_curve[f"{duration}s"] = max_avg
        
        return cp_curve
    
    def _calculate_20min_max_power(self, activity_id: str) -> Optional[float]:
        """計算20分鐘最大平均功率"""
        query_filter = (QueryFilter()
                       .add_term_filter("activity_id", activity_id)
                       .add_exists_filter("power_data.power")
                       .add_sort("timestamp", ascending=True))
        
        records = self.storage.search(DataType.RECORD, query_filter)
        
        if not records:
            return None
        
        power_values = [r.get("power_data", {}).get("power", 0) for r in records]
        power_values = [p for p in power_values if p > 0]
        
        if len(power_values) < 1200:  # 需要至少20分鐘的數據
            return None
        
        # 計算20分鐘滑動窗口的最大平均功率
        window_size = 1200  # 20分鐘 = 1200秒
        max_20min_power = 0
        
        for i in range(len(power_values) - window_size + 1):
            window_avg = np.mean(power_values[i:i+window_size])
            max_20min_power = max(max_20min_power, window_avg)
        
        return max_20min_power
    
    def _calculate_power_zone_distribution(self, filter_criteria: AnalyticsFilter, 
                                         power_zones: Dict[str, tuple]) -> Dict[str, Any]:
        """計算功率區間分布"""
        query_filter = self._build_query_filter(filter_criteria)
        query_filter.add_exists_filter("power_data.power")
        
        records = self.storage.search(DataType.RECORD, query_filter)
        
        zone_distribution = {}
        total_time = 0
        
        for zone_name, (min_power, max_power) in power_zones.items():
            zone_time = 0
            for record in records:
                power = record.get("power_data", {}).get("power", 0)
                if power and min_power <= power < max_power:
                    zone_time += 1
            
            zone_distribution[zone_name] = {
                "time_seconds": zone_time,
                "percentage": 0.0,
                "power_range": (min_power, max_power)
            }
            total_time += zone_time
        
        # 計算百分比
        if total_time > 0:
            for zone_data in zone_distribution.values():
                zone_data["percentage"] = round((zone_data["time_seconds"] / total_time) * 100, 1)
        
        return zone_distribution
    
    def _analyze_cadence_patterns(self, filter_criteria: AnalyticsFilter) -> Dict[str, Any]:
        """分析步頻模式"""
        query_filter = self._build_query_filter(filter_criteria)
        query_filter.add_exists_filter("cadence")
        
        records = self.storage.search(DataType.RECORD, query_filter)
        
        if not records:
            return {}
        
        cadence_values = [r.get("cadence", 0) for r in records if r.get("cadence")]
        
        if not cadence_values:
            return {}
        
        cadence_array = np.array(cadence_values)
        
        return {
            "average_cadence": float(np.mean(cadence_array)),
            "median_cadence": float(np.median(cadence_array)),
            "cadence_variability": float(np.std(cadence_array)),
            "optimal_range_percentage": self._calculate_optimal_cadence_percentage(cadence_array),
            "cadence_trends": self._analyze_cadence_trends(cadence_values)
        }
    
    def _calculate_optimal_cadence_percentage(self, cadence_array: np.ndarray) -> float:
        """計算最佳步頻範圍的百分比"""
        # 最佳跑步步頻通常在170-190 spm
        optimal_range = (cadence_array >= 170) & (cadence_array <= 190)
        return float(np.sum(optimal_range) / len(cadence_array) * 100)
    
    def _analyze_cadence_trends(self, cadence_values: List[float]) -> Dict[str, Any]:
        """分析步頻趨勢"""
        if len(cadence_values) < 10:
            return {}
        
        # 將數據分成10個區段分析趨勢
        segments = np.array_split(cadence_values, min(10, len(cadence_values)))
        segment_averages = [np.mean(segment) for segment in segments]
        
        # 計算趨勢
        x = np.arange(len(segment_averages))
        slope, intercept = np.polyfit(x, segment_averages, 1)
        
        return {
            "trend_slope": slope,
            "trend_direction": "increasing" if slope > 0.5 else "decreasing" if slope < -0.5 else "stable",
            "segment_averages": segment_averages
        }
    
    def _analyze_stride_metrics(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析步幅指標"""
        stride_lengths = []
        vertical_oscillations = []
        stance_times = []
        
        for record in records:
            rd = record.get("running_dynamics", {})
            if "step_length" in rd:
                stride_lengths.append(rd["step_length"])
            if "vertical_oscillation" in rd:
                vertical_oscillations.append(rd["vertical_oscillation"])
            if "stance_time" in rd:
                stance_times.append(rd["stance_time"])
        
        analysis = {}
        
        if stride_lengths:
            sl_array = np.array(stride_lengths)
            analysis["stride_length"] = {
                "average": float(np.mean(sl_array)),
                "median": float(np.median(sl_array)),
                "variability": float(np.std(sl_array)),
                "range": (float(np.min(sl_array)), float(np.max(sl_array)))
            }
        
        if vertical_oscillations:
            vo_array = np.array(vertical_oscillations)
            analysis["vertical_oscillation"] = {
                "average": float(np.mean(vo_array)),
                "median": float(np.median(vo_array)),
                "variability": float(np.std(vo_array)),
                "efficiency_score": self._calculate_vo_efficiency_score(vo_array)
            }
        
        if stance_times:
            st_array = np.array(stance_times)
            analysis["stance_time"] = {
                "average": float(np.mean(st_array)),
                "median": float(np.median(st_array)),
                "variability": float(np.std(st_array)),
                "balance_score": self._calculate_stance_balance_score(st_array)
            }
        
        return analysis
    
    def _calculate_vo_efficiency_score(self, vo_array: np.ndarray) -> float:
        """計算垂直振幅效率分數"""
        # 較低的垂直振幅通常表示更好的跑步效率
        avg_vo = np.mean(vo_array)
        
        # 基於典型範圍 (6-13 cm) 計算效率分數
        if avg_vo <= 7:
            return 10.0  # 優秀
        elif avg_vo <= 9:
            return 8.0   # 良好
        elif avg_vo <= 11:
            return 6.0   # 中等
        elif avg_vo <= 13:
            return 4.0   # 需要改善
        else:
            return 2.0   # 差
    
    def _calculate_stance_balance_score(self, st_array: np.ndarray) -> float:
        """計算著地時間平衡分數"""
        # 一致的著地時間表示更好的跑步技術
        variability = np.std(st_array) / np.mean(st_array) * 100  # 變異係數
        
        if variability <= 5:
            return 10.0
        elif variability <= 10:
            return 8.0
        elif variability <= 15:
            return 6.0
        elif variability <= 20:
            return 4.0
        else:
            return 2.0
    
    def _analyze_vertical_oscillation(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析垂直振幅"""
        vo_values = []
        
        for record in records:
            rd = record.get("running_dynamics", {})
            if "vertical_oscillation" in rd:
                vo_values.append(rd["vertical_oscillation"])
        
        if not vo_values:
            return {}
        
        vo_array = np.array(vo_values)
        
        return {
            "average_vo": float(np.mean(vo_array)),
            "median_vo": float(np.median(vo_array)),
            "vo_variability": float(np.std(vo_array)),
            "efficiency_score": self._calculate_vo_efficiency_score(vo_array),
            "optimal_range_percentage": float(np.sum((vo_array >= 6) & (vo_array <= 10)) / len(vo_array) * 100),
            "distribution": {
                "excellent": float(np.sum(vo_array <= 7) / len(vo_array) * 100),
                "good": float(np.sum((vo_array > 7) & (vo_array <= 9)) / len(vo_array) * 100),
                "average": float(np.sum((vo_array > 9) & (vo_array <= 11)) / len(vo_array) * 100),
                "needs_improvement": float(np.sum(vo_array > 11) / len(vo_array) * 100)
            }
        }
    
    def _analyze_ground_contact_time(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析著地時間"""
        gct_values = []
        
        for record in records:
            rd = record.get("running_dynamics", {})
            if "stance_time" in rd:
                gct_values.append(rd["stance_time"])
        
        if not gct_values:
            return {}
        
        gct_array = np.array(gct_values)
        
        return {
            "average_gct": float(np.mean(gct_array)),
            "median_gct": float(np.median(gct_array)),
            "gct_variability": float(np.std(gct_array)),
            "balance_score": self._calculate_stance_balance_score(gct_array),
            "optimal_range_percentage": float(np.sum((gct_array >= 150) & (gct_array <= 250)) / len(gct_array) * 100),
            "asymmetry_analysis": self._analyze_gct_asymmetry(gct_values)
        }
    
    def _analyze_gct_asymmetry(self, gct_values: List[float]) -> Dict[str, Any]:
        """分析著地時間不對稱性"""
        if len(gct_values) < 20:
            return {"insufficient_data": True}
        
        # 簡化的不對稱性分析
        left_foot_values = gct_values[::2]  # 假設偶數索引為左腳
        right_foot_values = gct_values[1::2]  # 假設奇數索引為右腳
        
        if len(left_foot_values) < 10 or len(right_foot_values) < 10:
            return {"insufficient_data": True}
        
        left_avg = np.mean(left_foot_values)
        right_avg = np.mean(right_foot_values)
        asymmetry_percentage = abs(left_avg - right_avg) / ((left_avg + right_avg) / 2) * 100
        
        return {
            "left_foot_avg": float(left_avg),
            "right_foot_avg": float(right_avg),
            "asymmetry_percentage": float(asymmetry_percentage),
            "asymmetry_level": "low" if asymmetry_percentage < 5 else "moderate" if asymmetry_percentage < 10 else "high"
        }
    
    # 路線分析輔助方法
    def _calculate_route_efficiency(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """計算路線效率"""
        if len(records) < 2:
            return {"error": "Insufficient GPS data"}
        
        # 計算總距離和直線距離
        total_distance = 0
        gps_points = []
        
        for record in records:
            location = record.get("location")
            if location and location.get("lat") and location.get("lon"):
                gps_points.append((location["lat"], location["lon"]))
        
        if len(gps_points) < 2:
            return {"error": "Insufficient GPS points"}
        
        # 計算累積距離
        for i in range(1, len(gps_points)):
            dist = self._calculate_distance_between_points(gps_points[i-1], gps_points[i])
            total_distance += dist
        
        # 計算直線距離
        straight_distance = self._calculate_distance_between_points(gps_points[0], gps_points[-1])
        
        # 效率指標
        efficiency_ratio = straight_distance / total_distance if total_distance > 0 else 0
        
        return {
            "total_distance": total_distance,
            "straight_line_distance": straight_distance,
            "efficiency_ratio": efficiency_ratio,
            "route_type": "out_and_back" if efficiency_ratio < 0.3 else "loop" if efficiency_ratio < 0.7 else "point_to_point"
        }
    
    def _calculate_distance_between_points(self, point1: tuple, point2: tuple) -> float:
        """計算兩點間距離（使用 Haversine 公式）"""
        import math
        
        lat1, lon1 = math.radians(point1[0]), math.radians(point1[1])
        lat2, lon2 = math.radians(point2[0]), math.radians(point2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # 地球半徑（公里）
        r = 6371
        
        return c * r * 1000  # 返回米
    
    def _detect_climb_segments(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """檢測爬坡路段"""
        segments = []
        current_segment = None
        climb_threshold = 10  # 最小爬升高度（米）
        
        for i, record in enumerate(records):
            altitude = record.get("altitude")
            if altitude is None:
                continue
            
            if i == 0:
                start_altitude = altitude
                continue
            
            prev_altitude = records[i-1].get("altitude", altitude)
            elevation_gain = altitude - prev_altitude
            
            if elevation_gain > 1:  # 開始爬坡
                if current_segment is None:
                    current_segment = {
                        "type": "climb",
                        "start_index": i-1,
                        "start_altitude": prev_altitude,
                        "start_time": records[i-1].get("timestamp"),
                        "total_gain": 0
                    }
                current_segment["total_gain"] += elevation_gain
            else:
                if current_segment and current_segment["total_gain"] >= climb_threshold:
                    current_segment.update({
                        "end_index": i-1,
                        "end_altitude": prev_altitude,
                        "end_time": records[i-1].get("timestamp"),
                        "distance": self._calculate_segment_distance(records, current_segment["start_index"], i-1)
                    })
                    segments.append(current_segment)
                current_segment = None
        
        return segments
    
    def _detect_descent_segments(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """檢測下坡路段"""
        segments = []
        current_segment = None
        descent_threshold = 10  # 最小下降高度（米）
        
        for i, record in enumerate(records):
            altitude = record.get("altitude")
            if altitude is None:
                continue
            
            if i == 0:
                continue
            
            prev_altitude = records[i-1].get("altitude", altitude)
            elevation_loss = prev_altitude - altitude
            
            if elevation_loss > 1:  # 開始下坡
                if current_segment is None:
                    current_segment = {
                        "type": "descent",
                        "start_index": i-1,
                        "start_altitude": prev_altitude,
                        "start_time": records[i-1].get("timestamp"),
                        "total_loss": 0
                    }
                current_segment["total_loss"] += elevation_loss
            else:
                if current_segment and current_segment["total_loss"] >= descent_threshold:
                    current_segment.update({
                        "end_index": i-1,
                        "end_altitude": prev_altitude,
                        "end_time": records[i-1].get("timestamp"),
                        "distance": self._calculate_segment_distance(records, current_segment["start_index"], i-1)
                    })
                    segments.append(current_segment)
                current_segment = None
        
        return segments
    
    def _detect_flat_segments(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """檢測平路路段"""
        segments = []
        current_segment = None
        flat_threshold = 2  # 高度變化閾值（米）
        min_distance = 500  # 最小平路距離（米）
        
        for i, record in enumerate(records):
            altitude = record.get("altitude")
            if altitude is None or i == 0:
                continue
            
            prev_altitude = records[i-1].get("altitude", altitude)
            elevation_change = abs(altitude - prev_altitude)
            
            if elevation_change <= flat_threshold:  # 平路
                if current_segment is None:
                    current_segment = {
                        "type": "flat",
                        "start_index": i-1,
                        "start_altitude": prev_altitude,
                        "start_time": records[i-1].get("timestamp"),
                        "avg_altitude": prev_altitude,
                        "altitude_sum": prev_altitude,
                        "count": 1
                    }
                else:
                    current_segment["altitude_sum"] += altitude
                    current_segment["count"] += 1
                    current_segment["avg_altitude"] = current_segment["altitude_sum"] / current_segment["count"]
            else:
                if current_segment:
                    distance = self._calculate_segment_distance(records, current_segment["start_index"], i-1)
                    if distance >= min_distance:
                        current_segment.update({
                            "end_index": i-1,
                            "end_altitude": prev_altitude,
                            "end_time": records[i-1].get("timestamp"),
                            "distance": distance
                        })
                        segments.append(current_segment)
                current_segment = None
        
        return segments
    
    def _calculate_segment_distance(self, records: List[Dict[str, Any]], start_idx: int, end_idx: int) -> float:
        """計算路段距離"""
        distance = 0
        for i in range(start_idx + 1, min(end_idx + 1, len(records))):
            if records[i].get("location") and records[i-1].get("location"):
                loc1 = records[i-1]["location"]
                loc2 = records[i]["location"]
                if all([loc1.get("lat"), loc1.get("lon"), loc2.get("lat"), loc2.get("lon")]):
                    dist = self._calculate_distance_between_points(
                        (loc1["lat"], loc1["lon"]),
                        (loc2["lat"], loc2["lon"])
                    )
                    distance += dist
        return distance
    
    def _calculate_elevation_profile(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """計算高度剖面"""
        altitudes = [r.get("altitude") for r in records if r.get("altitude") is not None]
        
        if not altitudes:
            return {"error": "No altitude data"}
        
        min_altitude = min(altitudes)
        max_altitude = max(altitudes)
        total_ascent = 0
        total_descent = 0
        
        for i in range(1, len(altitudes)):
            elevation_change = altitudes[i] - altitudes[i-1]
            if elevation_change > 0:
                total_ascent += elevation_change
            else:
                total_descent += abs(elevation_change)
        
        return {
            "min_altitude": min_altitude,
            "max_altitude": max_altitude,
            "elevation_range": max_altitude - min_altitude,
            "total_ascent": total_ascent,
            "total_descent": total_descent,
            "average_altitude": sum(altitudes) / len(altitudes),
            "altitude_profile": self._create_altitude_profile(altitudes)
        }
    
    def _create_altitude_profile(self, altitudes: List[float], buckets: int = 50) -> List[Dict[str, Any]]:
        """創建高度剖面圖數據"""
        if len(altitudes) <= buckets:
            return [{"index": i, "altitude": alt} for i, alt in enumerate(altitudes)]
        
        # 重新採樣到指定的桶數
        step = len(altitudes) / buckets
        profile = []
        
        for i in range(buckets):
            idx = int(i * step)
            if idx < len(altitudes):
                profile.append({
                    "index": i,
                    "altitude": altitudes[idx],
                    "progress_percentage": (i / buckets) * 100
                })
        
        return profile
    
    # 恢復分析輔助方法
    def _calculate_training_load_balance(self, sessions: List[Dict[str, Any]]) -> float:
        """計算訓練負荷平衡性評分"""
        if len(sessions) < 5:
            return 50.0  # 數據不足，返回中等評分
        
        # 計算每日訓練負荷
        daily_loads = []
        for session in sessions:
            duration = session.get("total_timer_time", 0) / 3600  # 小時
            intensity = session.get("avg_heart_rate", 140) / 150.0  # 標準化強度
            load = duration * intensity
            daily_loads.append(load)
        
        # 計算負荷變異性
        if len(daily_loads) > 1:
            avg_load = np.mean(daily_loads)
            load_variability = np.std(daily_loads) / avg_load if avg_load > 0 else 1.0
            
            # 適度的變異性是好的，但過度變異性不好
            balance_score = max(0, 100 - (load_variability * 100))
            return min(100, balance_score)
        
        return 50.0
    
    def _calculate_intensity_distribution(self, sessions: List[Dict[str, Any]]) -> float:
        """計算強度分布評分"""
        intensities = []
        for session in sessions:
            intensity = session.get("intensity", "moderate")
            intensities.append(str(intensity).lower())
        
        if not intensities:
            return 50.0
        
        # 理想的強度分布：80% 輕鬆，20% 高強度
        easy_count = intensities.count("easy") + intensities.count("active")
        hard_count = intensities.count("hard") + intensities.count("maximum")
        moderate_count = len(intensities) - easy_count - hard_count
        
        total = len(intensities)
        easy_ratio = easy_count / total
        hard_ratio = hard_count / total
        
        # 評估與理想分布的接近度
        ideal_easy = 0.8
        ideal_hard = 0.2
        
        distribution_score = 100 - (abs(easy_ratio - ideal_easy) + abs(hard_ratio - ideal_hard)) * 100
        return max(0, min(100, distribution_score))
    
    def _calculate_rest_day_ratio(self, sessions: List[Dict[str, Any]]) -> float:
        """計算休息日比例評分"""
        if len(sessions) < 7:
            return 70.0  # 數據不足，返回較好評分
        
        # 計算最近7天的運動天數
        recent_days = 7
        activity_days = min(recent_days, len(sessions))
        rest_days = recent_days - activity_days
        
        # 理想的休息比例約為2-3天/週
        ideal_rest_ratio = 2/7
        actual_rest_ratio = rest_days / recent_days
        
        # 計算評分
        ratio_difference = abs(actual_rest_ratio - ideal_rest_ratio)
        rest_score = 100 - (ratio_difference * 200)  # 放大差異
        
        return max(0, min(100, rest_score))
    
    def _calculate_hr_recovery_trend(self, sessions: List[Dict[str, Any]]) -> float:
        """計算心率恢復趨勢評分"""
        heart_rates = [s.get("avg_heart_rate") for s in sessions if s.get("avg_heart_rate")]
        
        if len(heart_rates) < 5:
            return 60.0  # 數據不足
        
        # 計算心率趨勢（下降趨勢表示更好的恢復）
        x = np.arange(len(heart_rates))
        slope, _ = np.polyfit(x, heart_rates, 1)
        
        # 輕微下降趨勢是理想的
        if slope < -1:  # 心率明顯下降
            return 90.0
        elif slope < 0:  # 心率輕微下降
            return 80.0
        elif slope < 1:  # 心率穩定
            return 70.0
        else:  # 心率上升
            return max(30.0, 70 - (slope * 10))
    
    def _get_recovery_recommendation(self, score: float) -> str:
        """根據恢復評分提供建議"""
        if score >= 80:
            return "恢復狀況良好，可以維持當前訓練強度"
        elif score >= 60:
            return "恢復狀況尚可，注意訓練與休息的平衡"
        elif score >= 40:
            return "恢復狀況需要改善，建議增加休息日或降低訓練強度"
        else:
            return "恢復狀況較差，建議暫時減少訓練強度並增加休息時間"
    
    # 趨勢分析輔助方法
    def _extract_rhr_trend_data(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取靜息心率趨勢數據"""
        trend_data = []
        
        if "aggregations" in results and "daily_rhr" in results["aggregations"]:
            buckets = results["aggregations"]["daily_rhr"]["buckets"]
            
            for bucket in buckets:
                date = bucket.get("key_as_string", bucket.get("key"))
                min_hr = bucket.get("min_hr", {}).get("value")
                
                if min_hr:
                    trend_data.append({
                        "date": date,
                        "resting_heart_rate": min_hr
                    })
        
        return trend_data
    
    def _analyze_rhr_trend(self, rhr_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析靜息心率趨勢"""
        if len(rhr_data) < 7:
            return {"trend": "insufficient_data"}
        
        values = [d["resting_heart_rate"] for d in rhr_data]
        x = np.arange(len(values))
        slope, _ = np.polyfit(x, values, 1)
        
        trend_analysis = {
            "slope": slope,
            "average_rhr": np.mean(values),
            "rhr_range": (min(values), max(values)),
            "trend_direction": "decreasing" if slope < -0.5 else "increasing" if slope > 0.5 else "stable"
        }
        
        # 添加健康評估
        avg_rhr = trend_analysis["average_rhr"]
        if avg_rhr < 60:
            trend_analysis["fitness_level"] = "excellent"
        elif avg_rhr < 70:
            trend_analysis["fitness_level"] = "good"
        elif avg_rhr < 80:
            trend_analysis["fitness_level"] = "average"
        else:
            trend_analysis["fitness_level"] = "needs_improvement"
        
        return trend_analysis
    
    # 比較分析輔助方法
    def _calculate_comparison_statistics(self, comparison_data: Dict[str, Dict[str, Any]], 
                                       metrics: List[str]) -> Dict[str, Any]:
        """計算比較統計"""
        stats = {}
        
        for metric in metrics:
            values = []
            for activity_data in comparison_data.values():
                value = activity_data.get(metric)
                if value is not None:
                    values.append(value)
            
            if values:
                stats[metric] = {
                    "min": min(values),
                    "max": max(values),
                    "average": sum(values) / len(values),
                    "range": max(values) - min(values),
                    "improvement_potential": (max(values) - min(values)) / max(values) * 100 if max(values) > 0 else 0
                }
        
        return stats
    
    def _compare_periods(self, period1_data: Dict[str, Any], period2_data: Dict[str, Any], 
                        metrics: List[str]) -> Dict[str, Any]:
        """比較兩個時間段的數據"""
        comparison = {}
        
        for metric in metrics:
            p1_avg = period1_data.get("aggregations", {}).get(f"avg_{metric}", {}).get("value", 0)
            p2_avg = period2_data.get("aggregations", {}).get(f"avg_{metric}", {}).get("value", 0)
            
            if p1_avg > 0:
                change_percentage = ((p2_avg - p1_avg) / p1_avg) * 100
            else:
                change_percentage = 0
            
            comparison[metric] = {
                "period1_avg": p1_avg,
                "period2_avg": p2_avg,
                "absolute_change": p2_avg - p1_avg,
                "percentage_change": change_percentage,
                "improvement": change_percentage > 0
            }
        
        return comparison
    
    def _calculate_user_comparison_stats(self, user_data: Dict[str, Dict[str, Any]], 
                                       metrics: List[str]) -> Dict[str, Any]:
        """計算用戶比較統計"""
        stats = {}
        
        for metric in metrics:
            values = []
            for user_stats in user_data.values():
                avg_value = user_stats.get("aggregations", {}).get(f"avg_{metric}", {}).get("value")
                if avg_value:
                    values.append(avg_value)
            
            if values:
                stats[metric] = {
                    "group_average": sum(values) / len(values),
                    "best_performance": max(values),
                    "performance_range": max(values) - min(values),
                    "performance_distribution": self._calculate_percentiles(values)
                }
        
        return stats
    
    def _calculate_percentiles(self, values: List[float]) -> Dict[str, float]:
        """計算百分位數"""
        return {
            "p25": float(np.percentile(values, 25)),
            "p50": float(np.percentile(values, 50)),
            "p75": float(np.percentile(values, 75)),
            "p90": float(np.percentile(values, 90))
        }
    
    def _get_field_name_for_metric(self, metric: str) -> str:
        """獲取指標對應的字段名"""
        field_mapping = {
            "distance": "total_distance",
            "duration": "total_timer_time",
            "heart_rate": "avg_heart_rate",
            "speed": "enhanced_avg_speed",
            "calories": "total_calories"
        }
        return field_mapping.get(metric, metric)
    
    # 洞察生成輔助方法
    def _extract_activity_count(self, performance_data: Dict[str, Any]) -> int:
        """從性能數據中提取活動計數"""
        if "aggregations" in performance_data:
            activity_count = performance_data["aggregations"].get("activity_count", {}).get("value", 0)
            return int(activity_count)
        return 0
    
    def _analyze_hr_zone_distribution(self, hr_zones_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """分析心率區間分布並生成洞察"""
        insights = []
        
        if "zones" in hr_zones_data:
            zones = hr_zones_data["zones"]
            
            # 檢查是否有足夠的低強度訓練
            zone1_percentage = zones.get("zone_1", {}).get("percentage", 0)
            zone2_percentage = zones.get("zone_2", {}).get("percentage", 0)
            low_intensity_total = zone1_percentage + zone2_percentage
            
            if low_intensity_total < 70:
                insights.append({
                    "type": "heart_rate_zones",
                    "level": "suggestion",
                    "message": f"低強度訓練比例較低（{low_intensity_total:.1f}%），建議增加輕鬆跑或恢復訓練",
                    "data": {"current_low_intensity": low_intensity_total, "recommended_minimum": 70}
                })
            
            # 檢查高強度訓練
            zone4_percentage = zones.get("zone_4", {}).get("percentage", 0)
            zone5_percentage = zones.get("zone_5", {}).get("percentage", 0)
            high_intensity_total = zone4_percentage + zone5_percentage
            
            if high_intensity_total > 20:
                insights.append({
                    "type": "heart_rate_zones",
                    "level": "warning",
                    "message": f"高強度訓練比例過高（{high_intensity_total:.1f}%），注意避免過度訓練",
                    "data": {"current_high_intensity": high_intensity_total, "recommended_maximum": 20}
                })
        
        return insights
    
    # 異常檢測輔助方法
    def _detect_statistical_anomalies(self, values: List[float], metric_name: str) -> List[Dict[str, Any]]:
        """使用統計方法檢測異常值"""
        if len(values) < 10:
            return []
        
        anomalies = []
        values_array = np.array(values)
        
        # 使用 Z-score 方法檢測異常
        mean_val = np.mean(values_array)
        std_val = np.std(values_array)
        
        if std_val > 0:
            z_scores = np.abs((values_array - mean_val) / std_val)
            
            # Z-score > 2.5 被認為是異常
            anomaly_indices = np.where(z_scores > 2.5)[0]
            
            for idx in anomaly_indices:
                anomalies.append({
                    "metric": metric_name,
                    "value": values[idx],
                    "z_score": z_scores[idx],
                    "severity": "high" if z_scores[idx] > 3 else "medium",
                    "message": f"異常的{metric_name}值: {values[idx]:.2f}，Z-score: {z_scores[idx]:.2f}"
                })
        
        return anomalies
