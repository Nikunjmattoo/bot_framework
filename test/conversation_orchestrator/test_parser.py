"""
Unit tests for intent detection parser.

Tests:
- JSON parsing
- Intent validation
- Response text validation
- Error handling
- Edge cases
"""

import pytest
import json
from pydantic import ValidationError

from conversation_orchestrator.intent_detection.parser import (
    parse_intent_response,
    _validate_response_text
)
from conversation_orchestrator.intent_detection.models import (
    IntentType,
    SingleIntent,
    IntentOutput
)
from conversation_orchestrator.exceptions import IntentDetectionError


# ============================================================================
# SECTION 1: Successful Parsing Tests
# ============================================================================

class TestSuccessfulParsing:
    """Test successful parsing of valid LLM responses."""
    
    def test_parse_single_greeting_intent(self):
        """✓ Parse single greeting intent successfully"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User said hello"
            }],
            "response_text": "Hello! How can I help?",
            "self_response": True,
            "reasoning": "Simple greeting"
        })
        
        result = parse_intent_response(response)
        
        assert isinstance(result, IntentOutput)
        assert len(result.intents) == 1
        assert result.intents[0].intent_type == IntentType.GREETING
        assert result.intents[0].confidence == 0.98
        assert result.self_response is True
        assert result.response_text == "Hello! How can I help?"
    
    def test_parse_single_action_intent(self):
        """✓ Parse single action intent successfully"""
        response = json.dumps({
            "intents": [{
                "intent_type": "action",
                "canonical_intent": "check_order_status",
                "confidence": 0.95,
                "entities": {"order_id": "12345"},
                "sequence_order": 1,
                "reasoning": "User wants to check order"
            }],
            "response_text": None,
            "self_response": False,
            "reasoning": "Action requires brain"
        })
        
        result = parse_intent_response(response)
        
        assert len(result.intents) == 1
        assert result.intents[0].intent_type == IntentType.ACTION
        assert result.intents[0].canonical_intent == "check_order_status"
        assert result.intents[0].confidence == 0.95
        assert result.self_response is False
        assert result.response_text is None
    
    def test_parse_multiple_intents(self):
        """✓ Parse multiple intents successfully"""
        response = json.dumps({
            "intents": [
                {
                    "intent_type": "gratitude",
                    "confidence": 0.97,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "User said thanks"
                },
                {
                    "intent_type": "action",
                    "canonical_intent": "check_order",
                    "confidence": 0.94,
                    "entities": {},
                    "sequence_order": 2,
                    "reasoning": "User wants to check order"
                }
            ],
            "response_text": None,
            "self_response": False,
            "reasoning": "Gratitude + action"
        })
        
        result = parse_intent_response(response)
        
        assert len(result.intents) == 2
        assert result.intents[0].intent_type == IntentType.GRATITUDE
        assert result.intents[1].intent_type == IntentType.ACTION
        assert result.self_response is False
    
    def test_parse_with_low_confidence_intent(self):
        """✓ Parse intent with low confidence (< 0.7) - should pass through"""
        response = json.dumps({
            "intents": [{
                "intent_type": "action",
                "confidence": 0.65,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Low confidence"
            }],
            "response_text": None,
            "self_response": False,
            "reasoning": "Uncertain intent"
        })
        
        result = parse_intent_response(response)
        
        # Should pass through to orchestrator/brain
        assert len(result.intents) == 1
        assert result.intents[0].confidence == 0.65
        assert result.intents[0].intent_type == IntentType.ACTION


# ============================================================================
# SECTION 2: Response Text Validation Tests
# ============================================================================

class TestResponseTextValidation:
    """Test response_text validation logic."""
    
    def test_self_respond_with_response_text_valid(self):
        """✓ self_response=True with response_text is valid"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1
            }],
            "response_text": "Hello!",
            "self_response": True,
            "reasoning": "Greeting"
        })
        
        result = parse_intent_response(response)
        assert result.self_response is True
        assert result.response_text == "Hello!"
    
    def test_self_respond_without_response_text_raises_error(self):
        """✓ self_response=True without response_text raises error"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1
            }],
            "response_text": None,
            "self_response": True,
            "reasoning": "Greeting"
        })
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response)
        
        assert exc.value.error_code == "MISSING_RESPONSE_TEXT"
    
    def test_brain_required_without_response_text_valid(self):
        """✓ self_response=False without response_text is valid"""
        response = json.dumps({
            "intents": [{
                "intent_type": "action",
                "confidence": 0.95,
                "entities": {},
                "sequence_order": 1
            }],
            "response_text": None,
            "self_response": False,
            "reasoning": "Action"
        })
        
        result = parse_intent_response(response)
        assert result.self_response is False
        assert result.response_text is None
    
    def test_infer_self_response_from_response_text(self):
        """✓ Infer self_response from response_text if not provided"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1
            }],
            "response_text": "Hello!",
            "self_response": False,  # Wrong flag
            "reasoning": "Greeting"
        })
        
        result = parse_intent_response(response)
        # Should infer self_response=True from greeting intent + response_text
        assert result.self_response is True


