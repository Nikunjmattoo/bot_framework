"""
Adapters for converting data between layers.

This module provides adapters for transforming data between
different layers of the application, such as from internal
models to external API formats.
"""
from .message_adapter import build_message_adapter, sanitize_adapter, validate_adapter

__version__ = "1.0.0"

__all__ = [
    "build_message_adapter",
    "sanitize_adapter",
    "validate_adapter",
    "__version__"
]