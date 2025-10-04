"""
Token management service for LLM budget control.

This module provides functions for managing token budgets for 
language model interactions, including initialization, tracking,
and enforcement of token usage limits.
"""
from typing import Dict, Any, Optional, List, Union, Tuple, cast
from datetime import datetime, timezone
import json
import logging
import importlib.util
import os
from sqlalchemy.orm import Session

from message_handler.exceptions import (
    DatabaseError, TokenBudgetExceededError, ValidationError,
    ResourceNotFoundError, ErrorCode
)
from message_handler.utils.logging import get_context_logger, with_context

# Configuration (with environment variable fallbacks)
DEFAULT_TOKEN_BUDGET = int(os.environ.get("DEFAULT_TOKEN_BUDGET", "1000"))
ENABLE_TOKEN_BUDGET_ENFORCEMENT = os.environ.get("ENABLE_TOKEN_BUDGET_ENFORCEMENT", "true").lower() == "true"
TOKEN_MANAGER_IMPORT_PATH = os.environ.get("TOKEN_MANAGER_IMPORT_PATH", "token_manager.service")

# Function to check if token manager is available
def _is_token_manager_available() -> bool:
    """Check if the token_manager module is available."""
    try:
        module_path_parts = TOKEN_MANAGER_IMPORT_PATH.split('.')
        module_name = module_path_parts[0]
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError):
        return False


def _get_token_service():
    """
    Get the token service implementation.
    
    Returns:
        Token service object or None if not available
    """
    try:
        if not _is_token_manager_available():
            return None
            
        # Dynamic import to avoid circular references
        module_path = TOKEN_MANAGER_IMPORT_PATH
        module_parts = module_path.split('.')
        
        # Import the module
        module = __import__(module_parts[0])
        
        # Navigate through the module path
        for part in module_parts[1:]:
            module = getattr(module, part)
            
        # Get the TokenService class
        return module.TokenService()
    except (ImportError, AttributeError) as e:
        return None


def process_token_management(
    db: Session,
    session: Any,
    trace_id: Optional[str] = None
) -> bool:
    """
    Process token management for a session.
    
    Args:
        db: Database session
        session: Session model instance
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True if successful, False otherwise
    """
    logger = get_context_logger(
        "token_service", 
        trace_id=trace_id,
        session_id=str(session.id) if session and hasattr(session, 'id') else None
    )
    
    # Check if session is provided
    if not session:
        logger.error("No session provided for token management")
        return False
    
    try:
        # Get token service
        token_service = _get_token_service()
        if not token_service:
            logger.warning("Token manager not available, skipping token management")
            return False
        
        # Initialize session if needed (first message)
        if not hasattr(session, 'token_plan_json') or not session.token_plan_json:
            logger.info("Initializing token budgets for session")
            result = token_service.initialize_session(db, str(session.id))
            if not result:
                logger.warning("Failed to initialize token budgets")
                return False
            logger.info("Initialized token budgets for session")
        
        # Process any brain-requested template changes
        try:
            if hasattr(session, 'requested_templates') and session.requested_templates:
                updated = token_service.process_template_requests(db, str(session.id))
                if updated:
                    logger.info("Updated token budgets based on brain requests")
        except Exception as template_error:
            logger.warning(f"Error processing template requests: {str(template_error)}")
            # Continue even if template processing fails
        
        return True
    except Exception as e:
        logger.error(f"Error in token management: {str(e)}")
        # Continue processing even if token management fails
        return False


