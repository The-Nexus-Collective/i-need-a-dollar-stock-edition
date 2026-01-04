"""
Snapshot Service - Minute-by-minute DB persistence

Handles:
- Portfolio equity snapshots every 60 seconds
- Position PnL history tracking
- Database persistence for equity curves and risk analysis
"""

import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .positions import PositionTracker

logger = logging.getLogger(__name__)

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Global database connection pool
_db_pool = None


async def get_db_pool():
    """Get or create database connection pool."""
    global _db_pool
    if _db_pool is None and DATABASE_URL:
        try:
            import asyncpg
            _db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
            logger.info("SnapshotService: Database connection pool created")
        except Exception as e:
            logger.warning(f"SnapshotService: Failed to create DB pool: {e}")
    return _db_pool


class SnapshotService:
    """
    Background service that saves portfolio and position snapshots to the database.
    
    Runs every 60 seconds to:
    1. Save portfolio equity snapshot to portfolio_snapshots
    2. Save each position's PnL to position_pnl_history
    """
    
    SNAPSHOT_INTERVAL_SECONDS = 60  # Save every minute
    
    def __init__(self, position_tracker: "PositionTracker"):
        """
        Initialize snapshot service.
        
        Args:
            position_tracker: Reference to PositionTracker for accessing positions
        """
        self.position_tracker = position_tracker
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._snapshot_count = 0
    
    async def start(self):
        """Start the background snapshot task."""
        if self._running:
            logger.warning("SnapshotService already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("SnapshotService started - saving snapshots every 60 seconds")
    
    async def stop(self):
        """Stop the background snapshot task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SnapshotService stopped")
    
    async def _run_loop(self):
        """Main loop that runs every SNAPSHOT_INTERVAL_SECONDS."""
        while self._running:
            try:
                await self._save_snapshot()
                self._snapshot_count += 1
                
                if self._snapshot_count % 10 == 0:  # Log every 10 snapshots
                    logger.info(f"SnapshotService: Saved {self._snapshot_count} snapshots")
                    
            except Exception as e:
                logger.error(f"SnapshotService error: {e}")
            
            # Wait for next interval
            await asyncio.sleep(self.SNAPSHOT_INTERVAL_SECONDS)
    
    async def _save_snapshot(self):
        """Save portfolio and position snapshots to database."""
        pool = await get_db_pool()
        if not pool:
            logger.debug("SnapshotService: No DB pool available")
            return
        
        try:
            async with pool.acquire() as conn:
                now = datetime.utcnow()
                
                # Get portfolio statistics
                stats = self.position_tracker.get_statistics()
                positions = list(self.position_tracker.positions.values())
                
                # Calculate additional metrics (size_usdt is notional, divide by leverage for margin)
                total_margin_used = sum(
                    p.size_usdt / p.leverage if p.leverage > 0 else p.size_usdt
                    for p in positions
                )
                avg_margin_risk = (
                    sum(p.margin_risk_pct for p in positions) / len(positions)
                    if positions else 0
                )
                
                # 1. Save portfolio snapshot
                await conn.execute("""
                    INSERT INTO portfolio_snapshots 
                        (timestamp, total_equity, cash, positions_value, 
                         unrealized_pnl, realized_pnl, daily_pnl, daily_pnl_percent,
                         total_trades, winning_trades, losing_trades,
                         open_positions_count, total_margin_used, avg_margin_risk_pct)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                    ON CONFLICT (timestamp) DO UPDATE SET
                        total_equity = EXCLUDED.total_equity,
                        unrealized_pnl = EXCLUDED.unrealized_pnl,
                        open_positions_count = EXCLUDED.open_positions_count
                """,
                    now,
                    Decimal(str(stats['total_equity'])),
                    Decimal(str(stats['current_capital'])),
                    Decimal(str(sum(p.size_usdt for p in positions))),
                    Decimal(str(stats['unrealized_pnl'])),
                    Decimal(str(stats['realized_pnl'])),
                    Decimal('0'),  # daily_pnl - would need start of day tracking
                    Decimal('0'),  # daily_pnl_percent
                    stats['total_trades'],
                    stats['winning_trades'],
                    stats['losing_trades'],
                    len(positions),
                    Decimal(str(total_margin_used)),
                    Decimal(str(avg_margin_risk)),
                )
                
                # 2. Save position PnL history for each open position
                if positions:
                    for pos in positions:
                        await conn.execute("""
                            INSERT INTO position_pnl_history 
                                (timestamp, position_id, symbol, direction,
                                 entry_price, current_price, unrealized_pnl, unrealized_pnl_pct,
                                 leverage, margin_risk_pct, liquidation_price,
                                 size_usdt, quantity)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        """,
                            now,
                            pos.id,
                            pos.symbol,
                            pos.direction,
                            Decimal(str(pos.entry_price)),
                            Decimal(str(pos.current_price)),
                            Decimal(str(pos.unrealized_pnl)),
                            Decimal(str(pos.unrealized_pnl_pct)),
                            pos.leverage,
                            Decimal(str(pos.margin_risk_pct)),
                            Decimal(str(pos.liquidation_price)),
                            Decimal(str(pos.size_usdt)),
                            Decimal(str(pos.quantity)),
                        )
                
                logger.debug(f"Saved snapshot: equity=${stats['total_equity']:,.2f}, positions={len(positions)}")
                
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")
    
    async def save_immediate(self):
        """Save an immediate snapshot (e.g., after a trade)."""
        await self._save_snapshot()
    
    async def cleanup_old_history(self, days: int = 7):
        """Delete position history older than specified days."""
        pool = await get_db_pool()
        if not pool:
            return
        
        try:
            async with pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM position_pnl_history 
                    WHERE timestamp < NOW() - INTERVAL '%s days'
                """, days)
                logger.info(f"Cleaned up old position history: {result}")
        except Exception as e:
            logger.error(f"Failed to cleanup history: {e}")
    
    def get_status(self) -> dict:
        """Get service status."""
        return {
            "running": self._running,
            "snapshot_count": self._snapshot_count,
            "interval_seconds": self.SNAPSHOT_INTERVAL_SECONDS,
        }
    
    def reset(self):
        """Reset snapshot counter (for paper trading reset)."""
        old_count = self._snapshot_count
        self._snapshot_count = 0
        logger.warning(f"SnapshotService reset: cleared {old_count} snapshot count")

