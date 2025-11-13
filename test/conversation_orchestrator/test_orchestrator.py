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
import asyncio
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

            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "Hello! How can I help you today?"
        assert len(result["intents"]) == 1
        assert result["intents"][0]["intent_type"] == "greeting"
    
    @pytest.mark.asyncio
    async def test_goodbye_intent_self_respond(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "Goodbye! Have a great day!"
        assert result["intents"][0]["intent_type"] == "goodbye"
    
    @pytest.mark.asyncio
    async def test_gratitude_intent_self_respond(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is True
        assert "You're welcome" in result["text"]
        assert result["intents"][0]["intent_type"] == "gratitude"
    
    @pytest.mark.asyncio
    async def test_chitchat_intent_self_respond(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is True
        assert result["text"] == "I'm doing well, thank you for asking! How can I assist you?"
        assert result["intents"][0]["intent_type"] == "chitchat"
    
    @pytest.mark.asyncio
    async def test_multiple_self_respond_intents(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is True
        assert len(result["intents"]) == 2
    
    @pytest.mark.asyncio
    async def test_self_respond_response_in_result(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Self-respond response included in result"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert "text" in result
        assert result["text"] is not None


# ============================================================================
# SECTION 2: Brain-Required Path Tests
# ============================================================================

class TestBrainRequiredPath:
    """Test brain-required path (help, fallback, affirm, deny, clarification, action)."""
    
    @pytest.mark.asyncio
    async def test_action_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ Action intent → brain-required path"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()  # Just flush, don't commit
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain') as mock_brain:
            
            mock_brain.return_value = {
                'text': 'Brain processed action',
                'status': 'completed'
            }
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["text"] == "Brain processed action"
        assert mock_brain.called
    
    @pytest.mark.asyncio
    async def test_help_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        llm_response_help
    ):
        """✓ Help intent → brain-required path"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_help)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain') as mock_brain:
            
            mock_brain.return_value = {
                'text': 'Brain processed help',
                'status': 'completed'
            }
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is False
    
    @pytest.mark.asyncio
    async def test_fallback_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        llm_response_fallback
    ):
        """✓ Fallback intent → brain-required path"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_fallback)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain') as mock_brain:
            
            mock_brain.return_value = {
                'text': 'Brain processed fallback',
                'status': 'completed'
            }
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is False
    
    @pytest.mark.asyncio
    async def test_brain_required_calls_brain(
        self,
        db_session,
        base_adapter_payload,
        llm_response_action
    ):
        """✓ Brain-required path calls brain processor"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_action)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain') as mock_brain:
            
            mock_brain.return_value = {
                'text': 'Brain response',
                'status': 'completed'
            }
            
            await process_message(db_session, base_adapter_payload)
            
            assert mock_brain.called


# ============================================================================
# SECTION 3: Response Structure Tests
# ============================================================================

class TestResponseStructure:
    """Test response structure validation."""
    
    @pytest.mark.asyncio
    async def test_response_contains_required_fields(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Response contains required fields"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert "text" in result
        assert "self_response" in result
        assert "intents" in result
    
    @pytest.mark.asyncio
    async def test_intents_is_list(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Intents is a list"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert isinstance(result["intents"], list)
    
    @pytest.mark.asyncio
    async def test_self_response_is_boolean(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ self_response is boolean"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert isinstance(result["self_response"], bool)
    
    @pytest.mark.asyncio
    async def test_text_is_string(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ text is string"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert isinstance(result["text"], str)
    
    @pytest.mark.asyncio
    async def test_intent_objects_have_required_fields(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Intent objects have required fields"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        for intent in result["intents"]:
            assert "intent_type" in intent
            assert "confidence" in intent
    
    @pytest.mark.asyncio
    async def test_confidence_is_float(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Confidence is float"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
        
        for intent in result["intents"]:
            assert isinstance(intent["confidence"], float)


# ============================================================================
# SECTION 4: Adapter Validation Tests
# ============================================================================

class TestAdapterValidation:
    """Test adapter payload validation."""
    
    @pytest.mark.asyncio
    async def test_missing_session_id_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing session_id raises ValidationError"""
        del base_adapter_payload["session_id"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_missing_message_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing message raises ValidationError"""
        del base_adapter_payload["message"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_missing_routing_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing routing raises ValidationError"""
        del base_adapter_payload["routing"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_invalid_message_content_handled(
        self,
        db_session,
        base_adapter_payload,
        llm_response_greeting
    ):
        """✓ Invalid message content handled gracefully"""
        base_adapter_payload["message"]["content"] = None
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_greeting)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            result = await process_message(db_session, base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_missing_llm_runtime_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing llm_runtime raises ValidationError"""
        del base_adapter_payload["llm_runtime"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_missing_template_config_raises_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ Missing template raises ValidationError"""
        del base_adapter_payload["template"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)


# ============================================================================
# SECTION 5: Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test error handling in orchestrator."""
    
    @pytest.mark.asyncio
    async def test_llm_error_raises_intent_detection_error(
        self,
        db_session,
        base_adapter_payload
    ):
        """✓ LLM error raises IntentDetectionError"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(side_effect=Exception("LLM error"))), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_invalid_json_response_handled(
        self,
        db_session,
        base_adapter_payload,
        llm_response_invalid_json
    ):
        """✓ Invalid JSON response handled"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_invalid_json)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_missing_intents_in_response_handled(
        self,
        db_session,
        base_adapter_payload,
        llm_response_missing_intents
    ):
        """✓ Missing intents in response handled"""
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_missing_intents)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'):
            
            with pytest.raises(Exception):
                await process_message(db_session, base_adapter_payload)
    
    @pytest.mark.asyncio
    async def test_validation_error_includes_details(self,
        db_session, base_adapter_payload):
        """✓ ValidationError includes details"""
        del base_adapter_payload["routing"]
        
        with pytest.raises(Exception):
            await process_message(db_session, base_adapter_payload)


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
            
            result = await process_message(db_session, base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_very_long_message_content(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_unicode_message_content(
        self,
        db_session,
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
            
            result = await process_message(db_session, base_adapter_payload)
            assert "text" in result
    
    @pytest.mark.asyncio
    async def test_unknown_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        llm_response_low_confidence
    ):
        """✓ Unknown intent goes to brain"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain', new=AsyncMock(return_value={"text": "Processing unknown intent"})) as mock_brain:
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"
    
    @pytest.mark.asyncio
    async def test_response_intent_brain_required(
        self,
        db_session,
        base_adapter_payload,
        llm_response_single_low_confidence
    ):
        """✓ Medium confidence intent goes to brain"""
        # Check if session exists, create only if needed
        from db.models.sessions import SessionModel
        existing = db_session.query(SessionModel).filter_by(
            id=base_adapter_payload["session_id"]
        ).first()
        
        if not existing:
            session = SessionModel(
                id=base_adapter_payload["session_id"],
                user_id=base_adapter_payload["message"]["sender_user_id"],
                instance_id=base_adapter_payload["routing"]["instance_id"]
            )
            session.initialize_default_state()
            db_session.add(session)
            db_session.flush()
        
        with patch('conversation_orchestrator.intent_detection.detector.fetch_template_string', new=AsyncMock(return_value="Template")), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_session_summary', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_previous_messages', return_value=[]), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_active_task', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.fetch_next_narrative', return_value=None), \
             patch('conversation_orchestrator.intent_detection.detector.call_llm_async', new=AsyncMock(return_value=llm_response_single_low_confidence)), \
             patch('conversation_orchestrator.intent_detection.detector.trigger_cold_paths'), \
             patch('conversation_orchestrator.brain.process_brain', new=AsyncMock(return_value={"text": "Processing medium confidence intent"})) as mock_brain:
            
            result = await process_message(db_session, base_adapter_payload)
        
        assert result["self_response"] is False
        assert result["intents"][0]["intent_type"] == "action"