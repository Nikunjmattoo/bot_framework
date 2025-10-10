"""Logging utilities with context."""
import logging
import json
import os
import sys
import traceback
import socket
from datetime import datetime, timezone  # FIXED: Added timezone import
from typing import Dict, Any, Optional, Union, cast
from logging.handlers import RotatingFileHandler

# Environment-specific configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.environ.get("LOG_FORMAT", "json")  # 'json' or 'text'
LOG_FILE = os.environ.get("LOG_FILE", None)  # File path or None for stdout
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 10485760))  # 10MB default
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 5))
HOSTNAME = socket.gethostname()
SERVICE_NAME = os.environ.get("SERVICE_NAME", "message_handler")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

# Sensitive fields that should be redacted in logs
SENSITIVE_FIELDS = {
    "password", "token", "secret", "key", "auth", "credential", "pwd",
    "ssn", "credit_card", "card_number", "cvv", "auth_token", "access_token"
}

class JsonFormatter(logging.Formatter):
    """Formatter for JSON-structured logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Extract exception info if present
        exc_info = None
        if record.exc_info:
            try:
                exc_info = {
                    "exception_type": record.exc_info[0].__name__,
                    "exception_message": str(record.exc_info[1]),
                    "traceback": traceback.format_exception(*record.exc_info)
                }
            except (AttributeError, TypeError) as e:
                exc_info = {
                    "exception_type": "unknown",
                    "exception_message": "Error formatting exception info",
                    "format_error": str(e)
                }
        
        # Base log data
        log_data = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": self._safe_str(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "service": SERVICE_NAME,
            "hostname": HOSTNAME,
            "environment": ENVIRONMENT,
        }
        
        # Add exception info if present
        if exc_info:
            log_data["exception"] = exc_info
        
        # Add extra fields from record
        if hasattr(record, "extra"):
            for key, value in record.extra.items():
                log_data[key] = value
        
        # Add extra fields from LoggerAdapter
        for key, value in getattr(record, "__dict__", {}).items():
            if (key not in log_data and not key.startswith("_") and 
                key not in ("args", "exc_info", "exc_text", "stack_info", "msg")):
                # Make sure value is JSON serializable
                try:
                    # Test JSON serialization without actually serializing the whole object
                    json.dumps({key: value})
                    log_data[key] = value
                except (TypeError, ValueError):
                    # If not serializable, convert to string
                    log_data[key] = self._safe_str(value)
        
        # Redact sensitive information
        self._redact_sensitive_data(log_data)
        
        # Ensure all data is JSON serializable
        try:
            return json.dumps(log_data)
        except (TypeError, ValueError):
            # Fallback if JSON serialization fails
            sanitized = {"message": "Error serializing log data", "original_message": self._safe_str(log_data)}
            return json.dumps(sanitized)
    
    def _safe_str(self, obj: Any) -> str:
        """Safely convert any object to string."""
        try:
            return str(obj)
        except Exception:
            return "<<Error converting to string>>"
    
    def _redact_sensitive_data(self, data: Any, path: str = "") -> None:
        """Recursively redact sensitive data."""
        if isinstance(data, dict):
            for key, value in list(data.items()):
                current_path = f"{path}.{key}" if path else key
                
                # Check if current key is sensitive
                is_sensitive = any(sensitive in str(key).lower() for sensitive in SENSITIVE_FIELDS)
                
                if is_sensitive and isinstance(value, (str, int, float)):
                    data[key] = "********"
                else:
                    self._redact_sensitive_data(value, current_path)
        
        elif isinstance(data, list):
            for i, item in enumerate(data):
                current_path = f"{path}[{i}]"
                self._redact_sensitive_data(item, current_path)


class TextFormatter(logging.Formatter):
    """Formatter for human-readable text logs."""
    
    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )


class ContextAdapter(logging.LoggerAdapter):
    """Logger adapter that adds context to all log messages."""
    
    def process(self, msg: str, kwargs: Dict[str, Any]) -> tuple:
        """Process log message, adding context."""
        # Ensure extra exists
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Add adapter's context to extra
        for key, value in self.extra.items():
            if key not in kwargs['extra']:
                kwargs['extra'][key] = value
        
        return msg, kwargs
    
    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log an exception with context."""
        super().exception(msg, *args, **kwargs)
        
        # Extract exception info
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type and exc_value:
            # Add more detailed exception info to the next debug log
            exc_details = {
                'exception_type': exc_type.__name__,
                'exception_message': str(exc_value),
            }
            self.debug(f"Exception details: {json.dumps(exc_details)}")


# Initialize module-level logger
_module_logger = None


def configure_logging() -> None:
    """Configure global logging settings."""
    # Clear any existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set log level
    try:
        log_level = getattr(logging, LOG_LEVEL)
    except AttributeError:
        log_level = logging.INFO
    root_logger.setLevel(log_level)
    
    # Create formatter based on format setting
    if LOG_FORMAT.lower() == "json":
        formatter = JsonFormatter()
    else:
        formatter = TextFormatter()
    
    # Create and configure handler
    if LOG_FILE:
        # Use rotating file handler
        try:
            handler = RotatingFileHandler(
                filename=LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT
            )
        except (IOError, PermissionError) as e:
            # Fall back to stdout if file creation fails
            sys.stderr.write(f"Error creating log file {LOG_FILE}: {e}. Using stdout instead.\n")
            handler = logging.StreamHandler(sys.stdout)
    else:
        # Use stdout
        handler = logging.StreamHandler(sys.stdout)
    
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_context_logger(
    name: str,
    trace_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    instance_id: Optional[str] = None,
    **additional_context
) -> logging.LoggerAdapter:
    """
    Get a logger with consistent context.
    
    Args:
        name: Logger name
        trace_id: Trace ID for request tracking
        user_id: User ID for user context
        session_id: Session ID for session context
        instance_id: Instance ID for instance context
        additional_context: Additional context key-value pairs
        
    Returns:
        Logger adapter with context
    """
    # Create base context
    context = additional_context.copy()
    
    # Add standard context if provided
    if trace_id:
        context["trace_id"] = trace_id
    if user_id:
        context["user_id"] = str(user_id)
    if session_id:
        context["session_id"] = str(session_id)
    if instance_id:
        context["instance_id"] = str(instance_id)
    
    # Get logger and wrap in adapter
    logger = logging.getLogger(name)
    return ContextAdapter(logger, context)


def with_context(
    logger_obj: Union[logging.Logger, logging.LoggerAdapter],
    **context
) -> logging.LoggerAdapter:
    """
    Create a new logger with additional context.
    
    Args:
        logger_obj: Existing logger or logger adapter
        **context: Additional context key-value pairs
        
    Returns:
        Logger adapter with merged context
    """
    # Use module-level logger if logger_obj is None or not appropriate
    if not isinstance(logger_obj, (logging.Logger, ContextAdapter)):
        # Fallback to creating a temporary logger
        temp_logger = logging.getLogger("temp")
        return ContextAdapter(temp_logger, context)
    
    if isinstance(logger_obj, ContextAdapter):
        # Merge with existing context
        new_context = logger_obj.extra.copy()
        new_context.update(context)
        return ContextAdapter(logger_obj.logger, new_context)
    elif isinstance(logger_obj, logging.Logger):
        # Add context to regular logger
        return ContextAdapter(logger_obj, context)
    else:
        # Fallback
        return cast(logging.LoggerAdapter, logger_obj)


# Configure logging at module load time
configure_logging()

# Initialize module-level logger after functions are defined
_module_logger = get_context_logger("logging_utils")