"""
Event Schemas for Redis Streams
All system communication flows through typed events
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All event types in the system"""
    # Signal Events
    SIGNAL_GENERATED = "signal.generated"
    SIGNAL_EXPIRED = "signal.expired"
    
    # Risk Events
    RISK_CHECK_REQUESTED = "risk.check_requested"
    RISK_APPROVED = "risk.approved"
    RISK_REJECTED = "risk.rejected"
    RISK_LIMIT_BREACH = "risk.limit_breach"
    
    # Order Events
    ORDER_SUBMITTED = "order.submitted"
    ORDER_FILLED = "order.filled"
    ORDER_PARTIAL = "order.partial"
    ORDER_CANCELLED = "order.cancelled"
    ORDER_REJECTED = "order.rejected"
    
    # Position Events
    POSITION_OPENED = "position.opened"
    POSITION_UPDATED = "position.updated"
    POSITION_CLOSED = "position.closed"
    
    # Portfolio Events
    PORTFOLIO_SNAPSHOT = "portfolio.snapshot"
    PORTFOLIO_REBALANCE = "portfolio.rebalance"
    
    # System Events
    CIRCUIT_BREAKER_TRIGGERED = "system.circuit_breaker"
    SYSTEM_HALT = "system.halt"
    SYSTEM_RESUME = "system.resume"
    HEARTBEAT = "system.heartbeat"
    
    # Market Data Events
    PRICE_UPDATE = "market.price_update"
    MARKET_DATA_STALE = "market.data_stale"


class BaseEvent(BaseModel):
    """Base event with common fields"""
    id: UUID = Field(default_factory=uuid4)
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str  # Which service produced this event
    correlation_id: Optional[UUID] = None  # For tracking related events
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Multi-asset support
    asset_type: str = "crypto"  # 'crypto' or 'stock'
    account_id: Optional[str] = None  # Which account this event relates to
    
    class Config:
        use_enum_values = True
        json_encoders = {
            UUID: str,
            datetime: lambda v: v.isoformat(),
            Decimal: str,
        }

    def to_redis_dict(self) -> Dict[str, str]:
        """Convert to Redis-compatible dict (all string values)"""
        import json
        return {"data": self.model_dump_json()}
    
    @classmethod
    def from_redis_dict(cls, data: Dict[bytes, bytes]) -> "BaseEvent":
        """Reconstruct from Redis dict"""
        import json
        json_data = data[b"data"].decode()
        return cls.model_validate_json(json_data)


# ═══════════════════════════════════════════════════════════════════════════
# SIGNAL EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class SignalGeneratedEvent(BaseEvent):
    """New trading signal from AI analysis"""
    type: EventType = EventType.SIGNAL_GENERATED
    
    signal_id: UUID = Field(default_factory=uuid4)
    coin: str
    sentiment_score: float  # -100 to +100
    narrative_strength: float  # 0 to 100
    combined_score: float  # sentiment * (narrative/100)
    confidence: float  # 0 to 1
    recommended_action: str  # 'long', 'short', 'hold', 'close'
    raw_response: Optional[str] = None
    response_hash: Optional[str] = None
    
    # Market context at time of signal
    current_price: Optional[float] = None
    atr_value: Optional[float] = None
    volume_24h: Optional[float] = None


class RiskCheckRequestedEvent(BaseEvent):
    """Signal awaiting risk approval"""
    type: EventType = EventType.RISK_CHECK_REQUESTED
    
    signal_id: UUID
    coin: str
    action: str  # 'long', 'short'
    proposed_quantity: float
    proposed_entry: float
    proposed_stop_loss: float
    proposed_take_profit: float
    signal_confidence: float


# ═══════════════════════════════════════════════════════════════════════════
# RISK EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class RiskApprovedEvent(BaseEvent):
    """Risk manager approved trade"""
    type: EventType = EventType.RISK_APPROVED
    
    signal_id: UUID
    coin: str
    action: str
    approved_quantity: float  # May be reduced from proposed
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_checks_passed: List[str]


class RiskRejectedEvent(BaseEvent):
    """Risk manager blocked trade"""
    type: EventType = EventType.RISK_REJECTED
    
    signal_id: UUID
    coin: str
    action: str
    rejection_reasons: List[str]
    risk_checks_failed: List[str]
    current_exposure: float
    limit_values: Dict[str, float]


class RiskLimitBreachEvent(BaseEvent):
    """Risk limit breached"""
    type: EventType = EventType.RISK_LIMIT_BREACH
    
    limit_type: str  # 'position', 'drawdown', 'var', 'exposure'
    current_value: float
    threshold_value: float
    severity: str  # 'warning', 'critical', 'emergency'
    affected_positions: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════
