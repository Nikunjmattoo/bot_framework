# utils/logging.py
import logging
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# Configure basic logging
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)

# Create formatter
DEFAULT_FORMAT = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def configure_logger(name: str, level: int = logging.INFO, 
                     format_str: str = DEFAULT_FORMAT,
                     date_format: str = DEFAULT_DATE_FORMAT) -> logging.Logger:
    """
    Configure a logger with file and console handlers.
    
    Args:
        name: Logger name
        level: Logging level
        format_str: Log format string
        date_format: Date format string
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Clear existing handlers
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_str, date_format)
    
    # File handler
    file_path = os.path.join(LOGS_DIR, f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log")
    file_handler = logging.FileHandler(file_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

class ContextLogger:
    """Logger with context for structured logging."""
    
    def __init__(self, name: str, level: int = logging.INFO):
        self.logger = configure_logger(name, level)
    
    def log(self, level: int, message: str, context: Dict[str, Any] = None, **kwargs):
        """Log a message with context."""
        # Handle 'extra' parameter by treating it as context
        extra_context = kwargs.get('extra')
        if extra_context and isinstance(extra_context, dict) and context is None:
            context = extra_context
        
        context_str = ""
        if context:
            context_filtered = {k: v for k, v in context.items() if v is not None}
            if context_filtered:
                context_str = " | " + " | ".join(f"{k}={v}" for k, v in context_filtered.items())
        
        self.logger.log(level, message + context_str)
    
    def debug(self, message: str, context: Dict[str, Any] = None, **kwargs):
        self.log(logging.DEBUG, message, context, **kwargs)
    
    def info(self, message: str, context: Dict[str, Any] = None, **kwargs):
        self.log(logging.INFO, message, context, **kwargs)
    
    def warning(self, message: str, context: Dict[str, Any] = None, **kwargs):
        self.log(logging.WARNING, message, context, **kwargs)
    
    def error(self, message: str, context: Dict[str, Any] = None, **kwargs):
        self.log(logging.ERROR, message, context, **kwargs)
    
    def exception(self, message: str, context: Dict[str, Any] = None, **kwargs):
        if context is None:
            context = {}
            
        # Handle 'extra' parameter by treating it as context
        extra_context = kwargs.get('extra')
        if extra_context and isinstance(extra_context, dict):
            context.update(extra_context)
            
        self.logger.exception(message + " | " + " | ".join(f"{k}={v}" for k, v in context.items() if v is not None))

def get_logger(name: str, level: int = logging.INFO) -> ContextLogger:
    """Get a context logger."""
    return ContextLogger(name, level)

def log_json_to_file(name: str, data: Dict[str, Any]):
    """Log JSON data to a file for debugging."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(LOGS_DIR, f"{name}_{timestamp}.json")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, default=str, ensure_ascii=False, indent=2)