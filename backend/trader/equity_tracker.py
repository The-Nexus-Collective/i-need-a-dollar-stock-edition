"""
Real-Time Equity Tracker

Calculates portfolio value every second using live prices from
Binance WebSocket and broadcasts updates to the frontend.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional
from dataclasses import dataclass, field

from integrations.binance_ws import get_binance_ws, PriceTick

logger = logging.getLogger(__name__)


@dataclass
class EquitySnapshot:
    """A point-in-time equity value."""
    timestamp: datetime
    total_equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    position_details: List[dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_equity": self.total_equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl,
            "position_details": self.position_details,
        }


class EquityTracker:
    """
    Tracks portfolio equity in real-time.
    
    Uses live prices from Binance WebSocket to calculate unrealized PnL
    and total portfolio value every second.
    """
    
    def __init__(self, executor=None):
        """
        Initialize equity tracker.
        
        Args:
            executor: Reference to the Executor instance for position data
        """
        self._executor = executor
        self._callbacks: List[Callable[[EquitySnapshot], None]] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._latest_snapshot: Optional[EquitySnapshot] = None
        self._history: List[EquitySnapshot] = []
        self._max_history = 3600  # Keep 1 hour of second-by-second data
    
    def set_executor(self, executor):
        """Set the executor reference."""
        logger.info(f"EquityTracker: Setting executor_id={id(executor)}")
        self._executor = executor
    
    def on_equity_update(self, callback: Callable[[EquitySnapshot], None]):
        """Register a callback for equity updates."""
        self._callbacks.append(callback)
    
    def get_latest(self) -> Optional[EquitySnapshot]:
        """Get the latest equity snapshot."""
        return self._latest_snapshot
    
    def get_history(self, limit: int = 60) -> List[EquitySnapshot]:
        """Get recent equity history."""
        return self._history[-limit:]
    
    def reset_state(self):
        """Reset all tracked equity data. Called when paper trades are reset."""
        self._latest_snapshot = None
        self._history = []
        
        # Also reset the executor's capital if we have a reference to it
        if self._executor:
            old_capital = self._executor.capital
            self._executor.reset_state()
            logger.warning(f"RESET: Executor capital ${old_capital:,.2f} -> ${self._executor.capital:,.2f}")
        else:
            logger.error("RESET FAILED: No executor reference in equity tracker!")
        
        logger.info("Equity tracker state reset")
    
    async def start(self):
        """Start the equity tracking loop."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Equity tracker started")
    
    async def stop(self):
        """Stop the equity tracking loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Equity tracker stopped")
    
    async def _run_loop(self):
        """Main loop that calculates equity every second."""
        while self._running:
            try:
                snapshot = await self._calculate_equity()
                
                if snapshot:
                    self._latest_snapshot = snapshot
                    self._history.append(snapshot)
                    
                    # Trim history
                    if len(self._history) > self._max_history:
                        self._history = self._history[-self._max_history:]
                    
                    # Notify callbacks
                    for callback in self._callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(snapshot)
                            else:
                                callback(snapshot)
                        except Exception as e:
                            logger.warning(f"Equity callback error: {e}")
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Equity calculation error: {e}")
                await asyncio.sleep(1)
    
    async def _calculate_equity(self) -> Optional[EquitySnapshot]:
        """Calculate current portfolio equity."""
        if not self._executor:
            logger.debug("No executor reference - returning None")
            return None
        
        ws = get_binance_ws()
        prices = ws.get_all_prices()
        
        cash = self._executor.capital
        num_positions = len(self._executor.positions)
        
        # Debug: Log executor ID and state
        logger.debug(f"Calculating equity: executor_id={id(self._executor)}, capital=${cash:,.2f}, positions={num_positions}")
        
        positions_value = 0.0
        unrealized_pnl = 0.0
        position_details = []
        
        for symbol, position in self._executor.positions.items():
            current_price = prices.get(symbol)
            
            # Validate price is plausible (within 50% of entry price)
            # This catches cases where WebSocket returns wrong price (e.g., different contract)
            if current_price is not None and position.entry_price > 0:
                price_ratio = current_price / position.entry_price
                if price_ratio < 0.5 or price_ratio > 2.0:
                    # Price looks wrong, use entry price instead
                    current_price = position.entry_price
            
            if current_price is None:
                # Fallback to entry price if no live price
                current_price = position.entry_price
            
            # Calculate position value
            pos_value = position.quantity * current_price
            
            # Calculate unrealized PnL
            if position.direction == "LONG":
                pnl_pct = (current_price - position.entry_price) / position.entry_price
            else:  # SHORT
                pnl_pct = (position.entry_price - current_price) / position.entry_price
            
            # Leverage amplifies PnL
            pnl_pct *= position.leverage
            pnl = position.size_usdt * pnl_pct
            
            positions_value += pos_value
            unrealized_pnl += pnl
            
            position_details.append({
                "symbol": symbol,
                "direction": position.direction,
                "entry_price": position.entry_price,
                "current_price": current_price,
                "quantity": position.quantity,
                "size_usdt": position.size_usdt,
                "leverage": position.leverage,
                "unrealized_pnl": pnl,
                "pnl_pct": pnl_pct * 100,
            })
        
        # Total equity = cash + unrealized PnL
        # (We don't add positions_value because size_usdt already represents margin)
        total_equity = cash + unrealized_pnl
        
        return EquitySnapshot(
            timestamp=datetime.utcnow(),
            total_equity=total_equity,
            cash=cash,
            positions_value=positions_value,
            unrealized_pnl=unrealized_pnl,
            position_details=position_details,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_equity_tracker: Optional[EquityTracker] = None


def get_equity_tracker() -> EquityTracker:
    """Get or create global equity tracker."""
    global _equity_tracker
    if _equity_tracker is None:
        _equity_tracker = EquityTracker()
    return _equity_tracker


async def start_equity_tracking(executor=None) -> EquityTracker:
    """Start the global equity tracker."""
    tracker = get_equity_tracker()
    if executor:
        tracker.set_executor(executor)
    await tracker.start()
    return tracker


async def stop_equity_tracking():
    """Stop the global equity tracker."""
    global _equity_tracker
    if _equity_tracker:
        await _equity_tracker.stop()
        _equity_tracker = None

