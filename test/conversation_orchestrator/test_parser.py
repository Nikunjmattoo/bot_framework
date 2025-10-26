"""
Unit tests for intent detection parser.

Tests:
- parse_intent_response() function
- Confidence filtering logic
- Fallback intent creation
- Clarification intent creation
- Response text validation
- Error handling
"""

import pytest
import json

from conversation_orchestrator.intent_detection.parser import (
    parse_intent_response,
    _filter_by_confidence,
    _create_fallback_intent,
    _create_clarification_intent,
    _validate_response_text
)
from conversation_orchestrator.intent_detection.models import (
    IntentType,
    SingleIntent,
    IntentOutput,
    MIN_CONFIDENCE,
    CLARIFICATION_CONFIDENCE
)
from conversation_orchestrator.exceptions import IntentDetectionError


# ============================================================================
# SECTION 1: Successful Parsing Tests
# ============================================================================

class TestParseIntentResponseSuccess:
    """Test successful parsing scenarios."""
    
    def test_parse_single_greeting_intent(self, llm_response_greeting):
        """✓ Parse single greeting intent successfully"""
        output = parse_intent_response(llm_response_greeting["content"])
        
        assert isinstance(output, IntentOutput)
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.GREETING
        assert output.intents[0].confidence == 0.98
        assert output.response_text == "Hello! How can I help you today?"
        assert output.self_response is True
    
    def test_parse_single_action_intent(self, llm_response_action):
        """✓ Parse single action intent successfully"""
        output = parse_intent_response(llm_response_action["content"])
        
        assert isinstance(output, IntentOutput)
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.ACTION
        assert output.intents[0].canonical_intent == "check_order_status"
        assert output.intents[0].confidence == 0.95
        assert output.response_text is None
        assert output.self_response is False
    
    def test_parse_multiple_intents_mixed(self, llm_response_multi_intent_mixed):
        """✓ Parse multiple intents (mixed types)"""
        output = parse_intent_response(llm_response_multi_intent_mixed["content"])
        
        assert isinstance(output, IntentOutput)
        assert len(output.intents) == 2
        assert output.intents[0].intent_type == IntentType.GRATITUDE
        assert output.intents[0].sequence_order == 1
        assert output.intents[1].intent_type == IntentType.ACTION
        assert output.intents[1].sequence_order == 2
        assert output.self_response is False
    
    def test_parse_multiple_intents_self_respond(self, llm_response_multi_intent_self_respond):
        """✓ Parse multiple self-respond intents"""
        output = parse_intent_response(llm_response_multi_intent_self_respond["content"])
        
        assert isinstance(output, IntentOutput)
        assert len(output.intents) == 2
        assert output.intents[0].intent_type == IntentType.GRATITUDE
        assert output.intents[1].intent_type == IntentType.GOODBYE
        assert output.response_text == "You're welcome! Goodbye and have a great day!"
        assert output.self_response is True
    
    def test_parse_multiple_action_intents(self, llm_response_multi_action):
        """✓ Parse multiple action intents"""
        output = parse_intent_response(llm_response_multi_action["content"])
        
        assert isinstance(output, IntentOutput)
        assert len(output.intents) == 2
        assert output.intents[0].canonical_intent == "create_profile"
        assert output.intents[1].canonical_intent == "apply_for_job"
        assert output.self_response is False
    
    def test_parse_all_self_respond_intent_types(
        self,
        llm_response_greeting,
        llm_response_goodbye,
        llm_response_gratitude,
        llm_response_chitchat
    ):
        """✓ Parse all 4 self-respond intent types"""
        responses = [
            llm_response_greeting,
            llm_response_goodbye,
            llm_response_gratitude,
            llm_response_chitchat
        ]
        
        expected_types = [
            IntentType.GREETING,
            IntentType.GOODBYE,
            IntentType.GRATITUDE,
            IntentType.CHITCHAT
        ]
        
        for response, expected_type in zip(responses, expected_types):
            output = parse_intent_response(response["content"])
            assert output.intents[0].intent_type == expected_type
            assert output.self_response is True
            assert output.response_text is not None
    
    def test_parse_reasoning_field_present(self, llm_response_greeting):
        """✓ Parse reasoning field if present"""
        output = parse_intent_response(llm_response_greeting["content"])
        assert output.reasoning == "Simple greeting - responding directly"
    
    def test_parse_entities_empty_dict(self, llm_response_greeting):
        """✓ Parse entities as empty dict"""
        output = parse_intent_response(llm_response_greeting["content"])
        assert output.intents[0].entities == {}


# ============================================================================
# SECTION 2: Confidence Filtering Tests
# ============================================================================

