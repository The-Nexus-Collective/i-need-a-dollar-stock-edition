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
from typing import Dict, List, Optional, Set
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

# Install health tracking logging handler to capture all errors/warnings
from core.health_tracker import install_health_logging, get_health_tracker
install_health_logging()


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
    """Forward events to WebSocket clients (works with in-memory bus)"""
    bus = get_event_bus()
    await bus.connect()
    
    async def handle_event(channel: str, event: BaseEvent):
        await manager.broadcast_event(event)
    
    try:
        # Subscribe to all real-time channels
        await bus.subscribe_realtime(
            ["signals", "risk", "orders", "positions", "portfolio", "system"],
            handle_event
        )
    except asyncio.CancelledError:
        logger.info("Event forwarder stopped")
    except Exception as e:
        logger.warning(f"Event forwarder error (non-critical): {e}")


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

# CORS middleware - allow configurable origins for production
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
DEFAULT_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8501"]
ALL_ORIGINS = CORS_ORIGINS + DEFAULT_ORIGINS

# If CORS_ALLOW_ALL is set, allow all origins (useful for development/testing)
allow_all_origins = os.getenv("CORS_ALLOW_ALL", "false").lower() == "true"

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all_origins else ALL_ORIGINS,
    allow_credentials=not allow_all_origins,  # Can't use credentials with wildcard
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include realtime WebSocket router
from .realtime import router as realtime_router
app.include_router(realtime_router, prefix="/ws", tags=["WebSocket"])

# Include swarm WebSocket router
from .swarm_ws import router as swarm_router
app.include_router(swarm_router, prefix="/ws", tags=["Swarm"])


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
    var_95: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None


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


@app.get("/api/debug/prices", tags=["Debug"])
async def debug_prices():
    """Debug endpoint to check WebSocket prices."""
    from integrations.binance_ws import get_binance_ws
    ws = get_binance_ws()
    prices = ws.get_all_prices()
    return {
        "count": len(prices),
        "prices": prices
    }


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
    """
    Get current portfolio state.
    
    Uses the in-memory executor as the source of truth for live trading data.
    This ensures consistency with the dashboard and equity tracker.
    """
    from trading_state import get_trading_loop
    from trader.equity_tracker import get_equity_tracker
    
    INITIAL_CAPITAL = 100000.0
    
    try:
        # Get live data from executor (single source of truth)
        loop = get_trading_loop()
        if loop and loop.executor:
            executor = loop.executor
            
            # Get equity snapshot for unrealized PnL
            tracker = get_equity_tracker()
            equity_snapshot = tracker.get_latest()
            
            # Calculate values from executor state
            capital = executor.capital
            starting_capital = executor.starting_capital
            open_positions = len(executor.positions)
            total_cycles = len(executor.cycles)
            
            # Calculate positions value and unrealized PnL
            positions_value = sum(p.size_usdt for p in executor.positions.values())
            unrealized_pnl = equity_snapshot.unrealized_pnl if equity_snapshot else 0.0
            total_equity = equity_snapshot.total_equity if equity_snapshot else capital
            
            # Get trading costs from executor
            total_fees = executor.total_fees_paid
            total_spread = executor.total_spread_cost
            total_slippage = executor.total_slippage_cost
            total_trading_costs = total_fees + total_spread + total_slippage
            
            # Calculate realized PnL from closed positions
            realized_pnl = sum(p.pnl or 0 for p in executor.closed_positions)
            
            # Calculate win rate from closed positions
            winning_trades = sum(1 for p in executor.closed_positions if (p.pnl or 0) > 0)
            total_trades = len(executor.closed_positions)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0.0
            
            # Total PnL = realized + unrealized
            total_pnl = realized_pnl + unrealized_pnl
            pnl_percent = (total_pnl / starting_capital * 100) if starting_capital > 0 else 0.0
            
            return {
                "total_equity": total_equity,
                "initial_capital": starting_capital,
                "cash": capital,
                "positions_value": positions_value,
                "unrealized_pnl": unrealized_pnl,
                "realized_pnl": realized_pnl,
                "total_pnl": total_pnl,
                "pnl_percent": pnl_percent,
                "open_positions": open_positions,
                "total_trades": total_trades,
                "winning_trades": winning_trades,
                "losing_trades": total_trades - winning_trades,
                "win_rate": win_rate,
                "total_volume": sum(p.size_usdt for p in executor.closed_positions),
                "total_fees": total_fees,
                "total_spread": total_spread,
                "total_slippage": total_slippage,
                "total_trading_costs": total_trading_costs,
                "var_95": None,
                "max_drawdown": 0.0,
            }
        
        # Fallback to defaults if no executor
        return {
            "total_equity": INITIAL_CAPITAL,
            "initial_capital": INITIAL_CAPITAL,
            "cash": INITIAL_CAPITAL,
            "positions_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_pnl": 0.0,
            "pnl_percent": 0.0,
            "open_positions": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_volume": 0.0,
            "total_fees": 0.0,
            "total_spread": 0.0,
            "total_slippage": 0.0,
            "total_trading_costs": 0.0,
            "var_95": None,
            "max_drawdown": 0.0,
        }
            
    except Exception as e:
        logger.error(f"Failed to calculate portfolio stats: {e}")
        
        # Return defaults on error
        return {
            "total_equity": INITIAL_CAPITAL,
            "initial_capital": INITIAL_CAPITAL,
            "cash": INITIAL_CAPITAL,
            "positions_value": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_pnl": 0.0,
            "pnl_percent": 0.0,
            "open_positions": 0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0.0,
            "total_volume": 0.0,
            "total_fees": 0.0,
            "total_spread": 0.0,
            "total_slippage": 0.0,
            "total_trading_costs": 0.0,
            "var_95": None,
            "max_drawdown": 0.0,
        }


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
    """
    Get positions by status.
    
    For 'open' positions: Uses in-memory executor state (single source of truth)
    For 'closed' positions: Could query database for historical data
    """
    from trading_state import get_trading_loop
    from integrations.binance_ws import get_binance_ws
    
    try:
        # For open positions, use executor's in-memory state
        if status.lower() == "open":
            loop = get_trading_loop()
            if loop and loop.executor:
                ws = get_binance_ws()
                prices = ws.get_all_prices()
                
                # Debug: log available prices
                logger.debug(f"Available prices: {list(prices.keys())}")
                
                positions = []
                for symbol, pos in loop.executor.positions.items():
                    # Symbol in executor might be "BTCUSDT" or just stored differently
                    current_price = prices.get(symbol)
                    if current_price is None:
                        # Try without USDT suffix
                        base_symbol = symbol.replace("USDT", "")
                        current_price = prices.get(f"{base_symbol}USDT")
                    
                    # Validate price is plausible (within 50% of entry price)
                    # This catches cases where WebSocket returns wrong price (e.g., different contract)
                    if current_price is not None:
                        price_ratio = current_price / pos.entry_price if pos.entry_price > 0 else 1
                        if price_ratio < 0.5 or price_ratio > 2.0:
                            logger.warning(
                                f"Price for {symbol} looks wrong: current=${current_price:.4f}, "
                                f"entry=${pos.entry_price:.4f}, ratio={price_ratio:.2f}. Using entry price."
                            )
                            current_price = pos.entry_price
                    
                    if current_price is None:
                        # Fallback to entry price
                        current_price = pos.entry_price
                        logger.warning(f"No price found for {symbol}, using entry price")
                    
                    # Calculate unrealized PnL
                    if pos.direction == "LONG":
                        pnl_pct = (current_price - pos.entry_price) / pos.entry_price
                    else:
                        pnl_pct = (pos.entry_price - current_price) / pos.entry_price
                    pnl_pct *= pos.leverage
                    unrealized_pnl = pos.size_usdt * pnl_pct
                    
                    positions.append({
                        'id': pos.position_id,
                        'symbol': symbol,
                        'direction': pos.direction,
                        'entry_price': pos.entry_price,
                        'current_price': current_price,
                        'quantity': pos.quantity,
                        'size_usdt': pos.size_usdt,
                        'leverage': pos.leverage,
                        'stop_loss_price': None,
                        'take_profit_price': None,
                        'status': 'OPEN',
                        'entry_time': pos.opened_at.isoformat() if pos.opened_at else None,
                        'exit_time': None,
                        'exit_price': None,
                        'realized_pnl': 0,
                        'unrealized_pnl': unrealized_pnl,
                        'pnl_percent': pnl_pct * 100,
                        'conviction': pos.conviction,
                        'reasoning': '',
                    })
                return positions
            return []
        
        # For closed positions, use executor's closed_positions list
        loop = get_trading_loop()
        if loop and loop.executor:
            return [{
                'id': pos.position_id,
                'symbol': pos.symbol,
                'direction': pos.direction,
                'entry_price': pos.entry_price,
                'exit_price': pos.exit_price,
                'quantity': pos.quantity,
                'size_usdt': pos.size_usdt,
                'leverage': pos.leverage,
                'status': 'CLOSED',
                'entry_time': pos.opened_at.isoformat() if pos.opened_at else None,
                'exit_time': pos.closed_at.isoformat() if pos.closed_at else None,
                'realized_pnl': pos.pnl or 0,
                'conviction': pos.conviction,
                'reasoning': '',
            } for pos in loop.executor.closed_positions[-50:]]
        return []
        
    except Exception as e:
        logger.warning(f"Failed to get positions: {e}")
        return []


