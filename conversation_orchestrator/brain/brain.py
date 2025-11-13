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
from db.db import get_db

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


async def check_and_handle_timeouts(db: Session, session_id: str) -> Dict[str, Any]:
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
    state = get_session_state(db, session_id)
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
                update_action_in_queue(db, session_id, i, queued_action)
                
                # Update intent ledger
                intent_id = queued_action.get('intent_id')
                if intent_id:
                    update_intent_status(intent_id, 'cancelled', blocked_reason=f'timeout_{status}')
                
                expired_actions.append(queued_action['canonical_action'])
        
        # Check total queue age
        created_at = datetime.fromisoformat(queued_action['created_at'])
        age_seconds = (now - created_at).total_seconds()
        
        if age_seconds > TIMEOUT_CONFIG['max_queue_age']:
            queued_action['status'] = 'expired'
            queued_action['expired_at'] = now.isoformat()
            queued_action['expiry_reason'] = 'max_queue_age_exceeded'
            update_action_in_queue(db, session_id, i, queued_action)
            
            intent_id = queued_action.get('intent_id')
            if intent_id:
                update_intent_status(intent_id, 'cancelled', blocked_reason='queue_expired')
            
            expired_actions.append(queued_action['canonical_action'])
    
    # Remove expired actions from queue
    if expired_actions:
        action_queue = [a for a in action_queue if a.get('status') not in ['expired']]
        update_session_state(db, session_id, {
            'action_queue': action_queue,
            'current_action_index': 0
        })
    
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
    user_id: str
) -> List[Dict[str, Any]]:
    """
    Order actions by dependency resolution.
    
    Uses topological sort to ensure dependencies execute first.
    """
    try:
        db: Session = next(get_db())
        try:
            # Build dependency graph
            graph = {}
            action_map = {}
            
            for action_data in actions_data:
                action = action_data['action']
                canonical_name = action.canonical_name
                
                action_map[canonical_name] = action_data
                graph[canonical_name] = action.prerequisite_actions or []
            
            # Topological sort
            visited = set()
            sorted_actions = []
            
            def visit(action_name):
                if action_name in visited:
                    return
                
                visited.add(action_name)
                
                # Visit dependencies first
                for dep in graph.get(action_name, []):
                    if dep in action_map:
                        visit(dep)
                
                # Then add this action
                if action_name in action_map:
                    sorted_actions.append(action_map[action_name])
            
            # Visit all actions
            for action_name in graph.keys():
                visit(action_name)
            
            return sorted_actions
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error ordering actions: {e}")
        # If ordering fails, return original order
        return actions_data


def expand_workflow(
    action: ActionModel,
    session_id: str,
    user_id: str,
    brand_id: str
) -> List[Dict[str, Any]]:
    """
    Expand workflow action into individual steps.
    
    Returns:
        List of action data dictionaries to add to queue
    """
    try:
        db: Session = next(get_db())
        try:
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
                should_skip, skip_reason = should_skip_workflow_action(wf_action, user_id, brand_id)
                
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
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error expanding workflow: {e}")
        return []


