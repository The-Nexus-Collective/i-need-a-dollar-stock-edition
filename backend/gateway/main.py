"""
FastAPI Gateway - Main Application
Central API entry point with WebSocket support for real-time updates
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Set
from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from events import EventBus, get_event_bus, BaseEvent
from models import get_db, Position, Trade, Signal, PortfolioSnapshot, RiskEvent
from models.audit import AuditLog
from .auth import get_current_user, create_access_token, User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════════════

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        await websocket.accept()
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
        logger.info(f"WebSocket connected to channel: {channel}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = "all"):
        async with self._lock:
            if channel in self.active_connections:
                self.active_connections[channel].discard(websocket)
    
    async def broadcast(self, message: dict, channel: str = "all"):
        """Broadcast message to all connections on a channel"""
        if channel not in self.active_connections:
            return
        
        dead_connections = set()
        for connection in self.active_connections[channel]:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.add(connection)
        
        # Clean up dead connections
        async with self._lock:
            for conn in dead_connections:
                self.active_connections[channel].discard(conn)
    
    async def broadcast_event(self, event: BaseEvent):
        """Broadcast an event to relevant channels"""
        event_data = {
            "type": "event",
            "event_type": str(event.type),
            "data": json.loads(event.model_dump_json()),
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast(event_data, "all")
        
        # Also broadcast to specific channel based on event type
        if "signal" in str(event.type):
            await self.broadcast(event_data, "signals")
        elif "position" in str(event.type) or "order" in str(event.type):
            await self.broadcast(event_data, "trading")
        elif "risk" in str(event.type):
            await self.broadcast(event_data, "risk")


manager = ConnectionManager()


async def event_forwarder():
    """Forward Redis events to WebSocket clients"""
    bus = get_event_bus()
    await bus.connect()
    
    async def handle_event(channel: str, event: BaseEvent):
        await manager.broadcast_event(event)
    
    # Subscribe to all real-time channels
    await bus.subscribe_realtime(
        ["signals", "risk", "orders", "positions", "portfolio", "system"],
        handle_event
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("Starting Trading Platform Gateway...")
    
    # Start event forwarder in background
    forwarder_task = asyncio.create_task(event_forwarder())
    
    # Initialize event bus
    bus = get_event_bus()
    await bus.connect()
    
    logger.info("Gateway ready")
    
    yield
    
    # Cleanup
    forwarder_task.cancel()
    await bus.disconnect()
    logger.info("Gateway shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Trading Platform API",
    description="Production-grade autonomous trading platform with AI-powered sentiment analysis",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include realtime WebSocket router
from .realtime import router as realtime_router
app.include_router(realtime_router, prefix="/ws", tags=["WebSocket"])


# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str
    mode: str


class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PortfolioResponse(BaseModel):
    total_equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl: float
    daily_pnl: float
    daily_pnl_percent: float
    open_positions: int
    var_95: float | None
    max_drawdown: float | None
    win_rate: float | None


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH & AUTH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0",
        mode=os.getenv("MODE", "paper")
    )


@app.post("/auth/token", response_model=TokenResponse, tags=["Authentication"])
async def login(request: TokenRequest):
    """
    Get access token.
    
    For demo purposes, accepts any username/password.
    In production, validate against user database.
    """
    # Demo: accept any credentials
    # In production: validate against database
    token = create_access_token(
        subject=request.username,
        permissions=["read", "write", "admin"] if request.username == "admin" else ["read"]
    )
    return TokenResponse(access_token=token)


@app.get("/auth/me", tags=["Authentication"])
async def get_me(user: User = Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": user.id,
        "username": user.username,
        "permissions": user.permissions
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PORTFOLIO ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/portfolio", tags=["Portfolio"])
async def get_portfolio(db=Depends(get_db)):
    """Get current portfolio state"""
    from sqlalchemy import select, func, text
    
    # Try to get from account_state first
    try:
        result = await db.execute(
            text("SELECT * FROM account_state WHERE account_id = 'paper_main'")
        )
        account = result.mappings().one_or_none()
        
        if account:
            balance = float(account['balance_usdt'])
            initial = float(account['initial_balance'])
            pnl = balance - initial
            total_trades = int(account.get('total_trades', 0))
            winning = int(account.get('winning_trades', 0))
            
            return {
                "total_equity": balance,
                "cash": balance,
                "positions_value": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl": float(account.get('realized_pnl', 0)),
                "daily_pnl": pnl,
                "daily_pnl_percent": (pnl / initial * 100) if initial > 0 else 0,
                "open_positions": 0,
                "var_95": None,
                "max_drawdown": float(account.get('max_drawdown', 0)),
                "win_rate": (winning / total_trades * 100) if total_trades > 0 else None,
                "total_fees": float(account.get('total_fees_paid', 0)),
                "total_slippage": float(account.get('total_slippage_cost', 0)),
                "total_trades": total_trades,
                "winning_trades": winning,
            }
    except Exception as e:
        logger.warning(f"Failed to get account_state: {e}")
    
    # Fallback: Get latest snapshot
    result = await db.execute(
        select(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.timestamp.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    
    if not snapshot:
        # Default to initial paper trading balance
        return {
            "total_equity": 108000.0,
            "cash": 108000.0,
            "positions_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "daily_pnl": 0.0,
            "daily_pnl_percent": 0.0,
            "open_positions": 0,
            "var_95": None,
            "max_drawdown": None,
            "win_rate": None
        }
    
    return snapshot.to_dict()


@app.get("/api/portfolio/history", tags=["Portfolio"])
async def get_portfolio_history(limit: int = 1000, db=Depends(get_db)):
    """Get portfolio history for equity curve"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(PortfolioSnapshot)
        .order_by(PortfolioSnapshot.timestamp.desc())
        .limit(limit)
    )
    snapshots = result.scalars().all()
    
    return [s.to_dict() for s in reversed(snapshots)]


