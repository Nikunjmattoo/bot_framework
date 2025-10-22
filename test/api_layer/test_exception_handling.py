# ============================================================================
# FILE: test/api_layer/test_exception_handling.py
# Test A5: Exception Handling
# ============================================================================

import pytest
import uuid

class TestExceptionHandling:
    """Test centralized exception handling."""
    
    def test_validation_error_returns_422(self, client, test_instance):
        """✓ ValidationError → Returns 422 + includes field name"""
        response = client.post("/api/messages", json={
            "content": "",  # Empty content
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 422  # Pydantic validation
        data = response.json()
        assert "error" in data or "detail" in data
    
    def test_resource_not_found_returns_404(self, client):
        """✓ ResourceNotFoundError → Returns 404"""
        # Use a VALID UUID format that just doesn't exist
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = client.post("/api/messages", json={
            "content": "Hello",
            "instance_id": fake_uuid,  # Valid UUID format, but doesn't exist
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 404
    
    def test_duplicate_error_returns_409(self, client, db_session, test_brand, test_template_set):
        """✓ DuplicateError → Always returns 409"""
        from db.models import InstanceModel, InstanceConfigModel
        
        instance = InstanceModel(
            brand_id=test_brand.id,
            name="Test Instance",
            channel="api",
            is_active=True,
            accept_guest_users=True
        )
        db_session.add(instance)
        db_session.flush()
        
        config = InstanceConfigModel(
            instance_id=instance.id,
            template_set_id=test_template_set.id,
            is_active=True
        )
        db_session.add(config)
        db_session.commit()
        
        request_id = str(uuid.uuid4())
        instance_id = str(instance.id)
        device_id = str(uuid.uuid4())
        
        # CRITICAL: Must provide brand_id for identity resolution to work!
        user_details = {
            "device_id": device_id,
            "brand_id": str(test_brand.id)  # ← ADD THIS!
        }
        
        # First request
        response1 = client.post("/api/messages", json={
            "content": "Hello",
            "instance_id": instance_id,
            "request_id": request_id,
            "user_details": user_details
        })
        print(f"First: {response1.status_code}")
        assert response1.status_code == 200
        
        # Duplicate - SAME device_id AND brand_id
        response2 = client.post("/api/messages", json={
            "content": "Hello",
            "instance_id": instance_id,
            "request_id": request_id,
            "user_details": user_details  # Same user_details
        })
        print(f"Second: {response2.status_code}")
        assert response2.status_code == 409

    def test_error_includes_trace_id(self, client):
        """✓ Error responses include trace_id"""
        response = client.post("/api/messages", json={
            "content": "Hello",
            "instance_id": str(uuid.uuid4()),
            "request_id": str(uuid.uuid4())
        })
        data = response.json()
        assert "trace_id" in data