@app.get("/api/positions/{position_id}", tags=["Positions"])
async def get_position(position_id: str, db=Depends(get_db)):
    """Get specific position from paper_positions"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT * FROM paper_positions WHERE id = :id
            """),
            {"id": position_id}
        )
        position = result.mappings().one_or_none()
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        return dict(position)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Failed to get position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# TRADES ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/trades", tags=["Trades"])
async def get_trades(limit: int = 100, db=Depends(get_db)):
    """Get recent trades from paper_trades"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT id, position_id, symbol, direction, entry_price, exit_price,
                       quantity, size_usdt, leverage, pnl_usdt, pnl_percent,
                       entry_time, exit_time, duration_seconds, exit_reason,
                       conviction, reasoning, created_at
                FROM paper_trades
                ORDER BY exit_time DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        trades = result.mappings().all()
        
        return [{
            'id': t['id'],
            'position_id': t['position_id'],
            'symbol': t['symbol'],
            'direction': t['direction'],
            'entry_price': float(t['entry_price']),
            'exit_price': float(t['exit_price']),
            'quantity': float(t['quantity']),
            'size_usdt': float(t['size_usdt']),
            'leverage': t['leverage'],
            'pnl_usdt': float(t['pnl_usdt']),
            'pnl_percent': float(t['pnl_percent']),
            'entry_time': str(t['entry_time']),
            'exit_time': str(t['exit_time']),
            'duration_seconds': t['duration_seconds'],
            'exit_reason': t['exit_reason'],
            'conviction': float(t['conviction']) if t['conviction'] else 0,
            'reasoning': t['reasoning'],
            'created_at': str(t['created_at']),
        } for t in trades]
    except Exception as e:
        logger.warning(f"Failed to get trades: {e}")
        return []


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


@app.get("/api/risk/margin-health", tags=["Risk"])
async def get_margin_health(db=Depends(get_db)):
    """
    Get margin health status for all open positions.
    
    Returns overall margin health and per-position liquidation risk.
    Uses the in-memory executor state as single source of truth.
    """
    from trading_state import get_trading_loop
    from integrations.binance_ws import get_binance_ws
    from core.account import AccountPosition, check_simulated_liquidation
    
    try:
        trading_loop = get_trading_loop()
        executor = trading_loop.executor if trading_loop else None
        
        if not executor or not executor.positions:
            return {
                "overall_status": "safe",
                "summary": {
                    "total_positions": 0,
                    "positions_safe": 0,
                    "positions_warning": 0,
                    "positions_danger": 0,
                    "total_margin_used": 0,
                    "margin_utilization_pct": 0,
                },
                "positions": []
            }
        
        # Get current prices from WebSocket
        binance_ws = get_binance_ws()
        
        positions_data = []
        positions_safe = 0
        positions_warning = 0
        positions_danger = 0
        total_margin_used = 0
        closest_to_liq = float('inf')
        
        for symbol, pos in executor.positions.items():
            coin = symbol.replace("USDT", "")
            
            # Get current price from WebSocket
            current_price = binance_ws.get_price(symbol) if binance_ws else pos.entry_price
            if not current_price:
                current_price = pos.entry_price
            
            # Create AccountPosition for liquidation check
            account_pos = AccountPosition(
                coin=coin,
                side="long" if pos.direction == "LONG" else "short",
                quantity=pos.quantity,
                entry_price=pos.entry_price,
                current_price=current_price,
                leverage=pos.leverage,
                position_id=pos.position_id
            )
            
            # Check liquidation distance
            would_liq, price_change, distance = check_simulated_liquidation(account_pos, current_price)
            
            # Determine status based on distance to liquidation
            distance_pct = distance * 100
            if would_liq:
                status = "liquidated"
                positions_danger += 1
            elif distance < 0.05:  # Within 5% of liquidation
                status = "danger"
                positions_danger += 1
            elif distance < 0.10:  # Within 10% of liquidation
                status = "warning"
                positions_warning += 1
            else:
                status = "safe"
                positions_safe += 1
            
            # Track closest to liquidation
            if distance_pct < closest_to_liq:
                closest_to_liq = distance_pct
            
            # Calculate margin for this position
            margin = pos.size_usdt / pos.leverage if pos.leverage > 0 else pos.size_usdt
            total_margin_used += margin
            
            positions_data.append({
                "coin": coin,
                "side": pos.direction.lower(),
                "leverage": pos.leverage,
                "entry_price": pos.entry_price,
                "current_price": current_price,
                "liquidation_price": account_pos.liquidation_price,
                "distance_to_liq_pct": round(distance_pct, 2),
                "price_change_pct": round(price_change * 100, 2),
                "margin_used": round(margin, 2),
                "status": status
            })
        
        # Determine overall status
        if positions_danger > 0:
            overall_status = "danger" if positions_danger == 1 else "critical"
        elif positions_warning > 0:
            overall_status = "warning"
        else:
            overall_status = "safe"
        
        # Calculate margin utilization
        total_capital = executor.capital
        margin_utilization = (total_margin_used / total_capital * 100) if total_capital > 0 else 0
        
        return {
            "overall_status": overall_status,
            "summary": {
                "total_positions": len(positions_data),
                "positions_safe": positions_safe,
                "positions_warning": positions_warning,
                "positions_danger": positions_danger,
                "total_margin_used": round(total_margin_used, 2),
                "margin_utilization_pct": round(margin_utilization, 2),
                "closest_to_liq_pct": round(closest_to_liq, 2) if closest_to_liq != float('inf') else None,
            },
            "positions": sorted(positions_data, key=lambda x: x["distance_to_liq_pct"])
        }
        
    except Exception as e:
        logger.error(f"Error getting margin health: {e}")
        return {
            "overall_status": "safe",
            "summary": {
                "total_positions": 0,
                "positions_safe": 0,
                "positions_warning": 0,
                "positions_danger": 0,
                "total_margin_used": 0,
                "margin_utilization_pct": 0,
            },
            "positions": [],
            "error": str(e)
        }


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
    """Get recent trading decisions from Tactician"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT 
                    id, created_at, decision, coin, direction,
                    size_percent, stop_loss_percent, take_profit_percent,
                    conviction, reasoning, available_capital,
                    open_positions_count, was_executed, position_id
                FROM trading_decisions
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit}
        )
        decisions = result.mappings().all()
        
        return [{
            'id': str(d['id']),
            'timestamp': str(d['created_at']),
            'decision': d['decision'],
            'coin': d['coin'],
            'direction': d['direction'],
            'size_percent': float(d['size_percent']) if d['size_percent'] else None,
            'stop_loss_percent': float(d['stop_loss_percent']) if d['stop_loss_percent'] else None,
            'take_profit_percent': float(d['take_profit_percent']) if d['take_profit_percent'] else None,
            'conviction': int(d['conviction']) if d['conviction'] else 0,
            'reasoning': d['reasoning'],
            'available_capital': float(d['available_capital']) if d['available_capital'] else 0,
            'open_positions': int(d['open_positions_count']) if d['open_positions_count'] else 0,
            'executed': d['was_executed'] or False,
            'position_id': d['position_id'],
        } for d in decisions]
    except Exception as e:
        logger.warning(f"Failed to get trading decisions: {e}")
        return []


