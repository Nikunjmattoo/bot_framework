"""Centralized error code to HTTP status mapping."""
from message_handler.exceptions import ErrorCode

# Map internal error codes to HTTP status codes and user-friendly messages
ERROR_CODE_MAP = {
    ErrorCode.VALIDATION_ERROR: {
        "status": 422,  # ← Changed from 400 to 422
        "message": "Validation failed"
    },
    ErrorCode.UNAUTHORIZED: {
        "status": 401,
        "message": "Authentication required"
    },
    ErrorCode.RESOURCE_NOT_FOUND: {
        "status": 404,
        "message": "Resource not found"
    },
    ErrorCode.RESOURCE_ALREADY_EXISTS: {
        "status": 409,
        "message": "Duplicate request detected"
    },
    ErrorCode.DATABASE_ERROR: {
        "status": 500,
        "message": "Database operation failed"
    },
    ErrorCode.SESSION_ERROR: {
        "status": 500,
        "message": "Session management error"
    },
    ErrorCode.ORCHESTRATION_ERROR: {
        "status": 502,
        "message": "Orchestration service error"
    },
    ErrorCode.INTERNAL_ERROR: {
        "status": 500,
        "message": "Internal server error"
    },
}


def get_http_status(error_code: ErrorCode) -> tuple[int, str]:
    """
    Get HTTP status code and message for an error code.
    
    Args:
        error_code: Internal error code
        
    Returns:
        Tuple of (status_code, message)
    """
    mapping = ERROR_CODE_MAP.get(error_code, {
        "status": 500,
        "message": "Internal server error"
    })
    
    return mapping["status"], mapping["message"]