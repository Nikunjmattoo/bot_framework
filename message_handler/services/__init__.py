"""
Service layer for business logic.

This module provides access to core service functions for handling messages,
users, sessions, instances, and related operations.
"""
from typing import Dict

# Service layer version for tracking compatibility
__version__ = "1.0.0"

# Import service functions with namespace organization
# to prevent namespace pollution and improve maintainability

# Identity services
from .identity_service import (
    resolve_user_web_app,
    resolve_user_whatsapp,
    resolve_user_guest
)

# Instance services
from .instance_service import (
    resolve_instance,
    resolve_instance_by_channel,
    get_instance_config
)

# Session services
from .session_service import (
    get_or_create_session,
    update_session_last_message
)

# Message services
from .message_service import (
    save_inbound_message,
    save_outbound_message,
    save_broadcast_message
)

# User context services
from .user_context_service import (
    prepare_user_context,
    prepare_whatsapp_user_context
)

# Idempotency services
from .idempotency_service import (
    create_idempotency_key,
    get_processed_message,
    mark_message_processed,
    idempotency_lock
)

# Token services
from .token_service import TokenManager

# Service function registry for dependency injection and testing
SERVICE_REGISTRY: Dict[str, Dict] = {
    "identity": {
        "resolve_user_web_app": resolve_user_web_app,
        "resolve_user_whatsapp": resolve_user_whatsapp,
        "resolve_user_guest": resolve_user_guest,
    },
    "instance": {
        "resolve_instance": resolve_instance,
        "resolve_instance_by_channel": resolve_instance_by_channel,
        "get_instance_config": get_instance_config,
    },
    "session": {
        "get_or_create_session": get_or_create_session,
        "update_session_last_message": update_session_last_message,
    },
    "message": {
        "save_inbound_message": save_inbound_message,
        "save_outbound_message": save_outbound_message,
        "save_broadcast_message": save_broadcast_message,
    },
    "user_context": {
        "prepare_user_context": prepare_user_context,
        "prepare_whatsapp_user_context": prepare_whatsapp_user_context,
    },
    "idempotency": {
        "create_idempotency_key": create_idempotency_key,
        "get_processed_message": get_processed_message,
        "mark_message_processed": mark_message_processed,
        "idempotency_lock": idempotency_lock,
    },
    "token": {
        "TokenManager": TokenManager,
    },
}

# Explicit exports to control the public API
__all__ = [
    # Identity
    "resolve_user_web_app",
    "resolve_user_whatsapp",
    "resolve_user_guest",
    
    # Instance
    "resolve_instance",
    "resolve_instance_by_channel",
    
    # Session
    "get_or_create_session",
    "update_session_last_message",
    
    # Message
    "save_inbound_message",
    "save_outbound_message",
    "save_broadcast_message",
    
    # User context
    "prepare_user_context",
    "prepare_whatsapp_user_context",
    
    # Idempotency
    "create_idempotency_key",
    "get_processed_message",
    "mark_message_processed",
    "idempotency_lock",
    
    # Token management
    "TokenManager",
    
    # Registry
    "SERVICE_REGISTRY",
    "__version__",
]