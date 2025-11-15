"""
Schema Checker - Validates data completeness from brand APIs.

This is the KILLER FEATURE - nobody else has this.

Checks if required data fields exist for a user before allowing actions to proceed.
"""

from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
import requests
from sqlalchemy.orm import Session

from db.models.schemas import SchemaModel
from db.models.brands import BrandModel


# In-memory cache for schema data
# Structure: {(schema_key, user_id): {"data": {...}, "fetched_at": datetime, "ttl": int}}
_schema_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}


def fetch_schema_data(
    db: Session,
    schema_key: str,
    user_id: str,
    brand_id: str,
    force_refresh: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Fetch schema data from brand API.
    
    Uses caching based on schema.cache_ttl_seconds.
    
    Args:
        db: Database session
        schema_key: Schema identifier (e.g., "user_profile")
        user_id: User UUID
        brand_id: Brand UUID
        force_refresh: Skip cache and fetch fresh data
        
    Returns:
        Schema data dictionary or None if fetch fails
    """
    cache_key = (schema_key, user_id)
    
    # Check cache first
    if not force_refresh and cache_key in _schema_cache:
        cached = _schema_cache[cache_key]
        fetched_at = cached['fetched_at']
        ttl = cached['ttl']
        age_seconds = (datetime.utcnow() - fetched_at).total_seconds()
        
        if age_seconds < ttl:
            # Cache still valid
            return cached['data']
    
    try:
        # Load schema definition
        schema = db.query(SchemaModel).filter(
            SchemaModel.schema_key == schema_key,
            SchemaModel.brand_id == brand_id
        ).first()
        
        if not schema:
            return None
        
        # Load brand for API base URL
        brand = db.query(BrandModel).filter(BrandModel.id == brand_id).first()
        
        if not brand or not brand.extra_config:
            return None
        
        brand_api_base = brand.extra_config.get('api_base_url')
        
        if not brand_api_base:
            return None
        
        # Build API endpoint
        api_endpoint = schema.api_endpoint.replace('{user_id}', str(user_id))
        api_url = f"{brand_api_base}{api_endpoint}"
        
        # Fetch data
        try:
            response = requests.get(api_url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Cache the result
                _schema_cache[cache_key] = {
                    'data': data,
                    'fetched_at': datetime.utcnow(),
                    'ttl': schema.cache_ttl_seconds
                }
                
                return data
            else:
                return None
        
        except Exception as e:
            # Log error (would use proper logging in production)
            print(f"Error fetching schema {schema_key}: {str(e)}")
            return None
            
    except Exception as e:
        print(f"Error in fetch_schema_data: {str(e)}")
        return None


def check_schema_completeness(
    db: Session,
    schema_key: str,
    required_fields: List[str],
    user_id: str,
    brand_id: str
) -> Tuple[bool, List[str]]:
    """
    Check if all required fields exist in schema data.
    
    Args:
        db: Database session
        schema_key: Schema identifier
        required_fields: List of field names that must exist
        user_id: User UUID
        brand_id: Brand UUID
        
    Returns:
        Tuple of (is_complete, missing_fields)
    """
    # Fetch schema data
    data = fetch_schema_data(db, schema_key, user_id, brand_id)
    
    if data is None:
        # Fetch failed - all fields are missing
        return False, required_fields
    
    # Check each required field
    missing_fields = []
    
    for field in required_fields:
        # Support nested fields with dot notation (e.g., "address.city")
        value = _get_nested_value(data, field)
        
        if value is None or value == '':
            missing_fields.append(field)
    
    is_complete = len(missing_fields) == 0
    
    return is_complete, missing_fields


def check_multiple_schemas(
    db: Session,
    schema_dependencies: List[Dict[str, Any]],
    user_id: str,
    brand_id: str
) -> Tuple[bool, List[str]]:
    """
    Check multiple schema dependencies at once.
    
    Args:
        db: Database session
        schema_dependencies: List of schema dependency objects
                            Each: {"schema_key": "...", "required_fields": [...]}
        user_id: User UUID
        brand_id: Brand UUID
        
    Returns:
        Tuple of (all_complete, blocking_reasons)
        
    Example:
        schema_dependencies = [
            {"schema_key": "user_profile", "required_fields": ["email", "phone"]},
            {"schema_key": "resume", "required_fields": ["resume_url"]}
        ]
        
        Returns: (False, ["incomplete_schema:user_profile:phone", "schema_not_found:resume"])
    """
    all_complete = True
    blocking_reasons = []
    
    for schema_dep in schema_dependencies:
        schema_key = schema_dep.get('schema_key')
        required_fields = schema_dep.get('required_fields', [])
        
        if not schema_key:
            continue
        
        # Check this schema
        is_complete, missing_fields = check_schema_completeness(
            db,
            schema_key,
            required_fields,
            user_id,
            brand_id
        )
        
        if not is_complete:
            all_complete = False
            
            # Build blocking reason
            if missing_fields == required_fields:
                # All fields missing - probably fetch failed
                blocking_reasons.append(f"schema_fetch_failed:{schema_key}")
            else:
                # Some specific fields missing
                fields_str = ",".join(missing_fields)
                blocking_reasons.append(f"incomplete_schema:{schema_key}:{fields_str}")
    
    return all_complete, blocking_reasons


def check_schema_exists(
    db: Session,
    schema_key: str,
    user_id: str,
    brand_id: str
) -> bool:
    """
    Check if schema data exists for user (any data, regardless of completeness).
    
    Used for blocked_if_schemas logic.
    
    Args:
        db: Database session
        schema_key: Schema identifier
        user_id: User UUID
        brand_id: Brand UUID
        
    Returns:
        True if schema data exists
    """
    data = fetch_schema_data(db, schema_key, user_id, brand_id)
    
    # Consider it "exists" if we got any non-empty data
    if data and len(data) > 0:
        return True
    
    return False


def check_data_exists(
    db: Session,
    schema_key: str,
    field_name: str,
    user_id: str,
    brand_id: str
) -> bool:
    """
    Check if specific data field exists for user.
    
    Used for workflow skip logic.
    
    Args:
        db: Database session
        schema_key: Schema identifier
        field_name: Field name to check (supports dot notation)
        user_id: User UUID
        brand_id: Brand UUID
        
    Returns:
        True if field exists and is not null/empty
    """
    data = fetch_schema_data(db, schema_key, user_id, brand_id)
    
    if data is None:
        return False
    
    value = _get_nested_value(data, field_name)
    
    if value is not None and value != '':
        return True
    
    return False


def invalidate_schema_cache(schema_key: str, user_id: str) -> None:
    """
    Invalidate cached schema data.
    
    Call this when schema data is updated.
    
    Args:
        schema_key: Schema identifier
        user_id: User UUID
    """
    cache_key = (schema_key, user_id)
    
    if cache_key in _schema_cache:
        del _schema_cache[cache_key]


def invalidate_all_schema_cache_for_user(user_id: str) -> None:
    """
    Invalidate all cached schema data for a user.
    
    Args:
        user_id: User UUID
    """
    keys_to_delete = [
        key for key in _schema_cache.keys()
        if key[1] == user_id
    ]
    
    for key in keys_to_delete:
        del _schema_cache[key]


def _get_nested_value(data: Dict[str, Any], field_path: str) -> Any:
    """
    Get value from nested dictionary using dot notation.
    
    Args:
        data: Dictionary to search
        field_path: Field path (e.g., "address.city")
        
    Returns:
        Value or None if not found
        
    Example:
        data = {"address": {"city": "SF", "state": "CA"}}
        _get_nested_value(data, "address.city") -> "SF"
    """
    if '.' not in field_path:
        # Simple field
        return data.get(field_path)
    
    # Nested field
    parts = field_path.split('.')
    current = data
    
    for part in parts:
        if not isinstance(current, dict):
            return None
        
        current = current.get(part)
        
        if current is None:
            return None
    
    return current


def get_schema_summary(
    db: Session,
    schema_key: str,
    user_id: str,
    brand_id: str
) -> Dict[str, Any]:
    """
    Get summary of schema completeness for debugging.
    
    Args:
        db: Database session
        schema_key: Schema identifier
        user_id: User UUID
        brand_id: Brand UUID
        
    Returns:
        Summary dictionary with completeness info
    """
    try:
        # Load schema definition
        schema = db.query(SchemaModel).filter(
            SchemaModel.schema_key == schema_key,
            SchemaModel.brand_id == brand_id
        ).first()
        
        if not schema:
            return {
                'schema_key': schema_key,
                'exists': False,
                'error': 'schema_not_defined'
            }
        
        # Fetch data
        data = fetch_schema_data(db, schema_key, user_id, brand_id)
        
        if data is None:
            return {
                'schema_key': schema_key,
                'exists': True,
                'data_fetched': False,
                'error': 'fetch_failed'
            }
        
        # Check required fields
        required_fields = schema.required_fields or []
        field_status = {}
        
        for field in required_fields:
            value = _get_nested_value(data, field)
            field_status[field] = {
                'exists': value is not None and value != '',
                'value_preview': str(value)[:50] if value else None
            }
        
        missing_count = sum(1 for f in field_status.values() if not f['exists'])
        
        return {
            'schema_key': schema_key,
            'exists': True,
            'data_fetched': True,
            'required_fields_count': len(required_fields),
            'complete_fields_count': len(required_fields) - missing_count,
            'missing_fields_count': missing_count,
            'is_complete': missing_count == 0,
            'fields': field_status
        }
        
    except Exception as e:
        return {
            'schema_key': schema_key,
            'exists': False,
            'error': f'exception: {str(e)}'
        }