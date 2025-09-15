"""
Development runner for PeakFlow Tasks.

This module provides a comprehensive development environment for running Celery workers
with enhanced features like file watching, better logging, and health checks.
"""

import os
import sys
import signal
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
import click
from dataclasses import dataclass

# Try to import optional dependencies
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

try:
    import colorama
    from colorama import Fore, Style, Back
    colorama.init()
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

# Load environment variables from .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False


@dataclass
class DevConfig:
    """Configuration for development runner."""
    concurrency: int = 1
    log_level: str = "debug"
    queues: str = "default,garmin,processing,storage,workflows"
    watch: bool = False
    flower: bool = False
    beat: bool = False
    env_file: Optional[str] = None
    check_deps: bool = True
    pool: str = "threads"
    hostname: Optional[str] = None


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for development."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    } if COLORAMA_AVAILABLE else {}
    
    RESET = '\033[0m' if COLORAMA_AVAILABLE else ''
    
    def format(self, record):
        if COLORAMA_AVAILABLE and record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.RESET}"
        return super().format(record)


class FileWatcher(FileSystemEventHandler):
    """File system event handler for auto-restart."""
    
    def __init__(self, callback, extensions=None):
        self.callback = callback
        self.extensions = extensions or {'.py'}
        self.last_restart = 0
        self.restart_delay = 2  # Minimum seconds between restarts
        
    def should_restart(self, event):
        """Check if we should restart based on the file event."""
        if event.is_directory:
            return False
            
        file_path = Path(event.src_path)
        if file_path.suffix not in self.extensions:
            return False
            
        # Avoid too frequent restarts
        current_time = time.time()
        if current_time - self.last_restart < self.restart_delay:
            return False
            
        # Skip certain files/directories
        skip_patterns = {'__pycache__', '.git', '.pytest_cache', 'node_modules'}
        if any(pattern in str(file_path) for pattern in skip_patterns):
            return False
            
        return True
    
    def on_modified(self, event):
        if self.should_restart(event):
            self.last_restart = time.time()
            self.callback(event.src_path)


