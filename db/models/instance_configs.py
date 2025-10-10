from sqlalchemy import Column, UUID, ForeignKey, Float, Integer, Boolean, String, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base

class InstanceConfigModel(Base):
    __tablename__ = 'instance_configs'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    instance_id = Column(UUID, ForeignKey('instances.id', ondelete='CASCADE'), nullable=False)
    template_set_id = Column(String(100), ForeignKey('template_sets.id'), nullable=False)
    temperature = Column(Float, nullable=False, server_default='0.7')
    timeout_ms = Column(Integer, nullable=False, server_default='15000')
    session_timeout_seconds = Column(Integer, nullable=False, server_default='300')
    use_rag = Column(Boolean, nullable=False, server_default='false')
    is_active = Column(Boolean, nullable=False, server_default='true')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instance = relationship("InstanceModel", back_populates="configs")
    template_set = relationship("TemplateSetModel", back_populates="instance_configs")
    
    # Table args
    __table_args__ = (
        UniqueConstraint('instance_id', 'is_active', name='instance_configs_instance_id_is_active_key'),
    )