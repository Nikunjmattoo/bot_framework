from sqlalchemy import Column, UUID, ForeignKey, String, Text, Boolean, Integer, Index
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class MessageModel(Base):
    __tablename__ = 'messages'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    session_id = Column(UUID, ForeignKey('sessions.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    instance_id = Column(UUID, ForeignKey('instances.id'), nullable=True)
    role = Column(String, nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True)
    topic_paths = Column(JSONB, nullable=False, server_default='[]')
    processed = Column(Boolean, nullable=True, index=True)
    request_id = Column(Text, nullable=True, index=True)
    turn_number = Column(Integer, nullable=True)
    trace_id = Column(Text, nullable=True)
    metadata_json = Column(JSONB, nullable=False, server_default='{}')
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Composite index for faster idempotency lookups
    __table_args__ = (
        Index('ix_messages_request_id_processed', 'request_id', 'processed'),
    )
    
    # Relationships
    session = relationship("SessionModel", back_populates="messages")
    user = relationship("UserModel", back_populates="messages")
    instance = relationship("InstanceModel", back_populates="messages")