@app.get("/api/decisions/stats", tags=["Decisions"])
async def get_decision_stats(db=Depends(get_db)):
    """Get decision statistics for today"""
    from sqlalchemy import text
    
    try:
        result = await db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_decisions,
                    COUNT(*) FILTER (WHERE decision = 'TRADE') as trade_decisions,
                    COUNT(*) FILTER (WHERE decision = 'WAIT') as wait_decisions,
                    COUNT(*) FILTER (WHERE decision = 'PASS') as pass_decisions,
                    COUNT(*) FILTER (WHERE was_executed = true) as executed_count,
                    COALESCE(AVG(conviction), 0) as avg_conviction
                FROM trading_decisions
                WHERE created_at >= CURRENT_DATE
            """)
        )
        stats = result.mappings().one_or_none()
        
        if stats:
            return {
                'total_decisions': int(stats['total_decisions']),
                'trade_decisions': int(stats['trade_decisions']),
                'wait_decisions': int(stats['wait_decisions']),
                'pass_decisions': int(stats['pass_decisions']),
                'executed_count': int(stats['executed_count']),
                'avg_conviction': round(float(stats['avg_conviction']), 1),
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
# AGGRESSIVE MODE: VELOCITY METRICS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/velocity", tags=["Velocity"])
async def get_velocity_metrics(db=Depends(get_db)):
    """
    Get trading velocity and deployment metrics for aggressive mode.
    
    Returns:
        - trades_last_hour: Trades in last hour
        - trades_today: Trades today
        - trades_24h: Trades in last 24 hours
        - rebalances_today: Rebalance trades today
        - avg_trades_per_hour: Average trades per hour (24h)
        - velocity_status: ON_TARGET (100+), MODERATE (50+), BELOW_TARGET
        - deployment_percent: Current portfolio deployment
        - positions_count: Open positions count
        - target_deployment: Target deployment (0.80)
        - deployment_status: ON_TARGET, MODERATE, LOW
        - force_trade_enabled: Whether FORCE_TRADE env is set
    """
    from sqlalchemy import text
    
    try:
        # Get trade velocity from database
        velocity_query = text("""
            SELECT 
                COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '1 hour') as trades_last_hour,
                COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE) as trades_today,
                COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '24 hours') as trades_24h,
                COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE AND is_rebalance = TRUE) as rebalances_today,
                ROUND(COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '24 hours')::NUMERIC / 24, 1) as avg_trades_per_hour
            FROM trades
            WHERE is_paper = TRUE
        """)
        result = await db.execute(velocity_query)
        row = result.fetchone()
        
        trades_today = row.trades_today if row else 0
        trades_last_hour = row.trades_last_hour if row else 0
        trades_24h = row.trades_24h if row else 0
        rebalances_today = row.rebalances_today if row else 0
        avg_trades_per_hour = float(row.avg_trades_per_hour) if row and row.avg_trades_per_hour else 0
        
        # Velocity status
        if trades_today >= 100:
            velocity_status = 'ON_TARGET'
        elif trades_today >= 50:
            velocity_status = 'MODERATE'
        else:
            velocity_status = 'BELOW_TARGET'
        
        # Get deployment from latest snapshot
        snapshot_query = text("""
            SELECT 
                COALESCE(deployment_percent, 0) as deployment_percent,
                COALESCE(positions_count, 0) as positions_count
            FROM portfolio_snapshots
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        snap_result = await db.execute(snapshot_query)
        snap_row = snap_result.fetchone()
        
        deployment_percent = float(snap_row.deployment_percent) if snap_row and snap_row.deployment_percent else 0
        positions_count = snap_row.positions_count if snap_row else 0
        
        # Deployment status
        if deployment_percent >= 0.80:
            deployment_status = 'ON_TARGET'
        elif deployment_percent >= 0.60:
            deployment_status = 'MODERATE'
        else:
            deployment_status = 'LOW'
        
        # Check FORCE_TRADE env
        force_trade_enabled = os.getenv('FORCE_TRADE', 'false').lower() == 'true'
        
        return {
            'trades_last_hour': trades_last_hour,
            'trades_today': trades_today,
            'trades_24h': trades_24h,
            'rebalances_today': rebalances_today,
            'avg_trades_per_hour': avg_trades_per_hour,
            'velocity_status': velocity_status,
            'deployment_percent': deployment_percent,
            'positions_count': positions_count,
            'target_deployment': 0.80,
            'deployment_status': deployment_status,
            'force_trade_enabled': force_trade_enabled,
        }
        
    except Exception as e:
        logger.warning(f"Failed to get velocity metrics: {e}")
        return {
            'trades_last_hour': 0,
            'trades_today': 0,
            'trades_24h': 0,
            'rebalances_today': 0,
            'avg_trades_per_hour': 0,
            'velocity_status': 'BELOW_TARGET',
            'deployment_percent': 0,
            'positions_count': 0,
            'target_deployment': 0.80,
            'deployment_status': 'LOW',
            'force_trade_enabled': False,
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
    
    # Get volatility regime info
    try:
        from core.filters import get_current_regime_info
        regime_info = get_current_regime_info()
    except Exception:
        regime_info = {
            "regime": "unknown",
            "regime_display": "Unknown",
            "threshold": 67,
            "btc_atr_percent": 0
        }
    
    return {
        "mode": os.getenv("MODE", "paper"),
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
        "websocket_connections": sum(len(c) for c in manager.active_connections.values()),
        "event_streams": streams_info,
        "volatility_regime": regime_info
    }


@app.get("/api/system/regime", tags=["System"])
async def get_volatility_regime():
    """
    Get current volatility regime and dynamic score threshold.
    
    Returns:
        - regime: Current regime (high_vol, normal, low_vol)
        - regime_display: Human-readable regime name
        - threshold: Current score threshold
        - btc_atr_percent: BTC ATR as percentage of price
        - thresholds: All threshold values by regime
    """
    try:
        from core.filters import get_current_regime_info
        return get_current_regime_info()
    except Exception as e:
        return {
            "regime": "unknown",
            "regime_display": "Unknown",
            "threshold": 67,
            "btc_atr_percent": 0,
            "error": str(e)
        }


@app.get("/api/system/health", tags=["System"])
async def get_system_health(db=Depends(get_db)):
    """
    Get comprehensive system health status including service connectivity
    and recent logged errors.
    
    Returns:
        - overall: "healthy", "degraded", or "unhealthy"
        - services: Status of each service (database, redis, grok)
        - error_count: Total errors since startup
        - warning_count: Total warnings since startup
        - recent_errors: List of recent error/warning log entries
        - last_check: Timestamp of this health check
    """
    import time
    from sqlalchemy import text
    
    tracker = get_health_tracker()
    
    # Check database connectivity
    try:
        start = time.time()
        await db.execute(text("SELECT 1"))
        latency = (time.time() - start) * 1000
        tracker.update_service("database", "healthy", latency_ms=round(latency, 1))
    except Exception as e:
        tracker.update_service("database", "unhealthy", error=str(e))
    
    # Check Event Bus (in-memory, always healthy if connected)
    try:
        bus = get_event_bus()
        if bus._connected:
            tracker.update_service("event_bus", "healthy", latency_ms=0.1)
        else:
            tracker.update_service("event_bus", "healthy", latency_ms=0.1)  # In-memory is always available
    except Exception as e:
        tracker.update_service("event_bus", "degraded", error=str(e))
    
    # Check Grok API key presence
    try:
        grok_key = os.getenv("XAI_API_KEY", "")
        if grok_key and len(grok_key) > 10:
            tracker.update_service("grok", "healthy")
        else:
            tracker.update_service("grok", "unhealthy", error="XAI_API_KEY not configured")
    except Exception as e:
        tracker.update_service("grok", "unhealthy", error=str(e))
    
    # Check Binance WebSocket status (via price cache if available)
    try:
        from core.price_cache import get_price_cache
        cache = get_price_cache()
        if cache and cache.get_all_prices():
            tracker.update_service("binance", "healthy")
        else:
            tracker.update_service("binance", "unknown", error="No price data available")
    except Exception as e:
        tracker.update_service("binance", "unknown", error=str(e))
    
    # Generate and return health report
    report = tracker.get_health_report(error_limit=30)
    return report.to_dict()


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK TRADING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/stocks/market-status", tags=["Stocks"])
async def get_market_status():
    """
    Get current US stock market status.
    
    Returns:
        - is_open: Whether market is currently open
        - status_text: Human-readable status
        - next_event: Time until next open/close
        - should_flatten: Whether positions should be closed
    """
    try:
        from core.market_hours import get_market_hours_manager
        manager = get_market_hours_manager()
        status = manager.get_status()
        return status.to_dict()
    except Exception as e:
        return {
            "is_open": False,
            "status_text": "Unknown",
            "error": str(e)
        }


@app.get("/api/stocks/regime", tags=["Stocks"])
async def get_stock_regime():
    """
    Get current stock market regime based on VIX.
    
    Returns:
        - vix_value: Current VIX level
        - regime: low_vol, normal, high_vol, or crisis
        - score_threshold: Dynamic threshold for this regime
        - should_trade: Whether to trade in current regime
    """
    try:
        from core.stock_regime import get_stock_regime_detector
        detector = get_stock_regime_detector()
        regime = await detector.get_regime()
        return regime.to_dict()
    except Exception as e:
        return {
            "vix_value": 20.0,
            "regime": "normal",
            "score_threshold": 70,
            "should_trade": True,
            "error": str(e)
        }


@app.get("/api/stocks/unified-regime", tags=["Stocks"])
async def get_unified_regime():
    """
    Get unified regime info across both crypto and stocks.
    
    Returns:
        - crypto: BTC ATR-based regime
        - stock: VIX-based regime
    """
    try:
        from core.filters import get_current_regime_info
        from core.stock_regime import get_stock_regime_detector
        
        crypto_regime = get_current_regime_info()
        
        stock_detector = get_stock_regime_detector()
        stock_regime = await stock_detector.get_regime()
        
        return {
            "crypto": crypto_regime,
            "stock": stock_regime.to_dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/stocks/portfolio", tags=["Stocks"])
async def get_multi_portfolio():
    """
    Get portfolio summary across all asset types.
    
    Returns:
        - crypto: Crypto portfolio (100k USDT)
        - stock: Stock portfolio (100k USD)
        - total: Combined USD value
    """
    try:
        from core.multi_account import get_multi_account_manager
        manager = get_multi_account_manager()
        
        # Ensure initialized
        if not manager._initialized:
            await manager.initialize()
        
        summary = await manager.get_portfolio_summary()
        return summary.to_dict()
    except Exception as e:
        return {
            "crypto": {"equity": 100000, "currency": "USDT"},
            "stock": {"equity": 100000, "currency": "USD"},
            "error": str(e)
        }


@app.get("/api/stocks/hype", tags=["Stocks"])
async def get_stock_hype(symbols: str = "PLTR,RTX,LMT"):
    """
    Get X hype scores for specified stocks.
    
    Args:
        symbols: Comma-separated stock symbols
    
    Returns:
        - Dict of symbol -> hype score
    """
    try:
        from integrations.x_client import get_x_hype_detector
        detector = get_x_hype_detector()
        
        symbol_list = [s.strip().upper() for s in symbols.split(",")]
        scores = await detector.get_hype_scores(symbol_list)
        
        return {
            symbol: score.to_dict() 
            for symbol, score in scores.items()
        }
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION TRADER ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/trader/status", tags=["Trader"])
async def get_trader_status():
    """Get current trading loop status."""
    try:
        from trading_state import get_trading_loop
        loop = get_trading_loop()
        if not loop:
            raise HTTPException(status_code=503, detail="Trading loop not initialized")
        return loop.get_status()
    except Exception as e:
        logger.warning(f"Failed to get trader status: {e}")
        return {
            "running": False,
            "cycle_count": 0,
            "error": str(e),
        }


@app.get("/api/trader/predictions", tags=["Trader"])
async def get_recent_predictions(limit: int = 100, db=Depends(get_db)):
    """Get recent predictions from all cycles."""
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT 
                p.id, p.cycle_id, p.coin, p.direction, p.conviction,
                p.leverage, p.reason, p.created_at,
                c.cycle_number, c.total_pnl
            FROM predictions p
            LEFT JOIN prediction_cycles c ON p.cycle_id = c.id
            ORDER BY p.created_at DESC
            LIMIT :limit
        """), {"limit": limit})
        
        rows = result.mappings().all()
        return [{
            'id': str(r['id']),
            'cycle_id': str(r['cycle_id']),
            'cycle_number': r['cycle_number'],
            'coin': r['coin'],
            'direction': r['direction'],
            'conviction': r['conviction'],
            'leverage': float(r['leverage']),
            'reason': r['reason'],
            'created_at': str(r['created_at']),
        } for r in rows]
    except Exception as e:
        logger.warning(f"Failed to get predictions: {e}")
        return []


@app.get("/api/trader/cycles", tags=["Trader"])
async def get_prediction_cycles(limit: int = 50, db=Depends(get_db)):
    """Get recent prediction cycles with summary."""
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT 
                c.id, c.cycle_number, c.started_at, c.completed_at,
                c.capital_before, c.capital_after, c.total_pnl,
                c.coins_traded, c.status,
                COUNT(p.id) as prediction_count,
                AVG(p.conviction) as avg_conviction
            FROM prediction_cycles c
            LEFT JOIN predictions p ON c.id = p.cycle_id
            GROUP BY c.id
            ORDER BY c.started_at DESC
            LIMIT :limit
        """), {"limit": limit})
        
        rows = result.mappings().all()
        return [{
            'id': str(r['id']),
            'cycle_number': r['cycle_number'],
            'started_at': str(r['started_at']),
            'completed_at': str(r['completed_at']) if r['completed_at'] else None,
            'capital_before': float(r['capital_before']) if r['capital_before'] else 0,
            'capital_after': float(r['capital_after']) if r['capital_after'] else 0,
            'total_pnl': float(r['total_pnl']) if r['total_pnl'] else 0,
            'coins_traded': r['coins_traded'] or [],
            'status': r['status'],
            'prediction_count': r['prediction_count'],
            'avg_conviction': float(r['avg_conviction']) if r['avg_conviction'] else 0,
        } for r in rows]
    except Exception as e:
        logger.warning(f"Failed to get prediction cycles: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# AGENTIC SYSTEM ENDPOINTS (Legacy)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/agents/logs", tags=["Agents"])
