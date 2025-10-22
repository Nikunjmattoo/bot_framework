"""
Core processing logic.

This module provides the core processing logic for handling
messages, including the main entry point for message processing
that is used by all channel handlers.
"""
from .processor import process_core

__version__ = "1.0.0"

__all__ = [
    "process_core",
    "__version__"
]