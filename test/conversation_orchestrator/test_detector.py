"""
Unit tests for intent detection detector.

Tests:
- detect_intents() function
- Template fetching and filling
- Enrichment data fetching
- LLM integration (mocked)
- Cold path triggering
- Error handling
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone

from conversation_orchestrator.intent_detection.detector import detect_intents
from conversation_orchestrator.exceptions import IntentDetectionError
from conversation_orchestrator.schemas import EnrichedContext, Message, ActiveTask


# ============================================================================
# SECTION 1: Successful Intent Detection Tests
# ============================================================================

class TestDetectIntentsSuccess:
    """Test successful intent detection flow."""
    
    @pytest.mark.asyncio
    async def test_detect_greeting_intent_success(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Detect greeting intent successfully"""
        
        # Mock all async functions
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        assert "intents" in result
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
        assert result["self_response"] is True
        assert result["response_text"] == "Hello! How can I help you today?"
    
    @pytest.mark.asyncio
    async def test_detect_action_intent_success(
        self,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ Detect action intent successfully"""
        
        base_adapter_payload["message"]["content"] = "Check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["canonical_intent"] == "check_order_status"
        assert result["self_response"] is False
    
    @pytest.mark.asyncio
    async def test_detect_multiple_intents_success(
        self,
        base_adapter_payload,
        llm_response_multi_intent_mixed
    ):
        """✓ Detect multiple intents successfully"""
        
        base_adapter_payload["message"]["content"] = "Thanks, check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_multi_intent_mixed)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "action"
    
    @pytest.mark.asyncio
    async def test_token_usage_included(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Token usage included in result"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        assert "token_usage" in result
        assert "prompt_tokens" in result["token_usage"]
        assert "completion_tokens" in result["token_usage"]


# ============================================================================
# SECTION 2: Template Handling Tests
# ============================================================================

class TestTemplateHandling:
    """Test template fetching and filling."""
    
    @pytest.mark.asyncio
    async def test_template_fetched_from_db(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Template fetched from database"""
        
        mock_fetch = AsyncMock(return_value="System: {{user_message}}")
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', mock_fetch), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            await detect_intents(base_adapter_payload, "trace-123")
        
        mock_fetch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_missing_template_key_raises_error(
        self,
        base_adapter_payload
    ):
        """✓ Missing template key raises error"""
        
        # Remove template key
        base_adapter_payload["template"] = {}
        
        with pytest.raises(IntentDetectionError) as exc:
            await detect_intents(base_adapter_payload, "trace-123")
        
        assert exc.value.error_code == "MISSING_TEMPLATE_KEY"
    
    @pytest.mark.asyncio
    async def test_template_variables_filled_correctly(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Template variables filled correctly"""
        
        captured_prompt = []
        
        async def capture_llm_call(prompt, *args, **kwargs):
            captured_prompt.append(prompt)
            return llm_response_greeting
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Message: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=capture_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            await detect_intents(base_adapter_payload, "trace-123")
        
        assert len(captured_prompt) == 1
        assert "Hello" in captured_prompt[0]


# ============================================================================
# SECTION 3: Enrichment Data Tests
# ============================================================================

class TestEnrichmentData:
    """Test enrichment data fetching."""
    
    @pytest.mark.asyncio
    async def test_fetch_enrichment_data_success(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Enrichment data fetched successfully"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value="Session summary"), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        assert "intents" in result
    
    def test_build_template_variables_structure(self):
        """✓ Template variables have correct structure"""
        from conversation_orchestrator.intent_detection.detector import _build_template_variables
        from conversation_orchestrator.schemas import EnrichedContext
        
        enriched = EnrichedContext(
            session_summary="Summary",
            previous_messages=[],
            active_task=None,
            next_narrative=None
        )
        
        variables = _build_template_variables(
            user_message="Hello",
            user_id="user-123",
            session_id="session-123",
            user_type="verified",
            enriched=enriched
        )
        
        assert "user_message" in variables
        assert "user_id" in variables
        assert "session_id" in variables
        assert "user_type" in variables
    
    @pytest.mark.asyncio
    async def test_user_type_derived_from_policy(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ User type derived from policy"""
        
        base_adapter_payload["policy"]["auth_state"] = "guest"
        
        captured_variables = []
        
        async def capture_llm_call(prompt, *args, **kwargs):
            captured_variables.append(prompt)
            return llm_response_greeting
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Type: {{user_type}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=capture_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            await detect_intents(base_adapter_payload, "trace-123")
        
        assert "guest" in captured_variables[0]


# ============================================================================
# SECTION 4: Cold Path Trigger Tests
# ============================================================================

class TestColdPathTrigger:
    """Test cold path triggering."""
    
    @pytest.mark.asyncio
    async def test_cold_paths_triggered(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Cold paths triggered after detection"""
        
        mock_trigger = MagicMock()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths', mock_trigger):
            
            await detect_intents(base_adapter_payload, "trace-123")
        
        mock_trigger.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cold_paths_include_session_summary_generator(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Cold paths include session_summary_generator"""
        
        mock_trigger = MagicMock()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths', mock_trigger):
            
            await detect_intents(base_adapter_payload, "trace-123")
        
        call_kwargs = mock_trigger.call_args[1]
        assert "session_summary_generator" in call_kwargs["cold_paths"]


# ============================================================================
# SECTION 5: Error Handling Tests
# ============================================================================

class TestDetectorErrorHandling:
    """Test detector error handling."""
    
    @pytest.mark.asyncio
    async def test_llm_timeout_raises_error(
        self,
        base_adapter_payload
    ):
        """✓ LLM timeout raises IntentDetectionError"""
        
        import asyncio
        
        async def mock_timeout(*args, **kwargs):
            raise asyncio.TimeoutError("LLM timeout")
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_timeout), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(IntentDetectionError):
                await detect_intents(base_adapter_payload, "trace-123")
    
    @pytest.mark.asyncio
    async def test_invalid_llm_response_raises_error(
        self,
        base_adapter_payload,
        llm_response_invalid_json
    ):
        """✓ Invalid LLM response raises error"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_invalid_json)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(IntentDetectionError):
                await detect_intents(base_adapter_payload, "trace-123")
    
    @pytest.mark.asyncio
    async def test_missing_template_raises_error(
        self,
        base_adapter_payload
    ):
        """✓ Missing template raises error"""
        
        async def mock_missing(*args, **kwargs):
            raise Exception("Template not found")
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=mock_missing):
            with pytest.raises(IntentDetectionError):
                await detect_intents(base_adapter_payload, "trace-123")


# ============================================================================
# SECTION 6: Detector-Parser Integration Tests
# ============================================================================

class TestDetectorParserIntegration:
    """Test detector-parser integration."""
    
    @pytest.mark.asyncio
    async def test_low_confidence_intents_passed_through(
        self,
        base_adapter_payload,
        llm_response_low_confidence
    ):
        """✓ Low confidence intents passed through as unknown"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        # Should pass through low confidence intent
        assert len(result["intents"]) == 1
        assert result["intents"][0]["confidence"] == 0.45
    
    @pytest.mark.asyncio
    async def test_single_medium_confidence_passed_through(
        self,
        base_adapter_payload,
        llm_response_single_low_confidence
    ):
        """✓ Single medium confidence intent passed through (no conversion)"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_single_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await detect_intents(base_adapter_payload, "trace-123")
        
        # Should pass through as-is
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["confidence"] == 0.75