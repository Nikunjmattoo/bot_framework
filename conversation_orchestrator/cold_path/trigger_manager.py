"""
Cold path trigger manager.

Orchestrates all cold path tasks (session_summary, judges) fired in parallel.
"""

import logging
import asyncio
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from db.db import session_scope

from conversation_orchestrator.cold_path.session_summary_generator import generate_session_summary

logger = logging.getLogger(__name__)


def trigger_cold_paths(
    session_id: str,
    user_message: str,
    conversation_history: List[Dict[str, str]],
    cold_paths: List[str],
    trace_id: str = None
) -> None:
    """
    Trigger cold path tasks in parallel.
    
    Fire and forget - does not wait for completion.
    
    Args:
        session_id: Session identifier
        user_message: User's message
        conversation_history: Full conversation history
        cold_paths: List of cold path names to trigger
        trace_id: Trace ID for logging
    """
    logger.info(
        "cold_path:triggering",
        extra={
            "trace_id": trace_id,
            "session_id": session_id,
            "cold_paths": cold_paths
        }
    )
    
    try:
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Schedule cold path tasks
        tasks = []
        
        if "session_summary_generator" in cold_paths:
            tasks.append(
                _run_session_summary_with_db(session_id, conversation_history, trace_id)
            )
        
        if "judge_topic" in cold_paths:
            tasks.append(
                _run_judge_stub("topic", user_message, session_id, trace_id)
            )
        
        if "judge_tone" in cold_paths:
            tasks.append(
                _run_judge_stub("tone", user_message, session_id, trace_id)
            )
        
        if "judge_state_of_mind" in cold_paths:
            tasks.append(
                _run_judge_stub("state_of_mind", user_message, session_id, trace_id)
            )
        
        # BUG FIX #2: Actually execute the tasks using create_task
        if tasks:
            asyncio.create_task(
                asyncio.gather(*tasks, return_exceptions=True)
            )
        
        logger.info(
            "cold_path:triggered",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "tasks_count": len(tasks)
            }
        )
    
    except Exception as e:
        logger.error(
            "cold_path:trigger_error",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "error": str(e)
            }
        )
        # Don't raise - cold paths should not break main flow


async def _run_session_summary_with_db(
    session_id: str,
    conversation_history: List[Dict[str, str]],
    trace_id: str = None
) -> None:
    """Wrapper to provide db session for session summary."""
    from db.db import session_scope
    
    with session_scope() as db:
        await generate_session_summary(
            db=db,
            session_id=session_id,
            conversation_history=conversation_history,
            trace_id=trace_id
        )

async def _run_judge_stub(
    judge_type: str,
    user_message: str,
    session_id: str,
    trace_id: str = None
) -> None:
    """
    Run judge analysis (stub).
    
    Args:
        judge_type: Type of judge ('topic', 'tone', 'state_of_mind')
        user_message: User's message
        session_id: Session identifier
        trace_id: Trace ID for logging
    """
    try:
        logger.info(
            f"cold_path:judge_{judge_type}_started",
            extra={"trace_id": trace_id, "session_id": session_id}
        )
        
        # Stub - does nothing for now
        await asyncio.sleep(0.01)
        
        logger.info(
            f"cold_path:judge_{judge_type}_completed",
            extra={"trace_id": trace_id, "session_id": session_id}
        )
    
    except Exception as e:
        logger.error(
            f"cold_path:judge_{judge_type}_error",
            extra={
                "trace_id": trace_id,
                "session_id": session_id,
                "error": str(e)
            }
        )