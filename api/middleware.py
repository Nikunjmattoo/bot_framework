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
    - Request ID for idempotency tracking
    
    This replaces scattered logging throughout the codebase.
    """
    # Generate or extract trace_id from headers or body
    trace_id = request.headers.get("X-Trace-ID")
    
    # If not in headers, try to extract from body (for JSON requests)
    if not trace_id and request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Save the body for later use by the endpoint
            body = await request.body()
            
            # Try to parse as JSON and extract trace_id
            if body:
                import json
                try:
                    body_json = json.loads(body.decode())
                    trace_id = body_json.get("trace_id")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            
            # Create a new request with the body preserved
            async def receive():
                return {"type": "http.request", "body": body}
            
            request._receive = receive
        except Exception:
            pass
    
    # Fall back to generating a new trace_id
    if not trace_id:
        trace_id = str(uuid.uuid4())
    
    request.state.trace_id = trace_id
    
    # Extract request_id from standard HTTP headers (Industry Standard)
    request_id = (
        request.headers.get("X-Request-ID") or 
        request.headers.get("Idempotency-Key") or
        request.headers.get("x-request-id") or
        request.headers.get("idempotency-key")
    )
    
    # If not in headers, try to extract from body for JSON requests
    if not request_id and request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.body()
            if body:
                import json
                try:
                    body_json = json.loads(body.decode())
                    request_id = body_json.get("request_id") or body_json.get("idempotency_key")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
                
                # Preserve body for endpoint
                async def receive():
                    return {"type": "http.request", "body": body}
                request._receive = receive
        except Exception:
            pass
    
    # Store request_id in request state for handlers
    request.state.request_id = request_id
    
    # Record start time
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000
    
    # ONE STRUCTURED LOG ENTRY PER REQUEST
    log_data = {
        "trace_id": trace_id,
        "request_id": request_id,
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
    
    # Echo request_id back to client (Industry Standard)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    
    return response


async def cors_middleware(request: Request, call_next):
    """
    Handle CORS if needed.
    
    Note: This is a placeholder. Use FastAPI's CORSMiddleware instead
    for production CORS handling.
    """
    response = await call_next(request)
    return response