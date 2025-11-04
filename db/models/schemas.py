"""
Schemas model - Brand-level data schemas for validation.
"""
from sqlalchemy import Column, UUID, ForeignKey, String, Integer
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from db.models.base import Base


class SchemaModel(Base):
    """
    Schemas - Brand-level data structures that actions depend on.
    
    Defines required fields and API endpoints to fetch schema data.
    Used for action eligibility checking.
    """
    __tablename__ = 'schemas'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    brand_id = Column(
        UUID,
        ForeignKey('brands.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    schema_key = Column(
        String(100),
        nullable=False,
        comment="e.g., user_profile, resume"
    )
    required_fields = Column(
        ARRAY(String),
        nullable=False,
        server_default='{}',
        comment="List of required field names"
    )
    api_endpoint = Column(
        String(500),
        nullable=False,
        comment="API endpoint to fetch schema data"
    )
    cache_ttl_seconds = Column(
        Integer,
        nullable=False,
        server_default='300',
        comment="How long to cache fetched data"
    )
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    brand = relationship("BrandModel", back_populates="schemas")
    
    def __repr__(self):
        return f"<Schema(id='{self.id}', schema_key='{self.schema_key}')>"
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': str(self.id),
            'brand_id': str(self.brand_id),
            'schema_key': self.schema_key,
            'required_fields': self.required_fields,
            'api_endpoint': self.api_endpoint,
            'cache_ttl_seconds': self.cache_ttl_seconds
        }