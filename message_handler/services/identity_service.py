"""
User identity resolution services.

This module provides functions for resolving user identity across different
channels (web, app, WhatsApp) with brand-scoped identity management.
"""
import re
from typing import Optional, Dict, Any, List, Tuple
import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.sql import text

from db.models.users import UserModel
from db.models.user_identifiers import UserIdentifierModel
from message_handler.exceptions import (
    UnauthorizedError, DatabaseError, ValidationError,
    ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction
from message_handler.utils.validation import validate_phone, validate_email, validate_device_id
from message_handler.utils.datetime_utils import ensure_timezone_aware, get_current_datetime

# Use context logger for module-level logging
logger = get_context_logger("identity_service")

# Constants
MAX_PHONE_LENGTH = 32
MAX_EMAIL_LENGTH = 128
MAX_DEVICE_ID_LENGTH = 128
MAX_AUTH_TOKEN_LENGTH = 256
PHONE_REGEX = re.compile(r'^\+[0-9]{1,14}$')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


def resolve_user_web_app(
    db: Session, 
    phone_e164: Optional[str] = None, 
    email: Optional[str] = None, 
    device_id: Optional[str] = None, 
    auth_token: Optional[str] = None,
    brand_id: Optional[str] = None,
    channel: str = "web", 
    accept_guest_users: bool = False,
    trace_id: Optional[str] = None
) -> Optional[UserModel]:
    """
    Resolve a user from web or app identifiers with brand-scoped identity.
    
    Resolution Priority (first match wins):
        1. phone_e164 - Highest priority (most verified/stable identifier)
        2. email - Second priority (verified but can change)
        3. device_id - Third priority (device-specific, less reliable)
        4. auth_token - Lowest priority (session-based, temporary)
    
    If no identifier matches and accept_guest_users=True, creates a new guest user.
    If no identifier matches and accept_guest_users=False, returns None.
    
    Why this priority?
        - Phone numbers are most stable and verified (especially via WhatsApp/SMS)
        - Email can change but still represents a verified identity
        - Device IDs are device-specific and less reliable (user changes device)
        - Auth tokens are temporary session identifiers
    
    Brand Scoping:
        All identifiers are scoped to brand_id, meaning the same phone/email
        can represent different users across different brands.
    
    Args:
        db: Database session
        phone_e164: E.164 formatted phone number (optional)
        email: Email address (optional)
        device_id: Device identifier (optional)
        auth_token: Authentication token (optional)
        brand_id: Brand ID for brand-scoped identity (required)
        channel: Channel identifier (default: "web")
        accept_guest_users: Whether to create guest user if no match found
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel if found or created, None if not found and guests not accepted
        
    Raises:
        ValidationError: If brand_id is missing or identifiers are invalid
        UnauthorizedError: If user authentication fails
        DatabaseError: If a database error occurs
    
    Example:
        # User with phone takes priority even if email also provided
        user = resolve_user_web_app(
            db, 
            phone_e164="+1234567890",
            email="user@example.com",  # This will be ignored if phone matches
            brand_id="brand-123"
        )
    """
    logger = get_context_logger("identity_service", trace_id=trace_id)
    
    try:
        # Validate brand ID
        if not brand_id:
            raise ValidationError(
                "Brand ID is required for user identity resolution",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="brand_id"
            )
        
        # Validate provided identifiers
        if phone_e164:
            is_valid, error_msg, _ = validate_phone(phone_e164)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="phone_e164",
                    value=phone_e164
                )
        
        if email:
            is_valid, error_msg, _ = validate_email(email)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="email",
                    value=email
                )
        
        if device_id:
            is_valid, error_msg, _ = validate_device_id(device_id)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="device_id",
                    value=device_id
                )
        
        # Check if we have enough identity information
        if not any([phone_e164, email, device_id, auth_token]):
            if not accept_guest_users:
                logger.warning("No identity information provided and guest users not accepted")
                return None
            
            # Create a guest user if guest users are accepted
            logger.info("No identifiers provided, creating guest user")
            return create_guest_user(db, channel, trace_id=trace_id)
        
        # Try to resolve by provided identifiers
        user = None
        resolution_method = None
        
        # Try to resolve by phone number
        if phone_e164 and not user:
            user = get_user_by_identifier(db, "phone", phone_e164, channel, brand_id, trace_id=trace_id)
            if user:
                resolution_method = "phone"
        
        # Try to resolve by email
        if email and not user:
            user = get_user_by_identifier(db, "email", email, channel, brand_id, trace_id=trace_id)
            if user:
                resolution_method = "email"
        
        # Try to resolve by device ID
        if device_id and not user:
            user = get_user_by_identifier(db, "device_id", device_id, channel, brand_id, trace_id=trace_id)
            if user:
                resolution_method = "device_id"
        
        # Try to resolve by auth token
        if auth_token and not user:
            user = get_user_by_identifier(db, "auth_token", auth_token, channel, brand_id, trace_id=trace_id)
            if user:
                resolution_method = "auth_token"
        
        # Found a user
        if user:
            logger.info(f"User resolved by {resolution_method}: {user.id}")
            
            # Update existing user with any new identifiers
            update_user_identifiers(
                db, user.id, brand_id, channel,
                phone_e164=phone_e164 if resolution_method != "phone" else None,
                email=email if resolution_method != "email" else None,
                device_id=device_id if resolution_method != "device_id" else None,
                auth_token=auth_token if resolution_method != "auth_token" else None,
                trace_id=trace_id
            )
            
            return user
        
        # If we get here, no existing user was found
        if accept_guest_users:
            # Create a new user with the provided identifiers
            logger.info("Creating new user with provided identifiers")
            return create_user_with_identifiers(
                db, 
                phone_e164=phone_e164, 
                email=email, 
                device_id=device_id, 
                auth_token=auth_token,
                channel=channel, 
                brand_id=brand_id,
                trace_id=trace_id
            )
        
        logger.warning("User not found and guest users not accepted")
        return None
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving web/app user: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="resolve_user_web_app"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error resolving web/app user: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="resolve_user_web_app"
        )

