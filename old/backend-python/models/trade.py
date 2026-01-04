"""
Trade Model - Individual order executions
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Trade(Base):
    """
    Represents an individual trade/order execution.
    Multiple trades can be associated with a single position.
    """
    
    __tablename__ = "trades"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # References
    position_id: Mapped[Optional[str]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id"),
        nullable=True,
        index=True
    )
    order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    exchange_order_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Trade details
    coin: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # 'buy' or 'sell'
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'market', 'limit', 'stop'
    
    # Quantities
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    
    # Fees
    fee: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=0, nullable=False)
    fee_currency: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True
    )  # 'pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected'
    
    # Mode
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Timestamps
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_trades_created', 'created_at'),
        Index('idx_trades_coin_status', 'coin', 'status'),
    )
    
    @property
    def value(self) -> Decimal:
        """Calculate trade value"""
        return self.quantity * self.price
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "position_id": str(self.position_id) if self.position_id else None,
            "order_id": self.order_id,
            "exchange_order_id": self.exchange_order_id,
            "coin": self.coin,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": float(self.quantity) if self.quantity else None,
            "price": float(self.price) if self.price else None,
            "fee": float(self.fee) if self.fee else None,
            "fee_currency": self.fee_currency,
            "status": self.status,
            "is_paper": self.is_paper,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
