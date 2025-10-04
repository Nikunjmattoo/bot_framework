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
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import retry_transaction

# Use context logger for module-level logging
logger = get_context_logger("instance_service")

# Cache TTL in seconds (5 minutes)
INSTANCE_CACHE_TTL = 300


class InstanceCache:
    """Simple in-memory cache for instance data."""
    
    def __init__(self):
        """Initialize empty cache."""
        self._instances: Dict[str, Tuple[Any, float]] = {}
        self._configs: Dict[str, Tuple[Any, float]] = {}
        self._channel_instances: Dict[str, Tuple[Any, float]] = {}
    
    def get_instance(self, instance_id: str) -> Optional[InstanceModel]:
        """
        Get instance from cache if available and not expired.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            InstanceModel or None if not in cache or expired
        """
        if instance_id in self._instances:
            instance, timestamp = self._instances[instance_id]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return instance
            # Expired, remove from cache
            del self._instances[instance_id]
        return None
    
    def set_instance(self, instance: InstanceModel) -> None:
        """
        Store instance in cache.
        
        Args:
            instance: Instance model to cache
        """
        if instance and instance.id:
            self._instances[str(instance.id)] = (instance, datetime.now().timestamp())
    
    def get_config(self, instance_id: str) -> Optional[InstanceConfigModel]:
        """
        Get instance config from cache if available and not expired.
        
        Args:
            instance_id: Instance ID
            
        Returns:
            InstanceConfigModel or None if not in cache or expired
        """
        if instance_id in self._configs:
            config, timestamp = self._configs[instance_id]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return config
            # Expired, remove from cache
            del self._configs[instance_id]
        return None
    
    def set_config(self, instance_id: str, config: InstanceConfigModel) -> None:
        """
        Store instance config in cache.
        
        Args:
            instance_id: Instance ID
            config: Instance config model to cache
        """
        if config and instance_id:
            self._configs[str(instance_id)] = (config, datetime.now().timestamp())
    
    def get_instance_by_channel(self, channel: str, recipient: Optional[str] = None) -> Optional[InstanceModel]:
        """
        Get instance by channel and recipient from cache if available and not expired.
        
        Args:
            channel: Channel name
            recipient: Recipient identifier (optional)
            
        Returns:
            InstanceModel or None if not in cache or expired
        """
        key = f"{channel}:{recipient or ''}"
        if key in self._channel_instances:
            instance, timestamp = self._channel_instances[key]
            if (datetime.now().timestamp() - timestamp) < INSTANCE_CACHE_TTL:
                return instance
            # Expired, remove from cache
            del self._channel_instances[key]
        return None
    
    def set_instance_by_channel(self, channel: str, recipient: Optional[str], instance: InstanceModel) -> None:
        """
        Store instance by channel and recipient in cache.
        
        Args:
            channel: Channel name
            recipient: Recipient identifier (optional)
            instance: Instance model to cache
        """
        if instance and channel:
            key = f"{channel}:{recipient or ''}"
            self._channel_instances[key] = (instance, datetime.now().timestamp())
    
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
        for key, (instance, _) in self._channel_instances.items():
            if str(instance.id) == instance_id:
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
    logger = with_context(logger, trace_id=trace_id, instance_id=instance_id)
    
    try:
        # Validate input
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_instance = instance_cache.get_instance(str(instance_id))
            if cached_instance:
                logger.debug(f"Using cached instance: {instance_id}")
                return cached_instance
        
        # Join load the brand to ensure we have brand_id available
        # and other related entities for better performance
        instance = (db.query(InstanceModel)
              .options(
                  joinedload(InstanceModel.brand),
                  joinedload(InstanceModel.default_config)
              )
              .filter(InstanceModel.id == instance_id)
              .first())
        
        # Not found
        if not instance:
            logger.warning(f"Instance not found: {instance_id}")
            return None
        
        # Inactive
        if not instance.is_active:
            logger.warning(f"Instance is not active: {instance_id}")
            return None
        
        # Cache the instance
        instance_cache.set_instance(instance)
        
        logger.debug(f"Resolved instance: {instance_id}")
        return instance
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving instance {instance_id}: {str(e)}"
        logger.error(error_msg)
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
        logger.exception(error_msg)
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
    logger = with_context(logger, trace_id=trace_id, instance_id=instance_id)
    
    try:
        # Validate input
        if not instance_id:
            raise ValidationError(
                "Instance ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="instance_id"
            )
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_config = instance_cache.get_config(str(instance_id))
            if cached_config:
                logger.debug(f"Using cached config for instance: {instance_id}")
                return cached_config
        
        # Get the active configuration with template_set and llm_model preloaded
        config = (db.query(InstanceConfigModel)
            .filter(
                InstanceConfigModel.instance_id == instance_id,
                InstanceConfigModel.is_active == True
            )
            .options(
                joinedload(InstanceConfigModel.template_set)
                .joinedload(TemplateSetModel.llm_model)
            )
            .first())
        
        # No active config found
        if not config:
            logger.warning(f"No active config found for instance: {instance_id}")
            return None
        
        # Validate essential relationships and fields
        validation_errors = []
        
        # Verify template_set relationship
        if not config.template_set:
            validation_errors.append("Config has no template set")
        
        # Verify functions field
        if config.template_set and (not hasattr(config.template_set, 'functions') or not config.template_set.functions):
            logger.warning(f"Template set {config.template_set.id} has no functions mapping")
            # Add as warning but not a critical error
        
        # Verify llm_model relationship through template_set
        if config.template_set and not config.template_set.llm_model:
            validation_errors.append(f"Template set {config.template_set.id} has no LLM model")
        
        # If there are validation errors, raise exception
        if validation_errors:
            error_msg = f"Instance configuration is invalid: {', '.join(validation_errors)}"
            logger.error(error_msg)
            raise InstanceConfigurationError(
                error_msg,
                error_code=ErrorCode.INSTANCE_CONFIGURATION_ERROR,
                instance_id=instance_id
            )
        
        # Cache the config
        instance_cache.set_config(str(instance_id), config)
        
        logger.debug(f"Retrieved active config for instance: {instance_id}")
        return config
        
    except SQLAlchemyError as e:
        error_msg = f"Database error getting instance config for {instance_id}: {str(e)}"
        logger.error(error_msg)
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
        logger.exception(error_msg)
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
    logger = with_context(logger, 
        trace_id=trace_id, 
        channel=channel,
        recipient=recipient_number
    )
    
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
            logger.warning("Recipient number is recommended for WhatsApp channel")
        
        # Check cache first (unless force refresh)
        if not force_refresh:
            cached_instance = instance_cache.get_instance_by_channel(channel, recipient_number)
            if cached_instance:
                logger.debug(f"Using cached instance for channel: {channel}")
                return cached_instance
        
        # Build query
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
            logger.warning(log_msg)
            return None
        
        # Cache the instance
        instance_cache.set_instance_by_channel(channel, recipient_number, instance)
        
        logger.debug(f"Resolved instance by channel: {channel}, instance_id: {instance.id}")
        return instance
        
    except SQLAlchemyError as e:
        error_msg = f"Database error resolving instance by channel {channel}: {str(e)}"
        logger.error(error_msg)
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
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="resolve_instance_by_channel"
        )