async def get_agent_logs(
    limit: int = 100,
    agent_name: str = None,
    action_type: str = None,
    cycle_id: str = None,
    db=Depends(get_db)
):
    """
    Get agent log entries for debugging and transparency.
    
    Args:
        limit: Maximum entries to return
        agent_name: Filter by agent (discovery, validation, sentiment, etc.)
        action_type: Filter by action (think, act, decide, error)
        cycle_id: Filter by specific cycle
    """
    from sqlalchemy import text
    
    try:
        query = """
            SELECT 
                id, timestamp, cycle_id, agent_name, action_type,
                input_context, reasoning, decision, output_data,
                confidence, duration_ms, tokens_used, triggered_by
            FROM agent_logs
            WHERE 1=1
        """
        params = {}
        
        if agent_name:
            query += " AND agent_name = :agent_name"
            params["agent_name"] = agent_name
        
        if action_type:
            query += " AND action_type = :action_type"
            params["action_type"] = action_type
        
        if cycle_id:
            query += " AND cycle_id = :cycle_id"
            params["cycle_id"] = cycle_id
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        # Import personas for agent info
        from agents.personas import get_persona
        
        logs = []
        for row in rows:
            persona = get_persona(row.agent_name)
            
            # Build narrative message
            narrative = f"{persona.emoji} **{persona.name}** "
            if row.action_type == "think":
                narrative += "💭 *thinking...* "
            elif row.action_type == "act":
                narrative += "⚡ *acting* "
            elif row.action_type == "decide":
                narrative += "✅ *decided* "
            elif row.action_type == "dispatch":
                narrative += "📤 *dispatching* "
            elif row.action_type == "cycle_start":
                narrative += "🔄 *starting cycle* "
            elif row.action_type == "cycle_complete":
                narrative += "✨ *cycle complete* "
            elif row.action_type == "startup":
                narrative += "🚀 *starting up* "
            elif row.action_type == "error":
                narrative += "❌ *error* "
            
            narrative += f"\n\n{row.reasoning or ''}"
            
            if row.decision:
                narrative += f"\n\n→ **{row.decision}**"
            
            logs.append({
                "id": str(row.id),
                "timestamp": row.timestamp.isoformat(),
                "cycle_id": str(row.cycle_id),
                "agent_name": row.agent_name,
                "action_type": row.action_type,
                "reasoning": row.reasoning,
                "decision": row.decision,
                "confidence": float(row.confidence) if row.confidence else None,
                "duration_ms": row.duration_ms,
                "tokens_used": row.tokens_used,
                "persona": {
                    "name": persona.name,
                    "emoji": persona.emoji,
                    "role": persona.role,
                    "personality": persona.personality,
                },
                "narrative": narrative,
            })
        
        return logs
    except Exception as e:
        logger.warning(f"Failed to get agent logs: {e}")
        return []


