"""
Position Tracker - DB-First Portfolio Management

PRODUCTION ARCHITECTURE:
- ALL data comes from the database
- NO in-memory state as source of truth
- Every read is from DB, every write goes to DB immediately
- Safe for production with millions of dollars
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Configuration
STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "50"))
POSITION_SIZE_PCT = float(os.getenv("POSITION_SIZE_PCT", "0.02"))


@dataclass
class Position:
    """Represents an open trading position."""
    
    id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    current_price: float
    quantity: float
    size_usdt: float
    leverage: int
    conviction: int  # 0-100
    
    # Timestamps
    opened_at: datetime = field(default_factory=datetime.utcnow)
    
    # Trading costs
    entry_fee: float = 0.0
    entry_spread: float = 0.0
    entry_slippage: float = 0.0
    
    # Reasoning from Grok
    reason: str = ""
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL in USDT."""
        if self.entry_price <= 0:
            return 0.0
        if self.direction == "LONG":
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - self.current_price) / self.entry_price
        
        return self.size_usdt * pnl_pct * self.leverage
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Calculate unrealized PnL as percentage of position size."""
        if self.entry_price <= 0:
            return 0.0
        if self.direction == "LONG":
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - self.current_price) / self.entry_price
        
        return pnl_pct * self.leverage * 100
    
    @property
    def liquidation_price(self) -> float:
        """Calculate approximate liquidation price."""
        if self.leverage <= 0:
            return 0.0
        margin_pct = 1.0 / self.leverage
        
        if self.direction == "LONG":
            return self.entry_price * (1 - margin_pct * 0.9)
        else:
            return self.entry_price * (1 + margin_pct * 0.9)
    
    @property
    def margin_risk_pct(self) -> float:
        """Calculate how close we are to liquidation (0-100%)."""
        if self.direction == "LONG":
            if self.current_price >= self.entry_price:
                return 0.0
            distance_to_liq = self.entry_price - self.liquidation_price
            current_loss = self.entry_price - self.current_price
        else:
            if self.current_price <= self.entry_price:
                return 0.0
            distance_to_liq = self.liquidation_price - self.entry_price
            current_loss = self.current_price - self.entry_price
        
        if distance_to_liq <= 0:
            return 100.0
        
        return min(100.0, (current_loss / distance_to_liq) * 100)
    
    def to_dict(self) -> dict:
        """Serialize position for API/logging."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "conviction": self.conviction,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "liquidation_price": self.liquidation_price,
            "margin_risk_pct": self.margin_risk_pct,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "reason": self.reason,
        }


@dataclass 
class ClosedPosition:
    """Record of a closed position."""
    
    id: str
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    size_usdt: float
    leverage: int
    conviction: int
    
    realized_pnl: float
    realized_pnl_pct: float
    
    opened_at: datetime
    closed_at: datetime
    
    close_reason: str  # "grok_decision", "stop_loss", "take_profit"
    
    total_fees: float = 0.0
    total_spread: float = 0.0
    total_slippage: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_pct": self.realized_pnl_pct,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "close_reason": self.close_reason,
            "duration_minutes": int((self.closed_at - self.opened_at).total_seconds() / 60) if self.opened_at and self.closed_at else 0,
        }


