"""
Version information for the message handler package.
"""

__version__ = "1.0.0"
__author__ = "Enterprise Team"
__license__ = "Proprietary"
__copyright__ = "Copyright 2025 Enterprise Company"

VERSION_INFO = {
    "major": 1,
    "minor": 0,
    "patch": 0,
    "release": "stable",
}

def get_version_string() -> str:
    """
    Get a formatted version string.
    
    Returns:
        Formatted version string
    """
    return f"{__version__} ({VERSION_INFO['release']})"


def get_version_info() -> dict:
    """
    Get detailed version information.
    
    Returns:
        Dict with version information
    """
    return {
        "version": __version__,
        "author": __author__,
        "license": __license__,
        "details": VERSION_INFO,
    }