def get_token_budgets(
    db: Session,
    session_id: str,
    trace_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get token budgets for a session.
    
    Args:
        db: Database session
        session_id: Session ID
        trace_id: Trace ID for logging (optional)
        
    Returns:
        Token budgets dict or default budgets if not available
    """
    logger = get_context_logger(
        "token_service", 
        trace_id=trace_id,
        session_id=session_id
    )
    
    # Default budget to return if no specific budgets are available
    default_budgets = {
        "default": {
            "prompt_in": DEFAULT_TOKEN_BUDGET,
            "completion_out": DEFAULT_TOKEN_BUDGET,
        },
        "enforcement_enabled": ENABLE_TOKEN_BUDGET_ENFORCEMENT
    }
    
    try:
        # Get token service
        token_service = _get_token_service()
        if not token_service:
            logger.warning("Token manager not available, returning default token budget")
            return default_budgets
        
        # Get token budgets
        token_budgets = token_service.get_all_budgets(db, str(session_id))
        
        if token_budgets:
            logger.info("Retrieved token budgets")
            
            # Add enforcement flag
            token_budgets["enforcement_enabled"] = ENABLE_TOKEN_BUDGET_ENFORCEMENT
            
            return token_budgets
        else:
            logger.warning("No token budgets found, returning default")
            return default_budgets
            
    except Exception as e:
        logger.error(f"Error retrieving token budgets: {str(e)}")
        # Return default budget as fallback
        default_budgets["error"] = str(e)
        return default_budgets


def update_token_usage(
    db: Session,
    session_id: str,
    module_name: str,
    token_usage: Dict[str, int],
    trace_id: Optional[str] = None
) -> bool:
    """
    Update token usage for a module.
    
    Args:
        db: Database session
        session_id: Session ID
        module_name: Module name
        token_usage: Token usage dict with keys 'prompt_in', 'completion_out', etc.
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True if successful, False otherwise
        
    Raises:
        TokenBudgetExceededError: If token budget is exceeded and enforcement is enabled
    """
    logger = get_context_logger(
        "token_service", 
        trace_id=trace_id,
        session_id=session_id,
        module=module_name
    )
    
    try:
        # Validate inputs
        if not session_id:
            raise ValidationError(
                "Session ID is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="session_id"
            )
            
        if not module_name:
            raise ValidationError(
                "Module name is required",
                error_code=ErrorCode.VALIDATION_ERROR,
                field="module_name"
            )
        
        # Get token service
        token_service = _get_token_service()
        if not token_service:
            logger.warning("Token manager not available, skipping token usage update")
            return False
            
        # Check if this would exceed budgets
        if ENABLE_TOKEN_BUDGET_ENFORCEMENT:
            current_budgets = token_service.get_all_budgets(db, str(session_id))
            if current_budgets and module_name in current_budgets:
                budget = current_budgets[module_name]
                
                # Check each token type
                for token_type, usage in token_usage.items():
                    if token_type in budget:
                        budget_limit = budget[token_type]
                        current_usage = token_service.get_module_usage(
                            db, str(session_id), module_name, token_type
                        ) or 0
                        
                        # Check if adding this usage would exceed budget
                        if current_usage + usage > budget_limit:
                            logger.warning(
                                f"Token budget exceeded for {module_name}.{token_type}: "
                                f"current={current_usage}, new={usage}, limit={budget_limit}"
                            )
                            
                            raise TokenBudgetExceededError(
                                f"Token budget exceeded for {module_name}.{token_type}",
                                error_code=ErrorCode.TOKEN_BUDGET_EXCEEDED,
                                token_type=token_type,
                                current_usage=current_usage,
                                budget_limit=budget_limit
                            )
        
        # Update token usage
        result = token_service.update_module_usage(
            db, str(session_id), module_name, token_usage
        )
        
        if result:
            logger.info(f"Updated token usage for {module_name}: {token_usage}")
        else:
            logger.warning(f"Failed to update token usage for {module_name}")
        
        return result
        
    except TokenBudgetExceededError:
        # Re-raise token budget exceeded errors
        raise
    except Exception as e:
        logger.error(f"Error updating token usage: {str(e)}")
        # Continue processing even if token update fails
        return False


def check_token_budget(
    db: Session,
    session_id: str,
    module_name: str,
    token_type: str,
    planned_usage: int,
    trace_id: Optional[str] = None
) -> bool:
    """
    Check if a planned token usage would exceed the budget.
    
    Args:
        db: Database session
        session_id: Session ID
        module_name: Module name
        token_type: Token type (e.g., 'prompt_in', 'completion_out')
        planned_usage: Planned token usage
        trace_id: Trace ID for logging (optional)
        
    Returns:
        True if budget is sufficient, False if exceeded
    """
    logger = get_context_logger(
        "token_service", 
        trace_id=trace_id,
        session_id=session_id,
        module=module_name,
        token_type=token_type
    )
    
    try:
        # Get token service
        token_service = _get_token_service()
        if not token_service:
            logger.warning("Token manager not available, assuming budget is sufficient")
            return True
            
        # Get current budget and usage
        budgets = token_service.get_all_budgets(db, str(session_id))
        if not budgets or module_name not in budgets:
            logger.warning(f"No budget found for module {module_name}, using default")
            return DEFAULT_TOKEN_BUDGET >= planned_usage
            
        module_budget = budgets[module_name]
        if token_type not in module_budget:
            logger.warning(f"No budget found for token type {token_type}, using default")
            return DEFAULT_TOKEN_BUDGET >= planned_usage
            
        budget_limit = module_budget[token_type]
        
        # Get current usage
        current_usage = token_service.get_module_usage(
            db, str(session_id), module_name, token_type
        ) or 0
        
        # Check if adding this usage would exceed budget
        result = current_usage + planned_usage <= budget_limit
        
        if not result:
            logger.warning(
                f"Token budget check failed for {module_name}.{token_type}: "
                f"current={current_usage}, planned={planned_usage}, limit={budget_limit}"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking token budget: {str(e)}")
        # Assume budget is sufficient in case of error
        return True