#!/usr/bin/env python3
"""
PeakFlow Utilities Module
"""
import json
import sys
import logging
from pathlib import Path
from typing import Optional

from .const import DEFAULT_GARMIN_CONFIG, DEFAULT_GARMIN_CONFIG_DIR


class LoggingConfig:
    """Centralized logging configuration using standard logging"""
    
    _initialized = False
    
    @classmethod
    def setup_logging(cls, 
                     log_level: str = "INFO",
                     log_file: Optional[str] = None,
                     log_format: Optional[str] = None,
                     enable_console: bool = True) -> None:
        """
        Setup standard logging configuration
        
        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file: Path to log file (optional)
            log_format: Custom log format
            enable_console: Enable console logging
        """
        if cls._initialized:
            return
        
        # Convert string level to logging constant
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Default format
        if log_format is None:
            log_format = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        
        # Configure root logger
        logging.basicConfig(
            level=numeric_level,
            format=log_format,
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[]
        )
        
        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(numeric_level)
            formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
            console_handler.setFormatter(formatter)
            logging.getLogger().addHandler(console_handler)
        
        # File handler
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(numeric_level)
            formatter = logging.Formatter(log_format, datefmt='%Y-%m-%d %H:%M:%S')
            file_handler.setFormatter(formatter)
            logging.getLogger().addHandler(file_handler)
        
        cls._initialized = True
        logging.info(f"🔧 Logging initialized - Level: {log_level}")
    
    @classmethod
    def get_logger(cls, name: str = None) -> logging.Logger:
        """Get a logger instance"""
        if not cls._initialized:
            cls.setup_logging()
        
        if name:
            return logging.getLogger(name)
        return logging.getLogger("peakflow")


# Configure default logging for the module
def setup_peakflow_logging(log_level: str = "INFO", 
                          log_dir: Optional[str] = None) -> None:
    """Setup logging for PeakFlow module"""
    log_file = None
    if log_dir:
        log_dir_path = Path(log_dir)
        log_dir_path.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir_path / "peakflow.log")
    
    LoggingConfig.setup_logging(
        log_level=log_level,
        log_file=log_file,
        log_format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )


# Default logger for the module
def get_peakflow_logger(module_name: str) -> logging.Logger:
    """Get a PeakFlow logger for a specific module"""
    return LoggingConfig.get_logger(module_name)


# Export logger creation function for other modules
def get_logger(module_name: str) -> logging.Logger:
    """Get a logger for a specific module"""
    return get_peakflow_logger(module_name)


# Initialize default logging
setup_peakflow_logging()

# Initialize logger for utils module
peakflow_logger = get_peakflow_logger("peakflow.utils")


def get_garmin_config_dir(user: str, config_dir: str = DEFAULT_GARMIN_CONFIG_DIR) -> str:
    config_dir = config_dir.format(user=user) 
    Path(config_dir).mkdir(parents=True, exist_ok=True)
    return config_dir


def build_garmin_config(user: str, 
                 password: str, 
                 config_dir: str = DEFAULT_GARMIN_CONFIG_DIR):
    config = DEFAULT_GARMIN_CONFIG.copy()
    config["credentials"]["user"] = user
    config["credentials"]["password"] = password
    config_dir = get_garmin_config_dir(user, config_dir)
    Path(config_dir).mkdir(parents=True, exist_ok=True)
    with open(Path(config_dir) / "GarminConnectConfig.json", "w") as f:
        json.dump(config, f, indent=4)
    return config
