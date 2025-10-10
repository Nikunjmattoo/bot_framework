"""
COMPREHENSIVE END-TO-END TEST SUITE - PART 1
============================================
Foundation, Configuration, and Test Fixtures

This is a LEVEL 10/10 test suite covering:
- All modules and components
- All error paths and exception handling
- Edge cases and boundary conditions
- Integration scenarios
- Performance and concurrency testing
"""

import pytest
import uuid
import time
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, patch, MagicMock
from contextlib import contextmanager
import threading
import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Import all application components
from main import app
from db.db import get_db, SessionLocal
from db.models.base import Base
from db.models.users import UserModel
from db.models.user_identifiers import UserIdentifierModel
from db.models.brands import BrandModel
from db.models.instances import InstanceModel
from db.models.instance_configs import InstanceConfigModel
from db.models.template_sets import TemplateSetModel
from db.models.llm_models import LLMModel
from db.models.sessions import SessionModel
from db.models.messages import MessageModel
from db.models.idempotency_locks import IdempotencyLockModel
from db.models.templates import TemplateModel

from message_handler.exceptions import *
from message_handler.services import *
from message_handler.handlers import *
from message_handler.core.processor import process_core
from message_handler.utils import *


# ============================================================================
# TEST CONFIGURATION
# ============================================================================

class TestConfig:
    """Centralized test configuration"""
    
    # Database
    TEST_DB_URL = "sqlite:///:memory:"
    
    # Test data
    TEST_BRAND_NAME = "Test Brand"
    TEST_INSTANCE_NAME = "Test Instance"
    TEST_PHONE = "+1234567890"
    TEST_EMAIL = "test@example.com"
    TEST_DEVICE_ID = "device-123"
    
    # Timing
    DEFAULT_TIMEOUT = 5
    RETRY_DELAY = 0.1
    MAX_RETRIES = 3
    
    # Performance
    CONCURRENT_REQUESTS = 10
    STRESS_TEST_ITERATIONS = 100


# ============================================================================
# DATABASE FIXTURES (using conftest.py)
# ============================================================================

# Note: test_engine and test_db fixtures are now in conftest.py
# They will be automatically available to all tests


@pytest.fixture(scope="function")
def test_client(test_db):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


# ============================================================================
# DATA FIXTURES - BRANDS & INSTANCES
# ============================================================================

