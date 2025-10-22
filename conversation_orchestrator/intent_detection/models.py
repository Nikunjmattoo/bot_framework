"""
Intent detection models.

Defines intent types and output structures.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class IntentType(str, Enum):
    """
    10 core intent types.
    """
    # Session management
    GREETING = "greeting"
    GOODBYE = "goodbye"
    
    # System
    HELP = "help"
    FALLBACK = "fallback"
    
    # Confirmation
    AFFIRM = "affirm"
    DENY = "deny"
    
    # Conversational
    CHITCHAT = "chitchat"
    GRATITUDE = "gratitude"
    CLARIFICATION = "clarification"
    
    # Functional (requires brain)
    ACTION = "action"


class SingleIntent(BaseModel):
    """Single detected intent."""
    
    intent_type: IntentType = Field(..., description="Detected intent type")
    
    canonical_intent: Optional[str] = Field(
        None,
        description="Canonical intent name (only for action intents, e.g., 'create_profile')"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0)"
    )
    
    entities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extracted entities"
    )
    
    sequence_order: Optional[int] = Field(
        None,
        description="Order in which intent appears in message (1, 2, 3...)"
    )


class IntentOutput(BaseModel):
    """
    Intent detection output.
    
    Contains all detected intents (multi-intent support).
    """
    
    intents: List[SingleIntent] = Field(
        ...,
        min_length=1,
        description="List of all detected intents"
    )
    
    reasoning: Optional[str] = Field(
        None,
        description="Brief explanation of classification decision"
    )


# Helper functions

def requires_brain(intents: List[SingleIntent]) -> bool:
    """
    Check if any intent requires brain processing.
    
    Args:
        intents: List of detected intents
    
    Returns:
        True if brain processing needed, False otherwise
    """
    return any(intent.intent_type == IntentType.ACTION for intent in intents)


def get_action_intents(intents: List[SingleIntent]) -> List[SingleIntent]:
    """
    Filter and return only action intents.
    
    Args:
        intents: List of detected intents
    
    Returns:
        List of action intents only
    """
    return [intent for intent in intents if intent.intent_type == IntentType.ACTION]


def get_primary_intent(intents: List[SingleIntent]) -> SingleIntent:
    """
    Get primary intent from list.
    
    Priority:
    1. Action intent (if present)
    2. First intent in list
    
    Args:
        intents: List of detected intents
    
    Returns:
        Primary intent
    """
    # Check for action intent first
    for intent in intents:
        if intent.intent_type == IntentType.ACTION:
            return intent
    
    # Return first intent
    return intents[0] if intents else None