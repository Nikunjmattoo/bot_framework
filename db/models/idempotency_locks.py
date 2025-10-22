# db/models/idempotency_locks.py
import uuid
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from db.models.base import Base

class IdempotencyLockModel(Base):
    __tablename__ = 'idempotency_locks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String, unique=True, nullable=False, index=True)  # ← CHANGED from idempotency_key
    created_at = Column(DateTime, nullable=False)