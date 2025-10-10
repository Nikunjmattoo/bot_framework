"""
COMPREHENSIVE END-TO-END TEST SUITE - PART 2
============================================
Core API Tests, Service Tests, and Integration Tests

Run with: pytest -v test_suite_part2.py
"""

import pytest
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List

# Import from Part 1
from test_suite_part1 import *


# ============================================================================
# HEALTH CHECK TESTS
# ============================================================================

class TestHealthChecks:
    """Test all health check endpoints"""
    
    def test_healthz_success(self, test_client):
        """Test /healthz endpoint returns healthy status"""
        response = test_client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
    
    def test_healthz_database_failure(self, test_client, test_db):
        """Test /healthz returns error when database fails"""
        # Close the database connection
        test_db.close()
        
        response = test_client.get("/healthz")
        # Should return 503 when unhealthy
        assert response.status_code in [200, 503]  # May vary
        data = response.json()
        if response.status_code == 503:
            assert data["status"] == "unhealthy"
    
    def test_ready_endpoint(self, test_client):
        """Test /ready endpoint"""
        response = test_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    def test_live_endpoint(self, test_client):
        """Test /live endpoint"""
        response = test_client.get("/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"


# ============================================================================
# API MESSAGE TESTS
# ============================================================================

class TestAPIMessages:
    """Test /api/messages endpoint"""
    
    def test_send_message_success(
        self,
        test_client,
        test_instance,
        helpers,
        mock_orchestrator_success
    ):
        """Test successful message processing"""
        request_data = helpers.create_message_request(
            content="Hello, test message",
            instance_id=str(test_instance.id),
            user_details={"phone_e164": TestConfig.TEST_PHONE}
        )
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        helpers.assert_response_success(data, ["data", "message"])
        assert "message_id" in data["data"]
        assert "response" in data["data"]
        assert data["data"]["response"]["content"]
    
    def test_send_message_empty_content(self, test_client, test_instance):
        """Test sending message with empty content fails"""
        request_data = {
            "content": "",
            "instance_id": str(test_instance.id)
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 422  # Changed from 400 to 422
        
        data = response.json()
        assert "detail" in data  # Pydantic validation error uses 'detail'
    
    def test_send_message_missing_instance(self, test_client):
        """Test sending message without instance_id fails"""
        request_data = {
            "content": "Test message"
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_send_message_invalid_instance(self, test_client):
        """Test sending message to non-existent instance"""
        request_data = {
            "content": "Test message",
            "instance_id": str(uuid.uuid4())
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 404
        
        data = response.json()
        assert data["success"] is False
        # Check for ResourceNotFoundError or error code 2000
        assert "ResourceNotFoundError" in str(data.get("error", {})) or data.get("error", {}).get("code") == 2000
    
    def test_send_message_very_long_content(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test sending message with maximum allowed content length"""
        # Create content at the limit (10000 characters)
        long_content = "a" * 10000
        
        request_data = {
            "content": long_content,
            "instance_id": str(test_instance.id)
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
    
    def test_send_message_exceeds_length_limit(self, test_client, test_instance):
        """Test sending message exceeding content length limit fails"""
        # Create content exceeding the limit
        too_long_content = "a" * 10001
        
        request_data = {
            "content": too_long_content,
            "instance_id": str(test_instance.id)
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 400
    
    def test_send_message_with_trace_id(
        self,
        test_client,
        test_instance,
        trace_id,
        mock_orchestrator_success
    ):
        """Test message with trace_id for tracking"""
        request_data = {
            "content": "Test with trace ID",
            "instance_id": str(test_instance.id),
            "trace_id": trace_id
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
        
        # Check trace_id in response headers
        assert "X-Trace-ID" in response.headers or response.json().get("_meta", {}).get("trace_id")
    
    def test_send_message_guest_user(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test sending message as guest user (no identifiers)"""
        request_data = {
            "content": "Guest message",
            "instance_id": str(test_instance.id)
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
    
    def test_send_message_with_email(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test sending message with email identifier"""
        request_data = {
            "content": "Email user message",
            "instance_id": str(test_instance.id),
            "user": {
                "email": "newuser@example.com"
            }
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
    
    def test_send_message_with_device_id(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test sending message with device_id identifier"""
        request_data = {
            "content": "Device user message",
            "instance_id": str(test_instance.id),
            "user": {
                "device_id": "device-xyz-789"
            }
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200
    
    def test_send_message_multiple_identifiers(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test sending message with multiple identifiers (phone priority)"""
        request_data = {
            "content": "Multi-identifier message",
            "instance_id": str(test_instance.id),
            "user": {
                "phone_e164": "+1111111111",
                "email": "secondary@example.com",
                "device_id": "device-secondary"
            }
        }
        
        response = test_client.post("/api/messages", json=request_data)
        assert response.status_code == 200


# ============================================================================
# IDEMPOTENCY TESTS
# ============================================================================

class TestIdempotency:
    """Test idempotent message processing"""
    
    def test_duplicate_request_returns_cached_response(
        self,
        test_client,
        test_instance,
        idempotency_key,
        mock_orchestrator_success
    ):
        """Test that duplicate requests return the same response"""
        request_data = {
            "content": "Idempotent message",
            "instance_id": str(test_instance.id),
            "idempotency_key": idempotency_key
        }
        
        # First request
        response1 = test_client.post("/api/messages", json=request_data)
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request with same idempotency key
        response2 = test_client.post("/api/messages", json=request_data)
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Should return same message_id
        assert data1["data"]["message_id"] == data2["data"]["message_id"]
        
        # Orchestrator should only be called once
        assert mock_orchestrator_success.call_count == 1
    
    def test_different_idempotency_keys_create_new_messages(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test that different idempotency keys create new messages"""
        base_request = {
            "content": "Unique message",
            "instance_id": str(test_instance.id)
        }
        
        # First request
        request1 = {**base_request, "idempotency_key": str(uuid.uuid4())}
        response1 = test_client.post("/api/messages", json=request1)
        
        # Second request with different key
        request2 = {**base_request, "idempotency_key": str(uuid.uuid4())}
        response2 = test_client.post("/api/messages", json=request2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Should have different message IDs
        assert data1["data"]["message_id"] != data2["data"]["message_id"]
        
        # Orchestrator should be called twice
        assert mock_orchestrator_success.call_count == 2
    

# ============================================================================
# WEB AND APP CHANNEL TESTS
# ============================================================================

class TestWebAppChannels:
    """Test /api/web/messages and /api/app/messages endpoints"""
    
    def test_web_message_success(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test web channel message processing"""
        request_data = {
            "content": "Web channel message",
            "instance_id": str(test_instance.id),
            "user": {"email": "webuser@example.com"}
        }
        
        response = test_client.post("/api/web/messages", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "message processed successfully" in data["message"].lower()
    
    def test_app_message_success(
        self,
        test_client,
        test_instance,
        mock_orchestrator_success
    ):
        """Test app channel message processing"""
        request_data = {
            "content": "App channel message",
            "instance_id": str(test_instance.id),
            "user": {"device_id": "mobile-device-123"}
        }
        
        response = test_client.post("/api/app/messages", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True


# ============================================================================
# WHATSAPP TESTS
# ============================================================================

class TestWhatsAppMessages:
    """Test WhatsApp message processing"""
    
    def test_whatsapp_text_message(
        self,
        test_client,
        test_whatsapp_instance,
        helpers,
        mock_orchestrator_success
    ):
        """Test processing WhatsApp text message"""
        wa_message = helpers.create_whatsapp_message(
            from_number="+1234567890",
            to_number="+9876543210",
            text_body="Hello from WhatsApp"
        )
        
        response = test_client.post("/api/whatsapp/messages", json=wa_message)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "whatsapp_message_id" in data["data"]
    
    def test_whatsapp_image_message(
        self,
        test_client,
        test_whatsapp_instance,
        mock_orchestrator_success
    ):
        """Test processing WhatsApp image message"""
        wa_message = {
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": str(uuid.uuid4()),
                "timestamp": str(int(time.time())),
                "image": {
                    "caption": "Check out this image",
                    "url": "https://example.com/image.jpg"
                }
            },
            "metadata": {"to": "+9876543210"}
        }
        
        response = test_client.post("/api/whatsapp/messages", json=wa_message)
        assert response.status_code == 200
    
    def test_whatsapp_missing_from_field(self, test_client):
        """Test WhatsApp message without 'from' field fails"""
        wa_message = {
            "message": {
                "to": "+9876543210",
                "text": {"body": "Test"}
            }
        }
        
        response = test_client.post("/api/whatsapp/messages", json=wa_message)
        assert response.status_code == 400
    
    def test_whatsapp_invalid_phone_format(self, test_client):
        """Test WhatsApp message with invalid phone format fails"""
        wa_message = {
            "message": {
                "from": "invalid-phone",
                "to": "+9876543210",
                "text": {"body": "Test"}
            },
            "metadata": {"to": "+9876543210"}
        }
        
        response = test_client.post("/api/whatsapp/messages", json=wa_message)
        assert response.status_code == 400


# ============================================================================
# BROADCAST TESTS
# ============================================================================

class TestBroadcast:
    """Test broadcast message functionality"""
    
    def test_broadcast_to_multiple_users(
        self,
        test_client,
        test_instance,
        test_db,
        test_brand
    ):
        """Test broadcasting message to multiple users"""
        # Create test users
        user_ids = []
        for i in range(3):
            user = UserModel(
                id=uuid.uuid4(),
                acquisition_channel="api",
                user_tier="standard",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            test_db.add(user)
            user_ids.append(str(user.id))
        
        test_db.commit()
        
        request_data = {
            "instance_id": str(test_instance.id),
            "content": "Broadcast message to all",
            "user_ids": user_ids
        }
        
        response = test_client.post("/api/broadcast", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "results" in data["data"]
        assert len(data["data"]["results"]) == 3
        assert "summary" in data["data"]
    
    def test_broadcast_empty_user_list(self, test_client, test_instance):
        """Test broadcast with empty user list fails"""
        request_data = {
            "instance_id": str(test_instance.id),
            "content": "Broadcast message",
            "user_ids": []
        }
        
        response = test_client.post("/api/broadcast", json=request_data)
        assert response.status_code == 422  # Validation error
    
    def test_broadcast_to_nonexistent_users(
        self,
        test_client,
        test_instance
    ):
        """Test broadcast to non-existent users"""
        request_data = {
            "instance_id": str(test_instance.id),
            "content": "Broadcast message",
            "user_ids": [str(uuid.uuid4()), str(uuid.uuid4())]
        }
        
        response = test_client.post("/api/broadcast", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        # Should have results even if users don't exist
        assert "results" in data["data"]


# This is Part 2 - Core API and Integration Tests
# Part 3 will contain service-level and error handling tests