# db/models/session_token_usage.py

from sqlalchemy import Column, UUID, ForeignKey, Integer, String, Numeric
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base

class SessionTokenUsageModel(Base):
    __tablename__ = 'session_token_usage'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(UUID, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    template_key = Column(String(100), nullable=False)
    function_name = Column(String(100), nullable=False)
    
    # Token counts
    planned_tokens = Column(Integer, nullable=False)
    sent_tokens = Column(Integer, nullable=False)
    received_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    
    # ✅ NEW: Cost tracking
    llm_model_id = Column(UUID, ForeignKey('llm_models.id', ondelete='SET NULL'), nullable=True)
    input_price_per_1k = Column(Numeric(10, 6), nullable=True)
    output_price_per_1k = Column(Numeric(10, 6), nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)
    currency = Column(String(3), nullable=True, server_default='USD')
    
    # Timestamps
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    session = relationship("SessionModel", back_populates="token_usage")
    llm_model = relationship("LLMModel")  # ✅ NEW