def resolve_user_whatsapp(
    db: Session, 
    phone_e164: str, 
    brand_id: Optional[str] = None, 
    accept_guest_users: bool = False,
    trace_id: Optional[str] = None
) -> Optional[UserModel]:
    """
    Resolve a user from WhatsApp phone number with brand-scoped identity.
    
    Args:
        db: Database session
        phone_e164: E.164 formatted phone number
        brand_id: Brand ID for brand-scoped identity
        accept_guest_users: Whether to accept guest users
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel or None if not found
        
    Raises:
        ValidationError: If phone number is invalid or brand_id is missing
        UnauthorizedError: If authentication fails
        DatabaseError: If a database error occurs
    """
    logger = get_context_logger("identity_service", trace_id=trace_id)
    
    try:
        # Validate brand ID
        if not brand_id:
            raise ValidationError(
                "Brand ID is required for user identity resolution",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="brand_id"
            )
        
        # Validate phone number
        if not phone_e164:
            raise ValidationError(
                "Phone number is required for WhatsApp user resolution",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="phone_e164"
            )
        
        is_valid, error_msg, _ = validate_phone(phone_e164)
        if not is_valid and error_msg:
            raise ValidationError(
                error_msg,
                error_code=ErrorCode.VALIDATION_ERROR,
                field="phone_e164",
                value=phone_e164
            )
        
        # Try to resolve by phone number
        user = get_user_by_identifier(db, "phone", phone_e164, "whatsapp", brand_id, trace_id=trace_id)
        
        if user:
            logger.info(f"WhatsApp user resolved by phone: {phone_e164}")
            return user
        
        # If we get here, no existing user was found
        if accept_guest_users:
            # Create a new user with the WhatsApp phone number
            logger.info(f"Creating new WhatsApp user with phone: {phone_e164}")
            return create_user_with_identifiers(
                db, 
                phone_e164=phone_e164, 
                channel="whatsapp", 
                brand_id=brand_id,
                trace_id=trace_id
            )
        
        logger.warning(f"WhatsApp user not found for phone {phone_e164} and guest users not accepted")
        return None
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving WhatsApp user: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="resolve_user_whatsapp"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error resolving WhatsApp user: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="resolve_user_whatsapp"
        )


def resolve_user_guest(
    db: Session, 
    channel: str = "web",
    trace_id: Optional[str] = None
) -> UserModel:
    """
    Create a new guest user without any identifiers.
    
    Args:
        db: Database session
        channel: Channel (default: "web")
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel for the new guest user
        
    Raises:
        DatabaseError: If a database error occurs
    """
    return create_guest_user(db, channel, trace_id=trace_id)


