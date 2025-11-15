"""
Intent Logger - Tracks intent lifecycle in intent_ledger table.

Logs all detected intents and tracks their status through:
- detected → queued → executing → completed/failed/cancelled
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc
import logging
import uuid

from db.models.intent_ledger import IntentLedgerModel
from db.models.sessions import SessionModel

logger = logging.getLogger(__name__)


def log_intent(
    db: Session,
    session_id: str,
    intent_type_id: str,
    canonical_action: Optional[str],
    canonical_intent_candidates: Optional[List[str]],
    match_type: Optional[str],
    confidence: float,
    turn_number: int,
    sequence_order: int,
    entities: Dict[str, Any],
    reasoning: str,
    response_type: str,
    status: str = 'detected'
) -> str:
    """
    Log detected intent to intent_ledger.
    
    Args:
        db: Database session
        session_id: Session UUID
        intent_type_id: Type of intent
        canonical_action: Canonical action name (for action intents)
        canonical_intent_candidates: List of 1-2 candidate action names
        match_type: Matching strategy - "exact", "fuzzy", "synonym", "not_found", or None
        confidence: Confidence score
        turn_number: Turn number
        sequence_order: Sequence in multi-intent
        entities: Extracted entities
        reasoning: LLM reasoning
        response_type: self_respond or brain_required
        status: Initial status (default: detected)
        
    Returns:
        intent_id (UUID as string)
    """
    try:
        intent = IntentLedgerModel(
            id=str(uuid.uuid4()),
            session_id=session_id,
            intent_type_id=intent_type_id,
            canonical_action=canonical_action,
            canonical_intent_candidates=canonical_intent_candidates or [],
            match_type=match_type,
            confidence=confidence,
            turn_number=turn_number,
            sequence_order=sequence_order,
            entities=entities,
            reasoning=reasoning,
            response_type=response_type,
            status=status
        )
        
        db.add(intent)
        db.flush()
        
        return str(intent.id)
        
    except Exception as e:
        logger.error(f"Error logging intent for session {session_id}: {e}")
        raise


def update_intent_status(
    db: Session,
    intent_id: str,
    status: str,
    blocked_reason: Optional[str] = None
) -> None:
    """
    Update intent status in ledger.
    
    Args:
        db: Database session
        intent_id: Intent UUID
        status: New status
        blocked_reason: Optional reason if blocked
    """
    try:
        intent = db.query(IntentLedgerModel).filter(
            IntentLedgerModel.id == intent_id
        ).first()
        
        if intent:
            intent.status = status
            if blocked_reason:
                intent.blocked_reason = blocked_reason
            db.flush()
        else:
            logger.warning(f"Intent not found: {intent_id}")
            
    except Exception as e:
        logger.error(f"Error updating intent status for {intent_id}: {e}")
        raise


def check_action_completed(
    db: Session,
    session_id: str,
    canonical_action: str
) -> bool:
    """
    Check if action was already completed in this session.
    
    Args:
        db: Database session
        session_id: Session UUID
        canonical_action: Action name
        
    Returns:
        True if action was completed
    """
    try:
        completed = db.query(IntentLedgerModel).filter(
            IntentLedgerModel.session_id == session_id,
            IntentLedgerModel.canonical_action == canonical_action,
            IntentLedgerModel.status == 'completed'
        ).first()
        
        return completed is not None
        
    except Exception as e:
        logger.error(f"Error checking action completion for {canonical_action}: {e}")
        raise


def count_action_executions(
    db: Session,
    session_id: str,
    canonical_action: str
) -> int:
    """
    Count how many times action was executed in this session.
    
    Args:
        db: Database session
        session_id: Session UUID
        canonical_action: Action name
        
    Returns:
        Execution count
    """
    try:
        count = db.query(IntentLedgerModel).filter(
            IntentLedgerModel.session_id == session_id,
            IntentLedgerModel.canonical_action == canonical_action,
            IntentLedgerModel.status.in_(['completed', 'executing'])
        ).count()
        
        return count
        
    except Exception as e:
        logger.error(f"Error counting executions for {canonical_action}: {e}")
        raise


def count_action_executions_today(
    db: Session,
    user_id: str,
    canonical_action: str
) -> int:
    """
    Count how many times action was executed today by this user.
    
    Args:
        db: Database session
        user_id: User UUID
        canonical_action: Action name
        
    Returns:
        Execution count for today
    """
    try:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        
        count = db.query(IntentLedgerModel).join(
            SessionModel,
            IntentLedgerModel.session_id == SessionModel.id
        ).filter(
            SessionModel.user_id == user_id,
            IntentLedgerModel.canonical_action == canonical_action,
            IntentLedgerModel.status == 'completed',
            IntentLedgerModel.created_at >= today_start
        ).count()
        
        return count
        
    except Exception as e:
        logger.error(f"Error counting today's executions for {canonical_action}: {e}")
        raise


def get_last_execution(
    db: Session,
    session_id: str,
    canonical_action: str
) -> Optional[datetime]:
    """
    Get timestamp of last execution of this action.
    
    Args:
        db: Database session
        session_id: Session UUID
        canonical_action: Action name
        
    Returns:
        Datetime of last execution or None
    """
    try:
        last = db.query(IntentLedgerModel).filter(
            IntentLedgerModel.session_id == session_id,
            IntentLedgerModel.canonical_action == canonical_action,
            IntentLedgerModel.status == 'completed'
        ).order_by(desc(IntentLedgerModel.created_at)).first()
        
        return last.created_at if last else None
        
    except Exception as e:
        logger.error(f"Error getting last execution for {canonical_action}: {e}")
        raise


def get_session_intents(
    db: Session,
    session_id: str
) -> List[Dict[str, Any]]:
    """
    Get all intents for a session.
    
    Args:
        db: Database session
        session_id: Session UUID
        
    Returns:
        List of intent dictionaries
    """
    try:
        intents = db.query(IntentLedgerModel).filter(
            IntentLedgerModel.session_id == session_id
        ).order_by(IntentLedgerModel.turn_number, IntentLedgerModel.sequence_order).all()
        
        return [
            {
                'intent_id': str(intent.id),
                'intent_type': intent.intent_type_id,
                'canonical_action': intent.canonical_action,
                'canonical_intent_candidates': intent.canonical_intent_candidates,
                'match_type': intent.match_type,
                'confidence': intent.confidence,
                'status': intent.status,
                'turn_number': intent.turn_number
            }
            for intent in intents
        ]
        
    except Exception as e:
        logger.error(f"Error getting session intents for {session_id}: {e}")
        raise