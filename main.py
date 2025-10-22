"""Application entry point."""
# Load environment variables from .env file
from dotenv import load_dotenv
import os

load_dotenv()

import uvicorn
from api.app import create_app

# Get environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "NOT_SET")

# Create the application
app = create_app()

if __name__ == "__main__":
    # Only print banner when running as main script
    print("\n" + "=" * 60)
    print("🚀 Bot Framework API Starting")
    print("=" * 60)
    print(f"Environment:     {ENVIRONMENT}")
    print(f"Database:        {DATABASE_URL[:50]}..." if len(DATABASE_URL) > 50 else f"Database:        {DATABASE_URL}")
    print(f"Engine:          {os.getenv('ENGINE_REF', 'NOT_SET')}")
    print("=" * 60 + "\n")
    
    # Run the application
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable for development
        log_level="info"
    )