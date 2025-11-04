"""
Instance Configs model - Updated with config JSONB for popular_actions.
"""
from sqlalchemy import Column, UUID, ForeignKey, Float, Integer, Boolean, String, Index, text
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
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
    
    # ========================================
    # NEW: Config JSONB field
    # ========================================
    # Stores:
    # - popular_actions: array of 3-7 most common actions
    # - other brain/action configuration
    config = Column(
        JSONB, 
        nullable=False, 
        server_default='{}',
        comment="Brain configuration including popular_actions"
    )
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instance = relationship("InstanceModel", back_populates="configs")
    template_set = relationship("TemplateSetModel", back_populates="instance_configs")
    
    # Table args - Partial unique index: only one active config per instance
    __table_args__ = (
        Index(
            'instance_configs_one_active_per_instance',
            'instance_id',
            unique=True,
            postgresql_where=text('is_active = true')
        ),
    )
    
    def __repr__(self):
        return f"<InstanceConfig(id='{self.id}', instance_id='{self.instance_id}', is_active={self.is_active})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': str(self.id),
            'instance_id': str(self.instance_id),
            'template_set_id': self.template_set_id,
            'temperature': float(self.temperature) if self.temperature else None,
            'timeout_ms': self.timeout_ms,
            'session_timeout_seconds': self.session_timeout_seconds,
            'use_rag': self.use_rag,
            'is_active': self.is_active,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    # Helper methods for config management
    def get_popular_actions(self):
        """Get popular_actions from config."""
        if not self.config:
            return []
        return self.config.get('popular_actions', [])
    
    def set_popular_actions(self, actions: list):
        """Set popular_actions in config."""
        if not self.config:
            self.config = {}
        self.config['popular_actions'] = actions
    
    def get_config_value(self, key: str, default=None):
        """Get a value from the config JSONB field."""
        if not self.config:
            return default
        return self.config.get(key, default)
    
    def set_config_value(self, key: str, value):
        """Set a value in the config JSONB field."""
        if not self.config:
            self.config = {}
        self.config[key] = value
    
    def update_config(self, updates: dict):
        """Update multiple values in the config JSONB field."""
        if not self.config:
            self.config = {}
        self.config.update(updates)