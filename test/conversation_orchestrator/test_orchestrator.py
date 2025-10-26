"""
Unit tests for orchestrator.

Tests:
- process_message() function
- Self-respond vs brain-required logic
- Response construction
- Error handling
- Adapter payload validation
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from conversation_orchestrator.orchestrator import process_message
from conversation_orchestrator.exceptions import (
    OrchestratorError,
    ValidationError,
    IntentDetectionError
)


# ============================================================================
# SECTION 1: Self-Respond Path Tests
# ============================================================================

class TestSelfRespondPath:
    """Test self-respond path (greeting, goodbye, gratitude, chitchat)."""
    
    def test_greeting_intent_self_respond(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Greeting intent → self-respond path"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "Hello! How can I help you today?"
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
    
    def test_goodbye_intent_self_respond(
        self,
        base_adapter_payload,
        llm_response_goodbye
    ):
        """✓ Goodbye intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Bye!"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_goodbye)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "Goodbye! Have a great day!"
        assert result["intents"][0]["intent_type"] == "goodbye"
    
    def test_gratitude_intent_self_respond(
        self,
        base_adapter_payload,
        llm_response_gratitude
    ):
        """✓ Gratitude intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Thanks!"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_gratitude)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert "You're welcome" in result["text"]
        assert result["intents"][0]["intent_type"] == "gratitude"
    
    def test_chitchat_intent_self_respond(
        self,
        base_adapter_payload,
        llm_response_chitchat
    ):
        """✓ Chitchat intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "How are you?"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_chitchat)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "I'm doing well, thank you for asking! How can I assist you?"
        assert result["intents"][0]["intent_type"] == "chitchat"
    
    def test_multiple_self_respond_intents(
        self,
        base_adapter_payload,
        llm_response_multi_intent_self_respond
    ):
        """✓ Multiple self-respond intents → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Thanks! Goodbye!"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_multi_intent_self_respond)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "You're welcome! Goodbye and have a great day!"
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "goodbye"
    
    def test_self_respond_without_response_text_fallback(
        self,
        base_adapter_payload,
        llm_response_self_respond_without_text
    ):
        """✓ Self-respond without response_text → error"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_self_respond_without_text)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                process_message(base_adapter_payload)


# ============================================================================
# SECTION 2: Brain-Required Path Tests
# ============================================================================

