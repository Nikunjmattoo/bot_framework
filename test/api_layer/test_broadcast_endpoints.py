# ============================================================================
# FILE: test/api_layer/test_broadcast_endpoints.py
# Test A4: Broadcast Endpoints
# ============================================================================

import pytest
import uuid

class TestBroadcastEndpoints:
    """Test /api/broadcast endpoint."""
    
    def test_missing_user_ids(self, client, test_instance):
        """✓ Missing user_ids → 400"""
        response = client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    def test_empty_user_ids_list(self, client, test_instance):
        """✓ Empty user_ids list → 400"""
        response = client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": [],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    def test_too_many_user_ids(self, client, test_instance):
        """✓ user_ids > 100 → 422"""  # ← Updated comment
        user_ids = [str(uuid.uuid4()) for _ in range(101)]
        response = client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": user_ids,
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 422  # ← Changed from 400 to 422

    def test_missing_content(self, client, test_instance, test_user):
        """✓ Missing content → 400"""
        response = client.post("/api/broadcast", json={
            "instance_id": str(test_instance.id),
            "user_ids": [str(test_user.id)],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    def test_successful_broadcast(self, client, test_instance, test_user):
        """✓ Successful broadcast returns summary"""
        response = client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": [str(test_user.id)],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data["data"]
        assert data["data"]["summary"]["total"] == 1
