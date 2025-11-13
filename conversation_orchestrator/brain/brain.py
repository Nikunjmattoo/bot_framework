"""
Brain - Main orchestration logic for action-based intent processing.

This is the CORE of the system. Handles:
- Multi-intent ordering and conflict detection
- Action queue management
- Eligibility checking (auth, limits, prerequisites, params, confirmation)
- Execution with retries
- State management
- Timeout handling
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import asyncio
import logging

from db.models.actions import ActionModel
from db.models.workflows import WorkflowModel
from db.models.users import UserModel
from .state_manager import (
    get_session_state,
    update_session_state,
    update_action_in_queue,
    add_action_to_queue,
    get_current_action,
    pause_queue,
    resume_queue,
    increment_current_action_index,
    has_more_actions,
    build_answer_sheet
)
from .schema_checker import check_multiple_schemas, check_schema_exists
from .intent_logger import (
    log_intent,
    update_intent_status,
    check_action_completed
)
from .action_planner import (
    check_authorization,
    check_execution_limits,
    check_prerequisites,
    check_params,
    should_skip_workflow_action
)

logger = logging.getLogger(__name__)


# Timeout configuration (seconds)
TIMEOUT_CONFIG = {
    'collecting_params': 300,      # 5 minutes
    'awaiting_confirmation': 60,   # 1 minute
    'max_queue_age': 1800          # 30 minutes
}


async def check_and_handle_timeouts(session_id: str, db: Session) -> Dict[str, Any]:
    """
    Check action queue for expired actions and clean them up.
    
    Called at the START of every message processing.
    
    Returns:
        {
            'cleaned_count': int,
            'expired_actions': List[str],
            'should_notify': bool
        }
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    
    now = datetime.utcnow()
    expired_actions = []
    
    for i, queued_action in enumerate(action_queue):
        status = queued_action.get('status')
        
        # Skip terminal states
        if status in ['completed', 'failed', 'cancelled', 'skipped', 'expired', 'undone']:
            continue
        
        # Check individual action timeout
        timeout_at_str = queued_action.get('timeout_at')
        if timeout_at_str:
            timeout_at = datetime.fromisoformat(timeout_at_str)
            if now > timeout_at:
                queued_action['status'] = 'expired'
                queued_action['expired_at'] = now.isoformat()
                queued_action['expiry_reason'] = f'timeout_in_{status}'
                update_action_in_queue(session_id, i, queued_action, db)
                
                # Update intent ledger
                intent_id = queued_action.get('intent_id')
                if intent_id:
                    update_intent_status(intent_id, 'cancelled', db, blocked_reason=f'timeout_{status}')
                
                expired_actions.append(queued_action['canonical_action'])
        
        # Check total queue age
        created_at = datetime.fromisoformat(queued_action['created_at'])
        age_seconds = (now - created_at).total_seconds()
        
        if age_seconds > TIMEOUT_CONFIG['max_queue_age']:
            queued_action['status'] = 'expired'
            queued_action['expired_at'] = now.isoformat()
            queued_action['expiry_reason'] = 'max_queue_age_exceeded'
            update_action_in_queue(session_id, i, queued_action, db)
            
            intent_id = queued_action.get('intent_id')
            if intent_id:
                update_intent_status(intent_id, 'cancelled', db, blocked_reason='queue_expired')
            
            expired_actions.append(queued_action['canonical_action'])
    
    # Remove expired actions from queue
    if expired_actions:
        action_queue = [a for a in action_queue if a.get('status') not in ['expired']]
        update_session_state(session_id, {
            'action_queue': action_queue,
            'current_action_index': 0
        }, db)
    
    return {
        'cleaned_count': len(expired_actions),
        'expired_actions': expired_actions,
        'should_notify': len(expired_actions) > 0
    }


