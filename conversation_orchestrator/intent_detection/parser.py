"""
Intent detection parser.

Parses LLM JSON response into IntentOutput structure.
"""

import logging
import json
from typing import Dict, Any, List

from conversation_orchestrator.intent_detection.models import (
    IntentOutput,
    SingleIntent,
    IntentType,
    SELF_RESPOND_INTENTS,
    MIN_CONFIDENCE,
    CLARIFICATION_CONFIDENCE,
    is_self_respond_only
)
from conversation_orchestrator.exceptions import IntentDetectionError

logger = logging.getLogger(__name__)


def parse_intent_response(response_content: str) -> IntentOutput:
    """
    Parse LLM JSON response into IntentOutput.
    
    Args:
        response_content: Raw JSON string from LLM
    
    Returns:
        IntentOutput object with parsed intents
    
    Raises:
        IntentDetectionError: If parsing fails
    """
    try:
        # Parse JSON
        data = json.loads(response_content)
        
        logger.debug(
            "intent_parser:json_parsed",
            extra={"data_keys": list(data.keys())}
        )
        
        # Validate structure
        if "intents" not in data:
            raise IntentDetectionError(
                message="Response missing 'intents' field",
                error_code="INVALID_RESPONSE_STRUCTURE"
            )
        
        if not isinstance(data["intents"], list):
            raise IntentDetectionError(
                message="'intents' must be a list",
                error_code="INVALID_RESPONSE_STRUCTURE"
            )
        
        if len(data["intents"]) == 0:
            raise IntentDetectionError(
                message="'intents' list cannot be empty",
                error_code="INVALID_RESPONSE_STRUCTURE"
            )
        
        # Parse intents
        intents = []
        for idx, intent_data in enumerate(data["intents"]):
            try:
                # Set sequence_order if not present
                if "sequence_order" not in intent_data or intent_data["sequence_order"] is None:
                    intent_data["sequence_order"] = idx + 1
                
                # Ensure entities exists
                if "entities" not in intent_data:
                    intent_data["entities"] = {}
                
                # Validate intent_type
                if "intent_type" not in intent_data:
                    logger.warning(
                        "intent_parser:missing_intent_type",
                        extra={"index": idx}
                    )
                    continue
                
                # Validate confidence
                if "confidence" not in intent_data:
                    logger.warning(
                        "intent_parser:missing_confidence",
                        extra={"index": idx}
                    )
                    intent_data["confidence"] = 0.5  # Default
                
                # Create SingleIntent object (Pydantic will validate)
                intent = SingleIntent(**intent_data)
                intents.append(intent)
                
                logger.debug(
                    "intent_parser:intent_parsed",
                    extra={
                        "index": idx,
                        "intent_type": intent.intent_type.value,
                        "confidence": intent.confidence
                    }
                )
            
            except Exception as e:
                logger.warning(
                    "intent_parser:failed_to_parse_intent",
                    extra={"index": idx, "error": str(e)}
                )
                # Continue with other intents
                continue
        
        if len(intents) == 0:
            raise IntentDetectionError(
                message="No valid intents could be parsed",
                error_code="NO_VALID_INTENTS"
            )
        
        # PHASE II: Apply confidence filtering
        filtered_intents = _filter_by_confidence(intents)
        
        # PHASE II: Extract response_text and self_response from LLM output
        response_text = data.get("response_text")
        self_response = data.get("self_response", False)
        
        # PHASE II: Infer self_response if not provided by LLM
        if not self_response and response_text:
            # If LLM provided response_text but didn't set self_response flag,
            # infer it based on intent types
            self_response = is_self_respond_only(filtered_intents)
        
        # PHASE II: Validate response_text consistency
        _validate_response_text(filtered_intents, response_text, self_response)
        
        # Create output object
        output = IntentOutput(
            intents=filtered_intents,
            reasoning=data.get("reasoning"),
            response_text=response_text,
            self_response=self_response
        )
        
        logger.info(
            "intent_parser:parsing_complete",
            extra={
                "intents_count": len(output.intents),
                "has_reasoning": output.reasoning is not None,
                "self_response": output.self_response,
                "has_response_text": output.response_text is not None
            }
        )
        
        return output
    
    except json.JSONDecodeError as e:
        logger.error(
            "intent_parser:invalid_json",
            extra={"error": str(e)}
        )
        raise IntentDetectionError(
            message=f"LLM response is not valid JSON: {str(e)}",
            error_code="INVALID_JSON"
        ) from e
    
    except IntentDetectionError:
        # Re-raise our own exceptions
        raise
    
    except Exception as e:
        logger.error(
            "intent_parser:unexpected_error",
            extra={"error": str(e)}
        )
        raise IntentDetectionError(
            message=f"Failed to parse intent response: {str(e)}",
            error_code="PARSING_FAILED"
        ) from e


