"""
Session summary generator stub.

STUB - Does nothing. Will be replaced by memory module later.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def generate_session_summary_stub(
    conversation_history: List[Dict[str, str]],
    session_id: str
) -> None:
    """
    Generate session summary (STUB).
    
    This is a placeholder. Real implementation will:
    1. Take full conversation history
    2. Compress to 100-150 tokens using LLM
    3. Save to database
    
    Args:
        conversation_history: Full conversation history
        session_id: Session identifier
    """
    logger.info(
        "session_summary_stub:called",
        extra={
            "session_id": session_id,
            "conversation_length": len(conversation_history)
        }
    )
    
    # Stub - does nothing
    # TODO: Replace with real implementation from memory module
    pass