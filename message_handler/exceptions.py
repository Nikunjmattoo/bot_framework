"""
Exception definitions for message handling.
Defines custom exceptions used throughout the message handler.
"""
from enum import Enum
from typing import Optional, Dict, Any
import traceback

class ErrorCode(Enum):
    """Standardized error codes for application exceptions."""
    # Validation errors (1000-1999)
    VALIDATION_ERROR = 1000
    SCHEMA_VALIDATION_ERROR = 1001
    INPUT_VALIDATION_ERROR = 1002
    
    # Resource errors (2000-2999)
    RESOURCE_NOT_FOUND = 2000
    RESOURCE_ALREADY_EXISTS = 2001
    RESOURCE_CONFLICT = 2002
    
    # Authentication/Authorization errors (3000-3999)
    UNAUTHORIZED = 3000
    FORBIDDEN = 3001
    TOKEN_EXPIRED = 3002
    
    # Database errors (4000-4999)
    DATABASE_ERROR = 4000
    DATABASE_CONNECTION_ERROR = 4001
    DATABASE_CONSTRAINT_ERROR = 4002
    
    # Service errors (5000-5999)
    SERVICE_UNAVAILABLE = 5000
    DEPENDENCY_ERROR = 5001
    TIMEOUT_ERROR = 5002
    
    # Orchestration errors (6000-6999)
    ORCHESTRATION_ERROR = 6000
    TOKEN_BUDGET_EXCEEDED = 6001
    
    # Configuration errors (7000-7999)
    CONFIGURATION_ERROR = 7000
    INSTANCE_CONFIGURATION_ERROR = 7001
    
    # Session errors (8000-8999)
    SESSION_ERROR = 8000
    SESSION_EXPIRED = 8001
    
    # System errors (9000-9999)
    INTERNAL_ERROR = 9000
    NOT_IMPLEMENTED = 9001


class BaseAppException(Exception):
    """Base exception for all application exceptions."""
    def __init__(
        self, 
        message: str, 
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        original_exception: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None,
        cached_response: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        self.message = message
        self.error_code = error_code
        self.original_exception = original_exception
        self.details = details or {}
        self.cached_response = cached_response
        self.stack_trace = traceback.format_exc() if original_exception else None
        
        # Add additional kwargs to details
        for key, value in kwargs.items():
            self.details[key] = value
        
        # Add original exception message to details if available
        if original_exception:
            self.details["original_error"] = str(original_exception)
            
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to a dictionary for serialization."""
        result = {
            "error_code": self.error_code.value,
            "error_type": self.error_code.name,
            "message": self.message
        }
        
        if self.details:
            result["details"] = self.details
            
        # Stack trace should only be included in development/debugging
        # and filtered out before sending to clients
        if self.stack_trace:
            result["stack_trace"] = self.stack_trace
            
        return result


class ValidationError(BaseAppException):
    """Exception raised for validation errors."""
    def __init__(
        self, 
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        error_code: ErrorCode = ErrorCode.VALIDATION_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class ResourceNotFoundError(BaseAppException):
    """Exception raised when a resource is not found."""
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.RESOURCE_NOT_FOUND,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class DuplicateError(BaseAppException):
    """Exception raised when attempting to create a duplicate resource.
    
    May include a cached_response from previous processing.
    """
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.RESOURCE_ALREADY_EXISTS,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if resource_type:
            details["resource_type"] = resource_type
        if resource_id:
            details["resource_id"] = resource_id
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class DatabaseError(BaseAppException):
    """Exception raised for database errors."""
    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.DATABASE_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if operation:
            details["operation"] = operation
        
        # Don't include sensitive DB details in error output
        # Filter or sanitize any sensitive information
        if "details" in details:
            details["details"] = self._sanitize_db_details(details["details"])
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )
    
    def _sanitize_db_details(self, details: Any) -> Any:
        """Remove sensitive information from database details."""
        # Implement sanitization logic here
        # For example, remove connection strings, passwords, etc.
        return details


class UnauthorizedError(BaseAppException):
    """Exception raised for unauthorized access."""
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNAUTHORIZED,
        **kwargs
    ):
        super().__init__(
            message=message, 
            error_code=error_code, 
            **kwargs
        )


class TokenBudgetExceededError(BaseAppException):
    """Exception raised when token budget is exceeded."""
    def __init__(
        self,
        message: str,
        token_type: Optional[str] = None,
        current_usage: Optional[int] = None,
        budget_limit: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.TOKEN_BUDGET_EXCEEDED,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if token_type:
            details["token_type"] = token_type
        if current_usage is not None:
            details["current_usage"] = current_usage
        if budget_limit is not None:
            details["budget_limit"] = budget_limit
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class InstanceConfigurationError(BaseAppException):
    """Exception raised for instance configuration issues."""
    def __init__(
        self,
        message: str,
        instance_id: Optional[str] = None,
        config_key: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.INSTANCE_CONFIGURATION_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if instance_id:
            details["instance_id"] = instance_id
        if config_key:
            details["config_key"] = config_key
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class SessionManagementError(BaseAppException):
    """Exception raised for session management issues."""
    def __init__(
        self,
        message: str,
        session_id: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.SESSION_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if session_id:
            details["session_id"] = session_id
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )


class OrchestrationError(BaseAppException):
    """Exception raised during message orchestration."""
    def __init__(
        self,
        message: str,
        orchestrator: Optional[str] = None,
        error_code: ErrorCode = ErrorCode.ORCHESTRATION_ERROR,
        **kwargs
    ):
        details = kwargs.pop("details", {}) or {}
        if orchestrator:
            details["orchestrator"] = orchestrator
            
        super().__init__(
            message=message, 
            error_code=error_code, 
            details=details, 
            **kwargs
        )