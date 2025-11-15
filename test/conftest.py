# ============================================================================
# FILE: test/conftest.py
# Shared fixtures for ALL test suites
# ============================================================================

import pytest
import pytest_asyncio
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
from httpx import AsyncClient, ASGITransport
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
    # SQLite doesn't support pool_size, max_overflow parameters
    # Use conditional configuration based on database type
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine(
            TEST_DATABASE_URL,
            connect_args={"check_same_thread": False}  # Required for SQLite
        )
    else:
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
def async_client(db_session):
    """
    Provide async FastAPI test client for testing async endpoints.

    Note: Despite the name, this returns a regular TestClient which can handle
    async endpoints automatically. FastAPI's TestClient uses anyio to run async
    endpoints synchronously, so you don't need await in your tests.
    """
    # Simply return the same as the client fixture - TestClient handles async endpoints
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


# ============================================================================
# ORCHESTRATOR-SPECIFIC FIXTURES
# ============================================================================

@pytest.fixture
def test_llm_model_orchestrator(db_session):
    """Create test LLM model for orchestrator tests."""
    from decimal import Decimal
    model = LLMModel(
        name="Llama 3.1 70B (Groq)",
        provider="groq",
        api_model_name="llama-3.1-70b-versatile",
        max_tokens=8000,
        temperature=Decimal("0.7"),
        input_price_per_1k=Decimal("0.0001"),
        output_price_per_1k=Decimal("0.0002")
    )
    db_session.add(model)
    db_session.commit()
    return model


@pytest.fixture
def test_template_full(db_session, test_llm_model_orchestrator):
    """Create full test intent template with all sections."""
    template = TemplateModel(
        template_key="intent_v1_test",
        name="Intent Detection Template v1 Test",
        description="Full template for testing",
        sections=[
            {
                "key": "system_role",
                "sequence": 1,
                "budget_tokens": 150,
                "content": "You are an intent classifier for a conversational AI assistant."
            },
            {
                "key": "intent_types",
                "sequence": 2,
                "budget_tokens": 350,
                "content": "## INTENT TYPES (8 total):\n\n**Self-Respond Intents (4)**:\n1. greeting\n2. goodbye\n3. gratitude\n4. chitchat\n\n**Brain-Required Intents (4)**:\n5. action\n6. help\n7. response\n8. unknown"
            },
            {
                "key": "self_respond_logic",
                "sequence": 3,
                "budget_tokens": 250,
                "content": "## SELF-RESPONSE vs BRAIN:\n\nIf ALL intents are self-respond types, set self_response = true"
            },
            {
                "key": "context",
                "sequence": 4,
                "budget_tokens": 200,
                "content": "## CONVERSATION CONTEXT:\n\n**Session Summary:**\n{{session_summary}}\n\n**User ID:** {{user_id}}\n**Session ID:** {{session_id}}"
            },
            {
                "key": "output_format",
                "sequence": 5,
                "budget_tokens": 400,
                "content": '## OUTPUT FORMAT:\n\nReturn ONLY valid JSON:\n\n{\n  "intents": [...],\n  "response_text": "text or null",\n  "self_response": true|false,\n  "reasoning": "explanation"\n}'
            },
            {
                "key": "user_message",
                "sequence": 6,
                "budget_tokens": 200,
                "content": "## CLASSIFY THIS MESSAGE:\n\n**User Message:** {{user_message}}"
            }
        ],
        llm_model_id=test_llm_model_orchestrator.id,
        version="1.0",
        is_active=True
    )
    db_session.add(template)
    db_session.commit()
    return template


