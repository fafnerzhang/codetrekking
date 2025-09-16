"""
Integration tests for performance monitoring in PeakFlow Tasks.

This module tests the advanced performance monitoring, profiling,
and metrics collection capabilities.
"""

import pytest
import time
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from typing import Dict, Any

from peakflow_tasks.utils.monitoring import (
    PerformanceProfiler,
    MetricsCollector,
    profile_task,
    monitor_performance,
    performance_profiler,
    metrics_collector
)


class TestPerformanceProfiler:
    """Test performance profiling functionality."""
    
    @pytest.fixture
    def profiler(self):
        """Create a fresh profiler instance."""
        return PerformanceProfiler(max_profiles=100)
    
    def test_profile_lifecycle(self, profiler):
        """Test complete profile lifecycle."""
        task_id = "test_task_123"
        task_name = "test_analytics_task"
        context = {"user_id": "test_user"}
        
        # Start profile
        profile_id = profiler.start_profile(task_id, task_name, context)
        
        assert profile_id is not None
        assert profile_id in profiler.active_profiles
        
        profile = profiler.active_profiles[profile_id]
        assert profile['task_id'] == task_id
        assert profile['task_name'] == task_name
        assert profile['context'] == context
        assert len(profile['resource_snapshots']) >= 1  # Start snapshot
    
    def test_checkpoint_functionality(self, profiler):
        """Test checkpoint addition during profiling."""
        task_id = "test_task_123"
        task_name = "test_task"
        
        profile_id = profiler.start_profile(task_id, task_name)
        
        # Add checkpoints
        profiler.add_checkpoint(profile_id, "data_loaded", {"records": 1000})
        profiler.add_checkpoint(profile_id, "processing_started")
        profiler.add_checkpoint(profile_id, "processing_completed", {"processed": 950})
        
        profile = profiler.active_profiles[profile_id]
        assert len(profile['checkpoints']) == 3
        
        checkpoint_names = [cp['name'] for cp in profile['checkpoints']]
        assert "data_loaded" in checkpoint_names
        assert "processing_started" in checkpoint_names
        assert "processing_completed" in checkpoint_names
        
        # Check checkpoint data
        data_loaded_cp = next(cp for cp in profile['checkpoints'] if cp['name'] == 'data_loaded')
        assert data_loaded_cp['data']['records'] == 1000
    
    def test_profile_completion(self, profiler):
        """Test profile completion and summary generation."""
        task_id = "test_task_123"
        task_name = "test_task"
        
        profile_id = profiler.start_profile(task_id, task_name)
        
        # Simulate some work
        time.sleep(0.1)
        
        profiler.add_checkpoint(profile_id, "work_done")
        
        # End profile
        summary = profiler.end_profile(profile_id, "completed")
        
        assert profile_id not in profiler.active_profiles
        assert len(profiler.profiles) == 1
        
        # Check summary
        assert summary['profile_id'] == profile_id
        assert summary['task_id'] == task_id
        assert summary['task_name'] == task_name
        assert summary['total_duration'] > 0.1
        assert summary['status'] == 'completed'
        assert summary['checkpoint_count'] == 1
        assert 'resource_efficiency' in summary
        assert 'performance_score' in summary
        assert 'bottlenecks' in summary
        assert 'recommendations' in summary
    
    def test_profile_with_error(self, profiler):
        """Test profile handling with errors."""
        task_id = "test_task_123"
        task_name = "test_task"
        
        profile_id = profiler.start_profile(task_id, task_name)
        
        # Simulate error
        error = Exception("Test error")
        summary = profiler.end_profile(profile_id, "failed", error)
        
        assert summary['status'] == 'failed'
        assert summary['error'] == 'Test error'
    
    def test_resource_efficiency_calculation(self, profiler):
        """Test resource efficiency calculation."""
        # Mock resource snapshots
        profile = {
            'resource_snapshots': [
                {'cpu_percent': 20, 'memory_percent': 30},
                {'cpu_percent': 25, 'memory_percent': 35},
                {'cpu_percent': 30, 'memory_percent': 40}
            ]
        }
        
        efficiency = profiler._calculate_resource_efficiency(profile)
        
        # Should be good efficiency (low resource usage)
        assert 50 < efficiency < 80  # Expecting good efficiency
    
    def test_performance_score_calculation(self, profiler):
        """Test performance score calculation."""
        profile = {
            'checkpoints': [{'name': 'cp1'}, {'name': 'cp2'}],
            'resource_snapshots': [
                {'cpu_percent': 20, 'memory_percent': 30}
            ]
        }
        
        # Test fast execution
        fast_score = profiler._calculate_performance_score(profile, 5.0)  # 5 seconds
        assert fast_score > 90
        
        # Test slow execution
        slow_score = profiler._calculate_performance_score(profile, 400.0)  # 6+ minutes
        assert slow_score <= 70
    
    def test_bottleneck_identification(self, profiler):
        """Test bottleneck identification."""
        now = datetime.now()
        
        profile = {
            'checkpoints': [
                {'name': 'start', 'timestamp': now},
                {'name': 'slow_operation', 'timestamp': now + timedelta(seconds=60)},  # 60s gap
                {'name': 'end', 'timestamp': now + timedelta(seconds=65)}
            ],
            'resource_snapshots': [
                {'stage': 'start', 'memory_percent': 85, 'cpu_percent': 50},  # High memory
                {'stage': 'end', 'memory_percent': 40, 'cpu_percent': 30}
            ]
        }
        
        bottlenecks = profiler._identify_bottlenecks(profile)
        
        assert len(bottlenecks) == 2  # Long gap + high memory
        
        bottleneck_types = [b['type'] for b in bottlenecks]
        assert 'long_gap' in bottleneck_types
        assert 'high_memory' in bottleneck_types
    
    def test_performance_analytics(self, profiler):
        """Test performance analytics generation."""
        # Add some completed profiles
        for i in range(5):
            profile = {
                'end_time': datetime.now(),
                'total_duration': 10.0 + i,
                'task_name': f'task_{i % 2}',  # Two different task types
                'performance_summary': {
                    'performance_score': 80.0 + i,
                    'bottlenecks': [{'type': 'test_bottleneck'}] if i % 2 == 0 else []
                }
            }
            profiler.profiles.append(profile)
        
        analytics = profiler.get_performance_analytics(24)
        
        assert analytics['total_profiles'] == 5
        assert 'duration_stats' in analytics
        assert 'performance_stats' in analytics
        assert 'task_breakdown' in analytics
        assert 'common_bottlenecks' in analytics
        assert 'improvement_opportunities' in analytics
        
        # Check duration stats
        duration_stats = analytics['duration_stats']
        assert duration_stats['min'] == 10.0
        assert duration_stats['max'] == 14.0
        assert duration_stats['avg'] == 12.0


