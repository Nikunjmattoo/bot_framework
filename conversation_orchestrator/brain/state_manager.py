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
import logging

from db.db import get_db
from db.models.sessions import SessionModel

logger = logging.getLogger(__name__)


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


def get_session_state(session_id: str) -> Dict[str, Any]:
    """
    Get current session state.
    
    Args:
        session_id: Session UUID
        
    Returns:
        Dictionary with state fields, or default empty state
    """
    try:
        db: Session = next(get_db())
        try:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            return session.state or get_default_state()
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting session state for {session_id}: {e}")
        raise


def update_session_state(
    session_id: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update session state with new values.
    
    Merges updates into existing state and persists to database.
    
    Args:
        session_id: Session UUID
        updates: Dictionary of fields to update
        
    Returns:
        Updated state dictionary
    """
    try:
        db: Session = next(get_db())
        try:
            session = db.query(SessionModel).filter(SessionModel.id == session_id).first()
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            current_state = session.state or get_default_state()
            current_state.update(updates)
            
            session.state = current_state
            db.commit()
            db.refresh(session)
            
            return current_state
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating session state for {session_id}: {e}")
        raise


def initialize_session_state(session: SessionModel) -> None:
    """
    Initialize state for a new session.
    
    Called when creating a new session.
    
    Args:
        session: Session model instance
    """
    session.state = get_default_state()


def update_action_in_queue(
    session_id: str,
    action_index: int,
    updated_action: Dict[str, Any]
) -> None:
    """
    Update a specific action in the queue.
    
    Args:
        session_id: Session UUID
        action_index: Index of action in queue
        updated_action: Updated action dictionary
    """
    try:
        db: Session = next(get_db())
        try:
            state = get_session_state(session_id)
            action_queue = state.get('action_queue', [])
            
            if 0 <= action_index < len(action_queue):
                action_queue[action_index] = updated_action
                update_session_state(session_id, {'action_queue': action_queue})
            else:
                logger.warning(f"Invalid action index {action_index} for session {session_id}")
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error updating action in queue for {session_id}: {e}")
        raise


def add_action_to_queue(
    session_id: str,
    action_data: Dict[str, Any]
) -> None:
    """
    Add a new action to the queue.
    
    Args:
        session_id: Session UUID
        action_data: Action dictionary to add
    """
    try:
        db: Session = next(get_db())
        try:
            state = get_session_state(session_id)
            action_queue = state.get('action_queue', [])
            action_queue.append(action_data)
            update_session_state(session_id, {'action_queue': action_queue})
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error adding action to queue for {session_id}: {e}")
        raise


def get_current_action(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the current action being processed.
    
    Args:
        session_id: Session UUID
        
    Returns:
        Current action dictionary or None
    """
    try:
        db: Session = next(get_db())
        try:
            state = get_session_state(session_id)
            action_queue = state.get('action_queue', [])
            current_index = state.get('current_action_index', 0)
            
            if 0 <= current_index < len(action_queue):
                return action_queue[current_index]
            
            return None
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error getting current action for {session_id}: {e}")
        raise


def pause_queue(session_id: str, reason: str) -> None:
    """
    Pause the action queue.
    
    Args:
        session_id: Session UUID
        reason: Reason for pausing
    """
    try:
        db: Session = next(get_db())
        try:
            update_session_state(session_id, {
                'queue_paused': True,
                'queue_paused_reason': reason
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error pausing queue for {session_id}: {e}")
        raise


def resume_queue(session_id: str) -> None:
    """
    Resume the action queue.
    
    Args:
        session_id: Session UUID
    """
    try:
        db: Session = next(get_db())
        try:
            update_session_state(session_id, {
                'queue_paused': False,
                'queue_paused_reason': None
            })
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error resuming queue for {session_id}: {e}")
        raise


def increment_current_action_index(session_id: str) -> None:
    """
    Move to the next action in queue.
    
    Args:
        session_id: Session UUID
    """
    try:
        db: Session = next(get_db())
        try:
            state = get_session_state(session_id)
            current_index = state.get('current_action_index', 0)
            update_session_state(session_id, {'current_action_index': current_index + 1})
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error incrementing action index for {session_id}: {e}")
        raise


def has_more_actions(session_id: str) -> bool:
    """
    Check if there are more actions to process.
    
    Args:
        session_id: Session UUID
        
    Returns:
        True if more actions exist
    """
    try:
        db: Session = next(get_db())
        try:
            state = get_session_state(session_id)
            action_queue = state.get('action_queue', [])
            current_index = state.get('current_action_index', 0)
            
            return current_index < len(action_queue)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error checking more actions for {session_id}: {e}")
        raise


def build_answer_sheet(action) -> Optional[Dict[str, Any]]:
    """
    Build answer sheet for parameter collection.
    
    Args:
        action: Action model with param_schema
        
    Returns:
        Answer sheet dictionary or None
    """
    if not hasattr(action, 'param_schema') or not action.param_schema:
        return None
    
    answer_sheet = {
        'action': action.canonical_name,
        'params': {},
        'options': {}
    }
    
    for param_name, param_config in action.param_schema.items():
        if param_config.get('enum'):
            answer_sheet['options'][param_name] = param_config['enum']
    
    return answer_sheet