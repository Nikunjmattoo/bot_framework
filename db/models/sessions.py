from sqlalchemy import Column, UUID, ForeignKey, Boolean, String
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class SessionModel(Base):
    __tablename__ = 'sessions'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    instance_id = Column(UUID, ForeignKey('instances.id', ondelete='SET NULL'), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    active = Column(Boolean, nullable=False, server_default='true')
    source = Column(String, nullable=True)
    last_message_at = Column(TIMESTAMP(timezone=True), nullable=True)
    rollup_cursor_at = Column(TIMESTAMP(timezone=True), nullable=True)
    token_plan_json = Column(JSONB, nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("UserModel", back_populates="sessions")
    instance = relationship("InstanceModel", back_populates="sessions")
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan")
    token_usage = relationship("SessionTokenUsageModel", back_populates="session", cascade="all, delete-orphan")