@pytest.fixture
def test_session_orchestrator(db_session, test_user, test_instance):
    """Create test session for orchestrator tests."""
    import uuid
    from datetime import datetime, timezone

    session_id = str(uuid.uuid4())

    session = SessionModel(
        id=session_id,
        user_id=test_user.id,  # Use actual test user
        instance_id=test_instance.id,  # Use actual test instance
        active=True,
        started_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db_session.add(session)
    db_session.commit()
    return session


@pytest.fixture
def test_messages_orchestrator(db_session, test_session_orchestrator):
    """Create test messages for context."""
    import uuid
    from datetime import datetime, timezone
    
    messages = []
    message_data = [
        ("user", "Hi there"),
        ("assistant", "Hello! How can I help?"),
        ("user", "Check my order"),
        ("assistant", "I'll check that for you")
    ]
    
    for i, (role, content) in enumerate(message_data):
        msg = MessageModel(
            id=str(uuid.uuid4()),
            session_id=test_session_orchestrator.id,
            role=role,
            content=content,
            message_type="text",
            channel=test_session_orchestrator.channel,
            created_at=datetime.now(timezone.utc)
        )
        messages.append(msg)
        db_session.add(msg)
    
    db_session.commit()
    return messages


@pytest.fixture
def base_adapter_payload(test_session_orchestrator, test_template_full, test_llm_model_orchestrator, test_brand):
    """Create base adapter payload for orchestrator tests."""
    import uuid

    return {
        "trace_id": str(uuid.uuid4()),
        "routing": {
            "instance_id": test_session_orchestrator.instance_id,
            "brand_id": test_brand.id  # ✅ Get from test_brand, not session
        },
        "message": {
            "content": "Hello",
            "sender_user_id": test_session_orchestrator.user_id,
            "channel": "whatsapp"  # ✅ Hardcode channel
        },
        "session_id": test_session_orchestrator.id,
        "policy": {
            "auth_state": "channel_verified",
            "can_call_tools": True
        },
        "template": {
            "json": {
                "intent": {
                    "template": "intent_v1_test"
                }
            }
        },
        "model": {
            "llm_model_id": str(test_llm_model_orchestrator.id),
            "llm_model_name": test_llm_model_orchestrator.name,
            "api_model_name": test_llm_model_orchestrator.api_model_name,
            "provider": test_llm_model_orchestrator.provider,
            "temperature": 0.7,
            "max_tokens": test_llm_model_orchestrator.max_tokens
        },
        "llm_runtime": {  # ✅ ADD MISSING LLM_RUNTIME FIELD
            "provider": test_llm_model_orchestrator.provider,
            "api_model_name": test_llm_model_orchestrator.api_model_name,
            "temperature": 0.7,
            "max_tokens": test_llm_model_orchestrator.max_tokens
        },
        "token_plan": {
            "templates": {
                "intent_v1_test": {
                    "function": "intent",
                    "template_key": "intent_v1_test",
                    "llm_model_id": str(test_llm_model_orchestrator.id),
                    "llm_model_name": test_llm_model_orchestrator.name,
                    "api_model_name": test_llm_model_orchestrator.api_model_name,
                    "provider": test_llm_model_orchestrator.provider,
                    "temperature": 0.7,
                    "total_budget": 1550
                }
            }
        }
    }
# LLM Response Fixtures for Orchestrator Tests

@pytest.fixture
def llm_response_greeting():
    """LLM response for greeting intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": null,
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Clear greeting from user"
            }],
            "response_text": "Hello! How can I help you today?",
            "self_response": true,
            "reasoning": "Simple greeting - responding directly"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 50,
            "total": 550
        }
    }


@pytest.fixture
def llm_response_goodbye():
    """LLM response for goodbye intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "goodbye",
                "canonical_intent": null,
                "confidence": 0.97,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User ending conversation"
            }],
            "response_text": "Goodbye! Have a great day!",
            "self_response": true,
            "reasoning": "Simple goodbye - responding directly"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 45,
            "total": 545
        }
    }


@pytest.fixture
def llm_response_gratitude():
    """LLM response for gratitude intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "gratitude",
                "canonical_intent": null,
                "confidence": 0.96,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User expressed thanks"
            }],
            "response_text": "You're welcome! Is there anything else I can help you with?",
            "self_response": true,
            "reasoning": "Gratitude - responding directly"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 55,
            "total": 555
        }
    }


@pytest.fixture
def llm_response_chitchat():
    """LLM response for chitchat intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "chitchat",
                "canonical_intent": null,
                "confidence": 0.95,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User asking casual question"
            }],
            "response_text": "I'm doing well, thank you for asking! How can I assist you?",
            "self_response": true,
            "reasoning": "Chitchat - responding directly"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 60,
            "total": 560
        }
    }


@pytest.fixture
def llm_response_action():
    """LLM response for action intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "action",
                "canonical_intent": "check_order_status",
                "canonical_intent_candidates": ["check_order_status", "view_order"],
                "confidence": 0.94,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User wants to check order status"
            }],
            "response_text": null,
            "self_response": false,
            "reasoning": "Action intent requires brain processing"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 60,
            "total": 560
        }
    }


@pytest.fixture
def llm_response_help():
    """LLM response for help intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "help",
                "canonical_intent": null,
                "confidence": 0.93,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User needs help"
            }],
            "response_text": null,
            "self_response": false,
            "reasoning": "Help intent requires brain processing"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 45,
            "total": 545
        }
    }

