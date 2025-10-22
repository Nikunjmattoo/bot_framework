"""
Logging utilities with trace_id support.
"""

import logging
import json
from typing import Any, Dict, Optional


class TraceLogger(logging.LoggerAdapter):
    """
    Logger adapter that adds trace_id to all log records.
    """
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Add trace_id to extra field if present."""
        extra = kwargs.get("extra", {})
        if self.extra.get("trace_id"):
            extra["trace_id"] = self.extra["trace_id"]
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(name: str, trace_id: Optional[str] = None) -> logging.Logger:
    """
    Get logger with optional trace_id support.
    
    Args:
        name: Logger name (usually __name__)
        trace_id: Optional trace ID to include in all logs
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    
    if trace_id:
        return TraceLogger(logger, {"trace_id": trace_id})
    
    return logger


def log_json(logger: logging.Logger, level: str, event: str, **kwargs):
    """
    Log structured JSON message.
    
    Args:
        logger: Logger instance
        level: Log level ('info', 'error', 'warning', 'debug')
        event: Event name
        **kwargs: Additional fields to include in log
    """
    log_data = {
        "event": event,
        **kwargs
    }
    
    log_method = getattr(logger, level, logger.info)
    log_method(json.dumps(log_data))