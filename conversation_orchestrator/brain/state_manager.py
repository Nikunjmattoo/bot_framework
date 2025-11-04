"""
State Manager - Handles session state operations for Brain orchestration.

This module manages the sessions.state JSONB column which contains:
- action_queue: List of actions to be processed
- current_action_index: Which action is currently being processed
- expecting_response: Is Brain waiting for user input
- answer_sheet: Expected response format from user
- queue_paused: Is the queue currently paused
- loop_state: For future loop handling
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from db.models.sessions import SessionModel


def get_session_state(session_id: str, db: Session) -> Dict[str, Any]:
    """
    Get current session state.
    
    Args:
        session_id: Session UUID
        db: Database session
        
    Returns:
        Dictionary with state fields, or default empty state
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Return state or default structure
    return session.state or get_default_state()


def get_default_state() -> Dict[str, Any]:
    """
    Get default state structure for new sessions.
    
    Returns:
        Default state dictionary
    """
    return {
        'expecting_response': False,
        'answer_sheet': None,
        'active_task': None,
        'previous_intents': [],
        'conversation_context': {},
        'available_signals': [],
        'action_queue': [],
        'current_action_index': 0,
        'queue_paused': False,
        'queue_paused_reason': None,
        'loop_state': None
    }


def update_session_state(
    session_id: str,
    updates: Dict[str, Any],
    db: Session
) -> Dict[str, Any]:
    """
    Update session state with new values.
    
    Merges updates into existing state and persists to database.
    
    Args:
        session_id: Session UUID
        updates: Dictionary of fields to update
        db: Database session
        
    Returns:
        Updated state dictionary
    """
    session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    # Get current state or default
    current_state = session.state or get_default_state()
    
    # Merge updates
    current_state.update(updates)
    
    # Persist to database
    session.state = current_state
    db.commit()
    db.refresh(session)
    
    return current_state


def initialize_session_state(session: SessionModel) -> None:
    """
    Initialize state for a new session.
    
    Called when creating a new session.
    
    Args:
        session: SessionModel instance
    """
    session.state = get_default_state()


def update_action_in_queue(
    session_id: str,
    action_index: int,
    updated_action: Dict[str, Any],
    db: Session
) -> None:
    """
    Update a specific action in the action queue.
    
    Args:
        session_id: Session UUID
        action_index: Index of action in queue (0-based)
        updated_action: Updated action dictionary
        db: Database session
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    
    if action_index < 0 or action_index >= len(action_queue):
        raise ValueError(f"Invalid action_index {action_index} for queue of length {len(action_queue)}")
    
    # Update action
    action_queue[action_index] = updated_action
    
    # Save back to state
    update_session_state(session_id, {'action_queue': action_queue}, db)


def add_action_to_queue(
    session_id: str,
    action_data: Dict[str, Any],
    db: Session,
    position: Optional[int] = None
) -> int:
    """
    Add an action to the queue.
    
    Args:
        session_id: Session UUID
        action_data: Action dictionary to add
        db: Database session
        position: Optional position to insert at (default: append to end)
        
    Returns:
        Index where action was added
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    
    if position is None:
        # Append to end
        action_queue.append(action_data)
        position = len(action_queue) - 1
    else:
        # Insert at position
        action_queue.insert(position, action_data)
    
    update_session_state(session_id, {'action_queue': action_queue}, db)
    
    return position


def remove_action_from_queue(
    session_id: str,
    action_index: int,
    db: Session
) -> None:
    """
    Remove an action from the queue.
    
    Args:
        session_id: Session UUID
        action_index: Index of action to remove
        db: Database session
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    
    if action_index < 0 or action_index >= len(action_queue):
        raise ValueError(f"Invalid action_index {action_index}")
    
    action_queue.pop(action_index)
    
    # Adjust current_action_index if needed
    current_index = state.get('current_action_index', 0)
    if current_index >= len(action_queue) and len(action_queue) > 0:
        current_index = len(action_queue) - 1
    elif len(action_queue) == 0:
        current_index = 0
    
    update_session_state(session_id, {
        'action_queue': action_queue,
        'current_action_index': current_index
    }, db)


def clear_action_queue(session_id: str, db: Session) -> None:
    """
    Clear the entire action queue.
    
    Args:
        session_id: Session UUID
        db: Database session
    """
    update_session_state(session_id, {
        'action_queue': [],
        'current_action_index': 0,
        'queue_paused': False,
        'queue_paused_reason': None
    }, db)


def get_current_action(session_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """
    Get the currently processing action from queue.
    
    Args:
        session_id: Session UUID
        db: Database session
        
    Returns:
        Current action dictionary or None if queue is empty
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    current_index = state.get('current_action_index', 0)
    
    if not action_queue or current_index >= len(action_queue):
        return None
    
    return action_queue[current_index]


def pause_queue(
    session_id: str,
    reason: str,
    db: Session
) -> None:
    """
    Pause action queue processing.
    
    Args:
        session_id: Session UUID
        reason: Reason for pausing (e.g., "collecting_params", "awaiting_confirmation")
        db: Database session
    """
    update_session_state(session_id, {
        'queue_paused': True,
        'queue_paused_reason': reason,
        'paused_at': datetime.utcnow().isoformat()
    }, db)


def resume_queue(session_id: str, db: Session) -> None:
    """
    Resume action queue processing.
    
    Args:
        session_id: Session UUID
        db: Database session
    """
    update_session_state(session_id, {
        'queue_paused': False,
        'queue_paused_reason': None,
        'paused_at': None
    }, db)


def increment_current_action_index(session_id: str, db: Session) -> int:
    """
    Move to next action in queue.
    
    Args:
        session_id: Session UUID
        db: Database session
        
    Returns:
        New current_action_index
    """
    state = get_session_state(session_id, db)
    current_index = state.get('current_action_index', 0)
    new_index = current_index + 1
    
    update_session_state(session_id, {'current_action_index': new_index}, db)
    
    return new_index


def is_queue_empty(session_id: str, db: Session) -> bool:
    """
    Check if action queue is empty.
    
    Args:
        session_id: Session UUID
        db: Database session
        
    Returns:
        True if queue is empty
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    return len(action_queue) == 0


def has_more_actions(session_id: str, db: Session) -> bool:
    """
    Check if there are more actions to process in queue.
    
    Args:
        session_id: Session UUID
        db: Database session
        
    Returns:
        True if there are unprocessed actions
    """
    state = get_session_state(session_id, db)
    action_queue = state.get('action_queue', [])
    current_index = state.get('current_action_index', 0)
    
    return current_index < len(action_queue)


def build_answer_sheet(
    answer_type: str,
    options: Optional[Dict[str, List[str]]] = None,
    entity_type: Optional[str] = None,
    validation: Optional[str] = None,
    context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build an answer sheet for expected user responses.
    
    Args:
        answer_type: Type of answer expected ("confirmation", "single_choice", "entity", etc.)
        options: For choice types, mapping of option_id to possible user inputs
        entity_type: For entity types, what entity to extract
        validation: Validation regex for entity types
        context: Context string for this answer
        
    Returns:
        Answer sheet dictionary
    """
    answer_sheet = {
        'type': answer_type,
        'context': context or 'unknown'
    }
    
    if options:
        answer_sheet['options'] = options
    
    if entity_type:
        answer_sheet['entity_type'] = entity_type
    
    if validation:
        answer_sheet['validation'] = validation
    
    return answer_sheet