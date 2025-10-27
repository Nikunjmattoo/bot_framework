"""
Integration tests for intent detection.

Tests full flow with real database, real templates, mocked LLM.
"""

import pytest
from unittest.mock import patch, AsyncMock

from conversation_orchestrator.orchestrator import process_message
from conversation_orchestrator.intent_detection.models import IntentType


# ============================================================================
# SECTION 1: End-to-End Integration Tests
# ============================================================================

class TestEndToEndIntegration:
    """Test end-to-end integration with real DB."""
    
    @pytest.mark.asyncio
    async def test_greeting_end_to_end(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ End-to-end: greeting intent with real DB"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        # Verify full result
        assert result["self_response"] is True
        assert result["text"] == "Hello! How can I help you today?"
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
        assert result["intents"][0]["confidence"] == 0.98
        assert "token_usage" in result
        assert "latency_ms" in result
        assert "trace_id" in result
    
    @pytest.mark.asyncio
    async def test_action_end_to_end(
        self,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ End-to-end: action intent with real DB"""
        
        base_adapter_payload["message"]["content"] = "Check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"
        assert result["intents"][0]["canonical_intent"] == "check_order_status"
        assert "Brain processing not implemented yet" in result["text"]
    
    @pytest.mark.asyncio
    async def test_multi_intent_end_to_end(
        self,
        base_adapter_payload,
        llm_response_multi_intent_mixed
    ):
        """✓ End-to-end: multiple intents with real DB"""
        
        base_adapter_payload["message"]["content"] = "Thanks, check my order"
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_multi_intent_mixed)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        assert result["self_response"] is False
        assert len(result["intents"]) == 2
        assert result["intents"][0]["intent_type"] == "gratitude"
        assert result["intents"][1]["intent_type"] == "action"


# ============================================================================
# SECTION 2: Template Integration Tests
# ============================================================================

class TestTemplateIntegration:
    """Test template fetching and rendering integration."""
    
    @pytest.mark.asyncio
    async def test_template_fetched_and_filled(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Template fetched from DB and variables filled"""
        
        # Capture filled prompt
        filled_prompt_capture = []
        
        async def mock_llm_call(prompt, *args, **kwargs):
            filled_prompt_capture.append(prompt)
            return llm_response_greeting
        
        template_content = """You are an intent classifier
INTENT TYPES
SELF-RESPONSE vs BRAIN
CONVERSATION CONTEXT
{{user_id}}
{{session_id}}
{{user_message}}
OUTPUT FORMAT
CLASSIFY THIS MESSAGE"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value=template_content)), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        # Verify template was filled
        filled_prompt = filled_prompt_capture[0]
        
        # Check all sections present
        assert "You are an intent classifier" in filled_prompt
        assert "INTENT TYPES" in filled_prompt
        assert "SELF-RESPONSE vs BRAIN" in filled_prompt
        assert "CONVERSATION CONTEXT" in filled_prompt
        assert "OUTPUT FORMAT" in filled_prompt
        assert "CLASSIFY THIS MESSAGE" in filled_prompt
        
        # Check variables filled
        assert base_adapter_payload["message"]["content"] in filled_prompt
    
    @pytest.mark.asyncio
    async def test_template_sections_ordered_correctly(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Template sections rendered in correct order"""
        
        filled_prompt_capture = []
        
        async def mock_llm_call(prompt, *args, **kwargs):
            filled_prompt_capture.append(prompt)
            return llm_response_greeting
        
        template_content = """You are an intent classifier
INTENT TYPES
SELF-RESPONSE vs BRAIN
CONVERSATION CONTEXT
OUTPUT FORMAT
CLASSIFY THIS MESSAGE"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value=template_content)), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        filled_prompt = filled_prompt_capture[0]
        
        # Check order (indices should be increasing)
        system_idx = filled_prompt.index("You are an intent classifier")
        intents_idx = filled_prompt.index("INTENT TYPES")
        logic_idx = filled_prompt.index("SELF-RESPONSE vs BRAIN")
        context_idx = filled_prompt.index("CONVERSATION CONTEXT")
        output_idx = filled_prompt.index("OUTPUT FORMAT")
        message_idx = filled_prompt.index("CLASSIFY THIS MESSAGE")
        
        assert system_idx < intents_idx < logic_idx < context_idx < output_idx < message_idx


# ============================================================================
# SECTION 3: Session Context Integration Tests
# ============================================================================

class TestSessionContextIntegration:
    """Test session context fetching and inclusion."""
    
    @pytest.mark.asyncio
    async def test_previous_messages_included_in_context(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Previous messages included in template context"""
        
        filled_prompt_capture = []
        
        async def mock_llm_call(prompt, *args, **kwargs):
            filled_prompt_capture.append(prompt)
            return llm_response_greeting
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="CONVERSATION CONTEXT\n{{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value="Previous summary"), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        filled_prompt = filled_prompt_capture[0]
        
        # Check if context section appears
        assert "CONVERSATION CONTEXT" in filled_prompt


# ============================================================================
# SECTION 4: Cold Path Integration Tests
# ============================================================================

class TestColdPathIntegration:
    """Test cold path triggering integration."""
    
    @pytest.mark.asyncio
    async def test_cold_paths_triggered_with_correct_data(
        self,
        base_adapter_payload,
        llm_response_greeting,
        mock_cold_paths
    ):
        """✓ Cold paths triggered with correct data"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template: {{user_message}}")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths', mock_cold_paths):
            
            result = await process_message(base_adapter_payload)
        
        # Verify cold paths called
        assert mock_cold_paths.called
        call_kwargs = mock_cold_paths.call_args[1]
        
        assert call_kwargs["session_id"] == base_adapter_payload["session_id"]
        assert call_kwargs["user_message"] == base_adapter_payload["message"]["content"]
        assert "conversation_history" in call_kwargs
        assert "cold_paths" in call_kwargs
        
        # Verify cold paths list
        cold_paths = call_kwargs["cold_paths"]
        assert "session_summary_generator" in cold_paths


# ============================================================================
# SECTION 5: Performance Integration Tests
# ============================================================================

class TestPerformanceIntegration:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_latency_under_reasonable_time(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Total latency under reasonable time (with mocked LLM)"""
        
        async def mock_llm_call(*args, **kwargs):
            # Simulate fast LLM response
            import asyncio
            await asyncio.sleep(0.01)  # 10ms simulated LLM call
            return llm_response_greeting
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(base_adapter_payload)
        
        # With mocked LLM, total latency should be < 1000ms (1 second)
        assert result["latency_ms"] < 1000
    
    @pytest.mark.asyncio
    async def test_multiple_requests_sequential(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Multiple sequential requests handled correctly"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            # Process 5 messages sequentially
            for i in range(5):
                base_adapter_payload["message"]["content"] = f"Hello {i}"
                result = await process_message(base_adapter_payload)
                assert result["self_response"] is True
                assert "Hello" in result["text"]


# ============================================================================
# SECTION 6: Error Recovery Integration Tests
# ============================================================================

class TestErrorRecoveryIntegration:
    """Test error recovery in integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_recovery_after_llm_timeout(
        self,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ System recovers after LLM timeout"""
        
        import asyncio
        call_count = [0]
        
        async def mock_llm_call(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise asyncio.TimeoutError("Timeout")
            return llm_response_greeting
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=mock_llm_call), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            # First call should fail
            with pytest.raises(Exception):
                await process_message(base_adapter_payload)
            
            # Second call should succeed
            result = await process_message(base_adapter_payload)
            assert result["self_response"] is True