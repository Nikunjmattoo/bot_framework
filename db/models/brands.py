from sqlalchemy import Column, String, UUID
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class BrandModel(Base):
    __tablename__ = 'brands'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String, nullable=False, unique=True)
    phone_number = Column(String, nullable=True)
    website = Column(String, nullable=True)
    extra_config = Column(JSONB, nullable=True, server_default='{}')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    instances = relationship("InstanceModel", back_populates="brand", cascade="all, delete-orphan")
    user_identifiers = relationship("UserIdentifierModel", back_populates="brand")
    schemas = relationship("SchemaModel", back_populates="brand", cascade="all, delete-orphan")
