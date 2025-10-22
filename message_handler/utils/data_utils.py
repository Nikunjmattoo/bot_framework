"""
Data utilities for the message handler system.

This module provides common data sanitization and normalization
functions used throughout the message handler codebase.
"""
from typing import Dict, Any, List, Union, Optional, Set, Tuple
import re
import html
import unicodedata

def sanitize_data(
    data: Any,
    allow_html: bool = False,
    trim_strings: bool = True,
    max_depth: int = 10,
    max_string_length: Optional[int] = None,
    max_list_items: Optional[int] = None,
    max_dict_items: Optional[int] = None,
    strip_keys: Optional[List[str]] = None,
    sanitize_keys: bool = True
) -> Any:
    """
    Sanitize data by removing potentially harmful content and normalizing values.
    
    Args:
        data: Data to sanitize (can be a string, dict, list, or other types)
        allow_html: Whether to allow HTML tags (default: False)
        trim_strings: Whether to trim whitespace from strings (default: True)
        max_depth: Maximum recursion depth (default: 10)
        max_string_length: Maximum string length (optional)
        max_list_items: Maximum number of list items (optional)
        max_dict_items: Maximum number of dictionary items (optional)
        strip_keys: List of keys to remove from dictionaries (optional)
        sanitize_keys: Whether to sanitize dictionary keys (default: True)
        
    Returns:
        Sanitized data
        
    Raises:
        ValueError: If max recursion depth is exceeded
    """
    # Prevent infinite recursion
    if max_depth <= 0:
        raise ValueError("Maximum recursion depth exceeded")
    
    # Set default values for optional parameters
    strip_keys = strip_keys or []
    
    # Handle different data types
    if data is None:
        return None
    
    elif isinstance(data, str):
        # Sanitize string
        return sanitize_string(
            data,
            allow_html=allow_html,
            trim=trim_strings,
            max_length=max_string_length
        )
    
    elif isinstance(data, (int, float, bool)):
        # Return primitive types as-is
        return data
    
    elif isinstance(data, dict):
        # Sanitize dictionary
        return sanitize_dict(
            data,
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth - 1,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys,
            sanitize_keys=sanitize_keys
        )
    
    elif isinstance(data, list):
        # Sanitize list
        return sanitize_list(
            data,
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth - 1,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys
        )
    
    elif isinstance(data, tuple):
        # Convert to list, sanitize, and convert back to tuple
        sanitized_list = sanitize_list(
            list(data),
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth - 1,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys
        )
        return tuple(sanitized_list)
    
    elif isinstance(data, set):
        # Convert to list, sanitize, and convert back to set
        sanitized_list = sanitize_list(
            list(data),
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth - 1,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys
        )
        # Only hashable types can be in a set
        result = set()
        for item in sanitized_list:
            if isinstance(item, (str, int, float, bool, tuple, frozenset)):
                result.add(item)
        return result
    
    else:
        # For other types, convert to string representation
        return str(data)


def sanitize_string(
    text: str,
    allow_html: bool = False,
    trim: bool = True,
    max_length: Optional[int] = None
) -> str:
    """
    Sanitize a string by removing harmful content and normalizing.
    
    Args:
        text: String to sanitize
        allow_html: Whether to allow HTML tags (default: False)
        trim: Whether to trim whitespace (default: True)
        max_length: Maximum string length (optional)
        
    Returns:
        Sanitized string
    """
    if not text:
        return ""
    
    # Normalize Unicode
    result = unicodedata.normalize('NFKC', text)
    
    # Remove control characters except newlines and tabs
    result = "".join(c for c in result if c == "\n" or c == "\t" or not unicodedata.category(c).startswith('C'))
    
    # Escape HTML if not allowed
    if not allow_html:
        result = html.escape(result)
    
    # Trim whitespace if requested
    if trim:
        result = result.strip()
    
    # Truncate if maximum length specified
    if max_length is not None and len(result) > max_length:
        result = result[:max_length]
    
    return result


def sanitize_dict(
    data: Dict[str, Any],
    allow_html: bool = False,
    trim_strings: bool = True,
    max_depth: int = 9,
    max_string_length: Optional[int] = None,
    max_list_items: Optional[int] = None,
    max_dict_items: Optional[int] = None,
    strip_keys: Optional[List[str]] = None,
    sanitize_keys: bool = True
) -> Dict[str, Any]:
    """
    Sanitize a dictionary recursively.
    
    Args:
        data: Dictionary to sanitize
        allow_html: Whether to allow HTML tags (default: False)
        trim_strings: Whether to trim whitespace from strings (default: True)
        max_depth: Maximum recursion depth (default: 9)
        max_string_length: Maximum string length (optional)
        max_list_items: Maximum number of list items (optional)
        max_dict_items: Maximum number of dictionary items (optional)
        strip_keys: List of keys to remove (optional)
        sanitize_keys: Whether to sanitize keys (default: True)
        
    Returns:
        Sanitized dictionary
    """
    strip_keys = strip_keys or []
    result = {}
    
    # Limit dictionary size if requested
    items = list(data.items())
    if max_dict_items is not None and len(items) > max_dict_items:
        items = items[:max_dict_items]
    
    # Process each key-value pair
    for key, value in items:
        # Skip keys that should be stripped
        if key in strip_keys:
            continue
        
        # Sanitize keys if requested
        if sanitize_keys and isinstance(key, str):
            key = sanitize_string(
                key,
                allow_html=False,  # Never allow HTML in keys
                trim=trim_strings,
                max_length=max_string_length
            )
        
        # Sanitize value recursively
        sanitized_value = sanitize_data(
            value,
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys,
            sanitize_keys=sanitize_keys
        )
        
        # Add to result
        result[key] = sanitized_value
    
    return result


def sanitize_list(
    data: List[Any],
    allow_html: bool = False,
    trim_strings: bool = True,
    max_depth: int = 9,
    max_string_length: Optional[int] = None,
    max_list_items: Optional[int] = None,
    max_dict_items: Optional[int] = None,
    strip_keys: Optional[List[str]] = None
) -> List[Any]:
    """
    Sanitize a list recursively.
    
    Args:
        data: List to sanitize
        allow_html: Whether to allow HTML tags (default: False)
        trim_strings: Whether to trim whitespace from strings (default: True)
        max_depth: Maximum recursion depth (default: 9)
        max_string_length: Maximum string length (optional)
        max_list_items: Maximum number of list items (optional)
        max_dict_items: Maximum number of dictionary items (optional)
        strip_keys: List of keys to remove from dictionaries (optional)
        
    Returns:
        Sanitized list
    """
    # Limit list size if requested
    if max_list_items is not None and len(data) > max_list_items:
        data = data[:max_list_items]
    
    # Sanitize each item
    result = []
    for item in data:
        sanitized_item = sanitize_data(
            item,
            allow_html=allow_html,
            trim_strings=trim_strings,
            max_depth=max_depth,
            max_string_length=max_string_length,
            max_list_items=max_list_items,
            max_dict_items=max_dict_items,
            strip_keys=strip_keys
        )
        result.append(sanitized_item)
    
    return result