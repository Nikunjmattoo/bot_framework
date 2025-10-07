"""
Handler for template configuration updates.

This module provides functions for updating template configurations
based on decisions made by the language model brain.
"""
import uuid
import json
from typing import Dict, Any, Optional, List, Union

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from message_handler.exceptions import (
    ValidationError, ResourceNotFoundError, DatabaseError,
    ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context
from message_handler.utils.transaction import transaction_scope, retry_transaction

# Constants
MAX_TEMPLATE_SIZE = 65536  # 64KB maximum template size


def validate_template_config(
    template_configs: Dict[str, Dict[str, str]],
    trace_id: Optional[str] = None
) -> None:
    """
    Validate template configuration structure and size.
    
    Args:
        template_configs: Template configuration dictionary
        trace_id: Trace ID for logging (optional)
        
    Raises:
        ValidationError: If validation fails
    """
    logger = get_context_logger("template_handler", trace_id=trace_id)
    
    # Check if template_configs is provided
    if not template_configs:
        logger.warning("Template configurations cannot be empty")
        raise ValidationError(
            "Template configurations cannot be empty",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="template_configs"
        )
    
    # Validate template structure
    for template_key, template_values in template_configs.items():
        if not isinstance(template_values, dict):
            logger.warning(f"Template configuration for '{template_key}' must be a dictionary")
            raise ValidationError(
                f"Template configuration for '{template_key}' must be a dictionary",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"template_configs.{template_key}",
                details={"actual_type": type(template_values).__name__}
            )
        
        # Check required fields
        if "model_id" not in template_values and "preset_id" not in template_values:
            logger.warning(f"Template '{template_key}' must contain 'model_id' or 'preset_id'")
            raise ValidationError(
                f"Template '{template_key}' must contain 'model_id' or 'preset_id'",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"template_configs.{template_key}",
                details={"missing_fields": ["model_id", "preset_id"]}
            )
    
    # Check total size
    try:
        serialized = json.dumps(template_configs)
        if len(serialized) > MAX_TEMPLATE_SIZE:
            logger.warning(f"Template configurations exceed maximum size: {len(serialized)} bytes")
            raise ValidationError(
                f"Template configurations exceed maximum size of {MAX_TEMPLATE_SIZE} bytes",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="template_configs",
                details={"size": len(serialized), "max_size": MAX_TEMPLATE_SIZE}
            )
    except (TypeError, ValueError, json.JSONDecodeError) as e:
        logger.warning(f"Cannot serialize template configurations: {str(e)}")
        raise ValidationError(
            f"Invalid template configuration format: {str(e)}",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="template_configs",
            details={"error": str(e)}
        )


def update_template_config_internal(
    db: Session,
    session_id: str,
    template_configs: Dict[str, Dict[str, str]],
    trace_id: Optional[str] = None
) -> bool:
    """
    Update template configurations based on brain decisions.
    
    Args:
        db: Database session
        session_id: Session ID
        template_configs: Dict of template_key -> {"model_id": "...", "preset_id": "..."}
        trace_id: Trace ID for logging (optional)
        
    Returns:
        bool: True if successful, False otherwise
        
    Raises:
        ValidationError: If template configuration is invalid
        ResourceNotFoundError: If session not found
        DatabaseError: If database operation fails
    """
    # Generate trace_id if not provided
    trace_id = trace_id or str(uuid.uuid4())
    
    logger = get_context_logger(
        "template_handler", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    logger.info("Updating template configurations")
    
    try:
        # Validate inputs
        if not session_id:
            logger.warning("Session ID is required")
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
        
        # Validate template configurations
        validate_template_config(template_configs, trace_id)
        
        # Import necessary modules
        from db.models.sessions import SessionModel
        
        # Process with retry capability
        with retry_transaction(db, trace_id=trace_id, max_retries=2) as tx:
            # Validate session exists
            session = tx.query(SessionModel).filter(SessionModel.id == session_id).first()
            if not session:
                logger.error(f"Session not found: {session_id}")
                raise ResourceNotFoundError(
                    f"Session not found: {session_id}",
                    error_code=ErrorCode.RESOURCE_NOT_FOUND,
                    resource_type="session",
                    resource_id=session_id
                )
            
            # Log updated template keys
            template_keys = sorted(list(template_configs.keys()))
            logger.info(f"Updated template configs: {template_keys}")
            
            return True
            
    except ValidationError:
        # Re-raise validation errors
        logger.warning(f"Validation error: {str(e)}")
        raise
    except ResourceNotFoundError:
        # Re-raise resource not found errors
        logger.warning(f"Resource not found: {str(e)}")
        raise
    except SQLAlchemyError as e:
        # Wrap database errors
        error_msg = f"Database error updating template configuration: {str(e)}"
        logger.error(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.DATABASE_ERROR,
            original_exception=e,
            operation="update_template_config"
        )
    except Exception as e:
        # Wrap unexpected errors
        error_msg = f"Unexpected error updating template configuration: {str(e)}"
        logger.exception(error_msg)
        raise DatabaseError(
            error_msg,
            error_code=ErrorCode.INTERNAL_ERROR,
            original_exception=e,
            operation="update_template_config"
        )