# utils/json_utils.py
import json
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Tuple, Union, Optional

class JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles UUIDs and datetimes."""
    def default(self, obj):
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def json_serialize(data: Any) -> str:
    """Serialize data to JSON, handling UUIDs and datetimes."""
    return json.dumps(data, cls=JSONEncoder)

def prepare_for_json(obj: Any) -> Any:
    """
    Prepare an object for JSON serialization by handling special types.
    
    Args:
        obj: The object to prepare
        
    Returns:
        JSON-serializable version of the object
    """
    if obj is None:
        return None
        
    # Handle basic types directly
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
        
    # Handle UUIDs
    if isinstance(obj, uuid.UUID):
        return str(obj)
        
    # Handle datetime/date objects
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # Handle dictionaries
    if isinstance(obj, dict):
        return {k: prepare_for_json(v) for k, v in obj.items()}
    
    # Handle lists
    if isinstance(obj, list):
        return [prepare_for_json(item) for item in obj]
        
    # Handle tuples
    if isinstance(obj, tuple):
        return tuple(prepare_for_json(item) for item in obj)
    
    # For all other objects, try string conversion
    try:
        return str(obj)
    except Exception:
        return None

def safe_parse_json(json_string: Union[str, Dict, None], default: Any = None) -> Any:
    """
    Safely parse a JSON string, handling errors gracefully.
    
    Args:
        json_string: String to parse, or dict to return as-is
        default: Default value to return on error (default: {})
        
    Returns:
        Parsed JSON object or default value on error
    """
    if json_string is None:
        return default if default is not None else {}
        
    if not isinstance(json_string, str):
        # Already parsed or not a string
        return json_string
        
    try:
        return json.loads(json_string)
    except Exception:
        return default if default is not None else {}