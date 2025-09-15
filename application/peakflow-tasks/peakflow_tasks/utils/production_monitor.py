"""
Production monitoring and alerting configuration for PeakFlow Tasks
"""

import logging
import time
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from celery import signals
from celery.signals import task_prerun, task_postrun, task_failure, task_retry


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricData:
    """Container for metric data"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]
    
    
@dataclass
class AlertData:
    """Container for alert data"""
    level: AlertLevel
    message: str
    timestamp: datetime
    context: Dict[str, Any]


class ProductionMonitor:
    """
    Production-grade monitoring for PeakFlow Tasks
    Tracks performance, errors, and system health
    """
    
    def __init__(self):
        self.metrics: List[MetricData] = []
        self.alerts: List[AlertData] = []
        self.task_stats = {
            'total_tasks': 0,
            'successful_tasks': 0,
            'failed_tasks': 0,
            'retried_tasks': 0,
            'avg_execution_time': 0.0,
            'task_types': {}
        }
        self.system_health = {
            'worker_status': 'unknown',
            'queue_depth': 0,
            'error_rate': 0.0,
            'last_health_check': None
        }
        
        # Setup logging
        self.logger = logging.getLogger('peakflow_tasks.monitor')
        self.setup_logging()
        
        # Connect to Celery signals
        self.connect_signals()
    
    def setup_logging(self):
        """Setup structured logging for production"""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def connect_signals(self):
        """Connect to Celery signals for monitoring"""
        
        @task_prerun.connect
        def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **kwds):
            """Monitor task start"""
            self.record_metric('task_started', 1, {
                'task_name': task.name,
                'task_id': task_id
            })
            self.logger.info(f"🚀 Task {task.name} [{task_id}] started")
        
        @task_postrun.connect
        def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, 
                               retval=None, state=None, **kwds):
            """Monitor task completion"""
            self.task_stats['total_tasks'] += 1
            
            if state == 'SUCCESS':
                self.task_stats['successful_tasks'] += 1
                self.record_metric('task_success', 1, {
                    'task_name': task.name,
                    'task_id': task_id
                })
                self.logger.info(f"✅ Task {task.name} [{task_id}] completed successfully")
            else:
                self.record_metric('task_completed', 1, {
                    'task_name': task.name,
                    'task_id': task_id,
                    'state': state
                })
                self.logger.info(f"📋 Task {task.name} [{task_id}] completed with state={state}")
        
        @task_failure.connect
        def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, einfo=None, **kwds):
            """Monitor task failures"""
            self.task_stats['failed_tasks'] += 1
            
            self.record_metric('task_failure', 1, {
                'task_name': sender.name,
                'task_id': task_id,
                'exception_type': type(exception).__name__
            })
            
            self.create_alert(
                AlertLevel.ERROR,
                f"Task {sender.name} [{task_id}] failed: {exception}",
                {
                    'task_name': sender.name,
                    'task_id': task_id,
                    'exception': str(exception),
                    'traceback': str(traceback)
                }
            )
            
            self.logger.error(f"❌ Task {sender.name} [{task_id}] failed: {exception}")
        
        @task_retry.connect  
        def task_retry_handler(sender=None, task_id=None, reason=None, einfo=None, **kwds):
            """Monitor task retries"""
            self.task_stats['retried_tasks'] += 1
            
            self.record_metric('task_retry', 1, {
                'task_name': sender.name,
                'task_id': task_id,
                'reason': str(reason)
            })
            
            self.logger.warning(f"🔄 Task {sender.name} [{task_id}] retry: {reason}")
    
    def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """Record a metric data point"""
        metric = MetricData(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {}
        )
        self.metrics.append(metric)
        
        # Keep only recent metrics (last 1000)
        if len(self.metrics) > 1000:
            self.metrics = self.metrics[-1000:]
    
    def create_alert(self, level: AlertLevel, message: str, context: Dict[str, Any] = None):
        """Create an alert"""
        alert = AlertData(
            level=level,
            message=message,
            timestamp=datetime.now(),
            context=context or {}
        )
        self.alerts.append(alert)
        
        # Keep only recent alerts (last 100)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # Log alerts
        if level == AlertLevel.CRITICAL:
            self.logger.critical(f"🚨 CRITICAL: {message}")
        elif level == AlertLevel.ERROR:
            self.logger.error(f"❌ ERROR: {message}")
        elif level == AlertLevel.WARNING:
            self.logger.warning(f"⚠️ WARNING: {message}")
        else:
            self.logger.info(f"ℹ️ INFO: {message}")
    
    def check_system_health(self):
        """Perform system health check"""
        try:
            from peakflow_tasks.celery_app import celery_app
            
            # Check worker status
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                self.system_health['worker_status'] = 'healthy'
                worker_count = len(stats)
                self.record_metric('active_workers', worker_count, {})
                
                # Check queue depths
                active_queues = inspect.active_queues()
                total_queue_depth = 0
                
                if active_queues:
                    for worker, queues in active_queues.items():
                        for queue_info in queues:
                            # In production, you'd query RabbitMQ for actual queue depth
                            # For now, we'll use a placeholder
                            total_queue_depth += 0  # Placeholder
                
                self.system_health['queue_depth'] = total_queue_depth
                self.record_metric('queue_depth', total_queue_depth, {})
                
            else:
                self.system_health['worker_status'] = 'unhealthy'
                self.create_alert(
                    AlertLevel.CRITICAL,
                    "No active Celery workers detected",
                    {'check_time': datetime.now().isoformat()}
                )
            
            # Calculate error rate
            if self.task_stats['total_tasks'] > 0:
                error_rate = self.task_stats['failed_tasks'] / self.task_stats['total_tasks']
                self.system_health['error_rate'] = error_rate
                self.record_metric('error_rate', error_rate, {})
                
                # Alert if error rate is too high
                if error_rate > 0.1:  # 10% error rate threshold
                    self.create_alert(
                        AlertLevel.ERROR,
                        f"High error rate detected: {error_rate:.2%}",
                        {
                            'error_rate': error_rate,
                            'failed_tasks': self.task_stats['failed_tasks'],
                            'total_tasks': self.task_stats['total_tasks']
                        }
                    )
            
            self.system_health['last_health_check'] = datetime.now()
            
        except Exception as e:
            self.create_alert(
                AlertLevel.ERROR,
                f"Health check failed: {e}",
                {'exception': str(e)}
            )
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current system health status"""
        self.check_system_health()
        return {
            'status': self.system_health['worker_status'],
            'metrics': {
                'total_tasks': self.task_stats['total_tasks'],
                'success_rate': (
                    self.task_stats['successful_tasks'] / max(self.task_stats['total_tasks'], 1)
                ),
                'error_rate': self.system_health['error_rate'],
                'queue_depth': self.system_health['queue_depth']
            },
            'last_check': self.system_health['last_health_check'].isoformat() if self.system_health['last_health_check'] else None,
            'recent_alerts': [
                {
                    'level': alert.level.value,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat()
                }
                for alert in self.alerts[-10:]  # Last 10 alerts
            ]
        }
    
    def export_metrics_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []
        
        # Task metrics
        lines.append("# HELP peakflow_tasks_total Total number of tasks processed")
        lines.append("# TYPE peakflow_tasks_total counter")
        lines.append(f"peakflow_tasks_total {self.task_stats['total_tasks']}")
        
        lines.append("# HELP peakflow_tasks_successful Successful tasks")
        lines.append("# TYPE peakflow_tasks_successful counter")
        lines.append(f"peakflow_tasks_successful {self.task_stats['successful_tasks']}")
        
        lines.append("# HELP peakflow_tasks_failed Failed tasks")
        lines.append("# TYPE peakflow_tasks_failed counter")
        lines.append(f"peakflow_tasks_failed {self.task_stats['failed_tasks']}")
        
        lines.append("# HELP peakflow_tasks_error_rate Current error rate")
        lines.append("# TYPE peakflow_tasks_error_rate gauge")
        lines.append(f"peakflow_tasks_error_rate {self.system_health['error_rate']}")
        
        lines.append("# HELP peakflow_tasks_queue_depth Current queue depth")
        lines.append("# TYPE peakflow_tasks_queue_depth gauge")
        lines.append(f"peakflow_tasks_queue_depth {self.system_health['queue_depth']}")
        
        return "\n".join(lines)


# Global monitor instance
production_monitor = ProductionMonitor()


# Health check endpoint function
def health_check_endpoint():
    """Health check endpoint for load balancers"""
    try:
        status = production_monitor.get_health_status()
        
        if status['status'] == 'healthy' and status['metrics']['error_rate'] < 0.2:
            return {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'metrics': status['metrics']
            }, 200
        else:
            return {
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'metrics': status['metrics'],
                'alerts': status['recent_alerts']
            }, 503
            
    except Exception as e:
        return {
            'status': 'error',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }, 500


# Metrics endpoint function
def metrics_endpoint():
    """Prometheus metrics endpoint"""
    try:
        metrics_data = production_monitor.export_metrics_prometheus()
        return metrics_data, 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        return f"# Error exporting metrics: {e}", 500, {'Content-Type': 'text/plain'}
