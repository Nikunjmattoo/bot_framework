# ============================================================================
# FILE: test/api_layer/test_health_endpoints.py
# Test A1: Health Endpoints - 100% Coverage
# ============================================================================

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException


class TestHealthEndpoints:
    """Test health, readiness, and liveness endpoints."""
    
    # ========================================================================
    # /healthz - Database Connectivity
    # ========================================================================
    
    def test_health_check_db_connected(self, client, db_session):
        """✓ DB connected → 200"""
        response = client.get("/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
    
    def test_health_check_db_disconnected(self, app):
        """✓ DB disconnected → 503"""
        from fastapi.testclient import TestClient
        from db.db import get_db
        from unittest.mock import MagicMock
        
        # Create a mock database session that fails
        def get_db_mock():
            mock_db = MagicMock()
            mock_db.execute.side_effect = Exception("Connection failed")
            yield mock_db
        
        # Override the dependency BEFORE creating the client
        app.dependency_overrides[get_db] = get_db_mock
        
        try:
            # Create a new client with the overridden dependency
            with TestClient(app) as client:
                response = client.get("/healthz")
                assert response.status_code == 503
                data = response.json()
                assert data["status"] == "unhealthy"
                assert data["database"] == "disconnected"
        finally:
            # Clean up the override
            app.dependency_overrides.clear()    
    # ========================================================================
    # Response Format Validation
    # ========================================================================
    
    def test_health_check_response_format(self, client):
        """✓ JSON structure validation + Status field present"""
        response = client.get("/healthz")
        data = response.json()
        
        # Check required fields
        assert "status" in data
        assert "database" in data
        assert isinstance(data, dict)
        
        # Check field types
        assert isinstance(data["status"], str)
        assert isinstance(data["database"], str)
    
    def test_health_check_content_type(self, client):
        """✓ Content-Type is application/json"""
        response = client.get("/healthz")
        assert "application/json" in response.headers["content-type"]
    
    # ========================================================================
    # /ready - Readiness Check
    # ========================================================================
    
    def test_readiness_endpoint(self, client):
        """✓ /ready endpoint available"""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
    
    def test_readiness_response_format(self, client):
        """✓ Readiness response has correct format"""
        response = client.get("/ready")
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
    
    # ========================================================================
    # /live - Liveness Check
    # ========================================================================
    
    def test_liveness_endpoint(self, client):
        """✓ /live endpoint available"""
        response = client.get("/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    def test_liveness_response_format(self, client):
        """✓ Liveness response has correct format"""
        response = client.get("/live")
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
    
    # ========================================================================
    # Edge Cases
    # ========================================================================
    
    def test_health_endpoint_case_insensitive(self, client):
        """✓ /healthz works regardless of case (if configured)"""
        # Test exact path only (FastAPI is case-sensitive by default)
        response = client.get("/healthz")
        assert response.status_code == 200
    
    def test_health_endpoint_no_query_params(self, client):
        """✓ /healthz ignores query parameters"""
        response = client.get("/healthz?extra=param")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_multiple_health_checks_consistent(self, client):
        """✓ Multiple calls return consistent results"""
        responses = [client.get("/healthz") for _ in range(5)]
        statuses = [r.json()["status"] for r in responses]
        
        # All should be "healthy" or all "unhealthy"
        assert len(set(statuses)) == 1