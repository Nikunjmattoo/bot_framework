"""
Intent detection parser.

Parses LLM JSON response into IntentOutput structure.
"""

import logging
import json
from typing import Dict, Any

from conversation_orchestrator.intent_detection.models import (
    IntentOutput,
    SingleIntent,
    IntentType
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
        
        # Create output object
        output = IntentOutput(
            intents=intents,
            reasoning=data.get("reasoning")
        )
        
        logger.info(
            "intent_parser:parsing_complete",
            extra={
                "intents_count": len(output.intents),
                "has_reasoning": output.reasoning is not None
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