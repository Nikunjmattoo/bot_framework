"""
Brain module - Action orchestration and eligibility checking.

Main entry point: process_with_brain()
"""

from .brain import process_with_brain, check_and_handle_timeouts
from .state_manager import (
    get_session_state,
    update_session_state,
    get_current_action,
    pause_queue,
    resume_queue
)
from .schema_checker import (
    fetch_schema_data,
    check_schema_completeness,
    check_data_exists
)
from .intent_logger import (
    log_intent,
    update_intent_status,
    get_session_intents
)
from .action_planner import (
    check_authorization,
    check_execution_limits,
    check_prerequisites,
    check_params
)

__all__ = [
    # Main entry point
    'process_with_brain',
    'check_and_handle_timeouts',
    
    # State management
    'get_session_state',
    'update_session_state',
    'get_current_action',
    'pause_queue',
    'resume_queue',
    
    # Schema checking
    'fetch_schema_data',
    'check_schema_completeness',
    'check_data_exists',
    
    # Intent logging
    'log_intent',
    'update_intent_status',
    'get_session_intents',
    
    # Action planning
    'check_authorization',
    'check_execution_limits',
    'check_prerequisites',
    'check_params'
]