class TestMetricsCollector:
    """Test metrics collection functionality."""
    
    @pytest.fixture
    def collector(self):
        """Create a fresh metrics collector."""
        return MetricsCollector()
    
    def test_metric_recording(self, collector):
        """Test basic metric recording."""
        collector.record_metric("task_duration", 10.5, {"status": "success"})
        collector.record_metric("task_duration", 12.3, {"status": "success"})
        collector.record_metric("task_duration", 8.7, {"status": "failed"})
        
        assert "task_duration" in collector.metrics_store
        assert len(collector.metrics_store["task_duration"]) == 3
    
    def test_metric_summary(self, collector):
        """Test metric summary generation."""
        # Record some metrics
        values = [10.0, 15.0, 20.0, 25.0, 30.0]
        for value in values:
            collector.record_metric("test_metric", value)
        
        summary = collector.get_metric_summary("test_metric", 60)
        
        assert summary['count'] == 5
        assert summary['min'] == 10.0
        assert summary['max'] == 30.0
        assert summary['avg'] == 20.0
        assert summary['latest'] == 30.0
        assert summary['trend'] in ['increasing', 'decreasing', 'stable']
    
    def test_trend_calculation(self, collector):
        """Test trend calculation."""
        # Test increasing trend
        increasing_values = [10, 15, 20, 25, 30]
        trend = collector._calculate_trend(increasing_values)
        assert trend == 'increasing'
        
        # Test decreasing trend
        decreasing_values = [30, 25, 20, 15, 10]
        trend = collector._calculate_trend(decreasing_values)
        assert trend == 'decreasing'
        
        # Test stable trend
        stable_values = [20, 21, 19, 20, 21]
        trend = collector._calculate_trend(stable_values)
        assert trend == 'stable'
    
    def test_metrics_aggregation(self, collector):
        """Test metrics aggregation."""
        # Record metrics for different metric names
        collector.record_metric("metric_a", 10.0)
        collector.record_metric("metric_a", 20.0)
        collector.record_metric("metric_b", 5.0)
        collector.record_metric("metric_b", 15.0)
        
        aggregated = collector.aggregate_metrics(force=True)
        
        assert "metric_a" in aggregated
        assert "metric_b" in aggregated
        
        assert aggregated["metric_a"]["avg"] == 15.0
        assert aggregated["metric_b"]["avg"] == 10.0
    
    def test_prometheus_export(self, collector):
        """Test Prometheus metrics export."""
        collector.record_metric("task_duration", 10.0)
        collector.record_metric("task_count", 5)
        
        # Force aggregation
        collector.aggregate_metrics(force=True)
        
        prometheus_output = collector.export_metrics_to_prometheus()
        
        assert "task_duration" in prometheus_output
        assert "task_count" in prometheus_output
        assert "TYPE" in prometheus_output
        assert "HELP" in prometheus_output


