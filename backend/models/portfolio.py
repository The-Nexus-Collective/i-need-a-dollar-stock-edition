"""
Portfolio Model - Portfolio snapshots for equity curve
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Column, DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class PortfolioSnapshot(Base):
    """
    Point-in-time snapshot of portfolio state.
    Used for equity curve, performance metrics, and risk calculations.
    TimescaleDB hypertable for efficient time-series queries.
    """
    
    __tablename__ = "portfolio_snapshots"
    
    # Primary key is timestamp (for TimescaleDB)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
        default=datetime.utcnow
    )
    
    # Portfolio values
    total_equity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cash: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    positions_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    
    # P&L
    unrealized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    daily_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    daily_pnl_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    
    # Risk metrics
    var_95: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    max_drawdown: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 4), nullable=True)
    
    # Performance metrics
    win_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "total_equity": float(self.total_equity) if self.total_equity else None,
            "cash": float(self.cash) if self.cash else None,
            "positions_value": float(self.positions_value) if self.positions_value else None,
            "unrealized_pnl": float(self.unrealized_pnl) if self.unrealized_pnl else None,
            "realized_pnl": float(self.realized_pnl) if self.realized_pnl else None,
            "daily_pnl": float(self.daily_pnl) if self.daily_pnl else None,
            "daily_pnl_percent": float(self.daily_pnl_percent) if self.daily_pnl_percent else None,
            "var_95": float(self.var_95) if self.var_95 else None,
            "max_drawdown": float(self.max_drawdown) if self.max_drawdown else None,
            "win_rate": float(self.win_rate) if self.win_rate else None,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
        }
