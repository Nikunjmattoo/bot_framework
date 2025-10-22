"""Transaction management utilities."""
from contextlib import contextmanager
from typing import Any, Optional, Callable, TypeVar, Generic
import time
import functools
import threading
from enum import Enum

from sqlalchemy import event
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError, SQLAlchemyError, OperationalError, IntegrityError, TimeoutError

from message_handler.utils.logging import get_context_logger
from message_handler.exceptions import (
    DatabaseError, ErrorCode
)

# Type variables for generic functions
T = TypeVar('T')
R = TypeVar('R')

# Use context logger for consistent logging
logger = get_context_logger("transaction")

# Transaction isolation levels
class IsolationLevel(str, Enum):
    """SQL transaction isolation levels."""
    READ_UNCOMMITTED = "READ UNCOMMITTED"
    READ_COMMITTED = "READ COMMITTED"
    REPEATABLE_READ = "REPEATABLE READ"
    SERIALIZABLE = "SERIALIZABLE"


@contextmanager
def transaction_scope(
    db: Session, 
    trace_id: Optional[str] = None,
    isolation_level: Optional[IsolationLevel] = None,
    readonly: bool = False,
    timeout_seconds: int = 30
) -> Any:
    """
    Provide a transactional scope around a series of operations.
    
    Args:
        db: Database session
        trace_id: Trace ID for logging (optional)
        isolation_level: SQL transaction isolation level (optional)
        readonly: If True, transaction is read-only (optional)
        timeout_seconds: Transaction timeout in seconds (optional)
        
    Yields:
        Database session for use in operations
        
    Raises:
        DatabaseError: If a database error occurs
        Original exception: Any other exception that occurred in the with block
    """
    logger = get_context_logger("transaction", trace_id=trace_id)
    
    # Set transaction start time for timeout detection
    start_time = time.time()
    
    # Create a thread-local flag for timeout tracking
    timeout_flag = threading.local()
    timeout_flag.timed_out = False
    
    # Function to check for timeout
    def check_timeout():
        if timeout_seconds > 0 and time.time() - start_time > timeout_seconds:
            timeout_flag.timed_out = True
            logger.error(f"Transaction timeout after {timeout_seconds} seconds")
            raise DatabaseError(
                f"Transaction timeout after {timeout_seconds} seconds",
                error_code=ErrorCode.TIMEOUT_ERROR,
                details={"timeout_seconds": timeout_seconds}
            )
    
    # For very long operations, setup a timer to periodically check timeout
    if timeout_seconds > 0:
        def timeout_checker():
            if not timeout_flag.timed_out and time.time() - start_time > timeout_seconds:
                timeout_flag.timed_out = True
                logger.error(f"Transaction timeout after {timeout_seconds} seconds")
                # Cannot raise exception from thread, just set the flag
        
        timer = threading.Timer(timeout_seconds / 2.0, timeout_checker)
        timer.daemon = True
        timer.start()
    else:
        timer = None
    
    # Set transaction isolation level if specified
    if isolation_level and hasattr(db, 'execute'):
        try:
            db.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation_level.value}")
            logger.debug(f"Set transaction isolation level to {isolation_level.value}")
        except Exception as e:
            logger.warning(f"Failed to set isolation level: {str(e)}")
    
    # Set read-only if specified
    if readonly and hasattr(db, 'execute'):
        try:
            db.execute("SET TRANSACTION READ ONLY")
            logger.debug("Set transaction to READ ONLY")
        except Exception as e:
            logger.warning(f"Failed to set read-only mode: {str(e)}")
    
    try:
        logger.debug("Transaction started")
        check_timeout()  # Check timeout before yielding
        yield db
        check_timeout()  # Check timeout before commit
        
        # Cancel the timer if it exists
        if timer:
            timer.cancel()
            
        if timeout_flag.timed_out:
            logger.error("Transaction timed out during execution")
            db.rollback()
            raise DatabaseError(
                f"Transaction timed out after {timeout_seconds} seconds",
                error_code=ErrorCode.TIMEOUT_ERROR,
                details={"timeout_seconds": timeout_seconds}
            )
            
        db.commit()
        logger.debug("Transaction committed successfully")
    except OperationalError as e:
        if timer:
            timer.cancel()
        db.rollback()
        logger.error(f"Database operational error: {str(e)}")
        
        # Re-raise the original OperationalError so retry_transaction can handle it
        raise
    except SQLAlchemyError as e:
        if timer:
            timer.cancel()
        db.rollback()
        logger.error(f"Database error: {type(e).__name__}: {str(e)}")
        raise DatabaseError(
            f"Database error: {str(e)}",
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="transaction"
        )
    except Exception as e:
        if timer:
            timer.cancel()
        db.rollback()
        logger.error(f"Transaction rolled back due to: {type(e).__name__}: {str(e)}")
        # Re-raise the original exception
        raise


