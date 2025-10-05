"""Application entry point."""
import uvicorn
from api.app import create_app

# Create the application
app = create_app()

if __name__ == "__main__":
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable for development
        log_level="info"
    )