def get_user_by_identifier(
    db: Session, 
    identifier_type: str, 
    identifier_value: str, 
    channel: str, 
    brand_id: str,
    trace_id: Optional[str] = None
) -> Optional[UserModel]:
    """
    Get a user by identifier with brand-scoped identity.
    
    Args:
        db: Database session
        identifier_type: Type of identifier (phone, email, device_id, auth_token)
        identifier_value: Value of the identifier
        channel: Channel (web, app, whatsapp)
        brand_id: Brand ID for brand-scoped identity
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel or None if not found
        
    Raises:
        DatabaseError: If a database error occurs
    """
    logger = get_context_logger("identity_service", 
        trace_id=trace_id, 
        identifier_type=identifier_type,
        channel=channel
    )
    
    try:
        if not identifier_value or not brand_id:
            return None
        
        # Map to standard identifier types
        if identifier_type == "phone":
            identifier_type = "phone_e164"
        
        # Query for the identifier with brand-scoped identity and eager load the user
        query = (db.query(UserIdentifierModel)
            .options(joinedload(UserIdentifierModel.user))
            .filter(
                UserIdentifierModel.identifier_type == identifier_type,
                UserIdentifierModel.identifier_value == identifier_value,
                UserIdentifierModel.channel == channel,
                UserIdentifierModel.brand_id == brand_id
            ))
        
        user_identifier = query.first()
        
        if not user_identifier:
            logger.debug(f"No user found with {identifier_type}={identifier_value}")
            return None
        
        # Get the user from the joined load
        user = user_identifier.user
        
        if not user:
            logger.warning(f"User identifier exists but user not found: {user_identifier.user_id}")
            return None
        
        return user
        
    except SQLAlchemyError as e:
        error_msg = f"Database error getting user by identifier: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_user_by_identifier"
        )
    except Exception as e:
        error_msg = f"Unexpected error getting user by identifier: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_user_by_identifier"
        )

