"""
Handler for WhatsApp message processing.

This module provides functions for extracting and processing messages
from the WhatsApp channel, with support for different message types.
"""
import uuid
import time
import re
from typing import Dict, Any, Optional, List, Union, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError, 
    UnauthorizedError, DuplicateError, ErrorCode
)
from message_handler.services.idempotency_service import (
    create_idempotency_key, get_processed_message, 
    mark_message_processed, idempotency_lock
)
from message_handler.services.token_service import TokenManager
from message_handler.services.user_context_service import prepare_whatsapp_user_context
from message_handler.core.processor import process_core
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import transaction_scope, retry_transaction
from message_handler.utils.validation import validate_phone, PHONE_REGEX
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime

# Constants
MAX_RETRY_ATTEMPTS = 3
SUPPORTED_MESSAGE_TYPES = ["text", "image", "audio", "document", "location", "contact", "contacts"]

def validate_whatsapp_message(
    whatsapp_message: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> None:
    """
    Validate WhatsApp message structure.
    
    Args:
        whatsapp_message: WhatsApp message object
        metadata: Additional metadata (optional)
        trace_id: Trace ID for logging (optional)
        
    Raises:
        ValidationError: If validation fails
    """
    logger = get_context_logger("whatsapp_handler", trace_id=trace_id)
    
    # Check if message is provided
    if not whatsapp_message:
        logger.warning("WhatsApp message cannot be empty")
        raise ValidationError(
            "WhatsApp message cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="whatsapp_message"
        )
    
    # Check if 'from' field exists and is valid
    if "from" not in whatsapp_message:
        logger.warning("WhatsApp 'from' field is missing")
        raise ValidationError(
            "WhatsApp 'from' field is missing",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="from"
        )
    
    # Validate phone number format
    from_number = whatsapp_message.get("from", "")
    is_valid, error_msg, _ = validate_phone(from_number, field_name="from")
    if not is_valid and error_msg:
        logger.warning(f"Invalid 'from' phone number format: {from_number}")
        raise ValidationError(
            error_msg,
            error_code=ErrorCode.VALIDATION_ERROR,
            field="from",
            value=from_number
        )
    
    # Check for recipient number (from metadata or message)
    to_number = None
    if metadata and isinstance(metadata, dict) and "to" in metadata:
        to_number = metadata.get("to")
    elif "to" in whatsapp_message:
        to_number = whatsapp_message.get("to")
        
    if not to_number:
        logger.warning("Recipient number not available in WhatsApp message")
        raise ValidationError(
            "Recipient number not available in WhatsApp message",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="to"
        )
    
    # Validate recipient number format
    is_valid, error_msg, _ = validate_phone(to_number, field_name="to")
    if not is_valid and error_msg:
        logger.warning(f"Invalid 'to' phone number format: {to_number}")
        raise ValidationError(
            error_msg,
            error_code=ErrorCode.VALIDATION_ERROR,
            field="to",
            value=to_number
        )
    
    # Check if the message has any supported content type
    has_content = False
    for content_type in SUPPORTED_MESSAGE_TYPES:
        if content_type in whatsapp_message:
            has_content = True
            break
    
    if not has_content:
        logger.warning("Unsupported WhatsApp message type")
        raise ValidationError(
            f"Unsupported WhatsApp message type. Supported types: {', '.join(SUPPORTED_MESSAGE_TYPES)}",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="message_type"
        )

def extract_whatsapp_data(
    whatsapp_message: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract data from WhatsApp message format.
    
    Args:
        whatsapp_message: WhatsApp message object
        metadata: Additional metadata (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Dict with extracted data containing:
            - from: Sender phone number
            - to: Recipient phone number
            - content: Message content
            - type: Message type (text, image, audio, etc.)
            - message_id: WhatsApp message ID
            - metadata: Additional metadata
        
    Raises:
        ValidationError: If message validation fails
    """
    logger = get_context_logger("whatsapp_handler", trace_id=trace_id)
    
    # Validate the message structure
    validate_whatsapp_message(whatsapp_message, metadata, trace_id)
    
    # Extract base metadata
    wa_metadata = metadata or {}
    
    # Extract phone numbers
    wa_from = whatsapp_message.get("from")
    wa_to = wa_metadata.get("to") if isinstance(wa_metadata, dict) else None
    if not wa_to:
        wa_to = whatsapp_message.get("to")
    
    # Extract message ID
    message_id = whatsapp_message.get("id", "")
    
    # Extract timestamp if available
    timestamp = whatsapp_message.get("timestamp", "")
    
    # Determine message type and content
    message_type = "unknown"
    message_content = ""
    media_url = None
    
    # Text message
    if "text" in whatsapp_message and isinstance(whatsapp_message["text"], dict) and "body" in whatsapp_message["text"]:
        message_type = "text"
        message_content = whatsapp_message["text"]["body"]
    
    # Image message
    elif "image" in whatsapp_message and isinstance(whatsapp_message["image"], dict):
        message_type = "image"
        message_content = "[IMAGE]"
        if "caption" in whatsapp_message["image"]:
            message_content += f": {whatsapp_message['image']['caption']}"
        media_url = whatsapp_message["image"].get("url")
    
    # Audio message
    elif "audio" in whatsapp_message and isinstance(whatsapp_message["audio"], dict):
        message_type = "audio"
        message_content = "[AUDIO]"
        media_url = whatsapp_message["audio"].get("url")
    
    # Document message
    elif "document" in whatsapp_message and isinstance(whatsapp_message["document"], dict):
        message_type = "document"
        doc_info = whatsapp_message["document"]
        filename = doc_info.get("filename", "unnamed")
        message_content = f"[DOCUMENT: {filename}]"
        if "caption" in doc_info:
            message_content += f": {doc_info['caption']}"
        media_url = doc_info.get("url")
    
    # Location message
    elif "location" in whatsapp_message and isinstance(whatsapp_message["location"], dict):
        message_type = "location"
        loc_info = whatsapp_message["location"]
        lat = loc_info.get("latitude", "unknown")
        lng = loc_info.get("longitude", "unknown")
        message_content = f"[LOCATION: {lat},{lng}]"
        if "name" in loc_info:
            message_content += f": {loc_info['name']}"
    
    # Contact message
    elif "contact" in whatsapp_message or "contacts" in whatsapp_message:
        message_type = "contact"
        contacts = whatsapp_message.get("contacts", whatsapp_message.get("contact", []))
        contact_names = []
        for contact in contacts:
            if isinstance(contact, dict) and "name" in contact and isinstance(contact["name"], dict):
                name_parts = []
                name_info = contact["name"]
                if name_info.get("formatted_name"):
                    name_parts.append(name_info["formatted_name"])
                elif name_info.get("first_name"):
                    name_parts.append(name_info["first_name"])
                    if name_info.get("last_name"):
                        name_parts.append(name_info["last_name"])
                contact_names.append(" ".join(name_parts) or "Unknown contact")
        
        message_content = f"[CONTACT: {', '.join(contact_names or ['Unknown contact'])}]"
    
    # Combine into result
    result = {
        "from": wa_from,
        "to": wa_to,
        "content": message_content,
        "type": message_type,
        "message_id": message_id,
        "timestamp": timestamp,
        "metadata": {
            "source": "whatsapp",
            "media_url": media_url,
            "original": {
                "message_type": message_type,
                # Include whitelisted fields from the original message
                "id": message_id,
                "from": wa_from,
                "to": wa_to,
                "timestamp": timestamp
            }
        }
    }
    
    logger.info(f"Extracted WhatsApp {message_type} message from {wa_from} to {wa_to}")
    return result


def process_whatsapp_message_internal(
    db: Session,
    whatsapp_message: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    instance_id: Optional[str] = None,
    request_id: str = None,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Process a WhatsApp message.
    
    Args:
        db: Database session
        whatsapp_message: WhatsApp message object
        metadata: Additional metadata (optional)
        instance_id: Instance ID (optional)
        request_id: Client-provided request ID (required)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Result data dict with message ID and response information
        
    Raises:
        ValidationError: If message validation fails
        ResourceNotFoundError: If instance or user not found
        UnauthorizedError: If user authentication fails
        DuplicateError: If concurrent request in progress
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    start_time = time.time()
    
    logger = get_context_logger("whatsapp_handler", trace_id=trace_id)
    
    logger.info("Processing WhatsApp message")
    
    try:
        # 1. Extract data from WhatsApp message
        wa_data = extract_whatsapp_data(whatsapp_message, metadata, trace_id)
        
        # 2. For WhatsApp, resolve instance FIRST to get instance_id
        # (needed for idempotency key generation)
        if not instance_id:
            from message_handler.services.instance_service import resolve_instance_by_channel
            instance = resolve_instance_by_channel(db, channel="whatsapp", recipient_number=wa_data["to"])
            if not instance:
                raise ResourceNotFoundError(
                    f"No WhatsApp instance found for recipient: {wa_data['to']}",
                    error_code=ErrorCode.RESOURCE_NOT_FOUND,
                    resource_type="instance",
                    resource_id=wa_data["to"]
                )
            instance_id = str(instance.id)

        # 3. Prepare WhatsApp user context (gets session)
        user = prepare_whatsapp_user_context(db, wa_data, instance_id, trace_id)
        
        # 4. Create scoped idempotency key from client-provided request_id
        idempotency_key = create_idempotency_key(
            request_id=request_id,
            instance_id=instance_id,
            session_id=str(user.session.id) if user and hasattr(user, 'session') else None
        )
        logger.info(f"Created idempotency key: {idempotency_key}")
        
        # 5. Check for duplicate message (idempotency)
        cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
        if cached_response:
            logger.info(f"Returning cached response for idempotency key: {idempotency_key}")
            return cached_response
        
        # 6. Process with idempotency lock
        with idempotency_lock(db, idempotency_key, trace_id=trace_id) as lock_result:
            # If lock_result is False, a cached result may now be available
            if lock_result is False:
                # Try to get the cached response again with retries
                for retry in range(MAX_RETRY_ATTEMPTS):
                    cached_response = get_processed_message(db, idempotency_key, trace_id=trace_id)
                    if cached_response:
                        logger.info(f"Found cached response after lock check (retry {retry})")
                        return cached_response
                    
                    # Short delay before retry
                    time.sleep(0.1 * (retry + 1))
                        
                logger.warning("Lock manager indicated cached result but none found after retries")
                # Continue with processing as fallback
            
            # 7. Process within a transaction 
            with transaction_scope(db, trace_id=trace_id) as tx:
                # Initialize token management if session exists
                if user and hasattr(user, 'session') and user.session:
                    try:
                        token_manager = TokenManager()
                        token_manager.initialize_session(tx, str(user.session.id), trace_id)
                        logger.debug("Token plan initialized for session")
                    except Exception as e:
                        logger.warning(f"Error initializing token plan: {str(e)}")
                        # Continue processing even if token initialization fails
                
                # Prepare meta info (this will be stored in metadata_json)
                meta_info = {
                    "channel": "whatsapp",
                    "message_type": wa_data["type"],
                    "whatsapp_message_id": wa_data["message_id"],
                    "whatsapp_from": wa_data["from"],
                    "whatsapp_to": wa_data["to"],
                    "whatsapp_timestamp": wa_data["timestamp"]
                }
                
                if "metadata" in wa_data and isinstance(wa_data["metadata"], dict):
                    meta_info.update(wa_data["metadata"])
                
                # Process the message
                result_data = process_core(
                    tx, 
                    wa_data["content"], 
                    user.instance.id if hasattr(user, 'instance') and hasattr(user.instance, 'id') else instance_id, 
                    user=user,
                    request_id=idempotency_key,
                    trace_id=trace_id,
                    channel="whatsapp",
                    meta_info=meta_info
                )
                
                # Add WhatsApp-specific result info
                if isinstance(result_data, dict):
                    result_data["whatsapp_message_id"] = wa_data["message_id"]
                    result_data["whatsapp_from"] = wa_data["from"]
                
                # Mark as processed for idempotency
                mark_message_processed(tx, idempotency_key, result_data, trace_id)
                
                processing_time = time.time() - start_time
                logger.info(f"WhatsApp message processed successfully in {processing_time:.2f}s")
                
                # Add processing metadata to result
                if isinstance(result_data, dict) and "_meta" not in result_data:
                    result_data["_meta"] = {
                        "processing_time_seconds": round(processing_time, 3),
                        "trace_id": trace_id,
                        "channel": "whatsapp",
                        "message_type": wa_data["type"]
                    }
                
                return result_data
                
    except ValidationError as e:
        # Log but re-raise validation errors
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError as e:
        # Log but re-raise resource not found errors
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except UnauthorizedError as e:
        # Log but re-raise unauthorized errors
        logger.warning(f"Unauthorized: {str(e)}")
        raise
    except DuplicateError as e:
        # Log but re-raise duplicate errors
        logger.warning(f"Duplicate request: {str(e)}")
        raise
    except SQLAlchemyError as e:
        # Wrap and log database errors
        error_msg = f"Database error processing WhatsApp message: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="process_whatsapp_message"
        )
    except Exception as e:
        # Log and wrap unexpected errors
        error_msg = f"Unexpected error processing WhatsApp message: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="process_whatsapp_message"
        )