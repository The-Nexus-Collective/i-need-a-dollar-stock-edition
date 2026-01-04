"""
Binance Integration for Real-Time Prices and Perpetual Futures

Provides:
- Real-time price data via REST API
- Funding rates for perpetual contracts
- Paper trading order simulation
- (Future) Live order placement

Paper Mode: All orders are simulated locally
Live Mode: Orders placed on Binance (requires API keys with trading permissions)
"""

import asyncio
import logging
import os
import random
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING COSTS SIMULATION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TradingCosts:
    """
    Simulates realistic trading costs for paper trading.
    
    Based on Binance Futures fee schedule and typical market conditions:
    - Taker fee: 0.04% (applied on both entry and exit)
    - Spread: ~0.01-0.02% for major pairs
    - Slippage: 0.01-0.10% depending on position size vs. volume
    """
    
    # Binance Futures taker fee (0.04%)
    TAKER_FEE_RATE: float = 0.0004
    
    # Typical bid-ask spread (0.01-0.02%)
    SPREAD_MIN: float = 0.0001
    SPREAD_MAX: float = 0.0003
    
    # Slippage based on position size (0.01-0.10%)
    SLIPPAGE_MIN: float = 0.0001
    SLIPPAGE_MAX: float = 0.0010
    
    # Volume threshold for increased slippage (in USDT)
    LARGE_ORDER_THRESHOLD: float = 50000
    
    @classmethod
    def calculate_entry_price(
        cls,
        market_price: float,
        side: str,
        size_usdt: float,
        volume_24h: float = 0,
    ) -> tuple[float, float, float, float]:
        """
        Calculate realistic entry price with costs.
        
        Args:
            market_price: Current market price
            side: "LONG" or "SHORT"
            size_usdt: Position size in USDT
            volume_24h: 24h volume for slippage calculation
            
        Returns:
            Tuple of (fill_price, spread_cost, slippage_cost, fee)
        """
        # Random spread within range
        spread = random.uniform(cls.SPREAD_MIN, cls.SPREAD_MAX)
        
        # Slippage based on order size
        slippage = cls._calculate_slippage(size_usdt, volume_24h)
        
        # Total impact (spread + slippage)
        total_impact = spread + slippage
        
        # Apply direction
        if side.upper() == "LONG":
            # Buying: pay higher price
            fill_price = market_price * (1 + total_impact)
        else:
            # Selling short: receive lower price
            fill_price = market_price * (1 - total_impact)
        
        # Calculate costs
        spread_cost = market_price * spread * (size_usdt / market_price)
        slippage_cost = market_price * slippage * (size_usdt / market_price)
        fee = size_usdt * cls.TAKER_FEE_RATE
        
        return fill_price, spread_cost, slippage_cost, fee
    
    @classmethod
    def calculate_exit_price(
        cls,
        market_price: float,
        side: str,
        size_usdt: float,
        volume_24h: float = 0,
    ) -> tuple[float, float, float, float]:
        """
        Calculate realistic exit price with costs.
        
        Args:
            market_price: Current market price
            side: Original position side ("LONG" or "SHORT")
            size_usdt: Position size in USDT
            volume_24h: 24h volume for slippage calculation
            
        Returns:
            Tuple of (fill_price, spread_cost, slippage_cost, fee)
        """
        spread = random.uniform(cls.SPREAD_MIN, cls.SPREAD_MAX)
        slippage = cls._calculate_slippage(size_usdt, volume_24h)
        total_impact = spread + slippage
        
        # Opposite direction for exit
        if side.upper() == "LONG":
            # Closing long: selling, receive lower price
            fill_price = market_price * (1 - total_impact)
        else:
            # Closing short: buying back, pay higher price
            fill_price = market_price * (1 + total_impact)
        
        spread_cost = market_price * spread * (size_usdt / market_price)
        slippage_cost = market_price * slippage * (size_usdt / market_price)
        fee = size_usdt * cls.TAKER_FEE_RATE
        
        return fill_price, spread_cost, slippage_cost, fee
    
    @classmethod
    def _calculate_slippage(cls, size_usdt: float, volume_24h: float) -> float:
        """Calculate slippage based on order size vs. volume."""
        if volume_24h <= 0:
            # No volume data, use random slippage
            return random.uniform(cls.SLIPPAGE_MIN, cls.SLIPPAGE_MAX)
        
        # Larger orders relative to volume = more slippage
        size_ratio = size_usdt / volume_24h
        
        if size_ratio < 0.0001:  # < 0.01% of 24h volume
            return random.uniform(cls.SLIPPAGE_MIN, cls.SLIPPAGE_MIN * 2)
        elif size_ratio < 0.001:  # < 0.1% of 24h volume
            return random.uniform(cls.SLIPPAGE_MIN * 2, cls.SLIPPAGE_MAX / 2)
        else:
            return random.uniform(cls.SLIPPAGE_MAX / 2, cls.SLIPPAGE_MAX)


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


