# ============================================================================
# FILE: test/message_handler_core/test_processor.py
# Tests for message_handler/core/processor.py (Section B2)
# ============================================================================

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from decimal import Decimal

from message_handler.core.processor import (
    process_core,
    validate_content_length,
    validate_orchestrator_response,
    extract_token_usage,
    DEFAULT_RESPONSE_TEXT
)
from message_handler.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    DatabaseError,
    OrchestrationError,
    ErrorCode
)


# ============================================================================
# SECTION B2.1: Input Validation Tests
# ============================================================================

class TestProcessCoreInputValidation:
    """Test input validation in process_core."""
    
    def test_missing_content_raises_validation_error(self, db_session, test_user, test_instance, test_session):
        """✓ Missing content → ValidationError"""
        # Get real config from database
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        # Setup user context with REAL objects
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        with pytest.raises(ValidationError) as exc_info:
            process_core(
                db=db_session,
                content="",  # Empty
                instance_id=str(test_instance.id),
                user=test_user
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_content_exceeds_max_length_raises_validation_error(self, db_session, test_user, test_instance, test_session):
        """✓ Content > 10000 → ValidationError"""
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            process_core(
                db=db_session,
                content=long_content,
                instance_id=str(test_instance.id),
                user=test_user
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_missing_user_raises_validation_error(self, db_session, test_instance):
        """✓ Missing user → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            process_core(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user=None  # Missing
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "user" in str(exc_info.value).lower()
    
    def test_missing_session_raises_resource_not_found(self, db_session, test_user, test_instance):
        """✓ Missing session → ResourceNotFoundError"""
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = None  # No session
        test_user.instance = test_instance
        test_user.instance_config = config
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            process_core(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user=test_user
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "session" in str(exc_info.value).lower()
    
    def test_missing_instance_raises_resource_not_found(self, db_session, test_user, test_session):
        """✓ Missing instance → ResourceNotFoundError"""
        from db.models.instance_configs import InstanceConfigModel
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = None  # No instance
        test_user.instance_config = None
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            process_core(
                db=db_session,
                content="Test",
                instance_id=str(uuid.uuid4()),
                user=test_user
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "instance" in str(exc_info.value).lower()
    
    def test_missing_config_raises_resource_not_found(self, db_session, test_user, test_instance, test_session):
        """✓ Missing config → ResourceNotFoundError"""
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = None  # No config
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            process_core(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user=test_user
            )
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
        assert "config" in str(exc_info.value).lower()


# ============================================================================
# SECTION B2.2: Message Saving Tests
# ============================================================================

class TestProcessCoreMessageSaving:
    """Test message saving in process_core."""
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_inbound_message_saved_with_request_id(
        self, mock_langfuse, mock_orchestrator, 
        db_session, test_session, test_user, test_instance
    ):
        """✓ Inbound message saved with request_id"""
        # Setup mocks for external services
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        # Get real config
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        # Setup user context with REAL objects
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        request_id = str(uuid.uuid4())
        
        result = process_core(
            db=db_session,
            content="Test message",
            instance_id=str(test_instance.id),
            user=test_user,
            request_id=request_id
        )
        
        # Check inbound message saved
        from db.models.messages import MessageModel
        inbound_msg = db_session.query(MessageModel).filter(
            MessageModel.session_id == test_session.id,
            MessageModel.role == "user",
            MessageModel.request_id == request_id
        ).first()
        
        assert inbound_msg is not None
        assert inbound_msg.content == "Test message"
        assert inbound_msg.request_id == request_id
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_message_metadata_includes_channel(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Message metadata includes channel"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user,
            channel="whatsapp"
        )
        
        from db.models.messages import MessageModel
        message = db_session.query(MessageModel).filter(
            MessageModel.session_id == test_session.id,
            MessageModel.role == "user"
        ).first()
        
        assert message.metadata_json is not None
        assert message.metadata_json.get("channel") == "whatsapp"
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    @pytest.mark.skip(reason="PII detector module not implemented yet - will be built as proper policy runner")
    def test_message_metadata_sanitized(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Message metadata sanitized"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        meta_info = {
            "channel": "api",
            "password": "secret123",  # Should be stripped
            "auth_token": "xyz"  # Should be stripped
        }
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user,
            meta_info=meta_info
        )
        
        from db.models.messages import MessageModel
        message = db_session.query(MessageModel).filter(
            MessageModel.session_id == test_session.id,
            MessageModel.role == "user"
        ).first()
        
        metadata = message.metadata_json
        assert "channel" in metadata
        assert "password" not in metadata
        assert "auth_token" not in metadata


# ============================================================================
# SECTION B2.3: Adapter Building Tests
# ============================================================================

class TestProcessCoreAdapterBuilding:
    """Test adapter building in process_core."""
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    @patch('message_handler.core.processor.build_message_adapter')
    def test_adapter_includes_required_fields(
        self, mock_build_adapter, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Adapter includes session_id, user_id, message, routing, template, policy"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        mock_build_adapter.return_value = {
            "session_id": str(test_session.id),
            "user_id": str(test_user.id),
            "message": {"content": "Test"},
            "routing": {"instance_id": str(test_instance.id)},
            "template": {},
            "policy": {}
        }
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Verify adapter was built
        mock_build_adapter.assert_called_once()
        call_args = mock_build_adapter.call_args
        
        assert call_args.kwargs['session'] == test_session
        assert call_args.kwargs['user'] == test_user
        assert call_args.kwargs['instance'] == test_instance
        assert call_args.kwargs['db'] is not None
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_adapter_validated(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance, test_template, test_llm_model
    ):
        """✓ Adapter validated (required fields present)"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        # This should not raise validation error
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        assert result is not None


# ============================================================================
# SECTION B2.4: Orchestrator Integration Tests
# ============================================================================

class TestProcessCoreOrchestratorIntegration:
    """Test orchestrator integration in process_core."""
    
    @patch('message_handler.core.processor.ORCHESTRATOR_AVAILABLE', False)
    @patch('message_handler.core.processor.langfuse_client')
    def test_mock_mode_in_development_returns_mock(
        self, mock_langfuse, monkeypatch,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Mock mode in development → returns mock"""
        monkeypatch.setenv("ENVIRONMENT", "development")
        
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Should get mock response
        assert result is not None
        assert "response" in result
    
    @pytest.mark.skip(reason="Implementation pending - documented technical debt: Empty ENVIRONMENT handling")
    @patch('message_handler.core.processor.ORCHESTRATOR_AVAILABLE', False)
    @patch('message_handler.core.processor.langfuse_client')
    def test_empty_environment_string_should_fail_in_production(
        self, mock_langfuse, monkeypatch,
        db_session, test_session, test_user, test_instance
    ):
        """ENVIRONMENT="" (empty string) → Should fail in production"""
        monkeypatch.setenv("ENVIRONMENT", "")  # Empty string
        
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        # BUG: Empty string is treated as development, should raise OrchestrationError
        with pytest.raises(OrchestrationError):
            process_core(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user=test_user
            )
    
    @patch('message_handler.core.processor.ORCHESTRATOR_AVAILABLE', True)
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_orchestrator_success_processes_response(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Orchestrator success → process response"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        mock_orchestrator.return_value = {
            "text": "Orchestrator response",
            "token_usage": {
                "prompt_in": 100,
                "completion_out": 50
            }
        }
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        assert result is not None
        assert "response" in result
        assert result["response"]["content"] == "Orchestrator response"
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_orchestrator_error_returns_default_response(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Orchestrator error → default response"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        mock_orchestrator.side_effect = Exception("Orchestrator failed")
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Should return default response
        assert result is not None
        assert result["response"]["content"] == DEFAULT_RESPONSE_TEXT
    
    @patch('message_handler.core.processor.process_orchestrator_message')
    @patch('message_handler.core.processor.langfuse_client')
    def test_orchestrator_timeout_returns_default_response(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Orchestrator timeout → default response"""
        import time
        
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        def slow_orchestrator(*args, **kwargs):
            time.sleep(0.1)  # Simulate delay
            raise TimeoutError("Timeout")
        
        mock_orchestrator.side_effect = slow_orchestrator
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        assert result["response"]["content"] == DEFAULT_RESPONSE_TEXT


# ============================================================================
# SECTION B2.5: Response Processing Tests
# ============================================================================

class TestValidateOrchestratorResponse:
    """Test validate_orchestrator_response function."""
    
    def test_extract_text_from_response(self):
        """✓ Extract text from response"""
        response = {"text": "Hello world"}
        result = validate_orchestrator_response(response)
        
        assert result["text"] == "Hello world"
    
    def test_fallback_to_llm_response_field(self):
        """✓ Fallback fields: llm_response"""
        response = {"llm_response": "From LLM"}
        result = validate_orchestrator_response(response)
        
        assert result["text"] == "From LLM"
    
    def test_fallback_to_message_field(self):
        """✓ Fallback fields: message"""
        response = {"message": "From message"}
        result = validate_orchestrator_response(response)
        
        assert result["text"] == "From message"
    
    def test_fallback_to_content_field(self):
        """✓ Fallback fields: content"""
        response = {"content": "From content"}
        result = validate_orchestrator_response(response)
        
        assert result["text"] == "From content"
    
    def test_default_text_if_no_field_found(self):
        """✓ Default text if no field found"""
        response = {"other": "data"}
        result = validate_orchestrator_response(response)
        
        assert result["text"] == DEFAULT_RESPONSE_TEXT
    
    def test_none_response_returns_default(self):
        """✓ None response → default"""
        result = validate_orchestrator_response(None)
        
        assert result["text"] == DEFAULT_RESPONSE_TEXT
        assert "error" in result
    
    def test_invalid_response_type_returns_default(self):
        """✓ Invalid type → default"""
        result = validate_orchestrator_response("not a dict")
        
        assert result["text"] == DEFAULT_RESPONSE_TEXT
        assert "error" in result
    
    def test_adds_timestamp_if_missing(self):
        """✓ Adds timestamp if missing"""
        response = {"text": "Test"}
        result = validate_orchestrator_response(response)
        
        assert "timestamp" in result


# ============================================================================
# SECTION B2.6: Token Usage Tests
# ============================================================================

class TestExtractTokenUsage:
    """Test extract_token_usage function."""
    
    def test_extract_token_usage_from_response(self):
        """✓ Extract token_usage from response"""
        response = {
            "token_usage": {
                "prompt_in": 100,
                "completion_out": 50
            }
        }
        
        result = extract_token_usage(response)
        
        assert result["prompt_in"] == 100
        assert result["completion_out"] == 50
    
    def test_map_prompt_tokens_to_prompt_in(self):
        """✓ Map prompt_tokens → prompt_in"""
        response = {
            "usage": {
                "prompt_tokens": 150,
                "completion_tokens": 75
            }
        }
        
        result = extract_token_usage(response)
        
        assert result["prompt_in"] == 150
        assert result["completion_out"] == 75
    
    def test_map_completion_tokens_to_completion_out(self):
        """✓ Map completion_tokens → completion_out"""
        response = {
            "usage": {
                "prompt": 200,
                "completion": 100
            }
        }
        
        result = extract_token_usage(response)
        
        assert result["prompt_in"] == 200
        assert result["completion_out"] == 100
    
    def test_empty_response_returns_empty_dict(self):
        """✓ Empty response → empty dict"""
        result = extract_token_usage({})
        assert result == {}
    
    def test_none_response_returns_empty_dict(self):
        """✓ None response → empty dict"""
        result = extract_token_usage(None)
        assert result == {}


@patch('message_handler.core.processor.process_orchestrator_message')
@patch('message_handler.core.processor.langfuse_client')
class TestProcessCoreTokenUsage:
    """Test token usage recording in process_core."""
    
    def test_record_usage_to_session_token_usage(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Record usage to session_token_usage"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        mock_orchestrator.return_value = {
            "text": "Response",
            "token_usage": {
                "prompt_in": 100,
                "completion_out": 50
            }
        }
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Check token usage was recorded
        from db.models.session_token_usage import SessionTokenUsageModel
        usage = db_session.query(SessionTokenUsageModel).filter(
            SessionTokenUsageModel.session_id == test_session.id
        ).first()
        
        assert usage is not None
        assert usage.sent_tokens == 100
        assert usage.received_tokens == 50


# ============================================================================
# SECTION B2.7: Outbound Message Tests
# ============================================================================

@patch('message_handler.core.processor.process_orchestrator_message')
@patch('message_handler.core.processor.langfuse_client')
class TestProcessCoreOutboundMessage:
    """Test outbound message saving in process_core."""
    
    def test_save_with_role_assistant(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Save with role=assistant"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Assistant response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        from db.models.messages import MessageModel
        outbound = db_session.query(MessageModel).filter(
            MessageModel.session_id == test_session.id,
            MessageModel.role == "assistant"
        ).first()
        
        assert outbound is not None
        assert outbound.content == "Assistant response"
    
    def test_save_orchestrator_response_in_metadata(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Save orchestrator response in metadata"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        orchestrator_response = {
            "text": "Response",
            "metadata": {"key": "value"}
        }
        mock_orchestrator.return_value = orchestrator_response
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        from db.models.messages import MessageModel
        outbound = db_session.query(MessageModel).filter(
            MessageModel.session_id == test_session.id,
            MessageModel.role == "assistant"
        ).first()
        
        assert outbound.metadata_json is not None
        assert "orchestrator_response" in outbound.metadata_json
    
    def test_update_session_last_message_at(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Update session.last_message_at"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        old_timestamp = test_session.last_message_at
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        db_session.refresh(test_session)
        assert test_session.last_message_at > old_timestamp
    
    def test_update_session_last_assistant_message_at(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Update session.last_assistant_message_at"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        db_session.refresh(test_session)
        assert test_session.last_assistant_message_at is not None


# ============================================================================
# SECTION B2.8: Langfuse Telemetry Tests
# ============================================================================

@patch('message_handler.core.processor.process_orchestrator_message')
@patch('message_handler.core.processor.langfuse_client')
class TestProcessCoreLangfuseTelemetry:
    """Test Langfuse telemetry in process_core."""
    
    def test_create_trace_with_trace_id(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Create trace with trace_id"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        trace_id = str(uuid.uuid4())
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user,
            trace_id=trace_id
        )
        
        # Verify trace was created
        mock_langfuse.trace.assert_called_once()
        call_args = mock_langfuse.trace.call_args
        assert call_args.kwargs['id'] == trace_id
    
    def test_span_save_inbound_message(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Span: save_inbound_message"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Verify span was created
        assert mock_trace.span.call_count >= 1
        span_names = [call.kwargs['name'] for call in mock_trace.span.call_args_list]
        assert "save_inbound_message" in span_names
    
    def test_span_build_adapter(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Span: build_adapter"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        span_names = [call.kwargs['name'] for call in mock_trace.span.call_args_list]
        assert "build_adapter" in span_names
    
    def test_span_orchestrator_with_token_metadata(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Span: orchestrator (with token metadata)"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        mock_orchestrator.return_value = {
            "text": "Response",
            "token_usage": {"prompt_in": 100, "completion_out": 50}
        }
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        span_names = [call.kwargs['name'] for call in mock_trace.span.call_args_list]
        assert "orchestrator" in span_names
    
    def test_trace_updated_with_success(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Trace updated with success"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        # Verify trace.update was called
        assert mock_trace.update.call_count >= 1


# ============================================================================
# SECTION B2.9: Performance Tests
# ============================================================================

@patch('message_handler.core.processor.process_orchestrator_message')
@patch('message_handler.core.processor.langfuse_client')
class TestProcessCorePerformance:
    """Test performance characteristics of process_core."""
    
    def test_total_processing_time_under_30_seconds(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Total processing time < 30s"""
        import time
        
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        start = time.time()
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        duration = time.time() - start
        
        assert duration < 30.0
        assert "_meta" in result
        assert "processing_time_seconds" in result["_meta"]
    
    def test_metadata_includes_timing_breakdown(
        self, mock_langfuse, mock_orchestrator,
        db_session, test_session, test_user, test_instance
    ):
        """✓ Metadata includes timing breakdown"""
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        mock_orchestrator.return_value = {"text": "Response"}
        
        from db.models.instance_configs import InstanceConfigModel
        config = db_session.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == test_instance.id
        ).first()
        
        test_user.session = test_session
        test_user.session_id = test_session.id
        test_user.instance = test_instance
        test_user.instance_config = config
        
        result = process_core(
            db=db_session,
            content="Test",
            instance_id=str(test_instance.id),
            user=test_user
        )
        
        assert "_meta" in result
        assert "processing_time_seconds" in result["_meta"]
        assert isinstance(result["_meta"]["processing_time_seconds"], (int, float))


# ============================================================================
# SECTION B2.10: Utility Function Tests
# ============================================================================

class TestValidateContentLength:
    """Test validate_content_length function."""
    
    def test_valid_content_returns_normalized(self):
        """✓ Valid content → normalized"""
        result = validate_content_length("  Hello world  ")
        assert result == "Hello world"
    
    def test_content_exceeds_max_length_raises_error(self):
        """✓ Content > 10000 → ValidationError"""
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            validate_content_length(long_content)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "10000" in str(exc_info.value)
    
    def test_empty_content_returns_empty_string(self):
        """✓ Empty content → empty string"""
        result = validate_content_length("")
        assert result == ""
    
    def test_whitespace_only_returns_empty_string(self):
        """✓ Whitespace only → empty string"""
        result = validate_content_length("   \n\t   ")
        assert result == ""