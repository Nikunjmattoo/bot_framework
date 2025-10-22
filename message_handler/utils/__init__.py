"""
Utility functions for message handler.

This module provides common utility functions used throughout
the message handler, including transaction management and logging.
"""
from .transaction import (
    transaction_scope, 
    retry_transaction, 
    with_transaction,
    IsolationLevel
)
from .logging import (
    get_context_logger,
    with_context,
    configure_logging
)
from .datetime_utils import (
    ensure_timezone_aware,
    parse_iso_datetime,
    format_iso_datetime,
    get_current_datetime,
    update_session_timestamp,
    is_recent
)
from .data_utils import sanitize_data
from .validation import (
    validate_input,
    validate_and_raise,
    validate_content_length,
    validate_metadata_field_size
)
from .error_handling import (
    handle_database_error,
    with_error_handling
)

__version__ = "1.0.0"

__all__ = [
    # Transaction management
    "transaction_scope",
    "retry_transaction",
    "with_transaction",
    "IsolationLevel",
    
    # Logging
    "get_context_logger",
    "with_context",
    "configure_logging",
    
    # Datetime utilities
    "ensure_timezone_aware",
    "parse_iso_datetime",
    "format_iso_datetime",
    "get_current_datetime",
    "update_session_timestamp",
    "is_recent",
    
    # Data sanitization
    "sanitize_data",
    
    # Validation
    "validate_input",
    "validate_and_raise",
    "validate_content_length",
    "validate_metadata_field_size",
    
    # Error handling
    "handle_database_error",
    "with_error_handling",
    
    # Version
    "__version__"
]