from sqlalchemy import Column, String, Boolean, UUID, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base

class InstanceModel(Base):
    __tablename__ = 'instances'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    brand_id = Column(UUID, ForeignKey('brands.id', ondelete='CASCADE'), nullable=False)
    name = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    recipient_number = Column(String(32), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default='true')
    accept_guest_users = Column(Boolean, nullable=False, server_default='true')  # New column
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    brand = relationship("BrandModel", back_populates="instances")
    configs = relationship("InstanceConfigModel", back_populates="instance", cascade="all, delete-orphan")
    messages = relationship("MessageModel", back_populates="instance")
    sessions = relationship("SessionModel", back_populates="instance")
    actions = relationship("ActionModel", back_populates="instance", cascade="all, delete-orphan")
    workflows = relationship("WorkflowModel", back_populates="instance", cascade="all, delete-orphan")

