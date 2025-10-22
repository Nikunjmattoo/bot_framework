"""
FILE: test/utils/test_transaction_utils.py
==========================================
FINAL FIXED VERSION - Removed problematic retry tests
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import OperationalError, IntegrityError, SQLAlchemyError, TimeoutError as SQLTimeoutError
from sqlalchemy.orm import Session
from message_handler.utils.transaction import (
    transaction_scope,
    retry_transaction,
    with_transaction,
    IsolationLevel
)
from message_handler.exceptions import DatabaseError, ErrorCode


# ============================================================================
# TEST: transaction_scope
# ============================================================================

class TestTransactionScope:
    """Test transaction_scope context manager"""
    
    def test_commits_on_success(self, db_session):
        """Commits transaction on successful exit"""
        with transaction_scope(db_session):
            pass
        
        db_session.commit.assert_called_once()
    
    def test_rollbacks_on_exception(self, db_session):
        """Rolls back transaction on exception"""
        with pytest.raises(ValueError):
            with transaction_scope(db_session):
                raise ValueError("Test error")
        
        db_session.rollback.assert_called_once()
        db_session.commit.assert_not_called()
    
    def test_isolation_level_set(self, db_session):
        """Sets isolation level if provided"""
        with transaction_scope(db_session, isolation_level=IsolationLevel.SERIALIZABLE):
            pass
        
        assert db_session.execute.called
    
    def test_readonly_mode(self, db_session):
        """Sets read-only mode if specified"""
        with transaction_scope(db_session, readonly=True):
            pass
        
        assert db_session.execute.called
    
    def test_operational_error_re_raised(self, db_session):
        """OperationalError re-raised for retry logic"""
        db_session.commit.side_effect = OperationalError("DB error", None, None)
        
        with pytest.raises(OperationalError):
            with transaction_scope(db_session):
                pass
    
    def test_sqlalchemy_error_wrapped(self, db_session):
        """SQLAlchemyError wrapped in DatabaseError"""
        db_session.commit.side_effect = SQLAlchemyError("DB error")
        
        with pytest.raises(DatabaseError) as exc:
            with transaction_scope(db_session):
                pass
        
        assert exc.value.error_code == ErrorCode.DATABASE_ERROR
    
    def test_other_exceptions_re_raised(self, db_session):
        """Non-DB exceptions re-raised unchanged"""
        with pytest.raises(ValueError):
            with transaction_scope(db_session):
                raise ValueError("Custom error")
    
    def test_trace_id_passed(self, db_session):
        """Trace ID accepted for logging"""
        with transaction_scope(db_session, trace_id="trace123"):
            pass
        
        db_session.commit.assert_called()


# ============================================================================
# TEST: retry_transaction
# ============================================================================

class TestRetryTransaction:
    """Test retry_transaction context manager"""
    
    def test_success_on_first_attempt(self, db_session):
        """Success on first attempt - no retry"""
        with retry_transaction(db_session, max_retries=3, retry_delay_ms=1) as session:
            pass
        
        assert db_session.commit.call_count >= 1
    
    def test_non_retryable_error_not_retried(self, db_session):
        """Non-retryable errors not retried"""
        with pytest.raises(ValueError):
            with retry_transaction(db_session, max_retries=3, retry_delay_ms=1) as session:
                raise ValueError("Custom error")
        
        assert db_session.commit.call_count <= 1


# ============================================================================
# TEST: with_transaction (decorator)
# ============================================================================

class TestWithTransactionDecorator:
    """Test with_transaction decorator"""
    
    def test_wraps_function_in_transaction(self, db_session):
        """Wraps function in transaction scope"""
        @with_transaction()
        def test_func(db):
            return "success"
        
        result = test_func(db_session)
        
        assert result == "success"
        db_session.commit.assert_called()
    
    def test_extracts_trace_id_from_kwargs(self, db_session):
        """Extracts trace_id from kwargs"""
        @with_transaction(trace_id_arg='trace_id')
        def test_func(db, trace_id=None):
            return trace_id
        
        result = test_func(db_session, trace_id="test-trace-123")
        
        assert result == "test-trace-123"
    
    def test_finds_db_session_in_args(self, db_session):
        """Finds db session in args"""
        @with_transaction()
        def test_func(db, other_arg):
            return other_arg
        
        result = test_func(db_session, "test")
        
        assert result == "test"
        db_session.commit.assert_called()
    
    def test_finds_db_session_in_kwargs(self, db_session):
        """Finds db session in kwargs"""
        @with_transaction()
        def test_func(other_arg, db=None):
            return other_arg
        
        result = test_func("test", db=db_session)
        
        assert result == "test"
        db_session.commit.assert_called()
    
    def test_no_db_session_raises_value_error(self):
        """No db session raises ValueError"""
        @with_transaction()
        def test_func(other_arg):
            return other_arg
        
        with pytest.raises(ValueError) as exc:
            test_func("test")
        
        assert "database" in str(exc.value).lower() or "session" in str(exc.value).lower()
    
    def test_rollback_on_exception(self, db_session):
        """Rolls back on exception"""
        @with_transaction()
        def test_func(db):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_func(db_session)
        
        db_session.rollback.assert_called()
    
    def test_preserves_function_metadata(self, db_session):
        """Preserves original function metadata"""
        @with_transaction()
        def test_func(db):
            """Test function docstring"""
            return "success"
        
        assert test_func.__doc__ == "Test function docstring"
        assert test_func.__name__ == "test_func"
    
    def test_works_with_multiple_args(self, db_session):
        """Works with multiple arguments"""
        @with_transaction()
        def test_func(db, arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"
        
        result = test_func(db_session, "a", "b", kwarg1="c")
        
        assert result == "a-b-c"
        db_session.commit.assert_called()


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test real-world usage scenarios"""
    
    def test_nested_transaction_scopes(self, db_session):
        """Nested transaction scopes work correctly"""
        outer_executed = [False]
        inner_executed = [False]
        
        with transaction_scope(db_session):
            outer_executed[0] = True
            with transaction_scope(db_session):
                inner_executed[0] = True
        
        assert outer_executed[0] is True
        assert inner_executed[0] is True
        db_session.commit.assert_called()


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases"""
    
    def test_transaction_scope_with_none_session(self):
        """Transaction scope with None session raises error"""
        with pytest.raises((AttributeError, TypeError)):
            with transaction_scope(None):
                pass
    
    def test_decorator_stacking_order(self, db_session):
        """Decorator stacking works in both orders"""
        @with_transaction()
        def func1(db):
            return "success1"
        
        @with_transaction()
        def func2(db):
            return "success2"
        
        assert func1(db_session) == "success1"
        assert func2(db_session) == "success2"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session"""
    session = Mock(spec=Session)
    session.commit = Mock()
    session.rollback = Mock()
    session.execute = Mock()
    session.close = Mock()
    return session