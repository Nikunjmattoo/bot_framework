# ============================================================================
# FILE: test/message_handler_core/test_handler.py
# Tests for message_handler/handler.py (Section B1)
# ============================================================================

import pytest
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

from message_handler.handler import (
    process_message,
    process_whatsapp_message,
    broadcast_message,
    validate_message_content,
    get_handler_status
)
from message_handler.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    OrchestrationError,
    ErrorCode
)


# ============================================================================
# SECTION B1.1: process_message Tests
# ============================================================================

class TestProcessMessage:
    """Test process_message function."""
    
    def test_valid_inputs_success(self, db_session, test_instance, test_user):
        """✓ Valid inputs → success"""
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.process_api_message') as mock_api:
            mock_api.return_value = {
                "message_id": str(uuid.uuid4()),
                "response": {"id": str(uuid.uuid4()), "content": "Test response"}
            }
            
            result = process_message(
                db=db_session,
                content="Hello world",
                instance_id=str(test_instance.id),
                user_details={"phone_e164": "+1234567890"},
                request_id=request_id,
                channel="api"
            )
            
            assert result is not None
            assert "message_id" in result
            mock_api.assert_called_once()
    
    def test_missing_instance_id_raises_validation_error(self, db_session):
        """✓ Missing instance_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            process_message(
                db=db_session,
                content="Hello",
                instance_id="",  # Empty string
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        # FIX: Check both error message and field attribute
        error_str = str(exc_info.value).lower()
        assert "instance" in error_str and "id" in error_str
    
    def test_missing_request_id_raises_validation_error(self, db_session, test_instance):
        """✓ Missing request_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            process_message(
                db=db_session,
                content="Hello",
                instance_id=str(test_instance.id),
                request_id=None  # Missing
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "request" in str(exc_info.value).lower() and "id" in str(exc_info.value).lower()
    
    def test_empty_content_raises_validation_error(self, db_session, test_instance):
        """✓ Invalid content length → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            process_message(
                db=db_session,
                content="",  # Empty
                instance_id=str(test_instance.id),
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "content" in str(exc_info.value).lower()
    
    def test_content_exceeds_max_length_raises_validation_error(self, db_session, test_instance):
        """✓ Content > 10000 chars → ValidationError"""
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            process_message(
                db=db_session,
                content=long_content,
                instance_id=str(test_instance.id),
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "10000" in str(exc_info.value)
    
    def test_delegates_to_api_handler(self, db_session, test_instance):
        """✓ Delegates to api_handler"""
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.process_api_message') as mock_api:
            mock_api.return_value = {"message_id": str(uuid.uuid4())}
            
            process_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                request_id=request_id,
                channel="api"
            )
            
            # Verify delegation
            mock_api.assert_called_once()
            call_args = mock_api.call_args
            assert call_args.kwargs['content'] == "Test"
            assert call_args.kwargs['instance_id'] == str(test_instance.id)
            assert call_args.kwargs['request_id'] == request_id
            assert call_args.kwargs['channel'] == "api"
    
    def test_adds_performance_metrics_to_response(self, db_session, test_instance):
        """✓ Response includes _meta with timing"""
        with patch('message_handler.handler.process_api_message') as mock_api:
            mock_api.return_value = {
                "message_id": str(uuid.uuid4()),
                "response": {"content": "Test"}
            }
            
            result = process_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                request_id=str(uuid.uuid4())
            )
            
            assert "_meta" in result
            assert "processing_time_seconds" in result["_meta"]
            assert "trace_id" in result["_meta"]
            assert "channel" in result["_meta"]
    
    def test_sanitizes_user_details(self, db_session, test_instance):
        """✓ User details are sanitized (strip sensitive keys)"""
        user_details = {
            "phone_e164": "+1234567890",
            "password": "secret123",  # Should be stripped
            "token": "abc123"  # Should be stripped
        }
        
        with patch('message_handler.handler.process_api_message') as mock_api:
            mock_api.return_value = {"message_id": str(uuid.uuid4())}
            
            process_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                request_id=str(uuid.uuid4()),
                user_details=user_details
            )
            
            # Check sanitized user_details passed to handler
            call_args = mock_api.call_args
            sanitized = call_args.kwargs['user_details']
            assert "phone_e164" in sanitized
            assert "password" not in sanitized
            assert "token" not in sanitized


# ============================================================================
# SECTION B1.2: process_whatsapp_message Tests
# ============================================================================

class TestProcessWhatsappMessage:
    """Test process_whatsapp_message function."""
    
    def test_valid_whatsapp_message_success(self, db_session, test_whatsapp_instance):
        """✓ Valid WhatsApp message → success"""
        whatsapp_message = {
            "from": "+1234567890",
            "to": "+9876543210",
            "id": "wamid_123",
            "text": {"body": "Hello"}
        }
        metadata = {"to": "+9876543210"}
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.process_whatsapp_message_internal') as mock_wa:
            mock_wa.return_value = {
                "message_id": str(uuid.uuid4()),
                "response": {"content": "Response"}
            }
            
            result = process_whatsapp_message(
                db=db_session,
                whatsapp_message=whatsapp_message,
                metadata=metadata,
                request_id=request_id
            )
            
            assert result is not None
            assert "message_id" in result
            mock_wa.assert_called_once()
    
    def test_missing_request_id_raises_validation_error(self, db_session):
        """✓ Missing request_id → ValidationError"""
        whatsapp_message = {
            "from": "+1234567890",
            "text": {"body": "Hello"}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            process_whatsapp_message(
                db=db_session,
                whatsapp_message=whatsapp_message,
                request_id=None  # Missing
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "request" in str(exc_info.value).lower() and "id" in str(exc_info.value).lower()
    
    def test_empty_message_raises_validation_error(self, db_session):
        """✓ Empty message → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            process_whatsapp_message(
                db=db_session,
                whatsapp_message=None,  # Empty
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_validates_message_structure(self, db_session):
        """✓ Do a basic validation of WhatsApp message structure"""
        invalid_message = {
            "from": "+1234567890"
            # Missing 'to' and content
        }
        
        with pytest.raises(ValidationError):
            process_whatsapp_message(
                db=db_session,
                whatsapp_message=invalid_message,
                request_id=str(uuid.uuid4())
            )
    
    def test_delegates_to_whatsapp_handler(self, db_session, test_whatsapp_instance):
        """✓ Delegates to whatsapp_handler"""
        whatsapp_message = {
            "from": "+1234567890",
            "to": "+9876543210",
            "text": {"body": "Test"}
        }
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.process_whatsapp_message_internal') as mock_wa:
            mock_wa.return_value = {"message_id": str(uuid.uuid4())}
            
            process_whatsapp_message(
                db=db_session,
                whatsapp_message=whatsapp_message,
                request_id=request_id
            )
            
            mock_wa.assert_called_once()
            call_args = mock_wa.call_args
            assert call_args.kwargs['whatsapp_message'] == whatsapp_message
            assert call_args.kwargs['request_id'] == request_id
    
    def test_sanitizes_whatsapp_message(self, db_session):
        """✓ WhatsApp message is sanitized"""
        whatsapp_message = {
            "from": "+1234567890",
            "to": "+9876543210",
            "text": {"body": "Test"},
            "password": "secret"  # Should be stripped
        }
        
        with patch('message_handler.handler.process_whatsapp_message_internal') as mock_wa:
            mock_wa.return_value = {"message_id": str(uuid.uuid4())}
            
            process_whatsapp_message(
                db=db_session,
                whatsapp_message=whatsapp_message,
                request_id=str(uuid.uuid4())
            )
            
            call_args = mock_wa.call_args
            sanitized = call_args.kwargs['whatsapp_message']
            assert "password" not in sanitized
    
    def test_adds_performance_metrics_to_response(self, db_session, test_whatsapp_instance):
        """✓ Response includes _meta"""
        whatsapp_message = {
            "from": "+1234567890",
            "to": "+9876543210",
            "text": {"body": "Test"}
        }
        
        with patch('message_handler.handler.process_whatsapp_message_internal') as mock_wa:
            mock_wa.return_value = {
                "message_id": str(uuid.uuid4()),
                "response": {"content": "Test"}
            }
            
            result = process_whatsapp_message(
                db=db_session,
                whatsapp_message=whatsapp_message,
                request_id=str(uuid.uuid4())
            )
            
            assert "_meta" in result
            assert "processing_time_seconds" in result["_meta"]
            assert "channel" in result["_meta"]
            assert result["_meta"]["channel"] == "whatsapp"


# ============================================================================
# SECTION B1.3: broadcast_message Tests
# ============================================================================

class TestBroadcastMessage:
    """Test broadcast_message function."""
    
    def test_valid_inputs_success(self, db_session, test_instance, test_user):
        """✓ Valid inputs → success"""
        user_ids = [str(test_user.id)]
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.broadcast_message_internal') as mock_bc:
            mock_bc.return_value = {
                "results": [{"user_id": str(test_user.id), "success": True}],
                "summary": {"total": 1, "successful": 1, "failed": 0}
            }
            
            result = broadcast_message(
                db=db_session,
                content="Broadcast test",
                instance_id=str(test_instance.id),
                user_ids=user_ids,
                request_id=request_id
            )
            
            assert result is not None
            assert "summary" in result
            mock_bc.assert_called_once()
    
    def test_missing_request_id_raises_validation_error(self, db_session, test_instance):
        """✓ Missing request_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            broadcast_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user_ids=[str(uuid.uuid4())],
                request_id=None  # Missing
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "request" in str(exc_info.value).lower() and "id" in str(exc_info.value).lower()
    
    def test_missing_instance_id_raises_validation_error(self, db_session):
        """✓ Missing instance_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            broadcast_message(
                db=db_session,
                content="Test",
                instance_id="",  # Empty
                user_ids=[str(uuid.uuid4())],
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        error_str = str(exc_info.value).lower()
        assert "instance" in error_str and "id" in error_str
    
    def test_empty_content_raises_validation_error(self, db_session, test_instance):
        """✓ Empty content → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            broadcast_message(
                db=db_session,
                content="",  # Empty
                instance_id=str(test_instance.id),
                user_ids=[str(uuid.uuid4())],
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_empty_user_ids_list_raises_validation_error(self, db_session, test_instance):
        """✓ Empty user_ids → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            broadcast_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user_ids=[],  # Empty list
                request_id=str(uuid.uuid4())
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        error_str = str(exc_info.value).lower()
        assert "user" in error_str and "id" in error_str
    
    def test_delegates_to_broadcast_handler(self, db_session, test_instance, test_user):
        """✓ Delegates to broadcast_handler"""
        user_ids = [str(test_user.id)]
        request_id = str(uuid.uuid4())
        
        with patch('message_handler.handler.broadcast_message_internal') as mock_bc:
            mock_bc.return_value = {
                "results": [],
                "summary": {"total": 0}
            }
            
            broadcast_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user_ids=user_ids,
                request_id=request_id
            )
            
            mock_bc.assert_called_once()
            call_args = mock_bc.call_args
            assert call_args.kwargs['content'] == "Test"
            assert call_args.kwargs['instance_id'] == str(test_instance.id)
            assert call_args.kwargs['request_id'] == request_id
    
    def test_sanitizes_user_ids_list(self, db_session, test_instance):
        """✓ User IDs list is sanitized"""
        user_ids = [str(uuid.uuid4())] * 1001  # Over limit
        
        with patch('message_handler.handler.broadcast_message_internal') as mock_bc:
            mock_bc.return_value = {
                "results": [],
                "summary": {"total": 0}
            }
            
            broadcast_message(
                db=db_session,
                content="Test",
                instance_id=str(test_instance.id),
                user_ids=user_ids,
                request_id=str(uuid.uuid4())
            )
            
            # Should be truncated to max_list_items
            call_args = mock_bc.call_args
            sanitized_ids = call_args.kwargs['user_ids']
            assert len(sanitized_ids) <= 1000


# ============================================================================
# SECTION B1.4: validate_message_content Tests
# ============================================================================

class TestValidateMessageContent:
    """Test validate_message_content function."""
    
    def test_empty_content_raises_validation_error(self):
        """✓ Empty content → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("")
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "content" in str(exc_info.value).lower()
    
    def test_whitespace_only_content_raises_validation_error(self):
        """✓ Whitespace only → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content("   \n\t   ")
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_content_exceeds_max_length_raises_validation_error(self):
        """✓ Content > 10000 → ValidationError"""
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            validate_message_content(long_content)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "10000" in str(exc_info.value)
    
    def test_valid_content_returns_true(self):
        """✓ Valid content → True"""
        result = validate_message_content("Hello world")
        assert result is True
    
    def test_content_at_max_length_returns_true(self):
        """✓ Content exactly 10000 chars → True"""
        content = "x" * 10000
        result = validate_message_content(content)
        assert result is True


# ============================================================================
# SECTION B1.5: get_handler_status Tests
# ============================================================================

class TestGetHandlerStatus:
    """Test get_handler_status function."""
    
    def test_returns_status_dict(self):
        """✓ Returns dict with status info"""
        status = get_handler_status()
        
        assert isinstance(status, dict)
        assert "name" in status
        assert "version" in status
        assert "status" in status
        assert "available_channels" in status
        assert "health" in status
    
    def test_includes_version_info(self):
        """✓ Includes version"""
        status = get_handler_status()
        assert status["version"] is not None
    
    def test_includes_available_channels(self):
        """✓ Includes channels list"""
        status = get_handler_status()
        channels = status["available_channels"]
        
        assert "api" in channels
        assert "web" in channels
        assert "app" in channels
        assert "whatsapp" in channels
        assert "broadcast" in channels
    
    def test_health_status_includes_timestamp(self):
        """✓ Health includes timestamp"""
        status = get_handler_status()
        assert "timestamp" in status["health"]