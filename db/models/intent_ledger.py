"""
Intent Ledger model.

Logs every detected intent per session for tracking and brain processing.
"""
from sqlalchemy import Column, UUID, ForeignKey, String, Text, Integer, Numeric, CheckConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base


class IntentLedgerModel(Base):
    """
    Intent Ledger - Logs all detected intents per session.
    
    Tracks intent detection, processing status, and action triggers.
    """
    __tablename__ = 'intent_ledger'
    
    # Primary Key
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    
    # Foreign Keys
    session_id = Column(
        UUID, 
        ForeignKey('sessions.id', ondelete='CASCADE'), 
        nullable=False
    )
    intent_type_id = Column(
        String(50), 
        ForeignKey('intent_types.id'), 
        nullable=False
    )
    
    # Intent Details
    canonical_action = Column(
        String(100), 
        nullable=True,
        comment="Action name for action intents (e.g., 'create_profile')"
    )
    canonical_intent_candidates = Column(
        JSONB,
        nullable=True,
        server_default='[]',
        comment="List of 1-2 candidate action names from intent detector"
    )
    match_type = Column(
        String(20),
        nullable=True,
        comment="Action matching strategy: exact, fuzzy, synonym, not_found"
    )
    confidence = Column(
        Numeric(3, 2), 
        nullable=False,
        comment="Confidence score 0.00-1.00"
    )
    
    # Context
    turn_number = Column(Integer, nullable=False, comment="Conversation turn number")
    sequence_order = Column(
        Integer, 
        nullable=True,
        comment="Order in multi-intent messages (1, 2, 3...)"
    )
    
    # Extracted Data
    entities = Column(
        JSONB, 
        nullable=False, 
        server_default='{}',
        comment="Extracted entities and parameters"
    )
    reasoning = Column(Text, nullable=True, comment="LLM reasoning for this intent")
    
    # Processing Status
    status = Column(
        String(50), 
        nullable=False, 
        server_default='new',
        comment="Processing status: new, processing, completed, failed, blocked, cancelled"
    )
    triggered_action_ids = Column(
        JSONB, 
        nullable=False, 
        server_default='[]',
        comment="Array of action IDs triggered by this intent"
    )
    blocked_reason = Column(
        Text, 
        nullable=True,
        comment="Reason if status is 'blocked'"
    )
    
    # Response Info
    response_type = Column(
        String(50), 
        nullable=False,
        comment="'self_respond' or 'brain_required'"
    )
    response_text = Column(
        Text, 
        nullable=True,
        comment="Generated response for self-respond intents"
    )
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    session = relationship("SessionModel", back_populates="intent_ledger_entries")
    intent_type = relationship("IntentTypeModel", back_populates="intent_ledger_entries")
    
    # Table constraints and indexes
    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.00 AND confidence <= 1.00",
            name='chk_intent_ledger_confidence'
        ),
        CheckConstraint(
            "status IN ('new', 'processing', 'collecting_params', 'executing', 'completed', 'failed', 'blocked', 'cancelled')",
            name='chk_intent_ledger_status'
        ),
        CheckConstraint(
            "response_type IN ('self_respond', 'brain_required')",
            name='chk_intent_ledger_response_type'
        ),
        Index('idx_intent_ledger_session_id', 'session_id'),
        Index('idx_intent_ledger_status', 'status'),
        Index('idx_intent_ledger_turn', 'session_id', 'turn_number'),
        Index('idx_intent_ledger_type', 'intent_type_id'),
        Index('idx_intent_ledger_match_type', 'match_type'),
        Index('idx_intent_ledger_created_at', 'created_at', postgresql_using='btree', postgresql_ops={'created_at': 'DESC'}),
    )
    
    def __repr__(self):
        return (
            f"<IntentLedger(id='{self.id}', session_id='{self.session_id}', "
            f"intent_type='{self.intent_type_id}', status='{self.status}')>"
        )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'session_id': str(self.session_id),
            'intent_type_id': self.intent_type_id,
            'canonical_action': self.canonical_action,
            'canonical_intent_candidates': self.canonical_intent_candidates,
            'match_type': self.match_type,
            'confidence': float(self.confidence) if self.confidence else None,
            'turn_number': self.turn_number,
            'sequence_order': self.sequence_order,
            'entities': self.entities,
            'reasoning': self.reasoning,
            'status': self.status,
            'triggered_action_ids': self.triggered_action_ids,
            'blocked_reason': self.blocked_reason,
            'response_type': self.response_type,
            'response_text': self.response_text,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }