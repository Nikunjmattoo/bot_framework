"""
Intent Types model.

System-defined intent types used by the Intent Detector.
"""
from sqlalchemy import Column, String, Text, Boolean, Integer, CheckConstraint
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base


class IntentTypeModel(Base):
    """
    Intent Types - System-defined intent types (8 total).
    
    Examples: greeting, goodbye, gratitude, chitchat, action, help, response, unknown
    """
    __tablename__ = 'intent_types'
    
    # Primary Key
    id = Column(String(50), primary_key=True)
    
    # Basic Info
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Classification
    category = Column(
        String(50), 
        nullable=False,
        comment="'self_respond' or 'brain_required'"
    )
    
    # Behavior Flags
    self_response_capable = Column(
        Boolean, 
        nullable=False, 
        server_default='false',
        comment="Can generate response without brain"
    )
    requires_brain = Column(
        Boolean, 
        nullable=False, 
        server_default='false',
        comment="Requires brain processing"
    )
    priority = Column(
        Integer, 
        nullable=False, 
        server_default='5',
        comment="1=highest, 10=lowest"
    )
    
    # Status
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    intent_ledger_entries = relationship(
        "IntentLedgerModel", 
        back_populates="intent_type",
        cascade="all, delete-orphan"
    )
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "category IN ('self_respond', 'brain_required')",
            name='chk_intent_types_category'
        ),
        CheckConstraint(
            "priority >= 1 AND priority <= 10",
            name='chk_intent_types_priority'
        ),
    )
    
    def __repr__(self):
        return f"<IntentType(id='{self.id}', name='{self.name}', category='{self.category}')>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'self_response_capable': self.self_response_capable,
            'requires_brain': self.requires_brain,
            'priority': self.priority,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }