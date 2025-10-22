"""Response models and builders for API endpoints."""
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse


class APIResponse:
    """Standardized API response builder."""
    
    @staticmethod
    def success(data: Any = None, message: Optional[str] = None, status_code: int = 200) -> JSONResponse:
        """Build a success response."""
        content = {"success": True}
        
        if data is not None:
            content["data"] = data
        
        if message:
            content["message"] = message
        
        return JSONResponse(status_code=status_code, content=content)
    
    @staticmethod
    def error(
        message: str,
        error_code: str,
        status_code: int = 500,
        error_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> JSONResponse:
        """Build an error response."""
        content = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message
            }
        }
        
        if error_type:
            content["error"]["type"] = error_type
        
        if details:
            content["error"]["details"] = details
        
        return JSONResponse(status_code=status_code, content=content)