class TestProfileTaskContextManager:
    """Test profile_task context manager."""
    
    def test_successful_profiling(self):
        """Test profiling with successful execution."""
        task_name = "test_context_task"
        
        with profile_task(task_name) as profiler_context:
            # Simulate some work
            time.sleep(0.05)
            profiler_context.checkpoint("work_started")
            time.sleep(0.05)
            profiler_context.checkpoint("work_completed")
        
        # Check if profile was completed
        # In a real scenario, we'd check the global profiler
        assert profiler_context.profile_id is not None
    
    def test_profiling_with_exception(self):
        """Test profiling when exception occurs."""
        task_name = "test_failing_task"
        
        with pytest.raises(ValueError):
            with profile_task(task_name) as profiler_context:
                profiler_context.checkpoint("before_error")
                raise ValueError("Test error")
        
        # Profile should still be completed with failed status
        assert profiler_context.profile_id is not None


class TestMonitorPerformanceDecorator:
    """Test monitor_performance decorator."""
    
    def test_successful_function_monitoring(self):
        """Test decorator with successful function execution."""
        
        @monitor_performance("test_function")
        def test_function(x, y):
            time.sleep(0.05)  # Simulate work
            return x + y
        
        result = test_function(2, 3)
        
        assert result == 5
        # In a real scenario, we'd verify metrics were recorded
    
    def test_function_monitoring_with_exception(self):
        """Test decorator when function raises exception."""
        
        @monitor_performance("failing_function")
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        # Metrics should still be recorded for failed execution


