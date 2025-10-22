# ============================================================================
# FILE: test/conftest.py
# Shared fixtures for ALL test suites
# ============================================================================

import pytest
import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from dotenv import load_dotenv
import uuid

# Load test environment
load_dotenv()

# CRITICAL: Use test database ONLY
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test"
)

# Import after env is loaded and path is fixed
from api.app import create_app
from db.models.base import Base
from db.models import (
    UserModel, BrandModel, InstanceModel, InstanceConfigModel,
    SessionModel, MessageModel, TemplateSetModel, TemplateModel,
    LLMModel, UserIdentifierModel, IdempotencyLockModel
)

# ... rest of conftest.py remains the same
@pytest.fixture(scope="session")
def test_engine():
    """Create test database engine (session-scoped, reused)."""
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True
    )
    return engine

@pytest.fixture(scope="session")
def setup_test_database(test_engine):
    """Setup test database schema once per test session."""
    # Drop all tables
    Base.metadata.drop_all(bind=test_engine)
    # Create all tables
    Base.metadata.create_all(bind=test_engine)
    
    yield
    
    # Cleanup after all tests
    Base.metadata.drop_all(bind=test_engine)

@pytest.fixture(scope="function")
def db_session(test_engine, setup_test_database):
    """Provide a transactional database session per test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection)
    session = SessionLocal()
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """Provide FastAPI test client with test database."""
    app = create_app()
    
    # Override database dependency
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from db.db import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def test_brand(db_session):
    """Create a test brand."""
    brand = BrandModel(
        name="Test Brand",
        phone_number="+1234567890",
        website="https://testbrand.com"
    )
    db_session.add(brand)
    db_session.commit()
    db_session.refresh(brand)
    return brand

@pytest.fixture
def test_llm_model(db_session):
    """Create a test LLM model."""
    llm_model = LLMModel(
        name="gpt-4",
        provider="openai",
        api_model_name="gpt-4",
        max_tokens=8192,
        temperature=0.7
    )
    db_session.add(llm_model)
    db_session.commit()
    db_session.refresh(llm_model)
    return llm_model

@pytest.fixture
def test_template(db_session, test_llm_model):
    """Create a test template."""
    template = TemplateModel(
        template_key="test_template",
        name="Test Template",
        sections=[
            {"key": "system", "budget_tokens": 500},
            {"key": "user", "budget_tokens": 1000}
        ],
        llm_model_id=test_llm_model.id
    )
    db_session.add(template)
    db_session.commit()
    db_session.refresh(template)
    return template

@pytest.fixture
def test_template_set(db_session, test_template, test_llm_model):
    """Create a test template set."""
    template_set = TemplateSetModel(
        id="test_template_set",
        name="Test Template Set",
        functions={"response": test_template.template_key}
    )
    template_set.llm_model_id = test_llm_model.id
    db_session.add(template_set)
    db_session.commit()
    db_session.refresh(template_set)
    return template_set

@pytest.fixture
def test_instance(db_session, test_brand, test_template_set):
    """Create a test instance."""
    instance = InstanceModel(
        brand_id=test_brand.id,
        name="Test Instance",
        channel="api",
        is_active=True,
        accept_guest_users=True
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    
    # Create instance config
    config = InstanceConfigModel(
        instance_id=instance.id,
        template_set_id=test_template_set.id,
        is_active=True
    )
    db_session.add(config)
    db_session.commit()
    
    return instance

@pytest.fixture
def test_instance_no_guest(db_session, test_brand, test_template_set):
    """Create a test instance that doesn't accept guests."""
    instance = InstanceModel(
        brand_id=test_brand.id,
        name="No Guest Instance",
        channel="api",
        is_active=True,
        accept_guest_users=False
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    
    config = InstanceConfigModel(
        instance_id=instance.id,
        template_set_id=test_template_set.id,
        is_active=True
    )
    db_session.add(config)
    db_session.commit()
    
    return instance

@pytest.fixture
def test_whatsapp_instance(db_session, test_brand, test_template_set):
    """Create a WhatsApp instance."""
    instance = InstanceModel(
        brand_id=test_brand.id,
        name="WhatsApp Instance",
        channel="whatsapp",
        recipient_number="+9876543210",
        is_active=True,
        accept_guest_users=True
    )
    db_session.add(instance)
    db_session.commit()
    db_session.refresh(instance)
    
    config = InstanceConfigModel(
        instance_id=instance.id,
        template_set_id=test_template_set.id,
        is_active=True
    )
    db_session.add(config)
    db_session.commit()
    
    return instance

@pytest.fixture
def test_user(db_session, test_brand):
    """Create a test user with identifiers."""
    user = UserModel(
        acquisition_channel="api",
        user_tier="standard"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    
    # Add phone identifier
    identifier = UserIdentifierModel(
        user_id=user.id,
        brand_id=test_brand.id,
        identifier_type="phone_e164",
        identifier_value="+1234567890",
        channel="api",
        verified=True
    )
    db_session.add(identifier)
    db_session.commit()
    
    return user

@pytest.fixture
def test_session(db_session, test_user, test_instance):
    """Create a test session."""
    from datetime import datetime, timezone
    
    session = SessionModel(
        user_id=test_user.id,
        instance_id=test_instance.id,
        started_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        active=True
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    return session

@pytest.fixture
def app():
    """FastAPI application instance for testing."""
    from main import app  # Adjust import path to wherever your FastAPI app is defined
    return app

@pytest.fixture(autouse=True)
def mock_langfuse():
    """Mock Langfuse telemetry globally for all tests."""
    with patch('telemetry.langfuse_config.langfuse_client') as mock:
        mock_trace = MagicMock()
        mock.trace.return_value = mock_trace
        yield mock