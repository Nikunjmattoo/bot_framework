# ============================================================================
# FILE: test/api_layer/test_whatsapp_endpoints.py
# Test A3: WhatsApp Endpoints
# ============================================================================

import pytest
import uuid

class TestWhatsAppEndpoints:
    """Test /api/whatsapp/messages endpoint."""
    
    # ========================================================================
    # MESSAGE TYPES
    # ========================================================================
    
    
    def test_text_message(self, async_client, test_instance):
        """✓ Text message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test123",
                "text": {"body": "Hello WhatsApp"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    def test_image_message(self, async_client, test_instance):
        """✓ Image message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test_image",
                "type": "image",
                "image": {
                    "id": "image123",
                    "mime_type": "image/jpeg",
                    "caption": "Check this out!"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    def test_audio_message(self, async_client, test_instance):
        """✓ Audio message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test_audio",
                "type": "audio",
                "audio": {
                    "id": "audio123",
                    "mime_type": "audio/mpeg"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    def test_document_message(self, async_client, test_instance):
        """✓ Document message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test_doc",
                "type": "document",
                "document": {
                    "id": "doc123",
                    "filename": "report.pdf",
                    "mime_type": "application/pdf",
                    "caption": "Here's the report"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    
    def test_location_message(self, async_client, test_instance):
        """✓ Location message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test_location",
                "type": "location",
                "location": {
                    "latitude": 37.7749,
                    "longitude": -122.4194,
                    "name": "San Francisco",
                    "address": "San Francisco, CA"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    
    
    def test_contact_message(self, async_client, test_instance):
        """✓ Contact message"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test_contact",
                "type": "contacts",
                "contacts": [{
                    "name": {
                        "formatted_name": "John Doe",
                        "first_name": "John",
                        "last_name": "Doe"
                    },
                    "phones": [{
                        "phone": "+1555000000",
                        "type": "CELL"
                    }]
                }]
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    # ========================================================================
    # REQUIRED FIELDS
    # ========================================================================
    
    
    def test_missing_from_field(self, async_client, test_instance):
        """✓ Missing 'from' → 422"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "to": "+9876543210",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 422
    
    
    def test_missing_to_field(self, async_client, test_instance):
        """✓ Missing 'to' → 422"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 422
    
    
    def test_invalid_phone_format(self, async_client, test_instance):
        """✓ Invalid phone format → 422"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "invalid-phone",
                "to": "+9876543210",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 422
    
    # ========================================================================
    # INSTANCE RESOLUTION
    # ========================================================================
    
    
    def test_resolve_instance_by_recipient_number(self, async_client, test_whatsapp_instance):  # ← Changed fixture
        """✓ Resolve instance by recipient_number (to field)"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": test_whatsapp_instance.recipient_number,  # ← This will be "+9876543210"
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4())
            # No instance_id provided - should resolve from 'to' field
        })
        assert response.status_code == 200
    
    
    def test_resolve_instance_by_instance_id(self, async_client, test_instance):
        """✓ Resolve instance by instance_id in metadata"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    
    def test_no_matching_instance(self, async_client):
        """✓ No matching instance → 404"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+1999999999",  # ← Valid format, but no instance with this number
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 404
    
    # ========================================================================
    # USER RESOLUTION
    # ========================================================================
    
    
    def test_existing_whatsapp_user(self, async_client, test_instance, test_user):
        """✓ Existing WhatsApp user → resolve"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",  # test_user's phone
                "to": "+9876543210",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
    
    
    def test_new_whatsapp_user(self, async_client, test_instance):
        """✓ New WhatsApp user → create with phone"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+9999999999",  # New phone number
                "to": "+9876543210",
                "text": {"body": "Hello"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        # Should create new user if accept_guest_users=True
        assert response.status_code == 200
    
    # ========================================================================
    # CONTENT EXTRACTION
    # ========================================================================
    
    
    def test_extract_text_body(self, async_client, test_instance):
        """✓ Extract text body"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test",
                "text": {"body": "Test message content"}
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
        # Content should be extracted from text.body
    
    
    @pytest.mark.skip(reason="Attachment/media handling not implemented - future feature")
    def test_extract_caption_from_media(self, async_client, test_instance):
        """✓ Extract caption from media"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test",
                "type": "image",
                "image": {
                    "id": "img123",
                    "caption": "This is the caption"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
        # Caption should be extracted as content
    
    
    def test_extract_location_coordinates(self, async_client, test_instance):
        """✓ Extract location coordinates"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test",
                "type": "location",
                "location": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "name": "NYC"
                }
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
        # Location should be formatted as content
    
    
    def test_extract_contact_names(self, async_client, test_instance):
        """✓ Extract contact names"""
        response = async_client.post("/api/whatsapp/messages", json={
            "message": {
                "from": "+1234567890",
                "to": "+9876543210",
                "id": "wamid.test",
                "type": "contacts",
                "contacts": [{
                    "name": {
                        "formatted_name": "Jane Smith",
                        "first_name": "Jane"
                    }
                }]
            },
            "request_id": str(uuid.uuid4()),
            "instance_id": str(test_instance.id)
        })
        assert response.status_code == 200
        # Contact name should be extracted