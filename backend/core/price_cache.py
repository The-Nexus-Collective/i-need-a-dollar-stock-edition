"""
Price Cache - Real-time price storage with pub/sub

Thread-safe in-memory cache for live market prices.
Supports multiple subscribers for real-time updates.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PriceUpdate:
    """Single price update"""
    coin: str
    price: float
    timestamp: float  # Unix timestamp
    source: str = "trade"  # "trade" or "book"


@dataclass
class PriceHistory:
    """Price history for a single coin"""
    coin: str
    prices: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add(self, price: float, timestamp: float):
        self.prices.append((timestamp, price))
    
    @property
    def last_price(self) -> Optional[float]:
        return self.prices[-1][1] if self.prices else None
    
    @property
    def last_update(self) -> Optional[float]:
        return self.prices[-1][0] if self.prices else None
    
    def get_prices_since(self, since: float) -> List[tuple]:
        """Get all prices since timestamp"""
        return [(t, p) for t, p in self.prices if t >= since]


class PriceCache:
    """
    Real-time price cache with pub/sub support.
    
    Features:
    - Thread-safe updates
    - Debounced notifications (configurable)
    - Price history retention
    - Multiple subscriber support
    """
    
    def __init__(self, debounce_ms: int = 100):
        self._prices: Dict[str, float] = {}
        self._history: Dict[str, PriceHistory] = {}
        self._subscribers: List[Callable] = []
        self._debounce_ms = debounce_ms
        self._last_notify = 0
        self._pending_updates: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._notify_task: Optional[asyncio.Task] = None
    
    async def update(self, coin: str, price: float, source: str = "trade"):
        """
        Update price for a coin.
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
            price: New price in USDT
            source: Update source ('trade' or 'book')
        """
        coin = coin.upper()
        timestamp = time.time()
        
        async with self._lock:
            self._prices[coin] = price
            
            # Update history
            if coin not in self._history:
                self._history[coin] = PriceHistory(coin=coin)
            self._history[coin].add(price, timestamp)
            
            # Queue for notification
            self._pending_updates[coin] = price
        
        # Debounced notification
        await self._schedule_notify()
    
    async def _schedule_notify(self):
        """Schedule debounced notification"""
        now = time.time() * 1000  # ms
        
        if now - self._last_notify >= self._debounce_ms:
            # Immediate notify
            await self._notify_subscribers()
        elif self._notify_task is None or self._notify_task.done():
            # Schedule delayed notify
            delay = (self._debounce_ms - (now - self._last_notify)) / 1000
            self._notify_task = asyncio.create_task(self._delayed_notify(delay))
    
    async def _delayed_notify(self, delay: float):
        """Delayed notification after debounce period"""
        await asyncio.sleep(delay)
        await self._notify_subscribers()
    
    async def _notify_subscribers(self):
        """Notify all subscribers of pending updates"""
        async with self._lock:
            if not self._pending_updates:
                return
            
            updates = self._pending_updates.copy()
            self._pending_updates.clear()
            self._last_notify = time.time() * 1000
        
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(updates)
                else:
                    callback(updates)
            except Exception as e:
                logger.error(f"Subscriber callback error: {e}")
    
    def subscribe(self, callback: Callable[[Dict[str, float]], None]):
        """
        Subscribe to price updates.
        
        Callback receives: Dict[coin, price] of updated prices
        """
        self._subscribers.append(callback)
        logger.info(f"Price cache subscriber added. Total: {len(self._subscribers)}")
    
    def unsubscribe(self, callback: Callable):
        """Remove a subscriber"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    def get(self, coin: str) -> Optional[float]:
        """Get current price for a coin"""
        return self._prices.get(coin.upper())
    
    def get_all(self) -> Dict[str, float]:
        """Get all current prices"""
        return self._prices.copy()
    
    def get_history(self, coin: str, seconds: float = 60) -> List[tuple]:
        """Get price history for last N seconds"""
        coin = coin.upper()
        if coin not in self._history:
            return []
        since = time.time() - seconds
        return self._history[coin].get_prices_since(since)
    
    def get_price_change(self, coin: str, seconds: float = 3600) -> Optional[float]:
        """Get price change percentage over last N seconds"""
        history = self.get_history(coin, seconds)
        if len(history) < 2:
            return None
        
        old_price = history[0][1]
        new_price = history[-1][1]
        
        return ((new_price - old_price) / old_price) * 100


