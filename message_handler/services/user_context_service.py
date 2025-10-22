"""User context resolution and preparation."""
from typing import Dict, Any, Optional, Union, cast
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from message_handler.exceptions import ValidationError, ResourceNotFoundError, UnauthorizedError, ErrorCode
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
        user_details: User details (optional) - should contain phone_e164, email, device_id, auth_token
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
        raise ResourceNotFoundError(
            f"Instance not found: {instance_id}",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="instance",
            resource_id=instance_id
        )
    
    # 2. Get instance configuration
    instance_config = get_instance_config(db, instance_id)
    if not instance_config:
        logger.error(f"Configuration not found for instance: {instance_id}")
        raise ResourceNotFoundError(
            f"Configuration not found for instance: {instance_id}",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="instance_config",
            resource_id=instance_id
        )
    
    # 3. Resolve the user with brand-scoped identity
    user = None
    brand_id = getattr(instance, 'brand_id', None)
    if not brand_id:
        logger.error(f"Instance missing brand_id: {instance_id}")
        raise ResourceNotFoundError(
            f"Instance missing brand_id: {instance_id}",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="instance.brand_id",
            resource_id=instance_id
        )

    # Try to resolve user if user_details provided
    if user_details:
        # Extract identifiers from user_details
        phone_e164 = user_details.get("phone_e164")
        email = user_details.get("email")
        device_id = user_details.get("device_id")
        auth_token = user_details.get("auth_token")
        
        # CRITICAL: Only call resolve_user_web_app if we have at least one identifier
        if any([phone_e164, email, device_id, auth_token]):
            user = resolve_user_web_app(
                db, 
                phone_e164=phone_e164, 
                email=email, 
                device_id=device_id, 
                auth_token=auth_token,
                brand_id=brand_id,
                channel=channel,
                accept_guest_users=getattr(instance, 'accept_guest_users', True),
                trace_id=trace_id
            )
    
    # If no user found and guest users are not allowed, reject
    if not user:
        accept_guests = getattr(instance, 'accept_guest_users', True)
        if not accept_guests:
            logger.warning(f"Authentication required but not provided for instance {instance_id}")
            raise UnauthorizedError(
                "Authentication required for this instance",
                error_code=ErrorCode.UNAUTHORIZED,
                details={"instance_id": instance_id, "channel": channel}
            )
        
        # Create a guest user if allowed and no user was found/created
        logger.info(f"Creating guest user for instance {instance_id}")
        user = resolve_user_guest(db, channel, trace_id=trace_id)
        if not user:
            logger.error("Unable to create guest user")
            raise UnauthorizedError(
                "Unable to create guest user",
                error_code=ErrorCode.UNAUTHORIZED,
                details={"instance_id": instance_id, "channel": channel}
            )
        logger.info(f"Created guest user: {user.id}")
    
    # Final safety check
    if not user:
        logger.error("Unable to authenticate user")
        raise UnauthorizedError(
            "Unable to authenticate user",
            error_code=ErrorCode.UNAUTHORIZED,
            details={"instance_id": instance_id, "channel": channel}
        )
    
    # Update logger with user ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        instance_id=instance_id
    )
    
    # 4. Get or create a session
    session = get_or_create_session(db, user.id, instance_id, trace_id=trace_id)
    if not session:
        logger.error("Failed to create or retrieve session")
        raise ResourceNotFoundError(
            "Failed to create or retrieve session",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="session",
            details={"user_id": str(user.id), "instance_id": instance_id}
        )
    
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
        raise ValidationError(
            "Missing 'from' in WhatsApp data",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="from"
        )
    if "to" not in whatsapp_data:
        logger.error("Missing 'to' in WhatsApp data")
        raise ValidationError(
            "Missing 'to' in WhatsApp data",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="to"
        )
    
    # Get sender and recipient numbers
    from_number = whatsapp_data.get("from")
    to_number = whatsapp_data.get("to")
    
    # Resolve instance if not provided
    resolved_instance = None
    resolved_instance_id = None
    
    if not instance_id:
        resolved_instance = resolve_instance_by_channel(db, "whatsapp", to_number)
        if not resolved_instance:
            logger.error(f"No WhatsApp instance found for recipient: {to_number}")
            raise ResourceNotFoundError(
                f"No WhatsApp instance found for recipient: {to_number}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="whatsapp_instance",
                resource_id=to_number
            )
        resolved_instance_id = str(resolved_instance.id)
    else:
        resolved_instance = resolve_instance(db, instance_id)
        if not resolved_instance:
            logger.error(f"Instance not found: {instance_id}")
            raise ResourceNotFoundError(
                f"Instance not found: {instance_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance",
                resource_id=instance_id
            )
        resolved_instance_id = instance_id
    
    # Update logger with instance ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        instance_id=resolved_instance_id
    )
    
    # Get instance configuration
    instance_config = get_instance_config(db, resolved_instance_id)
    if not instance_config:
        logger.error(f"Configuration not found for instance: {resolved_instance_id}")
        raise ResourceNotFoundError(
            f"Configuration not found for instance: {resolved_instance_id}",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="instance_config",
            resource_id=resolved_instance_id
        )
    
    # Resolve WhatsApp user
    brand_id = getattr(resolved_instance, 'brand_id', None)
    if not brand_id:
        logger.error(f"Instance missing brand_id: {resolved_instance_id}")
        raise ResourceNotFoundError(
            f"Instance missing brand_id: {resolved_instance_id}",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="instance.brand_id",
            resource_id=resolved_instance_id
        )
    
    user = resolve_user_whatsapp(
        db, 
        from_number, 
        brand_id=brand_id,
        accept_guest_users=getattr(resolved_instance, 'accept_guest_users', True),
        trace_id=trace_id
    )
    
    if not user:
        logger.error(f"Unable to authenticate WhatsApp user: {from_number}")
        raise UnauthorizedError(
            f"Unable to authenticate WhatsApp user: {from_number}",
            error_code=ErrorCode.UNAUTHORIZED,
            details={"instance_id": resolved_instance_id, "from": from_number}
        )
    
    # Update logger with user ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        instance_id=resolved_instance_id
    )
    
    # Get or create session
    session = get_or_create_session(db, user.id, resolved_instance_id, trace_id=trace_id)
    if not session:
        logger.error("Failed to create or retrieve session")
        raise ResourceNotFoundError(
            "Failed to create or retrieve session",
            error_code=ErrorCode.RESOURCE_NOT_FOUND,
            resource_type="session",
            details={"user_id": str(user.id), "instance_id": resolved_instance_id}
        )
    
    # Update logger with session ID
    logger = get_context_logger(
        "user_context", 
        trace_id=trace_id,
        user_id=str(user.id),
        session_id=str(session.id),
        instance_id=resolved_instance_id
    )
    
    logger.info("WhatsApp user context prepared successfully")
    
    # Attach context to user object
    user.session = session
    user.session_id = session.id
    user.instance = resolved_instance
    user.instance_config = instance_config
    
    return user