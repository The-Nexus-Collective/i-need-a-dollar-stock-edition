"""
Real-time WebSocket Gateway

Streams live data to dashboard:
- Equity updates (every 100ms)
- Price updates
- Trade notifications
- System status
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, List, Set
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for live data streaming.
    
    Features:
    - Connection tracking
    - Broadcast to all clients
    - Automatic cleanup on disconnect
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept connection and return connection ID"""
        await websocket.accept()
        connection_id = uuid4().hex[:8]
        
        async with self._lock:
            self.active_connections[connection_id] = websocket
        
        logger.info(f"WebSocket connected: {connection_id} (total: {len(self.active_connections)})")
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Remove connection"""
        async with self._lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]
        
        logger.info(f"WebSocket disconnected: {connection_id} (total: {len(self.active_connections)})")
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients"""
        if not self.active_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        async with self._lock:
            for conn_id, websocket in self.active_connections.items():
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(message_json)
                except Exception as e:
                    logger.error(f"Broadcast error for {conn_id}: {e}")
                    disconnected.append(conn_id)
        
        # Cleanup disconnected
        for conn_id in disconnected:
            await self.disconnect(conn_id)
    
    async def send_to(self, connection_id: str, message: dict):
        """Send message to specific client"""
        async with self._lock:
            websocket = self.active_connections.get(connection_id)
            if websocket and websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Send error for {connection_id}: {e}")
    
    @property
    def connection_count(self) -> int:
        return len(self.active_connections)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/live")
async def live_stream(websocket: WebSocket):
    """
    Live data WebSocket endpoint.
    
    Streams:
    - equity: Portfolio equity updates
    - price: Real-time price updates
    - trade: Trade execution notifications
    - status: System status updates
    """
    connection_id = await manager.connect(websocket)
    
    try:
        # Send initial state
        await send_initial_state(websocket)
        
        # Keep connection alive
        while True:
            try:
                # Wait for client messages (ping/pong, commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                # Handle client commands
                await handle_client_message(connection_id, data)
                
            except asyncio.TimeoutError:
                # Send ping to keep alive
                await websocket.send_json({"type": "ping", "timestamp": datetime.utcnow().timestamp()})
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await manager.disconnect(connection_id)


async def send_initial_state(websocket: WebSocket):
    """Send current state when client connects"""
    try:
        from core.equity_calculator import get_equity_calculator
        from core.price_cache import get_price_cache
        
        # Get current equity
        calc = get_equity_calculator()
        equity = calc.get_current_equity()
        
        # Get current prices
        prices = get_price_cache().get_all()
        
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "timestamp": datetime.utcnow().timestamp(),
            "equity": equity.to_dict(),
            "prices": prices
        })
        
    except Exception as e:
        logger.error(f"Error sending initial state: {e}")
        await websocket.send_json({
            "type": "init",
            "timestamp": datetime.utcnow().timestamp(),
            "equity": None,
            "prices": {},
            "error": str(e)
        })


async def handle_client_message(connection_id: str, data: str):
    """Handle messages from client"""
    try:
        message = json.loads(data)
        msg_type = message.get("type", "")
        
        if msg_type == "ping":
            await manager.send_to(connection_id, {
                "type": "pong",
                "timestamp": datetime.utcnow().timestamp()
            })
        
        elif msg_type == "subscribe":
            # Client wants to subscribe to specific channels
            channels = message.get("channels", [])
            logger.info(f"Client {connection_id} subscribed to: {channels}")
        
    except json.JSONDecodeError:
        pass


# ═══════════════════════════════════════════════════════════════════════════════
# BROADCAST FUNCTIONS (called from other services)
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast_equity(equity_update):
    """Broadcast equity update to all clients"""
    await manager.broadcast(equity_update.to_dict())


async def broadcast_price(coin: str, price: float):
    """Broadcast price update"""
    await manager.broadcast({
        "type": "price",
        "coin": coin,
        "price": price,
        "timestamp": datetime.utcnow().timestamp()
    })


async def broadcast_trade(trade_data: dict):
    """Broadcast trade notification"""
    await manager.broadcast({
        "type": "trade",
        "data": trade_data,
        "timestamp": datetime.utcnow().timestamp()
    })


async def broadcast_status(status: str, message: str):
    """Broadcast system status"""
    await manager.broadcast({
        "type": "status",
        "status": status,
        "message": message,
        "timestamp": datetime.utcnow().timestamp()
    })


async def broadcast_phase(phase: str, next_cycle_at: float = None, cycle_number: int = None):
    """
    Broadcast trading loop phase update.
    
    Args:
        phase: Current phase - 'idle', 'fetching', 'analyzing', 'trading'
        next_cycle_at: Unix timestamp of next cycle (only for idle phase)
        cycle_number: Current cycle number
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
    
    await manager.broadcast(message)


def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager"""
    return manager
