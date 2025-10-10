from sqlalchemy import Column, String, Integer, UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class LLMModel(Base):
    __tablename__ = 'llm_models'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=True)
    max_tokens = Column(Integer, nullable=False)
    details = Column(JSONB, nullable=True, server_default='{}')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    template_sets = relationship("TemplateSetModel", back_populates="llm_model")