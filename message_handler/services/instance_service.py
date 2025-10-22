"""
Instance resolution and configuration services.

This module provides functions for resolving and configuring instances
across different channels and with different configurations.
"""
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session, joinedload, contains_eager
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import text

from db.models.instances import InstanceModel
from db.models.instance_configs import InstanceConfigModel
from db.models.template_sets import TemplateSetModel
from message_handler.exceptions import (
    ResourceNotFoundError, DatabaseError, ValidationError,
    ErrorCode, InstanceConfigurationError
)
from message_handler.utils.logging import get_context_logger
from message_handler.utils.transaction import retry_transaction
from db.models.instance_configs import InstanceConfigModel
from db.models.template_sets import TemplateSetModel
from db.models.llm_models import LLMModel



# Cache TTL in seconds (5 minutes)
INSTANCE_CACHE_TTL = 300

# Use a global logger
logger = get_context_logger("instance_service")

class InstanceCache:
    """Simple in-memory cache for instance data."""
    
    def __init__(self):
        """Initialize empty cache."""
        # Store IDs and timestamps instead of actual ORM objects
        self._instances: Dict[str, Tuple[str, float]] = {}
        self._configs: Dict[str, Tuple[str, float]] = {}
        self._channel_instances: Dict[str, Tuple[str, float]] = {}
    
    def get_instance_id(self, instance_id: str) -> Optional[str]:
        """
        Get instance ID from cache if available and not expired.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Instance ID or None if not in cache or expired
        """
        if instance_id in self._instances:
            cached_id, timestamp = self._instances[instance_id]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return cached_id
            # Expired, remove from cache
            del self._instances[instance_id]
        return None
    
    def set_instance(self, instance_id: str) -> None:
        """
        Store instance ID in cache.
        
        Args:
            instance_id: Instance ID to cache
        """
        if instance_id:
            self._instances[instance_id] = (instance_id, datetime.now().timestamp())
    
    def get_config_id(self, instance_id: str) -> Optional[str]:
        """
        Get instance config ID from cache if available and not expired.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            Config ID or None if not in cache or expired
        """
        if instance_id in self._configs:
            config_id, timestamp = self._configs[instance_id]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return config_id
            # Expired, remove from cache
            del self._configs[instance_id]
        return None
    
    def set_config(self, instance_id: str, config_id: str) -> None:
        """
        Store instance config ID in cache.
        
        Args:
            instance_id: Instance ID
            config_id: Config ID to cache
        """
        if config_id and instance_id:
            self._configs[instance_id] = (config_id, datetime.now().timestamp())
    
    def get_instance_id_by_channel(self, channel: str, recipient: Optional[str] = None) -> Optional[str]:
        """
        Get instance ID by channel and recipient from cache if available and not expired.
        
        Args:
            channel: Channel name
            recipient: Recipient identifier (optional)
            
        Returns:
            Instance ID or None if not in cache or expired
        """
        key = f"{channel}:{recipient or ''}"
        if key in self._channel_instances:
            instance_id, timestamp = self._channel_instances[key]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return instance_id
            # Expired, remove from cache
            del self._channel_instances[key]
        return None
    
    def set_instance_by_channel(self, channel: str, recipient: Optional[str], instance_id: str) -> None:
        """
        Store instance ID by channel and recipient in cache.
        
        Args:
            channel: Channel name
            recipient: Recipient identifier (optional)
            instance_id: Instance ID to cache
        """
        if instance_id and channel:
            key = f"{channel}:{recipient or ''}"
            self._channel_instances[key] = (instance_id, datetime.now().timestamp())
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._instances.clear()
        self._configs.clear()
        self._channel_instances.clear()
    
    def invalidate_instance(self, instance_id: str) -> None:
        """
        Invalidate a specific instance in the cache.
        
        Args:
            instance_id: Instance ID to invalidate
        """
        if instance_id in self._instances:
            del self._instances[instance_id]
        if instance_id in self._configs:
            del self._configs[instance_id]
        
        # Also remove from channel instances if it matches
        to_remove = []
        for key, (cached_id, _) in self._channel_instances.items():
            if cached_id == instance_id:
                to_remove.append(key)
        
        for key in to_remove:
            if key in self._channel_instances:
                del self._channel_instances[key]


