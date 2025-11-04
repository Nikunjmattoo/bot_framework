"""
Intent Logger - Helper functions for logging intents to intent_ledger table.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from db.models.intent_ledger import IntentLedgerModel


def log_intent(
    session_id: str,
    intent_type_id: str,
    canonical_action: Optional[str],
    confidence: float,
    turn_number: int,
    sequence_order: Optional[int],
    entities: Dict[str, Any],
    reasoning: Optional[str],
    response_type: str,
    db: Session,
    status: str = "new"
) -> str:
    """
    Log a new intent to intent_ledger.
    
    Args:
        session_id: Session UUID
        intent_type_id: Intent type (e.g., "action", "response", "clarification")
        canonical_action: Action name (if intent_type is "action")
        confidence: Confidence score (0.0-1.0)
        turn_number: Conversation turn number
        sequence_order: Order within multi-intent detection
        entities: Extracted entities as dict
        reasoning: LLM reasoning for this intent
        response_type: Type of response generated
        db: Database session
        status: Initial status (default: "new")
        
    Returns:
        Intent ID (UUID as string)
    """
    intent = IntentLedgerModel(
        session_id=session_id,
        intent_type_id=intent_type_id,
        canonical_action=canonical_action,
        confidence=confidence,
        turn_number=turn_number,
        sequence_order=sequence_order,
        entities=entities or {},
        reasoning=reasoning,
        status=status,
        response_type=response_type,
        response_text=None,
        blocked_reason=None,
        triggered_action_ids=[]
    )
    
    db.add(intent)
    db.commit()
    db.refresh(intent)
    
    return str(intent.id)


def update_intent_status(
    intent_id: str,
    new_status: str,
    db: Session,
    blocked_reason: Optional[str] = None,
    response_text: Optional[str] = None
) -> None:
    """
    Update intent status.
    
    Args:
        intent_id: Intent UUID
        new_status: New status value
        db: Database session
        blocked_reason: Optional reason if status is "blocked" or "failed"
        response_text: Optional response text
    """
    intent = db.query(IntentLedgerModel).filter(IntentLedgerModel.id == intent_id).first()
    
    if not intent:
        raise ValueError(f"Intent {intent_id} not found")
    
    intent.status = new_status
    intent.updated_at = datetime.utcnow()
    
    if blocked_reason:
        intent.blocked_reason = blocked_reason
    
    if response_text:
        intent.response_text = response_text
    
    db.commit()


def get_intent(intent_id: str, db: Session) -> Optional[IntentLedgerModel]:
    """
    Get intent by ID.
    
    Args:
        intent_id: Intent UUID
        db: Database session
        
    Returns:
        IntentLedgerModel or None
    """
    return db.query(IntentLedgerModel).filter(IntentLedgerModel.id == intent_id).first()


def get_session_intents(
    session_id: str,
    db: Session,
    limit: Optional[int] = None
) -> List[IntentLedgerModel]:
    """
    Get all intents for a session.
    
    Args:
        session_id: Session UUID
        db: Database session
        limit: Optional limit on number of results
        
    Returns:
        List of IntentLedgerModel
    """
    query = db.query(IntentLedgerModel).filter(
        IntentLedgerModel.session_id == session_id
    ).order_by(IntentLedgerModel.created_at.desc())
    
    if limit:
        query = query.limit(limit)
    
    return query.all()


def check_action_completed(
    canonical_action: str,
    user_id: str,
    db: Session,
    session_id: Optional[str] = None
) -> bool:
    """
    Check if action was completed before.
    
    Args:
        canonical_action: Action name
        user_id: User UUID (need to join through sessions)
        db: Database session
        session_id: Optional - restrict to specific session
        
    Returns:
        True if action was completed
    """
    from db.models.sessions import SessionModel
    
    query = db.query(IntentLedgerModel).join(
        SessionModel,
        IntentLedgerModel.session_id == SessionModel.id
    ).filter(
        SessionModel.user_id == user_id,
        IntentLedgerModel.canonical_action == canonical_action,
        IntentLedgerModel.status == 'completed'
    )
    
    if session_id:
        query = query.filter(IntentLedgerModel.session_id == session_id)
    
    return query.first() is not None


def count_action_executions(
    canonical_action: str,
    session_id: str,
    db: Session,
    status: str = 'completed'
) -> int:
    """
    Count how many times action was executed in session.
    
    Args:
        canonical_action: Action name
        session_id: Session UUID
        db: Database session
        status: Status to count (default: "completed")
        
    Returns:
        Count of executions
    """
    return db.query(IntentLedgerModel).filter(
        IntentLedgerModel.session_id == session_id,
        IntentLedgerModel.canonical_action == canonical_action,
        IntentLedgerModel.status == status
    ).count()


def count_action_executions_today(
    canonical_action: str,
    user_id: str,
    db: Session,
    status: str = 'completed'
) -> int:
    """
    Count how many times action was executed today for user.
    
    Args:
        canonical_action: Action name
        user_id: User UUID
        db: Database session
        status: Status to count (default: "completed")
        
    Returns:
        Count of executions today
    """
    from db.models.sessions import SessionModel
    from sqlalchemy import func, cast, Date
    
    today = datetime.utcnow().date()
    
    count = db.query(IntentLedgerModel).join(
        SessionModel,
        IntentLedgerModel.session_id == SessionModel.id
    ).filter(
        SessionModel.user_id == user_id,
        IntentLedgerModel.canonical_action == canonical_action,
        IntentLedgerModel.status == status,
        cast(IntentLedgerModel.created_at, Date) == today
    ).count()
    
    return count


def get_last_execution(
    canonical_action: str,
    session_id: str,
    db: Session,
    status: str = 'completed'
) -> Optional[IntentLedgerModel]:
    """
    Get last execution of action in session.
    
    Args:
        canonical_action: Action name
        session_id: Session UUID
        db: Database session
        status: Status to filter (default: "completed")
        
    Returns:
        IntentLedgerModel or None
    """
    return db.query(IntentLedgerModel).filter(
        IntentLedgerModel.session_id == session_id,
        IntentLedgerModel.canonical_action == canonical_action,
        IntentLedgerModel.status == status
    ).order_by(IntentLedgerModel.created_at.desc()).first()


def add_triggered_action(
    intent_id: str,
    triggered_action_id: str,
    db: Session
) -> None:
    """
    Add triggered action ID to intent's triggered_action_ids array.
    
    Used when one action triggers another (e.g., workflow steps).
    
    Args:
        intent_id: Intent UUID
        triggered_action_id: Action UUID that was triggered
        db: Database session
    """
    intent = db.query(IntentLedgerModel).filter(IntentLedgerModel.id == intent_id).first()
    
    if not intent:
        raise ValueError(f"Intent {intent_id} not found")
    
    triggered_ids = intent.triggered_action_ids or []
    
    if triggered_action_id not in triggered_ids:
        triggered_ids.append(triggered_action_id)
        intent.triggered_action_ids = triggered_ids
        intent.updated_at = datetime.utcnow()
        db.commit()