@app.get("/api/agents/cycles", tags=["Agents"])
async def get_recent_cycles(limit: int = 20, db=Depends(get_db)):
    """Get recent trading cycles with summary stats."""
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT 
                cycle_id,
                MIN(timestamp) as start_time,
                MAX(timestamp) as end_time,
                COUNT(*) as log_count,
                COUNT(DISTINCT agent_name) as agents_involved,
                SUM(tokens_used) as total_tokens,
                AVG(confidence) as avg_confidence
            FROM agent_logs
            GROUP BY cycle_id
            ORDER BY MIN(timestamp) DESC
            LIMIT :limit
        """), {"limit": limit})
        
        rows = result.fetchall()
        return [
            {
                "cycle_id": str(row.cycle_id),
                "start_time": row.start_time.isoformat(),
                "end_time": row.end_time.isoformat(),
                "log_count": row.log_count,
                "agents_involved": row.agents_involved,
                "total_tokens": row.total_tokens or 0,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get cycles: {e}")
        return []


@app.get("/api/universe", tags=["Universe"])
async def get_tradable_universe(
    status: str = "approved",
    limit: int = 100,
    db=Depends(get_db)
):
    """
    Get the dynamic tradable universe.
    
    Args:
        status: Filter by validation status (approved, pending, rejected)
        limit: Maximum coins to return
    """
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT 
                coin, name, volume_24h, market_cap, price_usd,
                price_change_24h, hype_score, sentiment_score,
                narrative_strength, discovery_source, discovered_at,
                validated_at, validation_status, is_active
            FROM tradable_universe
            WHERE validation_status = :status AND is_active = TRUE
            ORDER BY volume_24h DESC
            LIMIT :limit
        """), {"status": status, "limit": limit})
        
        rows = result.fetchall()
        return [
            {
                "coin": row.coin,
                "name": row.name,
                "volume_24h": float(row.volume_24h) if row.volume_24h else 0,
                "market_cap": float(row.market_cap) if row.market_cap else 0,
                "price_usd": float(row.price_usd) if row.price_usd else 0,
                "price_change_24h": float(row.price_change_24h) if row.price_change_24h else 0,
                "hype_score": float(row.hype_score) if row.hype_score else 0,
                "sentiment_score": float(row.sentiment_score) if row.sentiment_score else 0,
                "narrative_strength": float(row.narrative_strength) if row.narrative_strength else 0,
                "discovery_source": row.discovery_source,
                "discovered_at": row.discovered_at.isoformat() if row.discovered_at else None,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get universe: {e}")
        return []


@app.get("/api/universe/stats", tags=["Universe"])
async def get_universe_stats(db=Depends(get_db)):
    """Get universe statistics."""
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE validation_status = 'approved' AND is_active) as approved_count,
                COUNT(*) FILTER (WHERE validation_status = 'pending') as pending_count,
                COUNT(*) FILTER (WHERE validation_status = 'rejected') as rejected_count,
                COUNT(*) FILTER (WHERE discovery_source = 'coingecko') as coingecko_count,
                COUNT(*) FILTER (WHERE discovery_source LIKE 'x_%') as x_discovery_count,
                SUM(volume_24h) FILTER (WHERE is_active) as total_volume,
                AVG(hype_score) FILTER (WHERE is_active) as avg_hype_score
            FROM tradable_universe
        """))
        
        row = result.fetchone()
        return {
            "approved_count": row.approved_count or 0,
            "pending_count": row.pending_count or 0,
            "rejected_count": row.rejected_count or 0,
            "coingecko_count": row.coingecko_count or 0,
            "x_discovery_count": row.x_discovery_count or 0,
            "total_volume": float(row.total_volume) if row.total_volume else 0,
            "avg_hype_score": float(row.avg_hype_score) if row.avg_hype_score else 0,
        }
    except Exception as e:
        logger.warning(f"Failed to get universe stats: {e}")
        return {}


@app.get("/api/strategies", tags=["Strategies"])
async def get_strategy_weights(db=Depends(get_db)):
    """Get current strategy weights and performance."""
    from sqlalchemy import text
    
    try:
        result = await db.execute(text("""
            SELECT DISTINCT ON (strategy_name)
                strategy_name, current_weight,
                win_rate_24h, pnl_24h, trades_24h,
                affinity_low_vol, affinity_normal_vol, affinity_high_vol,
                recorded_at
            FROM strategy_performance
            ORDER BY strategy_name, recorded_at DESC
        """))
        
        rows = result.fetchall()
        return [
            {
                "strategy": row.strategy_name,
                "weight": float(row.current_weight) if row.current_weight else 0.1667,
                "win_rate_24h": float(row.win_rate_24h) if row.win_rate_24h else None,
                "pnl_24h": float(row.pnl_24h) if row.pnl_24h else 0,
                "trades_24h": row.trades_24h or 0,
                "affinity": {
                    "low_vol": float(row.affinity_low_vol) if row.affinity_low_vol else 50,
                    "normal": float(row.affinity_normal_vol) if row.affinity_normal_vol else 50,
                    "high_vol": float(row.affinity_high_vol) if row.affinity_high_vol else 50,
                },
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get strategies: {e}")
        # Return default strategies
        return [
            {"strategy": "momentum", "weight": 0.20},
            {"strategy": "mean_reversion", "weight": 0.15},
            {"strategy": "hype_following", "weight": 0.20},
            {"strategy": "contrarian", "weight": 0.15},
            {"strategy": "volatility_expansion", "weight": 0.15},
            {"strategy": "narrative_driven", "weight": 0.15},
        ]


@app.get("/api/memories", tags=["Memory"])
async def get_recent_memories(
    memory_type: str = None,
    category: str = None,
    limit: int = 50,
    db=Depends(get_db)
):
    """Get recent memories from the learning system."""
    from sqlalchemy import text
    
    try:
        query = """
            SELECT 
                id, title, content, category, memory_type,
                importance_score, recall_count, created_at, related_coins
            FROM memories
            WHERE (expires_at IS NULL OR expires_at > NOW())
        """
        params = {}
        
        if memory_type:
            query += " AND memory_type = :memory_type"
            params["memory_type"] = memory_type
        
        if category:
            query += " AND category = :category"
            params["category"] = category
        
        query += " ORDER BY importance_score DESC, created_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "content": row.content[:200] + "..." if len(row.content) > 200 else row.content,
                "category": row.category,
                "memory_type": row.memory_type,
                "importance": float(row.importance_score) if row.importance_score else 0,
                "recall_count": row.recall_count or 0,
                "created_at": row.created_at.isoformat(),
                "coins": row.related_coins or [],
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get memories: {e}")
        return []


@app.get("/api/x/discoveries", tags=["X Discovery"])
async def get_x_discoveries(
    processed: bool = None,
    limit: int = 50,
    db=Depends(get_db)
):
    """Get recent X/Twitter discoveries."""
    from sqlalchemy import text
    
    try:
        query = """
            SELECT 
                id, coin, tweet_id, tweet_text, tweet_author,
                like_count, retweet_count, engagement_score,
                detected_narrative, sentiment_raw, discovered_at,
                processed, added_to_universe
            FROM x_discoveries
            WHERE 1=1
        """
        params = {}
        
        if processed is not None:
            query += " AND processed = :processed"
            params["processed"] = processed
        
        query += " ORDER BY engagement_score DESC, discovered_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await db.execute(text(query), params)
        rows = result.fetchall()
        
        return [
            {
                "id": str(row.id),
                "coin": row.coin,
                "tweet_id": row.tweet_id,
                "tweet_text": row.tweet_text[:280] if row.tweet_text else None,
                "author": row.tweet_author,
                "engagement": {
                    "likes": row.like_count or 0,
                    "retweets": row.retweet_count or 0,
                    "score": float(row.engagement_score) if row.engagement_score else 0,
                },
                "narrative": row.detected_narrative,
                "sentiment": float(row.sentiment_raw) if row.sentiment_raw else None,
                "discovered_at": row.discovered_at.isoformat(),
                "processed": row.processed,
                "added_to_universe": row.added_to_universe,
            }
            for row in rows
        ]
    except Exception as e:
        logger.warning(f"Failed to get X discoveries: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# WEBSOCKET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_websocket(websocket: WebSocket, channel: str = "all"):
    """
    Core WebSocket handler for real-time updates.
    
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


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, channel: str = "all"):
    """WebSocket endpoint at /ws"""
    await handle_websocket(websocket, channel)