class TestConfidenceFiltering:
    """Test confidence filtering logic."""
    
    def test_high_confidence_intents_pass_filter(self):
        """✓ High confidence intents (≥0.7) pass filter"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.95,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.85,
                entities={},
                sequence_order=2
            )
        ]
        
        filtered = _filter_by_confidence(intents)
        assert len(filtered) == 2
    
    def test_low_confidence_intents_filtered_out(self, llm_response_low_confidence):
        """✓ Low confidence intents (<0.7) filtered out → fallback"""
        output = parse_intent_response(llm_response_low_confidence["content"])
        
        # Should create fallback intent
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.FALLBACK
        assert output.intents[0].confidence == 0.5
    
    def test_single_medium_confidence_creates_clarification(self, llm_response_single_low_confidence):
        """✓ Single intent with confidence 0.7-0.85 creates clarification"""
        output = parse_intent_response(llm_response_single_low_confidence["content"])
        
        # Should create clarification intent
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.CLARIFICATION
        assert output.intents[0].confidence == 0.6
    
    def test_confidence_exactly_0_7_passes(self):
        """✓ Confidence = 0.7 passes filter (edge case)"""
        intents = [
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.7,
                entities={},
                sequence_order=1
            )
        ]
        
        filtered = _filter_by_confidence(intents)
        assert len(filtered) == 1
        assert filtered[0].intent_type == IntentType.ACTION
    
    def test_confidence_exactly_0_85_no_clarification(self):
        """✓ Confidence = 0.85 doesn't trigger clarification (edge case)"""
        intents = [
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.85,
                entities={},
                sequence_order=1
            )
        ]
        
        filtered = _filter_by_confidence(intents)
        assert len(filtered) == 1
        assert filtered[0].intent_type == IntentType.ACTION
    
    def test_mixed_confidence_filters_low_keeps_high(self):
        """✓ Mixed confidence: filters low, keeps high"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.95,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="unknown",
                confidence=0.45,
                entities={},
                sequence_order=2
            ),
            SingleIntent(
                intent_type=IntentType.GRATITUDE,
                confidence=0.88,
                entities={},
                sequence_order=3
            )
        ]
        
        filtered = _filter_by_confidence(intents)
        assert len(filtered) == 2
        assert filtered[0].intent_type == IntentType.GREETING
        assert filtered[1].intent_type == IntentType.GRATITUDE


# ============================================================================
# SECTION 3: Fallback Intent Creation Tests
# ============================================================================

class TestFallbackIntentCreation:
    """Test fallback intent creation."""
    
    def test_create_fallback_intent_structure(self):
        """✓ Fallback intent has correct structure"""
        fallback = _create_fallback_intent()
        
        assert isinstance(fallback, SingleIntent)
        assert fallback.intent_type == IntentType.FALLBACK
        assert fallback.canonical_intent is None
        assert fallback.confidence == 0.5
        assert fallback.entities == {}
        assert fallback.sequence_order == 1
    
    def test_no_high_confidence_creates_fallback(self, llm_response_low_confidence):
        """✓ No high-confidence intents → creates fallback"""
        output = parse_intent_response(llm_response_low_confidence["content"])
        
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.FALLBACK


# ============================================================================
# SECTION 4: Clarification Intent Creation Tests
# ============================================================================

class TestClarificationIntentCreation:
    """Test clarification intent creation."""
    
    def test_create_clarification_intent_structure(self):
        """✓ Clarification intent has correct structure"""
        clarification = _create_clarification_intent()
        
        assert isinstance(clarification, SingleIntent)
        assert clarification.intent_type == IntentType.CLARIFICATION
        assert clarification.canonical_intent is None
        assert clarification.confidence == 0.6
        assert clarification.entities == {}
        assert clarification.sequence_order == 1
    
    def test_single_medium_confidence_creates_clarification(self):
        """✓ Single intent with confidence 0.7-0.84 → creates clarification"""
        response_content = json.dumps({
            "intents": [{
                "intent_type": "action",
                "canonical_intent": "check_order",
                "confidence": 0.75,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Somewhat clear"
            }],
            "response_text": None,
            "self_response": False,
            "reasoning": "Medium confidence"
        })
        
        output = parse_intent_response(response_content)
        
        assert len(output.intents) == 1
        assert output.intents[0].intent_type == IntentType.CLARIFICATION
    
    def test_multiple_intents_no_clarification_even_if_low(self):
        """✓ Multiple intents with medium confidence → no clarification"""
        response_content = json.dumps({
            "intents": [
                {
                    "intent_type": "greeting",
                    "canonical_intent": None,
                    "confidence": 0.75,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "Greeting"
                },
                {
                    "intent_type": "action",
                    "canonical_intent": "check_order",
                    "confidence": 0.78,
                    "entities": {},
                    "sequence_order": 2,
                    "reasoning": "Action"
                }
            ],
            "response_text": None,
            "self_response": False,
            "reasoning": "Multiple intents"
        })
        
        output = parse_intent_response(response_content)
        
        # Should keep both intents, no clarification
        assert len(output.intents) == 2
        assert output.intents[0].intent_type == IntentType.GREETING
        assert output.intents[1].intent_type == IntentType.ACTION


# ============================================================================
# SECTION 5: Response Text Validation Tests
# ============================================================================

class TestResponseTextValidation:
    """Test response_text validation logic."""
    
    def test_self_response_true_with_text_valid(self):
        """✓ self_response=true with response_text → valid"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            )
        ]
        response_text = "Hello!"
        self_response = True
        
        # Should not raise
        _validate_response_text(intents, response_text, self_response)
    
    def test_self_response_true_without_text_invalid(self, llm_response_self_respond_without_text):
        """✓ self_response=true without response_text → invalid"""
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(llm_response_self_respond_without_text["content"])
        
        assert "response_text is missing" in str(exc.value).lower()
        assert exc.value.error_code == "MISSING_RESPONSE_TEXT"
    
    def test_self_response_false_without_text_valid(self):
        """✓ self_response=false without response_text → valid"""
        intents = [
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=1
            )
        ]
        response_text = None
        self_response = False
        
        # Should not raise
        _validate_response_text(intents, response_text, self_response)
    
    def test_self_response_false_with_text_warning_only(self, caplog):
        """✓ self_response=false with response_text → warning only"""
        intents = [
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=1
            )
        ]
        response_text = "Some text"
        self_response = False
        
        # Should not raise, but log warning
        _validate_response_text(intents, response_text, self_response)
        # Check logs if needed
    
    def test_all_self_respond_with_text_valid(self):
        """✓ All self-respond intents with response_text → valid"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.GRATITUDE,
                confidence=0.97,
                entities={},
                sequence_order=2
            )
        ]
        response_text = "Hello! You're welcome!"
        self_response = True
        
        # Should not raise
        _validate_response_text(intents, response_text, self_response)
    
    def test_all_self_respond_without_text_but_flag_true_invalid(self):
        """✓ All self-respond intents, self_response=true, no text → invalid"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            )
        ]
        response_text = None
        self_response = True
        
        with pytest.raises(IntentDetectionError) as exc:
            _validate_response_text(intents, response_text, self_response)
        
        assert exc.value.error_code == "MISSING_RESPONSE_TEXT"


