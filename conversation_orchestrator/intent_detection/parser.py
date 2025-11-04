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
        # Strip whitespace
        response_content = response_content.strip()
        
        # Remove markdown code fences if present (defensive parsing)
        if response_content.startswith('```'):
            lines = response_content.split('\n')
            # Remove first line (```json or ``` or ```JSON)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response_content = '\n'.join(lines).strip()
        
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
        
        # NO FILTERING - pass all intents through to orchestrator
        # Brain will decide what to do with low confidence intents
        
        # Extract response_text and self_response from LLM output
        response_text = data.get("response_text")
        self_response = data.get("self_response", False)
        
        # Infer self_response if not provided by LLM
        if not self_response and response_text:
            # If LLM provided response_text but didn't set self_response flag,
            # infer it based on intent types
            self_response = is_self_respond_only(intents)
        
        # Validate response_text consistency
        _validate_response_text(intents, response_text, self_response)
        
        # Create output object
        output = IntentOutput(
            intents=intents,
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
            message=f"LLM response is not valid json: {str(e)}",
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