# Create a global instance cache
instance_cache = InstanceCache()


def resolve_instance(
    db: Session, 
    instance_id: str,
    force_refresh: bool = False,
    trace_id: Optional[str] = None
) -> Optional[InstanceModel]:
    """
    Resolve an instance by ID with efficient caching.
    
    Args:
        db: Database session
        instance_id: Instance ID
        force_refresh: Force refresh from database even if cached
        trace_id: Trace ID for logging (optional)
        
    Returns:
        InstanceModel or None if not found
        
    Raises:
        DatabaseError: If a database error occurs
        ValidationError: If instance_id is invalid
    """
    log = get_context_logger("instance_service", trace_id=trace_id, instance_id=instance_id)
    
    try:
        # Validate input
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Check cache first (unless force refresh)
        cached = False
        if not force_refresh:
            cached_id = instance_cache.get_instance_id(str(instance_id))
            if cached_id:
                log.debug(f"Found cached instance ID: {cached_id}")
                cached = True
        
        # Always query from database to ensure we have a session-bound object
        instance = (db.query(InstanceModel)
              .options(
                  joinedload(InstanceModel.brand)
              )
              .filter(InstanceModel.id == instance_id)
              .first())
        
        # Not found
        if not instance:
            log.warning(f"Instance not found: {instance_id}")
            return None
        
        # Inactive
        if not instance.is_active:
            log.warning(f"Instance is not active: {instance_id}")
            return None
        
        # Cache the instance ID
        instance_cache.set_instance(str(instance.id))
        
        if cached:
            log.debug(f"Using cached instance: {instance_id}")
        else:
            log.debug(f"Resolved instance: {instance_id}")
            
        return instance
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving instance {instance_id}: {str(e)}"
        log.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="resolve_instance"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error resolving instance {instance_id}: {str(e)}"
        log.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="resolve_instance"
        )


def get_instance_config(
    db: Session, 
    instance_id: str,
    force_refresh: bool = False,
    trace_id: Optional[str] = None
) -> Optional[InstanceConfigModel]:
    """
    Get the active configuration for an instance with validation and caching.
    
    Args:
        db: Database session
        instance_id: Instance ID
        force_refresh: Force refresh from database even if cached
        trace_id: Trace ID for logging (optional)
        
    Returns:
        InstanceConfigModel with joined template_set and llm_model or None if not found
        
    Raises:
        DatabaseError: If a database error occurs
        InstanceConfigurationError: If configuration is invalid
    """
    log = get_context_logger("instance_service", trace_id=trace_id, instance_id=instance_id)
    
    try:
        # Validate input
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Check cache first (unless force refresh)
        cached = False
        if not force_refresh:
            cached_id = instance_cache.get_config_id(str(instance_id))
            if cached_id:
                log.debug(f"Found cached config ID: {cached_id}")
                cached = True
        
        # Always query from database to ensure we have a session-bound object
        config = (db.query(InstanceConfigModel)
            .filter(
                InstanceConfigModel.instance_id == instance_id,
                InstanceConfigModel.is_active == True
            )
            .options(
                joinedload(InstanceConfigModel.template_set)
            )
            .first())
        
        # No active config found
        if not config:
            log.warning(f"No active config found for instance: {instance_id}")
            return None
        
        # Validate essential relationships and fields
        validation_errors = []
        
        # Verify template_set relationship
        if not config.template_set:
            validation_errors.append("Config has no template set")
        
        # Verify functions field
        if config.template_set and (not hasattr(config.template_set, 'functions') or not config.template_set.functions):
            log.warning(f"Template set {config.template_set.id} has no functions mapping")
            # Add as warning but not a critical error
        
        # If there are validation errors, raise exception
        if validation_errors:
            error_msg = f"Instance configuration is invalid: {', '.join(validation_errors)}"
            log.error(error_msg)
            raise InstanceConfigurationError(
                error_msg,
                error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
                instance_id=instance_id
            )
        
        # Cache the config ID
        instance_cache.set_config(str(instance_id), str(config.id))
        
        if cached:
            log.debug(f"Using cached config for instance: {instance_id}")
        else:
            log.debug(f"Retrieved active config for instance: {instance_id}")
            
        return config
        
    except SQLAlchemyError as e:
        error_msg = f"Database error getting instance config for {instance_id}: {str(e)}"
        log.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_instance_config"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except InstanceConfigurationError:
        # Re-raise configuration errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error getting instance config for {instance_id}: {str(e)}"
        log.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_instance_config"
        )


