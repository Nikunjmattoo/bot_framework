from sqlalchemy import Column, UUID, ForeignKey, Integer, String
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
    planned_tokens = Column(Integer, nullable=False)
    sent_tokens = Column(Integer, nullable=False)
    received_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    session = relationship("SessionModel", back_populates="token_usage")