def update_user_identifiers(
    db: Session,
    user_id: str,
    brand_id: str,
    channel: str,
    phone_e164: Optional[str] = None,
    email: Optional[str] = None,
    device_id: Optional[str] = None,
    auth_token: Optional[str] = None,
    trace_id: Optional[str] = None
) -> bool:
    """
    Update or add identifiers for an existing user.
    
    Only adds identifiers that don't already exist for OTHER users.
    This prevents conflicts when the same identifier belongs to multiple users.
    
    Args:
        db: Database session
        user_id: User ID
        brand_id: Brand ID
        channel: Channel
        phone_e164: E.164 formatted phone number (optional)
        email: Email address (optional)
        device_id: Device ID (optional)
        auth_token: Authentication token (optional)
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True if any identifiers were added, False otherwise
        
    Raises:
        DatabaseError: If a database error occurs
    """
    logger = get_context_logger("identity_service", trace_id=trace_id, user_id=user_id)
    
    try:
        identifiers_added = False
        
        # Helper function to check if identifier belongs to another user
        def identifier_belongs_to_other_user(id_type: str, id_value: str) -> bool:
            """Check if identifier exists for a different user"""
            existing = db.query(UserIdentifierModel).filter(
                UserIdentifierModel.brand_id == brand_id,
                UserIdentifierModel.identifier_type == id_type,
                UserIdentifierModel.identifier_value == id_value,
                UserIdentifierModel.channel == channel,
                UserIdentifierModel.user_id != user_id
            ).first()
            return existing is not None
        
        # Add phone number if provided
        if phone_e164:
            # Check if already exists for this user
            exists = db.query(UserIdentifierModel).filter(
                UserIdentifierModel.user_id == user_id,
                UserIdentifierModel.brand_id == brand_id,
                UserIdentifierModel.identifier_type == "phone_e164",
                UserIdentifierModel.identifier_value == phone_e164,
                UserIdentifierModel.channel == channel
            ).first() is not None
            
            if not exists:
                # Check if belongs to another user
                if identifier_belongs_to_other_user("phone_e164", phone_e164):
                    logger.warning(
                        f"Phone {phone_e164} already belongs to another user, skipping",
                        extra={"user_id": user_id, "phone": phone_e164}
                    )
                else:
                    phone_id = UserIdentifierModel(
                        user_id=user_id,
                        brand_id=brand_id,
                        identifier_type="phone_e164",
                        identifier_value=phone_e164,
                        channel=channel,
                        verified=True
                    )
                    db.add(phone_id)
                    identifiers_added = True
        
        # Add email if provided
        if email:
            exists = db.query(UserIdentifierModel).filter(
                UserIdentifierModel.user_id == user_id,
                UserIdentifierModel.brand_id == brand_id,
                UserIdentifierModel.identifier_type == "email",
                UserIdentifierModel.identifier_value == email,
                UserIdentifierModel.channel == channel
            ).first() is not None
            
            if not exists:
                # Check if belongs to another user
                if identifier_belongs_to_other_user("email", email):
                    logger.warning(
                        f"Email {email} already belongs to another user, skipping",
                        extra={"user_id": user_id, "email": email}
                    )
                else:
                    email_id = UserIdentifierModel(
                        user_id=user_id,
                        brand_id=brand_id,
                        identifier_type="email",
                        identifier_value=email,
                        channel=channel,
                        verified=False
                    )
                    db.add(email_id)
                    identifiers_added = True
        
        # Add device ID if provided
        if device_id:
            exists = db.query(UserIdentifierModel).filter(
                UserIdentifierModel.user_id == user_id,
                UserIdentifierModel.brand_id == brand_id,
                UserIdentifierModel.identifier_type == "device_id",
                UserIdentifierModel.identifier_value == device_id,
                UserIdentifierModel.channel == channel
            ).first() is not None
            
            if not exists:
                # Check if belongs to another user
                if identifier_belongs_to_other_user("device_id", device_id):
                    logger.warning(
                        f"Device ID {device_id} already belongs to another user, skipping",
                        extra={"user_id": user_id, "device_id": device_id}
                    )
                else:
                    device_id_obj = UserIdentifierModel(
                        user_id=user_id,
                        brand_id=brand_id,
                        identifier_type="device_id",
                        identifier_value=device_id,
                        channel=channel,
                        verified=True
                    )
                    db.add(device_id_obj)
                    identifiers_added = True
        
        # Add auth token if provided
        if auth_token:
            exists = db.query(UserIdentifierModel).filter(
                UserIdentifierModel.user_id == user_id,
                UserIdentifierModel.brand_id == brand_id,
                UserIdentifierModel.identifier_type == "auth_token",
                UserIdentifierModel.channel == channel
            ).first() is not None
            
            if not exists:
                # Check if belongs to another user
                if identifier_belongs_to_other_user("auth_token", auth_token):
                    logger.warning(
                        f"Auth token already belongs to another user, skipping",
                        extra={"user_id": user_id}
                    )
                else:
                    auth_token_obj = UserIdentifierModel(
                        user_id=user_id,
                        brand_id=brand_id,
                        identifier_type="auth_token",
                        identifier_value=auth_token,
                        channel=channel,
                        verified=True
                    )
                    db.add(auth_token_obj)
                    identifiers_added = True
        
        # Flush changes if any identifiers were added
        if identifiers_added:
            db.flush()
            logger.info(f"Added new identifiers for user {user_id}")
        
        return identifiers_added
        
    except SQLAlchemyError as e:
        error_msg = f"Database error updating user identifiers: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="update_user_identifiers"
        )
    except Exception as e:
        error_msg = f"Unexpected error updating user identifiers: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="update_user_identifiers"
        )

def create_guest_user(
    db: Session, 
    channel: str = "guest",
    trace_id: Optional[str] = None
) -> UserModel:
    """
    Create a guest user without any identifiers.
    
    Args:
        db: Database session
        channel: Acquisition channel (default: "guest")
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel for the new guest user
        
    Raises:
        DatabaseError: If a database error occurs
    """
    logger = get_context_logger("identity_service", trace_id=trace_id, channel=channel)
    
    try:
        # Create a new guest user with a secure random ID
        user_id = uuid.uuid4()
        
        # Create a new guest user
        user = UserModel(
            id=user_id,
            acquisition_channel=channel,
            user_tier="guest",
            created_at=get_current_datetime()
        )
        db.add(user)
        db.flush()
        
        logger.info(f"Created new guest user: {user.id}")
        return user
        
    except SQLAlchemyError as e:
        error_msg = f"Database error creating guest user: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="create_guest_user"
        )
    except Exception as e:
        error_msg = f"Unexpected error creating guest user: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="create_guest_user"
        )


