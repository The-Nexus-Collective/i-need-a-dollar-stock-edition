"""
Portfolio Manager - Main orchestrator

Runs the 10-minute trading cycle:
1. Get current positions with live prices
2. Call Grok for analysis
3. Execute trades based on Grok's recommendations
4. Log to logbook

Now with DB-first architecture:
- Restores capital and positions from database on startup
- Saves portfolio snapshots every minute
- Tracks position PnL history for trend analysis
"""

import asyncio
import logging
import os
import signal
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set

from integrations.binance import BinanceClient, get_binance
from integrations.binance_ws import get_binance_ws, start_price_streaming

from .analyst import GrokAnalyst, AnalysisResult
from .positions import PositionTracker, Position
from .logbook import TradingLogbook, get_logbook
from .snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

# Database URL for state persistence
DATABASE_URL = os.getenv("DATABASE_URL", "")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CYCLE_INTERVAL_SECONDS = int(os.getenv("CYCLE_INTERVAL", "600"))  # 10 minutes
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "50"))
POSITION_SIZE_PCT = float(os.getenv("POSITION_SIZE_PCT", "0.02"))  # 2%
STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
MIN_DEPLOYMENT_RATIO = float(os.getenv("MIN_DEPLOYMENT_RATIO", "0.75"))  # 75% minimum
MAX_DEPLOYMENT_RATIO = float(os.getenv("MAX_DEPLOYMENT_RATIO", "0.90"))  # 90% maximum (capital exhausted)
CONVICTION_REPLACEMENT_THRESHOLD = int(os.getenv("CONVICTION_REPLACEMENT_THRESHOLD", "25"))  # +25 for replacement


