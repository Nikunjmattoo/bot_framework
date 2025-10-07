"""
Request handlers for different channels.

This module provides handlers for processing messages from different
channels (API, web, app, WhatsApp) and broadcasting messages to users.
"""

from .api_handler import process_api_message
from .whatsapp_handler import process_whatsapp_message_internal, extract_whatsapp_data
from .broadcast_handler import broadcast_message_internal
from .template_handler import update_template_config_internal

__version__ = "1.0.0"

__all__ = [
    # API/web/app handler
    "process_api_message",
    
    # WhatsApp handler
    "process_whatsapp_message_internal",
    "extract_whatsapp_data",
    
    # Broadcast handler
    "broadcast_message_internal",
    
    # Template handler
    "update_template_config_internal",
    
    # Version info
    "__version__"
]