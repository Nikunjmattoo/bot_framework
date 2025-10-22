"""
Routing plan configuration for message processing.

This module defines the routing plans for handling messages through
various processing modules, including intents, brain, and response
generation. Routing plans can be customized per instance.
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List, Union, cast
from pathlib import Path

from message_handler.utils.logging import get_context_logger
from message_handler.exceptions import (
    ValidationError, InstanceConfigurationError, ErrorCode
)

# Logger for this module
logger = get_context_logger("routing_plan")

# ✅ CHANGED: Removed model and llm_runtime - DATABASE is source of truth
# Default plan if no instance-specific plan is found
DEFAULT_PLAN: Dict[str, Any] = {
    "plan_key": "retail-v1",
    "templates": {
        "intent": "intent_v1",
        "brain": "brain_v1",
        "response": "response_v1",
    },
    "modules": [
        {"name": "intent",  "type": "llm",  "template_ref": "intent",  "budget": {"prompt_in": 3000, "completion_out": 256}},
        {"name": "brain",   "type": "tool", "tool": "vector_search",   "budget": {"ops": 20}},
        {"name": "compose", "type": "llm",  "template_ref": "response","budget": {"prompt_in": 6000, "completion_out": 800}},
    ],
}

# Cache for routing plans to avoid reloading
_plan_cache: Dict[str, Dict[str, Any]] = {}

# Environment variables for configuration
PLANS_DIRECTORY = os.environ.get("ROUTING_PLANS_DIRECTORY", "config/routing_plans")
DEFAULT_PLAN_KEY = os.environ.get("DEFAULT_ROUTING_PLAN", "default")
ENABLE_PLAN_CACHING = os.environ.get("ENABLE_PLAN_CACHING", "true").lower() == "true"


def validate_routing_plan(plan: Dict[str, Any]) -> bool:
    """
    Validate routing plan structure and required fields.
    
    Args:
        plan: Routing plan dictionary to validate
        
    Returns:
        True if the plan is valid
        
    Raises:
        ValidationError: If the plan is invalid
    """
    if not plan or not isinstance(plan, dict):
        raise ValidationError(
            "Routing plan must be a non-empty dictionary",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing_plan"
        )
        
    # Check required top-level fields
    required_fields = ["plan_key", "templates", "modules"]
    missing_fields = [field for field in required_fields if field not in plan]
    
    if missing_fields:
        raise ValidationError(
            f"Missing required fields in routing plan: {', '.join(missing_fields)}",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing_plan",
            details={"missing_fields": missing_fields}
        )
    
    # Check modules structure
    if not isinstance(plan["modules"], list) or not plan["modules"]:
        raise ValidationError(
            "Routing plan must contain at least one module",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing_plan.modules"
        )
    
    # Check each module has required fields
    for i, module in enumerate(plan["modules"]):
        if not isinstance(module, dict):
            raise ValidationError(
                f"Module {i} must be a dictionary",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.modules[{i}]",
                details={"actual_type": type(module).__name__}
            )
        
        if "name" not in module:
            raise ValidationError(
                f"Module {i} is missing required field 'name'",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.modules[{i}].name"
            )
        
        if "type" not in module:
            raise ValidationError(
                f"Module {i} is missing required field 'type'",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.modules[{i}].type"
            )
            
        # Check that LLM modules have template_ref
        if module.get("type") == "llm" and "template_ref" not in module:
            raise ValidationError(
                f"LLM module {module.get('name', i)} must have 'template_ref'",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.modules[{i}].template_ref"
            )
            
        # Check that tool modules have tool name
        if module.get("type") == "tool" and "tool" not in module:
            raise ValidationError(
                f"Tool module {module.get('name', i)} must have 'tool' field",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.modules[{i}].tool"
            )
    
    # Check templates structure
    if not isinstance(plan["templates"], dict):
        raise ValidationError(
            "Templates must be a dictionary",
            error_code=ErrorCode.VALIDATION_ERROR,
            field="routing_plan.templates",
            details={"actual_type": type(plan["templates"]).__name__}
        )
        
    # Ensure all template_ref values have a corresponding template key
    template_refs = set()
    for module in plan["modules"]:
        if "template_ref" in module:
            template_refs.add(module["template_ref"])
            
    for template_ref in template_refs:
        if template_ref not in plan["templates"]:
            raise ValidationError(
                f"Referenced template '{template_ref}' not found in templates",
                error_code=ErrorCode.VALIDATION_ERROR,
                field=f"routing_plan.templates.{template_ref}",
                details={"template_ref": template_ref, "available_templates": list(plan["templates"].keys())}
            )
    
    return True


def load_routing_plan_from_file(plan_key: str) -> Optional[Dict[str, Any]]:
    """
    Load routing plan from a JSON file.
    
    Args:
        plan_key: Plan key or filename (without extension)
        
    Returns:
        Routing plan dictionary or None if not found
    """
    # Build the path to the plan file
    plans_dir = Path(PLANS_DIRECTORY)
    plan_file = plans_dir / f"{plan_key}.json"
    
    # Check if the file exists
    if not plan_file.exists():
        logger.warning(f"Routing plan file not found: {plan_file}")
        return None
    
    # Load the plan from the file
    try:
        with open(plan_file, "r") as f:
            plan = json.load(f)
        
        # Validate the plan
        validate_routing_plan(plan)
        
        logger.info(f"Loaded routing plan from file: {plan_file}")
        return plan
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading routing plan from file {plan_file}: {str(e)}")
        return None
    except ValidationError as e:
        logger.error(f"Invalid routing plan in file {plan_file}: {str(e)}")
        return None


def get_instance_plan_key(instance_id: str) -> str:
    """
    Get the routing plan key for an instance.
    
    This function can be extended to look up instance-specific
    plan keys from a database or configuration file.
    
    Args:
        instance_id: Instance ID
        
    Returns:
        Plan key to use for this instance
    """
    # This is a placeholder for instance-specific plan mapping
    # In a real implementation, this could query a database
    # For now, we just use the default plan key
    return DEFAULT_PLAN_KEY


def load_for_instance(instance_id: str) -> Dict[str, Any]:
    """
    Load routing plan for an instance.
    
    This function looks up the appropriate routing plan for
    the specified instance, with fallback to the default plan.
    
    Args:
        instance_id: Instance ID
        
    Returns:
        Dict with routing plan
    """
    if not instance_id:
        logger.warning("Instance ID not provided, using default routing plan")
        return DEFAULT_PLAN
        
    # Check cache first if caching is enabled
    if ENABLE_PLAN_CACHING and instance_id in _plan_cache:
        return _plan_cache[instance_id]
    
    # Get the plan key for this instance
    plan_key = get_instance_plan_key(instance_id)
    
    # Try to load the plan from a file
    plan = None
    if plan_key:
        plan = load_routing_plan_from_file(plan_key)
    
    # Fall back to the default plan if not found
    if not plan:
        logger.info(f"Using default routing plan for instance {instance_id}")
        plan = DEFAULT_PLAN.copy()
    
    # Validate the plan
    try:
        validate_routing_plan(plan)
    except ValidationError as e:
        logger.error(f"Invalid routing plan for instance {instance_id}: {str(e)}")
        logger.info("Falling back to default routing plan")
        plan = DEFAULT_PLAN.copy()
    
    # Cache the plan if caching is enabled
    if ENABLE_PLAN_CACHING and instance_id:
        _plan_cache[instance_id] = plan
    
    return plan


def clear_plan_cache() -> None:
    """
    Clear the routing plan cache.
    
    This function can be called when routing plans are updated,
    to ensure the latest versions are used.
    """
    _plan_cache.clear()
    logger.info("Routing plan cache cleared")


def get_plan_details(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get detailed information about a routing plan.
    
    Args:
        plan: Routing plan dictionary
        
    Returns:
        Dict with plan details and metadata
    """
    if not plan or not isinstance(plan, dict):
        return {
            "error": "Invalid plan",
            "valid": False
        }
        
    try:
        # Check if plan is valid
        is_valid = validate_routing_plan(plan)
        
        # Extract key details
        details = {
            "plan_key": plan.get("plan_key", "unknown"),
            "valid": is_valid,
            "modules_count": len(plan.get("modules", [])),
            "templates_count": len(plan.get("templates", {})),
            "modules": [m.get("name") for m in plan.get("modules", []) if isinstance(m, dict) and "name" in m],
            "engine": plan.get("engine_ref"),
            "runtime_settings": plan.get("runtime")
        }
        
        return details
    except ValidationError as e:
        return {
            "error": str(e),
            "valid": False,
            "plan_key": plan.get("plan_key", "unknown") if isinstance(plan, dict) else None
        }
    except Exception as e:
        return {
            "error": f"Error analyzing plan: {str(e)}",
            "valid": False
        }