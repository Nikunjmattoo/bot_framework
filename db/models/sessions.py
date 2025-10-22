from sqlalchemy import Column, UUID, ForeignKey, Boolean, String, Text, Integer
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
    last_assistant_message_at = Column(TIMESTAMP(timezone=True), nullable=True)
    current_turn = Column(Integer, nullable=False, server_default='0')
    rollup_cursor_at = Column(TIMESTAMP(timezone=True), nullable=True)
    token_plan_json = Column(JSONB, nullable=True)
    
    # Orchestrator fields
    session_summary = Column(Text, nullable=True)
    active_task_name = Column(String(255), nullable=True)
    active_task_status = Column(String(50), nullable=True)
    next_narrative = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships - CRITICAL: Add passive_deletes=True to let DB handle CASCADE
    user = relationship("UserModel", back_populates="sessions")
    instance = relationship("InstanceModel", back_populates="sessions")
    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan", passive_deletes=True)
    token_usage = relationship("SessionTokenUsageModel", back_populates="session", cascade="all, delete-orphan", passive_deletes=True)