@pytest.fixture
def llm_response_fallback():
    """LLM response for fallback intent."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "unknown",
                "canonical_intent": "unknown_query",
                "confidence": 0.92,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "User query not understood, needs fallback handling"
            }],
            "response_text": null,
            "self_response": false,
            "reasoning": "Fallback intent requires brain processing"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 50,
            "total": 550
        }
    }
@pytest.fixture
def llm_response_multi_intent_mixed():
    """LLM response for mixed multiple intents."""
    return {
        "content": """{
            "intents": [
                {
                    "intent_type": "gratitude",
                    "canonical_intent": null,
                    "confidence": 0.97,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "User expressed thanks"
                },
                {
                    "intent_type": "action",
                    "canonical_intent": "check_order_status",
                    "canonical_intent_candidates": ["check_order_status", "view_order_status"],
                    "confidence": 0.94,
                    "entities": {},
                    "sequence_order": 2,
                    "reasoning": "User wants to check order"
                }
            ],
            "response_text": null,
            "self_response": false,
            "reasoning": "Mixed intents - action requires brain processing"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 80,
            "total": 580
        }
    }


@pytest.fixture
def llm_response_multi_intent_self_respond():
    """LLM response for multiple self-respond intents."""
    return {
        "content": """{
            "intents": [
                {
                    "intent_type": "gratitude",
                    "canonical_intent": null,
                    "confidence": 0.97,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "User expressed thanks"
                },
                {
                    "intent_type": "goodbye",
                    "canonical_intent": null,
                    "confidence": 0.98,
                    "entities": {},
                    "sequence_order": 2,
                    "reasoning": "User ending conversation"
                }
            ],
            "response_text": "You're welcome! Goodbye and have a great day!",
            "self_response": true,
            "reasoning": "Both gratitude and goodbye are self-respond"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 85,
            "total": 585
        }
    }


@pytest.fixture
def llm_response_multi_action():
    """LLM response for multiple action intents."""
    return {
        "content": """{
            "intents": [
                {
                    "intent_type": "action",
                    "canonical_intent": "create_profile",
                    "confidence": 0.96,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "User wants to create profile first"
                },
                {
                    "intent_type": "action",
                    "canonical_intent": "apply_for_job",
                    "confidence": 0.93,
                    "entities": {},
                    "sequence_order": 2,
                    "reasoning": "User wants to apply for job after"
                }
            ],
            "response_text": null,
            "self_response": false,
            "reasoning": "Multiple sequential actions require brain processing"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 90,
            "total": 590
        }
    }


@pytest.fixture
def llm_response_low_confidence():
    """LLM response with low confidence intents."""
    return {
        "content": """{
            "intents": [
                {
                    "intent_type": "action",
                    "canonical_intent": "unknown_action",
                    "confidence": 0.45,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "Unclear what user wants"
                }
            ],
            "response_text": null,
            "self_response": false,
            "reasoning": "Low confidence intent"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 50,
            "total": 550
        }
    }


@pytest.fixture
def llm_response_single_low_confidence():
    """LLM response with single medium confidence intent."""
    return {
        "content": """{
            "intents": [
                {
                    "intent_type": "action",
                    "canonical_intent": "check_order",
                    "confidence": 0.75,
                    "entities": {},
                    "sequence_order": 1,
                    "reasoning": "Somewhat clear but ambiguous"
                }
            ],
            "response_text": null,
            "self_response": false,
            "reasoning": "Single intent with medium confidence"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 50,
            "total": 550
        }
    }


@pytest.fixture
def llm_response_invalid_json():
    """Invalid JSON response from LLM."""
    return {
        "content": "This is not valid JSON {broken",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 10,
            "total": 510
        }
    }


@pytest.fixture
def llm_response_missing_intents():
    """LLM response missing intents field."""
    return {
        "content": """{
            "response_text": "Hello!",
            "self_response": true,
            "reasoning": "Missing intents field"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 20,
            "total": 520
        }
    }


@pytest.fixture
def llm_response_empty_intents():
    """LLM response with empty intents list."""
    return {
        "content": """{
            "intents": [],
            "response_text": null,
            "self_response": false,
            "reasoning": "Empty intents"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 15,
            "total": 515
        }
    }


@pytest.fixture
def llm_response_missing_confidence():
    """LLM response with intent missing confidence."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": null,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Missing confidence"
            }],
            "response_text": "Hello!",
            "self_response": true,
            "reasoning": "Intent missing confidence field"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 40,
            "total": 540
        }
    }


@pytest.fixture
def llm_response_self_respond_without_text():
    """LLM response with self_response=true but no response_text."""
    return {
        "content": """{
            "intents": [{
                "intent_type": "greeting",
                "canonical_intent": null,
                "confidence": 0.98,
                "entities": {},
                "sequence_order": 1,
                "reasoning": "Greeting"
            }],
            "response_text": null,
            "self_response": true,
            "reasoning": "Self-respond but no text"
        }""",
        "token_usage": {
            "prompt_tokens": 500,
            "completion_tokens": 45,
            "total": 545
        }
    }


@pytest.fixture
def mock_cold_paths():
    """Mock cold path triggers."""
    with patch('conversation_orchestrator.cold_path.trigger_manager.trigger_cold_paths') as mock:
        yield mock