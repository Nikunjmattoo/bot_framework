"""
Shared Pydantic models used across orchestrator steps.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class Message(BaseModel):
    """Single message in conversation history."""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")


class ActiveTask(BaseModel):
    """Active task information."""
    name: Optional[str] = Field(None, description="Task name (e.g., 'create_profile')")
    status: Optional[str] = Field(None, description="Task status: 'in_progress', 'completed', 'cancelled'")
    started_at: Optional[datetime] = Field(None, description="When task started")


class EnrichedContext(BaseModel):
    """
    Enriched context from DB fetches.
    
    Contains all data fetched from database to enrich adapter payload.
    """
    session_summary: Optional[str] = Field(
        None,
        description="Compressed conversation summary (100-150 tokens)"
    )
    previous_messages: List[Message] = Field(
        default_factory=list,
        description="Last 4 messages (2 turns)"
    )
    active_task: Optional[ActiveTask] = Field(
        None,
        description="Current active task"
    )
    next_narrative: Optional[str] = Field(
        None,
        description="Next narrative guidance from previous turn"
    )


class TemplateVariables(BaseModel):
    """Variables to fill in template."""
    user_message: str
    user_id: str
    session_id: str
    user_type: str
    session_summary: Optional[str] = None
    previous_messages: List[Message] = Field(default_factory=list)
    active_task: Optional[ActiveTask] = None
    next_narrative: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True