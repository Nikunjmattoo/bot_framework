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
    
    @pytest.mark.asyncio
    async def test_greeting_intent_self_respond(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Greeting intent → self-respond path"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Check result structure
        assert "text" in result
        assert "intents" in result
        assert "self_response" in result
        assert "token_usage" in result
        assert "latency_ms" in result
        assert "trace_id" in result
        
        # Check self-respond logic
        assert result["self_response"] is True
        assert result["text"] == "Hello! How can I help you today?"
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
    
    @pytest.mark.asyncio
    async def test_goodbye_intent_self_respond(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_goodbye,
        mock_cold_paths
    ):
        """✓ Goodbye intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Bye!"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_goodbye
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "Goodbye! Have a great day!"
        assert result["intents"][0]["intent_type"] == "goodbye"
    
    @pytest.mark.asyncio
    async def test_gratitude_intent_self_respond(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_gratitude,
        mock_cold_paths
    ):
        """✓ Gratitude intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Thanks!"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_gratitude
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert "You're welcome" in result["text"]
        assert result["intents"][0]["intent_type"] == "gratitude"
    
    @pytest.mark.asyncio
    async def test_chitchat_intent_self_respond(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_chitchat,
        mock_cold_paths
    ):
        """✓ Chitchat intent → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "How are you?"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_chitchat
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "I'm doing well, thank you for asking! How can I assist you?"
        assert result["intents"][0]["intent_type"] == "chitchat"
    
    @pytest.mark.asyncio
    async def test_multiple_self_respond_intents(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_multi_intent_self_respond,
        mock_cold_paths
    ):
        """✓ Multiple self-respond intents → self-respond path"""
        
        base_adapter_payload["message"]["content"] = "Thanks! Goodbye!"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_multi_intent_self_respond
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "You're welcome! Goodbye and have a great day!"
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "goodbye"
    
    @pytest.mark.asyncio
    async def test_self_respond_without_response_text_fallback(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        mock_cold_paths
    ):
        """✓ Self-respond without response_text → fallback message"""
        
        # Mock response with self_response=True but no text (should be caught by parser, but test fallback)
        mock_response = {
            "content": """{
                "intents": [{
                    "intent_type": "greeting",
                    "confidence": 0.98,
                    "entities": {},
                    "sequence_order": 1
                }],
                "response_text": null,
                "self_response": true,
                "reasoning": "No text provided"
            }""",
            "token_usage": {"prompt_tokens": 500, "completion_tokens": 50, "total": 550}
        }
        
        async def mock_llm_call(*args, **kwargs):
            return mock_response
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            # Parser should catch this and raise error
            with pytest.raises(IntentDetectionError):
                result = process_message(base_adapter_payload)


# ============================================================================
# SECTION 2: Brain-Required Path Tests
# ============================================================================

class TestBrainRequiredPath:
    """Test brain-required path (action, help, etc.)."""
    
    @pytest.mark.asyncio
    async def test_action_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_action,
        mock_cold_paths
    ):
        """✓ Action intent → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Check my order"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_action
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Check brain-required logic
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["canonical_intent"] == "check_order_status"
        
        # Since brain not implemented, should return placeholder
        assert "Brain processing not implemented yet" in result["text"]
    
    @pytest.mark.asyncio
    async def test_help_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_help,
        mock_cold_paths
    ):
        """✓ Help intent → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "I need help"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_help
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "help"
        assert "Brain processing not implemented yet" in result["text"]
    
    @pytest.mark.asyncio
    async def test_multiple_action_intents(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_multi_action,
        mock_cold_paths
    ):
        """✓ Multiple action intents → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Create profile and apply for job"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_multi_action
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert len(result["intents"]) == 2
        assert result["intents"][0]["canonical_intent"] == "create_profile"
        assert result["intents"][1]["canonical_intent"] == "apply_for_job"
    
    @pytest.mark.asyncio
    async def test_mixed_intents_brain_required(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_multi_intent_mixed,
        mock_cold_paths
    ):
        """✓ Mixed intents (self-respond + brain) → brain-required path"""
        
        base_adapter_payload["message"]["content"] = "Thanks, check my order"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_multi_intent_mixed
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Should go to brain because of action intent
        assert result["self_response"] is False
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "action"


# ============================================================================
# SECTION 3: Response Structure Tests
# ============================================================================

