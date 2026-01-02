"""
Signal Model - AI-generated trading signals
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Signal(Base):
    """
    Represents an AI-generated trading signal.
    Tracks sentiment analysis, risk approval, and execution status.
    """
    
    __tablename__ = "signals"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    # Timing
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Signal details
    coin: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    
    # Sentiment analysis
    sentiment_score: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )  # -100 to +100
    
    narrative_strength: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )  # 0 to 100
    
    combined_score: Mapped[Decimal] = mapped_column(
        Numeric(8, 4),
        nullable=False
    )  # sentiment * (narrative/100)
    
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )  # 0 to 1
    
    # Recommendation
    recommended_action: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True
    )  # 'long', 'short', 'hold', 'close'
    
    # Raw AI response
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    # Risk approval
    risk_approved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    risk_rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Execution status
    executed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Filter results (new)
    filter_score_pass: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    filter_volume_pass: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    
    # Market data at signal time (new)
    volume_1h: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    volume_24h_avg: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    atr_1h: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    price_at_signal: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 8), nullable=True)
    
    # Batch tracking (all signals from same Grok call)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Indexes
    __table_args__ = (
        Index('idx_signals_timestamp', 'timestamp'),
        Index('idx_signals_coin_executed', 'coin', 'executed'),
        Index('idx_signals_filters', 'filter_score_pass', 'filter_volume_pass'),
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "coin": self.coin,
            "sentiment_score": float(self.sentiment_score) if self.sentiment_score else None,
            "narrative_strength": float(self.narrative_strength) if self.narrative_strength else None,
            "combined_score": float(self.combined_score) if self.combined_score else None,
            "confidence": float(self.confidence) if self.confidence else None,
            "recommended_action": self.recommended_action,
            "risk_approved": self.risk_approved,
            "risk_rejection_reason": self.risk_rejection_reason,
            "executed": self.executed,
            "filter_score_pass": self.filter_score_pass,
            "filter_volume_pass": self.filter_volume_pass,
            "volume_1h": float(self.volume_1h) if self.volume_1h else None,
            "volume_24h_avg": float(self.volume_24h_avg) if self.volume_24h_avg else None,
            "atr_1h": float(self.atr_1h) if self.atr_1h else None,
            "price_at_signal": float(self.price_at_signal) if self.price_at_signal else None,
            "batch_id": self.batch_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
