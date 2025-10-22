"""
FILE: test/utils/test_error_handling.py (FIXED)
================================================
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import (
    IntegrityError, OperationalError, SQLAlchemyError,
    ProgrammingError, DataError
)
from message_handler.utils.error_handling import (
    handle_database_error,
    is_safe_to_retry,
    with_error_handling
)
from message_handler.exceptions import (
    DatabaseError, ValidationError, ErrorCode
)


# ============================================================================
# TEST: handle_database_error
# ============================================================================

class TestHandleDatabaseError:
    """Test database error handling and classification"""
    
    def test_integrity_error_mapped_to_constraint_error(self):
        """IntegrityError mapped to DATABASE_CONSTRAINT_ERROR"""
        error = IntegrityError("constraint violation", None, None)
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="test_operation")
        
        assert exc.value.error_code == ErrorCode.DATABASE_CONSTRAINT_ERROR
    
    def test_integrity_error_with_unique_constraint_detected(self):
        """IntegrityError with 'violates unique constraint' detected"""
        error = IntegrityError("duplicate key value violates unique constraint", None, None)
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="insert_user")
        
        assert "duplicate" in str(exc.value).lower()
        assert exc.value.details.get("error_type") == "duplicate_key"
    
    def test_integrity_error_with_duplicate_key_detected(self):
        """IntegrityError with 'duplicate key' text detected"""
        error = IntegrityError("ERROR: duplicate key value", None, None)
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="insert")
        
        assert exc.value.details.get("error_type") == "duplicate_key"
    
    def test_operational_error_timeout_mapped(self):
        """OperationalError with timeout mapped to TIMEOUT_ERROR"""
        error = OperationalError("statement timeout", None, None)
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="query")
        
        assert exc.value.error_code == ErrorCode.TIMEOUT_ERROR
    
    def test_operational_error_connection_mapped(self):
        """OperationalError connection issues mapped correctly"""
        error = OperationalError("connection refused", None, None)
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="connect")
        
        assert exc.value.error_code == ErrorCode.DATABASE_CONNECTION_ERROR
    
    def test_generic_sqlalchemy_error_mapped(self):
        """Generic SQLAlchemyError mapped to DATABASE_ERROR"""
        error = SQLAlchemyError("generic database error")
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="generic_op")
        
        assert exc.value.error_code == ErrorCode.DATABASE_ERROR
    
    def test_operation_included_in_error(self):
        """Operation name included in error"""
        error = SQLAlchemyError("test error")
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="saving_user")
        
        assert "saving_user" in str(exc.value)
        assert exc.value.details["operation"] == "saving_user"
    
    def test_trace_id_passed_to_logger(self):
        """Trace ID passed to logger"""
        error = SQLAlchemyError("test")
        
        with pytest.raises(DatabaseError):
            handle_database_error(error, operation="test", trace_id="trace123")
    
    def test_custom_error_code(self):
        """Custom error code used"""
        error = SQLAlchemyError("test")
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(
                error, 
                operation="test", 
                error_code=ErrorCode.INTERNAL_ERROR
            )
        
        assert exc.value.error_code == ErrorCode.INTERNAL_ERROR
    
    def test_additional_details_included(self):
        """Additional details included in error"""
        error = SQLAlchemyError("test")
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(
                error, 
                operation="test",
                details={"user_id": "user123"}
            )
        
        assert exc.value.details["user_id"] == "user123"


# ============================================================================
# TEST: is_safe_to_retry
# ============================================================================

class TestIsSafeToRetry:
    """Test retry safety detection"""
    
    def test_deadlock_error_safe_to_retry(self):
        """Deadlock errors safe to retry"""
        error = OperationalError("deadlock detected", None, None)
        assert is_safe_to_retry(error) is True
    
    def test_lock_timeout_safe_to_retry(self):
        """Lock timeout errors safe to retry"""
        error = OperationalError("lock timeout", None, None)
        assert is_safe_to_retry(error) is True
    
    def test_connection_error_safe_to_retry(self):
        """Connection errors safe to retry"""
        error = OperationalError("connection refused", None, None)
        assert is_safe_to_retry(error) is True
    
    def test_timeout_error_safe_to_retry(self):
        """Timeout errors safe to retry"""
        error = OperationalError("timeout exceeded", None, None)
        assert is_safe_to_retry(error) is True
    
    def test_serialization_error_safe_to_retry(self):
        """Serialization errors safe to retry"""
        error = SQLAlchemyError("could not serialize access")
        assert is_safe_to_retry(error) is True
    
    def test_integrity_error_not_safe_to_retry(self):
        """IntegrityError (constraint violation) not safe"""
        error = IntegrityError("unique constraint", None, None)
        assert is_safe_to_retry(error) is False
    
    def test_programming_error_not_safe(self):
        """ProgrammingError (SQL syntax) not safe"""
        error = ProgrammingError("syntax error", None, None)
        assert is_safe_to_retry(error) is False
    
    def test_non_sqlalchemy_error_not_safe(self):
        """Non-SQLAlchemy errors not safe to retry"""
        error = ValueError("custom error")
        assert is_safe_to_retry(error) is False


# ============================================================================
# TEST: with_error_handling (decorator)
# ============================================================================

class TestWithErrorHandlingDecorator:
    """Test with_error_handling decorator"""
    
    def test_successful_function_returns_normally(self):
        """Successful function returns normally"""
        @with_error_handling(operation_name="test_op")
        def test_func():
            return "success"
        
        result = test_func()
        assert result == "success"
    
    def test_validation_error_re_raised(self):
        """ValidationError re-raised without wrapping"""
        @with_error_handling(operation_name="test_op")
        def test_func():
            raise ValidationError("Invalid input", ErrorCode.VALIDATION_ERROR)
        
        with pytest.raises(ValidationError) as exc:
            test_func()
        
        assert exc.value.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_sqlalchemy_error_wrapped(self):
        """SQLAlchemyError wrapped in DatabaseError"""
        @with_error_handling(operation_name="test_op")
        def test_func():
            raise IntegrityError("constraint", None, None)
        
        with pytest.raises(DatabaseError):
            test_func()
    
    def test_uses_function_name_if_no_operation_name(self):
        """Uses function name if operation_name not provided"""
        @with_error_handling()
        def my_function():
            raise ValueError("test")
        
        with pytest.raises(DatabaseError) as exc:
            my_function()
        
        assert "my_function" in str(exc.value)
    
    def test_extracts_trace_id_from_kwargs(self):
        """Extracts trace_id from kwargs"""
        @with_error_handling()
        def test_func(trace_id=None):
            raise ValueError("test")
        
        with pytest.raises(DatabaseError):
            test_func(trace_id="trace123")
    
    def test_rollback_on_sqlalchemy_error(self):
        """Rolls back on SQLAlchemy error"""
        mock_db = Mock()
        
        @with_error_handling()
        def test_func(db=None):
            raise SQLAlchemyError("error")
        
        with pytest.raises(DatabaseError):
            test_func(db=mock_db)
        
        mock_db.rollback.assert_called_once()
    
    def test_preserves_function_metadata(self):
        """Preserves original function metadata"""
        @with_error_handling()
        def test_func():
            """Test docstring"""
            return "success"
        
        assert test_func.__doc__ == "Test docstring"
        assert test_func.__name__ == "test_func"
    
    def test_reraise_list_honored(self):
        """Reraise list honored"""
        @with_error_handling(reraise=[ValueError])
        def test_func():
            raise ValueError("custom")
        
        with pytest.raises(ValueError):
            test_func()


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test real-world integration scenarios"""
    
    def test_handle_duplicate_key_violation(self):
        """Handle duplicate key violation scenario"""
        error = IntegrityError(
            'duplicate key value violates unique constraint "users_email_key"',
            None, None
        )
        
        with pytest.raises(DatabaseError) as exc:
            handle_database_error(error, operation="creating_user")
        
        assert exc.value.details.get("error_type") == "duplicate_key"
        assert "creating_user" in str(exc.value)
    
    def test_retry_safe_errors_detected(self):
        """Retry-safe errors identified correctly"""
        error = OperationalError("deadlock", None, None)
        assert is_safe_to_retry(error) is True


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases"""
    
    def test_error_with_very_long_message(self):
        """Error with very long message handled"""
        long_msg = "x" * 10000
        error = SQLAlchemyError(long_msg)
        
        with pytest.raises(DatabaseError):
            handle_database_error(error, operation="test")
    
    def test_error_with_unicode_characters(self):
        """Error with unicode characters handled"""
        error = SQLAlchemyError("Error: 中文 émojis 🚀")
        
        with pytest.raises(DatabaseError):
            handle_database_error(error, operation="test")