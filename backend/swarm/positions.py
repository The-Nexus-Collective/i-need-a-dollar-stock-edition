"""
Position Manager - Capital and Risk Management

Tracks:
- Available capital
- Open positions
- PnL (unrealized and realized)
- Risk limits

Ensures:
- No position exceeds max size
- Total exposure stays within limits
- Stop losses are enforced
- Daily loss limits respected
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    STOPPED_OUT = "STOPPED_OUT"
    TAKE_PROFIT = "TAKE_PROFIT"


@dataclass
class Position:
    """Represents an open or closed position."""
    id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    
    # Entry details
    entry_price: float
    quantity: float
    size_usdt: float
    leverage: int = 10
    
    # Stop/Target
    stop_loss_price: Optional[float] = None
    take_profit_price: Optional[float] = None
    
    # Status
    status: PositionStatus = PositionStatus.OPEN
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    
    # PnL
    realized_pnl: float = 0.0
    
    # Metadata
    conviction: float = 0.0
    reasoning: str = ""
    
    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN
    
    def calculate_pnl(self, current_price: float) -> float:
        """Calculate unrealized PnL at a given price."""
        if self.direction == "LONG":
            pnl_pct = (current_price - self.entry_price) / self.entry_price
        else:  # SHORT
            pnl_pct = (self.entry_price - current_price) / self.entry_price
        
        # PnL in USDT (with leverage)
        return self.size_usdt * pnl_pct * self.leverage
    
    def calculate_pnl_percent(self, current_price: float) -> float:
        """Calculate unrealized PnL as percentage of position size."""
        if self.direction == "LONG":
            return ((current_price - self.entry_price) / self.entry_price) * 100 * self.leverage
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100 * self.leverage
    
    def should_stop_out(self, current_price: float) -> bool:
        """Check if stop loss should trigger."""
        if not self.stop_loss_price:
            return False
        
        if self.direction == "LONG":
            return current_price <= self.stop_loss_price
        else:
            return current_price >= self.stop_loss_price
    
    def should_take_profit(self, current_price: float) -> bool:
        """Check if take profit should trigger."""
        if not self.take_profit_price:
            return False
        
        if self.direction == "LONG":
            return current_price >= self.take_profit_price
        else:
            return current_price <= self.take_profit_price
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "status": self.status.value,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "realized_pnl": self.realized_pnl,
            "conviction": self.conviction,
            "reasoning": self.reasoning,
        }


@dataclass
class Trade:
    """Record of a completed trade."""
    id: str
    position_id: str
    symbol: str
    direction: str
    
    # Prices
    entry_price: float
    exit_price: float
    
    # Size
    quantity: float
    size_usdt: float
    leverage: int
    
    # PnL
    pnl_usdt: float
    pnl_percent: float
    
    # Timing
    entry_time: datetime
    exit_time: datetime
    duration_seconds: int
    
    # Exit type
    exit_reason: str  # "manual", "stop_loss", "take_profit"
    
    # Metadata
    conviction: float = 0.0
    reasoning: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "pnl_usdt": self.pnl_usdt,
            "pnl_percent": self.pnl_percent,
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "exit_reason": self.exit_reason,
            "conviction": self.conviction,
            "reasoning": self.reasoning,
        }


class PositionManager:
    """
    Manages trading capital and positions with risk controls.
    
    Risk Limits:
    - Max position size: 10% of capital
    - Max total exposure: 50% of capital
    - Per-trade stop loss: Max 3% drawdown
    - Daily loss limit: 5% of starting capital
    """
    
    # Risk limits (as percentages)
    MAX_POSITION_SIZE_PCT = 10.0      # Max 10% per position
    MAX_TOTAL_EXPOSURE_PCT = 50.0     # Max 50% total exposure
    MAX_STOP_LOSS_PCT = 5.0           # Max 5% stop loss distance
    DAILY_LOSS_LIMIT_PCT = 5.0        # Stop trading if down 5% today
    MIN_CONVICTION = 70               # Minimum conviction to trade (0-100)
    
    def __init__(
        self,
        initial_capital: float = 100_000.0,
        default_leverage: int = 10,
    ):
        """
        Initialize position manager.
        
        Args:
            initial_capital: Starting capital in USDT
            default_leverage: Default leverage for positions
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.default_leverage = default_leverage
        
        # Positions
        self.positions: Dict[str, Position] = {}  # position_id -> Position
        self.positions_by_symbol: Dict[str, str] = {}  # symbol -> position_id
        
        # Trade history
        self.trades: List[Trade] = []
        
        # Daily tracking
        self.daily_start_capital = initial_capital
        self.daily_pnl = 0.0
        self.last_reset_date: Optional[date] = None
        
        # Statistics
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
    
    def _reset_daily_if_needed(self):
        """Reset daily tracking at midnight."""
        today = date.today()
        if self.last_reset_date != today:
            self.daily_start_capital = self.capital
            self.daily_pnl = 0.0
            self.last_reset_date = today
            logger.info(f"Daily stats reset. Starting capital: ${self.capital:,.2f}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # RISK CHECKS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def can_open_position(
        self,
        size_usdt: float,
        conviction: int = 0,
    ) -> tuple[bool, str]:
        """
        Check if a new position can be opened.
        
        Args:
            size_usdt: Proposed position size in USDT
            conviction: Trade conviction (0-100)
            
        Returns:
            (can_trade, reason)
        """
        self._reset_daily_if_needed()
        
        # Check conviction
        if conviction < self.MIN_CONVICTION:
            return False, f"Conviction {conviction} below minimum {self.MIN_CONVICTION}"
        
        # Check daily loss limit
        if self.daily_pnl < -self.daily_start_capital * (self.DAILY_LOSS_LIMIT_PCT / 100):
            return False, f"Daily loss limit reached ({self.DAILY_LOSS_LIMIT_PCT}%)"
        
        # Check position size limit
        max_position = self.capital * (self.MAX_POSITION_SIZE_PCT / 100)
        if size_usdt > max_position:
            return False, f"Position size ${size_usdt:,.2f} exceeds max ${max_position:,.2f}"
        
        # Check total exposure limit
        current_exposure = sum(
            p.size_usdt for p in self.positions.values() if p.is_open
        )
        max_exposure = self.capital * (self.MAX_TOTAL_EXPOSURE_PCT / 100)
        if current_exposure + size_usdt > max_exposure:
            available = max_exposure - current_exposure
            return False, f"Would exceed max exposure. Available: ${available:,.2f}"
        
        # Check if we have enough capital
        if size_usdt > self.capital:
            return False, f"Insufficient capital. Available: ${self.capital:,.2f}"
        
        return True, "OK"
    
    def has_open_position(self, symbol: str) -> bool:
        """Check if there's already an open position for a symbol."""
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol in self.positions_by_symbol
    
    def get_available_capital(self) -> float:
        """Get capital available for new positions."""
        self._reset_daily_if_needed()
        
        # Check if daily limit hit
        if self.daily_pnl < -self.daily_start_capital * (self.DAILY_LOSS_LIMIT_PCT / 100):
            return 0.0
        
        # Calculate available based on exposure limit
        current_exposure = sum(
            p.size_usdt for p in self.positions.values() if p.is_open
        )
        max_exposure = self.capital * (self.MAX_TOTAL_EXPOSURE_PCT / 100)
        exposure_available = max_exposure - current_exposure
        
        # Also limited by actual cash (though in futures we use margin)
        return min(exposure_available, self.capital)
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # POSITION MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def open_position(
        self,
        symbol: str,
        direction: str,
        size_usdt: float,
        entry_price: float,
        stop_loss_pct: float = 3.0,
        take_profit_pct: float = 6.0,
        leverage: Optional[int] = None,
        conviction: float = 0.0,
        reasoning: str = "",
    ) -> Position:
        """
        Open a new position.
        
        Args:
            symbol: Trading pair (e.g., "BTCUSDT")
            direction: "LONG" or "SHORT"
            size_usdt: Position size in USDT
            entry_price: Entry price
            stop_loss_pct: Stop loss distance in percent
            take_profit_pct: Take profit distance in percent
            leverage: Position leverage (uses default if not specified)
            conviction: Trade conviction (0-100)
            reasoning: Reason for the trade
            
        Returns:
            The new Position object
        """
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        leverage = leverage or self.default_leverage
        
        # Clamp stop loss
        stop_loss_pct = min(stop_loss_pct, self.MAX_STOP_LOSS_PCT)
        
        # Calculate stop/target prices
        if direction == "LONG":
            stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
            take_profit_price = entry_price * (1 + take_profit_pct / 100)
        else:  # SHORT
            stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
            take_profit_price = entry_price * (1 - take_profit_pct / 100)
        
        # Calculate quantity
        quantity = size_usdt / entry_price
        
        # Create position
        position = Position(
            id=f"POS_{uuid4().hex[:8].upper()}",
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            size_usdt=size_usdt,
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            conviction=conviction,
            reasoning=reasoning,
        )
        
        # Store position
        self.positions[position.id] = position
        self.positions_by_symbol[symbol] = position.id
        
        logger.info(
            f"Opened {direction} position: {symbol} @ ${entry_price:,.2f} "
            f"(size: ${size_usdt:,.2f}, stop: ${stop_loss_price:,.2f}, "
            f"target: ${take_profit_price:,.2f})"
        )
        
        return position
    
    def close_position(
        self,
        position_id: str,
        exit_price: float,
        exit_reason: str = "manual",
    ) -> Trade:
        """
        Close an open position.
        
        Args:
            position_id: ID of the position to close
            exit_price: Exit price
            exit_reason: Why position was closed
            
        Returns:
            Trade record
        """
        position = self.positions.get(position_id)
        if not position or not position.is_open:
            raise ValueError(f"No open position with ID {position_id}")
        
        # Calculate PnL
        pnl_usdt = position.calculate_pnl(exit_price)
        pnl_percent = position.calculate_pnl_percent(exit_price)
        
        # Update position
        position.status = {
            "stop_loss": PositionStatus.STOPPED_OUT,
            "take_profit": PositionStatus.TAKE_PROFIT,
        }.get(exit_reason, PositionStatus.CLOSED)
        position.exit_time = datetime.utcnow()
        position.exit_price = exit_price
        position.realized_pnl = pnl_usdt
        
        # Create trade record
        trade = Trade(
            id=f"TRADE_{uuid4().hex[:8].upper()}",
            position_id=position.id,
            symbol=position.symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            size_usdt=position.size_usdt,
            leverage=position.leverage,
            pnl_usdt=pnl_usdt,
            pnl_percent=pnl_percent,
            entry_time=position.entry_time,
            exit_time=position.exit_time,
            duration_seconds=int((position.exit_time - position.entry_time).total_seconds()),
            exit_reason=exit_reason,
            conviction=position.conviction,
            reasoning=position.reasoning,
        )
        
        # Update capital
        self.capital += pnl_usdt
        self.daily_pnl += pnl_usdt
        self.total_pnl += pnl_usdt
        
        # Update stats
        self.trades.append(trade)
        self.total_trades += 1
        if pnl_usdt > 0:
            self.winning_trades += 1
        
        # Remove from active tracking
        if position.symbol in self.positions_by_symbol:
            del self.positions_by_symbol[position.symbol]
        
        logger.info(
            f"Closed {position.direction} {position.symbol} @ ${exit_price:,.2f} "
            f"| PnL: ${pnl_usdt:+,.2f} ({pnl_percent:+.2f}%) | Reason: {exit_reason}"
        )
        
        return trade
    
    def check_stops(self, current_prices: Dict[str, float]) -> List[str]:
        """
        Check if any positions should be stopped out.
        
        Args:
            current_prices: Dict mapping symbol to current price
            
        Returns:
            List of position IDs that were stopped
        """
        stopped_positions = []
        
        for position in list(self.positions.values()):
            if not position.is_open:
                continue
            
            price = current_prices.get(position.symbol)
            if not price:
                continue
            
            # Check stop loss
            if position.should_stop_out(price):
                trade = self.close_position(position.id, price, "stop_loss")
                stopped_positions.append(position.id)
                logger.warning(f"Stop loss triggered: {position.symbol} @ ${price:,.2f}")
            
            # Check take profit
            elif position.should_take_profit(price):
                trade = self.close_position(position.id, price, "take_profit")
                stopped_positions.append(position.id)
                logger.info(f"Take profit triggered: {position.symbol} @ ${price:,.2f}")
        
        return stopped_positions
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # QUERIES
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def get_open_positions(self) -> List[Position]:
        """Get all open positions."""
        return [p for p in self.positions.values() if p.is_open]
    
    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a specific position."""
        return self.positions.get(position_id)
    
    def get_position_by_symbol(self, symbol: str) -> Optional[Position]:
        """Get open position for a symbol."""
        symbol = symbol.upper()
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        position_id = self.positions_by_symbol.get(symbol)
        if position_id:
            position = self.positions.get(position_id)
            if position and position.is_open:
                return position
        return None
    
    def get_total_unrealized_pnl(self, current_prices: Dict[str, float]) -> float:
        """Calculate total unrealized PnL across all open positions."""
        total = 0.0
        for position in self.get_open_positions():
            price = current_prices.get(position.symbol)
            if price:
                total += position.calculate_pnl(price)
        return total
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get trading statistics."""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.capital,
            "total_pnl": self.total_pnl,
            "total_pnl_percent": (self.total_pnl / self.initial_capital) * 100,
            "daily_pnl": self.daily_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.total_trades - self.winning_trades,
            "win_rate": win_rate,
            "open_positions": len(self.get_open_positions()),
            "available_capital": self.get_available_capital(),
        }
    
    def to_dict(self) -> dict:
        """Serialize manager state."""
        return {
            "capital": self.capital,
            "initial_capital": self.initial_capital,
            "open_positions": [p.to_dict() for p in self.get_open_positions()],
            "statistics": self.get_statistics(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_position_manager: Optional[PositionManager] = None


def get_position_manager(initial_capital: float = 100_000.0) -> PositionManager:
    """Get or create global position manager."""
    global _position_manager
    if _position_manager is None:
        _position_manager = PositionManager(initial_capital=initial_capital)
        logger.info(f"Position manager initialized with ${initial_capital:,.2f}")
    return _position_manager