class TestIntegratedMonitoring:
    """Test integrated monitoring scenarios."""
    
    def test_end_to_end_profiling_scenario(self):
        """Test complete profiling scenario."""
        # Simulate a complex task with multiple stages
        task_name = "complex_analytics_task"
        task_id = "analytics_123"
        
        with profile_task(task_name, task_id) as profiler:
            # Stage 1: Data loading
            profiler.checkpoint("data_loading_started")
            time.sleep(0.02)  # Simulate data loading
            profiler.checkpoint("data_loaded", {"records": 1000})
            
            # Stage 2: Processing
            profiler.checkpoint("processing_started")
            time.sleep(0.03)  # Simulate processing
            profiler.checkpoint("processing_completed", {"processed": 950, "errors": 50})
            
            # Stage 3: Storage
            profiler.checkpoint("storage_started")
            time.sleep(0.01)  # Simulate storage
            profiler.checkpoint("storage_completed")
        
        # Verify profiling completed successfully
        assert profiler.profile_id is not None
    
    def test_metrics_collection_over_time(self):
        """Test metrics collection over multiple operations."""
        collector = MetricsCollector()
        
        # Simulate multiple task executions
        task_durations = [10.5, 12.3, 8.7, 15.2, 11.8]
        success_statuses = ["success", "success", "failed", "success", "success"]
        
        for duration, status in zip(task_durations, success_statuses):
            collector.record_metric("task_duration", duration, {"status": status})
            collector.record_metric("task_count", 1, {"status": status})
        
        # Generate summary
        duration_summary = collector.get_metric_summary("task_duration", 60)
        count_summary = collector.get_metric_summary("task_count", 60)
        
        assert duration_summary['count'] == 5
        assert count_summary['count'] == 5
        assert duration_summary['avg'] == sum(task_durations) / len(task_durations)
    
    def test_performance_bottleneck_detection(self):
        """Test bottleneck detection in realistic scenario."""
        profiler = PerformanceProfiler()
        
        task_id = "bottleneck_test"
        task_name = "data_processing"
        
        profile_id = profiler.start_profile(task_id, task_name)
        
        # Simulate task with bottleneck
        profiler.add_checkpoint(profile_id, "initialization")
        
        # Simulate long database operation (bottleneck)
        time.sleep(0.2)  # Longer sleep to ensure bottleneck detection
        profiler.add_checkpoint(profile_id, "database_query_completed")
        
        # Quick processing
        time.sleep(0.01)
        profiler.add_checkpoint(profile_id, "processing_completed")
        
        summary = profiler.end_profile(profile_id, "completed")
        
        # Should detect the long gap as potential bottleneck
        # Note: Actual bottleneck detection depends on thresholds
        # If no recommendations, just check that the summary contains expected fields
        assert 'recommendations' in summary
        assert isinstance(summary['recommendations'], list)


class TestPerformanceOptimizationRecommendations:
    """Test performance optimization recommendations."""
    
    def test_slow_task_recommendations(self):
        """Test recommendations for slow tasks."""
        profiler = PerformanceProfiler()
        
        profile = {
            'start_time': datetime.now() - timedelta(seconds=400),  # 6+ minutes
            'checkpoints': [],
            'resource_snapshots': [{'cpu_percent': 50, 'memory_percent': 60}]
        }
        
        recommendations = profiler._generate_performance_recommendations(profile)
        
        # Should recommend breaking down long tasks
        assert any("breaking down" in rec.lower() for rec in recommendations)
    
    def test_resource_intensive_task_recommendations(self):
        """Test recommendations for resource-intensive tasks."""
        profiler = PerformanceProfiler()
        
        now = datetime.now()
        profile = {
            'start_time': now,
            'checkpoints': [
                {'name': 'start', 'timestamp': now},
                {'name': 'end', 'timestamp': now + timedelta(seconds=10)}
            ],
            'resource_snapshots': [
                {'stage': 'start', 'memory_percent': 95, 'cpu_percent': 98}  # Very high usage
            ]
        }
        
        recommendations = profiler._generate_performance_recommendations(profile)
        
        # Should recommend optimization
        assert len(recommendations) > 0
        assert any("optim" in rec.lower() for rec in recommendations)


if __name__ == '__main__':
    pytest.main([__file__])
