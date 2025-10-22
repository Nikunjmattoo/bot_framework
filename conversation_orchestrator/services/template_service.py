"""
Template service for filling template variables.

Takes template string, fills placeholders with data, returns final prompt.
"""

import logging
import re
from typing import Dict, Any
from conversation_orchestrator.exceptions import TemplateError

logger = logging.getLogger(__name__)


def fill_template(template: str, variables: Dict[str, Any]) -> str:
    """
    Fill template with variables.
    
    Replaces placeholders like {{variable_name}} with actual values.
    
    Args:
        template: Template string with placeholders
        variables: Dict of variable_name -> value
    
    Returns:
        Final prompt string with all variables filled
    
    Raises:
        TemplateError: If template filling fails
    """
    try:
        filled_template = template
        
        # Find all placeholders: {{variable_name}}
        placeholders = re.findall(r'\{\{([^}]+)\}\}', template)
        
        logger.debug(
            "template_service:found_placeholders",
            extra={"count": len(placeholders), "placeholders": placeholders}
        )
        
        # Replace each placeholder
        for placeholder in placeholders:
            placeholder_key = placeholder.strip()
            
            if placeholder_key in variables:
                value = variables[placeholder_key]
                
                # Convert value to string
                if value is None:
                    value_str = ""
                elif isinstance(value, (list, dict)):
                    value_str = str(value)
                else:
                    value_str = str(value)
                
                # Replace placeholder
                filled_template = filled_template.replace(
                    f"{{{{{placeholder}}}}}",
                    value_str
                )
                
                logger.debug(
                    "template_service:replaced_placeholder",
                    extra={"placeholder": placeholder_key, "value_length": len(value_str)}
                )
            else:
                # Placeholder not found in variables - leave empty or log warning
                logger.warning(
                    "template_service:placeholder_not_found",
                    extra={"placeholder": placeholder_key}
                )
                filled_template = filled_template.replace(
                    f"{{{{{placeholder}}}}}",
                    ""
                )
        
        logger.info(
            "template_service:template_filled",
            extra={
                "template_length": len(template),
                "filled_length": len(filled_template),
                "variables_count": len(variables)
            }
        )
        
        return filled_template
    
    except Exception as e:
        logger.error(
            "template_service:fill_error",
            extra={"error": str(e)}
        )
        raise TemplateError(
            message=f"Failed to fill template: {str(e)}",
            error_code="TEMPLATE_FILL_ERROR"
        ) from e


def format_messages(messages: list) -> str:
    """
    Format messages for template insertion.
    
    Args:
        messages: List of Message objects
    
    Returns:
        Formatted string
    """
    if not messages:
        return "[No previous messages]"
    
    formatted = []
    for msg in messages:
        role = msg.role.capitalize()
        content = msg.content
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


def format_active_task(task) -> str:
    """
    Format active task for template insertion.
    
    Args:
        task: ActiveTask object or None
    
    Returns:
        Formatted string
    """
    if not task or not task.name:
        return "[No active task]"
    
    return f"Task: {task.name}, Status: {task.status}"