def get_instance_status(
    db: Session,
    instance_id: str,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get comprehensive status information for an instance.
    
    Args:
        db: Database session
        instance_id: Instance ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Dict containing instance status information
        
    Raises:
        ResourceNotFoundError: If instance not found
        DatabaseError: If a database error occurs
    """
    logger = with_context(logger, trace_id=trace_id, instance_id=instance_id)
    
    try:
        # Resolve instance
        instance = resolve_instance(db, instance_id, trace_id=trace_id)
        if not instance:
            raise ResourceNotFoundError(
                f"Instance not found: {instance_id}",
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                resource_type="instance",
                resource_id=instance_id
            )
        
        # Get instance configuration
        config = get_instance_config(db, instance_id, trace_id=trace_id)
        
        # Build status response
        status = {
            "id": str(instance.id),
            "name": instance.name if hasattr(instance, "name") else "Unknown",
            "channel": instance.channel,
            "is_active": instance.is_active,
            "brand_id": str(instance.brand_id),
            "created_at": instance.created_at.isoformat() if hasattr(instance, "created_at") and instance.created_at else None,
            "updated_at": instance.updated_at.isoformat() if hasattr(instance, "updated_at") and instance.updated_at else None,
            "config": None
        }
        
        # Add configuration details if available
        if config:
            config_details = {
                "id": str(config.id),
                "is_active": config.is_active,
                "template_set": None,
                "llm_model": None
            }
            
            if config.template_set:
                template_set = config.template_set
                config_details["template_set"] = {
                    "id": str(template_set.id),
                    "name": template_set.name if hasattr(template_set, "name") else "Unknown",
                    "has_functions": bool(template_set.functions) if hasattr(template_set, "functions") else False
                }
                
                if template_set.llm_model:
                    llm_model = template_set.llm_model
                    config_details["llm_model"] = {
                        "id": str(llm_model.id),
                        "name": llm_model.name if hasattr(llm_model, "name") else "Unknown",
                        "provider": llm_model.provider if hasattr(llm_model, "provider") else "Unknown"
                    }
            
            status["config"] = config_details
        
        logger.info(f"Retrieved status for instance: {instance_id}")
        return status
        
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        raise
    except SQLAlchemyError as e:
        error_msg = f"Database error getting instance status for {instance_id}: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="get_instance_status"
        )
    except Exception as e:
        error_msg = f"Unexpected error getting instance status for {instance_id}: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="get_instance_status"
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
    logger = with_context(logger, trace_id=trace_id)
    
    if instance_id:
        logger.info(f"Invalidating cache for instance: {instance_id}")
        instance_cache.invalidate_instance(str(instance_id))
    else:
        logger.info("Invalidating all instance cache entries")
        instance_cache.clear()