async def process_brain(
    db: Session,
    intent_result: Dict[str, Any],
    session_id: str,
    user_id: str,
    instance_id: str,
    brand_id: str,
    turn_number: int
) -> Dict[str, Any]:
    """
    Main Brain entry point.
    
    Processes intents detected by LLM and orchestrates action execution.
    
    Flow:
    1. Check for stuck/expired actions (timeouts)
    2. For each detected intent:
       a. Log to intent_ledger
       b. Map to canonical_action
       c. Check eligibility (auth, limits, prerequisites, schemas)
       d. Add to action_queue or respond with blocker
    3. Process action_queue (if not paused)
    4. Return response (text + metadata)
    
    Args:
        intent_result: Output from intent detector
        session_id: Session UUID
        user_id: User UUID
        instance_id: Instance UUID
        brand_id: Brand identifier
        turn_number: Current turn number
        
    Returns:
        {
            'text': str,
            'status': str,
            'actions_completed': List[str],
            'actions_pending': List[str]
        }
    """
    try:
        db: Session = next(get_db())
        try:
            response_parts = []
            
            # Step 1: Check for timeouts FIRST
            timeout_result = await check_and_handle_timeouts(db, session_id)
            
            if timeout_result['should_notify']:
                expired_list = ', '.join(timeout_result['expired_actions'])
                response_parts.append(f"⏰ Cancelled {timeout_result['cleaned_count']} expired action(s): {expired_list}")
            
            # Step 2: Load user for authorization checks
            user = db.query(UserModel).filter(UserModel.id == user_id).first()
            if not user:
                logger.error(f"User not found: {user_id}")
                return {
                    'text': "I'm having trouble accessing your account. Please try again.",
                    'status': 'error',
                    'error': 'user_not_found'
                }
            
            # Step 3: Process each detected intent
            intents = intent_result.get('intents', [])
            action_queue = []
            
            for intent in intents:
                intent_type = intent.get('intent_type')
                canonical_action = intent.get('canonical_intent')
                confidence = intent.get('confidence', 0.0)
                entities = intent.get('entities', {})
                
                # Log intent to ledger
                intent_id = log_intent(
                    session_id=session_id,
                    intent_type_id=intent_type,
                    canonical_action=canonical_action,
                    confidence=confidence,
                    turn_number=turn_number,
                    sequence_order=len(action_queue),
                    entities=entities,
                    reasoning=intent.get('reasoning', ''),
                    response_type='brain_required'
                )
                
                # Load action definition
                action = db.query(ActionModel).filter(
                    ActionModel.canonical_name == canonical_action,
                    ActionModel.brand_id == brand_id,
                    ActionModel.is_active == True
                ).first()
                
                if not action:
                    logger.warning(f"Action not found: {canonical_action}")
                    update_intent_status(intent_id, 'failed', blocked_reason='action_not_found')
                    response_parts.append(f"❌ Unknown action: {canonical_action}")
                    continue
                
                # Step 4: Check if action already completed in this session
                if check_action_completed(session_id, canonical_action):
                    if not action.allow_multiple:
                        update_intent_status(intent_id, 'skipped', blocked_reason='already_completed')
                        response_parts.append(f"✓ Already completed: {canonical_action}")
                        continue
                
                # Step 5: Check authorization
                authorized, auth_reasons = check_authorization(action, user)
                if not authorized:
                    update_intent_status(intent_id, 'blocked', blocked_reason=', '.join(auth_reasons))
                    response_parts.append(f"🔒 Not authorized: {canonical_action} ({', '.join(auth_reasons)})")
                    continue
                
                # Step 6: Check execution limits
                can_execute, limit_reason = check_execution_limits(action, session_id, user_id)
                if not can_execute:
                    update_intent_status(intent_id, 'blocked', blocked_reason=limit_reason)
                    response_parts.append(f"⛔ Execution limit: {canonical_action} ({limit_reason})")
                    continue
                
                # Step 7: Check schema dependencies
                if action.required_schemas:
                    schema_results = check_multiple_schemas(
                        schema_dependencies=action.required_schemas,
                        user_id=user_id,
                        brand_id=brand_id
                    )
                    
                    incomplete_schemas = [
                        s['schema_id'] for s in schema_results 
                        if s['status'] != 'complete'
                    ]
                    
                    if incomplete_schemas:
                        update_intent_status(intent_id, 'blocked', blocked_reason=f"schemas_incomplete: {', '.join(incomplete_schemas)}")
                        response_parts.append(f"📋 Missing data for {canonical_action}: {', '.join(incomplete_schemas)}")
                        continue
                
                # Step 8: Check prerequisites
                prereq_met, prereq_reasons = check_prerequisites(action, session_id, user_id, brand_id)
                if not prereq_met:
                    update_intent_status(intent_id, 'blocked', blocked_reason=', '.join(prereq_reasons))
                    response_parts.append(f"⚠️ Prerequisites not met: {canonical_action}")
                    continue
                
                # Step 9: Check parameters
                params_complete, missing_params = check_params(action, entities)
                
                # All checks passed - add to queue
                action_data = {
                    'intent_id': intent_id,
                    'canonical_action': canonical_action,
                    'sequence': len(action_queue),
                    'priority': action.priority or 50,
                    'status': 'queued',
                    'mode': 'collect_params' if not params_complete else 'execute',
                    'source': 'intent_detector',
                    'params_collected': entities,
                    'params_missing': missing_params,
                    'blocked_reasons': [],
                    'stuck_count': 0,
                    'created_at': datetime.utcnow().isoformat(),
                    'last_activity_at': datetime.utcnow().isoformat()
                }
                
                action_queue.append(action_data)
                update_intent_status(intent_id, 'queued')
                
                # If workflow action, expand workflow
                if action.workflow_id:
                    workflow_actions = expand_workflow(action, session_id, user_id, brand_id)
                    action_queue.extend(workflow_actions)
            
            # Step 10: Persist queue to session state
            if action_queue:
                state = get_session_state(db, session_id)
                existing_queue = state.get('action_queue', [])
                existing_queue.extend(action_queue)
                
                update_session_state(db, session_id, {
                    'action_queue': existing_queue
                })
            
            # Step 11: Build wires for next turn
            state = get_session_state(db, session_id)
            
            # Wire 1: expecting_response
            expecting_response_state = state.get('queue_paused', False)
            
            # Wire 2: answer_sheet
            answer_sheet_state = state.get('answer_sheet', None)
            
            # Wire 3: active_task
            active_task_state = state.get('active_task', None)
            
            # Wire 4: previous_intents (last 10)
            previous_intents_state = state.get('previous_intents', [])
            previous_intents_state.extend([
                intent.get('canonical_intent') for intent in intents
            ])
            previous_intents_state = previous_intents_state[-10:]
            
            # Wire 5: conversation_context
            conversation_context_state = state.get('conversation_context', {})
            
            # Wire 6: available_signals
            available_signals_state = []
            if answer_sheet_state:
                options = answer_sheet_state.get("options", {})
                for key, variants in options.items():
                    available_signals_state.append(key)
                    available_signals_state.extend(variants)
                available_signals_state = list(set(available_signals_state))
            
            # Update session state with all 6 wires
            update_session_state(db, session_id, {
                "expecting_response": expecting_response_state,
                "answer_sheet": answer_sheet_state,
                "active_task": active_task_state,
                "previous_intents": previous_intents_state,
                "conversation_context": conversation_context_state,
                "available_signals": available_signals_state
            })
            
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
            
            # Step 12: Process queue (COMMENTED OUT - TO BE IMPLEMENTED LATER)
            # NOTE: Actual queue processing would go here
            # For now, returning placeholder
            
            response_parts.append(f"🔄 Queued {len(action_queue)} action(s) for processing")
            
            result = {
                'text': '\n'.join(response_parts),
                'status': 'completed',
                'actions_completed': [],
                'actions_pending': [a['canonical_action'] for a in action_queue]
            }
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Brain processing error for session {session_id}: {e}")
        raise