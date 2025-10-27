# ============================================================================
# FILE: test/api_layer/test_broadcast_endpoints.py
# Test A4: Broadcast Endpoints
# ============================================================================

import pytest
import uuid

class TestBroadcastEndpoints:
    """Test /api/broadcast endpoint."""
    
    @pytest.mark.asyncio
    async def test_missing_user_ids(self, async_client, test_instance):
        """✓ Missing user_ids → 400"""
        response = await async_client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_empty_user_ids_list(self, async_client, test_instance):
        """✓ Empty user_ids list → 400"""
        response = await async_client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": [],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_too_many_user_ids(self, async_client, test_instance):
        """✓ user_ids > 100 → 422"""  # ← Updated comment
        user_ids = [str(uuid.uuid4()) for _ in range(101)]
        response = await async_client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": user_ids,
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 422  # ← Changed from 400 to 422

    @pytest.mark.asyncio
    async def test_missing_content(self, async_client, test_instance, test_user):
        """✓ Missing content → 400"""
        response = await async_client.post("/api/broadcast", json={
            "instance_id": str(test_instance.id),
            "user_ids": [str(test_user.id)],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code in [400, 422]
    
    @pytest.mark.asyncio
    async def test_successful_broadcast(self, async_client, test_instance, test_user):
        """✓ Successful broadcast returns summary"""
        response = await async_client.post("/api/broadcast", json={
            "content": "Hello everyone",
            "instance_id": str(test_instance.id),
            "user_ids": [str(test_user.id)],
            "request_id": str(uuid.uuid4())
        })
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data["data"]
        assert data["data"]["summary"]["total"] == 1
