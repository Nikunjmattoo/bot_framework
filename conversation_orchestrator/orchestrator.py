"""
Main orchestrator entry point.

Receives adapter payload, orchestrates all steps, returns final response.
"""

import logging
import time
import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session  # ← ADD THIS IMPORT

from conversation_orchestrator.exceptions import (
    OrchestratorError,
    ValidationError
)
from conversation_orchestrator.intent_detection.detector import detect_intents
from conversation_orchestrator.utils.logging import get_logger
from conversation_orchestrator.utils.validation import validate_adapter_payload

logger = get_logger(__name__)


async def process_message(
    db: Session,
    adapter_payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for conversation orchestrator.
    
    Orchestrates:
    1. Intent detection
    2. Brain processing (if needed)
    3. Response generation
    4. Post-processing
    
    Args:
        adapter_payload: Message adapter from message_handler
        db: Database session for persistence
        
    Returns:
        {
            "text": str,
            "intents": List[Dict],
            "self_response": bool,
            "reasoning": str,
            "token_usage": Dict,
            "latency_ms": float,
            "trace_id": str
        }
    """
    start_time = time.time()
    
    # Extract or generate trace_id
    trace_id = adapter_payload.get("trace_id") or str(uuid.uuid4())
    
    logger.info(
        "orchestrator:started",
        extra={
            "trace_id": trace_id,
            "session_id": adapter_payload.get("session_id"),
            "user_id": adapter_payload.get("message", {}).get("sender_user_id")
        }
    )
    
    try:
        # Validate adapter payload
        validate_adapter_payload(adapter_payload)
        
        # Get turn number from session
        session_id = adapter_payload.get("session_id")
        turn_number = 1  # Default
        
        if session_id:
            from db.models.messages import MessageModel
            # Count existing messages in this session
            turn_number = db.query(MessageModel).filter(
                MessageModel.session_id == session_id
            ).count() + 1
        
        # Step 1: Intent Detection
        intent_result = await detect_intents(db, adapter_payload, trace_id)
        
        logger.info(
            "orchestrator:intents_detected",
            extra={
                "trace_id": trace_id,
                "intents": [i["intent_type"] for i in intent_result["intents"]],
                "self_response": intent_result.get("self_response", False)
            }
        )
        
        # Step 2: Route based on intent type
        from conversation_orchestrator.intent_detection.models import is_self_respond_only
        
        self_response = intent_result.get("self_response", False)
        intents = intent_result.get("intents", [])
        
        # Convert dict intents to SingleIntent objects for helper function
        from conversation_orchestrator.intent_detection.models import SingleIntent, IntentType
        intent_objects = []
        for intent_dict in intents:
            intent_objects.append(SingleIntent(
                intent_type=IntentType(intent_dict["intent_type"]),
                canonical_intent=intent_dict.get("canonical_intent"),
                confidence=intent_dict["confidence"],
                entities=intent_dict.get("entities", {}),
                sequence_order=intent_dict.get("sequence_order"),
                reasoning=intent_dict.get("reasoning")
            ))
        
        if is_self_respond_only(intent_objects):
            # Self-respond path: Use LLM-generated response directly
            logger.info(
                "orchestrator:self_respond_path",
                extra={
                    "trace_id": trace_id,
                    "intents": [i["intent_type"] for i in intent_result["intents"]]
                }
            )
            
            final_text = intent_result.get("response_text") or "Hello! How can I help you?"
        
        else:
            # Brain-required: Pass to brain for processing
            logger.info(
                "orchestrator:brain_required_path",
                extra={
                    "trace_id": trace_id,
                    "intents": [i["intent_type"] for i in intent_result["intents"]]
                }
            )
            
            # Step 3: Brain Processing
            from conversation_orchestrator.brain import process_brain
            
            brain_result = await process_brain(
                db=db,  # ADD THIS
                intent_result=intent_result,
                session_id=adapter_payload["session_id"],
                user_id=adapter_payload["message"]["sender_user_id"],
                instance_id=adapter_payload["routing"]["instance_id"],
                brand_id=adapter_payload["routing"]["brand_id"],
                turn_number=turn_number
            )
            
            final_text = brain_result["text"]
            
            # TODO: Step 4 - Response Generation (if needed)
            # For now, Brain returns the final text
        
        # Calculate total latency
        total_latency_ms = (time.time() - start_time) * 1000
        
        # Build final result
        result = {
            "text": final_text,
            "intents": intent_result["intents"],
            "self_response": self_response,
            "reasoning": intent_result.get("reasoning"),
            "token_usage": intent_result.get("token_usage", {}),
            "latency_ms": total_latency_ms,
            "trace_id": trace_id
        }
        
        logger.info(
            "orchestrator:completed",
            extra={
                "trace_id": trace_id,
                "latency_ms": total_latency_ms,
                "self_response": self_response,
                "response_length": len(final_text),
                "tokens_total": intent_result.get("token_usage", {}).get("total", 0)
            }
        )
        
        return result
    
    except ValidationError as e:
        logger.error(
            "orchestrator:validation_error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_code": e.error_code
            }
        )
        raise
    
    except OrchestratorError as e:
        logger.error(
            "orchestrator:error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_code": e.error_code
            }
        )
        raise
    
    except Exception as e:
        logger.error(
            "orchestrator:unexpected_error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        raise OrchestratorError(
            message=f"Unexpected error: {str(e)}",
            error_code="UNEXPECTED_ERROR"
        ) from e