"""User context resolution and preparation."""
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from message_handler.exceptions import ValidationError, ResourceNotFoundError, UnauthorizedError
from message_handler.services.identity_service import (
    resolve_user_web_app, 
    resolve_user_whatsapp, 
    resolve_user_guest
)
from message_handler.services.instance_service import (
    resolve_instance,
    resolve_instance_by_channel,
    get_instance_config
)
from message_handler.services.session_service import get_or_create_session
from message_handler.utils.logging import get_context_logger

def prepare_user_context(
    db: Session,
    instance_id: str,
    user_details: Optional[Dict[str, Any]] = None,
    channel: str = "api",
    trace_id: Optional[str] = None
) -> Any:
    """
    Prepare user context for message processing.
    
    Args:
        db: Database session
        instance_id: Instance ID
        user_details: User details (optional)
        channel: Channel (default: "api")
        trace_id: Trace ID for logging (optional)
        
    Returns:
        User object with attached context
        
    Raises:
        ResourceNotFoundError: If instance or config not found
        UnauthorizedError: If user authentication fails
    """
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        instance_id=instance_id
    )
    
    # 1. Resolve the instance
    instance = resolve_instance(db, instance_id)
    if not instance:
        logger.error(f"Instance not found: {instance_id}")
        raise ResourceNotFoundError(f"Instance not found: {instance_id}")
    
    # 2. Get instance configuration
    instance_config = get_instance_config(db, instance_id)
    if not instance_config:
        logger.error(f"Configuration not found for instance: {instance_id}")
        raise ResourceNotFoundError(f"Configuration not found for instance: {instance_id}")
    
    # 3. Resolve the user with brand-scoped identity
    user = None
    if user_details:
        # Extract identifiers
        phone_e164 = user_details.get("phone_e164")
        email = user_details.get("email")
        device_id = user_details.get("device_id")
        auth_token = user_details.get("auth_token")
        
        user = resolve_user_web_app(
            db, phone_e164, email, device_id, auth_token,
            brand_id=instance.brand_id,
            channel=channel,
            accept_guest_users=getattr(instance, 'accept_guest_users', True)
        )
    
    if not user:
        # Check if guest users are allowed for this instance
        accept_guests = getattr(instance, 'accept_guest_users', True)
        if not accept_guests:
            logger.warning(f"Authentication required but not provided for instance {instance_id}")
            raise UnauthorizedError("Authentication required for this instance")
        
        # Create a guest user if allowed
        user = resolve_user_guest(db, channel)
        logger.info(f"Created guest user: {user.id}")
    
    if not user:
        logger.error("Unable to authenticate user")
        raise UnauthorizedError("Unable to authenticate user")
    
    # Update logger with user ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        instance_id=instance_id
    )
    
    # 4. Get or create a session
    session = get_or_create_session(db, user.id, instance_id)
    if not session:
        logger.error("Failed to create or retrieve session")
        raise ResourceNotFoundError("Failed to create or retrieve session")
    
    # Update logger with session ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        session_id=str(session.id),
        instance_id=instance_id
    )
    
    logger.info("User context prepared successfully")
        
    # Attach context to user object
    user.session = session
    user.session_id = session.id
    user.instance = instance
    user.instance_config = instance_config
    
    return user

def prepare_whatsapp_user_context(
    db: Session,
    whatsapp_data: Dict[str, Any],
    instance_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> Any:
    """
    Prepare user context for WhatsApp message.
    
    Args:
        db: Database session
        whatsapp_data: WhatsApp data from extract_whatsapp_data
        instance_id: Instance ID (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        User object with attached context
        
    Raises:
        ResourceNotFoundError: If instance or config not found
        UnauthorizedError: If user authentication fails
    """
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id
    )
    
    # Validate WhatsApp data
    if "from" not in whatsapp_data:
        logger.error("Missing 'from' in WhatsApp data")
        raise ValidationError("Missing 'from' in WhatsApp data")
    if "to" not in whatsapp_data:
        logger.error("Missing 'to' in WhatsApp data")
        raise ValidationError("Missing 'to' in WhatsApp data")
    
    # Resolve instance if not provided
    if not instance_id:
        instance = resolve_instance_by_channel(db, "whatsapp", whatsapp_data["to"])
        if not instance:
            logger.error(f"No WhatsApp instance found for recipient: {whatsapp_data['to']}")
            raise ResourceNotFoundError(f"No WhatsApp instance found for recipient: {whatsapp_data['to']}")
        instance_id = str(instance.id)
    else:
        instance = resolve_instance(db, instance_id)
        if not instance:
            logger.error(f"Instance not found: {instance_id}")
            raise ResourceNotFoundError(f"Instance not found: {instance_id}")
    
    # Update logger with instance ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        instance_id=instance_id
    )
    
    # Get instance configuration
    instance_config = get_instance_config(db, instance_id)
    if not instance_config:
        logger.error(f"Configuration not found for instance: {instance_id}")
        raise ResourceNotFoundError(f"Configuration not found for instance: {instance_id}")
    
    # Resolve WhatsApp user
    user = resolve_user_whatsapp(
        db, 
        whatsapp_data["from"], 
        brand_id=instance.brand_id,
        accept_guest_users=getattr(instance, 'accept_guest_users', True)
    )
    
    if not user:
        logger.error(f"Unable to authenticate WhatsApp user: {whatsapp_data['from']}")
        raise UnauthorizedError(f"Unable to authenticate WhatsApp user: {whatsapp_data['from']}")
    
    # Update logger with user ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        instance_id=instance_id
    )
    
    # Get or create session
    session = get_or_create_session(db, user.id, instance_id)
    if not session:
        logger.error("Failed to create or retrieve session")
        raise ResourceNotFoundError("Failed to create or retrieve session")
    
    # Update logger with session ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        session_id=str(session.id),
        instance_id=instance_id
    )
    
    logger.info("WhatsApp user context prepared successfully")
    
    # Attach context to user object
    user.session = session
    user.session_id = session.id
    user.instance = instance
    user.instance_config = instance_config
    
    return user