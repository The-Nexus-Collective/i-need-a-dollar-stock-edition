"""
Integrations - External API clients

Available clients:
- XHypeDetector: X/Twitter hype detection for stocks and crypto
- CoinGeckoClient: Market data and coin discovery
- BinanceClient: Real-time prices and perpetual futures trading
"""

from .x_client import (
    XHypeDetector,
    get_x_hype_detector,
    HypeScore,
    Tweet,
)

from .coingecko import (
    CoinGeckoClient,
    get_coingecko_client,
    CoinInfo,
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
    
    # CoinGecko
    "CoinGeckoClient",
    "get_coingecko_client",
    "CoinInfo",
    
    # Binance
    "BinanceClient",
    "get_binance",
    "PriceData",
    "Order",
    "OrderSide",
    "OrderType",
    "PositionSide",
]

