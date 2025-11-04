"""
Workflows model - Multi-step action sequences.
"""
from sqlalchemy import Column, UUID, ForeignKey, String, Text, Boolean
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base


class WorkflowModel(Base):
    """
    Workflows - Multi-step sequences of actions.
    
    Groups related actions into workflows (e.g., profile_creation_workflow).
    """
    __tablename__ = 'workflows'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    instance_id = Column(
        UUID,
        ForeignKey('instances.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    canonical_name = Column(
        String(100),
        nullable=False,
        comment="e.g., profile_creation_workflow"
    )
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instance = relationship("InstanceModel", back_populates="workflows")
    actions = relationship("ActionModel", back_populates="workflow")
    
    def __repr__(self):
        return f"<Workflow(id='{self.id}', canonical_name='{self.canonical_name}')>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'instance_id': str(self.instance_id),
            'canonical_name': self.canonical_name,
            'display_name': self.display_name,
            'description': self.description,
            'is_active': self.is_active
        }