class HealthChecker:
    """Health checker for development dependencies."""
    
    @staticmethod
    def check_uv() -> bool:
        """Check if uv is available."""
        try:
            result = subprocess.run(
                ["uv", "--version"], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @staticmethod
    def check_broker_connection() -> Dict[str, Any]:
        """Check broker connection."""
        broker_url = os.getenv("CELERY_BROKER_URL")
        if not broker_url:
            return {"status": "warning", "message": "No CELERY_BROKER_URL configured"}
        
        # For now, just return OK - could implement actual connection check
        return {"status": "ok", "message": f"Broker configured: {broker_url}"}
    
    @staticmethod
    def check_environment() -> Dict[str, List[str]]:
        """Check environment variables."""
        required_vars = [
            "CELERY_BROKER_URL", 
            "CELERY_RESULT_BACKEND",
        ]
        
        optional_vars = [
            "RABBITMQ_HOST", 
            "RABBITMQ_PORT", 
            "RABBITMQ_USER", 
            "RABBITMQ_PASSWORD",
            "REDIS_URL",
        ]
        
        loaded = []
        missing = []
        
        for var in required_vars:
            if os.getenv(var):
                loaded.append(var)
            else:
                missing.append(var)
        
        for var in optional_vars:
            if os.getenv(var):
                loaded.append(var)
        
        return {"loaded": loaded, "missing": missing}


class DevRunner:
    """Development runner for Celery workers."""
    
    def __init__(self, config: DevConfig):
        self.config = config
        self.worker_process: Optional[subprocess.Popen] = None
        self.flower_process: Optional[subprocess.Popen] = None
        self.beat_process: Optional[subprocess.Popen] = None
        self.observer: Optional[Observer] = None
        self.should_stop = threading.Event()
        self.restart_requested = threading.Event()
        self.logger = self._setup_logger()
        self.setup_signal_handlers()
        
    def _setup_logger(self) -> logging.Logger:
        """Setup enhanced development logger."""
        logger = logging.getLogger("peakflow_dev")
        logger.setLevel(getattr(logging, self.config.log_level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Console handler with colors
        console_handler = logging.StreamHandler(sys.stdout)
        if COLORAMA_AVAILABLE:
            formatter = ColoredFormatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        else:
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_file = Path.cwd() / "dev_celery.log"
        file_handler = logging.FileHandler(log_file)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            self.logger.info(f"Received {signal_name} signal, shutting down gracefully...")
            self.should_stop.set()
            self.stop_all_processes()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        if hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, signal_handler)
    
    def load_environment(self):
        """Load environment variables from .env file."""
        if not DOTENV_AVAILABLE:
            self.logger.warning("python-dotenv not available, skipping .env file loading")
            return
        
        env_file = self.config.env_file or ".env"
        env_path = Path.cwd() / env_file
        
        if env_path.exists():
            self.logger.info(f"Loading environment from {env_path}")
            load_dotenv(env_path)
        else:
            self.logger.info(f"No {env_file} file found, using system environment")
    
    def check_prerequisites(self) -> bool:
        """Check development prerequisites."""
        if not self.config.check_deps:
            return True
            
        self.logger.info("🔍 Checking prerequisites...")
        
        # Check project structure
        if not Path("pyproject.toml").exists():
            self.logger.error("❌ pyproject.toml not found. Run from peakflow-tasks directory.")
            return False
        
        # Check uv
        if not HealthChecker.check_uv():
            self.logger.error("❌ uv package manager not found")
            return False
        
        self.logger.info("✅ uv package manager found")
        
        # Check environment
        env_status = HealthChecker.check_environment()
        if env_status["loaded"]:
            self.logger.info(f"✅ Environment variables loaded: {', '.join(env_status['loaded'])}")
        
        if env_status["missing"]:
            self.logger.warning(f"⚠️  Missing environment variables: {', '.join(env_status['missing'])}")
            self.logger.info("Some variables may use defaults or be optional")
        
        # Check broker
        broker_status = HealthChecker.check_broker_connection()
        if broker_status["status"] == "ok":
            self.logger.info(f"✅ {broker_status['message']}")
        else:
            self.logger.warning(f"⚠️  {broker_status['message']}")
        
        self.logger.info("✅ Prerequisites check completed")
        return True
    
    def get_worker_command(self) -> List[str]:
        """Build Celery worker command."""
        cmd = [
            "uv", "run", "celery",
            "-A", "peakflow_tasks.celery_app",
            "worker",
            f"--loglevel={self.config.log_level}",
            f"--concurrency={self.config.concurrency}",
            f"--queues={self.config.queues}",
        ]
        
        if self.config.hostname:
            cmd.extend([f"--hostname={self.config.hostname}"])
        
        return cmd
    
    def start_worker(self) -> bool:
        """Start Celery worker process."""
        cmd = self.get_worker_command()
        self.logger.info(f"🚀 Starting Celery worker: {' '.join(cmd)}")
        
        try:
            self.worker_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=Path.cwd(),
                env=os.environ.copy(),
                bufsize=1,
                universal_newlines=True
            )
            
            self.logger.info(f"✅ Celery worker started (PID: {self.worker_process.pid})")
            
            # Start log forwarding thread
            log_thread = threading.Thread(
                target=self._forward_logs,
                args=(self.worker_process, "CELERY"),
                daemon=True
            )
            log_thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Celery worker: {e}")
            return False
    
    def start_flower(self) -> bool:
        """Start Flower monitoring interface."""
        if not self.config.flower:
            return True
        
        cmd = [
            "uv", "run", "celery",
            "--app", "peakflow_tasks.celery_app:celery_app", 
            "flower",
            "--port=5555"
        ]
        
        self.logger.info("🌸 Starting Flower monitoring...")
        
        try:
            self.flower_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=Path.cwd(),
                env=os.environ.copy(),
                bufsize=1,
                universal_newlines=True
            )
            
            self.logger.info(f"✅ Flower started (PID: {self.flower_process.pid})")
            self.logger.info("🌐 Flower available at: http://localhost:5555")
            
            # Start log forwarding thread
            log_thread = threading.Thread(
                target=self._forward_logs,
                args=(self.flower_process, "FLOWER"),
                daemon=True
            )
            log_thread.start()
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to start Flower: {e}")
            return False
    
    def start_file_watcher(self):
        """Start file watcher for auto-restart."""
        if not self.config.watch or not WATCHDOG_AVAILABLE:
            if self.config.watch:
                self.logger.warning("⚠️  File watching requested but watchdog not available")
            return
        
        self.logger.info("👀 Starting file watcher...")
        
        def restart_callback(file_path):
            self.logger.info(f"📝 File changed: {file_path}")
            self.logger.info("🔄 Restarting worker...")
            self.restart_requested.set()
        
        event_handler = FileWatcher(restart_callback)
        self.observer = Observer()
        
        # Watch current directory and subdirectories
        watch_dirs = [Path.cwd() / "peakflow_tasks"]
        for watch_dir in watch_dirs:
            if watch_dir.exists():
                self.observer.schedule(event_handler, str(watch_dir), recursive=True)
                self.logger.info(f"📁 Watching: {watch_dir}")
        
        self.observer.start()
        self.logger.info("✅ File watcher started")
    
    def _forward_logs(self, process: subprocess.Popen, prefix: str):
        """Forward subprocess logs to main logger."""
        try:
            while not self.should_stop.is_set() and process.poll() is None:
                line = process.stdout.readline()
                if line:
                    line = line.rstrip()
                    if line:
                        self.logger.info(f"[{prefix}] {line}")
        except Exception as e:
            self.logger.error(f"Error forwarding logs from {prefix}: {e}")
    
    def stop_process(self, process: Optional[subprocess.Popen], name: str):
        """Stop a subprocess gracefully."""
        if not process:
            return
        
        self.logger.info(f"🛑 Stopping {name}...")
        
        try:
            process.terminate()
            
            # Wait for graceful shutdown
            try:
                process.wait(timeout=10)
                self.logger.info(f"✅ {name} stopped gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning(f"⚠️  {name} didn't stop gracefully, forcing...")
                process.kill()
                process.wait()
                self.logger.info(f"✅ {name} terminated forcefully")
                
        except Exception as e:
            self.logger.error(f"❌ Error stopping {name}: {e}")
    
    def stop_all_processes(self):
        """Stop all running processes."""
        self.stop_process(self.worker_process, "Celery worker")
        self.stop_process(self.flower_process, "Flower")
        self.stop_process(self.beat_process, "Celery beat")
        
        if self.observer:
            self.logger.info("👀 Stopping file watcher...")
            self.observer.stop()
            self.observer.join()
            self.logger.info("✅ File watcher stopped")
    
    def restart_worker(self):
        """Restart the Celery worker."""
        self.stop_process(self.worker_process, "Celery worker")
        self.worker_process = None
        
        time.sleep(1)  # Brief pause before restart
        
        if not self.start_worker():
            self.logger.error("❌ Failed to restart worker")
            return False
        
        return True
    
    def run(self) -> int:
        """Main run method."""
        self.logger.info("🚀 PeakFlow Tasks Development Runner")
        self.logger.info("=" * 50)
        self.logger.info("Press Ctrl+C to stop gracefully")
        
        try:
            # Load environment
            self.load_environment()
            
            # Check prerequisites
            if not self.check_prerequisites():
                return 1
            
            # Start services
            if not self.start_worker():
                return 1
            
            if not self.start_flower():
                return 1
            
            # Start file watcher
            self.start_file_watcher()
            
            self.logger.info("✅ All services started successfully")
            self.logger.info("🎯 Development environment ready!")
            
            # Main loop
            while not self.should_stop.is_set():
                # Check if restart was requested
                if self.restart_requested.is_set():
                    self.restart_requested.clear()
                    if not self.restart_worker():
                        break
                
                # Check if processes are still running
                if self.worker_process and self.worker_process.poll() is not None:
                    exit_code = self.worker_process.returncode
                    if exit_code != 0:
                        self.logger.error(f"❌ Worker exited with code {exit_code}")
                        break
                    else:
                        self.logger.info("✅ Worker completed successfully")
                        break
                
                time.sleep(0.5)
            
        except KeyboardInterrupt:
            self.logger.info("🛑 Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"❌ Unexpected error: {e}")
            return 1
        
        finally:
            self.stop_all_processes()
            self.logger.info("✅ Development runner stopped")
        
        return 0
