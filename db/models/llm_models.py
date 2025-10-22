# db/models/llm_models.py

from sqlalchemy import Column, String, Integer, UUID, Numeric
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
    
    # API model name and temperature
    api_model_name = Column(String(255), nullable=True)
    temperature = Column(Numeric(3, 2), nullable=True, server_default='0.7')
    
    # Pricing columns
    input_price_per_1k = Column(Numeric(10, 6), nullable=True)
    output_price_per_1k = Column(Numeric(10, 6), nullable=True)
    currency = Column(String(3), nullable=True, server_default='USD')
    pricing_updated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    templates = relationship("TemplateModel", back_populates="llm_model")  # ✅ KEEP THIS