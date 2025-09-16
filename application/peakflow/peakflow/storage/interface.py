#!/usr/bin/env python3
"""
Storage Layer Abstract Interface - Separates business logic from storage implementation
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum


class DataType(Enum):
    """Data type enumeration"""

    SESSION = "session"
    RECORD = "record"
    LAP = "lap"
    USER_INDICATOR = "user_indicator"  # Added for user personal metrics
    WELLNESS = "wellness"  # Health wellness data
    SLEEP_DATA = "sleep_data"  # Sleep tracking data
    HRV_STATUS = "hrv_status"  # Heart rate variability data
    METRICS = "metrics"  # Health metrics data


class QueryFilter:
    """Query filter"""

    def __init__(self):
        self.filters = {}
        self.date_range = {}
        self.geo_bounds = {}
        self.sort_fields = []
        self.limit = 1000
        self.offset = 0

    def add_term_filter(self, field: str, value: Any) -> "QueryFilter":
        """Add exact match filter"""
        self.filters[field] = value
        return self

    def add_date_range(
        self, field: str, start: datetime = None, end: datetime = None
    ) -> "QueryFilter":
        """Add date range filter"""
        self.date_range[field] = {"start": start, "end": end}
        return self

    def add_geo_bounds(self, top_left: tuple, bottom_right: tuple) -> "QueryFilter":
        """添加地理邊界過濾器"""
        self.geo_bounds = {
            "top_left": {"lat": top_left[0], "lon": top_left[1]},
            "bottom_right": {"lat": bottom_right[0], "lon": bottom_right[1]},
        }
        return self

    def add_sort(self, field: str, ascending: bool = True) -> "QueryFilter":
        """添加排序"""
        self.sort_fields.append({"field": field, "ascending": ascending})
        return self

    def add_terms_filter(self, field: str, values: list) -> "QueryFilter":
        """Add terms filter for multiple values"""
        if "terms" not in self.filters:
            self.filters["terms"] = {}
        self.filters["terms"][field] = values
        return self

    def add_exists_filter(self, field: str) -> "QueryFilter":
        """Add exists filter to check if field exists"""
        if "exists" not in self.filters:
            self.filters["exists"] = []
        self.filters["exists"].append(field)
        return self

    def add_range_filter(
        self, field: str, gte=None, lte=None, gt=None, lt=None
    ) -> "QueryFilter":
        """Add range filter for numeric/date fields"""
        if "range" not in self.filters:
            self.filters["range"] = {}

        range_params = {}
        if gte is not None:
            range_params["gte"] = gte
        if lte is not None:
            range_params["lte"] = lte
        if gt is not None:
            range_params["gt"] = gt
        if lt is not None:
            range_params["lt"] = lt

        self.filters["range"][field] = range_params
        return self

    def set_pagination(self, limit: int, offset: int = 0) -> "QueryFilter":
        """設定分頁"""
        self.limit = limit
        self.offset = offset
        return self


class AggregationQuery:
    """聚合查詢"""

    def __init__(self):
        self.aggs = {}

    def add_metric(self, name: str, metric_type: str, field: str) -> "AggregationQuery":
        """添加度量聚合 (sum, avg, max, min, count)"""
        self.aggs[name] = {"type": "metric", "metric": metric_type, "field": field}
        return self

    def add_terms(self, name: str, field: str, size: int = 10) -> "AggregationQuery":
        """添加詞條聚合"""
        self.aggs[name] = {"type": "terms", "field": field, "size": size}
        return self

    def add_date_histogram(
        self, name: str, field: str, interval: str
    ) -> "AggregationQuery":
        """添加日期直方圖聚合"""
        self.aggs[name] = {
            "type": "date_histogram",
            "field": field,
            "interval": interval,
        }
        return self


class IndexingResult:
    """索引結果"""

    def __init__(self):
        self.success_count = 0
        self.failed_count = 0
        self.errors = []
        self.stats = {}

    def add_success(self, count: int):
        self.success_count += count

    def add_failure(self, count: int, error: str = None):
        self.failed_count += count
        if error:
            self.errors.append(error)

    def set_stats(self, stats: Dict[str, int]):
        self.stats = stats


class StorageInterface(ABC):
    """儲存層抽象介面"""

    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化儲存連接"""
        pass

    @abstractmethod
    def create_indices(self, force_recreate: bool = False) -> bool:
        """建立索引/表格"""
        pass

    @abstractmethod
    def index_document(
        self, data_type: DataType, doc_id: str, document: Dict[str, Any]
    ) -> bool:
        """索引單一文檔"""
        pass

    @abstractmethod
    def bulk_index(
        self, data_type: DataType, documents: List[Dict[str, Any]]
    ) -> IndexingResult:
        """批量索引文檔"""
        pass

    @abstractmethod
    def search(
        self, data_type: DataType, query_filter: QueryFilter
    ) -> List[Dict[str, Any]]:
        """搜尋文檔"""
        pass

    @abstractmethod
    def aggregate(
        self,
        data_type: DataType,
        query_filter: QueryFilter,
        agg_query: AggregationQuery,
    ) -> Dict[str, Any]:
        """聚合查詢"""
        pass

    @abstractmethod
    def get_by_id(self, data_type: DataType, doc_id: str) -> Optional[Dict[str, Any]]:
        """根據 ID 取得文檔"""
        pass

    @abstractmethod
    def delete_by_id(self, data_type: DataType, doc_id: str) -> bool:
        """根據 ID 刪除文檔"""
        pass

    @abstractmethod
    def delete_by_query(self, data_type: DataType, query_filter: QueryFilter) -> int:
        """根據查詢條件刪除文檔"""
        pass

    @abstractmethod
    def get_stats(self, data_type: DataType) -> Dict[str, Any]:
        """取得儲存統計資訊"""
        pass


class ValidationError(Exception):
    """驗證錯誤"""

    pass


class StorageError(Exception):
    """儲存錯誤"""

    pass


class DataValidator:
    """數據驗證器"""

    @staticmethod
    def validate_session_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """驗證 Session 數據"""
        required_fields = ["activity_id", "user_id", "timestamp"]

        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")

        # 數值範圍驗證
        if "total_distance" in data and data["total_distance"] < 0:
            raise ValidationError("total_distance cannot be negative")

        if "avg_heart_rate" in data and not (30 <= data["avg_heart_rate"] <= 220):
            raise ValidationError("avg_heart_rate must be between 30-220 bpm")

        return data

    @staticmethod
    def validate_record_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """驗證 Record 數據"""
        required_fields = ["activity_id", "user_id", "timestamp", "sequence"]

        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")

        # GPS 座標驗證
        if "location" in data:
            location = data["location"]
            if "lat" in location and not (-90 <= location["lat"] <= 90):
                raise ValidationError("Invalid latitude")
            if "lon" in location and not (-180 <= location["lon"] <= 180):
                raise ValidationError("Invalid longitude")

        return data

    @staticmethod
    def validate_lap_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """驗證 Lap 數據"""
        required_fields = ["activity_id", "user_id", "timestamp", "lap_number"]

        for field in required_fields:
            if field not in data or data[field] is None:
                raise ValidationError(f"Missing required field: {field}")

        if "lap_number" in data and data["lap_number"] < 1:
            raise ValidationError("lap_number must be positive")

        return data
