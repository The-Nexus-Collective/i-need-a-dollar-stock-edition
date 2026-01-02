"""
Portfolio Manager - Tracks portfolio state and metrics
"""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, func

from events import get_event_bus, PortfolioSnapshotEvent
from models import AsyncSessionLocal, Position, Trade, PortfolioSnapshot

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Portfolio Manager - Centralized portfolio state management.
    
    Responsibilities:
    1. Track total equity, cash, positions value
    2. Calculate P&L (realized, unrealized, daily)
    3. Compute performance metrics (win rate, drawdown)
    4. Store periodic snapshots for equity curve
    """
    
    def __init__(self, initial_equity: float = 10000.0):
        self.initial_equity = initial_equity
        self.bus = get_event_bus()
    
    async def get_current_state(self) -> Dict:
        """Get current portfolio state"""
        async with AsyncSessionLocal() as session:
            # Get open positions
            result = await session.execute(
                select(Position).where(Position.status == 'open')
            )
            positions = result.scalars().all()
            
            # Calculate positions value
            positions_value = sum(
                float(p.quantity) * float(p.current_price or p.entry_price)
                for p in positions
            )
            
            # Calculate unrealized P&L
            unrealized_pnl = sum(
                float(p.unrealized_pnl or 0)
                for p in positions
            )
            
            # Get latest snapshot for cash
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            cash = float(snapshot.cash) if snapshot else self.initial_equity
            
            # Calculate realized P&L
            result = await session.execute(
                select(func.sum(Position.realized_pnl))
                .where(Position.status == 'closed')
            )
            realized_pnl = float(result.scalar() or 0)
            
            # Total equity
            total_equity = cash + positions_value
            
            # Get today's start equity for daily P&L
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            result = await session.execute(
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.timestamp >= today_start)
                .order_by(PortfolioSnapshot.timestamp.asc())
                .limit(1)
            )
            day_start_snapshot = result.scalar_one_or_none()
            
            if day_start_snapshot:
                day_start_equity = float(day_start_snapshot.total_equity)
                daily_pnl = total_equity - day_start_equity
                daily_pnl_percent = (daily_pnl / day_start_equity) * 100
            else:
                daily_pnl = 0
                daily_pnl_percent = 0
            
            return {
                'total_equity': total_equity,
                'cash': cash,
                'positions_value': positions_value,
                'unrealized_pnl': unrealized_pnl,
                'realized_pnl': realized_pnl,
                'daily_pnl': daily_pnl,
                'daily_pnl_percent': daily_pnl_percent,
                'open_positions': len(positions),
            }
    
    async def get_performance_metrics(self) -> Dict:
        """Calculate performance metrics"""
        async with AsyncSessionLocal() as session:
            # Total trades
            result = await session.execute(
                select(func.count(Position.id))
                .where(Position.status == 'closed')
            )
            total_trades = result.scalar() or 0
            
            # Winning trades
            result = await session.execute(
                select(func.count(Position.id))
                .where(Position.status == 'closed')
                .where(Position.realized_pnl > 0)
            )
            winning_trades = result.scalar() or 0
            
            # Calculate win rate
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            # Average win/loss
            result = await session.execute(
                select(func.avg(Position.realized_pnl))
                .where(Position.status == 'closed')
                .where(Position.realized_pnl > 0)
            )
            avg_win = float(result.scalar() or 0)
            
            result = await session.execute(
                select(func.avg(Position.realized_pnl))
                .where(Position.status == 'closed')
                .where(Position.realized_pnl < 0)
            )
            avg_loss = float(result.scalar() or 0)
            
            # Profit factor
            result = await session.execute(
                select(func.sum(Position.realized_pnl))
                .where(Position.status == 'closed')
                .where(Position.realized_pnl > 0)
            )
            total_wins = float(result.scalar() or 0)
            
            result = await session.execute(
                select(func.abs(func.sum(Position.realized_pnl)))
                .where(Position.status == 'closed')
                .where(Position.realized_pnl < 0)
            )
            total_losses = float(result.scalar() or 1)
            
            profit_factor = total_wins / total_losses if total_losses > 0 else 0
            
            # Max drawdown from snapshots
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.asc())
            )
            snapshots = result.scalars().all()
            
            max_drawdown = 0
            peak = 0
            for snapshot in snapshots:
                equity = float(snapshot.total_equity)
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak if peak > 0 else 0
                if drawdown > max_drawdown:
                    max_drawdown = drawdown
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': total_trades - winning_trades,
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'max_drawdown': max_drawdown * 100,
            }
    
    async def get_equity_history(self, limit: int = 1000) -> List[Dict]:
        """Get equity history for charting"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(limit)
            )
            snapshots = result.scalars().all()
            
            return [
                {
                    'timestamp': s.timestamp.isoformat(),
                    'equity': float(s.total_equity),
                    'cash': float(s.cash),
                    'positions_value': float(s.positions_value),
                }
                for s in reversed(snapshots)
            ]


async def main():
    """Test portfolio manager"""
    pm = PortfolioManager()
    
    state = await pm.get_current_state()
    print("Current State:", state)
    
    metrics = await pm.get_performance_metrics()
    print("Metrics:", metrics)


if __name__ == "__main__":
    asyncio.run(main())
