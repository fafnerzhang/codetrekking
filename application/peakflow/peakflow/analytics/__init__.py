#!/usr/bin/env python3
"""
Analytics 模組 - 分析與統計
"""

from .interface import (
    FitnessAnalyzer, PowerAnalyzer, RunningDynamicsAnalyzer, 
    TrajectoryAnalyzer, RecoveryAnalyzer, ComparisonAnalyzer, CompositeAnalyzer,
    AnalyticsType, AggregationLevel, TimeRange, AnalyticsFilter, 
    MetricThresholds, AnalyticsResult,
    AnalyticsError, InsufficientDataError, InvalidParameterError, CalculationError
)

from .elasticsearch import ElasticsearchAnalytics
from .advanced import AdvancedStatistics
from .tss import TSSCalculator, TSSAnalyzer

__all__ = [
    # 抽象接口
    'FitnessAnalyzer', 'PowerAnalyzer', 'RunningDynamicsAnalyzer',
    'TrajectoryAnalyzer', 'RecoveryAnalyzer', 'ComparisonAnalyzer', 'CompositeAnalyzer',
    
    # 數據類型和枚舉
    'AnalyticsType', 'AggregationLevel', 'TimeRange', 'AnalyticsFilter',
    'MetricThresholds', 'AnalyticsResult',
    
    # 異常類型
    'AnalyticsError', 'InsufficientDataError', 'InvalidParameterError', 'CalculationError',
    
    # 具體實現
    'ElasticsearchAnalytics', 'AdvancedStatistics',
    
    # TSS 功能
    'TSSCalculator', 'TSSAnalyzer'
]
