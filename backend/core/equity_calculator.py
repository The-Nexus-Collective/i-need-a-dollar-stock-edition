"""
Equity Calculator - Real-time portfolio valuation

Calculates portfolio equity on every price tick:
- Updates position PnL
- Broadcasts to dashboard via WebSocket
- Records snapshots for charting
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .account import TradingAccount, get_trading_account
from .price_cache import PriceCache, get_price_cache

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# How often to save equity snapshots to database (seconds)
SNAPSHOT_INTERVAL = 1.0

# Debounce equity broadcasts (milliseconds)
BROADCAST_DEBOUNCE_MS = 100


@dataclass
class EquityUpdate:
    """Real-time equity update for broadcasting"""
    timestamp: float  # Unix timestamp
    equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    
    # Position details
    positions: Dict[str, dict] = field(default_factory=dict)
    
    # Reference prices
    btc_price: float = 0
    
    def to_dict(self) -> dict:
        return {
            "type": "equity",
            "timestamp": self.timestamp,
            "equity": self.equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "positions": self.positions,
            "btc_price": self.btc_price
        }


class EquityCalculator:
    """
    Real-time equity calculator with pub/sub.
    
    Features:
    - Subscribes to price cache for live updates
    - Updates position PnL on every tick
    - Broadcasts equity to dashboard WebSocket
    - Periodically saves snapshots to database
    """
    
    def __init__(
        self,
        account: TradingAccount = None,
        price_cache: PriceCache = None
    ):
        self.account = account or get_trading_account()
        self.price_cache = price_cache or get_price_cache()
        
        # Subscribers for equity updates
        self._subscribers: List[Callable[[EquityUpdate], None]] = []
        
        # State
        self._last_equity: float = 0
        self._last_broadcast: float = 0
        self._last_snapshot: float = 0
        self._running: bool = False
        self._snapshot_task: Optional[asyncio.Task] = None
    
    def subscribe(self, callback: Callable[[EquityUpdate], None]):
        """Subscribe to equity updates"""
        self._subscribers.append(callback)
        logger.info(f"Equity subscriber added. Total: {len(self._subscribers)}")
    
    def unsubscribe(self, callback: Callable):
        """Remove a subscriber"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def start(self):
        """Start the equity calculator"""
        self._running = True
        
        # Subscribe to price updates
        self.price_cache.subscribe(self._on_price_update)
        
        # Start snapshot task
        self._snapshot_task = asyncio.create_task(self._snapshot_loop())
        
        logger.info("Equity calculator started")
    
    async def stop(self):
        """Stop the equity calculator"""
        self._running = False
        
        if self._snapshot_task:
            self._snapshot_task.cancel()
            try:
                await self._snapshot_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Equity calculator stopped")
    
    async def _on_price_update(self, prices: Dict[str, float]):
        """Handle price updates from cache"""
        if not self.account._loaded:
            return
        
        # Update position prices
        self.account.update_position_prices(prices)
        
        # Check if we should broadcast
        now = time.time() * 1000  # ms
        if now - self._last_broadcast >= BROADCAST_DEBOUNCE_MS:
            await self._broadcast_equity(prices)
            self._last_broadcast = now
    
    async def _broadcast_equity(self, prices: Dict[str, float]):
        """Broadcast current equity to all subscribers"""
        if not self.account._state:
            return
        
        state = self.account.state
        
        # Build position details
        positions = {}
        for coin, pos in state.positions.items():
            positions[coin] = {
                "side": pos.side,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "pnl_pct": ((pos.current_price - pos.entry_price) / pos.entry_price * 100) 
                          if pos.side == 'long' and pos.entry_price > 0
                          else ((pos.entry_price - pos.current_price) / pos.entry_price * 100)
                          if pos.entry_price > 0 else 0
            }
        
        update = EquityUpdate(
            timestamp=time.time(),
            equity=state.equity,
            cash=state.balance_usdt,
            positions_value=state.positions_value,
            unrealized_pnl=state.unrealized_pnl,
            realized_pnl=state.realized_pnl,
            positions=positions,
            btc_price=prices.get('BTC', 0)
        )
        
        # Notify subscribers
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(update)
                else:
                    callback(update)
            except Exception as e:
                logger.error(f"Equity subscriber callback error: {e}")
        
        self._last_equity = state.equity
    
    async def _snapshot_loop(self):
        """Periodically save equity snapshots to database"""
        while self._running:
            try:
                await asyncio.sleep(SNAPSHOT_INTERVAL)
                
                if self.account._loaded:
                    btc_price = self.price_cache.get('BTC') or 0
                    await self.account.record_equity(btc_price)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Snapshot error: {e}")
    
    def get_current_equity(self) -> EquityUpdate:
        """Get current equity synchronously"""
        if not self.account._state:
            return EquityUpdate(
                timestamp=time.time(),
                equity=0,
                cash=0,
                positions_value=0,
                unrealized_pnl=0,
                realized_pnl=0
            )
        
        state = self.account.state
        prices = self.price_cache.get_all()
        
        positions = {}
        for coin, pos in state.positions.items():
            positions[coin] = {
                "side": pos.side,
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl
            }
        
        return EquityUpdate(
            timestamp=time.time(),
            equity=state.equity,
            cash=state.balance_usdt,
            positions_value=state.positions_value,
            unrealized_pnl=state.unrealized_pnl,
            realized_pnl=state.realized_pnl,
            positions=positions,
            btc_price=prices.get('BTC', 0)
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_equity_calculator: Optional[EquityCalculator] = None


def get_equity_calculator() -> EquityCalculator:
    """Get or create global equity calculator"""
    global _equity_calculator
    if _equity_calculator is None:
        _equity_calculator = EquityCalculator()
    return _equity_calculator


async def init_equity_calculator() -> EquityCalculator:
    """Initialize and start equity calculator"""
    calc = get_equity_calculator()
    await calc.start()
    return calc