@dataclass
class PriceData:
    """Real-time price data for a symbol."""
    symbol: str
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Optional extended data
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    change_24h_pct: Optional[float] = None
    funding_rate: Optional[float] = None
    next_funding_time: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "bid": self.bid,
            "ask": self.ask,
            "volume_24h": self.volume_24h,
            "change_24h_pct": self.change_24h_pct,
            "funding_rate": self.funding_rate,
            "next_funding_time": self.next_funding_time.isoformat() if self.next_funding_time else None,
        }


@dataclass
class Order:
    """Represents an order (paper or live)."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "NEW"
    filled_quantity: float = 0.0
    filled_price: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Paper trading metadata
    is_paper: bool = True
    
    # Trading costs (for paper trading realism)
    market_price: Optional[float] = None  # Raw market price before costs
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    fee: float = 0.0
    total_cost: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "market_price": self.market_price,
            "spread_cost": self.spread_cost,
            "slippage_cost": self.slippage_cost,
            "fee": self.fee,
            "total_cost": self.total_cost,
            "timestamp": self.timestamp.isoformat(),
            "is_paper": self.is_paper,
        }


class BinanceClient:
    """
    Binance API client for perpetual futures.
    
    Supports both paper trading (simulated) and live trading.
    Paper mode is the default and safest for testing.
    """
    
    # Binance API endpoints
    SPOT_BASE_URL = "https://api.binance.com"
    FUTURES_BASE_URL = "https://fapi.binance.com"
    
    # Common trading pairs with USDT perpetuals
    TRADABLE_PERPS = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT",
        "MATICUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "APTUSDT",
        "SUIUSDT", "SEIUSDT", "ARBUSDT", "OPUSDT", "INJUSDT",
    ]
    
    def __init__(self, paper_mode: bool = True):
        """
        Initialize Binance client.
        
        Args:
            paper_mode: If True, all orders are simulated locally
        """
        self.paper_mode = paper_mode
        self._client: Optional[httpx.AsyncClient] = None
        
        # Price cache (refreshed on each query)
        self._price_cache: Dict[str, PriceData] = {}
        self._cache_ttl = 5  # Seconds before cache is stale
        self._last_cache_update: Optional[datetime] = None
        
        # API credentials (only needed for live trading)
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.api_secret = os.getenv("BINANCE_API_SECRET", "")
        
        if not paper_mode and (not self.api_key or not self.api_secret):
            logger.warning("Binance API credentials not set - live trading will fail!")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # PRICE DATA
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def get_price(self, symbol: str) -> float:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Current price as float
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Check cache first
        if symbol in self._price_cache:
            cached = self._price_cache[symbol]
            age = (datetime.utcnow() - cached.timestamp).total_seconds()
            if age < self._cache_ttl:
                return cached.price
        
        # Fetch from API
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/ticker/price",
                params={"symbol": symbol}
            )
            
            if response.status_code == 200:
                data = response.json()
                price = float(data["price"])
                
                # Update cache
                self._price_cache[symbol] = PriceData(
                    symbol=symbol,
                    price=price,
                )
                
                return price
            else:
                logger.warning(f"Binance price API error for {symbol}: {response.status_code}")
                # Return cached price if available
                if symbol in self._price_cache:
                    return self._price_cache[symbol].price
                raise Exception(f"Failed to get price for {symbol}")
                
        except Exception as e:
            logger.error(f"Error fetching Binance price for {symbol}: {e}")
            if symbol in self._price_cache:
                return self._price_cache[symbol].price
            raise
    
    async def get_prices(self, symbols: Optional[List[str]] = None) -> Dict[str, float]:
        """
        Get prices for multiple symbols at once.
        
        Args:
            symbols: List of symbols, or None for all tradable perps
            
        Returns:
            Dict mapping symbol to price
        """
        if symbols is None:
            symbols = self.TRADABLE_PERPS
        
        symbols = [s.upper() if s.endswith("USDT") else f"{s.upper()}USDT" for s in symbols]
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/ticker/price"
            )
            
            if response.status_code == 200:
                all_prices = {item["symbol"]: float(item["price"]) for item in response.json()}
                
                # Filter and cache
                result = {}
                for symbol in symbols:
                    if symbol in all_prices:
                        price = all_prices[symbol]
                        result[symbol] = price
                        self._price_cache[symbol] = PriceData(symbol=symbol, price=price)
                
                self._last_cache_update = datetime.utcnow()
                return result
            else:
                logger.warning(f"Binance prices API error: {response.status_code}")
                # Return cached prices
                return {s: self._price_cache[s].price for s in symbols if s in self._price_cache}
                
        except Exception as e:
            logger.error(f"Error fetching Binance prices: {e}")
            return {s: self._price_cache[s].price for s in symbols if s in self._price_cache}
    
    async def get_price_data(self, symbol: str) -> PriceData:
        """
        Get extended price data including 24h stats.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            PriceData with extended information
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        client = await self._get_client()
        
        try:
            # Get 24h ticker data
            response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/ticker/24hr",
                params={"symbol": symbol}
            )
            
            if response.status_code == 200:
                data = response.json()
                
                price_data = PriceData(
                    symbol=symbol,
                    price=float(data["lastPrice"]),
                    bid=float(data.get("bidPrice", 0)),
                    ask=float(data.get("askPrice", 0)),
                    volume_24h=float(data.get("volume", 0)),
                    change_24h_pct=float(data.get("priceChangePercent", 0)),
                )
                
                # Update cache
                self._price_cache[symbol] = price_data
                
                return price_data
            else:
                raise Exception(f"Binance 24h ticker error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching Binance price data for {symbol}: {e}")
            if symbol in self._price_cache:
                return self._price_cache[symbol]
            raise
    
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """
        Get current funding rate for a perpetual contract.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            
        Returns:
            Dict with funding rate info
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/premiumIndex",
                params={"symbol": symbol}
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "symbol": symbol,
                    "funding_rate": float(data.get("lastFundingRate", 0)),
                    "next_funding_time": datetime.fromtimestamp(
                        int(data.get("nextFundingTime", 0)) / 1000
                    ),
                    "mark_price": float(data.get("markPrice", 0)),
                    "index_price": float(data.get("indexPrice", 0)),
                }
            else:
                raise Exception(f"Funding rate API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error fetching funding rate for {symbol}: {e}")
            return {
                "symbol": symbol,
                "funding_rate": 0.0,
                "next_funding_time": None,
                "mark_price": 0.0,
                "index_price": 0.0,
            }
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # ORDER PLACEMENT (Paper Mode Only for Now)
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def open_position(
        self,
        symbol: str,
        side: str,  # "LONG" or "SHORT"
        size_usdt: float,
        leverage: int = 10,
    ) -> Order:
        """
        Open a perpetual futures position.
        
        Args:
            symbol: Trading pair (e.g., "BTC" or "BTCUSDT")
            side: "LONG" or "SHORT"
            size_usdt: Position size in USDT
            leverage: Leverage multiplier (1-125)
            
        Returns:
            Order object with fill details
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Get current market price
        market_price = await self.get_price(symbol)
        
        # Get 24h volume for slippage calculation
        volume_24h = 0.0
        if symbol in self._price_cache:
            volume_24h = self._price_cache[symbol].volume_24h or 0.0
        
        # Determine order side
        order_side = OrderSide.BUY if side.upper() == "LONG" else OrderSide.SELL
        
        if self.paper_mode:
            # Calculate realistic fill price with costs
            fill_price, spread_cost, slippage_cost, fee = TradingCosts.calculate_entry_price(
                market_price=market_price,
                side=side,
                size_usdt=size_usdt,
                volume_24h=volume_24h,
            )
            
            # Calculate quantity at fill price
            quantity = size_usdt / fill_price
            total_cost = spread_cost + slippage_cost + fee
            
            # Simulate order fill
            order = Order(
                order_id=f"PAPER_{uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                status="FILLED",
                filled_quantity=quantity,
                filled_price=fill_price,
                market_price=market_price,
                spread_cost=spread_cost,
                slippage_cost=slippage_cost,
                fee=fee,
                total_cost=total_cost,
                is_paper=True,
            )
            
            logger.info(
                f"Paper trade opened: {side} {quantity:.6f} {symbol} @ ${fill_price:,.2f} "
                f"(market: ${market_price:,.2f}, costs: ${total_cost:,.2f})"
            )
            return order
        else:
            # TODO: Implement live trading
            raise NotImplementedError("Live trading not yet implemented")
    
    async def close_position(
        self,
        symbol: str,
        side: str,  # Original position side ("LONG" or "SHORT")
        quantity: float,
        size_usdt: float = 0,  # Original position size for cost calculation
    ) -> Order:
        """
        Close a perpetual futures position.
        
        Args:
            symbol: Trading pair
            side: Original position side (LONG means we SELL to close)
            quantity: Quantity to close
            size_usdt: Original position size for cost calculation
            
        Returns:
            Order object with fill details
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Get current market price
        market_price = await self.get_price(symbol)
        
        # Get 24h volume for slippage calculation
        volume_24h = 0.0
        if symbol in self._price_cache:
            volume_24h = self._price_cache[symbol].volume_24h or 0.0
        
        # Calculate position value if not provided
        if size_usdt <= 0:
            size_usdt = quantity * market_price
        
        # Opposite side to close
        order_side = OrderSide.SELL if side.upper() == "LONG" else OrderSide.BUY
        
        if self.paper_mode:
            # Calculate realistic fill price with costs
            fill_price, spread_cost, slippage_cost, fee = TradingCosts.calculate_exit_price(
                market_price=market_price,
                side=side,
                size_usdt=size_usdt,
                volume_24h=volume_24h,
            )
            
            total_cost = spread_cost + slippage_cost + fee
            
            order = Order(
                order_id=f"PAPER_{uuid4().hex[:8].upper()}",
                symbol=symbol,
                side=order_side,
                order_type=OrderType.MARKET,
                quantity=quantity,
                status="FILLED",
                filled_quantity=quantity,
                filled_price=fill_price,
                market_price=market_price,
                spread_cost=spread_cost,
                slippage_cost=slippage_cost,
                fee=fee,
                total_cost=total_cost,
                is_paper=True,
            )
            
            logger.info(
                f"Paper trade closed: {order_side.value} {quantity:.6f} {symbol} @ ${fill_price:,.2f} "
                f"(market: ${market_price:,.2f}, costs: ${total_cost:,.2f})"
            )
            return order
        else:
            raise NotImplementedError("Live trading not yet implemented")
    
    async def set_stop_loss(
        self,
        symbol: str,
        side: str,
        quantity: float,
        stop_price: float,
    ) -> Order:
        """
        Set a stop loss order for an open position.
        
        Args:
            symbol: Trading pair
            side: Position side (LONG means stop triggers SELL)
            quantity: Quantity to close
            stop_price: Price at which stop triggers
            
        Returns:
            Order object (pending until stop triggers)
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        order_side = OrderSide.SELL if side.upper() == "LONG" else OrderSide.BUY
        
        order = Order(
            order_id=f"PAPER_SL_{uuid4().hex[:8].upper()}",
            symbol=symbol,
            side=order_side,
            order_type=OrderType.STOP_MARKET,
            quantity=quantity,
            stop_price=stop_price,
            status="NEW",
            is_paper=self.paper_mode,
        )
        
        logger.info(f"Stop loss set: {symbol} @ ${stop_price:,.2f}")
        return order
    
    async def set_take_profit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        take_profit_price: float,
    ) -> Order:
        """
        Set a take profit order for an open position.
        
        Args:
            symbol: Trading pair
            side: Position side (LONG means TP triggers SELL)
            quantity: Quantity to close
            take_profit_price: Price at which TP triggers
            
        Returns:
            Order object (pending until TP triggers)
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        order_side = OrderSide.SELL if side.upper() == "LONG" else OrderSide.BUY
        
        order = Order(
            order_id=f"PAPER_TP_{uuid4().hex[:8].upper()}",
            symbol=symbol,
            side=order_side,
            order_type=OrderType.TAKE_PROFIT_MARKET,
            quantity=quantity,
            stop_price=take_profit_price,
            status="NEW",
            is_paper=self.paper_mode,
        )
        
        logger.info(f"Take profit set: {symbol} @ ${take_profit_price:,.2f}")
        return order
    
    def get_tradable_coins(self) -> List[str]:
        """Get list of tradable perpetual coins (without USDT suffix)."""
        return [s.replace("USDT", "") for s in self.TRADABLE_PERPS]
    
    async def get_top_coins_by_volume(self, limit: int = 10) -> List[str]:
        """
        Get top coins by 24h trading volume.
        
        Args:
            limit: Number of coins to return (default 10)
            
        Returns:
            List of coin symbols (without USDT suffix), sorted by volume
        """
        client = await self._get_client()
        
        try:
            # Get 24h tickers for all futures
            response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/ticker/24hr"
            )
            
            if response.status_code == 200:
                tickers = response.json()
                
                # Filter to USDT pairs only, exclude stablecoins
                usdt_tickers = [
                    t for t in tickers
                    if t["symbol"].endswith("USDT")
                    and not any(stable in t["symbol"] for stable in ["USDC", "BUSD", "TUSD", "FDUSD", "DAI"])
                ]
                
                # Sort by 24h quote volume (volume in USDT)
                sorted_tickers = sorted(
                    usdt_tickers,
                    key=lambda x: float(x.get("quoteVolume", 0)),
                    reverse=True
                )
                
                # Extract coin symbols (without USDT)
                top_coins = [
                    t["symbol"].replace("USDT", "")
                    for t in sorted_tickers[:limit]
                ]
                
                logger.info(f"Top {limit} coins by volume: {top_coins}")
                
                # Update price cache while we have the data
                for t in sorted_tickers[:50]:  # Cache top 50
                    symbol = t["symbol"]
                    self._price_cache[symbol] = PriceData(
                        symbol=symbol,
                        price=float(t["lastPrice"]),
                        volume_24h=float(t.get("volume", 0)),
                        change_24h_pct=float(t.get("priceChangePercent", 0)),
                    )
                
                return top_coins
            else:
                logger.warning(f"Failed to fetch tickers: {response.status_code}")
                # Fallback to hardcoded list
                return self.get_tradable_coins()[:limit]
                
        except Exception as e:
            logger.error(f"Error fetching top coins by volume: {e}")
            return self.get_tradable_coins()[:limit]
    
    async def get_top_coins_by_market_cap(self, limit: int = 100) -> List[str]:
        """
        Get top coins by market cap using CoinGecko API.
        
        Only returns coins that are tradable on Binance Futures.
        Excludes stablecoins and wrapped tokens.
        
        Args:
            limit: Number of coins to return (default 100)
            
        Returns:
            List of coin symbols (without USDT suffix), sorted by market cap
        """
        client = await self._get_client()
        
        try:
            # Step 1: Get available Binance Futures symbols
            futures_response = await client.get(
                f"{self.FUTURES_BASE_URL}/fapi/v1/exchangeInfo"
            )
            
            if futures_response.status_code != 200:
                logger.warning("Could not fetch Binance futures symbols, falling back to volume")
                return await self.get_top_coins_by_volume(limit)
            
            futures_data = futures_response.json()
            binance_symbols = {
                s["symbol"].replace("USDT", "").upper()
                for s in futures_data.get("symbols", [])
                if s["symbol"].endswith("USDT") and s.get("status") == "TRADING"
            }
            
            # Step 2: Get top coins by market cap from CoinGecko
            # Fetch up to 250 coins to ensure we have enough after filtering
            coingecko_response = await client.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 250,  # Fetch more to filter stablecoins and find 100 tradable
                    "page": 1,
                    "sparkline": "false",
                }
            )
            
            if coingecko_response.status_code != 200:
                logger.warning(f"CoinGecko API failed: {coingecko_response.status_code}, falling back to volume")
                return await self.get_top_coins_by_volume(limit)
            
            coins_data = coingecko_response.json()
            
            # Step 3: Filter to only Binance-tradable coins
            SKIP_SYMBOLS = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "WBTC", "WETH", "STETH"}
            
            top_coins = []
            for coin in coins_data:
                symbol = coin.get("symbol", "").upper()
                
                # Skip stablecoins and wrapped tokens
                if symbol in SKIP_SYMBOLS:
                    continue
                
                # Check if tradable on Binance Futures
                # Handle special cases (e.g., PEPE -> 1000PEPE on Binance)
                binance_symbol = symbol
                if symbol == "PEPE":
                    binance_symbol = "1000PEPE"
                elif symbol == "SHIB":
                    binance_symbol = "1000SHIB"
                elif symbol == "FLOKI":
                    binance_symbol = "1000FLOKI"
                elif symbol == "BONK":
                    binance_symbol = "1000BONK"
                elif symbol == "LUNC":
                    binance_symbol = "1000LUNC"
                
                if binance_symbol in binance_symbols:
                    top_coins.append(binance_symbol)
                    
                    if len(top_coins) >= limit:
                        break
            
            logger.info(f"Top {len(top_coins)} coins by market cap: {top_coins}")
            return top_coins
            
        except Exception as e:
            logger.error(f"Error fetching top coins by market cap: {e}")
            # Fallback to volume-based selection
            return await self.get_top_coins_by_volume(limit)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_binance: Optional[BinanceClient] = None


def get_binance(paper_mode: bool = True) -> BinanceClient:
    """Get or create global Binance client."""
    global _binance
    if _binance is None:
        mode = os.getenv("MODE", "paper").lower()
        paper_mode = mode != "live"
        _binance = BinanceClient(paper_mode=paper_mode)
        logger.info(f"Binance client initialized in {'PAPER' if paper_mode else 'LIVE'} mode")
    return _binance

