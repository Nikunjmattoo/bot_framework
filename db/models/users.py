from sqlalchemy import Column, String, UUID, ForeignKey, Numeric, Boolean
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base

class UserModel(Base):
    __tablename__ = 'users'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    acquisition_channel = Column(String, nullable=True)
    referred_by_user_id = Column(UUID, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user_tier = Column(String, nullable=True)
    trust_score = Column(Numeric, nullable=True)
    is_internal_tester = Column(Boolean, nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships - CRITICAL: Add passive_deletes=True to let DB handle CASCADE
    identifiers = relationship("UserIdentifierModel", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    sessions = relationship("SessionModel", back_populates="user", cascade="all, delete-orphan", passive_deletes=True)
    messages = relationship("MessageModel", back_populates="user")