def with_transaction(
    trace_id_arg: str = 'trace_id',
    isolation_level: Optional[IsolationLevel] = None,
    readonly: bool = False,
    timeout_seconds: int = 30
) -> Callable[[Callable[..., R]], Callable[..., R]]:
    """
    Decorator to wrap a function in a transaction.
    
    Args:
        trace_id_arg: Name of the function argument containing trace_id
        isolation_level: SQL transaction isolation level
        readonly: If True, transaction is read-only
        timeout_seconds: Transaction timeout in seconds
        
    Returns:
        Decorated function
        
    Example:
        @with_transaction(trace_id_arg='trace_id')
        def process_data(db, user_id, data, trace_id=None):
            # This function will be wrapped in a transaction
            pass
    """
    def decorator(func: Callable[..., R]) -> Callable[..., R]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> R:
            # Find the database session argument
            db = None
            for arg in args:
                if isinstance(arg, Session):
                    db = arg
                    break
            
            if db is None and 'db' in kwargs:
                db = kwargs['db']
                
            if db is None:
                raise ValueError("Database session not found in arguments")
                
            # Get trace_id from kwargs if available
            trace_id = kwargs.get(trace_id_arg)
                
            # Execute the function within a transaction
            with transaction_scope(
                db, 
                trace_id=trace_id,
                isolation_level=isolation_level,
                readonly=readonly,
                timeout_seconds=timeout_seconds
            ):
                return func(*args, **kwargs)
                
        return wrapper
    return decorator


@contextmanager
def retry_transaction(
    db: Session, 
    trace_id: Optional[str] = None,
    max_retries: int = 3,
    retry_delay_ms: int = 100,
    max_retry_delay_ms: int = 2000,
    retryable_errors: tuple = (OperationalError, IntegrityError, TimeoutError),
    isolation_level: Optional[IsolationLevel] = None,
    readonly: bool = False,
    timeout_seconds: int = 30
) -> Any:
    """
    Provide a transactional scope with automatic retries for deadlocks and similar issues.
    
    Args:
        db: Database session
        trace_id: Trace ID for logging (optional)
        max_retries: Maximum number of retry attempts
        retry_delay_ms: Initial retry delay in milliseconds
        max_retry_delay_ms: Maximum retry delay in milliseconds
        retryable_errors: Tuple of exception types that trigger retry
        isolation_level: SQL transaction isolation level
        readonly: If True, transaction is read-only
        timeout_seconds: Transaction timeout in seconds
        
    Yields:
        Database session for use in operations
        
    Raises:
        DatabaseError: If a database error occurs after max retries
        Original exception: Any other exception that occurred in the with block
    """
    logger = get_context_logger("transaction", trace_id=trace_id)
    
    attempt = 0
    delay_ms = retry_delay_ms
    last_error = None
    
    while attempt < max_retries:
        attempt += 1
        try:
            with transaction_scope(
                db, 
                trace_id=trace_id, 
                isolation_level=isolation_level,
                readonly=readonly,
                timeout_seconds=timeout_seconds
            ) as session:
                yield session
                return  # Success, exit
        except retryable_errors as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(
                    f"Transaction error (attempt {attempt}/{max_retries}), "
                    f"retrying in {delay_ms}ms: {str(e)}"
                )
                time.sleep(delay_ms / 1000)
                # Exponential backoff with jitter
                import random
                delay_ms = min(
                    delay_ms * 2, 
                    max_retry_delay_ms
                ) + random.randint(0, min(100, delay_ms))
                # Continue to next retry
                continue
            else:
                logger.error(f"Transaction failed after {max_retries} attempts: {str(e)}")
                raise DatabaseError(
                    f"Transaction failed after {max_retries} attempts",
                    error_code=ErrorCode.DATABASE_ERROR,
                    original_exception=e,
                    details={"attempts": attempt, "max_retries": max_retries}
                )
        except Exception as e:
            # Don't retry on non-retryable exceptions
            logger.error(f"Non-retryable error in transaction: {type(e).__name__}: {str(e)}")
            raise
    
    # If we exhausted retries
    if last_error:
        raise DatabaseError(
            "Transaction failed after retries",
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=last_error
        )