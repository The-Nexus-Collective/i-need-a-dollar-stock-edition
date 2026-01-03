"""
Executor - Manages positions and executes trades

Handles:
- Closing all existing positions at cycle start
- Opening new positions based on predictions
- Position sizing by conviction (weighted allocation)
- Leverage calculation (1x-10x based on conviction)
- PnL tracking
- Database persistence for positions
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from integrations.binance import BinanceClient, get_binance
from .predictor import Prediction

logger = logging.getLogger(__name__)

# Database URL for saving cycles (optional)
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Global database connection pool
_db_pool = None


async def get_db_pool():
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None and DATABASE_URL:
        try:
            import asyncpg
            _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
            logger.info("Database connection pool created")
        except Exception as e:
            logger.warning(f"Failed to create DB pool: {e}")
    return _db_pool


@dataclass
class Position:
    """An open position."""
    position_id: str
    symbol: str
    direction: str  # "LONG" or "SHORT"
    entry_price: float
    quantity: float
    size_usdt: float
    leverage: float
    conviction: int
    opened_at: datetime = field(default_factory=datetime.utcnow)
    
    # Trading costs on entry
    entry_fee: float = 0.0
    entry_spread: float = 0.0
    entry_slippage: float = 0.0
    
    # Filled when position is closed
    exit_price: Optional[float] = None
    closed_at: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    
    # Trading costs on exit
    exit_fee: float = 0.0
    exit_spread: float = 0.0
    exit_slippage: float = 0.0
    total_costs: float = 0.0
    
    @property
    def is_open(self) -> bool:
        return self.exit_price is None
    
    def to_dict(self) -> dict:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "conviction": self.conviction,
            "opened_at": self.opened_at.isoformat(),
            "entry_fee": self.entry_fee,
            "entry_spread": self.entry_spread,
            "entry_slippage": self.entry_slippage,
            "exit_price": self.exit_price,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "exit_fee": self.exit_fee,
            "exit_spread": self.exit_spread,
            "exit_slippage": self.exit_slippage,
            "total_costs": self.total_costs,
        }


@dataclass
class CycleResult:
    """Result of one trading cycle."""
    cycle_id: str
    timestamp: datetime
    closed_positions: List[Position]
    opened_positions: List[Position]
    total_pnl: float  # From closed positions
    capital_before: float
    capital_after: float
    
    def to_dict(self) -> dict:
        return {
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp.isoformat(),
            "closed_positions": [p.to_dict() for p in self.closed_positions],
            "opened_positions": [p.to_dict() for p in self.opened_positions],
            "total_pnl": self.total_pnl,
            "capital_before": self.capital_before,
            "capital_after": self.capital_after,
        }


class Executor:
    """
    Trade executor for the prediction trader.
    
    Manages capital allocation, position sizing, and trade execution.
    """
    
    DEFAULT_CAPITAL = 100_000.0  # Starting capital in USDT
    MAX_LEVERAGE = 10
    MIN_LEVERAGE = 1
    DEFAULT_MAX_POSITIONS = 50
    DEFAULT_POSITION_SIZE_PCT = 0.02  # 2% of capital
    CONVICTION_REPLACEMENT_THRESHOLD = 15  # New signal must be 15+ points higher
    
    def __init__(
        self,
        starting_capital: float = DEFAULT_CAPITAL,
        binance: Optional[BinanceClient] = None,
        max_positions: int = DEFAULT_MAX_POSITIONS,
        position_size_pct: float = DEFAULT_POSITION_SIZE_PCT,
    ):
        """
        Initialize executor.
        
        Args:
            starting_capital: Initial capital in USDT
            binance: BinanceClient instance (uses global if not provided)
            max_positions: Maximum number of open positions (default 50)
            position_size_pct: Position size as % of capital (default 0.02 = 2%)
        """
        self.capital = starting_capital
        self.starting_capital = starting_capital
        self.binance = binance or get_binance()
        self.max_positions = max_positions
        self.position_size_pct = position_size_pct
        
        # Current open positions
        self.positions: Dict[str, Position] = {}  # symbol -> Position
        
        # History
        self.closed_positions: List[Position] = []
        self.cycles: List[CycleResult] = []
        
        # Fee tracking
        self.total_fees_paid: float = 0.0
        self.total_spread_cost: float = 0.0
        self.total_slippage_cost: float = 0.0
        
        # Track if we've loaded positions from DB
        self._positions_loaded = False
        
        # Reset counter - incremented on each reset to detect stale operations
        self._reset_counter = 0
        
        # Track last predictions for smart cycle logic (coin -> (direction, conviction))
        self._last_predictions: Dict[str, tuple] = {}
        
        # Track position convictions for smart replacement
        self._position_convictions: Dict[str, int] = {}  # symbol -> conviction
    
    async def close_orphaned_positions(self):
        """
        Close any orphaned positions from database on startup.
        
        This handles the restart case: if the backend crashed or restarted,
        there may be positions marked as OPEN in the database that need to
        be closed before we start a fresh cycle.
        
        Returns the number of orphaned positions closed.
        """
        if self._positions_loaded:
            return 0
        
        self._positions_loaded = True
        
        pool = await get_db_pool()
        if not pool:
            logger.warning("No DB pool - cannot check for orphaned positions")
            return 0
        
        try:
            async with pool.acquire() as conn:
                # Find all orphaned OPEN positions
                rows = await conn.fetch("""
                    SELECT id, symbol, direction, entry_price, quantity, size_usdt,
                           leverage, conviction, entry_time
                    FROM paper_positions
                    WHERE status = 'OPEN'
                """)
                
                if not rows:
                    logger.info("No orphaned positions found")
                    return 0
                
                logger.warning(f"Found {len(rows)} orphaned positions from previous run - closing them")
                
                closed_count = 0
                for row in rows:
                    position = Position(
                        position_id=row['id'],
                        symbol=row['symbol'],
                        direction=row['direction'],
                        entry_price=float(row['entry_price']),
                        quantity=float(row['quantity']),
                        size_usdt=float(row['size_usdt']),
                        leverage=float(row['leverage']) if row['leverage'] else 1.0,
                        conviction=int(row['conviction']) if row['conviction'] else 50,
                        opened_at=row['entry_time'],
                    )
                    
                    # Close the orphaned position
                    try:
                        close_order = await self.binance.close_position(
                            symbol=position.symbol,
                            side=position.direction,
                            quantity=position.quantity,
                            size_usdt=position.size_usdt,
                        )
                        
                        current_price = close_order.filled_price
                        
                        # Calculate PnL
                        if position.direction == "LONG":
                            pnl_pct = (current_price - position.entry_price) / position.entry_price
                        else:
                            pnl_pct = (position.entry_price - current_price) / position.entry_price
                        
                        pnl_pct *= position.leverage
                        pnl = position.size_usdt * pnl_pct - close_order.fee
                        
                        # Update position and close in DB
                        position.exit_price = current_price
                        position.closed_at = datetime.utcnow()
                        position.pnl = pnl
                        position.exit_fee = close_order.fee
                        
                        await self._close_position_in_db(position)
                        self.closed_positions.append(position)
                        self.capital += pnl
                        
                        logger.info(
                            f"Closed orphaned {position.direction} {position.symbol}: "
                            f"${position.entry_price:,.2f} -> ${current_price:,.2f} "
                            f"PnL: ${pnl:+,.2f}"
                        )
                        closed_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to close orphaned position {position.symbol}: {e}")
                
                logger.info(f"Closed {closed_count}/{len(rows)} orphaned positions")
                return closed_count
                
        except Exception as e:
            logger.error(f"Failed to check for orphaned positions: {e}")
            return 0
    
    def should_close_position(self, coin: str, new_direction: str, new_conviction: int) -> tuple:
        """
        Determine if a position should be closed based on sentiment change.
        
        Returns:
            (should_close: bool, reason: str)
        """
        symbol = f"{coin}USDT"
        
        # No existing position for this coin
        if symbol not in self.positions:
            return (False, "no_position")
        
        # No previous prediction recorded
        if coin not in self._last_predictions:
            return (False, "no_previous_prediction")
        
        old_direction, old_conviction = self._last_predictions[coin]
        
        # Direction flip (LONG -> SHORT or SHORT -> LONG)
        if new_direction != old_direction:
            return (True, f"direction_flip:{old_direction}->{new_direction}")
        
        # Conviction changed by 15+ points
        conviction_change = abs(new_conviction - old_conviction)
        if conviction_change >= 15:
            return (True, f"conviction_change:{old_conviction}->{new_conviction}")
        
        return (False, "stable")
    
    async def execute_cycle_smart(self, predictions: List[Prediction]) -> CycleResult:
        """
        Execute a smart trading cycle that only closes positions when sentiment changes.
        
        Unlike execute_cycle() which closes ALL positions every cycle, this method:
        1. Keeps positions open if direction and conviction are stable
        2. Only closes positions when direction flips OR conviction changes by ±15 points
        3. Opens new positions for coins without existing positions
        4. Enforces max_positions limit by replacing low-conviction positions with high-conviction signals
        
        Args:
            predictions: List of predictions from Predictor
            
        Returns:
            CycleResult with closed and opened positions
        """
        cycle_id = f"CYCLE_{uuid4().hex[:8].upper()}"
        timestamp = datetime.utcnow()
        
        # Capture reset counter to detect if reset happens during cycle
        cycle_reset_counter = self._reset_counter
        
        # Close any orphaned positions from database (handles restart case)
        await self.close_orphaned_positions()
        
        capital_before = self.capital
        
        logger.info(f"═══════════════════════════════════════════════════════")
        logger.info(f"Starting SMART cycle {cycle_id}")
        logger.info(f"Capital: ${capital_before:,.2f}")
        logger.info(f"Open positions: {len(self.positions)}/{self.max_positions}")
        logger.info(f"═══════════════════════════════════════════════════════")
        
        closed_positions = []
        opened_positions = []
        kept_positions = []
        
        # Track which positions we're keeping
        coins_to_close = []
        coins_to_open = []
        coins_to_keep = []
        
        # Step 1: Analyze each prediction
        for pred in predictions:
            symbol = f"{pred.coin}USDT"
            should_close, reason = self.should_close_position(pred.coin, pred.direction, pred.conviction)
            
            if symbol in self.positions:
                if should_close:
                    coins_to_close.append((pred, reason))
                    logger.info(f"  {pred.coin}: CLOSE position ({reason})")
                else:
                    coins_to_keep.append(pred)
                    # Update conviction tracking for kept positions
                    self._position_convictions[symbol] = pred.conviction
                    logger.info(f"  {pred.coin}: KEEP position (direction={pred.direction}, conviction={pred.conviction}%)")
            else:
                # Only open positions for LONG/SHORT, skip NEUTRAL
                if pred.direction in ["LONG", "SHORT"]:
                    coins_to_open.append(pred)
                    logger.info(f"  {pred.coin}: OPEN new position ({pred.direction}, {pred.conviction}%)")
                else:
                    logger.info(f"  {pred.coin}: SKIP (NEUTRAL prediction, no position)")
        
        # Step 2: Close positions that need to be closed
        for pred, reason in coins_to_close:
            symbol = f"{pred.coin}USDT"
            position = self.positions.get(symbol)
            if position:
                try:
                    closed_pos = await self._close_single_position(position)
                    if closed_pos:
                        closed_positions.append(closed_pos)
                        # Remove from conviction tracking
                        self._position_convictions.pop(symbol, None)
                        # Only reopen if new prediction is LONG/SHORT, not NEUTRAL
                        if pred.direction in ["LONG", "SHORT"]:
                            coins_to_open.append(pred)
                        else:
                            logger.info(f"  {pred.coin}: Closed but not reopening (NEUTRAL)")
                except Exception as e:
                    logger.error(f"Failed to close {symbol}: {e}")
        
        # Calculate PnL from closed positions
        total_pnl = sum(p.pnl or 0 for p in closed_positions)
        
        # Only add PnL if reset didn't happen during this cycle
        if self._reset_counter == cycle_reset_counter:
            if total_pnl != 0:
                logger.info(f"Realized PnL from closed positions: ${total_pnl:+,.2f}")
            self.capital += total_pnl
        else:
            logger.warning(f"Reset detected - skipping PnL: ${total_pnl:+,.2f}")
            total_pnl = 0
        
        # Step 3: Smart position replacement - close low-conviction positions for high-conviction signals
        # Sort candidates by conviction (highest first)
        coins_to_open.sort(key=lambda p: p.conviction, reverse=True)
        
        # Calculate how many slots are available
        current_position_count = len(self.positions)
        available_slots = self.max_positions - current_position_count
        
        if len(coins_to_open) > available_slots:
            logger.info(f"  Position limit: {current_position_count}/{self.max_positions} open, {len(coins_to_open)} want to open, {available_slots} slots available")
            
            # Find positions that can be replaced (lowest conviction first)
            replaceable_positions = self._find_replaceable_positions(coins_to_open, available_slots)
            
            for old_symbol, new_pred in replaceable_positions:
                position = self.positions.get(old_symbol)
                if position:
                    old_conviction = self._position_convictions.get(old_symbol, 50)
                    logger.info(f"  REPLACING {old_symbol} (conviction={old_conviction}%) with {new_pred.coin} (conviction={new_pred.conviction}%)")
                    try:
                        closed_pos = await self._close_single_position(position)
                        if closed_pos:
                            closed_positions.append(closed_pos)
                            self._position_convictions.pop(old_symbol, None)
                            # PnL from replacement
                            if closed_pos.pnl and self._reset_counter == cycle_reset_counter:
                                self.capital += closed_pos.pnl
                                total_pnl += closed_pos.pnl
                    except Exception as e:
                        logger.error(f"Failed to close replacement position {old_symbol}: {e}")
        
        # Step 4: Calculate sizes and open positions (limited to available slots + replacements)
        final_open_count = min(len(coins_to_open), self.max_positions - len(self.positions))
        coins_to_actually_open = coins_to_open[:final_open_count]
        
        if coins_to_actually_open:
            sizes = self._calculate_sizes(coins_to_actually_open)
            
            # Open new positions
            opened_positions = await self._open_positions(coins_to_actually_open, sizes)
            
            # Track conviction for newly opened positions
            for pred in coins_to_actually_open:
                symbol = f"{pred.coin}USDT"
                if symbol in self.positions:
                    self._position_convictions[symbol] = pred.conviction
        
        # Step 5: Update last predictions for all coins
        for pred in predictions:
            self._last_predictions[pred.coin] = (pred.direction, pred.conviction)
        
        # Log summary
        logger.info(f"───────────────────────────────────────────────────────")
        logger.info(f"Cycle {cycle_id} summary:")
        logger.info(f"  Kept: {len(coins_to_keep)} positions")
        logger.info(f"  Closed: {len(closed_positions)} positions (PnL: ${total_pnl:+,.2f})")
        logger.info(f"  Opened: {len(opened_positions)} positions")
        logger.info(f"  Total open: {len(self.positions)} positions")
        logger.info(f"  Capital: ${self.capital:,.2f}")
        logger.info(f"───────────────────────────────────────────────────────")
        
        # Create result
        result = CycleResult(
            cycle_id=cycle_id,
            timestamp=timestamp,
            closed_positions=closed_positions,
            opened_positions=opened_positions,
            total_pnl=total_pnl,
            capital_before=capital_before,
            capital_after=self.capital,
        )
        
        self.cycles.append(result)
        
        # Save to database (non-blocking) - only if no reset happened
        if self._reset_counter == cycle_reset_counter:
            try:
                await self._save_cycle_to_db(result, predictions)
            except Exception as e:
                logger.warning(f"Failed to save cycle to DB: {e}")
        
        return result
    
    async def _close_single_position(self, position: Position) -> Optional[Position]:
        """Close a single position and calculate PnL."""
        try:
            close_order = await self.binance.close_position(
                symbol=position.symbol,
                side=position.direction,
                quantity=position.quantity,
                size_usdt=position.size_usdt,
            )
            
            current_price = close_order.filled_price
            
            # Calculate PnL with leverage
            if position.direction == "LONG":
                pnl_pct = (current_price - position.entry_price) / position.entry_price
            else:  # SHORT
                pnl_pct = (position.entry_price - current_price) / position.entry_price
            
            pnl_pct *= position.leverage
            
            # Calculate total costs
            position.exit_fee = close_order.fee
            position.exit_spread = close_order.spread_cost
            position.exit_slippage = close_order.slippage_cost
            position.total_costs = (
                position.entry_fee + position.exit_fee +
                position.entry_spread + position.exit_spread +
                position.entry_slippage + position.exit_slippage
            )
            
            gross_pnl = position.size_usdt * pnl_pct
            pnl = gross_pnl - position.total_costs
            
            # Update position
            position.exit_price = current_price
            position.closed_at = datetime.utcnow()
            position.pnl = pnl
            position.pnl_pct = (pnl / position.size_usdt) * 100
            
            # Remove from active positions
            if position.symbol in self.positions:
                del self.positions[position.symbol]
            
            self.closed_positions.append(position)
            
            # Track costs
            self.total_fees_paid += position.exit_fee
            self.total_spread_cost += position.exit_spread
            self.total_slippage_cost += position.exit_slippage
            
            # Update in database
            await self._close_position_in_db(position)
            
            logger.info(
                f"Closed {position.direction} {position.symbol}: "
                f"${position.entry_price:,.2f} -> ${current_price:,.2f} "
                f"PnL: ${pnl:+,.2f} ({position.pnl_pct:+.2f}%)"
            )
            
            return position
            
        except Exception as e:
            logger.error(f"Failed to close position {position.symbol}: {e}")
            return None
    
    async def execute_cycle(self, predictions: List[Prediction]) -> CycleResult:
        """
        Execute one complete trading cycle.
        
        1. Close any orphaned positions from database (handles restart)
        2. Close all current in-memory positions (realize PnL)
        3. Calculate position sizes based on conviction
        4. Open new positions
        
        Args:
            predictions: List of predictions from Predictor
            
        Returns:
            CycleResult with all details
        """
        cycle_id = f"CYCLE_{uuid4().hex[:8].upper()}"
        timestamp = datetime.utcnow()
        
        # Capture reset counter to detect if reset happens during cycle
        cycle_reset_counter = self._reset_counter
        
        # Close any orphaned positions from database (handles restart case)
        await self.close_orphaned_positions()
        
        capital_before = self.capital
        
        logger.info(f"═══════════════════════════════════════════════════════")
        logger.info(f"Starting cycle {cycle_id}")
        logger.info(f"Capital: ${capital_before:,.2f}")
        logger.info(f"Open positions: {len(self.positions)}")
        logger.info(f"═══════════════════════════════════════════════════════")
        
        # Step 1: Close all existing positions (including any loaded from DB)
        logger.info(f"Cycle {cycle_id}: Closing {len(self.positions)} positions...")
        closed_positions = await self._close_all_positions()
        
        # Calculate PnL from closed positions
        total_pnl = sum(p.pnl or 0 for p in closed_positions)
        
        # Only add PnL if reset didn't happen during this cycle
        if self._reset_counter == cycle_reset_counter:
            if total_pnl != 0:
                logger.warning(f"Cycle {cycle_id}: Adding PnL ${total_pnl:+,.2f} to capital ${self.capital:,.2f}")
            self.capital += total_pnl
        else:
            logger.warning(f"Cycle {cycle_id}: Reset detected (counter {cycle_reset_counter} -> {self._reset_counter}) - skipping PnL: ${total_pnl:+,.2f}")
            total_pnl = 0  # Reset total for result
        
        if closed_positions:
            logger.info(f"Closed {len(closed_positions)} positions, PnL: ${total_pnl:+,.2f}")
        
        # Step 2: Calculate position sizes
        sizes = self._calculate_sizes(predictions)
        
        # Step 3: Open new positions
        opened_positions = await self._open_positions(predictions, sizes)
        
        logger.info(f"Opened {len(opened_positions)} new positions")
        
        # Create result
        result = CycleResult(
            cycle_id=cycle_id,
            timestamp=timestamp,
            closed_positions=closed_positions,
            opened_positions=opened_positions,
            total_pnl=total_pnl,
            capital_before=capital_before,
            capital_after=self.capital,
        )
        
        self.cycles.append(result)
        
        # Log summary
        self._log_cycle_summary(result, predictions)
        
        # Save to database (non-blocking) - only if no reset happened
        if self._reset_counter == cycle_reset_counter:
            try:
                await self._save_cycle_to_db(result, predictions)
            except Exception as e:
                logger.warning(f"Failed to save cycle to DB: {e}")
        else:
            logger.warning(f"Cycle {cycle_id}: Skipping DB save - reset detected during cycle")
        
        return result
    
    async def _close_all_positions(self) -> List[Position]:
        """Close all open positions and calculate PnL."""
        closed = []
        
        if self.positions:
            logger.info(f"_close_all_positions: Found {len(self.positions)} positions to close")
        
        for symbol, position in list(self.positions.items()):
            try:
                # Close on Binance with realistic costs
                close_order = await self.binance.close_position(
                    symbol=symbol,
                    side=position.direction,
                    quantity=position.quantity,
                    size_usdt=position.size_usdt,
                )
                
                # Use fill price from order (includes spread/slippage)
                current_price = close_order.filled_price
                
                # Track exit costs
                position.exit_fee = close_order.fee
                position.exit_spread = close_order.spread_cost
                position.exit_slippage = close_order.slippage_cost
                position.total_costs = (
                    position.entry_fee + position.entry_spread + position.entry_slippage +
                    position.exit_fee + position.exit_spread + position.exit_slippage
                )
                
                # Track total costs
                self.total_fees_paid += close_order.fee
                self.total_spread_cost += close_order.spread_cost
                self.total_slippage_cost += close_order.slippage_cost
                
                # Calculate PnL (note: exit price already includes slippage)
                if position.direction == "LONG":
                    pnl_pct = (current_price - position.entry_price) / position.entry_price
                else:  # SHORT
                    pnl_pct = (position.entry_price - current_price) / position.entry_price
                
                # Leverage amplifies PnL
                pnl_pct *= position.leverage
                
                # Subtract total costs from PnL
                gross_pnl = position.size_usdt * pnl_pct
                pnl = gross_pnl - position.total_costs
                
                # Update position
                position.exit_price = current_price
                position.closed_at = datetime.utcnow()
                position.pnl = pnl
                position.pnl_pct = (pnl / position.size_usdt) * 100
                
                closed.append(position)
                self.closed_positions.append(position)
                
                # Update position in database
                await self._close_position_in_db(position)
                
                logger.info(
                    f"Closed {position.direction} {symbol}: "
                    f"${position.entry_price:,.2f} -> ${current_price:,.2f} "
                    f"PnL: ${pnl:+,.2f} ({pnl_pct*100:+.2f}%)"
                )
                
            except Exception as e:
                logger.error(f"Failed to close position {symbol}: {e}")
        
        # Clear positions dict
        self.positions.clear()
        
        return closed
    
    def _find_replaceable_positions(
        self,
        candidates_to_open: List[Prediction],
        available_slots: int,
    ) -> List[tuple]:
        """
        Find positions that should be closed to make room for high-conviction signals.
        
        Args:
            candidates_to_open: Predictions wanting to open (sorted by conviction, highest first)
            available_slots: Current number of available position slots
            
        Returns:
            List of tuples (old_symbol, new_prediction) for positions to replace
        """
        replacements = []
        
        # How many more positions do we need?
        needed_slots = len(candidates_to_open) - available_slots
        if needed_slots <= 0:
            return []
        
        # Get all open positions sorted by conviction (lowest first)
        positions_by_conviction = sorted(
            [(sym, self._position_convictions.get(sym, 50)) for sym in self.positions.keys()],
            key=lambda x: x[1]
        )
        
        # Check each candidate that can't fit
        candidates_needing_slot = candidates_to_open[available_slots:]
        
        for new_pred in candidates_needing_slot:
            if not positions_by_conviction:
                break  # No more positions to replace
            
            # Get lowest conviction position
            old_symbol, old_conviction = positions_by_conviction[0]
            
            # Only replace if new conviction is significantly higher (threshold: 15 points)
            if new_pred.conviction >= old_conviction + self.CONVICTION_REPLACEMENT_THRESHOLD:
                replacements.append((old_symbol, new_pred))
                positions_by_conviction.pop(0)  # Remove from consideration
                logger.debug(f"Will replace {old_symbol} (conv={old_conviction}) with {new_pred.coin} (conv={new_pred.conviction})")
            else:
                # New prediction isn't strong enough to replace anything
                logger.debug(f"Cannot replace any position for {new_pred.coin} (conv={new_pred.conviction}) - lowest existing is {old_conviction}")
        
        return replacements
    
    def _calculate_sizes(self, predictions: List[Prediction]) -> List[float]:
        """
        Calculate position sizes using fixed percentage of capital.
        
        Each position uses self.position_size_pct (default 2%) of capital.
        NEUTRAL predictions get 0 allocation.
        
        Args:
            predictions: List of predictions
            
        Returns:
            List of sizes in USDT (same order as predictions)
        """
        if not predictions:
            return []
        
        # Fixed size per position (2% of capital by default)
        size_per_position = self.capital * self.position_size_pct
        
        # Assign fixed size for tradeable predictions, 0 for NEUTRAL
        sizes = []
        tradeable_count = 0
        for pred in predictions:
            if pred.direction == "NEUTRAL":
                sizes.append(0.0)
            else:
                sizes.append(size_per_position)
                tradeable_count += 1
        
        logger.debug(f"Position size: ${size_per_position:,.0f} ({self.position_size_pct*100:.0f}% of ${self.capital:,.0f}) × {tradeable_count} tradeable predictions")
        
        return sizes
    
    async def _open_positions(
        self,
        predictions: List[Prediction],
        sizes: List[float],
    ) -> List[Position]:
        """Open new positions based on predictions. NEUTRAL predictions are skipped."""
        opened = []
        skipped_neutral = 0
        
        for pred, size in zip(predictions, sizes):
            try:
                # Skip NEUTRAL predictions - no position opened
                if pred.direction == "NEUTRAL" or size <= 0:
                    skipped_neutral += 1
                    logger.debug(f"Skipping {pred.coin}: direction={pred.direction}, size=${size:.0f}")
                    continue
                
                symbol = f"{pred.coin}USDT"
                
                # Calculate leverage (1x to 10x)
                leverage = self.MIN_LEVERAGE + (pred.conviction / 100) * (self.MAX_LEVERAGE - self.MIN_LEVERAGE)
                leverage = min(self.MAX_LEVERAGE, max(self.MIN_LEVERAGE, leverage))
                
                # Open on Binance
                order = await self.binance.open_position(
                    symbol=symbol,
                    side=pred.direction,
                    size_usdt=size,
                    leverage=int(leverage),
                )
                
                # Create position record with entry costs
                position = Position(
                    position_id=f"POS_{uuid4().hex[:8].upper()}",
                    symbol=symbol,
                    direction=pred.direction,
                    entry_price=order.filled_price,
                    quantity=order.filled_quantity,
                    size_usdt=size,
                    leverage=leverage,
                    conviction=pred.conviction,
                    entry_fee=order.fee,
                    entry_spread=order.spread_cost,
                    entry_slippage=order.slippage_cost,
                )
                
                # Track total costs
                self.total_fees_paid += order.fee
                self.total_spread_cost += order.spread_cost
                self.total_slippage_cost += order.slippage_cost
                
                self.positions[symbol] = position
                opened.append(position)
                
                # Save position to database
                await self._save_position_to_db(position, pred.reason)
                
                logger.info(
                    f"Opened {pred.direction} {pred.coin}: "
                    f"${size:,.0f} @ ${order.filled_price:,.2f} "
                    f"({leverage:.1f}x leverage, {pred.conviction}% conviction)"
                )
                
            except Exception as e:
                logger.error(f"Failed to open position for {pred.coin}: {e}")
        
        return opened
    
    async def _save_position_to_db(self, position: Position, reasoning: str = None):
        """Save a newly opened position to paper_positions table."""
        pool = await get_db_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO paper_positions 
                        (id, symbol, direction, entry_price, quantity, size_usdt,
                         leverage, conviction, reasoning, status, entry_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'OPEN', $10)
                    ON CONFLICT (id) DO NOTHING
                """,
                    position.position_id,
                    position.symbol,
                    position.direction,
                    position.entry_price,
                    position.quantity,
                    position.size_usdt,
                    int(position.leverage),
                    position.conviction,
                    reasoning,
                    position.opened_at,
                )
                logger.debug(f"Saved position {position.position_id} to database")
        except Exception as e:
            logger.warning(f"Failed to save position to DB: {e}")
    
    async def _close_position_in_db(self, position: Position):
        """Update a closed position in paper_positions table."""
        pool = await get_db_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                # Update position with exit info
                await conn.execute("""
                    UPDATE paper_positions SET
                        status = 'CLOSED',
                        exit_price = $2,
                        exit_time = $3,
                        realized_pnl = $4
                    WHERE id = $1
                """,
                    position.position_id,
                    position.exit_price,
                    position.closed_at,
                    position.pnl,
                )
                
                # Calculate total costs for this trade
                total_fee = getattr(position, 'entry_fee', 0) + getattr(position, 'exit_fee', 0)
                total_spread = getattr(position, 'entry_spread', 0) + getattr(position, 'exit_spread', 0)
                total_slippage = getattr(position, 'entry_slippage', 0) + getattr(position, 'exit_slippage', 0)
                
                # Also save to paper_trades for history
                await conn.execute("""
                    INSERT INTO paper_trades
                        (id, position_id, symbol, direction, entry_price, exit_price,
                         quantity, size_usdt, leverage, pnl_usdt, pnl_percent,
                         entry_time, exit_time, duration_seconds, exit_reason,
                         conviction, reasoning, fee_usdt, spread_cost_usdt, slippage_cost_usdt)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                    ON CONFLICT (id) DO NOTHING
                """,
                    f"TRADE_{uuid4().hex[:8].upper()}",
                    position.position_id,
                    position.symbol,
                    position.direction,
                    position.entry_price,
                    position.exit_price,
                    position.quantity,
                    position.size_usdt,
                    int(position.leverage),
                    position.pnl,
                    position.pnl_pct,
                    position.opened_at,
                    position.closed_at,
                    int((position.closed_at - position.opened_at).total_seconds()) if position.closed_at else 0,
                    "cycle_close",
                    position.conviction,
                    None,
                    total_fee,
                    total_spread,
                    total_slippage,
                )
                
                logger.debug(f"Closed position {position.position_id} in database")
        except Exception as e:
            logger.warning(f"Failed to close position in DB: {e}")
    
    def _log_cycle_summary(self, result: CycleResult, predictions: List[Prediction]):
        """Log a nice summary of the cycle."""
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════╗")
        logger.info("║              CYCLE SUMMARY                          ║")
        logger.info("╠══════════════════════════════════════════════════════╣")
        
        # Capital
        capital_change = result.capital_after - result.capital_before
        logger.info(f"║ Capital: ${result.capital_after:,.2f} ({capital_change:+,.2f})")
        
        # Positions opened
        logger.info("║ New Positions:")
        for pred in predictions:
            arrow = "🟢 LONG " if pred.direction == "LONG" else "🔴 SHORT"
            logger.info(f"║   {arrow} {pred.coin}: {pred.conviction}% conviction → {pred.leverage:.1f}x")
        
        logger.info("╚══════════════════════════════════════════════════════╝")
        logger.info("")
    
    def get_status(self) -> dict:
        """Get current executor status."""
        total_pnl = sum(p.pnl or 0 for p in self.closed_positions)
        total_pnl_pct = (self.capital / self.starting_capital - 1) * 100
        total_costs = self.total_fees_paid + self.total_spread_cost + self.total_slippage_cost
        
        return {
            "capital": self.capital,
            "starting_capital": self.starting_capital,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "open_positions": len(self.positions),
            "total_cycles": len(self.cycles),
            "total_trades": len(self.closed_positions),
            "positions": [p.to_dict() for p in self.positions.values()],
            "total_fees_paid": self.total_fees_paid,
            "total_spread_cost": self.total_spread_cost,
            "total_slippage_cost": self.total_slippage_cost,
            "total_trading_costs": total_costs,
        }
    
    def reset_state(self):
        """
        Reset all in-memory state. Called when paper trades are reset.
        
        Resets capital to starting amount and clears all tracked positions,
        history, and fee totals.
        """
        # Increment reset counter - any running cycles will detect this and skip PnL
        self._reset_counter += 1
        
        old_capital = self.capital
        old_positions = len(self.positions)
        old_closed = len(self.closed_positions)
        
        self.capital = self.starting_capital
        self.positions.clear()
        self.closed_positions.clear()
        self.cycles.clear()
        self.total_fees_paid = 0.0
        self.total_spread_cost = 0.0
        self.total_slippage_cost = 0.0
        self._positions_loaded = True  # Prevent loading orphaned positions again
        self._last_predictions.clear()  # Clear sentiment history for smart cycles
        self._position_convictions.clear()  # Clear conviction tracking
        
        logger.warning(
            f"EXECUTOR RESET #{self._reset_counter}: ${old_capital:,.2f} -> ${self.capital:,.2f} "
            f"(cleared {old_positions} open, {old_closed} closed positions)"
        )
    
    async def _save_cycle_to_db(
        self,
        result: CycleResult,
        predictions: List[Prediction],
    ):
        """Save cycle and predictions to database (if DATABASE_URL is set)."""
        if not DATABASE_URL:
            logger.debug("No DATABASE_URL set - skipping database save")
            return
        
        try:
            import asyncpg
            
            conn = await asyncpg.connect(DATABASE_URL)
            
            try:
                # Save the cycle - let DB auto-generate cycle_number from sequence
                row = await conn.fetchrow("""
                    INSERT INTO prediction_cycles 
                        (started_at, completed_at, capital_before, 
                         capital_after, total_pnl, coins_traded, status)
                    VALUES ($1, $2, $3, $4, $5, $6, 'completed')
                    RETURNING id, cycle_number
                """,
                    result.timestamp,
                    datetime.utcnow(),
                    result.capital_before,
                    result.capital_after,
                    result.total_pnl,
                    [p.coin for p in predictions],
                )
                cycle_id = row['id']
                cycle_number = row['cycle_number']
                
                # Save each prediction
                for pred in predictions:
                    pos = next((p for p in result.opened_positions if p.symbol == f"{pred.coin}USDT"), None)
                    await conn.execute("""
                        INSERT INTO predictions
                            (cycle_id, coin, direction, conviction, leverage, reason,
                             position_id, entry_price, quantity, size_usdt)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    """,
                        cycle_id,
                        pred.coin,
                        pred.direction,
                        pred.conviction,
                        pred.leverage,
                        pred.reason,
                        pos.position_id if pos else None,
                        pos.entry_price if pos else None,
                        pos.quantity if pos else None,
                        pos.size_usdt if pos else None,
                    )
                
                # Update trader state
                winning = sum(1 for p in self.closed_positions if (p.pnl or 0) > 0)
                losing = sum(1 for p in self.closed_positions if (p.pnl or 0) < 0)
                
                await conn.execute("""
                    UPDATE trader_state SET
                        current_capital = $1,
                        total_cycles = $2,
                        total_trades = $3,
                        winning_trades = $4,
                        losing_trades = $5,
                        total_pnl = $6,
                        peak_capital = GREATEST(peak_capital, $1),
                        last_cycle_at = NOW(),
                        updated_at = NOW()
                    WHERE id = 'main'
                """,
                    self.capital,
                    len(self.cycles),
                    len(self.closed_positions),
                    winning,
                    losing,
                    sum(p.pnl or 0 for p in self.closed_positions),
                )
                
                logger.info(f"Saved cycle #{cycle_number} to database: {cycle_id}")
                
            finally:
                await conn.close()
                
        except ImportError:
            logger.warning("asyncpg not installed - skipping database save")
        except Exception as e:
            logger.error(f"Failed to save cycle to database: {e}")

