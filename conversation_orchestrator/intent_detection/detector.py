"""
Intent detection detector.

Main logic - enriches adapter with DB fetches, fills template, calls LLM, triggers cold paths.
"""

import logging
import asyncio
import time
from typing import Dict, Any

from conversation_orchestrator.schemas import EnrichedContext, TemplateVariables
from conversation_orchestrator.services.db_service import (
    fetch_session_summary,
    fetch_previous_messages,
    fetch_active_task,
    fetch_next_narrative,
    fetch_template_string,
    fetch_brain_state,
    fetch_popular_actions
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


async def detect_intents(
    adapter_payload: Dict[str, Any],
    trace_id: str
) -> Dict[str, Any]:
    """
    Detect user intents from message.
    
    Steps:
    1. Fetch template from DB
    2. Fetch enrichment data (session summary, etc.)
    3. Fill template with variables
    4. Call LLM with correct model config
    5. Parse response
    6. Trigger cold paths
    
    Returns:
        Dict with intents, self_response, response_text, token_usage
    """
    start_time = time.time()
    
    try:
        # Step 1: Get template key from adapter
        template_key = adapter_payload.get("template", {}).get("json", {}).get("intent", {}).get("template")
        
        if not template_key:
            raise IntentDetectionError(
                message="Missing intent template key in adapter payload",
                error_code="MISSING_TEMPLATE_KEY"
            )
        
        # Step 2: Get LLM config from token_plan
        llm_config = adapter_payload.get("token_plan", {}).get("templates", {}).get(template_key, {})
        
        if not llm_config:
            raise IntentDetectionError(
                message=f"Missing LLM config for template {template_key} in token_plan",
                error_code="MISSING_LLM_CONFIG"
            )
        
        provider = llm_config.get("provider")
        api_model_name = llm_config.get("api_model_name")
        temperature = llm_config.get("temperature", 0.7)
        max_tokens = llm_config.get("max_tokens", 2000)
        
        logger.info(
            "intent_detection:llm_config",
            extra={
                "trace_id": trace_id,
                "provider": provider,
                "model": api_model_name,
                "temperature": temperature
            }
        )
        
        # Step 3: Fetch template from DB
        template_string = await fetch_template_string(template_key)
        
        # Step 4: Fetch enrichment data
        session_id = adapter_payload.get("session_id")
        instance_id = adapter_payload.get("routing", {}).get("instance_id")
        enriched = _fetch_enrichment_data(session_id, instance_id, trace_id)
        
        # Step 5: Build template variables
        user_message = adapter_payload.get("message", {}).get("content", "")
        user_id = adapter_payload.get("message", {}).get("sender_user_id", "")
        user_type = "verified" if adapter_payload.get("policy", {}).get("auth_state") == "channel_verified" else "guest"
        
        variables = _build_template_variables(
            user_message=user_message,
            user_id=user_id,
            session_id=session_id,
            user_type=user_type,
            enriched=enriched
        )
        
        # Step 6: Fill template using template service (BUG FIX #4)
        filled_template = fill_template(template_string, variables)
        
        logger.info(
            "intent_detection:template_filled",
            extra={
                "trace_id": trace_id,
                "template_key": template_key,
                "prompt_length": len(filled_template)
            }
        )
        
        # Step 7: Call LLM with correct config (BUG FIX #1: provider → runtime)
        llm_response = await call_llm_async(
            prompt=filled_template,
            runtime=provider,  # FIX: Changed from 'provider' to 'runtime'
            model=api_model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_id=trace_id,
            response_format={"type": "json_object"}  # Force JSON output (no markdown)
        )
        
        logger.info(
            "intent_detection:llm_called",
            extra={
                "trace_id": trace_id,
                "tokens_used": llm_response.get("token_usage", {}).get("total", 0)
            }
        )
        
        # Step 8: Parse LLM response
        intent_output = parse_intent_response(llm_response["content"])
        
        # Step 9: Build result (BUG FIX #5: Log reasoning)
        result = {
            "intents": [intent.model_dump() for intent in intent_output.intents],
            "self_response": intent_output.self_response,
            "response_text": intent_output.response_text,
            "reasoning": intent_output.reasoning,
            "token_usage": llm_response.get("token_usage", {})
        }
        
        # Log reasoning for analysis (BUG FIX #5)
        logger.info(
            "intent_detection:reasoning",
            extra={
                "trace_id": trace_id,
                "reasoning": intent_output.reasoning,
                "intents": [i.intent_type.value for i in intent_output.intents]
            }
        )
        
        # Step 10: Trigger cold paths (async, non-blocking)
        _trigger_cold_paths_async(
            session_id=session_id,
            user_message=user_message,
            enriched=enriched,
            trace_id=trace_id
        )
        
        logger.info(
            "intent_detection:completed",
            extra={
                "trace_id": trace_id,
                "intents_count": len(result["intents"]),
                "self_response": result["self_response"],
                "latency_ms": (time.time() - start_time) * 1000
            }
        )
        
        return result
    
    except IntentDetectionError:
        raise
    
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


def _fetch_enrichment_data(session_id: str, instance_id: str, trace_id: str) -> EnrichedContext:
    """
    Fetch enrichment data from database.
    
    Args:
        session_id: Session identifier
        instance_id: Instance identifier  # ← ADD THIS PARAMETER
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
    active_task = fetch_active_task(session_id)  # ← DEPRECATED: Will be replaced by brain state
    next_narrative = fetch_next_narrative(session_id)
    
    # NEW: Fetch brain state (6 wires)
    brain_state = fetch_brain_state(session_id)
    
    # NEW: Fetch popular actions (wire 7)
    popular_actions = fetch_popular_actions(instance_id)
    
    enriched = EnrichedContext(
        session_summary=session_summary,
        previous_messages=previous_messages,
        active_task=active_task,
        next_narrative=next_narrative
    )
    
    # Store brain state and popular actions in enriched context
    # We'll access these directly in _build_template_variables
    enriched.brain_state = brain_state
    enriched.popular_actions = popular_actions
    
    logger.info(
        "intent_detection:enrichment_fetched",
        extra={
            "trace_id": trace_id,
            "has_summary": session_summary is not None,
            "messages_count": len(previous_messages),
            "has_task": active_task is not None,
            "has_narrative": next_narrative is not None,
            "has_brain_state": bool(brain_state),
            "expecting_response": brain_state.get("expecting_response", False),
            "popular_actions_count": len(popular_actions)
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
    # Extract brain state from enriched context
    brain_state = getattr(enriched, 'brain_state', {})
    popular_actions = getattr(enriched, 'popular_actions', [])
    
    return {
        # Basic context (5 variables) - EXISTING ✅
        "user_message": user_message,
        "user_id": user_id,
        "session_id": session_id,
        "user_type": user_type,
        "session_summary": enriched.session_summary or "[No session summary]",
        
        # Message history (1 variable) - EXISTING ✅
        "previous_messages": format_messages(enriched.previous_messages),
        
        # Brain wires (6 variables) - NEW ✅
        "expecting_response": brain_state.get("expecting_response", False),
        "answer_sheet": brain_state.get("answer_sheet"),
        "active_task": brain_state.get("active_task") or format_active_task(enriched.active_task),  # Fallback to old column
        "previous_intents": brain_state.get("previous_intents", []),
        "available_signals": brain_state.get("available_signals", []),
        "conversation_context": brain_state.get("conversation_context", {}),
        
        # Brain output (1 variable) - EXISTING ✅
        "next_narrative": enriched.next_narrative or "[No narrative guidance]",
        
        # Instance config (1 variable) - NEW ✅
        "popular_actions": popular_actions
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