@pytest.fixture
def test_brand(test_db):
    """Create a test brand"""
    brand = BrandModel(
        id=uuid.uuid4(),
        name=TestConfig.TEST_BRAND_NAME,
        phone_number=TestConfig.TEST_PHONE,
        website="https://test-brand.com",
        extra_config={"test": True},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(brand)
    test_db.commit()
    test_db.refresh(brand)
    return brand


@pytest.fixture
def test_llm_model(test_db):
    """Create a test LLM model"""
    llm_model = LLMModel(
        id=uuid.uuid4(),
        name="test-gpt-4",
        provider="openai",
        max_tokens=8000,
        details={"version": "4.0"},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(llm_model)
    test_db.commit()
    test_db.refresh(llm_model)
    return llm_model


@pytest.fixture
def test_template_set(test_db, test_llm_model):
    """Create a test template set"""
    template_set = TemplateSetModel(
        id="test_template_set_v1",
        name="Test Template Set",
        description="Template set for testing",
        functions={
            "intent": "intent_detection_v1",
            "compose": "response_generation_v1"
        },
        llm_model_id=test_llm_model.id,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(template_set)
    test_db.commit()
    test_db.refresh(template_set)
    return template_set


@pytest.fixture
def test_templates(test_db):
    """Create test templates"""
    templates = [
        TemplateModel(
            id=uuid.uuid4(),
            template_key="intent_detection_v1",
            name="Intent Detection",
            description="Detects user intent",
            modules={
                "intent_classifier": {
                    "budget_tokens": 1000,
                    "type": "llm",
                    "sequence": 1
                }
            },
            version="1.0",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        ),
        TemplateModel(
            id=uuid.uuid4(),
            template_key="response_generation_v1",
            name="Response Generation",
            description="Generates responses",
            modules={
                "response_generator": {
                    "budget_tokens": 2000,
                    "type": "llm",
                    "sequence": 1
                }
            },
            version="1.0",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
    ]
    
    for template in templates:
        test_db.add(template)
    test_db.commit()
    
    for template in templates:
        test_db.refresh(template)
    
    return templates


@pytest.fixture
def test_instance(test_db, test_brand, test_template_set):
    """Create a test instance with configuration"""
    instance = InstanceModel(
        id=uuid.uuid4(),
        brand_id=test_brand.id,
        name=TestConfig.TEST_INSTANCE_NAME,
        channel="api",
        is_active=True,
        accept_guest_users=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(instance)
    test_db.flush()
    
    # Create instance config
    config = InstanceConfigModel(
        id=uuid.uuid4(),
        instance_id=instance.id,
        template_set_id=test_template_set.id,
        temperature=0.7,
        timeout_ms=15000,
        session_timeout_seconds=300,
        use_rag=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(config)
    test_db.commit()
    test_db.refresh(instance)
    
    return instance


@pytest.fixture
def test_whatsapp_instance(test_db, test_brand, test_template_set):
    """Create a WhatsApp test instance"""
    instance = InstanceModel(
        id=uuid.uuid4(),
        brand_id=test_brand.id,
        name="WhatsApp Instance",
        channel="whatsapp",
        recipient_number="+9876543210",
        is_active=True,
        accept_guest_users=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(instance)
    test_db.flush()
    
    config = InstanceConfigModel(
        id=uuid.uuid4(),
        instance_id=instance.id,
        template_set_id=test_template_set.id,
        temperature=0.7,
        timeout_ms=15000,
        session_timeout_seconds=300,
        use_rag=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(config)
    test_db.commit()
    test_db.refresh(instance)
    
    return instance


# ============================================================================
# USER FIXTURES
# ============================================================================

@pytest.fixture
def test_user(test_db, test_brand):
    """Create a test user with identifiers"""
    user = UserModel(
        id=uuid.uuid4(),
        acquisition_channel="api",
        user_tier="standard",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.flush()
    
    # Add phone identifier
    phone_id = UserIdentifierModel(
        id=uuid.uuid4(),
        user_id=user.id,
        brand_id=test_brand.id,
        identifier_type="phone_e164",
        identifier_value=TestConfig.TEST_PHONE,
        channel="api",
        verified=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(phone_id)
    
    # Add email identifier
    email_id = UserIdentifierModel(
        id=uuid.uuid4(),
        user_id=user.id,
        brand_id=test_brand.id,
        identifier_type="email",
        identifier_value=TestConfig.TEST_EMAIL,
        channel="api",
        verified=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(email_id)
    
    test_db.commit()
    test_db.refresh(user)
    
    return user


@pytest.fixture
def test_guest_user(test_db):
    """Create a guest user"""
    user = UserModel(
        id=uuid.uuid4(),
        acquisition_channel="guest",
        user_tier="guest",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


# ============================================================================
# SESSION FIXTURES
# ============================================================================

@pytest.fixture
def test_session(test_db, test_user, test_instance):
    """Create a test session"""
    session = SessionModel(
        id=uuid.uuid4(),
        user_id=test_user.id,
        instance_id=test_instance.id,
        started_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        active=True,
        source="api",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    test_db.add(session)
    test_db.commit()
    test_db.refresh(session)
    return session


# ============================================================================
# MOCK FIXTURES
# ============================================================================

@pytest.fixture
def mock_orchestrator_success():
    """Mock successful orchestrator response"""
    with patch('message_handler.core.processor.process_orchestrator_message') as mock:
        mock.return_value = {
            "text": "This is a test response from the orchestrator",
            "status": "success",
            "token_usage": {
                "prompt_in": 100,
                "completion_out": 50
            },
            "template_key": "response_generation_v1",
            "function_name": "compose",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        yield mock


@pytest.fixture
def mock_orchestrator_error():
    """Mock orchestrator error"""
    with patch('message_handler.core.processor.process_orchestrator_message') as mock:
        mock.side_effect = Exception("Orchestrator service unavailable")
        yield mock


@pytest.fixture
def mock_orchestrator_timeout():
    """Mock orchestrator timeout"""
    with patch('message_handler.core.processor.process_orchestrator_message') as mock:
        def timeout_side_effect(*args, **kwargs):
            time.sleep(2)
            raise TimeoutError("Orchestrator timeout")
        mock.side_effect = timeout_side_effect
        yield mock


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def trace_id():
    """Generate a unique trace ID for each test"""
    return str(uuid.uuid4())


@pytest.fixture
def idempotency_key():
    """Generate a unique idempotency key"""
    return str(uuid.uuid4())


@contextmanager
def assert_time_limit(seconds: float):
    """Context manager to assert operation completes within time limit"""
    start = time.time()
    yield
    duration = time.time() - start
    assert duration < seconds, f"Operation took {duration:.2f}s, expected < {seconds}s"


@pytest.fixture
def performance_tracker():
    """Track performance metrics"""
    class PerformanceTracker:
        def __init__(self):
            self.metrics = []
        
        def record(self, operation: str, duration: float, success: bool = True):
            self.metrics.append({
                "operation": operation,
                "duration": duration,
                "success": success,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        def get_stats(self, operation: Optional[str] = None):
            if operation:
                metrics = [m for m in self.metrics if m["operation"] == operation]
            else:
                metrics = self.metrics
            
            if not metrics:
                return None
            
            durations = [m["duration"] for m in metrics]
            return {
                "count": len(metrics),
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "success_rate": sum(1 for m in metrics if m["success"]) / len(metrics)
            }
    
    return PerformanceTracker()


# ============================================================================
# TEST HELPERS
# ============================================================================

class TestHelpers:
    """Collection of test helper methods"""
    
    @staticmethod
    def create_message_request(
        content: str,
        instance_id: str,
        user_details: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a standard message request"""
        request = {
            "content": content,
            "instance_id": instance_id
        }
        
        if user_details:
            request["user"] = user_details
        if idempotency_key:
            request["idempotency_key"] = idempotency_key
        if trace_id:
            request["trace_id"] = trace_id
        
        return request
    
    @staticmethod
    def create_whatsapp_message(
        from_number: str,
        to_number: str,
        text_body: str,
        message_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a WhatsApp message"""
        return {
            "message": {
                "from": from_number,
                "to": to_number,
                "id": message_id or str(uuid.uuid4()),
                "timestamp": str(int(time.time())),
                "text": {
                    "body": text_body
                }
            },
            "metadata": {
                "to": to_number
            }
        }
    
    @staticmethod
    def assert_response_success(response, expected_keys: Optional[List[str]] = None):
        """Assert response is successful and has expected structure"""
        assert "success" in response
        assert response["success"] is True
        
        if expected_keys:
            for key in expected_keys:
                assert key in response, f"Missing key: {key}"
    
    @staticmethod
    def assert_error_response(
        response,
        expected_code: Optional[str] = None,
        expected_status: Optional[int] = None
    ):
        """Assert response is an error with expected properties"""
        assert "success" in response
        assert response["success"] is False
        assert "error" in response
        
        if expected_code:
            assert response["error"]["code"] == expected_code
        
        if expected_status:
            assert response.get("status_code") == expected_status


@pytest.fixture
def helpers():
    """Provide test helpers"""
    return TestHelpers


# ============================================================================
# CLEANUP FIXTURES
# ============================================================================

@pytest.fixture(autouse=True)
def cleanup_after_test(test_db):
    """Cleanup database after each test"""
    yield
    # Rollback any uncommitted changes
    test_db.rollback()


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment once per session"""
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)
    
    yield
    
    # Cleanup after all tests
    pass


# ============================================================================
# PARAMETERIZATION FIXTURES
# ============================================================================

@pytest.fixture(params=[
    "api",
    "web",
    "app"
])
def channel(request):
    """Parameterized channel fixture"""
    return request.param


@pytest.fixture(params=[
    {"phone_e164": TestConfig.TEST_PHONE},
    {"email": TestConfig.TEST_EMAIL},
    {"device_id": TestConfig.TEST_DEVICE_ID},
    {"phone_e164": TestConfig.TEST_PHONE, "email": TestConfig.TEST_EMAIL}
])
def user_details(request):
    """Parameterized user details fixture"""
    return request.param


# This is Part 1 of the test suite - Foundation & Setup
# Next parts will contain actual test cases