from sqlalchemy import Column, String, Text, UUID, ForeignKey, Boolean, Float
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class PromptTemplateModel(Base):
    __tablename__ = 'prompt_templates'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(100), nullable=False)
    template_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # JSON content (instead of sections)
    json = Column(JSONB, nullable=False)
    
    # Additional columns from the database
    budget_percentage = Column(Float, nullable=True)
    is_default = Column(Boolean, nullable=False, server_default='false')
    is_latest = Column(Boolean, nullable=False, server_default='true')
    purpose = Column(String(50), nullable=True)
    tags = Column(JSONB, nullable=True)
    created_by = Column(UUID, nullable=True)
    updated_by = Column(UUID, nullable=True)
    
    # Existing columns
    instance_id = Column(UUID, ForeignKey('instances.id', ondelete='CASCADE'), nullable=False)
    type = Column(String(50), nullable=False, server_default='response')
    version = Column(String(20), nullable=False, server_default='1.0')
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instance = relationship("InstanceModel", back_populates="prompt_templates")