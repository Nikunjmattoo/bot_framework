"""Centralized exception handlers for the API."""
from fastapi import Request
from fastapi.responses import JSONResponse

from message_handler.exceptions import BaseAppException, DuplicateError
from api.error_codes import get_http_status
from utils import get_logger

logger = get_logger("api_exceptions")


def handle_message_handler_exception(request: Request, exc: BaseAppException) -> JSONResponse:
    """
    Handle all custom message handler exceptions.
    
    Maps internal error codes to appropriate HTTP status codes and
    returns structured error responses.
    """
    if isinstance(exc, DuplicateError):
        error_content = {
            "success": False,
            "error": {
                "code": exc.error_code.value,
                "message": str(exc) or "Duplicate request detected",
                "type": exc.__class__.__name__,
                "retry_after_ms": exc.details.get("retry_after_ms", 1000) if hasattr(exc, 'details') and exc.details else 1000
            }
        }
        
        if hasattr(exc, 'details') and exc.details and 'request_id' in exc.details:
            error_content["request_id"] = exc.details['request_id']
        
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            error_content["trace_id"] = trace_id
        
        return JSONResponse(
            status_code=409,
            content=error_content
        )
    
    status_code, default_message = get_http_status(exc.error_code)
    
    error_content = {
        "success": False,
        "error": {
            "code": exc.error_code.value,
            "message": str(exc) or default_message,
            "type": exc.__class__.__name__
        }
    }
    
    trace_id = getattr(request.state, "trace_id", None)
    if trace_id:
        error_content["trace_id"] = trace_id
    
    if hasattr(exc, 'details') and exc.details:
        error_content["error"]["details"] = exc.details
    
    return JSONResponse(status_code=status_code, content=error_content)


def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle unexpected exceptions that weren't caught by custom handlers.
    
    Logs the full exception and returns a generic error to the client.
    """
    trace_id = getattr(request.state, "trace_id", "unknown")
    
    logger.exception(
        "Unexpected exception in API",
        extra={
            "trace_id": trace_id,
            "path": request.url.path,
            "method": request.method,
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "type": "InternalServerError"
            },
            "trace_id": trace_id
        }
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    app.add_exception_handler(BaseAppException, handle_message_handler_exception)
    app.add_exception_handler(Exception, handle_unexpected_exception)