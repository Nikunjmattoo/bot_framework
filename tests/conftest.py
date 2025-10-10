"""
conftest.py - Pytest Configuration
==================================
SIMPLE SOLUTION: Use PostgreSQL for tests (same as production)

This avoids all SQLite compatibility issues.
"""

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

# Import your models and app
from db.models.base import Base
from main import app
from db.db import get_db

# Test database configuration
# IMPORTANT: Create a test database first:
# CREATE DATABASE bot_framework_test;
TEST_DATABASE_URL = "postgresql+psycopg2://postgres:admin@localhost:5432/bot_framework_test"


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine using PostgreSQL"""
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    
    # Set timezone
    @event.listens_for(engine, "connect")
    def set_timezone(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.close()
    
    # Drop and recreate all tables for clean slate
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    yield engine
    
    # Cleanup after all tests
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_db(test_engine):
    """Create a test database session"""
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)
    
    yield session
    
    # Rollback transaction after each test (keeps DB clean)
    session.close()
    transaction.rollback()
    connection.close()


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


# Clean up between test classes
@pytest.fixture(autouse=True)
def cleanup_database(test_db):
    """Clean up database between tests"""
    yield
    # Rollback is handled in test_db fixture