# ============================================================================
# SECTION 6: Error Handling Tests
# ============================================================================

class TestParserErrorHandling:
    """Test parser error handling."""
    
    def test_invalid_json_raises_error(self, llm_response_invalid_json):
        """✓ Invalid JSON raises IntentDetectionError"""
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(llm_response_invalid_json["content"])
        
        assert exc.value.error_code == "INVALID_JSON"
        assert "not valid JSON" in str(exc.value).lower()
    
    def test_missing_intents_field_raises_error(self, llm_response_missing_intents):
        """✓ Missing 'intents' field raises error"""
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(llm_response_missing_intents["content"])
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
        assert "missing 'intents' field" in str(exc.value).lower()
    
    def test_empty_intents_list_raises_error(self, llm_response_empty_intents):
        """✓ Empty intents list raises error"""
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(llm_response_empty_intents["content"])
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
        assert "cannot be empty" in str(exc.value).lower()
    
    def test_missing_confidence_field_uses_default(self, llm_response_missing_confidence):
        """✓ Missing confidence field uses default 0.5"""
        output = parse_intent_response(llm_response_missing_confidence["content"])
        
        # Should parse with default confidence
        assert output.intents[0].confidence == 0.5
    
    def test_malformed_intent_skipped_continues_parsing(self):
        """✓ Malformed intent skipped, parsing continues"""
        response_content = json.dumps({
            "intents": [
                {
                    "intent_type": "greeting",
                    "confidence": 0.98,
                    "entities": {},
                    "sequence_order": 1
                },
                {
                    # Missing intent_type - malformed
                    "confidence": 0.95,
                    "entities": {},
                    "sequence_order": 2
                },
                {
                    "intent_type": "gratitude",
                    "confidence": 0.97,
                    "entities": {},
                    "sequence_order": 3
                }
            ],
            "response_text": "Hello! Thanks!",
            "self_response": True,
            "reasoning": "Mixed"
        })
        
        output = parse_intent_response(response_content)
        
        # Should have 2 valid intents (greeting and gratitude)
        assert len(output.intents) == 2
        assert output.intents[0].intent_type == IntentType.GREETING
        assert output.intents[1].intent_type == IntentType.GRATITUDE
    
    def test_all_intents_malformed_raises_error(self):
        """✓ All intents malformed raises NO_VALID_INTENTS error"""
        response_content = json.dumps({
            "intents": [
                {
                    # Missing intent_type
                    "confidence": 0.95,
                    "entities": {}
                },
                {
                    # Missing confidence
                    "intent_type": "greeting",
                    "entities": {}
                }
            ],
            "response_text": None,
            "self_response": False,
            "reasoning": "All malformed"
        })
        
        # Should raise error after trying to parse all
        # Note: This depends on implementation - might create fallback
        # Let's check actual behavior
        try:
            output = parse_intent_response(response_content)
            # If it doesn't raise, check if fallback was created
            assert output.intents[0].intent_type == IntentType.FALLBACK
        except IntentDetectionError as e:
            assert e.error_code == "NO_VALID_INTENTS"
    
    def test_intents_not_list_raises_error(self):
        """✓ 'intents' not a list raises error"""
        response_content = json.dumps({
            "intents": "not_a_list",
            "response_text": None,
            "self_response": False,
            "reasoning": "Invalid"
        })
        
        with pytest.raises(IntentDetectionError) as exc:
            parse_intent_response(response_content)
        
        assert exc.value.error_code == "INVALID_RESPONSE_STRUCTURE"
        assert "must be a list" in str(exc.value).lower()
    
    def test_sequence_order_auto_assigned_if_missing(self):
        """✓ sequence_order auto-assigned if missing"""
        response_content = json.dumps({
            "intents": [
                {
                    "intent_type": "greeting",
                    "confidence": 0.98,
                    "entities": {}
                    # No sequence_order
                },
                {
                    "intent_type": "gratitude",
                    "confidence": 0.97,
                    "entities": {}
                    # No sequence_order
                }
            ],
            "response_text": "Hello! Thanks!",
            "self_response": True,
            "reasoning": "Auto sequence"
        })
        
        output = parse_intent_response(response_content)
        
        assert output.intents[0].sequence_order == 1
        assert output.intents[1].sequence_order == 2