def detect_conflicts(actions_data: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Detect conflicting actions (opposites).
    
    Returns:
        List of conflict dictionaries
    """
    conflicts = []
    
    for i, action_a in enumerate(actions_data):
        for j, action_b in enumerate(actions_data):
            if i >= j:
                continue
            
            action_a_model = action_a['action']
            action_b_model = action_b['action']
            
            # Check if A is opposite of B
            if action_a_model.opposite_action == action_b_model.canonical_name:
                conflicts.append({
                    'action_1': action_a_model.canonical_name,
                    'action_2': action_b_model.canonical_name,
                    'reason': 'opposite_actions'
                })
    
    return conflicts


def order_actions_by_dependencies(
    actions_data: List[Dict[str, Any]],
    user_id: str,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Order actions by dependency resolution.
    
    Uses topological sort to ensure dependencies execute first.
    """
    # Build dependency graph
    graph = {}
    action_map = {}
    
    for action_data in actions_data:
        action = action_data['action']
        canonical_name = action.canonical_name
        
        action_map[canonical_name] = action_data
        
        # Get dependencies
        prereqs = action.get_prerequisites()
        depends_on = prereqs.get('depends_on_actions', [])
        
        # Filter out already fulfilled dependencies
        unfulfilled_deps = [
            dep for dep in depends_on
            if not check_action_completed(dep, user_id, db)
        ]
        
        graph[canonical_name] = unfulfilled_deps
    
    # Topological sort
    sorted_names = topological_sort(graph)
    
    # Rebuild actions_data in sorted order
    sorted_actions = []
    for name in sorted_names:
        if name in action_map:
            sorted_actions.append(action_map[name])
    
    return sorted_actions


def topological_sort(graph: Dict[str, List[str]]) -> List[str]:
    """
    Topological sort using Kahn's algorithm.
    """
    # Calculate in-degree
    in_degree = {node: 0 for node in graph}
    for deps in graph.values():
        for dep in deps:
            if dep in in_degree:
                in_degree[dep] += 1
    
    # Find nodes with no dependencies
    queue = [node for node, degree in in_degree.items() if degree == 0]
    sorted_list = []
    
    while queue:
        current = queue.pop(0)
        sorted_list.append(current)
        
        # Reduce in-degree for dependents
        for dependent in graph.get(current, []):
            if dependent in in_degree:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
    
    return sorted_list


def expand_workflow_into_queue(
    action: ActionModel,
    user_id: str,
    brand_id: str,
    session_id: str,
    db: Session
) -> List[Dict[str, Any]]:
    """
    Expand workflow into individual action queue items.
    
    Args:
        action: The action that triggers the workflow
        user_id: User UUID
        brand_id: Brand UUID
        session_id: Session UUID
        db: Database session
        
    Returns:
        List of action data dictionaries to add to queue
    """
    if not action.workflow_id:
        return []
    
    # Load workflow actions
    workflow_actions = db.query(ActionModel).filter(
        ActionModel.workflow_id == action.workflow_id,
        ActionModel.is_active == True
    ).order_by(ActionModel.sequence_number).all()
    
    queue_additions = []
    
    for wf_action in workflow_actions:
        # Check if should skip
        should_skip, skip_reason = should_skip_workflow_action(wf_action, user_id, brand_id, db)
        
        if should_skip:
            # Log as skipped
            log_intent(
                session_id=session_id,
                intent_type_id='action',
                canonical_action=wf_action.canonical_name,
                confidence=1.0,
                turn_number=0,  # Workflow actions don't have turn numbers
                sequence_order=wf_action.sequence_number,
                entities={},
                reasoning=f'Skipped: {skip_reason}',
                response_type='brain_required',
                db=db,
                status='skipped'
            )
            continue
        
        # Add to queue
        queue_additions.append({
            'intent_id': None,  # Workflow actions don't have original intents
            'canonical_action': wf_action.canonical_name,
            'sequence': wf_action.sequence_number,
            'priority': wf_action.sequence_number,
            'status': 'queued',
            'mode': 'execute',
            'source': 'workflow',
            'params_collected': {},
            'params_missing': [],
            'blocked_reasons': [],
            'stuck_count': 0,
            'created_at': datetime.utcnow().isoformat(),
            'last_activity_at': datetime.utcnow().isoformat()
        })
    
    return queue_additions


async def process_with_brain(
    intent_result: Dict[str, Any],
    session_id: str,
    user_id: str,
    instance_id: str,
    brand_id: str,
    turn_number: int,
    db: Session
) -> Dict[str, Any]:
    """
    Main Brain entry point.
    
    Processes intents detected by LLM and orchestrates action execution.
    
    Args:
        intent_result: Result from intent detector
        session_id: Session UUID
        user_id: User UUID
        instance_id: Instance UUID
        brand_id: Brand UUID
        turn_number: Current conversation turn
        db: Database session
        
    Returns:
        {
            'text': str,  # Response to user
            'status': str,  # 'completed', 'waiting_input', 'error'
            'actions_completed': List[str],
            'actions_pending': List[str]
        }
    """
    # Step 1: Check for expired actions
    timeout_result = await check_and_handle_timeouts(session_id, db)
    
    response_parts = []
    
    if timeout_result['should_notify']:
        expired_list = ', '.join(timeout_result['expired_actions'])
        response_parts.append(f"⏰ Previous actions expired: {expired_list}")
    
    # Step 2: Load user
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    
    # Step 3: Extract intents
    intents = intent_result.get('intents', [])
    
    if not intents:
        return {
            'text': "I didn't detect any intent.",
            'status': 'error',
            'actions_completed': [],
            'actions_pending': []
        }
    
    # Step 4: Log all intents
    intent_ids = []
    for intent in intents:
        intent_id = log_intent(
            session_id=session_id,
            intent_type_id=intent.get('intent_type', 'action'),
            canonical_action=intent.get('canonical_intent'),  # ← FIXED: was canonical_action
            confidence=intent.get('confidence', 0.0),
            turn_number=turn_number,
            sequence_order=intent.get('sequence', 0),
            entities=intent.get('entities', {}),
            reasoning=intent.get('reasoning'),
            response_type='brain_required',
            db=db
        )
        intent_ids.append(intent_id)
    
    # Step 5: Load actions from database
    actions_data = []
    
    for i, intent in enumerate(intents):
        canonical_action = intent.get('canonical_intent')  # ← FIXED: was canonical_action
        
        if not canonical_action:
            continue
        
        action = db.query(ActionModel).filter(
            ActionModel.canonical_name == canonical_action,
            ActionModel.instance_id == instance_id,
            ActionModel.is_active == True
        ).first()
        
        if not action:
            update_intent_status(intent_ids[i], 'failed', db, blocked_reason='action_not_found')
            response_parts.append(f"❌ I don't know how to {canonical_action}")
            continue
        
        actions_data.append({
            'intent': intent,
            'intent_id': intent_ids[i],
            'action': action,
            'sequence': intent.get('sequence', 0)
        })
    
    if not actions_data:
        return {
            'text': '\n'.join(response_parts),
            'status': 'error',
            'actions_completed': [],
            'actions_pending': []
        }
    
    # Step 6: Detect conflicts
    conflicts = detect_conflicts(actions_data)
    
    if conflicts:
        conflict_text = f"You want to both {conflicts[0]['action_1']} and {conflicts[0]['action_2']}. Which one?"
        response_parts.append(conflict_text)
        return {
            'text': '\n'.join(response_parts),
            'status': 'waiting_input',
            'actions_completed': [],
            'actions_pending': []
        }
    
    # Step 7: Order by dependencies
    ordered_actions = order_actions_by_dependencies(actions_data, user_id, db)
    
    # Step 8: Build action queue
    action_queue = []
    
    for action_data in ordered_actions:
        action = action_data['action']
        intent = action_data['intent']
        
        # Check if triggers workflow
        if action.workflow_id:
            workflow_steps = expand_workflow_into_queue(action, user_id, brand_id, session_id, db)
            action_queue.extend(workflow_steps)
        else:
            action_queue.append({
                'intent_id': action_data['intent_id'],
                'canonical_action': action.canonical_name,
                'sequence': intent.get('sequence', 0),
                'priority': len(action_queue) + 1,
                'status': 'queued',
                'mode': intent.get('mode', 'execute'),
                'source': 'intent',
                'params_collected': intent.get('entities', {}),
                'params_missing': [],
                'blocked_reasons': [],
                'stuck_count': 0,
                'created_at': datetime.utcnow().isoformat(),
                'last_activity_at': datetime.utcnow().isoformat()
            })
    
    # Save queue to state
    update_session_state(session_id, {
        'action_queue': action_queue,
        'current_action_index': 0,
        'queue_paused': False
    }, db)
    
    # Step 9: POPULATE BRAIN STATE FOR INTENT DETECTOR ✅
    # This populates the 6 wires that Intent Detector needs for next turn
    
    # Wire 3: active_task
    active_task_state = None
    if action_queue:
        first_action = action_queue[0]
        active_task_state = {
            "task_id": first_action.get("intent_id"),
            "canonical_action": first_action.get("canonical_action"),
            "params_collected": first_action.get("params_collected", {}),
            "params_missing": first_action.get("params_missing", []),
            "status": first_action.get("status", "queued"),
            "created_at": first_action.get("created_at"),
            "last_activity_at": first_action.get("last_activity_at")
        }
    
    # Wire 4: previous_intents
    previous_intents_state = []
    for i, action_data in enumerate(ordered_actions):
        previous_intents_state.append({
            "intent_type": action_data['intent'].get('intent_type'),
            "canonical_action": action_data['action'].canonical_name,
            "confidence": action_data['intent'].get('confidence'),
            "sequence": action_data['intent'].get('sequence'),
            "turn": turn_number
        })
    
    # Wire 6: conversation_context
    conversation_context_state = {
        "domain": "general",  # TODO: Derive from instance config later
        "user_state": "queued_actions" if action_queue else "idle",
        "last_action": previous_intents_state[-1].get("canonical_action") if previous_intents_state else None,
        "pending_confirmation": False,  # Will be set when we implement confirmation logic
        "turn_number": turn_number
    }
    
    # Wire 1: expecting_response (default False for now, will be set when collecting params)
    expecting_response_state = False
    
    # Wire 2: answer_sheet (default None for now, will be set when collecting params)
    answer_sheet_state = None
    
    # Wire 5: available_signals (derived from answer_sheet)
    available_signals_state = []
    if answer_sheet_state:
        # Extract all signal variants from answer_sheet options
        options = answer_sheet_state.get("options", {})
        for key, variants in options.items():
            available_signals_state.append(key)
            available_signals_state.extend(variants)
        # Remove duplicates
        available_signals_state = list(set(available_signals_state))
    
    # Update session state with all 6 wires
    update_session_state(session_id, {
        "expecting_response": expecting_response_state,
        "answer_sheet": answer_sheet_state,
        "active_task": active_task_state,
        "previous_intents": previous_intents_state,
        "conversation_context": conversation_context_state,
        "available_signals": available_signals_state
    }, db)
    
    logger.info(
        "brain:state_populated",
        extra={
            "session_id": session_id,
            "expecting_response": expecting_response_state,
            "has_answer_sheet": answer_sheet_state is not None,
            "has_active_task": active_task_state is not None,
            "previous_intents_count": len(previous_intents_state),
            "available_signals_count": len(available_signals_state)
        }
    )
    
    # Step 10: Process queue (COMMENTED OUT - TO BE IMPLEMENTED LATER)
    # NOTE: Actual queue processing would go here
    # For now, returning placeholder
    
    response_parts.append(f"🔄 Queued {len(action_queue)} action(s) for processing")
    
    return {
        'text': '\n'.join(response_parts),
        'status': 'completed',
        'actions_completed': [],
        'actions_pending': [a['canonical_action'] for a in action_queue]
    }