# ============================================================================
# SECTION 3: Parser Error Handling Tests
# ============================================================================

class TestParserErrorHandling:
    """Test parser error handling."""
    
    def test_invalid_json_raises_error(self):
        """✓ Invalid JSON raises IntentDetectionError"""
        response = "This is not valid JSON {broken"
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response)
        
        assert exc.value.error_code == "INVALID_JSON"
        assert "not valid json" in str(exc.value).lower()
    
    def test_missing_intents_field_raises_error(self):
        """✓ Missing 'intents' field raises error"""
        response = json.dumps({
            "response_text": "Hello!",
            "self_response": True
        })
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response)
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
        assert "intents" in str(exc.value).lower()
    
    def test_empty_intents_list_raises_error(self):
        """✓ Empty intents list raises error"""
        response = json.dumps({
            "intents": [],
            "response_text": None,
            "self_response": False
        })
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response)
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
    
    def test_intents_not_list_raises_error(self):
        """✓ intents not a list raises error"""
        response = json.dumps({
            "intents": "not a list",
            "response_text": None,
            "self_response": False
        })
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response)
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
    
    def test_missing_intent_type_skips_intent(self):
        """✓ Missing intent_type skips that intent"""
        response = json.dumps({
            "intents": [
                {
                    "confidence": 0.95,
                    "entities": {}
                },
                {
                    "intent_type": "greeting",
                    "confidence": 0.98,
                    "entities": {}
                }
            ],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        # Should skip first intent, parse second
        assert len(result.intents) == 1
        assert result.intents[0].intent_type == IntentType.GREETING
    
    def test_missing_confidence_uses_default(self):
        """✓ Missing confidence uses default 0.5"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "entities": {}
            }],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].confidence == 0.5


# ============================================================================
# SECTION 4: Intent Field Handling Tests
# ============================================================================

class TestIntentFieldHandling:
    """Test handling of optional intent fields."""
    
    def test_sequence_order_auto_assigned(self):
        """✓ sequence_order auto-assigned if missing"""
        response = json.dumps({
            "intents": [
                {
                    "intent_type": "greeting",
                    "confidence": 0.98,
                    "entities": {}
                },
                {
                    "intent_type": "action",
                    "confidence": 0.95,
                    "entities": {}
                }
            ],
            "response_text": None,
            "self_response": False
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].sequence_order == 1
        assert result.intents[1].sequence_order == 2
    
    def test_entities_defaults_to_empty_dict(self):
        """✓ entities defaults to empty dict if missing"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98
            }],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].entities == {}
    
    def test_canonical_intent_optional(self):
        """✓ canonical_intent is optional"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {}
            }],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].canonical_intent is None
    
    def test_reasoning_optional_in_intent(self):
        """✓ reasoning is optional in intent"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {}
            }],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].reasoning is None
    
    def test_reasoning_optional_in_output(self):
        """✓ reasoning is optional in output"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {}
            }],
            "response_text": "Hello!",
            "self_response": True
        })
        
        result = parse_intent_response(response)
        
        assert result.reasoning is None


# ============================================================================
# SECTION 5: Edge Cases
# ============================================================================

class TestParserEdgeCases:
    """Test parser edge cases."""
    
    def test_response_with_unicode_characters(self):
        """✓ Parse response with unicode characters"""
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "reasoning": "User said 你好"
            }],
            "response_text": "Hello! 你好!",
            "self_response": True,
            "reasoning": "Greeting with unicode"
        })
        
        result = parse_intent_response(response)
        
        assert "你好" in result.response_text
        assert result.intents[0].reasoning == "User said 你好"
    
    def test_response_with_very_long_reasoning(self):
        """✓ Parse response with very long reasoning"""
        long_reasoning = "A" * 1000
        response = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "reasoning": long_reasoning
            }],
            "response_text": "Hello!",
            "self_response": True,
            "reasoning": long_reasoning
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].reasoning == long_reasoning
        assert result.reasoning == long_reasoning
    
    def test_response_with_special_characters_in_entities(self):
        """✓ Parse entities with special characters"""
        response = json.dumps({
            "intents": [{
                "intent_type": "action",
                "confidence": 0.95,
                "entities": {
                    "email": "user@example.com",
                    "phone": "+1-234-567-8900",
                    "name": "O'Brien"
                }
            }],
            "response_text": None,
            "self_response": False
        })
        
        result = parse_intent_response(response)
        
        assert result.intents[0].entities["email"] == "user@example.com"
        assert result.intents[0].entities["phone"] == "+1-234-567-8900"
        assert result.intents[0].entities["name"] == "O'Brien"
    
    def test_all_intents_with_confidence_variations(self):
        """✓ Parse intents with various confidence scores"""
        response = json.dumps({
            "intents": [
                {"intent_type": "greeting", "confidence": 0.99, "entities": {}},
                {"intent_type": "action", "confidence": 0.85, "entities": {}},
                {"intent_type": "gratitude", "confidence": 0.70, "entities": {}},
                {"intent_type": "chitchat", "confidence": 0.65, "entities": {}}
            ],
            "response_text": None,
            "self_response": False
        })
        
        result = parse_intent_response(response)
        
        # All intents should pass through (no filtering)
        assert len(result.intents) == 4
        assert result.intents[0].confidence == 0.99
        assert result.intents[1].confidence == 0.85
        assert result.intents[2].confidence == 0.70
        assert result.intents[3].confidence == 0.65


# ============================================================================
# SECTION 6: Validation Function Tests
# ============================================================================

class TestValidateResponseText:
    """Test _validate_response_text function directly."""
    
    def test_valid_self_respond_with_text(self):
        """✓ Valid: self_response=True with response_text"""
        intents = [SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=0.98,
            entities={}
        )]
        
        # Should not raise
        _validate_response_text(intents, "Hello!", True)
    
    def test_invalid_self_respond_without_text(self):
        """✓ Invalid: self_response=True without response_text"""
        intents = [SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=0.98,
            entities={}
        )]
        
        with pytest.raises(IntentDetectionError) as exc:
            _validate_response_text(intents, None, True)
        
        assert exc.value.error_code == "MISSING_RESPONSE_TEXT"
    
    def test_valid_brain_required_without_text(self):
        """✓ Valid: self_response=False without response_text"""
        intents = [SingleIntent(
            intent_type=IntentType.ACTION,
            confidence=0.95,
            entities={}
        )]
        
        # Should not raise
        _validate_response_text(intents, None, False)
    
    def test_warning_for_brain_required_with_text(self):
        """✓ Warning (not error): self_response=False with response_text"""
        intents = [SingleIntent(
            intent_type=IntentType.ACTION,
            confidence=0.95,
            entities={}
        )]
        
        # Should not raise (just warning)
        _validate_response_text(intents, "Some text", False)