def create_user_with_identifiers(
    db: Session, 
    phone_e164: Optional[str] = None, 
    email: Optional[str] = None, 
    device_id: Optional[str] = None, 
    auth_token: Optional[str] = None, 
    channel: str = "web", 
    brand_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> UserModel:
    """
    Create a new user with the provided identifiers and brand-scoped identity.
    
    Args:
        db: Database session
        phone_e164: E.164 formatted phone number (optional)
        email: Email address (optional)
        device_id: Device ID (optional)
        auth_token: Authentication token (optional)
        channel: Channel (default: "web")
        brand_id: Brand ID for brand-scoped identity
        trace_id: Trace ID for logging (optional)
        
    Returns:
        UserModel for the new user
        
    Raises:
        ValidationError: If brand_id is missing or identifiers are invalid
        DatabaseError: If a database error occurs
    """
    logger = get_context_logger("identity_service", trace_id=trace_id, channel=channel)
    
    try:
        # Validate brand ID
        if not brand_id:
            raise ValidationError(
                "Brand ID is required to create user with identifiers",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="brand_id"
            )
        
        # Validate at least one identifier is provided
        if not any([phone_e164, email, device_id, auth_token]):
            raise ValidationError(
                "At least one identifier (phone, email, device_id, auth_token) is required",
                error_code=ErrorCode.VALIDATION_ERROR
            )
        
        # Validate provided identifiers
        if phone_e164:
            is_valid, error_msg, _ = validate_phone(phone_e164)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="phone_e164",
                    value=phone_e164
                )
        
        if email:
            is_valid, error_msg, _ = validate_email(email)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="email",
                    value=email
                )
        
        if device_id:
            is_valid, error_msg, _ = validate_device_id(device_id)
            if not is_valid and error_msg:
                raise ValidationError(
                    error_msg,
                    error_code=ErrorCode.VALIDATION_ERROR,
                    field="device_id",
                    value=device_id
                )
        
        # Determine user tier based on channel
        user_tier = "verified" if channel == "whatsapp" else "standard"
        
        # Create a new user with a secure random ID
        user_id = uuid.uuid4()
        
        # Create a new user
        user = UserModel(
            id=user_id,
            acquisition_channel=channel,
            user_tier=user_tier,
            created_at=get_current_datetime()
        )
        db.add(user)
        db.flush()
        
        # Add identifiers
        identifiers = []
        
        if phone_e164:
            phone_id = UserIdentifierModel(
                user_id=user.id,
                brand_id=brand_id,
                identifier_type="phone_e164",
                identifier_value=phone_e164,
                channel=channel,
                verified=True  # Phone is verified by WhatsApp/SMS
            )
            identifiers.append(phone_id)
            db.add(phone_id)
        
        if email:
            email_id = UserIdentifierModel(
                user_id=user.id,
                brand_id=brand_id,
                identifier_type="email",
                identifier_value=email,
                channel=channel,
                verified=False  # Email should be verified separately
            )
            identifiers.append(email_id)
            db.add(email_id)
        
        if device_id:
            device_id_obj = UserIdentifierModel(
                user_id=user.id,
                brand_id=brand_id,
                identifier_type="device_id",
                identifier_value=device_id,
                channel=channel,
                verified=True  # Device ID is verified by possession
            )
            identifiers.append(device_id_obj)
            db.add(device_id_obj)
            
        if auth_token:
            auth_token_obj = UserIdentifierModel(
                user_id=user.id,
                brand_id=brand_id,
                identifier_type="auth_token",
                identifier_value=auth_token,
                channel=channel,
                verified=True
            )
            identifiers.append(auth_token_obj)
            db.add(auth_token_obj)
        
        db.flush()
        
        logger.info(f"Created user with ID: {user.id} and {len(identifiers)} identifiers")
        return user
            
    except SQLAlchemyError as e:
        error_msg = f"Database error creating user with identifiers: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="create_user_with_identifiers"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error creating user with identifiers: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="create_user_with_identifiers"
        )