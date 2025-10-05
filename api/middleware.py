"""Middleware for the API."""
import time
import uuid
from fastapi import Request
from utils import get_logger

logger = get_logger("api_middleware")


async def request_logging_middleware(request: Request, call_next):
    """
    Log all requests with structured logging.
    
    Creates ONE log entry per request with:
    - Request details (method, path)
    - Response status
    - Processing duration
    - Trace ID for correlation
    
    This replaces scattered logging throughout the codebase.
    """
    # Generate or extract trace_id
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    request.state.trace_id = trace_id
    
    # Record start time
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # ONE STRUCTURED LOG ENTRY PER REQUEST
    log_data = {
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "duration_ms": round(duration_ms, 2),
        "success": 200 <= response.status_code < 400,
        "client_ip": request.client.host if request.client else None
    }
    
    # Log at appropriate level based on status
    if response.status_code >= 500:
        logger.error("request_completed", extra=log_data)
    elif response.status_code >= 400:
        logger.warning("request_completed", extra=log_data)
    else:
        logger.info("request_completed", extra=log_data)
    
    # Add trace_id to response headers for client tracking
    response.headers["X-Trace-ID"] = trace_id
    
    return response


async def cors_middleware(request: Request, call_next):
    """
    Handle CORS if needed.
    
    Note: This is a placeholder. Use FastAPI's CORSMiddleware instead
    for production CORS handling.
    """
    response = await call_next(request)
    return response