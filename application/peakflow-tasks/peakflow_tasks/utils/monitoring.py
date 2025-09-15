"""
Task monitoring and metrics utilities for PeakFlow Tasks.

This module provides functionality for monitoring task execution, collecting metrics,
and integrating with monitoring systems.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import json

from celery.signals import (
    task_prerun,
    task_postrun,
    task_failure,
    task_retry,
    worker_ready,
    worker_shutdown,
)

logger = logging.getLogger(__name__)


@dataclass
class TaskMetrics:
    """Container for task execution metrics."""
    
    task_name: str
    task_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    status: str = "PENDING"
    retries: int = 0
    worker: Optional[str] = None
    exception: Optional[str] = None
    memory_usage: Optional[float] = None
    args_hash: Optional[str] = None
    kwargs_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'task_name': self.task_name,
            'task_id': self.task_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'status': self.status,
            'retries': self.retries,
            'worker': self.worker,
            'exception': self.exception,
            'memory_usage': self.memory_usage,
            'args_hash': self.args_hash,
            'kwargs_hash': self.kwargs_hash,
        }


@dataclass
class WorkerMetrics:
    """Container for worker metrics."""
    
    worker_name: str
    start_time: datetime
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_task_time: Optional[datetime] = None
    
    def update_task_completion(self, duration: float) -> None:
        """Update metrics after task completion."""
        self.tasks_completed += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.tasks_completed
        self.last_task_time = datetime.now()
    
    def update_task_failure(self) -> None:
        """Update metrics after task failure."""
        self.tasks_failed += 1
        self.last_task_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            'worker_name': self.worker_name,
            'start_time': self.start_time.isoformat(),
            'tasks_completed': self.tasks_completed,
            'tasks_failed': self.tasks_failed,
            'total_duration': self.total_duration,
            'avg_duration': self.avg_duration,
            'last_task_time': self.last_task_time.isoformat() if self.last_task_time else None,
        }


class TaskMonitor:
    """
    Task monitoring and metrics collection.
    """
    
    def __init__(self, max_history: int = 1000):
        self.max_history = max_history
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.task_history: deque = deque(maxlen=max_history)
        self.task_counts: Dict[str, int] = defaultdict(int)
        self.task_durations: Dict[str, List[float]] = defaultdict(list)
        self.error_counts: Dict[str, int] = defaultdict(int)
        
    def record_task_start(self, sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
        """Record task start."""
        task_name = task.name if task else str(sender)
        worker_name = kwds.get('hostname', 'unknown')
        
        metrics = TaskMetrics(
            task_name=task_name,
            task_id=task_id,
            start_time=datetime.now(),
            worker=worker_name,
        )
        
        self.task_metrics[task_id] = metrics
        logger.debug(f"📊 Recording task start: {task_name} [{task_id}]")
    
    def record_task_completion(self, sender=None, task_id=None, task=None, retval=None, state=None, **kwds):
        """Record task completion."""
        if task_id not in self.task_metrics:
            return
        
        metrics = self.task_metrics[task_id]
        metrics.end_time = datetime.now()
        metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
        metrics.status = state or "SUCCESS"
        
        # Update task counts and durations
        self.task_counts[metrics.task_name] += 1
        self.task_durations[metrics.task_name].append(metrics.duration)
        
        # Keep only recent durations (last 100 per task)
        if len(self.task_durations[metrics.task_name]) > 100:
            self.task_durations[metrics.task_name] = self.task_durations[metrics.task_name][-100:]
        
        # Update worker metrics
        if metrics.worker and metrics.worker in self.worker_metrics:
            self.worker_metrics[metrics.worker].update_task_completion(metrics.duration)
        
        # Add to history
        self.task_history.append(metrics.to_dict())
        
        logger.debug(f"📊 Recording task completion: {metrics.task_name} [{task_id}] in {metrics.duration:.2f}s")
    
    def record_task_failure(self, sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
        """Record task failure."""
        if task_id not in self.task_metrics:
            return
        
        metrics = self.task_metrics[task_id]
        metrics.end_time = datetime.now()
        metrics.duration = (metrics.end_time - metrics.start_time).total_seconds()
        metrics.status = "FAILURE"
        metrics.exception = str(exception) if exception else "Unknown error"
        
        # Update error counts
        self.error_counts[metrics.task_name] += 1
        
        # Update worker metrics
        if metrics.worker and metrics.worker in self.worker_metrics:
            self.worker_metrics[metrics.worker].update_task_failure()
        
        # Add to history
        self.task_history.append(metrics.to_dict())
        
        logger.debug(f"📊 Recording task failure: {metrics.task_name} [{task_id}] after {metrics.duration:.2f}s")
    
    def record_task_retry(self, sender=None, task_id=None, reason=None, einfo=None, **kwds):
        """Record task retry."""
        if task_id not in self.task_metrics:
            return
        
        metrics = self.task_metrics[task_id]
        metrics.retries += 1
        
        logger.debug(f"📊 Recording task retry: {metrics.task_name} [{task_id}] (retry #{metrics.retries})")
    
    def record_worker_ready(self, sender=None, **kwds):
        """Record worker ready."""
        worker_name = sender.hostname if sender else "unknown"
        
        self.worker_metrics[worker_name] = WorkerMetrics(
            worker_name=worker_name,
            start_time=datetime.now(),
        )
        
        logger.info(f"📊 Worker ready: {worker_name}")
    
    def record_worker_shutdown(self, sender=None, **kwds):
        """Record worker shutdown."""
        worker_name = sender.hostname if sender else "unknown"
        
        if worker_name in self.worker_metrics:
            del self.worker_metrics[worker_name]
        
        logger.info(f"📊 Worker shutdown: {worker_name}")
    
    def get_task_stats(self, task_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get task statistics.
        
        Args:
            task_name: Optional task name to filter by
            
        Returns:
            Dictionary with task statistics
        """
        if task_name:
            durations = self.task_durations.get(task_name, [])
            return {
                'task_name': task_name,
                'total_count': self.task_counts.get(task_name, 0),
                'error_count': self.error_counts.get(task_name, 0),
                'avg_duration': sum(durations) / len(durations) if durations else 0,
                'min_duration': min(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0,
                'recent_durations': durations[-10:] if durations else [],
            }
        else:
            # Return stats for all tasks
            stats = {}
            for task_name in self.task_counts.keys():
                stats[task_name] = self.get_task_stats(task_name)
            return stats
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        return {
            worker_name: metrics.to_dict()
            for worker_name, metrics in self.worker_metrics.items()
        }
    
    def get_recent_tasks(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent task history.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            List of recent task dictionaries
        """
        return list(self.task_history)[-limit:]
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        total_tasks = sum(self.task_counts.values())
        total_errors = sum(self.error_counts.values())
        
        return {
            'total_tasks': total_tasks,
            'total_errors': total_errors,
            'error_rate': total_errors / total_tasks if total_tasks > 0 else 0,
            'errors_by_task': dict(self.error_counts),
        }
    
    def cleanup_old_metrics(self, max_age_hours: int = 24) -> None:
        """
        Clean up old metrics to prevent memory growth.
        
        Args:
            max_age_hours: Maximum age of metrics to keep in hours
        """
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        
        # Clean up task metrics
        to_remove = [
            task_id for task_id, metrics in self.task_metrics.items()
            if metrics.start_time < cutoff_time
        ]
        
        for task_id in to_remove:
            del self.task_metrics[task_id]
        
        logger.debug(f"📊 Cleaned up {len(to_remove)} old task metrics")


# Global monitor instance
monitor = TaskMonitor()


def setup_monitoring() -> None:
    """Setup task monitoring signal handlers."""
    
    # Connect signal handlers
    task_prerun.connect(monitor.record_task_start, weak=False)
    task_postrun.connect(monitor.record_task_completion, weak=False)
    task_failure.connect(monitor.record_task_failure, weak=False)
    task_retry.connect(monitor.record_task_retry, weak=False)
    worker_ready.connect(monitor.record_worker_ready, weak=False)
    worker_shutdown.connect(monitor.record_worker_shutdown, weak=False)
    
    logger.info("📊 Task monitoring setup completed")


def get_task_monitor() -> TaskMonitor:
    """Get the global task monitor instance."""
    return monitor


def export_metrics_to_file(file_path: str) -> None:
    """
    Export current metrics to a JSON file.
    
    Args:
        file_path: Path to output file
    """
    metrics_data = {
        'timestamp': datetime.now().isoformat(),
        'task_stats': monitor.get_task_stats(),
        'worker_stats': monitor.get_worker_stats(),
        'error_summary': monitor.get_error_summary(),
        'recent_tasks': monitor.get_recent_tasks(100),
    }
    
    with open(file_path, 'w') as f:
        json.dump(metrics_data, f, indent=2, default=str)
    
    logger.info(f"📊 Metrics exported to {file_path}")


def print_metrics_summary() -> None:
    """Print a summary of current metrics to the console."""
    task_stats = monitor.get_task_stats()
    worker_stats = monitor.get_worker_stats()
    error_summary = monitor.get_error_summary()
    
    print("\n📊 Task Metrics Summary")
    print("=" * 50)
    
    if task_stats:
        print("\nTask Statistics:")
        for task_name, stats in task_stats.items():
            print(f"  {task_name}:")
            print(f"    Total: {stats['total_count']}")
            print(f"    Errors: {stats['error_count']}")
            print(f"    Avg Duration: {stats['avg_duration']:.2f}s")
    
    if worker_stats:
        print("\nWorker Statistics:")
        for worker_name, stats in worker_stats.items():
            print(f"  {worker_name}:")
            print(f"    Completed: {stats['tasks_completed']}")
            print(f"    Failed: {stats['tasks_failed']}")
            print(f"    Avg Duration: {stats['avg_duration']:.2f}s")
    
    print(f"\nError Summary:")
    print(f"  Total Tasks: {error_summary['total_tasks']}")
    print(f"  Total Errors: {error_summary['total_errors']}")
    print(f"  Error Rate: {error_summary['error_rate']:.2%}")
    
    print("=" * 50)


# Advanced Performance Monitoring

class PerformanceProfiler:
    """
    Advanced performance profiler for tasks with detailed metrics collection.
    """
    
    def __init__(self, max_profiles: int = 1000):
        self.max_profiles = max_profiles
        self.profiles = deque(maxlen=max_profiles)
        self.active_profiles = {}
        
    def start_profile(self, task_id: str, task_name: str, context: Dict[str, Any] = None) -> str:
        """Start profiling a task execution."""
        profile_id = f"profile_{task_id}_{int(time.time())}"
        
        profile_data = {
            'profile_id': profile_id,
            'task_id': task_id,
            'task_name': task_name,
            'context': context or {},
            'start_time': datetime.now(),
            'checkpoints': [],
            'resource_snapshots': [],
            'performance_markers': {}
        }
        
        self.active_profiles[profile_id] = profile_data
        self._take_resource_snapshot(profile_id, 'start')
        
        logger.debug(f"🔍 Started performance profile: {profile_id}")
        return profile_id
    
    def add_checkpoint(self, profile_id: str, checkpoint_name: str, data: Dict[str, Any] = None):
        """Add a checkpoint to the performance profile."""
        if profile_id not in self.active_profiles:
            logger.warning(f"Profile {profile_id} not found for checkpoint {checkpoint_name}")
            return
        
        checkpoint = {
            'name': checkpoint_name,
            'timestamp': datetime.now(),
            'data': data or {}
        }
        
        profile = self.active_profiles[profile_id]
        profile['checkpoints'].append(checkpoint)
        
        # Calculate time since start
        duration = (checkpoint['timestamp'] - profile['start_time']).total_seconds()
        logger.debug(f"📍 Checkpoint '{checkpoint_name}' at {duration:.2f}s")
        
        self._take_resource_snapshot(profile_id, checkpoint_name)
    
    def end_profile(self, profile_id: str, status: str = 'completed', error: Exception = None) -> Dict[str, Any]:
        """End profiling and return performance summary."""
        if profile_id not in self.active_profiles:
            logger.warning(f"Profile {profile_id} not found for end")
            return {}
        
        profile = self.active_profiles.pop(profile_id)
        end_time = datetime.now()
        total_duration = (end_time - profile['start_time']).total_seconds()
        
        # Take final resource snapshot
        self._take_resource_snapshot(profile_id, 'end', profile)
        
        # Calculate performance metrics
        performance_summary = {
            'profile_id': profile_id,
            'task_id': profile['task_id'],
            'task_name': profile['task_name'],
            'total_duration': total_duration,
            'status': status,
            'error': str(error) if error else None,
            'checkpoint_count': len(profile['checkpoints']),
            'resource_efficiency': self._calculate_resource_efficiency(profile),
            'performance_score': self._calculate_performance_score(profile, total_duration),
            'bottlenecks': self._identify_bottlenecks(profile),
            'recommendations': self._generate_performance_recommendations(profile)
        }
        
        # Store completed profile
        completed_profile = {
            **profile,
            'end_time': end_time,
            'total_duration': total_duration,
            'performance_summary': performance_summary
        }
        
        self.profiles.append(completed_profile)
        logger.info(f"📊 Performance profile completed: {profile_id} ({total_duration:.2f}s)")
        
        return performance_summary
    
    def _take_resource_snapshot(self, profile_id: str, stage: str, profile: Dict[str, Any] = None):
        """Take a snapshot of resource usage."""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            snapshot = {
                'stage': stage,
                'timestamp': datetime.now(),
                'cpu_percent': process.cpu_percent(),
                'memory_mb': process.memory_info().rss / 1024 / 1024,
                'memory_percent': process.memory_percent(),
                'open_files': len(process.open_files()),
                'threads': process.num_threads()
            }
            
            if profile:
                profile['resource_snapshots'].append(snapshot)
            elif profile_id in self.active_profiles:
                self.active_profiles[profile_id]['resource_snapshots'].append(snapshot)
                
        except ImportError:
            # psutil not available, use basic metrics
            snapshot = {
                'stage': stage,
                'timestamp': datetime.now(),
                'note': 'Limited metrics - psutil not available'
            }
            
            if profile:
                profile['resource_snapshots'].append(snapshot)
            elif profile_id in self.active_profiles:
                self.active_profiles[profile_id]['resource_snapshots'].append(snapshot)
    
    def _calculate_resource_efficiency(self, profile: Dict[str, Any]) -> float:
        """Calculate resource efficiency score (0-100)."""
        snapshots = profile['resource_snapshots']
        if len(snapshots) < 2:
            return 50.0  # Default neutral score
        
        # Calculate average resource usage
        avg_cpu = sum(s.get('cpu_percent', 0) for s in snapshots) / len(snapshots)
        avg_memory = sum(s.get('memory_percent', 0) for s in snapshots) / len(snapshots)
        
        # Efficiency is inverse of resource usage (lower is better for efficiency)
        cpu_efficiency = max(0, 100 - avg_cpu)
        memory_efficiency = max(0, 100 - avg_memory)
        
        return (cpu_efficiency + memory_efficiency) / 2
    
    def _calculate_performance_score(self, profile: Dict[str, Any], duration: float) -> float:
        """Calculate overall performance score based on multiple factors."""
        base_score = 100.0
        
        # Penalty for long duration (adjust thresholds as needed)
        if duration > 300:  # 5 minutes
            base_score -= 30
        elif duration > 60:  # 1 minute
            base_score -= 15
        elif duration > 10:  # 10 seconds
            base_score -= 5
        
        # Bonus for efficient resource usage
        efficiency = self._calculate_resource_efficiency(profile)
        resource_bonus = (efficiency - 50) * 0.2  # Scale to -10 to +10
        
        # Penalty for excessive checkpoints (might indicate inefficient processing)
        checkpoint_count = len(profile['checkpoints'])
        if checkpoint_count > 20:
            base_score -= 10
        elif checkpoint_count > 10:
            base_score -= 5
        
        final_score = max(0, min(100, base_score + resource_bonus))
        return round(final_score, 1)
    
    def _identify_bottlenecks(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify performance bottlenecks from profile data."""
        bottlenecks = []
        checkpoints = profile['checkpoints']
        
        if len(checkpoints) < 2:
            return bottlenecks
        
        # Find long gaps between checkpoints
        for i in range(1, len(checkpoints)):
            prev_checkpoint = checkpoints[i-1]
            curr_checkpoint = checkpoints[i]
            
            gap_duration = (curr_checkpoint['timestamp'] - prev_checkpoint['timestamp']).total_seconds()
            
            # Consider gaps > 30 seconds as potential bottlenecks
            if gap_duration > 30:
                bottlenecks.append({
                    'type': 'long_gap',
                    'location': f"Between '{prev_checkpoint['name']}' and '{curr_checkpoint['name']}'",
                    'duration': gap_duration,
                    'severity': 'high' if gap_duration > 120 else 'medium'
                })
        
        # Check for resource spikes
        snapshots = profile['resource_snapshots']
        for snapshot in snapshots:
            if snapshot.get('memory_percent', 0) > 80:
                bottlenecks.append({
                    'type': 'high_memory',
                    'location': f"At stage '{snapshot['stage']}'",
                    'value': snapshot['memory_percent'],
                    'severity': 'high' if snapshot['memory_percent'] > 90 else 'medium'
                })
            
            if snapshot.get('cpu_percent', 0) > 95:
                bottlenecks.append({
                    'type': 'high_cpu',
                    'location': f"At stage '{snapshot['stage']}'",
                    'value': snapshot['cpu_percent'],
                    'severity': 'high'
                })
        
        return bottlenecks
    
    def _generate_performance_recommendations(self, profile: Dict[str, Any]) -> List[str]:
        """Generate performance optimization recommendations."""
        recommendations = []
        bottlenecks = self._identify_bottlenecks(profile)
        duration = (profile.get('end_time', datetime.now()) - profile['start_time']).total_seconds()
        
        # Duration-based recommendations
        if duration > 300:
            recommendations.append("Consider breaking down long-running tasks into smaller chunks")
        
        # Bottleneck-based recommendations
        for bottleneck in bottlenecks:
            if bottleneck['type'] == 'long_gap':
                recommendations.append(f"Investigate slow operation: {bottleneck['location']}")
            elif bottleneck['type'] == 'high_memory':
                recommendations.append("Consider implementing memory optimization or streaming processing")
            elif bottleneck['type'] == 'high_cpu':
                recommendations.append("Consider optimizing CPU-intensive operations or adding parallelization")
        
        # Resource efficiency recommendations
        efficiency = self._calculate_resource_efficiency(profile)
        if efficiency < 30:
            recommendations.append("Review resource usage patterns and optimize algorithms")
        
        return recommendations
    
    def get_performance_analytics(self, time_window_hours: int = 24) -> Dict[str, Any]:
        """Get performance analytics for completed profiles."""
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        recent_profiles = [
            p for p in self.profiles 
            if p.get('end_time', datetime.now()) >= cutoff_time
        ]
        
        if not recent_profiles:
            return {'status': 'no_data', 'message': 'No profiles in time window'}
        
        # Calculate statistics
        durations = [p['total_duration'] for p in recent_profiles]
        performance_scores = [p['performance_summary']['performance_score'] for p in recent_profiles]
        
        analytics = {
            'time_window_hours': time_window_hours,
            'total_profiles': len(recent_profiles),
            'duration_stats': {
                'min': min(durations),
                'max': max(durations),
                'avg': sum(durations) / len(durations),
                'median': sorted(durations)[len(durations) // 2]
            },
            'performance_stats': {
                'min_score': min(performance_scores),
                'max_score': max(performance_scores),
                'avg_score': sum(performance_scores) / len(performance_scores)
            },
            'task_breakdown': self._analyze_task_performance(recent_profiles),
            'common_bottlenecks': self._analyze_common_bottlenecks(recent_profiles),
            'improvement_opportunities': self._identify_improvement_opportunities(recent_profiles)
        }
        
        return analytics
    
    def _analyze_task_performance(self, profiles: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Analyze performance by task type."""
        task_stats = defaultdict(list)
        
        for profile in profiles:
            task_name = profile['task_name']
            task_stats[task_name].append({
                'duration': profile['total_duration'],
                'score': profile['performance_summary']['performance_score']
            })
        
        result = {}
        for task_name, stats in task_stats.items():
            durations = [s['duration'] for s in stats]
            scores = [s['score'] for s in stats]
            
            result[task_name] = {
                'count': len(stats),
                'avg_duration': sum(durations) / len(durations),
                'avg_score': sum(scores) / len(scores),
                'max_duration': max(durations),
                'min_duration': min(durations)
            }
        
        return result
    
    def _analyze_common_bottlenecks(self, profiles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze common bottleneck patterns."""
        bottleneck_counts = defaultdict(int)
        
        for profile in profiles:
            bottlenecks = profile['performance_summary'].get('bottlenecks', [])
            for bottleneck in bottlenecks:
                bottleneck_type = bottleneck['type']
                bottleneck_counts[bottleneck_type] += 1
        
        return dict(bottleneck_counts)
    
    def _identify_improvement_opportunities(self, profiles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify improvement opportunities across profiles."""
        opportunities = []
        
        # Find tasks with consistently poor performance
        task_performance = self._analyze_task_performance(profiles)
        for task_name, stats in task_performance.items():
            if stats['avg_score'] < 60 and stats['count'] >= 3:
                opportunities.append({
                    'type': 'task_optimization',
                    'task': task_name,
                    'priority': 'high',
                    'description': f"Task {task_name} has low average performance score ({stats['avg_score']:.1f})"
                })
            
            if stats['avg_duration'] > 300 and stats['count'] >= 3:
                opportunities.append({
                    'type': 'duration_optimization',
                    'task': task_name,
                    'priority': 'medium',
                    'description': f"Task {task_name} takes long time on average ({stats['avg_duration']:.1f}s)"
                })
        
        # Find common bottlenecks
        bottlenecks = self._analyze_common_bottlenecks(profiles)
        for bottleneck_type, count in bottlenecks.items():
            if count >= len(profiles) * 0.3:  # Affects 30% or more of tasks
                opportunities.append({
                    'type': 'bottleneck_resolution',
                    'bottleneck': bottleneck_type,
                    'priority': 'high',
                    'description': f"Bottleneck '{bottleneck_type}' affects {count} tasks ({count/len(profiles)*100:.1f}%)"
                })
        
        return opportunities


class MetricsCollector:
    """
    Centralized metrics collection and aggregation.
    """
    
    def __init__(self):
        self.metrics_store = defaultdict(list)
        self.aggregated_metrics = {}
        self.last_aggregation = datetime.now()
        
    def record_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None, 
                     timestamp: datetime = None):
        """Record a metric value with optional labels."""
        metric_entry = {
            'value': value,
            'labels': labels or {},
            'timestamp': timestamp or datetime.now()
        }
        
        self.metrics_store[metric_name].append(metric_entry)
        
        # Keep only recent metrics (last 24 hours)
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.metrics_store[metric_name] = [
            m for m in self.metrics_store[metric_name] 
            if m['timestamp'] >= cutoff_time
        ]
    
    def get_metric_summary(self, metric_name: str, time_window_minutes: int = 60) -> Dict[str, Any]:
        """Get summary statistics for a metric."""
        if metric_name not in self.metrics_store:
            return {'error': f'Metric {metric_name} not found'}
        
        cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
        recent_metrics = [
            m for m in self.metrics_store[metric_name] 
            if m['timestamp'] >= cutoff_time
        ]
        
        if not recent_metrics:
            return {'error': f'No recent data for {metric_name}'}
        
        values = [m['value'] for m in recent_metrics]
        
        return {
            'metric_name': metric_name,
            'time_window_minutes': time_window_minutes,
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else None,
            'trend': self._calculate_trend(values)
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction for metric values."""
        if len(values) < 2:
            return 'insufficient_data'
        
        # Compare first half vs second half
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(values[mid:]) / (len(values) - mid)
        
        if second_half_avg > first_half_avg * 1.1:
            return 'increasing'
        elif second_half_avg < first_half_avg * 0.9:
            return 'decreasing'
        else:
            return 'stable'
    
    def aggregate_metrics(self, force: bool = False) -> Dict[str, Any]:
        """Aggregate metrics for reporting."""
        now = datetime.now()
        if not force and (now - self.last_aggregation).total_seconds() < 300:  # 5 minutes
            return self.aggregated_metrics
        
        aggregated = {}
        
        for metric_name, metrics in self.metrics_store.items():
            if not metrics:
                continue
            
            # Get last hour summary
            summary = self.get_metric_summary(metric_name, 60)
            aggregated[metric_name] = summary
        
        self.aggregated_metrics = aggregated
        self.last_aggregation = now
        
        return aggregated
    
    def export_metrics_to_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        prometheus_output = []
        
        for metric_name, summary in self.aggregated_metrics.items():
            if 'error' in summary:
                continue
            
            # Clean metric name for Prometheus
            clean_name = metric_name.replace(' ', '_').replace('-', '_').lower()
            
            prometheus_output.append(f"# HELP {clean_name} {metric_name} metric")
            prometheus_output.append(f"# TYPE {clean_name} gauge")
            prometheus_output.append(f"{clean_name}_avg {summary['avg']}")
            prometheus_output.append(f"{clean_name}_min {summary['min']}")
            prometheus_output.append(f"{clean_name}_max {summary['max']}")
            prometheus_output.append(f"{clean_name}_count {summary['count']}")
        
        return '\n'.join(prometheus_output)


# Global instances for advanced monitoring
performance_profiler = PerformanceProfiler()
metrics_collector = MetricsCollector()


# Context managers for easy profiling

class profile_task:
    """Context manager for task performance profiling."""
    
    def __init__(self, task_name: str, task_id: str = None, context: Dict[str, Any] = None):
        self.task_name = task_name
        self.task_id = task_id or f"task_{int(time.time())}"
        self.context = context or {}
        self.profile_id = None
    
    def __enter__(self):
        self.profile_id = performance_profiler.start_profile(
            self.task_id, self.task_name, self.context
        )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.profile_id:
            status = 'failed' if exc_type else 'completed'
            error = exc_val if exc_type else None
            performance_profiler.end_profile(self.profile_id, status, error)
    
    def checkpoint(self, name: str, data: Dict[str, Any] = None):
        """Add a checkpoint during task execution."""
        if self.profile_id:
            performance_profiler.add_checkpoint(self.profile_id, name, data)


# Performance monitoring decorators

def monitor_performance(task_name: str = None):
    """Decorator for automatic performance monitoring."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            nonlocal task_name
            if not task_name:
                task_name = func.__name__
            
            task_id = f"{task_name}_{int(time.time())}"
            
            with profile_task(task_name, task_id):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    success = True
                except Exception as e:
                    success = False
                    raise
                finally:
                    duration = time.time() - start_time
                    
                    # Record metrics
                    metrics_collector.record_metric(
                        f"{task_name}_duration", 
                        duration,
                        labels={'status': 'success' if success else 'failed'}
                    )
                    
                    metrics_collector.record_metric(
                        f"{task_name}_count",
                        1,
                        labels={'status': 'success' if success else 'failed'}
                    )
            
            return result
        
        return wrapper
    return decorator