class OrderBookCache:
    """
    Real-time order book cache.
    
    Stores top 20 levels for each coin for slippage calculation.
    """
    
    def __init__(self):
        self._books: Dict[str, dict] = {}
        self._subscribers: List[Callable] = []
        self._lock = asyncio.Lock()
    
    async def update(self, coin: str, bids: List[tuple], asks: List[tuple]):
        """
        Update order book for a coin.
        
        Args:
            coin: Coin symbol
            bids: List of (price, quantity) tuples, highest first
            asks: List of (price, quantity) tuples, lowest first
        """
        coin = coin.upper()
        timestamp = time.time()
        
        async with self._lock:
            self._books[coin] = {
                'bids': bids,
                'asks': asks,
                'timestamp': timestamp,
                'mid_price': (bids[0][0] + asks[0][0]) / 2 if bids and asks else 0,
                'spread': asks[0][0] - bids[0][0] if bids and asks else 0
            }
        
        # Notify subscribers
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(coin, self._books[coin])
                else:
                    callback(coin, self._books[coin])
            except Exception as e:
                logger.error(f"Book subscriber callback error: {e}")
    
    def subscribe(self, callback: Callable):
        """Subscribe to order book updates"""
        self._subscribers.append(callback)
    
    def get(self, coin: str) -> Optional[dict]:
        """Get current order book for a coin"""
        return self._books.get(coin.upper())
    
    def get_depth(self, coin: str, side: str, quantity: float) -> tuple:
        """
        Calculate fill price and slippage for a given order size.
        
        Args:
            coin: Coin symbol
            side: 'buy' or 'sell'
            quantity: Order size in base currency
        
        Returns:
            (vwap, slippage_percent, levels_used)
        """
        book = self.get(coin)
        if not book:
            return (0, 0, 0)
        
        levels = book['asks'] if side == 'buy' else book['bids']
        if not levels:
            return (0, 0, 0)
        
        best_price = levels[0][0]
        filled = 0
        total_cost = 0
        levels_used = 0
        
        for price, qty in levels:
            fill_qty = min(quantity - filled, qty)
            total_cost += fill_qty * price
            filled += fill_qty
            levels_used += 1
            
            if filled >= quantity:
                break
        
        if filled == 0:
            return (0, 0, 0)
        
        vwap = total_cost / filled
        slippage_pct = abs(vwap - best_price) / best_price * 100
        
        return (vwap, slippage_pct, levels_used)
    
    def get_total_depth(self, coin: str, side: str, levels: int = 20) -> float:
        """Get total depth (quantity) available at N levels"""
        book = self.get(coin)
        if not book:
            return 0
        
        book_side = book['asks'] if side == 'buy' else book['bids']
        return sum(qty for _, qty in book_side[:levels])


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════

_price_cache: Optional[PriceCache] = None
_book_cache: Optional[OrderBookCache] = None


def get_price_cache() -> PriceCache:
    """Get or create global price cache"""
    global _price_cache
    if _price_cache is None:
        _price_cache = PriceCache()
    return _price_cache


def get_book_cache() -> OrderBookCache:
    """Get or create global order book cache"""
    global _book_cache
    if _book_cache is None:
        _book_cache = OrderBookCache()
    return _book_cache


async def init_caches():
    """Initialize and wire up caches with WebSocket manager"""
    from .websocket_manager import get_ws_manager
    
    price_cache = get_price_cache()
    book_cache = get_book_cache()
    ws_manager = get_ws_manager()
    
    # Wire up callbacks
    async def on_price(coin: str, price: float):
        await price_cache.update(coin, price, source="trade")
    
    async def on_book(book):
        bids = [(level.price, level.quantity) for level in book.bids]
        asks = [(level.price, level.quantity) for level in book.asks]
        await book_cache.update(book.coin, bids, asks)
    
    ws_manager.on_price(on_price)
    ws_manager.on_book(on_book)
    
    logger.info("Price and order book caches initialized")
    
    return price_cache, book_cache
