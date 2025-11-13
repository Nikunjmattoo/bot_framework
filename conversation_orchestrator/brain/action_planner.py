"""
Action Planner - Core eligibility checking and execution planning.

This module contains ALL the business logic for determining if an action can execute.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging

from db.db import get_db
from db.models.actions import ActionModel
from db.models.users import UserModel
from .intent_logger import (
    check_action_completed,
    count_action_executions,
    count_action_executions_today,
    get_last_execution
)
from .schema_checker import check_schema_exists

logger = logging.getLogger(__name__)


def check_authorization(
    action: ActionModel,
    user: UserModel
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
    user_id: str
) -> Tuple[bool, Optional[str]]:
    """
    Check execution limits.
    
    Checks:
    - max_per_session
    - max_per_day
    - min_interval_seconds
    
    Returns:
        Tuple of (can_execute, reason_if_not)
    """
    # Check max per session
    if action.max_per_session:
        session_count = count_action_executions(session_id, action.canonical_name)
        if session_count >= action.max_per_session:
            return False, f'max_per_session_reached ({action.max_per_session})'
    
    # Check max per day
    if action.max_per_day:
        today_count = count_action_executions_today(user_id, action.canonical_name)
        if today_count >= action.max_per_day:
            return False, f'max_per_day_reached ({action.max_per_day})'
    
    # Check minimum interval
    if action.min_interval_seconds:
        last_execution = get_last_execution(session_id, action.canonical_name)
        if last_execution:
            elapsed = (datetime.utcnow() - last_execution).total_seconds()
            if elapsed < action.min_interval_seconds:
                remaining = action.min_interval_seconds - elapsed
                return False, f'min_interval_not_met ({int(remaining)}s remaining)'
    
    return True, None


def check_prerequisites(
    action: ActionModel,
    session_id: str,
    user_id: str,
    brand_id: str
) -> Tuple[bool, List[str]]:
    """
    Check action prerequisites.
    
    Checks:
    - prerequisite_actions (must be completed)
    - conflicting_actions (must not be completed)
    
    Returns:
        Tuple of (prerequisites_met, reasons_if_not)
    """
    reasons = []
    
    # Check prerequisite actions
    if action.prerequisite_actions:
        for prereq_action in action.prerequisite_actions:
            if not check_action_completed(session_id, prereq_action):
                reasons.append(f'prerequisite_not_met: {prereq_action}')
    
    # Check conflicting actions
    if action.conflicting_actions:
        for conflict_action in action.conflicting_actions:
            if check_action_completed(session_id, conflict_action):
                reasons.append(f'conflicting_action_completed: {conflict_action}')
    
    prerequisites_met = len(reasons) == 0
    return prerequisites_met, reasons


def check_params(
    action: ActionModel,
    collected_params: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Check if all required parameters are collected.
    
    Args:
        action: Action model with param_schema
        collected_params: Already collected parameters
        
    Returns:
        Tuple of (params_complete, missing_params)
    """
    if not action.param_schema:
        return True, []
    
    missing_params = []
    
    for param_name, param_config in action.param_schema.items():
        if param_config.get('required', False):
            if param_name not in collected_params or collected_params[param_name] is None:
                missing_params.append(param_name)
    
    params_complete = len(missing_params) == 0
    return params_complete, missing_params


def should_skip_workflow_action(
    action: ActionModel,
    user_id: str,
    brand_id: str
) -> Tuple[bool, Optional[str]]:
    """
    Determine if workflow action should be skipped.
    
    Checks skip_if_conditions from action definition.
    
    Returns:
        Tuple of (should_skip, skip_reason)
    """
    if not action.skip_if_conditions:
        return False, None
    
    # Check each skip condition
    for condition in action.skip_if_conditions:
        condition_type = condition.get('type')
        
        if condition_type == 'schema_complete':
            schema_id = condition.get('schema_id')
            result = check_schema_exists(brand_id, schema_id)
            if result and result.get('status') == 'complete':
                return True, f'schema_{schema_id}_already_complete'
        
        elif condition_type == 'action_completed':
            # Would need session_id to check properly
            # For now, skip this check
            pass
    
    return False, None