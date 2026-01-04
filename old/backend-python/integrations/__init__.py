"""
Integrations - External API clients

Available clients:
- XHypeDetector: X/Twitter hype detection for stocks and crypto
- BinanceClient: Real-time prices and perpetual futures trading
"""

from .x_client import (
    XHypeDetector,
    get_x_hype_detector,
    HypeScore,
    Tweet,
)

from .binance import (
    BinanceClient,
    get_binance,
    PriceData,
    Order,
    OrderSide,
    OrderType,
    PositionSide,
)

__all__ = [
    # X/Twitter
    "XHypeDetector",
    "get_x_hype_detector",
    "HypeScore",
    "Tweet",
    
    # Binance
    "BinanceClient",
    "get_binance",
    "PriceData",
    "Order",
    "OrderSide",
    "OrderType",
    "PositionSide",
]
