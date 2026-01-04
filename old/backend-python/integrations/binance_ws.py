"""
Binance WebSocket Client for Real-Time Price Streaming

Provides real-time price updates for all tracked symbols via Binance's
futures WebSocket streams.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# WebSocket URL for Binance Futures
BINANCE_WS_URL = "wss://fstream.binance.com/ws"


@dataclass
class PriceTick:
    """A single price update."""
    symbol: str
    price: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
        }


class BinanceWebSocket:
    """
    WebSocket client for real-time Binance Futures prices.
    
    Subscribes to mark price streams for all tracked symbols and
    broadcasts price updates to registered callbacks.
    """
    
    def __init__(self, symbols: Optional[List[str]] = None):
        """
        Initialize WebSocket client.
        
        Args:
            symbols: Initial list of symbols to track (e.g., ["BTCUSDT", "ETHUSDT"])
        """
        self._symbols: Set[str] = set(symbols or [])
        self._prices: Dict[str, float] = {}
        self._last_update: Dict[str, datetime] = {}
        self._callbacks: List[Callable[[PriceTick], None]] = []
        self._ws = None
        self._running = False
        self._reconnect_delay = 1
        self._task: Optional[asyncio.Task] = None
    
    def add_symbol(self, symbol: str):
        """Add a symbol to track."""
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        self._symbols.add(symbol)
    
    def add_symbols(self, symbols: List[str]):
        """Add multiple symbols to track."""
        for symbol in symbols:
            self.add_symbol(symbol)
    
    def remove_symbol(self, symbol: str):
        """Remove a symbol from tracking."""
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        self._symbols.discard(symbol)
    
    def on_price(self, callback: Callable[[PriceTick], None]):
        """Register a callback for price updates."""
        self._callbacks.append(callback)
    
    def get_price(self, symbol: str) -> Optional[float]:
        """Get the latest price for a symbol."""
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return self._prices.get(symbol)
    
    def get_all_prices(self) -> Dict[str, float]:
        """Get all current prices."""
        return self._prices.copy()
    
    async def start(self):
        """Start the WebSocket connection."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_forever())
        logger.info(f"Binance WebSocket started, tracking {len(self._symbols)} symbols")
    
    async def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Binance WebSocket stopped")
    
    async def _run_forever(self):
        """Main loop that maintains the WebSocket connection."""
        while self._running:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"WebSocket error: {e}, reconnecting in {self._reconnect_delay}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
    
    async def _connect_and_listen(self):
        """Connect to WebSocket and listen for messages."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed. Install with: pip install websockets")
            return
        
        if not self._symbols:
            logger.warning("No symbols to track, waiting...")
            await asyncio.sleep(5)
            return
        
        # Build stream names for all symbols
        # Using markPrice stream for mark price updates (every 3s by default, or every 1s with @1s)
        streams = [f"{s.lower()}@markPrice@1s" for s in self._symbols]
        
        # Combined stream URL
        stream_url = f"{BINANCE_WS_URL}"
        
        logger.info(f"Connecting to Binance WebSocket for {len(self._symbols)} symbols...")
        
        async with websockets.connect(stream_url, ping_interval=20) as ws:
            self._ws = ws
            self._reconnect_delay = 1  # Reset on successful connect
            
            # Subscribe to streams
            subscribe_msg = {
                "method": "SUBSCRIBE",
                "params": streams,
                "id": 1
            }
            await ws.send(json.dumps(subscribe_msg))
            logger.info(f"Subscribed to {len(streams)} price streams")
            
            # Listen for messages
            async for message in ws:
                try:
                    data = json.loads(message)
                    
                    # Skip subscription confirmations
                    if "result" in data or "id" in data:
                        continue
                    
                    # Process mark price update
                    if "e" in data and data["e"] == "markPriceUpdate":
                        symbol = data["s"]
                        price = float(data["p"])  # Mark price
                        
                        self._prices[symbol] = price
                        self._last_update[symbol] = datetime.utcnow()
                        
                        tick = PriceTick(symbol=symbol, price=price)
                        
                        # Notify callbacks
                        for callback in self._callbacks:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(tick)
                                else:
                                    callback(tick)
                            except Exception as e:
                                logger.warning(f"Callback error: {e}")
                    
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message[:100]}")
                except Exception as e:
                    logger.warning(f"Error processing message: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_binance_ws: Optional[BinanceWebSocket] = None


def get_binance_ws() -> BinanceWebSocket:
    """Get or create global Binance WebSocket client."""
    global _binance_ws
    if _binance_ws is None:
        _binance_ws = BinanceWebSocket()
    return _binance_ws


async def start_price_streaming(symbols: List[str] = None):
    """Start the global price streaming with given symbols."""
    ws = get_binance_ws()
    if symbols:
        ws.add_symbols(symbols)
    await ws.start()
    return ws


async def stop_price_streaming():
    """Stop the global price streaming."""
    global _binance_ws
    if _binance_ws:
        await _binance_ws.stop()
        _binance_ws = None

