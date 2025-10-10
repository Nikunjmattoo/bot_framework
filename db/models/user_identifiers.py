from sqlalchemy import Column, String, UUID, ForeignKey, Boolean, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.orm import relationship

from db.models.base import Base

class UserIdentifierModel(Base):
    __tablename__ = 'user_identifiers'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    user_id = Column(UUID, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    brand_id = Column(UUID, ForeignKey('brands.id'), nullable=True)
    identifier_type = Column(String(50), nullable=False)
    identifier_value = Column(String(500), nullable=False)
    channel = Column(String(50), nullable=False)
    verified = Column(Boolean, nullable=False, server_default='false')
    verified_via = Column(Text, nullable=True)
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship("UserModel", back_populates="identifiers")
    # Update this relationship with back_populates to resolve the warning
    brand = relationship("BrandModel", back_populates="user_identifiers")
    
    # Updated unique constraint using Index
    __table_args__ = (
        Index('user_identifiers_brand_scoped_key', 
              identifier_type, identifier_value, channel, brand_id,
              unique=True,
              postgresql_where=brand_id.isnot(None)),
    )