class PortfolioManager:
    """
    Main trading loop orchestrator.
    
    Every 10 minutes:
    1. Get live prices for open positions
    2. Ask Grok to analyze market and make decisions
    3. Validate Grok's recommendations against Binance symbols
    4. Execute trades (close/open)
    5. Log to logbook
    """
    
    def __init__(
        self,
        starting_capital: float = STARTING_CAPITAL,
        max_positions: int = MAX_POSITIONS,
        position_size_pct: float = POSITION_SIZE_PCT,
    ):
        # Store config for potential restore
        self._starting_capital = starting_capital
        self._max_positions = max_positions
        self._position_size_pct = position_size_pct
        
        # Core components
        self.binance = get_binance()
        self.analyst = GrokAnalyst()
        self.positions = PositionTracker(
            starting_capital=starting_capital,
            max_positions=max_positions,
            position_size_pct=position_size_pct,
        )
        self.logbook = get_logbook()
        
        # Snapshot service for minute-by-minute DB persistence
        self.snapshot_service = SnapshotService(self.positions)
        
        # Valid Binance Futures symbols (cached)
        self._valid_symbols: Set[str] = set()
        self._symbols_last_fetched: Optional[datetime] = None
        
        # State
        self._running = False
        self._cycle_count = 0
        self._current_phase = "idle"
        self._db_restored = False  # Track if we've restored from DB
        
        # Broadcast callback for WebSocket updates
        self._broadcast_callback = None
    
    def set_broadcast_callback(self, callback):
        """Set callback for real-time updates."""
        self._broadcast_callback = callback
        self.logbook.set_broadcast_callback(callback)
    
    async def _broadcast_phase(self, phase: str, next_cycle_at: float = None):
        """Broadcast current phase to connected clients."""
        self._current_phase = phase
        logger.info(f"📡 Phase: {phase}")
        
        if self._broadcast_callback:
            try:
                await self._broadcast_callback({
                    "type": "phase",
                    "data": {
                        "phase": phase,
                        "cycle": self._cycle_count,
                        "next_cycle_at": next_cycle_at,
                    }
                })
            except Exception as e:
                logger.debug(f"Broadcast failed: {e}")
    
    async def _fetch_valid_symbols(self):
        """Fetch and cache valid Binance Futures symbols."""
        # Refresh every hour
        if (
            self._symbols_last_fetched and
            (datetime.utcnow() - self._symbols_last_fetched).seconds < 3600
        ):
            return
        
        try:
            # Get exchange info from Binance
            client = await self.binance._get_client()
            response = await client.get(
                f"{self.binance.FUTURES_BASE_URL}/fapi/v1/exchangeInfo"
            )
            
            if response.status_code == 200:
                data = response.json()
                self._valid_symbols = {
                    s["symbol"]
                    for s in data.get("symbols", [])
                    if s["symbol"].endswith("USDT") and s.get("status") == "TRADING"
                }
                self._symbols_last_fetched = datetime.utcnow()
                logger.info(f"Cached {len(self._valid_symbols)} valid Binance Futures symbols")
            
        except Exception as e:
            logger.warning(f"Failed to fetch valid symbols: {e}")
    
    async def _restore_from_db(self):
        """
        DB-FIRST: Log current state from database on startup.
        
        No "restore" needed - database IS the source of truth.
        All reads come directly from DB via repositories.
        """
        if self._db_restored:
            return
        
        self._db_restored = True
        
        try:
            from repositories import TraderStateRepository, PositionRepository
            
            # Log current state from DB
            state = await TraderStateRepository.get_state()
            positions = await PositionRepository.get_open_positions()
            
            if state:
                self._cycle_count = state.total_cycles
                logger.info(f"DB State: Capital ${state.current_capital:,.2f}, Cycles: {state.total_cycles}, Trades: {state.total_trades}")
            else:
                logger.info("No trader_state in DB - will use defaults")
            
            if positions:
                logger.info(f"DB has {len(positions)} open positions:")
                for pos in positions:
                    logger.info(f"  {pos.direction} {pos.symbol}: ${pos.size_usdt:.0f} @ ${pos.entry_price:.4f}")
            else:
                logger.info("No open positions in DB")
                
        except Exception as e:
            logger.warning(f"Could not read DB state: {e}")
    
    def _is_valid_symbol(self, symbol: str) -> bool:
        """Check if symbol is tradable on Binance Futures."""
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        return symbol in self._valid_symbols
    
    async def _get_positions_for_grok(self, positions: Dict[str, Position]) -> str:
        """Build positions context string for Grok analysis."""
        if not positions:
            return "No open positions."
        
        lines = []
        for symbol, pos in positions.items():
            lines.append(
                f"- {symbol}: {pos.direction} {pos.leverage}x @ ${pos.entry_price:.4f}, "
                f"PnL: ${pos.unrealized_pnl:+,.2f} ({pos.unrealized_pnl_pct:+.1f}%), "
                f"Conv: {pos.conviction}%"
            )
        return "\n".join(lines)
    
    async def _can_open_new_position(
        self, 
        positions: Dict[str, Position],
        capital: float,
        total_equity: float,
        max_deployment: float
    ) -> bool:
        """Check if we can open a new position (slots and capital)."""
        # Check slots
        if len(positions) >= self._max_positions:
            return False
        
        # Check capital deployment
        total_deployed = sum(p.size_usdt for p in positions.values())
        deployment_pct = total_deployed / total_equity if total_equity > 0 else 0
        
        if deployment_pct >= max_deployment:
            return False
        
        # Check if we have enough capital for 2% position
        position_size = capital * self._position_size_pct
        if capital < position_size:
            return False
        
        return True
    
    def _get_lowest_conviction_position(self, positions: Dict[str, Position]) -> Optional[Position]:
        """Get position with lowest conviction."""
        if not positions:
            return None
        return min(positions.values(), key=lambda p: p.conviction)
    
    async def _update_position_prices(self):
        """Update current prices for all open positions from DB."""
        positions = await self.positions.get_positions()
        if not positions:
            return
        
        symbols = list(positions.keys())
        prices = await self.binance.get_prices(symbols)
        # Prices are stored in live WebSocket, no need to write to DB
    
    async def run_cycle(self):
        """Run a single trading cycle."""
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info(f"║  CYCLE #{self._cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info("╚══════════════════════════════════════════════════════════════════╝")
        
        try:
            # Step 1: Update valid symbols cache
            await self._broadcast_phase("validating")
            await self._fetch_valid_symbols()
            
            # Step 2: Update position prices
            await self._broadcast_phase("updating_prices")
            await self._update_position_prices()
            
            # Step 3: Call Grok for analysis
            await self._broadcast_phase("analyzing")
            
            # Get data from DB
            positions = await self.positions.get_positions()
            available_slots = await self.positions.get_available_slots()
            capital = await self.positions.get_capital()
            stats = await self.positions.get_statistics()
            
            # Build positions context for Grok
            positions_context = await self._get_positions_for_grok(positions)
            
            # Calculate deployment
            total_deployed = sum(p.size_usdt for p in positions.values())
            total_equity = capital + sum(p.unrealized_pnl for p in positions.values())
            deployment_pct = (total_deployed / total_equity * 100) if total_equity > 0 else 0
            
            # Build deployment info for Grok
            deployment_info = ""
            if deployment_pct < MIN_DEPLOYMENT_RATIO * 100:
                gap = total_equity * MIN_DEPLOYMENT_RATIO - total_deployed
                deployment_info = f"""
⚠️ CRITICAL: CAPITAL DEPLOYMENT BELOW MINIMUM!
- Current deployment: {deployment_pct:.1f}%
- Minimum required: {MIN_DEPLOYMENT_RATIO * 100:.0f}%
- Additional to deploy: ${gap:,.2f}

PRIORITY: Open new positions or extend existing ones (EXTEND) to reach the minimum!
"""
            
            logger.info(f"Calling Grok with {len(positions)} positions, {available_slots} slots available...")
            logger.info(f"Deployment: {deployment_pct:.1f}% (min: {MIN_DEPLOYMENT_RATIO * 100:.0f}%)")
            
            analysis = await self.analyst.analyze(positions_context, available_slots, deployment_info)
            
            logger.info(f"Grok analyzed {analysis.coins_analyzed} coins, skipped {analysis.coins_skipped}")
            logger.info(f"Decisions: {len(analysis.position_decisions)} position reviews, {len(analysis.new_opportunities)} opportunities")
            
            # Step 4: Execute trades
            await self._broadcast_phase("trading")
            
            closed_positions = []
            opened_positions = []
            kept_positions = []
            extended_positions = []
            reduced_positions = []
            
            # Process position decisions
            for decision in analysis.position_decisions:
                if decision.action == "CLOSE":
                    closed = await self._close_position(decision.symbol)
                    if closed:
                        closed_positions.append({
                            "symbol": decision.symbol,
                            "reason": decision.reason,
                            "pnl": closed.realized_pnl,
                            "transaction_type": "CLOSE",
                        })
                elif decision.action == "EXTEND":
                    extended = await self._extend_position(decision)
                    if extended:
                        extended_positions.append({
                            "symbol": decision.symbol,
                            "reason": decision.reason,
                            "scale_percent": decision.scale_percent,
                            "new_size": extended.position_size_after,
                            "transaction_type": "EXTEND",
                        })
                elif decision.action == "REDUCE":
                    reduced = await self._reduce_position(decision)
                    if reduced:
                        reduced_positions.append({
                            "symbol": decision.symbol,
                            "reason": decision.reason,
                            "scale_percent": decision.scale_percent,
                            "pnl": reduced.realized_pnl,
                            "remaining_size": reduced.position_size_after,
                            "transaction_type": "REDUCE",
                        })
                else:
                    kept_positions.append(decision.symbol)
            
            # Open new positions
            for opportunity in analysis.new_opportunities:
                # Validate symbol
                if not self._is_valid_symbol(opportunity.symbol):
                    logger.warning(f"Skipping {opportunity.symbol} - not valid on Binance Futures")
                    continue
                
                # Check if we have room (both slots AND capital)
                can_open = await self._can_open_new_position(positions, capital, total_equity, MAX_DEPLOYMENT_RATIO)
                if not can_open:
                    # Need to close lowest conviction position - but only if new conviction is SIGNIFICANTLY higher
                    lowest = self._get_lowest_conviction_position(positions)
                    required_conviction = lowest.conviction + CONVICTION_REPLACEMENT_THRESHOLD if lowest else 100
                    
                    if lowest and opportunity.conviction >= required_conviction:
                        # Determine which limit was hit
                        if available_slots <= 0:
                            limit_reason = "max positions reached (50)"
                        else:
                            limit_reason = f"capital exhausted ({deployment_pct:.1f}% deployed)"
                        
                        logger.info(
                            f"Replacement triggered ({limit_reason}): "
                            f"Closing {lowest.symbol} (conv={lowest.conviction}) for {opportunity.symbol} (conv={opportunity.conviction})"
                        )
                        closed = await self._close_position(lowest.symbol)
                        if closed:
                            closed_positions.append({
                                "symbol": lowest.symbol,
                                "reason": f"Replaced by significantly higher conviction {opportunity.symbol} (conv={opportunity.conviction} vs {lowest.conviction}, +{CONVICTION_REPLACEMENT_THRESHOLD} required)",
                                "pnl": closed.realized_pnl,
                                "transaction_type": "CLOSE",
                            })
                            # Refresh positions after close
                            positions = await self.positions.get_positions()
                            available_slots = await self.positions.get_available_slots()
                    else:
                        if lowest:
                            logger.info(
                                f"Skipping {opportunity.symbol} (conv={opportunity.conviction}) - "
                                f"conviction not significantly higher than lowest position {lowest.symbol} (conv={lowest.conviction}, need +{CONVICTION_REPLACEMENT_THRESHOLD})"
                            )
                        else:
                            logger.info(f"Skipping {opportunity.symbol} - no positions to replace")
                        continue
                
                # Open the position
                opened = await self._open_position(opportunity)
                if opened:
                    opened_positions.append({
                        "symbol": opportunity.symbol,
                        "direction": opportunity.direction,
                        "conviction": opportunity.conviction,
                        "leverage": opportunity.leverage,
                        "reason": opportunity.reason,
                        "transaction_type": "OPEN",
                    })
            
            # Refresh state from DB after trades
            positions = await self.positions.get_positions()
            capital = await self.positions.get_capital()
            total_unrealized = sum(p.unrealized_pnl for p in positions.values())
            total_equity = capital + total_unrealized
            total_deployed = sum(p.size_usdt for p in positions.values())
            deployment_pct = (total_deployed / total_equity * 100) if total_equity > 0 else 0
            
            # If still below minimum deployment, try to extend high-conviction positions
            if deployment_pct < MIN_DEPLOYMENT_RATIO * 100:
                await self._enforce_minimum_deployment(extended_positions, positions)
            
            # Increment cycle in DB
            from repositories import TraderStateRepository
            await TraderStateRepository.increment_cycle()
            
            # Step 5: Log to logbook
            await self._broadcast_phase("logging")
            
            await self.logbook.log(
                analysis_text=analysis.analysis_text,
                market_summary=analysis.market_summary,
                positions_closed=closed_positions,
                positions_opened=opened_positions,
                positions_kept=kept_positions,
                positions_extended=extended_positions,
                positions_reduced=reduced_positions,
                coins_analyzed=analysis.coins_analyzed,
                coins_skipped=analysis.coins_skipped,
                tokens_used=analysis.tokens_used,
                total_equity=total_equity,
                unrealized_pnl=total_unrealized,
                open_positions=len(positions),
                deployment_percent=deployment_pct,
                raw_prompt=analysis.raw_prompt,
                raw_response=analysis.raw_response,
            )
            
            # Log summary
            cycle_time = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(f"")
            logger.info(f"Cycle #{self._cycle_count} completed in {cycle_time:.1f}s")
            logger.info(f"  Closed: {len(closed_positions)} | Opened: {len(opened_positions)} | Extended: {len(extended_positions)} | Reduced: {len(reduced_positions)}")
            logger.info(f"  Equity: ${total_equity:,.2f} | Deployed: {deployment_pct:.1f}% | Open: {len(positions)}/{self._max_positions}")
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
            await self._broadcast_phase("error")
    
    async def _close_position(self, symbol: str):
        """Close a position - DB-FIRST: reads from DB, writes to DB."""
        position = await self.positions.get_position(symbol)
        if not position:
            return None
        
        try:
            # Get exit price from Binance (paper mode simulates)
            close_order = await self.binance.close_position(
                symbol=symbol,
                side=position.direction,
                quantity=position.quantity,
                size_usdt=position.size_usdt,
            )
            
            # Close in DB - this is the source of truth
            closed = await self.positions.close_position(
                symbol=symbol,
                exit_price=close_order.filled_price,
                reason="grok_decision",
            )
            
            # Remove symbol from WebSocket (no longer need live prices)
            ws = get_binance_ws()
            ws.remove_symbol(symbol)
            
            return closed
            
        except Exception as e:
            logger.error(f"Failed to close {symbol}: {e}")
            return None
    
    async def _open_position(self, opportunity):
        """Open a new position - DB-FIRST: writes directly to DB."""
        symbol = opportunity.symbol
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        # Already have this position? Check DB
        if await self.positions.has_position(symbol):
            logger.warning(f"Already have position in {symbol}")
            return None
        
        try:
            # Get position size from DB
            position_size = await self.positions.get_position_size_usdt()
            
            # Get entry price from Binance (paper mode simulates)
            open_order = await self.binance.open_position(
                symbol=symbol,
                side=opportunity.direction,
                size_usdt=position_size,
                leverage=opportunity.leverage,
            )
            
            # Open in DB - this is the source of truth
            position = await self.positions.open_position(
                symbol=symbol,
                direction=opportunity.direction,
                entry_price=open_order.filled_price,
                leverage=opportunity.leverage,
                conviction=opportunity.conviction,
                reason=opportunity.reason,
            )
            
            # Add symbol to WebSocket for live price updates
            ws = get_binance_ws()
            ws.add_symbol(symbol)
            if not ws._running:
                await ws.start()
            
            return position
            
        except Exception as e:
            logger.error(f"Failed to open {symbol}: {e}")
            return None
    
    async def _extend_position(self, decision):
        """
        Extend an existing position by adding more size.
        
        NOTE: DB-First - extend/reduce not yet implemented in repositories.
        For now, log and skip.
        """
        symbol = decision.symbol
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        position = await self.positions.get_position(symbol)
        if not position:
            logger.warning(f"No position to extend for {symbol}")
            return None
        
        # TODO: Implement extend in PositionRepository
        logger.info(f"EXTEND {symbol} by {decision.scale_percent}% - not yet implemented in DB-First")
        return None
    
    async def _reduce_position(self, decision):
        """
        Reduce an existing position by selling a percentage.
        
        NOTE: DB-First - extend/reduce not yet implemented in repositories.
        For now, log and skip.
        """
        symbol = decision.symbol
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"
        
        position = await self.positions.get_position(symbol)
        if not position:
            logger.warning(f"No position to reduce for {symbol}")
            return None
        
        # TODO: Implement reduce in PositionRepository
        logger.info(f"REDUCE {symbol} by {decision.scale_percent}% - not yet implemented in DB-First")
        return None
    
    async def _enforce_minimum_deployment(self, extended_positions: list, positions: Dict[str, Position] = None):
        """
        Enforce minimum capital deployment by extending high-conviction positions.
        
        Called when Grok's recommendations didn't reach 75% deployment.
        DB-FIRST: All state comes from database.
        """
        # Get state from DB
        if positions is None:
            positions = await self.positions.get_positions()
        capital = await self.positions.get_capital()
        total_equity = capital + sum(p.unrealized_pnl for p in positions.values())
        total_deployed = sum(p.size_usdt for p in positions.values())
        
        target_deployed = total_equity * MIN_DEPLOYMENT_RATIO
        gap = target_deployed - total_deployed
        
        if gap <= 0:
            return
        
        logger.info(f"Enforcing minimum deployment: need to deploy ${gap:,.2f} more")
        
        # Sort positions by conviction (highest first)
        sorted_positions = sorted(
            positions.values(),
            key=lambda p: p.conviction,
            reverse=True
        )
        
        # Extend highest conviction positions until we reach target
        for position in sorted_positions:
            if gap <= 0:
                break
            
            # Extend by up to 50% of current size, limited by remaining gap
            extend_amount = min(position.size_usdt * 0.5, gap)
            extend_percent = (extend_amount / position.size_usdt) * 100
            
            if extend_percent < 10:
                continue  # Too small to bother
            
            try:
                # NOTE: For now, just log - extend functionality needs DB implementation
                logger.info(f"Would extend {position.symbol} by ${extend_amount:,.2f} for minimum deployment")
                gap -= extend_amount
                    
            except Exception as e:
                logger.warning(f"Failed to auto-extend {position.symbol}: {e}")
                continue
        
        if gap > 0:
            logger.warning(f"Could not fully reach minimum deployment, ${gap:,.2f} still needed")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # DATABASE PERSISTENCE METHODS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def _save_position_to_db(self, position: Position):
        """Save a newly opened position to paper_positions table."""
        if not DATABASE_URL:
            return
        
        try:
            import asyncpg
            conn = await asyncpg.connect(DATABASE_URL)
            
            try:
                await conn.execute("""
                    INSERT INTO paper_positions 
                        (id, symbol, direction, entry_price, quantity, size_usdt,
                         leverage, conviction, reasoning, status, entry_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'OPEN', $10)
                    ON CONFLICT (id) DO UPDATE SET
                        status = 'OPEN',
                        updated_at = NOW()
                """,
                    position.id,
                    position.symbol,
                    position.direction,
                    position.entry_price,
                    position.quantity,
                    position.size_usdt,
                    position.leverage,
                    position.conviction,
                    position.reason,
                    position.opened_at,
                )
                logger.debug(f"Saved position {position.id} to database")
            finally:
                await conn.close()
                
        except ImportError:
            logger.debug("asyncpg not installed - skipping DB save")
        except Exception as e:
            logger.warning(f"Failed to save position to DB: {e}")
    
    async def _save_closed_position_to_db(self, closed, original_position: Position):
        """Update a closed position in paper_positions and save to paper_trades."""
        if not DATABASE_URL:
            return
        
        try:
            import asyncpg
            from uuid import uuid4
            
            conn = await asyncpg.connect(DATABASE_URL)
            
            try:
                # Update position status
                await conn.execute("""
                    UPDATE paper_positions SET
                        status = 'CLOSED',
                        exit_price = $2,
                        exit_time = $3,
                        realized_pnl = $4,
                        updated_at = NOW()
                    WHERE id = $1
                """,
                    closed.id,
                    closed.exit_price,
                    closed.closed_at,
                    closed.realized_pnl,
                )
                
                # Calculate total costs
                total_fee = closed.total_fees
                total_spread = closed.total_spread
                total_slippage = closed.total_slippage
                
                # Save to paper_trades
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
                    closed.id,
                    closed.symbol,
                    closed.direction,
                    closed.entry_price,
                    closed.exit_price,
                    closed.quantity,
                    closed.size_usdt,
                    closed.leverage,
                    closed.realized_pnl,
                    closed.realized_pnl_pct,
                    closed.opened_at,
                    closed.closed_at,
                    int((closed.closed_at - closed.opened_at).total_seconds()),
                    closed.close_reason,
                    closed.conviction,
                    original_position.reason,
                    total_fee,
                    total_spread,
                    total_slippage,
                )
                
                # Update trader_state with new capital
                await conn.execute("""
                    UPDATE trader_state SET
                        current_capital = $1,
                        total_trades = total_trades + 1,
                        winning_trades = winning_trades + CASE WHEN $2 > 0 THEN 1 ELSE 0 END,
                        losing_trades = losing_trades + CASE WHEN $2 < 0 THEN 1 ELSE 0 END,
                        total_pnl = total_pnl + $2,
                        peak_capital = GREATEST(peak_capital, $1),
                        updated_at = NOW()
                    WHERE id = 'main'
                """,
                    self.positions.capital,
                    closed.realized_pnl,
                )
                
                logger.debug(f"Saved closed position {closed.id} to database")
                
            finally:
                await conn.close()
                
        except ImportError:
            logger.debug("asyncpg not installed - skipping DB save")
        except Exception as e:
            logger.warning(f"Failed to save closed position to DB: {e}")
    
    async def run(self):
        """Main trading loop."""
        self._running = True
        
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info("        🚀 PORTFOLIO MANAGER STARTING 🚀")
        logger.info("═══════════════════════════════════════════════════════════════════")
        
        # Step 1: Restore state from database
        logger.info("  Restoring state from database...")
        await self._restore_from_db()
        
        # Get state from DB
        capital = await self.positions.get_capital()
        positions = await self.positions.get_positions()
        position_size = await self.positions.get_position_size_usdt()
        
        logger.info(f"  Max Positions:    {self._max_positions}")
        logger.info(f"  Position Size:    {POSITION_SIZE_PCT*100:.0f}% (${position_size:,.0f})")
        logger.info(f"  Current Capital:  ${capital:,.0f}")
        logger.info(f"  Open Positions:   {len(positions)}")
        logger.info(f"  Cycle Interval:   {CYCLE_INTERVAL_SECONDS}s ({CYCLE_INTERVAL_SECONDS//60}m)")
        logger.info(f"  Mode:             {'PAPER' if self.binance.paper_mode else 'LIVE'}")
        
        # Step 2: Start snapshot service for minute-by-minute persistence
        logger.info("  Starting snapshot service...")
        await self.snapshot_service.start()
        
        # Step 3: Start Binance WebSocket for live price updates
        symbols = list(positions.keys())
        if symbols:
            logger.info(f"  Starting price WebSocket for {len(symbols)} symbols...")
            await start_price_streaming(symbols)
        else:
            logger.info("  No open positions - WebSocket will start when positions are opened")
        
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info("")
        
        while self._running:
            try:
                # Run a cycle
                await self.run_cycle()
                
                if not self._running:
                    break
                
                # Broadcast idle phase with next cycle timestamp
                import time
                next_cycle_at = time.time() + CYCLE_INTERVAL_SECONDS
                await self._broadcast_phase("idle", next_cycle_at)
                
                # Wait for next cycle
                logger.info(f"Next cycle in {CYCLE_INTERVAL_SECONDS//60} minutes...")
                
                # Wait in small increments to allow graceful shutdown
                for _ in range(CYCLE_INTERVAL_SECONDS // 5):
                    if not self._running:
                        break
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await self._broadcast_phase("error")
                await asyncio.sleep(60)
        
        logger.info("Trading loop stopped")
    
    async def shutdown(self):
        """Gracefully shutdown."""
        logger.info("Shutting down Portfolio Manager...")
        self._running = False
        
        # Stop snapshot service
        await self.snapshot_service.stop()
        
        # Close Grok client
        await self.analyst.close()
        
        # Close Binance client
        await self.binance.close()
        
        logger.info("Portfolio Manager shutdown complete")
    
    def get_status(self) -> dict:
        """Get current status for API."""
        return {
            "running": self._running,
            "phase": self._current_phase,
            "cycle_count": self._cycle_count,
            "cycle_interval_seconds": CYCLE_INTERVAL_SECONDS,
            "mode": "paper" if self.binance.paper_mode else "live",
            "portfolio": {"note": "Use API endpoints for portfolio data"},
            "logbook": self.logbook.get_statistics(),
            "snapshot_service": self.snapshot_service.get_status(),
            "db_restored": self._db_restored,
        }
    
    def reset(self):
        """
        Reset is handled by DB - no in-memory state to reset.
        
        DB-FIRST: Use the /api/paper-trades/reset endpoint instead.
        This method is kept for backwards compatibility but does nothing.
        """
        logger.warning("PortfolioManager.reset() called - DB-First architecture")
        logger.warning("Use /api/paper-trades/reset endpoint to reset DB state")
        self._cycle_count = 0
        self._db_restored = False
        
        return {
            "capital": self._starting_capital,
            "positions_cleared": False,
            "message": "DB-First: Use API to reset database",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE & ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

# NOTE: get_portfolio_manager and set_portfolio_manager are now in trading_state.py
# to avoid duplicate global variables. Import from there.

async def run_portfolio_manager():
    """Main entry point for the portfolio manager."""
    from trading_state import get_portfolio_manager
    manager = get_portfolio_manager()
    
    if manager is None:
        logger.error("No portfolio manager set!")
        return
    
    try:
        await manager.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        await manager.shutdown()

