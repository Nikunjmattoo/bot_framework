"""
Session summary generator for cold path.

Generates and saves session summaries after each turn.
Summary includes conversation messages and (future) backend actions.
"""

import logging
from typing import List, Dict, Any, Optional

from conversation_orchestrator.services.summarizer_service import summarize_conversation
from conversation_orchestrator.services.db_service import save_session_summary

logger = logging.getLogger(__name__)


async def generate_session_summary(
    session_id: str,
    conversation_history: List[Dict[str, str]],
    trace_id: Optional[str] = None
) -> None:
    """
    Generate and save session summary.
    
    This runs in the cold path (async, non-blocking) after each turn.
    Creates a compressed summary of the conversation that includes:
    - Key facts about the user
    - User's intent and goals
    - Conversation progress
    - Backend actions (future: when brain is built)
    
    The summary is saved to the database and will be read by the
    intent detector in the next turn to provide context.
    
    Args:
        session_id: Session identifier
        conversation_history: Full conversation history
            Format: [{"role": "user/assistant", "content": "..."}]
        trace_id: Trace ID for logging
    
    Returns:
        None (saves summary to database)
    
    Flow:
        1. Fetch backend actions (empty for now, brain will populate)
        2. Call summarizer with messages + actions
        3. Save summary to database
        4. Next turn: Intent detector reads summary as context
    
    Example:
        # Turn 5: Cold path triggers after response sent
        await generate_session_summary(
            session_id="abc-123",
            conversation_history=[
                {"role": "user", "content": "I want to create a profile"},
                {"role": "assistant", "content": "What's your name?"},
                {"role": "user", "content": "Nikunj"}
            ]
        )
        # Saves: "User wants to create profile. Provided name (Nikunj)."
        
        # Turn 6: Intent detector reads summary
        # Has context from previous turns without full history
    """
    try:
        logger.info(
            "cold_path:session_summary_started",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "message_count": len(conversation_history)
            }
        )
        
        # TODO: When brain is built, fetch actions from brain's ledger
        # from brain.ledger import get_completed_actions
        # actions = get_completed_actions(session_id)
        # For now, no actions (brain doesn't exist yet)
        actions = None
        
        # Generate summary
        summary = await summarize_conversation(
            messages=conversation_history,
            goal="key facts about user, their intent, conversation progress, and any backend actions",
            max_tokens=150,
            actions=actions,  # Will be populated by brain later
            max_input_tokens=2000,
            trace_id=trace_id
        )
        
        # Handle empty summary (LLM failure)
        if not summary:
            logger.warning(
                "cold_path:session_summary_empty",
                extra={
                    "trace_id": trace_id,
                    "session_id": session_id
                }
            )
            # Keep old summary if exists, don't overwrite with empty
            return
        
        # Save to database
        save_session_summary(session_id, summary)
        
        logger.info(
            "cold_path:session_summary_completed",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "summary_length": len(summary)
            }
        )
    
    except Exception as e:
        logger.error(
            "cold_path:session_summary_error",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        # Don't raise - cold path failures should not break hot path