# ═══════════════════════════════════════════════════════════════════════════════
# POSITIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/positions", tags=["Positions"])
async def get_positions(status: str = "open", db=Depends(get_db)):
    """Get positions by status"""
    from sqlalchemy import select
    
    query = select(Position)
    if status:
        query = query.where(Position.status == status)
    query = query.order_by(Position.opened_at.desc())
    
    result = await db.execute(query)
    positions = result.scalars().all()
    
    return [p.to_dict() for p in positions]


@app.get("/api/positions/{position_id}", tags=["Positions"])
async def get_position(position_id: str, db=Depends(get_db)):
    """Get specific position"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Position).where(Position.id == position_id)
    )
    position = result.scalar_one_or_none()
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    return position.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# TRADES ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/trades", tags=["Trades"])
async def get_trades(limit: int = 100, db=Depends(get_db)):
    """Get recent trades"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Trade)
        .order_by(Trade.created_at.desc())
        .limit(limit)
    )
    trades = result.scalars().all()
    
    return [t.to_dict() for t in trades]


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNALS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/signals", tags=["Signals"])
async def get_signals(limit: int = 100, db=Depends(get_db)):
    """Get recent signals"""
    from sqlalchemy import select
    
    result = await db.execute(
        select(Signal)
        .order_by(Signal.timestamp.desc())
        .limit(limit)
    )
    signals = result.scalars().all()
    
    return [s.to_dict() for s in signals]


@app.get("/api/signals/latest", tags=["Signals"])
async def get_latest_signals(db=Depends(get_db)):
    """Get latest signal for each coin - returns only real data from database"""
    from sqlalchemy import select, func, text
    
    try:
        result = await db.execute(
            text("""
                SELECT DISTINCT ON (coin) *
                FROM signals 
                ORDER BY coin, timestamp DESC
            """)
        )
        signals = result.mappings().all()
        
        if signals and len(signals) > 0:
            return {s['coin']: {
                'id': str(s.get('id', '')),
                'coin': s['coin'],
                'sentiment_score': float(s.get('sentiment_score', 0)),
                'narrative_strength': float(s.get('narrative_strength', 0)),
                'combined_score': float(s.get('combined_score', 0)),
                'filter_score_pass': s.get('filter_score_pass', True),
                'filter_volume_pass': s.get('filter_volume_pass', True),
                'recommended_action': s.get('recommended_action', 'none'),
                'timestamp': str(s.get('timestamp', '')),
            } for s in signals}
    except Exception as e:
        logger.warning(f"Failed to get signals from DB: {e}")
    
    # Return empty dict if no signals - never fake data
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# RISK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/risk/events", tags=["Risk"])
async def get_risk_events(
    severity: str = None,
    limit: int = 100,
    db=Depends(get_db)
):
    """Get risk events"""
    from sqlalchemy import select
    
    query = select(RiskEvent).order_by(RiskEvent.timestamp.desc())
    
    if severity:
        query = query.where(RiskEvent.severity == severity)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [e.to_dict() for e in events]


