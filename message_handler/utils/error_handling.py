"""
Error handling utilities for the message handler system.

This module provides common error handling functions used throughout
the message handler codebase.
"""
from typing import Optional, Any, Dict, Type, Union, List
from message_handler.exceptions import (
    DatabaseError, ErrorCode, ValidationError, ResourceNotFoundError, OrchestrationError
)
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError
from message_handler.exceptions import DatabaseError, ErrorCode
from message_handler.utils.logging import get_context_logger
import functools
from typing import Callable, TypeVar, Dict, Any, Optional, Union, Type, List, Tuple

# Type variables for generic decorator
T = TypeVar('T')
R = TypeVar('R')

def handle_database_error(
    exception: Exception, 
    operation: str, 
    logger: Any = None, 
    trace_id: Optional[str] = None,
    error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
    details: Optional[Dict[str, Any]] = None,
    field: Optional[str] = None
) -> None:
    """
    Standardized handler for database errors.
    
    Args:
        exception: The exception that occurred
        operation: Description of the operation that failed
        logger: Logger instance to use (optional)
        trace_id: Trace ID for logging context (optional)
        error_code: Error code to use (default: DATABASE_ERROR)
        details: Additional error details (optional)
        field: Field name associated with the error (optional)
        
    Raises:
        DatabaseError: A standardized error wrapping the original exception
    """
    # Create logger if not provided
    if logger is None:
        logger = get_context_logger("database", trace_id=trace_id)
    
    # Build error message
    error_msg = f"Database error in {operation}: {str(exception)}"
    
    # Prepare error details
    error_details = details or {}
    error_details["operation"] = operation
    
    # Detect specific database error types
    if isinstance(exception, IntegrityError):
        # Handle integrity errors (constraint violations, etc.)
        error_code = ErrorCode.DATABASE_CONSTRAINT_ERROR
        if "duplicate key" in str(exception).lower() or "unique constraint" in str(exception).lower():
            error_msg = f"Duplicate data in {operation}: {str(exception)}"
            error_details["error_type"] = "duplicate_key"
    
    elif isinstance(exception, OperationalError):
        # Handle operational errors (connection issues, timeouts, etc.)
        if "timeout" in str(exception).lower() or "timed out" in str(exception).lower():
            error_code = ErrorCode.TIMEOUT_ERROR
            error_msg = f"Database timeout in {operation}: {str(exception)}"
            error_details["error_type"] = "timeout"
        elif "connection" in str(exception).lower():
            error_code = ErrorCode.DATABASE_CONNECTION_ERROR
            error_msg = f"Database connection error in {operation}: {str(exception)}"
            error_details["error_type"] = "connection_error"
    
    # Log the error
    logger.error(error_msg)
    
    # Create and raise standardized error
    raise DatabaseError(
        error_msg,
        error_code=error_code,
        original_exception=exception,
        operation=operation,
        details=error_details,
        field=field
    )


def is_safe_to_retry(exception: Exception) -> bool:
    """
    Determine if an exception is safe to retry.
    
    Args:
        exception: The exception to check
        
    Returns:
        True if the exception is retryable, False otherwise
    """
    # Deadlocks, lock timeouts, connection issues are typically retryable
    if isinstance(exception, OperationalError):
        error_str = str(exception).lower()
        return (
            "deadlock" in error_str or
            "lock timeout" in error_str or
            "connection" in error_str or
            "lost connection" in error_str or
            "timeout" in error_str
        )
    
    # Some transaction serialization errors can be retried
    if isinstance(exception, SQLAlchemyError):
        error_str = str(exception).lower()
        return (
            "serialization" in error_str or
            "could not serialize" in error_str or
            "retry transaction" in error_str
        )
    
    return False

def with_error_handling(
    operation_name: Optional[str] = None,
    expected_exceptions: Optional[Dict[Type[Exception], ErrorCode]] = None,
    trace_id_param: str = 'trace_id',
    logger_param: str = 'logger',
    db_param: str = 'db',
    reraise: List[Type[Exception]] = []
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator to standardize error handling across the codebase.
    
    Args:
        operation_name: Name of the operation (defaults to function name if None)
        expected_exceptions: Mapping of exception types to error codes
        trace_id_param: Name of the parameter containing trace_id
        logger_param: Name of the parameter containing logger
        db_param: Name of the parameter containing database session
        reraise: List of exception types to re-raise without wrapping
        
    Returns:
        Decorated function with standardized error handling
    """
    # Import at function level to avoid circular imports
    from message_handler.exceptions import (
        DuplicateError, UnauthorizedError, ResourceNotFoundError, 
        ValidationError, OrchestrationError
    )
    
    # Default mapping of exceptions to error codes
    default_exceptions = {
        SQLAlchemyError: ErrorCode.DATABASE_ERROR,
        IntegrityError: ErrorCode.DATABASE_CONSTRAINT_ERROR,
        OperationalError: ErrorCode.DATABASE_CONNECTION_ERROR,
        ValueError: ErrorCode.VALIDATION_ERROR,
        KeyError: ErrorCode.VALIDATION_ERROR,
        TypeError: ErrorCode.VALIDATION_ERROR
    }
    
    # Use provided exceptions or defaults
    exception_mapping = expected_exceptions or default_exceptions
    
    # CRITICAL: Always reraise these custom exceptions so they reach the API layer
    always_reraise = [
        ValidationError,
        ResourceNotFoundError, 
        UnauthorizedError,
        DuplicateError,
        OrchestrationError
    ]
    
    # Combine with user-provided reraise list
    all_reraise = list(set(always_reraise + reraise))
    
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            # Use provided operation name or function name
            operation = operation_name or func.__name__
            
            # Extract trace_id and logger from kwargs if available
            trace_id = kwargs.get(trace_id_param)
            logger = kwargs.get(logger_param)
            
            # Create logger if not provided
            if logger is None:
                logger = get_context_logger(operation, trace_id=trace_id)
            
            try:
                # Call the original function
                return func(*args, **kwargs)
                
            except tuple(all_reraise) as e:
                # Re-raise custom exceptions without wrapping
                # Log but don't wrap - let API layer handle HTTP status mapping
                logger.error(f"Error in {operation}: {str(e)}")
                raise
                
            except Exception as e:
                # Handle unexpected exceptions
                error_code = ErrorCode.INTERNAL_ERROR
                
                # Check if exception type is in our mapping
                for exc_type, code in exception_mapping.items():
                    if isinstance(e, exc_type):
                        error_code = code
                        break
                
                # Handle database errors specially
                if isinstance(e, SQLAlchemyError):
                    db = kwargs.get(db_param)
                    if db and hasattr(db, 'rollback'):
                        try:
                            db.rollback()
                            logger.info(f"Rolled back transaction in {operation} after error")
                        except Exception as rollback_error:
                            logger.warning(f"Failed to rollback transaction: {str(rollback_error)}")
                    
                    # Use database error handler
                    handle_database_error(
                        e, operation, logger, trace_id=trace_id, error_code=error_code
                    )
                else:
                    # For non-database errors, create a standardized error message
                    error_msg = f"Error in {operation}: {str(e)}"
                    logger.error(error_msg)
                    
                    # Raise a generic error
                    raise DatabaseError(
                        error_msg,
                        error_code=error_code,
                        original_exception=e,
                        operation=operation
                    )
                    
        return wrapper
    return decorator