@app.websocket("/")
async def websocket_root_endpoint(websocket: WebSocket, channel: str = "all"):
    """
    WebSocket endpoint at root path.
    
    This is a fallback for when a reverse proxy strips the /ws prefix.
    """
    await handle_websocket(websocket, channel)


# Legacy endpoint for backward compatibility
@app.websocket("/ws/live")
async def websocket_endpoint_legacy(websocket: WebSocket, channel: str = "all"):
    """Legacy WebSocket endpoint at /ws/live"""
    await handle_websocket(websocket, channel)


# ═══════════════════════════════════════════════════════════════════════════════
# EQUITY STREAMING WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

# Track equity WebSocket connections for broadcasting reset messages
_equity_websockets: Set[WebSocket] = set()
_equity_ws_lock = asyncio.Lock()


async def broadcast_equity_reset():
    """Broadcast reset message to all equity WebSocket connections."""
    async with _equity_ws_lock:
        dead_connections = set()
        for ws in _equity_websockets:
            try:
                await ws.send_json({
                    "type": "paper_trades_reset",
                    "message": "All paper trades have been reset",
                    "initial_capital": 100000,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception:
                dead_connections.add(ws)
        
        # Remove dead connections
        for ws in dead_connections:
            _equity_websockets.discard(ws)


async def broadcast_phase_to_equity_ws(phase: str, next_cycle_at: float = None, cycle_number: int = None, progress_current: int = None, progress_total: int = None):
    """
    Broadcast phase update to all equity WebSocket connections.
    
    This allows the dashboard to show real-time phase updates.
    """
    message = {
        "type": "phase",
        "phase": phase,
        "timestamp": datetime.utcnow().timestamp(),
    }
    
    if next_cycle_at is not None:
        message["next_cycle_at"] = next_cycle_at
    
    if cycle_number is not None:
        message["cycle_number"] = cycle_number
    
    if progress_current is not None:
        message["progress_current"] = progress_current
    
    if progress_total is not None:
        message["progress_total"] = progress_total
    
    async with _equity_ws_lock:
        dead_connections = set()
        for ws in _equity_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_connections.add(ws)
        
        for ws in dead_connections:
            _equity_websockets.discard(ws)


@app.websocket("/ws/equity")
async def websocket_equity_stream(websocket: WebSocket):
    """
    Real-time equity stream via WebSocket.
    
    Sends equity updates every second with:
    - total_equity: Current portfolio value
    - unrealized_pnl: PnL from open positions
    - position_details: Per-position breakdown
    """
    await websocket.accept()
    logger.info("Equity WebSocket connected")
    
    # Add to tracked connections
    async with _equity_ws_lock:
        _equity_websockets.add(websocket)
    
    try:
        from trader.equity_tracker import get_equity_tracker
        tracker = get_equity_tracker()
        
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Send current phase if available
        try:
            from trading_state import get_trading_loop
            trading_loop = get_trading_loop()
            if trading_loop and hasattr(trading_loop, '_current_phase'):
                phase_msg = {
                    "type": "phase",
                    "phase": trading_loop._current_phase,
                    "timestamp": datetime.utcnow().timestamp(),
                    "cycle_number": trading_loop._cycle_count
                }
                await websocket.send_json(phase_msg)
        except Exception as e:
            logger.debug(f"Could not send initial phase: {e}")
        
        # Send equity updates every second
        while True:
            try:
                latest = tracker.get_latest()
                
                if latest:
                    await websocket.send_json({
                        "type": "equity_update",
                        "data": latest.to_dict()
                    })
                else:
                    # No data yet, send empty update
                    await websocket.send_json({
                        "type": "equity_update",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                            "total_equity": 100000,
                            "cash": 100000,
                            "positions_value": 0,
                            "unrealized_pnl": 0,
                            "position_details": []
                        }
                    })
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
                
    except WebSocketDisconnect:
        logger.info("Equity WebSocket disconnected")
    except Exception as e:
        logger.warning(f"Equity WebSocket error: {e}")
    finally:
        # Remove from tracked connections
        async with _equity_ws_lock:
            _equity_websockets.discard(websocket)


@app.get("/api/equity/history", tags=["Equity"])
async def get_equity_history(limit: int = 60):
    """
    Get recent equity history for charting.
    
    Returns the last N seconds of equity snapshots.
    """
    try:
        from trader.equity_tracker import get_equity_tracker
        tracker = get_equity_tracker()
        
        history = tracker.get_history(limit)
        return [h.to_dict() for h in history]
    except Exception as e:
        logger.warning(f"Failed to get equity history: {e}")
        return []


@app.get("/api/equity/current", tags=["Equity"])
async def get_current_equity():
    """Get current equity snapshot."""
    try:
        from trader.equity_tracker import get_equity_tracker
        tracker = get_equity_tracker()
        
        latest = tracker.get_latest()
        if latest:
            return latest.to_dict()
        
        # Fallback
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_equity": 100000,
            "cash": 100000,
            "positions_value": 0,
            "unrealized_pnl": 0,
            "position_details": []
        }
    except Exception as e:
        logger.warning(f"Failed to get current equity: {e}")
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# PAPER TRADE RESET ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