class TestResponseStructure:
    """Test response structure and metadata."""
    
    @pytest.mark.asyncio
    async def test_response_contains_all_required_fields(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Response contains all required fields"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
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
    
    @pytest.mark.asyncio
    async def test_trace_id_preserved_from_adapter(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ trace_id preserved from adapter payload"""
        
        original_trace_id = base_adapter_payload["trace_id"]
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert result["trace_id"] == original_trace_id
    
    @pytest.mark.asyncio
    async def test_trace_id_generated_if_missing(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ trace_id generated if missing from adapter"""
        
        # Remove trace_id
        del base_adapter_payload["trace_id"]
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Should have generated trace_id
        assert "trace_id" in result
        assert result["trace_id"] is not None
        assert len(result["trace_id"]) > 0
    
    @pytest.mark.asyncio
    async def test_token_usage_has_correct_structure(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ token_usage has correct structure"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert "token_usage" in result
        assert "prompt_tokens" in result["token_usage"]
        assert "completion_tokens" in result["token_usage"]
        assert "total" in result["token_usage"]
        
        # Check values are integers
        assert isinstance(result["token_usage"]["prompt_tokens"], int)
        assert isinstance(result["token_usage"]["completion_tokens"], int)
        assert isinstance(result["token_usage"]["total"], int)
    
    @pytest.mark.asyncio
    async def test_latency_ms_is_positive_number(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ latency_ms is positive number"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        assert "latency_ms" in result
        assert isinstance(result["latency_ms"], (int, float))
        assert result["latency_ms"] > 0
    
    @pytest.mark.asyncio
    async def test_intents_serialized_correctly(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_action,
        mock_cold_paths
    ):
        """✓ Intents serialized to dict correctly"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_action
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Check intent structure
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
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Missing trace_id generates new one with warning"""
        
        del base_adapter_payload["trace_id"]
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Should succeed with generated trace_id
        assert "trace_id" in result
    
    def test_missing_routing_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing routing raises ValidationError"""
        
        del base_adapter_payload["routing"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"
    
    def test_missing_message_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing message raises ValidationError"""
        
        del base_adapter_payload["message"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"
    
    def test_missing_session_id_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing session_id raises ValidationError"""
        
        del base_adapter_payload["session_id"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"
    
    def test_missing_template_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing template raises ValidationError"""
        
        del base_adapter_payload["template"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"
    
    def test_missing_token_plan_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing token_plan raises ValidationError"""
        
        del base_adapter_payload["token_plan"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"


# ============================================================================
# SECTION 5: Error Handling Tests
# ============================================================================

class TestOrchestratorErrorHandling:
    """Test orchestrator error handling."""
    
    @pytest.mark.asyncio
    async def test_intent_detection_error_propagates(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_invalid_json,
        mock_cold_paths
    ):
        """✓ IntentDetectionError propagates correctly"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_invalid_json
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            with pytest.raises(IntentDetectionError) as exc:
                process_message(base_adapter_payload)
            
            assert exc.value.error_code == "INVALID_JSON"
    
    @pytest.mark.asyncio
    async def test_llm_timeout_error_handling(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        mock_cold_paths
    ):
        """✓ LLM timeout handled correctly"""
        
        import asyncio
        
        async def mock_llm_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("LLM timeout")
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_timeout):
            with pytest.raises(IntentDetectionError):
                process_message(base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_database_error_handling(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        mock_cold_paths
    ):
        """✓ Database errors handled correctly"""
        
        # Mock DB fetch to raise error
        with patch('conversation_orchestrator.services.db_service.fetch_template_string') as mock_fetch:
            mock_fetch.side_effect = Exception("Database connection lost")
            
            with pytest.raises(Exception):
                process_message(base_adapter_payload)
    
    def test_validation_error_includes_details(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ ValidationError includes details"""
        
        del base_adapter_payload["routing"]
        
        with pytest.raises(ValidationError) as exc:
            process_message(base_adapter_payload)
        
        assert exc.value.error_code == "INVALID_ADAPTER_PAYLOAD"
        assert "routing" in str(exc.value).lower()


# ============================================================================
# SECTION 6: Edge Cases
# ============================================================================

class TestOrchestratorEdgeCases:
    """Test orchestrator edge cases."""
    
    @pytest.mark.asyncio
    async def test_empty_message_content(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Empty message content handled"""
        
        base_adapter_payload["message"]["content"] = ""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            # Should succeed or raise appropriate error
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_very_long_message_content(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Very long message content handled"""
        
        base_adapter_payload["message"]["content"] = "A" * 10000
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_unicode_message_content(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Unicode message content handled"""
        
        base_adapter_payload["message"]["content"] = "Hello 你好 مرحبا 🚀"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_fallback_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_low_confidence,
        mock_cold_paths
    ):
        """✓ Fallback intent goes to brain (not self-respond)"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_low_confidence
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Fallback should go to brain
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_clarification_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_single_low_confidence,
        mock_cold_paths
    ):
        """✓ Clarification intent goes to brain (not self-respond)"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_single_low_confidence
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = process_message(base_adapter_payload)
        
        # Clarification should go to brain
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "clarification"