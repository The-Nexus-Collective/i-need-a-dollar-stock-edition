"""
Risk Models - Risk events and system configuration
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class RiskEvent(Base):
    """
    Records risk-related events (limit breaches, circuit breakers, etc.)
    """
    
    __tablename__ = "risk_events"
    
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
    
    # Event classification
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )  # 'drawdown_breach', 'var_breach', 'position_limit', 'circuit_breaker'
    
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True
    )  # 'info', 'warning', 'critical', 'emergency'
    
    # Trigger details
    trigger_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 8),
        nullable=True
    )
    threshold_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(20, 8),
        nullable=True
    )
    
    # Action taken
    action_taken: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True
    )  # 'reduce_size', 'close_positions', 'halt_trading'
    
    # Additional details
    details: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    # Acknowledgment
    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "severity": self.severity,
            "trigger_value": float(self.trigger_value) if self.trigger_value else None,
            "threshold_value": float(self.threshold_value) if self.threshold_value else None,
            "action_taken": self.action_taken,
            "details": self.details,
            "acknowledged": self.acknowledged,
            "acknowledged_by": self.acknowledged_by,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


class SystemConfig(Base):
    """
    System configuration stored in database.
    Allows runtime configuration changes.
    """
    
    __tablename__ = "system_config"
    
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    updated_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    @classmethod
    async def get_value(cls, session, key: str, default: Any = None) -> Any:
        """Get configuration value by key"""
        from sqlalchemy import select
        result = await session.execute(
            select(cls.value).where(cls.key == key)
        )
        row = result.scalar_one_or_none()
        return row if row is not None else default
    
    @classmethod
    async def set_value(
        cls,
        session,
        key: str,
        value: Any,
        description: str = None,
        updated_by: str = "system"
    ) -> None:
        """Set configuration value"""
        from sqlalchemy import select
        from sqlalchemy.dialects.postgresql import insert
        
        stmt = insert(cls).values(
            key=key,
            value=value,
            description=description,
            updated_by=updated_by
        ).on_conflict_do_update(
            index_elements=[cls.key],
            set_={
                "value": value,
                "description": description,
                "updated_by": updated_by,
                "updated_at": datetime.utcnow()
            }
        )
        await session.execute(stmt)


# Risk limits configuration keys
class RiskLimits:
    """
    Constants for risk configuration keys.
    
    Updated limits for leveraged perpetuals trading:
    - Per-Asset: 15% (leverage-adjusted)
    - Max Deployed: 70% (leaves buffer for margin)
    - Altcoin Cap: 40% (non-BTC/ETH exposure)
    - Daily Loss: 4% (circuit breaker trigger)
    - Leverage: 3-5x adaptive
    """
    POSITION_LIMIT_PER_ASSET = "risk.position_limit_per_asset"
    POSITION_LIMIT_ALTCOINS = "risk.position_limit_altcoins"
    MAX_DEPLOYED = "risk.max_deployed"
    DRAWDOWN_LEVEL_1 = "risk.drawdown_level_1"
    DRAWDOWN_LEVEL_2 = "risk.drawdown_level_2"
    DRAWDOWN_LEVEL_3 = "risk.drawdown_level_3"
    VAR_LIMIT = "risk.var_limit"
    STOP_LOSS_ATR = "trading.stop_loss_atr"
    TAKE_PROFIT_ATR = "trading.take_profit_atr"
    RISK_PER_TRADE = "trading.risk_per_trade"
    MAX_LEVERAGE = "risk.max_leverage"
    MIN_LEVERAGE = "risk.min_leverage"
    DAILY_LOSS_LIMIT = "risk.daily_loss_limit"
    
    # Default values (updated for leveraged perpetuals)
    DEFAULTS = {
        POSITION_LIMIT_PER_ASSET: 0.15,   # 15% max equity in one coin (was 10%)
        POSITION_LIMIT_ALTCOINS: 0.40,    # 40% non-BTC/ETH exposure (was 30%)
        MAX_DEPLOYED: 0.70,               # 70% total positions (was 80%)
        DRAWDOWN_LEVEL_1: 0.04,           # 4% triggers warning (was 5%)
        DRAWDOWN_LEVEL_2: 0.08,           # 8% reduces position size
        DRAWDOWN_LEVEL_3: 0.12,           # 12% halts new trades (was 15%)
        VAR_LIMIT: 0.03,                  # 3% daily VaR limit
        STOP_LOSS_ATR: 1.5,               # Stop loss at 1.5x ATR
        TAKE_PROFIT_ATR: 4.0,             # Take profit at 4x ATR
        RISK_PER_TRADE: 0.02,             # 2% risk per trade
        MAX_LEVERAGE: 5.0,                # Maximum adaptive leverage
        MIN_LEVERAGE: 3.0,                # Minimum leverage floor
        DAILY_LOSS_LIMIT: 0.04,           # 4% daily loss circuit breaker
    }
