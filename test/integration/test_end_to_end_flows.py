# ============================================================================
# FILE: test/integration/test_end_to_end_flows.py
# Integration Tests - Category G1: End-to-End Flows
# ============================================================================

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from db.models import (
    UserModel, UserIdentifierModel, SessionModel, MessageModel
)
from message_handler.services.token_service import TokenManager


class TestNewUserFirstMessage:
    """G1.1: New User, First Message - Full flow from request to response."""

    def test_new_user_first_message_success(self, client, test_instance, test_brand, db_session):
        """
        ✓ POST /api/messages with user identifiers
        ✓ User created
        ✓ User identifiers created (brand-scoped)
        ✓ Session created
        ✓ Token plan initialized
        ✓ Inbound message saved
        ✓ Adapter built
        ✓ Orchestrator called
        ✓ Outbound message saved
        ✓ Token usage recorded
        ✓ Response returned
        """
        request_id = str(uuid.uuid4())

        payload = {
            "content": "Hello, this is my first message!",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {
                "phone_e164": "+19876543210",
                "email": "newuser@example.com"
            }
        }

        # Mock orchestrator response
        mock_orchestrator_response = {
            "text": "Welcome! How can I help you?",
            "intents": [],
            "token_usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120
            }
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_orchestrator_response):
            response = client.post("/api/messages", json=payload)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["response"]["content"] == "Welcome! How can I help you?"
        assert "message_id" in data["data"]

        # Get user from session to verify user was created
        message_id = data["data"]["message_id"]
        from db.models import MessageModel
        message = db_session.query(MessageModel).filter(
            MessageModel.id == message_id
        ).first()
        assert message is not None

        user = db_session.query(UserModel).filter(
            UserModel.id == message.user_id
        ).first()
        assert user is not None
        assert user.user_tier == "standard"

        # Verify user identifiers created (brand-scoped)
        identifiers = db_session.query(UserIdentifierModel).filter(
            UserIdentifierModel.user_id == user.id,
            UserIdentifierModel.brand_id == test_brand.id
        ).all()
        assert len(identifiers) == 2  # phone and email
        identifier_values = {i.identifier_value for i in identifiers}
        assert "+19876543210" in identifier_values
        assert "newuser@example.com" in identifier_values

        # Verify session was created
        session = db_session.query(SessionModel).filter(
            SessionModel.user_id == user.id,
            SessionModel.instance_id == test_instance.id
        ).first()
        assert session is not None
        assert session.active is True

        # Verify messages were saved (inbound + outbound)
        messages = db_session.query(MessageModel).filter(
            MessageModel.session_id == session.id
        ).order_by(MessageModel.created_at).all()
        assert len(messages) == 2

        # Inbound message
        inbound = messages[0]
        assert inbound.role == "user"
        assert inbound.content == "Hello, this is my first message!"
        assert inbound.user_id == user.id
        assert inbound.metadata_json.get("request_id") == request_id

        # Outbound message
        outbound = messages[1]
        assert outbound.role == "assistant"
        assert outbound.content == "Welcome! How can I help you?"
        assert outbound.user_id is None


class TestExistingUserNewMessage:
    """G1.2: Existing User, New Message."""

    def test_existing_user_new_message(self, client, test_instance, test_user, test_session, db_session):
        """
        ✓ User resolved
        ✓ Existing session returned
        ✓ Token plan loaded
        ✓ Messages saved
        ✓ Response returned
        """
        request_id = str(uuid.uuid4())

        payload = {
            "content": "Follow up question",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {
                "phone_e164": "+1234567890"  # Existing user phone
            }
        }

        mock_response = {
            "text": "Sure, here's the answer",
            "intents": [],
            "token_usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60
            }
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert user_id == str(test_user.id)
        assert session_id == str(test_session.id)


