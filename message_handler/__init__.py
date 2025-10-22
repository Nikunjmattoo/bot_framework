"""
Message handling and processing for bot framework.

This module provides the main entry points for processing messages 
from different channels, coordinating between identity management, 
session tracking, and orchestration services.
"""
from typing import Dict, Any, List, Optional

from .handler import (
    process_message, 
    process_whatsapp_message, 
    broadcast_message,
    validate_message_content,
    get_handler_status
)

from .version import __version__, __author__, __license__

__all__ = [
    # Main entry points
    "process_message",
    "process_whatsapp_message", 
    "broadcast_message",
    
    # Utilities
    "validate_message_content",
    "get_handler_status",
    
    # Version information
    "__version__",
    "__author__",
    "__license__"
]