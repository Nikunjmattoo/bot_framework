"""Health check routes."""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.db import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthcheck(db: Session = Depends(get_db)):
    """
    Health check endpoint.
    
    Tests database connectivity and returns health status.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        # Return 503 Service Unavailable if unhealthy
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@router.get("/ready")
def readiness():
    """
    Readiness check endpoint.
    
    Simple check that the service is ready to handle requests.
    """
    return {"status": "ready"}


@router.get("/live")
def liveness():
    """
    Liveness check endpoint.
    
    Simple check that the service is alive.
    """
    return {"status": "alive"}