@app.delete("/api/paper-trades/reset", tags=["Trading"])
async def reset_paper_trades(db=Depends(get_db)):
    """
    Reset all paper trades and positions.
    
    This endpoint deletes all data from:
    - paper_trades (closed trades)
    - paper_positions (open and closed positions)
    - trading_decisions
    - predictions
    - prediction_cycles
    - portfolio_snapshots
    
    The system will start fresh with initial capital of $100,000 USDT.
    
    WARNING: This action is irreversible!
    """
    from sqlalchemy import text
    
    try:
        # FIRST: Reset in-memory state BEFORE clearing DB
        # This prevents race conditions where new cycles use old capital
        reset_result = None
        try:
            from trading_state import get_trading_loop
            loop = get_trading_loop()
            if loop:
                reset_result = loop.reset_paper_trading()
                logger.warning(f"IN-MEMORY RESET COMPLETE: {reset_result}")
            else:
                logger.error("RESET FAILED: No trading loop!")
        except Exception as e:
            logger.error(f"Could not reset via trading loop: {e}", exc_info=True)
        
        # THEN: Delete database records
        tables_to_clear = [
            "paper_trades",       # Depends on paper_positions
            "paper_positions",    # Main positions table
            "predictions",        # Depends on prediction_cycles
            "prediction_cycles",  # Trading cycle data
            "trading_decisions",  # Tactician decisions
            "portfolio_snapshots", # Equity history
        ]
        
        deleted_counts = {}
        
        for table in tables_to_clear:
            try:
                # Count before delete
                count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar() or 0
                
                # Delete all rows
                await db.execute(text(f"DELETE FROM {table}"))
                deleted_counts[table] = count
                
                logger.info(f"Deleted {count} rows from {table}")
            except Exception as table_error:
                logger.warning(f"Could not clear {table}: {table_error}")
                deleted_counts[table] = 0
        
        # Reset the cycle number sequence to start from 1
        try:
            await db.execute(text("ALTER SEQUENCE prediction_cycle_seq RESTART WITH 1"))
            logger.info("Reset prediction_cycle_seq sequence to 1")
        except Exception as seq_error:
            logger.warning(f"Could not reset sequence: {seq_error}")
        
        # Commit the transaction
        await db.commit()
        logger.warning("DATABASE RESET COMPLETE")
        
        # Broadcast reset message to all WebSocket clients
        try:
            reset_message = {
                "type": "paper_trades_reset",
                "message": "All paper trades have been reset",
                "initial_capital": 100000,
                "timestamp": datetime.utcnow().isoformat()
            }
            await manager.broadcast(reset_message, "all")
            logger.info("Broadcast reset message to WebSocket clients")
        except Exception as e:
            logger.debug(f"Could not broadcast reset message: {e}")
        
        # Broadcast reset to equity WebSocket clients
        try:
            await broadcast_equity_reset()
            logger.info("Broadcast reset to equity WebSocket clients")
        except Exception as e:
            logger.debug(f"Could not broadcast equity reset: {e}")
        
        # Add reset result info
        positions_cleared = reset_result.get('positions_cleared', 0) if reset_result else 0

        total_deleted = sum(deleted_counts.values())
        
        logger.info(f"Paper trade reset complete. Total rows deleted: {total_deleted}")
        
        return {
            "status": "success",
            "message": "All paper trades and positions have been reset.",
            "deleted_counts": deleted_counts,
            "total_deleted": total_deleted,
            "positions_cleared": positions_cleared,
            "initial_capital": 100000,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to reset paper trades: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset paper trades: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
