"""
In-Memory Event Bus (No Redis Required)

Provides the same API as the Redis version but uses asyncio queues.
All events are stored in-memory for real-time processing.
For a monolithic application, this is faster and simpler.
"""

import asyncio
import json
import logging
from collections import deque
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, List, Optional, Set

from .schemas import BaseEvent, EventType, deserialize_event

logger = logging.getLogger(__name__)


class InMemoryEventBus:
    """
    In-memory event bus using asyncio primitives.
    
    Features:
    - asyncio.Queue for pub/sub
    - In-memory event history (configurable size)
    - Same API as Redis version for drop-in replacement
    - WebSocket broadcast support
    """
    
    # Stream names (kept for API compatibility)
    STREAMS = {
        "signals": "trading:signals",
        "risk": "trading:risk",
        "orders": "trading:orders",
        "positions": "trading:positions",
        "portfolio": "trading:portfolio",
        "system": "trading:system",
        "market": "trading:market",
    }
    
    # Map event types to streams
    EVENT_STREAM_MAP = {
        EventType.SIGNAL_GENERATED: "signals",
        EventType.SIGNAL_EXPIRED: "signals",
        EventType.RISK_CHECK_REQUESTED: "risk",
        EventType.RISK_APPROVED: "risk",
        EventType.RISK_REJECTED: "risk",
        EventType.RISK_LIMIT_BREACH: "risk",
        EventType.ORDER_SUBMITTED: "orders",
        EventType.ORDER_FILLED: "orders",
        EventType.ORDER_PARTIAL: "orders",
        EventType.ORDER_CANCELLED: "orders",
        EventType.ORDER_REJECTED: "orders",
        EventType.POSITION_OPENED: "positions",
        EventType.POSITION_UPDATED: "positions",
        EventType.POSITION_CLOSED: "positions",
        EventType.PORTFOLIO_SNAPSHOT: "portfolio",
        EventType.PORTFOLIO_REBALANCE: "portfolio",
        EventType.CIRCUIT_BREAKER_TRIGGERED: "system",
        EventType.SYSTEM_HALT: "system",
        EventType.SYSTEM_RESUME: "system",
        EventType.HEARTBEAT: "system",
        EventType.PRICE_UPDATE: "market",
        EventType.MARKET_DATA_STALE: "market",
    }
    
    def __init__(self, history_size: int = 10000):
        """
        Initialize in-memory event bus.
        
        Args:
            history_size: Max events to keep per stream (for get_recent_events)
        """
        self.history_size = history_size
        self._connected = False
        
        # Event queues per stream (for consumers)
        self._queues: Dict[str, List[asyncio.Queue]] = {}
        
        # Event history per stream (for get_recent_events)
        self._history: Dict[str, deque] = {}
        
        # Real-time subscribers (for WebSocket forwarding)
        self._realtime_subscribers: Dict[str, List[Callable]] = {}
        
        # Running state
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []
        
        # Initialize streams
        for stream_key in self.STREAMS:
            self._queues[stream_key] = []
            self._history[stream_key] = deque(maxlen=history_size)
        
        logger.info("InMemoryEventBus initialized")
    
    async def connect(self) -> None:
        """Connect (no-op for in-memory, kept for API compatibility)"""
        self._connected = True
        logger.info("InMemoryEventBus connected")
    
    async def disconnect(self) -> None:
        """Disconnect and cleanup"""
        self._running = False
        self._connected = False
        
        # Cancel all consumer tasks
        for task in self._consumer_tasks:
            task.cancel()
        
        # Clear queues
        for stream_key in self._queues:
            self._queues[stream_key] = []
        
        logger.info("InMemoryEventBus disconnected")
    
    async def publish(self, event: BaseEvent) -> str:
        """
        Publish an event to the appropriate stream.
        
        Returns a synthetic message ID.
        """
        if not self._connected:
            await self.connect()
        
        # Determine stream
        event_type = EventType(event.type) if isinstance(event.type, str) else event.type
        stream_key = self.EVENT_STREAM_MAP.get(event_type, "system")
        
        # Generate message ID
        message_id = f"{datetime.utcnow().timestamp()}-{event.id}"
        
        # Add to history
        self._history[stream_key].append((message_id, event))
        
        # Notify all queue consumers
        for queue in self._queues.get(stream_key, []):
            try:
                queue.put_nowait((message_id, event))
            except asyncio.QueueFull:
                logger.warning(f"Queue full for {stream_key}, dropping event")
        
        # Notify real-time subscribers (for WebSocket)
        for callback in self._realtime_subscribers.get(stream_key, []):
            try:
                await callback(stream_key, event)
            except Exception as e:
                logger.error(f"Error in realtime subscriber: {e}")
        
        logger.debug(f"Published {event.type} to {stream_key}: {message_id}")
        return message_id
    
    async def create_consumer_group(
        self,
        stream_key: str,
        group_name: str,
        start_id: str = "0"
    ) -> bool:
        """Create consumer group (no-op for in-memory, kept for API compatibility)"""
        logger.debug(f"Consumer group {group_name} ready for {stream_key}")
        return True
    
    async def consume(
        self,
        stream_key: str,
        group_name: str,
        consumer_name: str,
        handler: Callable[[BaseEvent], None],
        batch_size: int = 10,
        block_ms: int = 5000
    ) -> None:
        """
        Consume events from a stream.
        
        Creates an asyncio.Queue for this consumer and processes events.
        """
        if not self._connected:
            await self.connect()
        
        # Create queue for this consumer
        queue = asyncio.Queue(maxsize=1000)
        self._queues[stream_key].append(queue)
        
        self._running = True
        logger.info(f"Consumer {consumer_name} started for {stream_key}")
        
        try:
            while self._running:
                try:
                    # Wait for event with timeout
                    message_id, event = await asyncio.wait_for(
                        queue.get(),
                        timeout=block_ms / 1000
                    )
                    
                    try:
                        await handler(event)
                        logger.debug(f"Processed {message_id}")
                    except Exception as e:
                        logger.error(f"Error processing {message_id}: {e}")
                    
                except asyncio.TimeoutError:
                    # No events, continue waiting
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            # Remove queue from list
            if queue in self._queues.get(stream_key, []):
                self._queues[stream_key].remove(queue)
            logger.info(f"Consumer {consumer_name} stopped")
    
    async def consume_multiple(
        self,
        stream_keys: List[str],
        group_name: str,
        consumer_name: str,
        handler: Callable[[BaseEvent], None],
        batch_size: int = 10,
        block_ms: int = 5000
    ) -> None:
        """Consume from multiple streams simultaneously"""
        if not self._connected:
            await self.connect()
        
        # Create queues for all streams
        queues = {}
        for stream_key in stream_keys:
            queue = asyncio.Queue(maxsize=1000)
            self._queues[stream_key].append(queue)
            queues[stream_key] = queue
        
        self._running = True
        logger.info(f"Multi-stream consumer {consumer_name} started for {stream_keys}")
        
        try:
            while self._running:
                # Check all queues
                for stream_key, queue in queues.items():
                    try:
                        message_id, event = queue.get_nowait()
                        try:
                            await handler(event)
                        except Exception as e:
                            logger.error(f"Error processing {message_id}: {e}")
                    except asyncio.QueueEmpty:
                        continue
                
                # Small sleep to prevent busy loop
                await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            pass
        finally:
            # Remove queues
            for stream_key, queue in queues.items():
                if queue in self._queues.get(stream_key, []):
                    self._queues[stream_key].remove(queue)
    
    async def subscribe_realtime(
        self,
        channels: List[str],
        handler: Callable[[str, BaseEvent], None]
    ) -> None:
        """
        Subscribe to real-time events.
        Used for WebSocket forwarding.
        """
        for channel in channels:
            if channel not in self._realtime_subscribers:
                self._realtime_subscribers[channel] = []
            self._realtime_subscribers[channel].append(handler)
        
        logger.info(f"Subscribed to real-time channels: {channels}")
        
        # Keep running until cancelled
        self._running = True
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            # Remove handlers
            for channel in channels:
                if handler in self._realtime_subscribers.get(channel, []):
                    self._realtime_subscribers[channel].remove(handler)
    
    async def get_stream_info(self, stream_key: str) -> Dict:
        """Get information about a stream"""
        history = self._history.get(stream_key, deque())
        
        return {
            "length": len(history),
            "first_entry": history[0] if history else None,
            "last_entry": history[-1] if history else None,
            "consumers": len(self._queues.get(stream_key, [])),
        }
    
    async def get_recent_events(
        self,
        stream_key: str,
        count: int = 100
    ) -> List[BaseEvent]:
        """Get recent events from a stream"""
        history = self._history.get(stream_key, deque())
        
        # Get last N events
        events = []
        for i, (message_id, event) in enumerate(reversed(history)):
            if i >= count:
                break
            events.append(event)
        
        return events


# Use InMemoryEventBus as the default EventBus
EventBus = InMemoryEventBus

# Global event bus instance
_event_bus: Optional[InMemoryEventBus] = None


def get_event_bus() -> InMemoryEventBus:
    """Get or create the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = InMemoryEventBus()
    return _event_bus


async def init_event_bus() -> InMemoryEventBus:
    """Initialize and connect the event bus"""
    bus = get_event_bus()
    await bus.connect()
    return bus