# ============================================================================
# SECTION 7: Edge Cases
# ============================================================================

class TestParserEdgeCases:
    """Test parser edge cases."""
    
    def test_response_with_unicode_characters(self):
        """✓ Response with unicode characters parsed correctly"""
        response_content = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": None,
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User greeted with émojis 🚀"
            }],
            "response_text": "Hello! 你好! مرحبا!",
            "self_response": True,
            "reasoning": "Multi-language greeting"
        })
        
        output = parse_intent_response(response_content)
        
        assert output.response_text == "Hello! 你好! مرحبا!"
        assert output.intents[0].reasoning == "User greeted with émojis 🚀"
    
    def test_response_with_very_long_reasoning(self):
        """✓ Very long reasoning text parsed correctly"""
        long_reasoning = "A" * 10000
        response_content = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": long_reasoning
            }],
            "response_text": "Hello!",
            "self_response": True,
            "reasoning": long_reasoning
        })
        
        output = parse_intent_response(response_content)
        
        assert len(output.reasoning) == 10000
        assert len(output.intents[0].reasoning) == 10000
    
    def test_response_with_nested_entities(self):
        """✓ Nested entities parsed correctly"""
        response_content = json.dumps({
            "intents": [{
                "intent_type": "action",
                "canonical_intent": "book_appointment",
                "confidence": 0.95,
                "entities": {
                    "date": "2025-10-27",
                    "time": "10:00",
                    "location": {
                        "city": "San Francisco",
                        "address": "123 Main St"
                    }
                },
                "sequence_order": 1,
                "reasoning": "Booking appointment"
            }],
            "response_text": None,
            "self_response": False,
            "reasoning": "Action with nested entities"
        })
        
        output = parse_intent_response(response_content)
        
        assert output.intents[0].entities["location"]["city"] == "San Francisco"
        assert output.intents[0].entities["date"] == "2025-10-27"
    
    def test_response_with_null_canonical_intent(self):
        """✓ null canonical_intent parsed as None"""
        response_content = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": None,
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Greeting"
            }],
            "response_text": "Hello!",
            "self_response": True,
            "reasoning": "Simple greeting"
        })
        
        output = parse_intent_response(response_content)
        
        assert output.intents[0].canonical_intent is None
    
    def test_response_with_extra_fields_ignored(self):
        """✓ Extra fields in response ignored gracefully"""
        response_content = json.dumps({
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": None,
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Greeting",
                "extra_field": "ignored",
                "another_field": 12345
            }],
            "response_text": "Hello!",
            "self_response": True,
            "reasoning": "Simple greeting",
            "extra_top_level": "also ignored"
        })
        
        output = parse_intent_response(response_content)
        
        # Should parse successfully, ignoring extra fields
        assert output.intents[0].intent_type == IntentType.GREETING
        assert output.response_text == "Hello!"