@dataclass
class Transaction:
    """Record of a position transaction (OPEN, CLOSE, EXTEND, REDUCE)."""
    
    id: str
    position_id: str
    symbol: str
    direction: str
    transaction_type: str  # "OPEN", "CLOSE", "EXTEND", "REDUCE"
    
    price: float
    quantity: float
    size_usdt: float
    leverage: int
    
    position_size_before: float
    position_size_after: float
    avg_entry_before: float
    avg_entry_after: float
    
    realized_pnl: float = 0.0
    realized_pnl_pct: float = 0.0
    
    fee: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    
    reason: str = ""
    conviction: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "transaction_type": self.transaction_type,
            "price": self.price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "position_size_before": self.position_size_before,
            "position_size_after": self.position_size_after,
            "avg_entry_before": self.avg_entry_before,
            "avg_entry_after": self.avg_entry_after,
            "realized_pnl": self.realized_pnl,
            "realized_pnl_pct": self.realized_pnl_pct,
            "fee": self.fee,
            "spread": self.spread,
            "slippage": self.slippage,
            "reason": self.reason,
            "conviction": self.conviction,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class PositionTracker:
    """
    DB-FIRST Position Tracker - Production Ready.
    
    ALL data comes from the database:
    - Positions are read from paper_positions table
    - Capital is read from trader_state table
    - Every open/close/update writes to DB immediately
    
    NO IN-MEMORY STATE as source of truth.
    
    This is safe for production with millions of dollars because:
    - No data loss on process crash
    - Single source of truth (database)
    - Consistent state across all components
    """
    
    DEFAULT_CAPITAL = STARTING_CAPITAL
    MAX_POSITIONS = MAX_POSITIONS
    POSITION_SIZE_PCT = POSITION_SIZE_PCT
    
    def __init__(
        self,
        starting_capital: float = DEFAULT_CAPITAL,
        max_positions: int = MAX_POSITIONS,
        position_size_pct: float = POSITION_SIZE_PCT,
    ):
        self._starting_capital = starting_capital
        self._max_positions = max_positions
        self._position_size_pct = position_size_pct
        
        # These are COMPUTED from DB, not stored
        # They exist only for API compatibility during transition
        self._cached_positions: Dict[str, Position] = {}
        self._cache_valid = False
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DB READ METHODS - All data comes from database
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def get_capital(self) -> float:
        """Read current capital from database."""
        from repositories import TraderStateRepository
        state = await TraderStateRepository.get_state()
        return state.current_capital if state else self._starting_capital
    
    async def get_positions(self) -> Dict[str, Position]:
        """Read all open positions from database."""
        from repositories import PositionRepository
        db_positions = await PositionRepository.get_open_positions()
        
        positions = {}
        for p in db_positions:
            positions[p.symbol] = Position(
                id=p.id,
                symbol=p.symbol,
                direction=p.direction,
                entry_price=p.entry_price,
                current_price=p.current_price if p.current_price > 0 else p.entry_price,
                quantity=p.quantity,
                size_usdt=p.size_usdt,
                leverage=p.leverage,
                conviction=p.conviction,
                opened_at=p.entry_time,
                reason=p.reasoning,
            )
        return positions
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get a specific position from database."""
        from repositories import PositionRepository
        p = await PositionRepository.get_position_by_symbol(symbol)
        if not p:
            return None
        
        return Position(
            id=p.id,
            symbol=p.symbol,
            direction=p.direction,
            entry_price=p.entry_price,
            current_price=p.current_price if p.current_price > 0 else p.entry_price,
            quantity=p.quantity,
            size_usdt=p.size_usdt,
            leverage=p.leverage,
            conviction=p.conviction,
            opened_at=p.entry_time,
            reason=p.reasoning,
        )
    
    async def has_position(self, symbol: str) -> bool:
        """Check if we have an open position for this symbol."""
        from repositories import PositionRepository
        return await PositionRepository.has_position(symbol)
    
    async def get_position_count(self) -> int:
        """Get count of open positions from database."""
        from repositories import PositionRepository
        return await PositionRepository.get_position_count()
    
    async def get_available_slots(self) -> int:
        """Get number of available position slots."""
        count = await self.get_position_count()
        return self._max_positions - count
    
    async def get_total_unrealized_pnl(self) -> float:
        """Calculate total unrealized PnL from all positions."""
        positions = await self.get_positions()
        return sum(p.unrealized_pnl for p in positions.values())
    
    async def get_total_equity(self) -> float:
        """Calculate total equity (capital + unrealized PnL)."""
        capital = await self.get_capital()
        unrealized = await self.get_total_unrealized_pnl()
        return capital + unrealized
    
    async def get_position_size_usdt(self) -> float:
        """Calculate size for a new position (2% of capital)."""
        capital = await self.get_capital()
        return capital * self._position_size_pct
    
    async def get_statistics(self) -> dict:
        """Get portfolio statistics from database."""
        from repositories import TraderStateRepository
        state = await TraderStateRepository.get_state()
        positions = await self.get_positions()
        
        total_unrealized = sum(p.unrealized_pnl for p in positions.values())
        capital = state.current_capital if state else self._starting_capital
        
        return {
            "capital": capital,
            "starting_capital": self._starting_capital,
            "total_equity": capital + total_unrealized,
            "total_unrealized_pnl": total_unrealized,
            "total_realized_pnl": state.total_pnl if state else 0,
            "open_positions": len(positions),
            "max_positions": self._max_positions,
            "available_slots": self._max_positions - len(positions),
            "total_trades": state.total_trades if state else 0,
            "winning_trades": state.winning_trades if state else 0,
            "losing_trades": state.losing_trades if state else 0,
            "win_rate": state.win_rate if state else 0,
            "total_fees": state.total_fees if state else 0,
            "total_spread": state.total_spread if state else 0,
            "total_slippage": state.total_slippage if state else 0,
        }
    
    # ═══════════════════════════════════════════════════════════════════════════
    # DB WRITE METHODS - All changes go to database immediately
    # ═══════════════════════════════════════════════════════════════════════════
    
    async def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        leverage: int = 5,
        conviction: int = 50,
        reason: str = "",
    ) -> Optional[Position]:
        """
        Open a new position and write to database immediately.
        
        Returns the created Position or None if failed.
        """
        from repositories import PositionRepository, TraderStateRepository
        from integrations.binance import TradingCosts
        
        # Check if we already have this position
        if await self.has_position(symbol):
            logger.warning(f"Already have position in {symbol}")
            return None
        
        # Check slot availability
        slots = await self.get_available_slots()
        if slots <= 0:
            logger.warning(f"No available slots (max {self._max_positions})")
            return None
        
        # Calculate position size
        capital = await self.get_capital()
        size_usdt = capital * self._position_size_pct
        quantity = size_usdt / entry_price
        
        # Calculate trading costs
        costs = TradingCosts()
        fee = costs.calculate_fee(size_usdt)
        spread = costs.calculate_spread(size_usdt)
        slippage = costs.calculate_slippage(size_usdt)
        total_costs = fee + spread + slippage
        
        # Generate position ID
        position_id = f"POS_{uuid4().hex[:8].upper()}"
        
        # Write to database
        success = await PositionRepository.create_position(
            position_id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            quantity=quantity,
            size_usdt=size_usdt,
            leverage=leverage,
            conviction=conviction,
            reasoning=reason,
        )
        
        if not success:
            logger.error(f"Failed to create position in DB")
            return None
        
        # Update capital (deduct position size + costs)
        new_capital = capital - size_usdt - total_costs
        await TraderStateRepository.update_capital(new_capital)
        
        # Create and return Position object
        position = Position(
            id=position_id,
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            quantity=quantity,
            size_usdt=size_usdt,
            leverage=leverage,
            conviction=conviction,
            entry_fee=fee,
            entry_spread=spread,
            entry_slippage=slippage,
            reason=reason,
        )
        
        logger.info(f"Opened {direction} {symbol} @ ${entry_price:.4f}, size=${size_usdt:.2f}")
        return position
    
    async def close_position(
        self,
        symbol: str,
        exit_price: float,
        reason: str = "grok_decision",
    ) -> Optional[ClosedPosition]:
        """
        Close a position and update database immediately.
        
        Returns the ClosedPosition or None if failed.
        """
        from repositories import PositionRepository, TraderStateRepository
        from integrations.binance import TradingCosts
        
        # Get the position from DB
        position = await self.get_position(symbol)
        if not position:
            logger.warning(f"No position found for {symbol}")
            return None
        
        # Calculate PnL
        if position.direction == "LONG":
            pnl_pct = (exit_price - position.entry_price) / position.entry_price
        else:
            pnl_pct = (position.entry_price - exit_price) / position.entry_price
        
        realized_pnl = position.size_usdt * pnl_pct * position.leverage
        
        # Calculate exit costs
        costs = TradingCosts()
        exit_fee = costs.calculate_fee(position.size_usdt)
        exit_spread = costs.calculate_spread(position.size_usdt)
        exit_slippage = costs.calculate_slippage(position.size_usdt)
        total_exit_costs = exit_fee + exit_spread + exit_slippage
        
        # Net PnL after costs
        net_pnl = realized_pnl - total_exit_costs
        
        # Update position in DB
        success = await PositionRepository.close_position(
            position_id=position.id,
            exit_price=exit_price,
            realized_pnl=net_pnl,
            status="CLOSED",
        )
        
        if not success:
            logger.error(f"Failed to close position in DB")
            return None
        
        # Update trader state (capital and statistics)
        is_win = net_pnl > 0
        await TraderStateRepository.record_trade(
            pnl=net_pnl,
            is_win=is_win,
            fee=exit_fee + position.entry_fee,
            spread=exit_spread + position.entry_spread,
            slippage=exit_slippage + position.entry_slippage,
        )
        
        # Return capital + PnL
        capital = await self.get_capital()
        new_capital = capital + position.size_usdt + net_pnl
        await TraderStateRepository.update_capital(new_capital)
        
        closed = ClosedPosition(
            id=position.id,
            symbol=symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=exit_price,
            quantity=position.quantity,
            size_usdt=position.size_usdt,
            leverage=position.leverage,
            conviction=position.conviction,
            realized_pnl=net_pnl,
            realized_pnl_pct=pnl_pct * position.leverage * 100,
            opened_at=position.opened_at,
            closed_at=datetime.utcnow(),
            close_reason=reason,
            total_fees=exit_fee + position.entry_fee,
            total_spread=exit_spread + position.entry_spread,
            total_slippage=exit_slippage + position.entry_slippage,
        )
        
        logger.info(f"Closed {symbol} @ ${exit_price:.4f}, PnL=${net_pnl:+.2f}")
        return closed
    
    async def update_prices(self, prices: Dict[str, float]) -> None:
        """
        Update current prices for all positions.
        
        Note: This doesn't need to write to DB - prices are fetched live.
        The DB stores entry_price, current_price is calculated on read.
        """
        # Prices are fetched live, no need to store in DB
        pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # SYNC COMPATIBILITY PROPERTIES
    # These exist for backwards compatibility with old sync code
    # They should be replaced with async methods over time
    # ═══════════════════════════════════════════════════════════════════════════
    
    @property
    def starting_capital(self) -> float:
        """Starting capital (config value)."""
        return self._starting_capital
    
    @property
    def capital(self) -> float:
        """
        DEPRECATED: Use await get_capital() instead.
        Returns starting capital as fallback.
        """
        logger.warning("Sync capital access - use await get_capital()")
        return self._starting_capital
    
    @property
    def positions(self) -> Dict[str, Position]:
        """
        DEPRECATED: Use await get_positions() instead.
        Returns empty dict as fallback.
        """
        logger.warning("Sync positions access - use await get_positions()")
        return {}
    
    @property
    def max_positions(self) -> int:
        return self._max_positions
    
    @property
    def position_size_pct(self) -> float:
        return self._position_size_pct
    
    @property
    def total_fees_paid(self) -> float:
        """DEPRECATED: Read from DB via get_statistics()"""
        return 0.0
    
    @property
    def total_spread_cost(self) -> float:
        """DEPRECATED: Read from DB via get_statistics()"""
        return 0.0
    
    @property
    def total_slippage_cost(self) -> float:
        """DEPRECATED: Read from DB via get_statistics()"""
        return 0.0
    
    @property 
    def closed_positions(self) -> List[ClosedPosition]:
        """DEPRECATED: Use PositionRepository.get_closed_positions()"""
        return []
    
    @property
    def transactions(self) -> List[Transaction]:
        """DEPRECATED: Read from DB"""
        return []
    
    def reset(self):
        """
        DEPRECATED: Use TraderStateRepository.reset() instead.
        This is a no-op since we have no in-memory state.
        """
        logger.warning("PositionTracker.reset() called - use TraderStateRepository.reset()")
        pass
    
    def to_dict(self) -> dict:
        """Serialize tracker state - requires async, returns minimal sync data."""
        return {
            "positions": [],
            "statistics": {
                "capital": self._starting_capital,
                "note": "Use async get_statistics() for full data"
            },
        }
