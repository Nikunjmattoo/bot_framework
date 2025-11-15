"""
Intent detection models.

Defines intent types and output structures.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# Intent type enum must be defined first
class IntentType(str, Enum):
    """
    8 core intent types (matches intents.md).
    """
    # Self-Respond Intents (4)
    GREETING = "greeting"
    GOODBYE = "goodbye"
    GRATITUDE = "gratitude"
    CHITCHAT = "chitchat"
    
    # Brain-Required Intents (4)
    ACTION = "action"
    HELP = "help"
    RESPONSE = "response"
    UNKNOWN = "unknown"


# Constants for intent classification (using IntentType enum)
SELF_RESPOND_INTENTS = {
    IntentType.GREETING,
    IntentType.GOODBYE,
    IntentType.GRATITUDE,
    IntentType.CHITCHAT
}

BRAIN_REQUIRED_INTENTS = {
    IntentType.ACTION,
    IntentType.HELP,
    IntentType.RESPONSE,
    IntentType.UNKNOWN
}

MIN_CONFIDENCE = 0.7


class SingleIntent(BaseModel):
    """Single detected intent."""
    
    intent_type: IntentType = Field(..., description="Detected intent type")
    
    canonical_intent: Optional[str] = Field(
        None,
        description="Canonical intent name (only for action intents, e.g., 'create_profile')"
    )
    
    canonical_intent_candidates: Optional[List[str]] = Field(
        None,
        min_length=1,
        max_length=2,
        description="1-2 canonical intent name candidates for fuzzy matching (action intents only). "
                    "Ordered by likelihood: [primary, alternative]"
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
    
    reasoning: Optional[str] = Field(
        None,
        description="Brief explanation for this intent"
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
    
    response_text: Optional[str] = Field(
        None,
        description="Generated response text (only for self-respond intents)"
    )
    
    self_response: bool = Field(
        False,
        description="Flag indicating if this is a self-response (no brain needed)"
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
    if not intents:
        return False
    
    return any(intent.intent_type in BRAIN_REQUIRED_INTENTS for intent in intents)


def get_action_intents(intents: List[SingleIntent]) -> List[SingleIntent]:
    """
    Filter and return only action intents.
    
    Args:
        intents: List of detected intents
    
    Returns:
        List of action intents only
    """
    return [intent for intent in intents if intent.intent_type == IntentType.ACTION]


def get_primary_intent(intents: List[SingleIntent]) -> Optional[SingleIntent]:
    """
    Get primary intent from list.
    
    Priority:
    1. Action intent (if present)
    2. First intent in list
    
    Args:
        intents: List of detected intents
    
    Returns:
        Primary intent or None if list is empty
    """
    if not intents:
        return None
    
    # Check for action intent first
    for intent in intents:
        if intent.intent_type == IntentType.ACTION:
            return intent
    
    # Return first intent
    return intents[0]


def is_self_respond_only(intents: List[SingleIntent]) -> bool:
    """
    Check if all intents are self-respond types.
    
    Self-respond intents: greeting, goodbye, gratitude, chitchat
    
    Args:
        intents: List of detected intents
    
    Returns:
        True if all intents are self-respond, False otherwise
    """
    if not intents:
        return False
    
    return all(intent.intent_type in SELF_RESPOND_INTENTS for intent in intents)