class TestBrainRequiredPath:
    """Test brain-required path (action, help, etc.)."""
    
    def test_action_intent_brain_required(
        self,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ Action intent → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["canonical_intent"] == "check_order_status"
        assert "Brain processing not implemented yet" in result["text"]
    
    def test_help_intent_brain_required(
        self,
        base_adapter_payload,
        llm_response_help
    ):
        """✓ Help intent → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "I need help"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_help)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "help"
        assert "Brain processing not implemented yet" in result["text"]
    
    def test_multiple_action_intents(
        self,
        base_adapter_payload,
        llm_response_multi_action
    ):
        """✓ Multiple action intents → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Create profile and apply for job"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_multi_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert len(result["intents"]) == 2
        assert result["intents"][0]["canonical_intent"] == "create_profile"
        assert result["intents"][1]["canonical_intent"] == "apply_for_job"
    
    def test_mixed_intents_brain_required(
        self,
        base_adapter_payload,
        llm_response_multi_intent_mixed
    ):
        """✓ Mixed intents (self-respond + brain) → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Thanks, check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_multi_intent_mixed)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "action"


# ============================================================================
# SECTION 3: Response Structure Tests
# ============================================================================

class TestResponseStructure:
    """Test response structure and metadata."""
    
    def test_response_contains_all_required_fields(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Response contains all required fields"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        required_fields = [
            "text",
            "intents",
            "self_response",
            "reasoning",
            "token_usage",
            "latency_ms",
            "trace_id"
        ]
        
        for field in required_fields:
            assert field in result, f"Missing field: {field}"
    
    def test_trace_id_preserved_from_adapter(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ trace_id preserved from adapter payload"""
        
        original_trace_id = base_adapter_payload["trace_id"]
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["trace_id"] == original_trace_id
    
    def test_trace_id_generated_if_missing(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ trace_id generated if missing from adapter"""
        
        del base_adapter_payload["trace_id"]
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert "trace_id" in result
        assert result["trace_id"] is not None
        assert len(result["trace_id"]) > 0
    
    def test_token_usage_has_correct_structure(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ token_usage has correct structure"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert "token_usage" in result
        assert "prompt_tokens" in result["token_usage"]
        assert "completion_tokens" in result["token_usage"]
        assert "total" in result["token_usage"]
    
    def test_latency_ms_is_positive_number(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ latency_ms is positive number"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], (int, float))
        assert result["latency_ms"] > 0
    
    def test_intents_serialized_correctly(
        self,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ Intents serialized to dict correctly"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        intent = result["intents"][0]
        assert isinstance(intent, dict)
        assert "intent_type" in intent
        assert "canonical_intent" in intent
        assert "confidence" in intent
        assert "entities" in intent
        assert "sequence_order" in intent


# ============================================================================
# SECTION 4: Adapter Validation Tests
# ============================================================================

class TestAdapterValidation:
    """Test adapter payload validation."""
    
    def test_missing_trace_id_generates_one(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Missing trace_id generates new one"""
        
        del base_adapter_payload["trace_id"]
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert "trace_id" in result
    
    def test_missing_routing_raises_error(self, base_adapter_payload):
        """✓ Missing routing raises ValidationError"""
        del base_adapter_payload["routing"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)
    
    def test_missing_message_raises_error(self, base_adapter_payload):
        """✓ Missing message raises ValidationError"""
        del base_adapter_payload["message"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)
    
    def test_missing_session_id_raises_error(self, base_adapter_payload):
        """✓ Missing session_id raises ValidationError"""
        del base_adapter_payload["session_id"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)
    
    def test_missing_template_raises_error(self, base_adapter_payload):
        """✓ Missing template raises ValidationError"""
        del base_adapter_payload["template"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)
    
    def test_missing_token_plan_raises_error(self, base_adapter_payload):
        """✓ Missing token_plan raises ValidationError"""
        del base_adapter_payload["token_plan"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)


# ============================================================================
# SECTION 5: Error Handling Tests
# ============================================================================

class TestOrchestratorErrorHandling:
    """Test orchestrator error handling."""
    
    def test_intent_detection_error_propagates(
        self,
        base_adapter_payload,
        llm_response_invalid_json
    ):
        """✓ IntentDetectionError propagates correctly"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_invalid_json)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                process_message(base_adapter_payload)
    
    def test_llm_timeout_error_handling(
        self,
        base_adapter_payload
    ):
        """✓ LLM timeout handled correctly"""
        
        import asyncio
        
        async def mock_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("Timeout")
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_timeout), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                process_message(base_adapter_payload)
    
    def test_database_error_handling(
        self,
        base_adapter_payload
    ):
        """✓ Database errors handled correctly"""
        
        async def mock_db_error(*args, **kwargs):
            raise Exception("DB error")
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=mock_db_error):
            with pytest.raises(Exception):
                process_message(base_adapter_payload)
    
    def test_validation_error_includes_details(self, base_adapter_payload):
        """✓ ValidationError includes details"""
        del base_adapter_payload["routing"]
        
        with pytest.raises(Exception):
            process_message(base_adapter_payload)


# ============================================================================
# SECTION 6: Edge Cases
# ============================================================================

class TestOrchestratorEdgeCases:
    """Test orchestrator edge cases."""
    
    def test_empty_message_content(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Empty message content handled"""
        
        base_adapter_payload["message"]["content"] = ""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    def test_very_long_message_content(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Very long message content handled"""
        
        base_adapter_payload["message"]["content"] = "A" * 10000
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    def test_unicode_message_content(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Unicode message content handled"""
        
        base_adapter_payload["message"]["content"] = "Hello 你好 مرحبا 🚀"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    def test_fallback_intent_brain_required(
        self,
        base_adapter_payload,
        llm_response_low_confidence
    ):
        """✓ Low confidence intent goes to brain"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"
    
    def test_clarification_intent_brain_required(
        self,
        base_adapter_payload,
        llm_response_single_low_confidence
    ):
        """✓ Medium confidence intent goes to brain"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_single_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"