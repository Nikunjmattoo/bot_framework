from sqlalchemy import Column, String, Text, UUID, ForeignKey, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.types import TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from db.models.base import Base

class TokenPresetModel(Base):
    __tablename__ = 'token_presets'
    
    id = Column(UUID, primary_key=True, server_default=func.gen_random_uuid())
    name = Column(String(100), nullable=False)
    template_key = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    weights = Column(JSONB, nullable=False)
    is_default = Column(Boolean, nullable=False, server_default='false')
    
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_token_presets_default', template_key, is_default, 
              postgresql_where=(is_default == True)),
    )