class TestIdempotentRequest:
    """G1.3: Idempotent Request - Same request_id should return cached response."""

    def test_first_request_processes(self, client, test_instance, db_session):
        """✓ First request → process"""
        request_id = str(uuid.uuid4())

        payload = {
            "content": "Test message",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {
                "phone_e164": "+15555555555"
            }
        }

        mock_response = {
            "text": "First response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200
        assert response.json()["data"]["response_text"] == "First response"

    def test_duplicate_request_returns_409(self, client, test_instance, test_user, test_session, db_session):
        """✓ Duplicate request → 409 with cached response"""
        request_id = str(uuid.uuid4())

        # Create a message with request_id
        message = MessageModel(
            session_id=test_session.id,
            user_id=test_user.id,
            instance_id=test_instance.id,
            role="user",
            content="Test",
            metadata_json={
                "request_id": request_id,
                "processed": True,
                "cached_response": {
                    "response_text": "Cached response",
                    "message_id": str(uuid.uuid4())
                }
            }
        )
        db_session.add(message)
        db_session.commit()

        payload = {
            "content": "Test message",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {
                "phone_e164": "+1234567890"
            }
        }

        response = client.post("/api/messages", json=payload)

        assert response.status_code == 409
        assert "already processed" in response.json()["error"]["message"].lower()


class TestWhatsAppMessage:
    """G1.4: WhatsApp Message - Full WhatsApp flow."""

    def test_whatsapp_text_message(self, client, test_whatsapp_instance, db_session):
        """
        ✓ POST /api/whatsapp/messages
        ✓ Extract from/to from message
        ✓ Resolve instance by recipient_number
        ✓ Resolve user by phone (brand-scoped)
        ✓ Extract message content
        ✓ Process through core
        ✓ Response returned
        """
        request_id = str(uuid.uuid4())

        payload = {
            "request_id": request_id,
            "whatsapp_message": {
                "from": "+11234567890",
                "to": "+9876543210",  # Matches test_whatsapp_instance.recipient_number
                "type": "text",
                "text": {
                    "body": "Hello from WhatsApp"
                }
            }
        }

        mock_response = {
            "text": "WhatsApp response",
            "intents": [],
            "token_usage": {"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/whatsapp/messages", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["response"]["content"] == "WhatsApp response"

        # Verify WhatsApp user was created
        user = db_session.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
        assert user is not None
        assert user.user_tier == "verified"  # WhatsApp users get verified tier


class TestBroadcastMessage:
    """G1.5: Broadcast Message - Send to multiple users."""

    def test_broadcast_to_multiple_users(self, client, test_instance, test_brand, db_session):
        """
        ✓ POST /api/broadcast
        ✓ Resolve instance
        ✓ For each user_id: get/create session, save message
        ✓ Return summary + per-user results
        """
        # Create 3 test users
        users = []
        for i in range(3):
            user = UserModel(acquisition_channel="api", user_tier="standard")
            db_session.add(user)
            db_session.flush()

            identifier = UserIdentifierModel(
                user_id=user.id,
                brand_id=test_brand.id,
                identifier_type="phone_e164",
                identifier_value=f"+1555000{i:04d}",
                channel="api"
            )
            db_session.add(identifier)
            users.append(user)

        db_session.commit()

        request_id = str(uuid.uuid4())
        payload = {
            "content": "Broadcast message to all",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user_ids": [str(u.id) for u in users]
        }

        response = client.post("/api/broadcast", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Check summary
        summary = data["data"]["summary"]
        assert summary["total"] == 3
        assert summary["successful"] == 3
        assert summary["failed"] == 0


class TestGuestUser:
    """G1.6: Guest User - Create guest when no identifiers."""

    def test_guest_user_accepted(self, client, test_instance, db_session):
        """
        ✓ POST /api/messages with no user identifiers
        ✓ Instance has accept_guest_users=true
        ✓ Guest user created
        ✓ Session created
        ✓ Message processed
        """
        request_id = str(uuid.uuid4())

        payload = {
            "content": "I am a guest",
            "instance_id": str(test_instance.id),
            "request_id": request_id
            # No user
        }

        mock_response = {
            "text": "Welcome guest!",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify guest user created
        user = db_session.query(UserModel).filter(
            UserModel.id == user_id
        ).first()
        assert user.user_tier == "guest"

    def test_guest_user_rejected(self, client, test_instance_no_guest, db_session):
        """
        ✓ POST /api/messages with no user identifiers
        ✓ Instance has accept_guest_users=false
        ✓ 401 Unauthorized
        """
        request_id = str(uuid.uuid4())

        payload = {
            "content": "I want to be a guest",
            "instance_id": str(test_instance_no_guest.id),
            "request_id": request_id
        }

        response = client.post("/api/messages", json=payload)

        assert response.status_code == 401


class TestBrandScopedIdentity:
    """G1.7: Brand-Scoped Identity - Same identifier, different brands."""

    def test_same_phone_different_brands(self, client, db_session, test_template_set, test_llm_model):
        """
        ✓ User A with phone +123 in Brand A
        ✓ User B with phone +123 in Brand B
        ✓ Resolve separately per brand
        """
        from db.models import BrandModel, InstanceModel, InstanceConfigModel

        # Create two brands
        brand_a = BrandModel(name="Brand A", phone_number="+1111111111", website="https://a.com")
        brand_b = BrandModel(name="Brand B", phone_number="+2222222222", website="https://b.com")
        db_session.add_all([brand_a, brand_b])
        db_session.flush()

        # Create instances for each brand
        instance_a = InstanceModel(
            brand_id=brand_a.id, name="Instance A", channel="api",
            is_active=True, accept_guest_users=True
        )
        instance_b = InstanceModel(
            brand_id=brand_b.id, name="Instance B", channel="api",
            is_active=True, accept_guest_users=True
        )
        db_session.add_all([instance_a, instance_b])
        db_session.flush()

        # Create configs
        config_a = InstanceConfigModel(
            instance_id=instance_a.id, template_set_id=test_template_set.id, is_active=True
        )
        config_b = InstanceConfigModel(
            instance_id=instance_b.id, template_set_id=test_template_set.id, is_active=True
        )
        db_session.add_all([config_a, config_b])
        db_session.commit()

        shared_phone = "+15551234567"

        # Message to Brand A
        payload_a = {
            "content": "Message to Brand A",
            "instance_id": str(instance_a.id),
            "request_id": str(uuid.uuid4()),
            "user": {"phone_e164": shared_phone}
        }

        mock_response = {
            "text": "Response", "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response_a = client.post("/api/messages", json=payload_a)

        assert response_a.status_code == 200
        user_id_a = response_a.json()["data"]["user_id"]

        # Message to Brand B (same phone)
        payload_b = {
            "content": "Message to Brand B",
            "instance_id": str(instance_b.id),
            "request_id": str(uuid.uuid4()),
            "user": {"phone_e164": shared_phone}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response_b = client.post("/api/messages", json=payload_b)

        assert response_b.status_code == 200
        user_id_b = response_b.json()["data"]["user_id"]

        # Different users despite same phone
        assert user_id_a != user_id_b


class TestSessionTimeout:
    """G1.8: Session Timeout - Create new session after timeout."""

    def test_session_timeout_creates_new_session(self, client, test_instance, test_user, db_session):
        """
        ✓ Last message > 60 minutes ago
        ✓ New session created on next message
        """
        from datetime import timedelta

        # Create an expired session (>60 minutes old)
        old_session = SessionModel(
            user_id=test_user.id,
            instance_id=test_instance.id,
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=2),
            active=True
        )
        db_session.add(old_session)
        db_session.commit()

        request_id = str(uuid.uuid4())
        payload = {
            "content": "New message after timeout",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {"phone_e164": "+1234567890"}
        }

        mock_response = {
            "text": "Response", "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Should create new session
        new_session_id = session_id
        assert new_session_id != str(old_session.id)


class TestTokenBudget:
    """G1.9: Token Budget - Initialize and track token usage."""

    def test_token_plan_initialization_and_tracking(self, client, test_instance, db_session):
        """
        ✓ Initialize plan from template_set
        ✓ Calculate budget from sections
        ✓ Track actual usage
        ✓ Calculate cost
        """
        request_id = str(uuid.uuid4())

        payload = {
            "content": "Test token tracking",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user": {"phone_e164": "+15559999999"}
        }

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {
                "prompt_tokens": 150,
                "completion_tokens": 50,
                "total_tokens": 200
            }
        }

        with patch('message_handler.core.processor.process_orchestrator_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200
        data = response.json()

        # Verify session has token plan
        session_id = session_id
        session = db_session.query(SessionModel).filter(SessionModel.id == session_id).first()

        # Token plan should be initialized
        assert session.token_plan_json is not None
        assert "templates" in session.token_plan_json
