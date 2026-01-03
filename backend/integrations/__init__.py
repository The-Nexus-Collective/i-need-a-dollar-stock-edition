"""
Integrations - External API clients
"""

from .x_client import (
    XHypeDetector,
    get_x_hype_detector,
    HypeScore,
    Tweet,
)

__all__ = [
    "XHypeDetector",
    "get_x_hype_detector",
    "HypeScore",
    "Tweet",
]