# ORDER EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class OrderSubmittedEvent(BaseEvent):
    """Order sent to exchange"""
    type: EventType = EventType.ORDER_SUBMITTED
    
    order_id: UUID = Field(default_factory=uuid4)
    signal_id: UUID
    position_id: Optional[UUID] = None
    coin: str
    side: str  # 'buy', 'sell'
    order_type: str  # 'market', 'limit', 'stop'
    quantity: float
    price: Optional[float] = None  # For limit orders
    stop_price: Optional[float] = None  # For stop orders
    is_paper: bool = True


class OrderFilledEvent(BaseEvent):
    """Execution confirmed"""
    type: EventType = EventType.ORDER_FILLED
    
    order_id: UUID
    exchange_order_id: Optional[str] = None
    position_id: Optional[UUID] = None
    coin: str
    side: str
    quantity: float
    fill_price: float
    fee: float = 0
    fee_currency: str = "USDT"
    is_paper: bool = True


# ═══════════════════════════════════════════════════════════════════════════
# POSITION EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class PositionOpenedEvent(BaseEvent):
    """New position opened"""
    type: EventType = EventType.POSITION_OPENED
    
    position_id: UUID = Field(default_factory=uuid4)
    coin: str
    side: str  # 'long', 'short'
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    signal_id: UUID


class PositionUpdatedEvent(BaseEvent):
    """Position state changed"""
    type: EventType = EventType.POSITION_UPDATED
    
    position_id: UUID
    coin: str
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    distance_to_stop: float  # In price units
    distance_to_target: float


class PositionClosedEvent(BaseEvent):
    """Position closed"""
    type: EventType = EventType.POSITION_CLOSED
    
    position_id: UUID
    coin: str
    side: str
    quantity: float
    entry_price: float
    exit_price: float
    realized_pnl: float
    realized_pnl_percent: float
    close_reason: str  # 'stop_loss', 'take_profit', 'manual', 'circuit_breaker', 'end_of_day'
    duration_seconds: int


# ═══════════════════════════════════════════════════════════════════════════
# SYSTEM EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class CircuitBreakerEvent(BaseEvent):
    """Emergency stop triggered"""
    type: EventType = EventType.CIRCUIT_BREAKER_TRIGGERED
    
    level: int  # 1, 2, or 3
    trigger_type: str  # 'drawdown', 'var', 'manual'
    trigger_value: float
    threshold: float
    action_taken: str  # 'reduce_size', 'close_all', 'halt_system'
    positions_affected: List[str] = Field(default_factory=list)


class PortfolioSnapshotEvent(BaseEvent):
    """Portfolio state snapshot"""
    type: EventType = EventType.PORTFOLIO_SNAPSHOT
    
    total_equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    daily_pnl_percent: float
    var_95: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    open_positions: int = 0


class HeartbeatEvent(BaseEvent):
    """Service health check"""
    type: EventType = EventType.HEARTBEAT
    
    service_name: str
    status: str  # 'healthy', 'degraded', 'unhealthy'
    uptime_seconds: int
    memory_usage_mb: float
    active_tasks: int = 0
    last_activity: Optional[datetime] = None


# ═══════════════════════════════════════════════════════════════════════════
# MARKET DATA EVENTS
# ═══════════════════════════════════════════════════════════════════════════

class PriceUpdateEvent(BaseEvent):
    """Real-time price update"""
    type: EventType = EventType.PRICE_UPDATE
    
    coin: str
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume_24h: Optional[float] = None
    price_change_24h: Optional[float] = None


# Event type registry for deserialization
EVENT_TYPE_MAP = {
    EventType.SIGNAL_GENERATED: SignalGeneratedEvent,
    EventType.RISK_CHECK_REQUESTED: RiskCheckRequestedEvent,
    EventType.RISK_APPROVED: RiskApprovedEvent,
    EventType.RISK_REJECTED: RiskRejectedEvent,
    EventType.RISK_LIMIT_BREACH: RiskLimitBreachEvent,
    EventType.ORDER_SUBMITTED: OrderSubmittedEvent,
    EventType.ORDER_FILLED: OrderFilledEvent,
    EventType.POSITION_OPENED: PositionOpenedEvent,
    EventType.POSITION_UPDATED: PositionUpdatedEvent,
    EventType.POSITION_CLOSED: PositionClosedEvent,
    EventType.CIRCUIT_BREAKER_TRIGGERED: CircuitBreakerEvent,
    EventType.PORTFOLIO_SNAPSHOT: PortfolioSnapshotEvent,
    EventType.HEARTBEAT: HeartbeatEvent,
    EventType.PRICE_UPDATE: PriceUpdateEvent,
}


def deserialize_event(data: Dict[bytes, bytes]) -> BaseEvent:
    """Deserialize event from Redis to correct type"""
    import json
    json_data = json.loads(data[b"data"].decode())
    event_type = EventType(json_data["type"])
    event_class = EVENT_TYPE_MAP.get(event_type, BaseEvent)
    return event_class.model_validate(json_data)
