from sqlalchemy import Column, String, Text, UUID, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class TemplateSetModel(Base):
    __tablename__ = 'template_sets'
    
    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    functions = Column(JSONB, nullable=False, server_default='{}')  # Changed from template_names
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instance_configs = relationship("InstanceConfigModel", back_populates="template_set")