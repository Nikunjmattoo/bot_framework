from sqlalchemy import Column, String, Text, UUID, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class TemplateModel(Base):
    __tablename__ = 'templates'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    template_key = Column(String(100), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    sections = Column(JSONB, nullable=False, server_default='[]')
    llm_model_id = Column(UUID, ForeignKey('llm_models.id'), nullable=True)
    
    version = Column(String(20), nullable=False, server_default='1.0')
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    llm_model = relationship("LLMModel", back_populates="templates")