def _filter_by_confidence(intents: List[SingleIntent]) -> List[SingleIntent]:
    """
    Filter intents by confidence threshold.
    
    Rules:
    - Remove intents with confidence < 0.7
    - If no intents remain -> create fallback intent
    - If single intent remains with confidence < 0.85 -> create clarification intent
    
    Args:
        intents: List of parsed intents
    
    Returns:
        List of filtered intents (or fallback/clarification intent)
    """
    # Filter by minimum confidence
    high_confidence_intents = [
        intent for intent in intents 
        if intent.confidence >= MIN_CONFIDENCE
    ]
    
    logger.debug(
        "intent_parser:confidence_filtering",
        extra={
            "original_count": len(intents),
            "filtered_count": len(high_confidence_intents),
            "min_confidence": MIN_CONFIDENCE
        }
    )
    
    # Case 1: No high-confidence intents remain
    if len(high_confidence_intents) == 0:
        logger.info(
            "intent_parser:no_high_confidence_intents",
            extra={"creating": "fallback_intent"}
        )
        return [_create_fallback_intent()]
    
    # Case 2: Single intent with confidence < 0.85
    if len(high_confidence_intents) == 1:
        single_intent = high_confidence_intents[0]
        if single_intent.confidence < CLARIFICATION_CONFIDENCE:
            logger.info(
                "intent_parser:low_confidence_single_intent",
                extra={
                    "confidence": single_intent.confidence,
                    "threshold": CLARIFICATION_CONFIDENCE,
                    "creating": "clarification_intent"
                }
            )
            return [_create_clarification_intent()]
    
    # Case 3: Return filtered intents
    return high_confidence_intents


def _create_fallback_intent() -> SingleIntent:
    """
    Create fallback intent when no high-confidence intents found.
    
    Returns:
        SingleIntent with fallback type
    """
    return SingleIntent(
        intent_type=IntentType.FALLBACK,
        canonical_intent=None,
        confidence=0.5,
        entities={},
        sequence_order=1
    )


def _create_clarification_intent() -> SingleIntent:
    """
    Create clarification intent when single intent has low confidence.
    
    Returns:
        SingleIntent with clarification type
    """
    return SingleIntent(
        intent_type=IntentType.CLARIFICATION,
        canonical_intent=None,
        confidence=0.6,
        entities={},
        sequence_order=1
    )


def _validate_response_text(
    intents: List[SingleIntent],
    response_text: str | None,
    self_response: bool
) -> None:
    """
    Validate consistency between response_text and self_response flag.
    
    Rules:
    - If self_response=True, response_text must exist
    - If self_response=False, response_text should be None
    - If all intents are self-respond types, validate response_text exists
    
    Args:
        intents: List of filtered intents
        response_text: Response text from LLM
        self_response: Self-response flag
    
    Raises:
        IntentDetectionError: If validation fails
    """
    # Check if all intents are self-respond types
    all_self_respond = is_self_respond_only(intents)
    
    # Rule 1: If self_response=True, response_text must exist
    if self_response and not response_text:
        logger.error(
            "intent_parser:validation_error",
            extra={
                "error": "self_response=True but response_text is None",
                "intents": [i.intent_type.value for i in intents]
            }
        )
        raise IntentDetectionError(
            message="self_response is True but response_text is missing",
            error_code="MISSING_RESPONSE_TEXT",
            details={
                "self_response": self_response,
                "intents": [i.intent_type.value for i in intents]
            }
        )
    
    # Rule 2: If all intents are self-respond and self_response=True, response_text must exist
    if all_self_respond and self_response and not response_text:
        logger.error(
            "intent_parser:validation_error",
            extra={
                "error": "all self-respond intents but no response_text",
                "intents": [i.intent_type.value for i in intents]
            }
        )
        raise IntentDetectionError(
            message="All intents are self-respond types but response_text is missing",
            error_code="MISSING_RESPONSE_TEXT",
            details={
                "intents": [i.intent_type.value for i in intents]
            }
        )
    
    # Rule 3: If self_response=False, response_text should ideally be None (warning only)
    if not self_response and response_text:
        logger.warning(
            "intent_parser:inconsistent_response",
            extra={
                "warning": "self_response=False but response_text exists",
                "response_text_length": len(response_text)
            }
        )
    
    logger.debug(
        "intent_parser:validation_passed",
        extra={
            "self_response": self_response,
            "has_response_text": response_text is not None,
            "all_self_respond": all_self_respond
        }
    )