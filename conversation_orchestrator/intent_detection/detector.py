"""
Intent detection detector.

Main logic - enriches adapter with DB fetches, fills template, calls LLM, triggers cold paths.
"""

import logging
import asyncio
from typing import Dict, Any

from conversation_orchestrator.schemas import EnrichedContext, TemplateVariables
from conversation_orchestrator.services.db_service import (
    fetch_session_summary,
    fetch_previous_messages,
    fetch_active_task,
    fetch_next_narrative,
    fetch_template_string
)
from conversation_orchestrator.services.template_service import (
    fill_template,
    format_messages,
    format_active_task
)
from conversation_orchestrator.services.llm_service import call_llm_async
from conversation_orchestrator.cold_path.trigger_manager import trigger_cold_paths
from conversation_orchestrator.intent_detection.parser import parse_intent_response
from conversation_orchestrator.exceptions import IntentDetectionError
from conversation_orchestrator.utils.logging import get_logger

logger = get_logger(__name__)


def detect_intents(adapter_payload: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    """
    Detect intents from user message.
    
    Flow:
    1. Extract data from adapter
    2. Fetch enrichment data from DB
    3. Fill intent_detection template
    4. Fire LLM call (async)
    5. Trigger cold paths (parallel with LLM)
    6. Wait for LLM response
    7. Parse and return intents
    
    Args:
        adapter_payload: Adapter payload from message_handler
        trace_id: Trace ID for logging
    
    Returns:
        Dict with:
            - intents: List of detected intents
            - token_usage: Token usage stats
            - reasoning: Optional reasoning
    
    Raises:
        IntentDetectionError: If detection fails
    """
    logger.info(
        "intent_detection:started",
        extra={"trace_id": trace_id}
    )
    
    try:
        # Step 1: Extract from adapter
        user_message = adapter_payload["message"]["content"]
        user_id = adapter_payload["message"]["sender_user_id"]
        session_id = adapter_payload["session_id"]
        
        # Derive user_type from policy.auth_state
        policy = adapter_payload.get("policy", {})
        auth_state = policy.get("auth_state", "guest")
        user_type = "verified" if auth_state == "channel_verified" else "guest"
        
        # Get template key from functions mapping
        functions = adapter_payload["template"]["json"]
        intent_function = functions.get("intent", {})
        template_key = intent_function.get("template")

        if not template_key:
            raise IntentDetectionError(
                message="Intent template key not found in adapter",
                error_code="MISSING_TEMPLATE_KEY"
            )

        # Fetch template string from DB
        intent_template = fetch_template_string(template_key)

        # Extract budget and model from token_plan
        template_data = adapter_payload["token_plan"]["templates"][template_key]
        token_budget = template_data["total_budget"]
        model_id = template_data["llm_model_id"]
        api_model_name = template_data["api_model_name"]
        provider = template_data.get("provider", "groq")
        temperature = template_data.get("temperature", 0.7)
        
        logger.info(
            "intent_detection:extracted_from_adapter",
            extra={
                "trace_id": trace_id,
                "user_type": user_type,
                "model": api_model_name,
                "token_budget": token_budget
            }
        )
        
        # Step 2: Fetch enrichment data from DB
        enriched = _fetch_enrichment_data(session_id, trace_id)
        
        # Step 3: Build template variables
        template_vars = _build_template_variables(
            user_message=user_message,
            user_id=user_id,
            session_id=session_id,
            user_type=user_type,
            enriched=enriched
        )
        
        # Step 4: Fill template
        filled_prompt = fill_template(intent_template, template_vars)
        
        logger.info(
            "intent_detection:template_filled",
            extra={
                "trace_id": trace_id,
                "prompt_length": len(filled_prompt)
            }
        )
        
        # Step 5: Fire LLM call (async)
        llm_future = call_llm_async(
            prompt=filled_prompt,
            model=api_model_name,
            runtime=provider,
            max_tokens=token_budget,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        logger.info(
            "intent_detection:llm_call_fired",
            extra={"trace_id": trace_id}
        )
        
        # Step 6: Trigger cold paths (parallel with LLM)
        _trigger_cold_paths_async(
            session_id=session_id,
            user_message=user_message,
            enriched=enriched,
            trace_id=trace_id
        )
        
        # Step 7: Wait for LLM response
        loop = asyncio.get_event_loop()
        llm_result = loop.run_until_complete(llm_future)
        
        logger.info(
            "intent_detection:llm_response_received",
            extra={
                "trace_id": trace_id,
                "tokens_used": llm_result["token_usage"]["total"]
            }
        )
        
        # Step 8: Parse response
        intent_output = parse_intent_response(llm_result["content"])
        
        logger.info(
            "intent_detection:completed",
            extra={
                "trace_id": trace_id,
                "intents_count": len(intent_output.intents),
                "intents": [i.intent_type.value for i in intent_output.intents]
            }
        )
        
        # Return result
        return {
            "intents": [intent.dict() for intent in intent_output.intents],
            "token_usage": llm_result["token_usage"],
            "reasoning": intent_output.reasoning
        }
    
    except Exception as e:
        logger.error(
            "intent_detection:error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise IntentDetectionError(
            message=f"Intent detection failed: {str(e)}",
            error_code="INTENT_DETECTION_FAILED"
        ) from e


def _fetch_enrichment_data(session_id: str, trace_id: str) -> EnrichedContext:
    """
    Fetch enrichment data from database.
    
    Args:
        session_id: Session identifier
        trace_id: Trace ID for logging
    
    Returns:
        EnrichedContext object
    """
    logger.info(
        "intent_detection:fetching_enrichment",
        extra={"trace_id": trace_id, "session_id": session_id}
    )
    
    # Fetch all data
    session_summary = fetch_session_summary(session_id)
    previous_messages = fetch_previous_messages(session_id, limit=4)
    active_task = fetch_active_task(session_id)
    next_narrative = fetch_next_narrative(session_id)
    
    enriched = EnrichedContext(
        session_summary=session_summary,
        previous_messages=previous_messages,
        active_task=active_task,
        next_narrative=next_narrative
    )
    
    logger.info(
        "intent_detection:enrichment_fetched",
        extra={
            "trace_id": trace_id,
            "has_summary": session_summary is not None,
            "messages_count": len(previous_messages),
            "has_task": active_task is not None,
            "has_narrative": next_narrative is not None
        }
    )
    
    return enriched


def _build_template_variables(
    user_message: str,
    user_id: str,
    session_id: str,
    user_type: str,
    enriched: EnrichedContext
) -> Dict[str, Any]:
    """
    Build template variables for filling.
    
    Args:
        user_message: User's message
        user_id: User identifier
        session_id: Session identifier
        user_type: User type ('verified' or 'guest')
        enriched: Enriched context from DB
    
    Returns:
        Dict of template variables
    """
    return {
        "user_message": user_message,
        "user_id": user_id,
        "session_id": session_id,
        "user_type": user_type,
        "session_summary": enriched.session_summary or "[No session summary]",
        "previous_messages": format_messages(enriched.previous_messages),
        "active_task": format_active_task(enriched.active_task),
        "next_narrative": enriched.next_narrative or "[No narrative guidance]"
    }


def _trigger_cold_paths_async(
    session_id: str,
    user_message: str,
    enriched: EnrichedContext,
    trace_id: str
) -> None:
    """
    Trigger cold paths asynchronously.
    
    Args:
        session_id: Session identifier
        user_message: User's message
        enriched: Enriched context
        trace_id: Trace ID for logging
    """
    # Build conversation history for cold paths
    conversation_history = []
    for msg in enriched.previous_messages:
        conversation_history.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # Add current user message
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    
    # Trigger cold paths
    cold_paths_to_trigger = [
        "session_summary_generator",
        # "judge_topic",  # Uncomment when ready
        # "judge_tone",
        # "judge_state_of_mind"
    ]
    
    trigger_cold_paths(
        session_id=session_id,
        user_message=user_message,
        conversation_history=conversation_history,
        cold_paths=cold_paths_to_trigger,
        trace_id=trace_id
    )