@app.post("/api/risk/acknowledge/{event_id}", tags=["Risk"])
async def acknowledge_risk_event(
    event_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db)
):
    """Acknowledge a risk event"""
    from sqlalchemy import select, update
    
    result = await db.execute(
        update(RiskEvent)
        .where(RiskEvent.id == event_id)
        .values(
            acknowledged=True,
            acknowledged_by=user.username,
            acknowledged_at=datetime.utcnow()
        )
        .returning(RiskEvent)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Risk event not found")
    
    return {"status": "acknowledged", "event_id": event_id}


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/audit", tags=["Audit"])
async def get_audit_log(
    event_type: str = None,
    entity_type: str = None,
    entity_id: str = None,
    limit: int = 100,
    db=Depends(get_db)
):
    """Get audit log entries"""
    from sqlalchemy import select
    
    query = select(AuditLog).order_by(AuditLog.timestamp.desc())
    
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    
    query = query.limit(limit)
    
    result = await db.execute(query)
    entries = result.scalars().all()
    
    return [{
        "id": e.id,
        "timestamp": e.timestamp.isoformat(),
        "event_type": e.event_type,
        "actor": e.actor,
        "action": e.action,
        "entity_type": e.entity_type,
        "entity_id": e.entity_id,
        "reasoning": e.reasoning,
        "hash": e.hash
    } for e in entries]


@app.get("/api/audit/verify", tags=["Audit"])
async def verify_audit_chain(limit: int = 1000, db=Depends(get_db)):
    """Verify audit log integrity"""
    result = await AuditLog.verify_chain(db, limit)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING DECISIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/decisions", tags=["Decisions"])
async def get_trading_decisions(limit: int = 24, db=Depends(get_db)):
    """Get recent trading decisions with filter reasons"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT 
                    id, timestamp, batch_id, selected_coin, selected_score,
                    decision, filter_reason, position_size, entry_price,
                    stop_loss, take_profit, atr_value, equity_before,
                    risk_amount, all_scores, executed
                FROM trading_decisions
                ORDER BY timestamp DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        decisions = result.mappings().all()
        
        return [{
            'id': str(d['id']),
            'timestamp': str(d['timestamp']),
            'batch_id': d['batch_id'],
            'selected_coin': d['selected_coin'],
            'selected_score': float(d['selected_score']) if d['selected_score'] else None,
            'decision': d['decision'],
            'filter_reason': d['filter_reason'],
            'position_size': float(d['position_size']) if d['position_size'] else None,
            'entry_price': float(d['entry_price']) if d['entry_price'] else None,
            'stop_loss': float(d['stop_loss']) if d['stop_loss'] else None,
            'take_profit': float(d['take_profit']) if d['take_profit'] else None,
            'equity_before': float(d['equity_before']) if d['equity_before'] else None,
            'risk_amount': float(d['risk_amount']) if d['risk_amount'] else None,
            'all_scores': d['all_scores'],
            'executed': d['executed'],
        } for d in decisions]
    except Exception as e:
        logger.warning(f"Failed to get trading decisions: {e}")
        return []


@app.get("/api/decisions/stats", tags=["Decisions"])
async def get_decision_stats(db=Depends(get_db)):
    """Get filter statistics for today"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_decisions,
                    COUNT(*) FILTER (WHERE decision = 'long') as long_decisions,
                    COUNT(*) FILTER (WHERE decision = 'short') as short_decisions,
                    COUNT(*) FILTER (WHERE decision = 'flat') as flat_decisions,
                    COUNT(*) FILTER (WHERE decision = 'filtered') as filtered_decisions,
                    COUNT(*) FILTER (WHERE filter_reason LIKE '%score%') as score_filtered,
                    COUNT(*) FILTER (WHERE filter_reason LIKE '%volume%') as volume_filtered,
                    COUNT(*) FILTER (WHERE executed = true) as executed_count
                FROM trading_decisions
                WHERE timestamp >= CURRENT_DATE
            """)
        )
        stats = result.mappings().one_or_none()
        
        if stats:
            return {
                'total_decisions': int(stats['total_decisions']),
                'long_decisions': int(stats['long_decisions']),
                'short_decisions': int(stats['short_decisions']),
                'flat_decisions': int(stats['flat_decisions']),
                'filtered_decisions': int(stats['filtered_decisions']),
                'score_filtered': int(stats['score_filtered']),
                'volume_filtered': int(stats['volume_filtered']),
                'executed_count': int(stats['executed_count']),
            }
    except Exception as e:
        logger.warning(f"Failed to get decision stats: {e}")
    
    return {
        'total_decisions': 0,
        'long_decisions': 0,
        'short_decisions': 0,
        'flat_decisions': 0,
        'filtered_decisions': 0,
        'score_filtered': 0,
        'volume_filtered': 0,
        'executed_count': 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/system/status", tags=["System"])
async def get_system_status():
    """Get overall system status"""
    bus = get_event_bus()
    
    # Get stream info
    streams_info = {}
    for stream_key in ["signals", "risk", "orders", "positions"]:
        streams_info[stream_key] = await bus.get_stream_info(stream_key)
    
    return {
        "mode": os.getenv("MODE", "paper"),
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_connections": sum(len(c) for c in manager.active_connections.values()),
        "event_streams": streams_info
    }


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str = "all"):
    """
    WebSocket endpoint for real-time updates.
    
    Channels:
    - all: All events
    - signals: Signal events only
    - trading: Position and order events
    - risk: Risk events only
    """
    await manager.connect(websocket, channel)
    
    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle ping/pong
                if data == "ping":
                    await websocket.send_text("pong")
                
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    except WebSocketDisconnect:
        await manager.disconnect(websocket, channel)
        logger.info(f"WebSocket disconnected from channel: {channel}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
