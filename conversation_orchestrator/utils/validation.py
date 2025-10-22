"""
Input validation utilities.
"""

from typing import Dict, Any
from conversation_orchestrator.exceptions import ValidationError


def validate_adapter_payload(payload: Dict[str, Any]) -> None:
    """
    Validate adapter payload structure.
    
    Ensures all required fields are present and valid.
    
    Args:
        payload: Adapter payload dict
    
    Raises:
        ValidationError: If validation fails
    """
    # Check required top-level keys
    required_keys = [
        "routing",
        "message",
        "session_id",
        "policy",
        "template",
        "token_plan",
        "model",
        "llm_runtime"
    ]
    
    for key in required_keys:
        if key not in payload:
            raise ValidationError(
                f"Missing required field: {key}",
                error_code="MISSING_FIELD",
                details={"field": key}
            )
    
    # Validate routing
    routing = payload.get("routing", {})
    if "instance_id" not in routing:
        raise ValidationError(
            "Missing routing.instance_id",
            error_code="MISSING_FIELD",
            details={"field": "routing.instance_id"}
        )
    
    # Validate message
    msg = payload.get("message", {})
    if "content" not in msg:
        raise ValidationError(
            "Missing message.content",
            error_code="MISSING_FIELD",
            details={"field": "message.content"}
        )
    
    if "sender_user_id" not in msg:
        raise ValidationError(
            "Missing message.sender_user_id",
            error_code="MISSING_FIELD",
            details={"field": "message.sender_user_id"}
        )
    
    # Validate session_id
    if not payload.get("session_id"):
        raise ValidationError(
            "session_id cannot be empty",
            error_code="INVALID_FIELD",
            details={"field": "session_id"}
        )
    
    # Validate policy
    policy = payload.get("policy", {})
    if "auth_state" not in policy:
        raise ValidationError(
            "Missing policy.auth_state",
            error_code="MISSING_FIELD",
            details={"field": "policy.auth_state"}
        )
    
    # Validate template structure (new adapter format)
    template = payload.get("template", {})
    template_json = template.get("json", {})
    
    if not isinstance(template_json, dict):
        raise ValidationError(
            "template.json must be a dictionary",
            error_code="INVALID_FIELD",
            details={"field": "template.json"}
        )
    
    # Validate token_plan structure (new adapter format)
    token_plan = payload.get("token_plan", {})
    
    if token_plan is None:
        raise ValidationError(
            "token_plan cannot be null",
            error_code="MISSING_FIELD",
            details={"field": "token_plan"}
        )
    
    if not isinstance(token_plan, dict):
        raise ValidationError(
            "token_plan must be a dictionary",
            error_code="INVALID_FIELD",
            details={"field": "token_plan"}
        )
    
    # Check for templates key in token_plan
    if "templates" not in token_plan:
        raise ValidationError(
            "token_plan must have 'templates' key",
            error_code="INVALID_FIELD",
            details={"field": "token_plan.templates"}
        )


def validate_template_variables(variables: Dict[str, Any]) -> None:
    """
    Validate template variables.
    
    Args:
        variables: Template variables dict
    
    Raises:
        ValidationError: If validation fails
    """
    required = ["user_message", "user_id", "session_id", "user_type"]
    
    for key in required:
        if key not in variables:
            raise ValidationError(
                f"Missing template variable: {key}",
                error_code="MISSING_VARIABLE",
                details={"variable": key}
            )
        
        if not variables[key]:
            raise ValidationError(
                f"Template variable cannot be empty: {key}",
                error_code="EMPTY_VARIABLE",
                details={"variable": key}
            )