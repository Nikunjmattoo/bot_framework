"""
Action Planner - Core eligibility checking and execution planning.

This module contains ALL the business logic for determining if an action can execute.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from db.models.actions import ActionModel
from db.models.users import UserModel
from .schema_checker import check_multiple_schemas, check_schema_exists, check_data_exists
from .intent_logger import (
    check_action_completed,
    count_action_executions,
    count_action_executions_today,
    get_last_execution
)


def check_authorization(
    action: ActionModel,
    user: UserModel,
    db: Session
) -> Tuple[bool, List[str]]:
    """
    Check if user is authorized to execute action.
    
    Checks:
    - requires_auth
    - min_trust_score
    - allowed_user_tiers
    - blocked_user_tiers
    
    Returns:
        Tuple of (authorized, reasons_if_not)
    """
    reasons = []
    
    # Check authentication
    if action.requires_auth and (not user or user.acquisition_channel == 'guest'):
        reasons.append('requires_authentication')
    
    # Check trust score
    if hasattr(user, 'trust_score') and action.min_trust_score:
        if user.trust_score < action.min_trust_score:
            reasons.append(f'trust_score_too_low')
    
    # Check allowed tiers
    if action.allowed_user_tiers and hasattr(user, 'tier'):
        if user.tier not in action.allowed_user_tiers:
            reasons.append('tier_not_allowed')
    
    # Check blocked tiers
    if action.blocked_user_tiers and hasattr(user, 'tier'):
        if user.tier in action.blocked_user_tiers:
            reasons.append('tier_blocked')
    
    authorized = len(reasons) == 0
    return authorized, reasons


def check_execution_limits(
    action: ActionModel,
    session_id: str,
    user_id: str,
    db: Session
) -> Tuple[bool, Optional[str]]:
    """
    Check execution limits.
    
    Checks:
    - is_repeatable
    - max_executions_per_session
    - max_executions_per_day
    - min_repeat_interval_seconds
    
    Returns:
        Tuple of (can_execute, reason_if_not)
    """
    # Check if repeatable
    if not action.is_repeatable:
        if check_action_completed(action.canonical_name, user_id, db, session_id):
            return False, 'already_executed'
    
    # Check session limit
    if action.max_executions_per_session:
        count = count_action_executions(action.canonical_name, session_id, db)
        if count >= action.max_executions_per_session:
            return False, f'session_limit_exceeded:{action.max_executions_per_session}'
    
    # Check daily limit
    if action.max_executions_per_day:
        count = count_action_executions_today(action.canonical_name, user_id, db)
        if count >= action.max_executions_per_day:
            return False, f'daily_limit_exceeded:{action.max_executions_per_day}'
    
    # Check repeat interval
    if action.min_repeat_interval_seconds:
        last_exec = get_last_execution(action.canonical_name, session_id, db)
        if last_exec:
            seconds_since = (datetime.utcnow() - last_exec.created_at).total_seconds()
            if seconds_since < action.min_repeat_interval_seconds:
                wait_seconds = int(action.min_repeat_interval_seconds - seconds_since)
                return False, f'repeat_too_soon:wait_{wait_seconds}s'
    
    return True, None


def check_prerequisites(
    action: ActionModel,
    user_id: str,
    brand_id: str,
    session_id: str,
    db: Session
) -> Tuple[bool, List[str]]:
    """
    Check action prerequisites.
    
    Checks:
    - depends_on_actions
    - depends_on_schemas (KILLER FEATURE)
    - blocked_if_actions
    - blocked_if_schemas
    - blockers (custom logic)
    
    Returns:
        Tuple of (ready, reasons_if_not)
    """
    reasons = []
    prereqs = action.get_prerequisites()
    
    # Check depends_on_actions
    depends_on = prereqs.get('depends_on_actions', [])
    for required_action in depends_on:
        if not check_action_completed(required_action, user_id, db):
            reasons.append(f'missing_action:{required_action}')
    
    # Check depends_on_schemas
    schema_deps = prereqs.get('depends_on_schemas', [])
    if schema_deps:
        schemas_complete, schema_reasons = check_multiple_schemas(
            schema_deps,
            user_id,
            brand_id,
            db
        )
        if not schemas_complete:
            reasons.extend(schema_reasons)
    
    # Check blocked_if_actions
    blocked_if_actions = prereqs.get('blocked_if_actions', [])
    for blocking_action in blocked_if_actions:
        if check_action_completed(blocking_action, user_id, db):
            reasons.append(f'blocked_by:{blocking_action}')
    
    # Check blocked_if_schemas
    blocked_if_schemas = prereqs.get('blocked_if_schemas', [])
    for schema_key in blocked_if_schemas:
        if check_schema_exists(schema_key, user_id, brand_id, db):
            reasons.append(f'schema_exists:{schema_key}')
    
    # Check custom blockers
    blockers = prereqs.get('blockers', [])
    for blocker in blockers:
        is_blocked = check_custom_blocker(blocker, user_id, action, db)
        if is_blocked:
            reasons.append(blocker)
    
    ready = len(reasons) == 0
    return ready, reasons


def check_params(
    action: ActionModel,
    params_collected: Dict[str, Any]
) -> Tuple[Dict[str, Any], List[str], Dict[str, str]]:
    """
    Check if all required parameters are collected.
    
    Returns:
        Tuple of (params_collected, params_missing, validation_errors)
    """
    params_required = action.get_params_required()
    params_missing = []
    validation_errors = {}
    
    # Check required params
    for param in params_required:
        if param not in params_collected or params_collected[param] is None:
            params_missing.append(param)
        else:
            # Validate param if validation rules exist
            validation = action.config.get('param_validation', {}).get(param, {})
            if validation:
                error = validate_param(param, params_collected[param], validation)
                if error:
                    validation_errors[param] = error
    
    return params_collected, params_missing, validation_errors


def validate_param(param_name: str, value: Any, validation: Dict[str, Any]) -> Optional[str]:
    """
    Validate parameter against rules.
    
    Returns:
        Error message if invalid, None if valid
    """
    import re
    
    # Type validation
    expected_type = validation.get('type')
    if expected_type == 'email':
        regex = r'^[\w\.-]+@[\w\.-]+\.\w+$'
        if not re.match(regex, str(value)):
            return validation.get('error_message', 'Invalid email format')
    
    # Regex validation
    regex = validation.get('regex')
    if regex:
        if not re.match(regex, str(value)):
            return validation.get('error_message', f'Invalid {param_name}')
    
    # Min/max length
    min_length = validation.get('min_length')
    if min_length and len(str(value)) < min_length:
        return f'Must be at least {min_length} characters'
    
    max_length = validation.get('max_length')
    if max_length and len(str(value)) > max_length:
        return f'Must be at most {max_length} characters'
    
    return None


def check_custom_blocker(blocker: str, user_id: str, action: ActionModel, db: Session) -> bool:
    """
    Check custom blocker logic.
    
    Add your custom blocker implementations here.
    
    Returns:
        True if blocked, False if not
    """
    # Example blockers
    if blocker == 'email_in_use':
        # Check if email already exists (would need email from somewhere)
        # For now, return False
        return False
    
    elif blocker == 'resume_already_uploaded':
        # Check if user has resume
        # Would check schemas or database
        return False
    
    # Add more custom blockers as needed
    return False


def should_skip_workflow_action(
    action: ActionModel,
    user_id: str,
    brand_id: str,
    db: Session
) -> Tuple[bool, Optional[str]]:
    """
    Determine if workflow action should be skipped.
    
    Used in workflow expansion.
    
    Returns:
        Tuple of (should_skip, skip_reason)
    """
    # Check if already completed
    if check_action_completed(action.canonical_name, user_id, db):
        return True, 'already_completed'
    
    # Check skip_if_data_available logic
    workflow_config = action.config.get('workflow', {})
    skip_if_data = workflow_config.get('skip_if_data_available', False)
    
    if skip_if_data:
        data_schema = workflow_config.get('data_source_schema')
        data_field = workflow_config.get('data_source_field')
        mandatory = workflow_config.get('mandatory_if_missing', False)
        
        if data_schema and data_field:
            has_data = check_data_exists(data_schema, data_field, user_id, brand_id, db)
            
            if has_data:
                # Data available, skip
                return True, 'data_already_available'
            elif not mandatory:
                # Data missing but optional, skip
                return True, 'optional_and_missing'
            else:
                # Data missing and mandatory, don't skip
                return False, None
    
    return False, None