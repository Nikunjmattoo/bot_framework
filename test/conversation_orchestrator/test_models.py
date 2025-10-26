"""
Unit tests for intent detection models.

Tests:
- IntentType enum
- SingleIntent validation
- IntentOutput validation
- Helper functions
- Confidence constants
"""

import pytest
from pydantic import ValidationError

from conversation_orchestrator.intent_detection.models import (
    IntentType,
    SingleIntent,
    IntentOutput,
    SELF_RESPOND_INTENTS,
    MIN_CONFIDENCE,
    CLARIFICATION_CONFIDENCE,
    requires_brain,
    get_action_intents,
    get_primary_intent,
    is_self_respond_only
)


# ============================================================================
# SECTION 1: IntentType Enum Tests
# ============================================================================

class TestIntentTypeEnum:
    """Test IntentType enum definition."""
    
    def test_all_10_intent_types_defined(self):
        """✓ All 10 intent types defined"""
        expected_types = {
            "greeting", "goodbye", "gratitude", "chitchat",
            "help", "fallback", "affirm", "deny", "clarification", "action"
        }
        actual_types = {intent.value for intent in IntentType}
        assert actual_types == expected_types, f"Expected {expected_types}, got {actual_types}"
    
    def test_self_respond_intents_correct(self):
        """✓ SELF_RESPOND_INTENTS contains exactly 4 types"""
        assert len(SELF_RESPOND_INTENTS) == 4
        expected = {
            IntentType.GREETING,
            IntentType.GOODBYE,
            IntentType.GRATITUDE,
            IntentType.CHITCHAT
        }
        assert SELF_RESPOND_INTENTS == expected
    
    def test_confidence_constants_have_correct_values(self):
        """✓ Confidence constants defined correctly"""
        assert MIN_CONFIDENCE == 0.7
        assert CLARIFICATION_CONFIDENCE == 0.85
    
    def test_intent_type_string_values(self):
        """✓ IntentType enum has correct string values"""
        assert IntentType.GREETING.value == "greeting"
        assert IntentType.GOODBYE.value == "goodbye"
        assert IntentType.ACTION.value == "action"
        assert IntentType.FALLBACK.value == "fallback"


# ============================================================================
# SECTION 2: SingleIntent Model Tests
# ============================================================================

