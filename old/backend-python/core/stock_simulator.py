"""
Stock Market Simulator - Paper trading for stocks via CapTrader/IBKR style

Features:
- Realistic fill simulation with slippage
- CFD/Margin trading simulation
- Market hours awareness
- Short selling support

Uses Alpha Vantage or Yahoo Finance for real-time quotes.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

import httpx
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class StockQuote:
    """Real-time stock quote"""
    symbol: str
    price: float
    bid: float
    ask: float
    volume: int
    timestamp: datetime
    
    @property
    def spread(self) -> float:
        """Bid-ask spread as percentage"""
        if self.bid > 0:
            return (self.ask - self.bid) / self.bid * 100
        return 0.1  # Default 0.1%
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
            "spread_pct": self.spread,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class StockFill:
    """Simulated order fill"""
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    order_price: float
    fill_price: float
    slippage: float
    commission: float
    
    # CFD/Margin specific
    leverage: float = 1.0
    margin_required: float = 0.0
    
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_cost(self) -> float:
        """Total cost including commission"""
        return self.fill_price * self.quantity + self.commission
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "order_price": self.order_price,
            "fill_price": self.fill_price,
            "slippage_pct": self.slippage * 100,
            "commission": self.commission,
            "leverage": self.leverage,
            "margin_required": self.margin_required,
            "total_cost": self.total_cost,
            "timestamp": self.timestamp.isoformat(),
        }


class StockSimulator:
    """
    Paper trading simulator for stocks.
    
    Features:
    - Real-time quotes from Yahoo Finance
    - Gaussian slippage model
    - Commission simulation (IBKR rates)
    - CFD/margin leverage
    - Short selling support
    """
    
    # IBKR-style commission structure
    COMMISSION_MIN = 1.0  # $1 minimum
    COMMISSION_PER_SHARE = 0.005  # $0.005 per share
    
    # Slippage model
    SLIPPAGE_MEAN = 0.0005  # 0.05% mean
    SLIPPAGE_STD = 0.0003   # 0.03% std
    
    # Margin requirements (for CFDs)
    MARGIN_REQUIREMENT = 0.20  # 20% margin = 5x max leverage
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._quote_cache: Dict[str, StockQuote] = {}
        self._cache_ttl = 60  # 1 minute
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """
        Get real-time quote for a stock.
        
        Uses Yahoo Finance (free, no API key needed).
        """
        # Check cache
        cache_key = symbol.upper()
        if cache_key in self._quote_cache:
            cached = self._quote_cache[cache_key]
            age = (datetime.utcnow() - cached.timestamp).total_seconds()
            if age < self._cache_ttl:
                return cached
        
        client = await self._get_client()
        
        try:
            # Yahoo Finance API (unofficial but works)
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
            response = await client.get(url, params={"interval": "1m", "range": "1d"})
            
            if response.status_code != 200:
                logger.error(f"Yahoo Finance error: {response.status_code}")
                return None
            
            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            
            quote = StockQuote(
                symbol=symbol.upper(),
                price=meta.get("regularMarketPrice", 0),
                bid=meta.get("bid", meta.get("regularMarketPrice", 0) * 0.999),
                ask=meta.get("ask", meta.get("regularMarketPrice", 0) * 1.001),
                volume=meta.get("regularMarketVolume", 0),
                timestamp=datetime.utcnow(),
            )
            
            self._quote_cache[cache_key] = quote
            return quote
            
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None
    
    async def get_quotes(self, symbols: List[str]) -> Dict[str, StockQuote]:
        """Get quotes for multiple symbols"""
        quotes = {}
        for symbol in symbols:
            quote = await self.get_quote(symbol)
            if quote:
                quotes[symbol] = quote
            await asyncio.sleep(0.1)  # Rate limit
        return quotes
    
    def _simulate_slippage(self, side: str) -> float:
        """
        Generate realistic slippage using Gaussian model.
        
        Returns:
            Slippage as decimal (e.g., 0.001 = 0.1%)
        """
        base_slippage = np.random.normal(self.SLIPPAGE_MEAN, self.SLIPPAGE_STD)
        # Ensure positive slippage (always against us)
        slippage = max(0.0001, min(0.005, abs(base_slippage)))
        return slippage
    
    def _calculate_commission(self, quantity: float, price: float) -> float:
        """Calculate IBKR-style commission"""
        per_share = quantity * self.COMMISSION_PER_SHARE
        return max(self.COMMISSION_MIN, per_share)
    
    async def simulate_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        leverage: float = 1.0
    ) -> Optional[StockFill]:
        """
        Simulate a market order fill.
        
        Args:
            symbol: Stock symbol
            side: 'buy' or 'sell' (or 'short' for shorting)
            quantity: Number of shares
            leverage: Leverage multiplier (1x-5x)
        
        Returns:
            StockFill with simulated execution details
        """
        quote = await self.get_quote(symbol)
        if not quote:
            logger.error(f"Cannot get quote for {symbol}")
            return None
        
        # Use bid/ask depending on side
        if side in ('buy', 'cover'):
            base_price = quote.ask
        else:  # sell, short
            base_price = quote.bid
        
        # Apply slippage
        slippage = self._simulate_slippage(side)
        if side in ('buy', 'cover'):
            fill_price = base_price * (1 + slippage)
        else:
            fill_price = base_price * (1 - slippage)
        
        # Calculate commission
        commission = self._calculate_commission(quantity, fill_price)
        
        # Calculate margin for leveraged trades
        notional = fill_price * quantity
        if leverage > 1:
            margin_required = notional / leverage
        else:
            margin_required = notional
        
        fill = StockFill(
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_price=base_price,
            fill_price=fill_price,
            slippage=slippage,
            commission=commission,
            leverage=leverage,
            margin_required=margin_required,
        )
        
        logger.info(
            f"Simulated {side} {quantity} {symbol} @ ${fill_price:.2f} "
            f"(slippage: {slippage*100:.3f}%, commission: ${commission:.2f})"
        )
        
        return fill
    
    async def simulate_cfd_position(
        self,
        symbol: str,
        side: str,  # 'long' or 'short'
        notional_value: float,
        leverage: float = 5.0
    ) -> Optional[StockFill]:
        """
        Simulate opening a CFD position.
        
        CFDs allow:
        - Long or short without borrowing
        - Leverage up to 5x
        - Pay spread + overnight financing
        
        Args:
            symbol: Stock symbol
            side: 'long' or 'short'
            notional_value: Total position value
            leverage: Leverage multiplier (3x-5x)
        
        Returns:
            StockFill representing the position
        """
        quote = await self.get_quote(symbol)
        if not quote:
            return None
        
        # Calculate quantity from notional
        quantity = notional_value / quote.price
        
        # Map side to order type
        order_side = 'buy' if side == 'long' else 'short'
        
        return await self.simulate_order(
            symbol=symbol,
            side=order_side,
            quantity=quantity,
            leverage=leverage
        )
    
    def calculate_overnight_cost(
        self,
        notional_value: float,
        leverage: float,
        days: int = 1
    ) -> float:
        """
        Calculate overnight financing cost for leveraged position.
        
        CFD financing is roughly:
        - Long: Pay benchmark rate + spread (~3-5% annual)
        - Short: Receive benchmark rate - spread (often ~0)
        
        Returns:
            Daily financing cost in USD
        """
        annual_rate = 0.05  # 5% annual
        daily_rate = annual_rate / 365
        
        # Only pay financing on borrowed portion
        borrowed = notional_value * (1 - 1/leverage)
        return borrowed * daily_rate * days
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_stock_simulator: Optional[StockSimulator] = None


def get_stock_simulator() -> StockSimulator:
    """Get or create global stock simulator"""
    global _stock_simulator
    if _stock_simulator is None:
        _stock_simulator = StockSimulator()
    return _stock_simulator