def resolve_instance_by_channel(
    db: Session, 
    channel: str, 
    recipient_number: Optional[str] = None,
    force_refresh: bool = False,
    trace_id: Optional[str] = None
) -> Optional[InstanceModel]:
    """
    Resolve an instance by channel and recipient number with efficient caching.
    
    Args:
        db: Database session
        channel: Channel (e.g., 'whatsapp', 'web')
        recipient_number: Recipient phone number (for WhatsApp)
        force_refresh: Force refresh from database even if cached
        trace_id: Trace ID for logging (optional)
        
    Returns:
        InstanceModel or None if not found
        
    Raises:
        DatabaseError: If a database error occurs
        ValidationError: If channel is invalid
    """
    log = get_context_logger("instance_service", trace_id=trace_id, channel=channel, recipient=recipient_number)
    
    try:
        # Validate input
        if not channel:
            raise ValidationError(
                "Channel is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="channel"
            )
        
        # Channel-specific validation
        if channel == "whatsapp" and not recipient_number:
            log.warning("Recipient number is recommended for WhatsApp channel")
        
        # Check cache first (unless force refresh)
        cached = False
        if not force_refresh:
            cached_id = instance_cache.get_instance_id_by_channel(channel, recipient_number)
            if cached_id:
                # Use the cached ID to query from DB to get a session-bound object
                instance = (db.query(InstanceModel)
                      .options(joinedload(InstanceModel.brand))
                      .filter(InstanceModel.id == cached_id)
                      .first())
                      
                if instance and instance.is_active:
                    log.debug(f"Using cached instance for channel: {channel}")
                    return instance
                else:
                    # Invalid cache entry, remove it
                    log.warning(f"Cached instance ID {cached_id} no longer valid")
                    instance_cache.invalidate_instance(cached_id)
        
        # Build query for direct lookup
        query = (db.query(InstanceModel)
            .options(joinedload(InstanceModel.brand))
            .filter(
                InstanceModel.channel == channel,
                InstanceModel.is_active == True
            ))
        
        # Add recipient filter if provided and channel is WhatsApp
        if recipient_number and channel == "whatsapp":
            query = query.filter(InstanceModel.recipient_number == recipient_number)
        
        # Get the first active instance that matches
        instance = query.first()
        
        # Not found
        if not instance:
            log_msg = f"No instance found for channel: {channel}"
            if recipient_number:
                log_msg += f" and recipient: {recipient_number}"
            log.warning(log_msg)
            return None
        
        # Cache the instance ID
        instance_cache.set_instance_by_channel(channel, recipient_number, str(instance.id))
        
        log.debug(f"Resolved instance by channel: {channel}, instance_id: {instance.id}")
        return instance
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving instance by channel {channel}: {str(e)}"
        log.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="resolve_instance_by_channel"
        )
    except ValidationError:
        # Re-raise validation errors
        raise
    except Exception as e:
        error_msg = f"Unexpected error resolving instance by channel {channel}: {str(e)}"
        log.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="resolve_instance_by_channel"
        )

def invalidate_instance_cache(
    instance_id: Optional[str] = None,
    trace_id: Optional[str] = None
) -> None:
    """
    Invalidate instance cache entries.
    
    Args:
        instance_id: Specific instance ID to invalidate (optional)
        trace_id: Trace ID for logging (optional)
    """
    log = get_context_logger("instance_service", trace_id=trace_id)
    
    if instance_id:
        log.info(f"Invalidating cache for instance: {instance_id}")
        instance_cache.invalidate_instance(str(instance_id))
    else:
        log.info("Invalidating all instance cache entries")
        instance_cache.clear()