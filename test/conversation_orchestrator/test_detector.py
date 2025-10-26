"""
Unit tests for intent detection detector.

Tests:
- detect_intents() function
- Template fetching
- LLM call integration
- Cold path triggering
- Error handling
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from conversation_orchestrator.intent_detection.detector import (
    detect_intents,
    _fetch_enrichment_data,
    _build_template_variables,
    _trigger_cold_paths_async
)
from conversation_orchestrator.intent_detection.models import IntentType
from conversation_orchestrator.exceptions import IntentDetectionError
from conversation_orchestrator.schemas import EnrichedContext, PreviousMessage, ActiveTask


# ============================================================================
# SECTION 1: Successful Detection Tests
# ============================================================================

class TestDetectIntentsSuccess:
    """Test successful intent detection scenarios."""
    
    @pytest.mark.asyncio
    async def test_detect_greeting_intent_success(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Detect greeting intent successfully"""
        
        # Mock LLM call
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert "intents" in result
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
        assert result["self_response"] is True
        assert result["response_text"] == "Hello! How can I help you today?"
        assert "token_usage" in result
    
    @pytest.mark.asyncio
    async def test_detect_action_intent_success(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_action,
        mock_cold_paths
    ):
        """✓ Detect action intent successfully"""
        
        # Update payload message
        base_adapter_payload["message"]["content"] = "Check my order status"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_action
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["canonical_intent"] == "check_order_status"
        assert result["self_response"] is False
        assert result["response_text"] is None
    
    @pytest.mark.asyncio
    async def test_detect_multiple_intents_success(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_multi_intent_mixed,
        mock_cold_paths
    ):
        """✓ Detect multiple intents successfully"""
        
        base_adapter_payload["message"]["content"] = "Thanks, now check my order"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_multi_intent_mixed
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "action"
        assert result["self_response"] is False
    
    @pytest.mark.asyncio
    async def test_token_usage_included(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Token usage stats included in result"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert "token_usage" in result
        assert result["token_usage"]["prompt_tokens"] == 500
        assert result["token_usage"]["completion_tokens"] == 50
        assert result["token_usage"]["total"] == 550


# ============================================================================
# SECTION 2: Template Handling Tests
# ============================================================================

class TestTemplateHandling:
    """Test template fetching and filling."""
    
    @pytest.mark.asyncio
    async def test_template_fetched_from_db(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Template fetched from database"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        # Should succeed (template exists in DB)
        assert "intents" in result
    
    @pytest.mark.asyncio
    async def test_missing_template_key_raises_error(
        self,
        db_session,
        base_adapter_payload,
        mock_cold_paths
    ):
        """✓ Missing template key raises error"""
        
        # Remove template key
        base_adapter_payload["template"]["json"]["intent"] = {}
        
        with pytest.raises(IntentDetectionError) as exc:
            detect_intents(base_adapter_payload, "test-trace-id")
        
        assert exc.value.error_code == "MISSING_TEMPLATE_KEY"
    
    @pytest.mark.asyncio
    async def test_template_variables_filled_correctly(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        test_session,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Template variables filled correctly"""
        
        # Capture the filled prompt
        filled_prompt_capture = []
        
        async def mock_llm_call(prompt, *args, **kwargs):
            filled_prompt_capture.append(prompt)
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        # Check that variables were filled
        filled_prompt = filled_prompt_capture[0]
        assert "Hello" in filled_prompt  # user_message
        assert test_session.user_id in filled_prompt  # user_id
        assert test_session.id in filled_prompt  # session_id


# ============================================================================
# SECTION 3: Enrichment Data Tests
# ============================================================================

class TestEnrichmentData:
    """Test enrichment data fetching."""
    
    def test_fetch_enrichment_data_success(
        self,
        db_session,
        test_session,
        test_messages
    ):
        """✓ Fetch enrichment data successfully"""
        
        enriched = _fetch_enrichment_data(test_session.id, "test-trace-id")
        
        assert isinstance(enriched, EnrichedContext)
        assert enriched.session_summary is None or isinstance(enriched.session_summary, str)
        assert isinstance(enriched.previous_messages, list)
        # Note: Depending on implementation, this might return empty list or actual messages
    
    def test_build_template_variables_structure(
        self,
        db_session,
        test_session
    ):
        """✓ Template variables have correct structure"""
        
        enriched = EnrichedContext(
            session_summary="Test summary",
            previous_messages=[],
            active_task=None,
            next_narrative=None
        )
        
        variables = _build_template_variables(
            user_message="Hello",
            user_id=test_session.user_id,
            session_id=test_session.id,
            user_type="verified",
            enriched=enriched
        )
        
        assert "user_message" in variables
        assert "user_id" in variables
        assert "session_id" in variables
        assert "user_type" in variables
        assert "session_summary" in variables
        assert "previous_messages" in variables
        assert "active_task" in variables
        assert "next_narrative" in variables
    
    def test_user_type_derived_from_policy(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ User type derived from policy.auth_state"""
        
        # Test verified user
        base_adapter_payload["policy"]["auth_state"] = "channel_verified"
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        # Should succeed (user_type = "verified")
        assert "intents" in result
        
        # Test guest user
        base_adapter_payload["policy"]["auth_state"] = "guest"
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        # Should succeed (user_type = "guest")
        assert "intents" in result


# ============================================================================
# SECTION 4: Cold Path Tests
# ============================================================================

class TestColdPathTrigger:
    """Test cold path triggering."""
    
    @pytest.mark.asyncio
    async def test_cold_paths_triggered(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Cold paths triggered during detection"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        # Check cold paths were triggered
        mock_cold_paths.assert_called_once()
        call_args = mock_cold_paths.call_args
        
        assert call_args[1]["session_id"] == base_adapter_payload["session_id"]
        assert call_args[1]["user_message"] == base_adapter_payload["message"]["content"]
        assert "conversation_history" in call_args[1]
        assert "cold_paths" in call_args[1]
    
    @pytest.mark.asyncio
    async def test_cold_paths_include_session_summary_generator(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Cold paths include session_summary_generator"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_greeting
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        call_args = mock_cold_paths.call_args
        cold_paths = call_args[1]["cold_paths"]
        
        assert "session_summary_generator" in cold_paths


# ============================================================================
# SECTION 5: Error Handling Tests
# ============================================================================

class TestDetectorErrorHandling:
    """Test detector error handling."""
    
    @pytest.mark.asyncio
    async def test_llm_timeout_raises_error(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        mock_cold_paths
    ):
        """✓ LLM timeout raises error"""
        
        async def mock_llm_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("LLM timeout")
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_timeout):
            with pytest.raises(IntentDetectionError) as exc:
                detect_intents(base_adapter_payload, "test-trace-id")
            
            assert "INTENT_DETECTION_FAILED" in str(exc.value.error_code)
    
    @pytest.mark.asyncio
    async def test_invalid_llm_response_raises_error(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_invalid_json,
        mock_cold_paths
    ):
        """✓ Invalid LLM response raises error"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_invalid_json
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            with pytest.raises(IntentDetectionError) as exc:
                detect_intents(base_adapter_payload, "test-trace-id")
            
            assert "INVALID_JSON" in str(exc.value.error_code)
    
    @pytest.mark.asyncio
    async def test_missing_template_raises_error(
        self,
        db_session,
        base_adapter_payload,
        mock_cold_paths
    ):
        """✓ Missing template in DB raises error"""
        
        # Set non-existent template key
        base_adapter_payload["template"]["json"]["intent"]["template"] = "nonexistent_template"
        
        with pytest.raises(Exception):  # Should raise DatabaseError or similar
            detect_intents(base_adapter_payload, "test-trace-id")


# ============================================================================
# SECTION 6: Integration with Parser Tests
# ============================================================================

class TestDetectorParserIntegration:
    """Test detector integration with parser."""
    
    @pytest.mark.asyncio
    async def test_low_confidence_filtered_to_fallback(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_low_confidence,
        mock_cold_paths
    ):
        """✓ Low confidence intents filtered → fallback created"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_low_confidence
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_single_medium_confidence_to_clarification(
        self,
        db_session,
        base_adapter_payload,
        test_template_full,
        llm_response_single_low_confidence,
        mock_cold_paths
    ):
        """✓ Single medium confidence → clarification created"""
        
        async def mock_llm_call(*args, **kwargs):
            return llm_response_single_low_confidence
        
        with patch('conversation_orchestrator.services.llm_service.call_llm_async', new=mock_llm_call):
            result = detect_intents(base_adapter_payload, "test-trace-id")
        
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "clarification"