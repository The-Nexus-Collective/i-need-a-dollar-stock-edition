"""
Swarm WebSocket - Real-time streaming for the UI

Streams:
- Agent thoughts (as they think)
- Signals between agents
- Swarm status updates
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class SwarmStreamManager:
    """Manages WebSocket connections for swarm streaming."""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {
            "thoughts": set(),
            "signals": set(),
            "status": set(),
            "all": set(),
        }
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            if channel not in self.active_connections:
                self.active_connections[channel] = set()
            self.active_connections[channel].add(websocket)
            self.active_connections["all"].add(websocket)
        logger.info(f"Swarm WebSocket connected to channel: {channel}")
    
    async def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """Remove a WebSocket connection."""
        async with self._lock:
            for ch in self.active_connections.values():
                ch.discard(websocket)
    
    async def broadcast(self, message: dict, channel: str = "all"):
        """Broadcast a message to all connections on a channel."""
        connections = self.active_connections.get(channel, set())
        
        dead = set()
        for conn in connections:
            try:
                await conn.send_json(message)
            except Exception:
                dead.add(conn)
        
        # Clean up dead connections
        async with self._lock:
            for conn in dead:
                for ch in self.active_connections.values():
                    ch.discard(conn)
    
    async def broadcast_thought(self, chunk):
        """Broadcast a thought chunk."""
        logger.info(f"Broadcasting thought to WS: {chunk.agent_name} - {chunk.content[:50] if chunk.content else '[final]'}...")
        
        message = {
            "type": "thought",
            "agent_id": chunk.agent_id,
            "agent_name": chunk.agent_name,
            "content": chunk.content,
            "is_final": chunk.is_final,
            "timestamp": chunk.timestamp.isoformat() if hasattr(chunk.timestamp, 'isoformat') else str(chunk.timestamp),
        }
        
        connections = self.active_connections.get("all", set())
        logger.info(f"Active WebSocket connections: {len(connections)}")
        
        await self.broadcast(message, "thoughts")
        await self.broadcast(message, "all")
    
    async def broadcast_signal(self, signal):
        """Broadcast a signal."""
        logger.info(f"Broadcasting signal to WS: {signal.sender_name} [{signal.type}] - {signal.content[:50]}...")
        
        message = {
            "type": "signal",
            **signal.to_dict(),
        }
        await self.broadcast(message, "signals")
        await self.broadcast(message, "all")


# Global instance
stream_manager = SwarmStreamManager()


def get_stream_manager() -> SwarmStreamManager:
    """Get the stream manager."""
    return stream_manager


@router.websocket("/swarm")
async def swarm_websocket(websocket: WebSocket, channel: str = "all"):
    """
    WebSocket endpoint for swarm streaming.
    
    Channels:
    - all: All events
    - thoughts: Agent thinking (streamed)
    - signals: Agent-to-agent signals
    - status: Swarm status updates
    """
    await stream_manager.connect(websocket, channel)
    
    try:
        # Send connection confirmation
        await websocket.send_json({
            "type": "connected",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )
                
                if data == "ping":
                    await websocket.send_text("pong")
                    
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.utcnow().isoformat(),
                })
    
    except WebSocketDisconnect:
        await stream_manager.disconnect(websocket, channel)
        logger.info(f"Swarm WebSocket disconnected from channel: {channel}")
    except Exception as e:
        logger.error(f"Swarm WebSocket error: {e}")
        await stream_manager.disconnect(websocket, channel)


@router.get("/swarm/status")
async def get_swarm_status():
    """Get current swarm status."""
    try:
        from swarm import get_swarm_network
        network = get_swarm_network()
        return network.get_status()
    except Exception as e:
        logger.error(f"Failed to get swarm status: {e}")
        return {"error": str(e)}