class TestSingleIntentModel:
    """Test SingleIntent Pydantic model validation."""
    
    def test_valid_greeting_intent(self):
        """✓ Valid greeting intent created successfully"""
        intent = SingleIntent(
            intent_type=IntentType.GREETING,
            canonical_intent=None,
            confidence=0.95,
            entities={},
            sequence_order=1
        )
        assert intent.intent_type == IntentType.GREETING
        assert intent.canonical_intent is None
        assert intent.confidence == 0.95
        assert intent.entities == {}
        assert intent.sequence_order == 1
    
    def test_valid_action_intent_with_canonical(self):
        """✓ Valid action intent with canonical_intent"""
        intent = SingleIntent(
            intent_type=IntentType.ACTION,
            canonical_intent="check_order_status",
            confidence=0.92,
            entities={"order_id": "12345"},
            sequence_order=1
        )
        assert intent.intent_type == IntentType.ACTION
        assert intent.canonical_intent == "check_order_status"
        assert intent.entities == {"order_id": "12345"}
    
    def test_confidence_below_0_rejected(self):
        """✓ Confidence < 0.0 rejected"""
        with pytest.raises(ValidationError) as exc:
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=-0.1,
                entities={},
                sequence_order=1
            )
        assert "confidence" in str(exc.value).lower()
    
    def test_confidence_above_1_rejected(self):
        """✓ Confidence > 1.0 rejected"""
        with pytest.raises(ValidationError) as exc:
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=1.5,
                entities={},
                sequence_order=1
            )
        assert "confidence" in str(exc.value).lower()
    
    def test_confidence_at_0_accepted(self):
        """✓ Confidence = 0.0 accepted (edge case)"""
        intent = SingleIntent(
            intent_type=IntentType.FALLBACK,
            confidence=0.0,
            entities={},
            sequence_order=1
        )
        assert intent.confidence == 0.0
    
    def test_confidence_at_1_accepted(self):
        """✓ Confidence = 1.0 accepted (edge case)"""
        intent = SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=1.0,
            entities={},
            sequence_order=1
        )
        assert intent.confidence == 1.0
    
    def test_missing_intent_type_rejected(self):
        """✓ Missing intent_type rejected"""
        with pytest.raises(ValidationError):
            SingleIntent(
                confidence=0.9,
                entities={},
                sequence_order=1
            )
    
    def test_missing_confidence_rejected(self):
        """✓ Missing confidence rejected"""
        with pytest.raises(ValidationError):
            SingleIntent(
                intent_type=IntentType.GREETING,
                entities={},
                sequence_order=1
            )
    
    def test_entities_defaults_to_empty_dict(self):
        """✓ Entities defaults to empty dict if not provided"""
        intent = SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=0.9,
            sequence_order=1
        )
        assert intent.entities == {}
    
    def test_canonical_intent_optional_for_non_action(self):
        """✓ canonical_intent optional for non-action intents"""
        intent = SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=0.9,
            sequence_order=1
        )
        assert intent.canonical_intent is None
    
    def test_sequence_order_optional(self):
        """✓ sequence_order is optional"""
        intent = SingleIntent(
            intent_type=IntentType.GREETING,
            confidence=0.9
        )
        assert intent.sequence_order is None
    
    def test_dict_serialization(self):
        """✓ SingleIntent serializes to dict correctly"""
        intent = SingleIntent(
            intent_type=IntentType.ACTION,
            canonical_intent="check_order",
            confidence=0.95,
            entities={"order_id": "123"},
            sequence_order=1
        )
        intent_dict = intent.dict()
        assert intent_dict["intent_type"] == "action"
        assert intent_dict["canonical_intent"] == "check_order"
        assert intent_dict["confidence"] == 0.95
        assert intent_dict["entities"] == {"order_id": "123"}
        assert intent_dict["sequence_order"] == 1


# ============================================================================
# SECTION 3: IntentOutput Model Tests
# ============================================================================

class TestIntentOutputModel:
    """Test IntentOutput Pydantic model validation."""
    
    def test_valid_output_single_intent(self):
        """✓ Valid output with one intent"""
        output = IntentOutput(
            intents=[
                SingleIntent(
                    intent_type=IntentType.GREETING,
                    confidence=0.95,
                    entities={},
                    sequence_order=1
                )
            ],
            reasoning="User greeted",
            response_text="Hello!",
            self_response=True
        )
        assert len(output.intents) == 1
        assert output.self_response is True
        assert output.response_text == "Hello!"
    
    def test_valid_output_multiple_intents(self):
        """✓ Valid output with multiple intents"""
        output = IntentOutput(
            intents=[
                SingleIntent(
                    intent_type=IntentType.GRATITUDE,
                    confidence=0.97,
                    entities={},
                    sequence_order=1
                ),
                SingleIntent(
                    intent_type=IntentType.ACTION,
                    canonical_intent="check_order",
                    confidence=0.94,
                    entities={},
                    sequence_order=2
                )
            ],
            reasoning="Mixed intents",
            response_text=None,
            self_response=False
        )
        assert len(output.intents) == 2
        assert output.self_response is False
        assert output.response_text is None
    
    def test_empty_intents_list_rejected(self):
        """✓ Empty intents list rejected"""
        with pytest.raises(ValidationError) as exc:
            IntentOutput(
                intents=[],
                reasoning="No intents"
            )
        assert "intents" in str(exc.value).lower()
    
    def test_reasoning_optional(self):
        """✓ reasoning is optional"""
        output = IntentOutput(
            intents=[
                SingleIntent(
                    intent_type=IntentType.GREETING,
                    confidence=0.95,
                    entities={},
                    sequence_order=1
                )
            ]
        )
        assert output.reasoning is None
    
    def test_response_text_optional(self):
        """✓ response_text is optional"""
        output = IntentOutput(
            intents=[
                SingleIntent(
                    intent_type=IntentType.ACTION,
                    canonical_intent="check_order",
                    confidence=0.95,
                    entities={},
                    sequence_order=1
                )
            ],
            self_response=False
        )
        assert output.response_text is None
    
    def test_self_response_defaults_to_false(self):
        """✓ self_response defaults to False"""
        output = IntentOutput(
            intents=[
                SingleIntent(
                    intent_type=IntentType.ACTION,
                    canonical_intent="check_order",
                    confidence=0.95,
                    entities={},
                    sequence_order=1
                )
            ]
        )
        assert output.self_response is False


