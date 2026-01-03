"""
Position Model - Tracks open and closed positions
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, DateTime, Numeric, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Position(Base, TimestampMixin):
    """
    Represents a trading position (long or short).
    Tracks entry, exit, P&L, and risk parameters.
    """
    
    __tablename__ = "positions"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Position details
    coin: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'long' or 'short'
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    
    # Pricing
    entry_price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    
    # P&L
    unrealized_pnl: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    
    # Risk management
    stop_loss: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    take_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    
    # Leverage (4-7x aggressive mode)
    leverage: Mapped[Decimal] = mapped_column(Numeric(4, 1), default=1.0, nullable=False)
    liquidation_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    margin_required: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        nullable=False,
        index=True
    )  # 'open', 'closed', 'liquidated'
    
    # Timestamps
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_positions_coin_status', 'coin', 'status'),
    )
    
    def calculate_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L at given price"""
        if self.side == "long":
            return (current_price - self.entry_price) * self.quantity
        else:  # short
            return (self.entry_price - current_price) * self.quantity
    
    def calculate_pnl_percent(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L percentage"""
        if self.side == "long":
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100
    
    def check_stop_loss(self, current_price: Decimal) -> bool:
        """Check if stop loss has been hit"""
        if not self.stop_loss:
            return False
        if self.side == "long":
            return current_price <= self.stop_loss
        else:
            return current_price >= self.stop_loss
    
    def check_take_profit(self, current_price: Decimal) -> bool:
        """Check if take profit has been hit"""
        if not self.take_profit:
            return False
        if self.side == "long":
            return current_price >= self.take_profit
        else:
            return current_price <= self.take_profit
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "coin": self.coin,
            "side": self.side,
            "quantity": float(self.quantity) if self.quantity else None,
            "entry_price": float(self.entry_price) if self.entry_price else None,
            "current_price": float(self.current_price) if self.current_price else None,
            "unrealized_pnl": float(self.unrealized_pnl) if self.unrealized_pnl else None,
            "realized_pnl": float(self.realized_pnl) if self.realized_pnl else None,
            "stop_loss": float(self.stop_loss) if self.stop_loss else None,
            "take_profit": float(self.take_profit) if self.take_profit else None,
            "leverage": float(self.leverage) if self.leverage else 1.0,
            "liquidation_price": float(self.liquidation_price) if self.liquidation_price else None,
            "status": self.status,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }
