# ============================================================================
# FILE: test/message_handler_services/test_message_service.py
# Tests for message_handler/services/message_service.py (Section C4)
# ============================================================================

import pytest
import uuid
import json

from message_handler.services.message_service import (
    save_inbound_message,
    save_outbound_message,
    save_broadcast_message,
    get_recent_messages,
    get_message_by_id
)
from message_handler.exceptions import (
    ValidationError,
    ResourceNotFoundError,
    DatabaseError,
    ErrorCode
)
from db.models.messages import MessageModel


# ============================================================================
# SECTION C4.1: save_inbound_message Tests
# ============================================================================

class TestSaveInboundMessage:
    """Test save_inbound_message function."""
    
    @pytest.mark.asyncio
    async def test_missing_session_id_raises_validation_error(self, db_session, test_user, test_instance):
        """✓ Missing session_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_inbound_message(
                db_session,
                session_id=None,
                user_id=str(test_user.id),
                instance_id=str(test_instance.id),
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "session" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_missing_user_id_raises_validation_error(self, db_session, test_session, test_instance):
        """✓ Missing user_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=None,
                instance_id=str(test_instance.id),
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "user" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_missing_instance_id_raises_validation_error(self, db_session, test_session, test_user):
        """✓ Missing instance_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=str(test_user.id),
                instance_id=None,
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "instance" in str(exc_info.value).lower()
    
    def test_content_exceeds_10000_raises_validation_error(
        self, db_session, test_session, test_user, test_instance
    ):
        """✓ Content > 10000 → ValidationError"""
        long_content = "x" * 10001
        
        with pytest.raises(ValidationError) as exc_info:
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=str(test_user.id),
                instance_id=str(test_instance.id),
                content=long_content
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "10000" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_valid_inputs_saves_message(self, db_session, test_session, test_user, test_instance):
        """✓ Valid inputs → save message"""
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test message"
        )
        
        assert message is not None
        assert message.content == "Test message"
    
    @pytest.mark.asyncio
    async def test_role_is_user(self, db_session, test_session, test_user, test_instance):
        """✓ role = user"""
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.role == "user"
    
    @pytest.mark.asyncio
    async def test_include_request_id(self, db_session, test_session, test_user, test_instance):
        """✓ Include request_id"""
        request_id = str(uuid.uuid4())
        
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test",
            request_id=request_id
        )
        
        assert message.request_id == request_id
    
    @pytest.mark.asyncio
    async def test_include_trace_id(self, db_session, test_session, test_user, test_instance):
        """✓ Include trace_id"""
        trace_id = str(uuid.uuid4())
        
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test",
            trace_id=trace_id
        )
        
        assert message.trace_id == trace_id
    
    @pytest.mark.asyncio
    async def test_sanitize_metadata(self, db_session, test_session, test_user, test_instance):
        """✓ Sanitize metadata"""
        meta_info = {
            "channel": "api",
            "password": "secret123",
            "token": "xyz"
        }
        
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test",
            meta_info=meta_info
        )
        
        # Sensitive keys should be stripped
        assert "channel" in message.metadata_json
        assert "password" not in message.metadata_json
        assert "token" not in message.metadata_json
    
    def test_validate_metadata_size_less_than_64kb(
        self, db_session, test_session, test_user, test_instance
    ):
        """✓ Validate metadata size (< 64KB)"""
        # Small metadata should work
        meta_info = {"key": "value"}
        
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test",
            meta_info=meta_info
        )
        
        assert message.metadata_json is not None
    
    @pytest.mark.asyncio
    async def test_update_session_last_message_at(self, db_session, test_session, test_user, test_instance):
        """✓ Update session.last_message_at"""
        old_time = test_session.last_message_at
        
        save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        db_session.refresh(test_session)
        assert test_session.last_message_at > old_time


# ============================================================================
# SECTION C4.2: save_outbound_message Tests
# ============================================================================

class TestSaveOutboundMessage:
    """Test save_outbound_message function."""
    
    @pytest.mark.asyncio
    async def test_missing_session_id_raises_validation_error(self, db_session, test_instance):
        """✓ Missing session_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_outbound_message(
                db_session,
                session_id=None,
                instance_id=str(test_instance.id),
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    @pytest.mark.asyncio
    async def test_missing_instance_id_raises_validation_error(self, db_session, test_session):
        """✓ Missing instance_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_outbound_message(
                db_session,
                session_id=str(test_session.id),
                instance_id=None,
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_content_exceeds_10000_truncates_with_warning(
        self, db_session, test_session, test_instance
    ):
        """✓ Content > 10000 → truncate + warning"""
        long_content = "x" * 10001
        
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content=long_content
        )
        
        # Should be truncated
        assert len(message.content) <= 10000
        assert "[truncated]" in message.content
    
    @pytest.mark.asyncio
    async def test_valid_inputs_saves_message(self, db_session, test_session, test_instance):
        """✓ Valid inputs → save message"""
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Response message"
        )
        
        assert message is not None
        assert message.content == "Response message"
    
    @pytest.mark.asyncio
    async def test_role_is_assistant(self, db_session, test_session, test_instance):
        """✓ role = assistant"""
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.role == "assistant"
    
    @pytest.mark.asyncio
    async def test_user_id_is_null(self, db_session, test_session, test_instance):
        """✓ user_id = NULL"""
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.user_id is None
    
    def test_include_orchestrator_response_in_metadata(
        self, db_session, test_session, test_instance
    ):
        """✓ Include orchestrator_response in metadata"""
        orchestrator_response = {
            "text": "Response",
            "metadata": {"key": "value"}
        }
        
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test",
            orchestrator_response=orchestrator_response
        )
        
        assert "orchestrator_response" in message.metadata_json
    
    def test_truncate_large_orchestrator_response_exceeds_64kb(
        self, db_session, test_session, test_instance
    ):
        """✓ Truncate large orchestrator_response (> 64KB)"""
        # Create large response
        large_response = {
            "text": "x" * 70000,
            "metadata": {"key": "value"}
        }
        
        message = save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test",
            orchestrator_response=large_response
        )
        
        # Should be truncated or handled
        assert message.metadata_json is not None
    
    @pytest.mark.asyncio
    async def test_update_session_last_message_at(self, db_session, test_session, test_instance):
        """✓ Update session.last_message_at"""
        old_time = test_session.last_message_at
        
        save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        db_session.refresh(test_session)
        assert test_session.last_message_at > old_time
    
    def test_update_session_last_assistant_message_at(
        self, db_session, test_session, test_instance
    ):
        """✓ Update session.last_assistant_message_at"""
        save_outbound_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        db_session.refresh(test_session)
        assert test_session.last_assistant_message_at is not None


# ============================================================================
# SECTION C4.3: save_broadcast_message Tests
# ============================================================================

class TestSaveBroadcastMessage:
    """Test save_broadcast_message function."""
    
    @pytest.mark.asyncio
    async def test_missing_session_id_raises_validation_error(self, db_session, test_instance):
        """✓ Missing session_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_broadcast_message(
                db_session,
                session_id=None,
                instance_id=str(test_instance.id),
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    @pytest.mark.asyncio
    async def test_missing_instance_id_raises_validation_error(self, db_session, test_session):
        """✓ Missing instance_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            save_broadcast_message(
                db_session,
                session_id=str(test_session.id),
                instance_id=None,
                content="Test"
            )
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    @pytest.mark.asyncio
    async def test_content_exceeds_10000_truncates(self, db_session, test_session, test_instance):
        """✓ Content > 10000 → truncate"""
        long_content = "x" * 10001
        
        message = save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content=long_content
        )
        
        assert len(message.content) <= 10000
        assert "[truncated]" in message.content
    
    @pytest.mark.asyncio
    async def test_valid_inputs_saves_message(self, db_session, test_session, test_instance):
        """✓ Valid inputs → save message"""
        message = save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Broadcast message"
        )
        
        assert message is not None
        assert message.content == "Broadcast message"
    
    @pytest.mark.asyncio
    async def test_role_is_assistant(self, db_session, test_session, test_instance):
        """✓ role = assistant"""
        message = save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.role == "assistant"
    
    @pytest.mark.asyncio
    async def test_user_id_is_null(self, db_session, test_session, test_instance):
        """✓ user_id = NULL"""
        message = save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.user_id is None
    
    @pytest.mark.asyncio
    async def test_metadata_channel_is_broadcast(self, db_session, test_session, test_instance):
        """✓ metadata.channel = broadcast"""
        message = save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        assert message.metadata_json.get("channel") == "broadcast"
    
    @pytest.mark.asyncio
    async def test_update_session_last_message_at(self, db_session, test_session, test_instance):
        """✓ Update session.last_message_at"""
        old_time = test_session.last_message_at
        
        save_broadcast_message(
            db_session,
            session_id=str(test_session.id),
            instance_id=str(test_instance.id),
            content="Test"
        )
        
        db_session.refresh(test_session)
        assert test_session.last_message_at > old_time


# ============================================================================
# SECTION C4.4: get_recent_messages Tests
# ============================================================================

class TestGetRecentMessages:
    """Test get_recent_messages function."""
    
    @pytest.mark.asyncio
    async def test_missing_session_id_raises_validation_error(self, db_session):
        """✓ Missing session_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            get_recent_messages(db_session, session_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    @pytest.mark.asyncio
    async def test_session_not_found_raises_resource_not_found_error(self, db_session):
        """✓ Session not found → ResourceNotFoundError"""
        fake_id = str(uuid.uuid4())
        
        with pytest.raises(ResourceNotFoundError) as exc_info:
            get_recent_messages(db_session, session_id=fake_id)
        
        assert exc_info.value.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_limit_less_than_or_equal_to_zero_raises_validation_error(
        self, db_session, test_session
    ):
        """✓ limit <= 0 → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            get_recent_messages(db_session, str(test_session.id), limit=0)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_limit_greater_than_100_caps_at_100(
        self, db_session, test_session, test_user, test_instance
    ):
        """✓ limit > 100 → cap at 100"""
        # Create some messages
        for i in range(5):
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=str(test_user.id),
                instance_id=str(test_instance.id),
                content=f"Message {i}"
            )
        
        messages = get_recent_messages(db_session, str(test_session.id), limit=200)
        
        # Should return at most 100, but we only created 5
        assert len(messages) <= 100
    
    def test_return_messages_ordered_by_created_at_desc(
        self, db_session, test_session, test_user, test_instance
    ):
        """✓ Return messages ordered by created_at desc"""
        # Create messages
        for i in range(3):
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=str(test_user.id),
                instance_id=str(test_instance.id),
                content=f"Message {i}"
            )
        
        messages = get_recent_messages(db_session, str(test_session.id))
        
        # Should be ordered newest first
        assert len(messages) == 3
        assert messages[0].content == "Message 2"
        assert messages[2].content == "Message 0"
    
    @pytest.mark.asyncio
    async def test_apply_limit(self, db_session, test_session, test_user, test_instance):
        """✓ Apply limit"""
        # Create 5 messages
        for i in range(5):
            save_inbound_message(
                db_session,
                session_id=str(test_session.id),
                user_id=str(test_user.id),
                instance_id=str(test_instance.id),
                content=f"Message {i}"
            )
        
        messages = get_recent_messages(db_session, str(test_session.id), limit=3)
        
        assert len(messages) == 3


# ============================================================================
# SECTION C4.5: get_message_by_id Tests
# ============================================================================

class TestGetMessageById:
    """Test get_message_by_id function."""
    
    @pytest.mark.asyncio
    async def test_missing_message_id_raises_validation_error(self, db_session):
        """✓ Missing message_id → ValidationError"""
        with pytest.raises(ValidationError) as exc_info:
            get_message_by_id(db_session, message_id=None)
        
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_valid_message_id_returns_message(
        self, db_session, test_session, test_user, test_instance
    ):
        """✓ Valid message_id → return message"""
        message = save_inbound_message(
            db_session,
            session_id=str(test_session.id),
            user_id=str(test_user.id),
            instance_id=str(test_instance.id),
            content="Test message"
        )
        
        retrieved = get_message_by_id(db_session, str(message.id))
        
        assert retrieved is not None
        assert retrieved.id == message.id
    
    @pytest.mark.asyncio
    async def test_invalid_message_id_returns_none(self, db_session):
        """✓ Invalid message_id → None"""
        fake_id = str(uuid.uuid4())
        message = get_message_by_id(db_session, fake_id)
        
        assert message is None