from sqlalchemy import Column, UUID, ForeignKey, Integer
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class TokenPlanModel(Base):
    __tablename__ = 'token_plans'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(UUID, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    total_budget = Column(Integer, nullable=False)
    template_budgets = Column(JSONB, nullable=False)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    session = relationship("SessionModel", back_populates="token_plans")