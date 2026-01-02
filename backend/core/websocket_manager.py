"""
Binance WebSocket Manager - Real-time market data streams

Connects to Binance Futures WebSocket for:
- Trade streams (real-time prices)
- Order book depth (for slippage calculation)

No API key required - uses public endpoints.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Top 10 coins to track
COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'TRX', 'LINK']

# Binance Futures WebSocket endpoints (public, no key needed)
WS_BASE_URL = "wss://fstream.binance.com"

# Stream types
TRADE_STREAM = "@trade"           # Real-time trades
DEPTH_STREAM = "@depth20@100ms"   # Order book top 20 levels, 100ms updates


@dataclass
class Trade:
    """Single trade from WebSocket"""
    coin: str
    price: float
    quantity: float
    timestamp: datetime
    is_buyer_maker: bool


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    quantity: float


@dataclass
class OrderBook:
    """Order book snapshot"""
    coin: str
    bids: List[OrderBookLevel]  # Sorted highest to lowest
    asks: List[OrderBookLevel]  # Sorted lowest to highest
    timestamp: datetime
    
    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0
    
    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 0
    
    @property
    def mid_price(self) -> float:
        return (self.best_bid + self.best_ask) / 2 if self.bids and self.asks else 0
    
    @property
    def spread(self) -> float:
        return self.best_ask - self.best_bid if self.bids and self.asks else 0
    
    @property
    def spread_percent(self) -> float:
        return (self.spread / self.mid_price * 100) if self.mid_price > 0 else 0


class BinanceWSManager:
    """
    Manages WebSocket connections to Binance Futures.
    
    Features:
    - Automatic reconnection
    - Combined stream for efficiency
    - Pub/sub for price and order book updates
    - Thread-safe callbacks
    """
    
    def __init__(self, coins: List[str] = None):
        self.coins = coins or COINS
        self.running = False
        
        # Callbacks
        self._trade_callbacks: List[Callable[[Trade], None]] = []
        self._book_callbacks: List[Callable[[OrderBook], None]] = []
        self._price_callbacks: List[Callable[[str, float], None]] = []
        
        # Current state
        self._prices: Dict[str, float] = {}
        self._books: Dict[str, OrderBook] = {}
        
        # Connection state
        self._ws = None
        self._reconnect_delay = 1
        self._max_reconnect_delay = 60
    
    def _build_stream_url(self) -> str:
        """Build combined stream URL for all coins"""
        streams = []
        
        for coin in self.coins:
            symbol = f"{coin.lower()}usdt"
            streams.append(f"{symbol}{TRADE_STREAM}")
            streams.append(f"{symbol}{DEPTH_STREAM}")
        
        stream_param = "/".join(streams)
        return f"{WS_BASE_URL}/stream?streams={stream_param}"
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SUBSCRIPTION METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_trade(self, callback: Callable[[Trade], None]):
        """Subscribe to trade updates"""
        self._trade_callbacks.append(callback)
    
    def on_book(self, callback: Callable[[OrderBook], None]):
        """Subscribe to order book updates"""
        self._book_callbacks.append(callback)
    
    def on_price(self, callback: Callable[[str, float], None]):
        """Subscribe to price updates (coin, price)"""
        self._price_callbacks.append(callback)
    
    def get_price(self, coin: str) -> Optional[float]:
        """Get last known price for a coin"""
        return self._prices.get(coin.upper())
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all current prices"""
        return self._prices.copy()
    
    def get_book(self, coin: str) -> Optional[OrderBook]:
        """Get current order book for a coin"""
        return self._books.get(coin.upper())
    
    # ═══════════════════════════════════════════════════════════════════════════
    # MESSAGE HANDLING
    # ═══════════════════════════════════════════════════════════════════════════
    
    def _parse_trade(self, data: dict) -> Trade:
        """Parse trade message from WebSocket"""
        symbol = data['s']  # e.g., "BTCUSDT"
        coin = symbol.replace('USDT', '')
        
        return Trade(
            coin=coin,
            price=float(data['p']),
            quantity=float(data['q']),
            timestamp=datetime.fromtimestamp(data['T'] / 1000),
            is_buyer_maker=data['m']
        )
    
    def _parse_depth(self, data: dict, stream: str) -> OrderBook:
        """Parse order book depth message"""
        # Stream format: "btcusdt@depth20@100ms"
        symbol = stream.split('@')[0].upper()
        coin = symbol.replace('USDT', '')
        
        bids = [
            OrderBookLevel(price=float(p), quantity=float(q))
            for p, q in data['b']
        ]
        asks = [
            OrderBookLevel(price=float(p), quantity=float(q))
            for p, q in data['a']
        ]
        
        return OrderBook(
            coin=coin,
            bids=bids,
            asks=asks,
            timestamp=datetime.now()
        )
    
    async def _handle_message(self, message: str):
        """Handle incoming WebSocket message"""
        try:
            data = json.loads(message)
            
            if 'stream' not in data:
                return
            
            stream = data['stream']
            payload = data['data']
            
            if '@trade' in stream:
                # Trade message
                trade = self._parse_trade(payload)
                
                # Update price cache
                self._prices[trade.coin] = trade.price
                
                # Notify subscribers
                for callback in self._price_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(trade.coin, trade.price)
                        else:
                            callback(trade.coin, trade.price)
                    except Exception as e:
                        logger.error(f"Price callback error: {e}")
                
                for callback in self._trade_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(trade)
                        else:
                            callback(trade)
                    except Exception as e:
                        logger.error(f"Trade callback error: {e}")
            
            elif '@depth' in stream:
                # Order book message
                book = self._parse_depth(payload, stream)
                
                # Update book cache
                self._books[book.coin] = book
                
                # Also update price from mid
                if book.mid_price > 0:
                    self._prices[book.coin] = book.mid_price
                
                # Notify subscribers
                for callback in self._book_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(book)
                        else:
                            callback(book)
                    except Exception as e:
                        logger.error(f"Book callback error: {e}")
                        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
        except Exception as e:
            logger.error(f"Message handling error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CONNECTION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def connect(self):
        """Connect to Binance WebSocket and start receiving data"""
        self.running = True
        url = self._build_stream_url()
        
        logger.info(f"Connecting to Binance WebSocket: {len(self.coins)} coins")
        
        while self.running:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self._ws = ws
                    self._reconnect_delay = 1  # Reset on successful connect
                    
                    logger.info("WebSocket connected successfully")
                    
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)
                        
            except ConnectionClosed as e:
                logger.warning(f"WebSocket closed: {e}")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self.running:
                logger.info(f"Reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(
                    self._reconnect_delay * 2,
                    self._max_reconnect_delay
                )
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("WebSocket disconnected")
    
    async def start(self):
        """Start the WebSocket manager (alias for connect)"""
        await self.connect()
    
    async def stop(self):
        """Stop the WebSocket manager (alias for disconnect)"""
        await self.disconnect()


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_ws_manager: Optional[BinanceWSManager] = None


def get_ws_manager() -> BinanceWSManager:
    """Get or create the global WebSocket manager"""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = BinanceWSManager()
    return _ws_manager


async def start_ws_manager() -> BinanceWSManager:
    """Start the global WebSocket manager"""
    manager = get_ws_manager()
    asyncio.create_task(manager.start())
    return manager


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Standalone test runner"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    manager = BinanceWSManager()
    
    # Example callbacks
    def on_price(coin: str, price: float):
        print(f"{coin}: ${price:,.2f}")
    
    def on_book(book: OrderBook):
        print(f"{book.coin} Book: bid={book.best_bid:.2f} ask={book.best_ask:.2f} spread={book.spread_percent:.4f}%")
    
    manager.on_price(on_price)
    manager.on_book(on_book)
    
    try:
        await manager.start()
    except KeyboardInterrupt:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