# ============================================================================
# SECTION 4: Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions in models module."""
    
    # requires_brain() tests
    
    def test_requires_brain_with_action_intent(self):
        """✓ requires_brain returns True for action intent"""
        intents = [
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=1
            )
        ]
        assert requires_brain(intents) is True
    
    def test_requires_brain_with_greeting_intent(self):
        """✓ requires_brain returns False for greeting intent"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.95,
                entities={},
                sequence_order=1
            )
        ]
        assert requires_brain(intents) is False
    
    def test_requires_brain_with_mixed_intents(self):
        """✓ requires_brain returns True if any intent requires brain"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GRATITUDE,
                confidence=0.97,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.94,
                entities={},
                sequence_order=2
            )
        ]
        assert requires_brain(intents) is True
    
    def test_requires_brain_with_empty_list(self):
        """✓ requires_brain returns False for empty list"""
        assert requires_brain([]) is False
    
    # get_action_intents() tests
    
    def test_get_action_intents_filters_correctly(self):
        """✓ get_action_intents returns only action intents"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=2
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="create_profile",
                confidence=0.93,
                entities={},
                sequence_order=3
            )
        ]
        action_intents = get_action_intents(intents)
        assert len(action_intents) == 2
        assert all(i.intent_type == IntentType.ACTION for i in action_intents)
    
    def test_get_action_intents_empty_if_no_actions(self):
        """✓ get_action_intents returns empty list if no actions"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            )
        ]
        action_intents = get_action_intents(intents)
        assert action_intents == []
    
    # get_primary_intent() tests
    
    def test_get_primary_intent_returns_action_if_present(self):
        """✓ get_primary_intent prioritizes action intent"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=2
            )
        ]
        primary = get_primary_intent(intents)
        assert primary.intent_type == IntentType.ACTION
    
    def test_get_primary_intent_returns_first_if_no_action(self):
        """✓ get_primary_intent returns first intent if no action"""
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
        primary = get_primary_intent(intents)
        assert primary.intent_type == IntentType.GREETING
    
    def test_get_primary_intent_returns_none_for_empty_list(self):
        """✓ get_primary_intent returns None for empty list"""
        assert get_primary_intent([]) is None
    
    # is_self_respond_only() tests
    
    def test_is_self_respond_only_true_for_all_self_respond(self):
        """✓ is_self_respond_only returns True if all intents are self-respond"""
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
        assert is_self_respond_only(intents) is True
    
    def test_is_self_respond_only_false_if_any_brain_required(self):
        """✓ is_self_respond_only returns False if any intent requires brain"""
        intents = [
            SingleIntent(
                intent_type=IntentType.GREETING,
                confidence=0.98,
                entities={},
                sequence_order=1
            ),
            SingleIntent(
                intent_type=IntentType.ACTION,
                canonical_intent="check_order",
                confidence=0.95,
                entities={},
                sequence_order=2
            )
        ]
        assert is_self_respond_only(intents) is False
    
    def test_is_self_respond_only_false_for_empty_list(self):
        """✓ is_self_respond_only returns False for empty list"""
        assert is_self_respond_only([]) is False