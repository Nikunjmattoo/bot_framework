"""FastAPI application factory and configuration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.middleware import request_logging_middleware
from api.exceptions import register_exception_handlers
from api.routes import messages, whatsapp, broadcast, health


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Create app instance
    app = FastAPI(
        title="Bot Framework API",
        version="1.0.0",
        description="Multi-channel messaging platform API"
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add custom middleware
    app.middleware("http")(request_logging_middleware)
    
    # Register exception handlers
    register_exception_handlers(app)
    
    # Include routers
    app.include_router(health.router)
    app.include_router(messages.router)
    app.include_router(whatsapp.router)
    app.include_router(broadcast.router)
    
    return app