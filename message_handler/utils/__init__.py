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
    
    # Version
    "__version__"
]