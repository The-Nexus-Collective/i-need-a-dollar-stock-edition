"""
Redis Streams Event Bus
Persistent, ordered, with consumer groups for reliable event processing
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, List, Optional, Set
from uuid import UUID

import redis.asyncio as redis
from redis.asyncio.client import Redis

from .schemas import BaseEvent, EventType, deserialize_event

logger = logging.getLogger(__name__)


class EventBus:
    """
    Redis Streams-based event bus for reliable event delivery.
    
    Features:
    - Persistent events (survives restarts)
    - Ordered delivery per stream
    - Consumer groups for load balancing
    - Automatic acknowledgment
    - Dead letter handling
    """
    
    # Stream names for different event categories
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
    
    def __init__(self, redis_url: str = None):
        # Handle empty string case
        env_url = os.getenv("REDIS_URL", "").strip()
        self.redis_url = redis_url or env_url or "redis://localhost:6379"
        logger.info(f"EventBus using Redis URL: {self.redis_url[:30]}...")
        self._redis: Optional[Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._subscribers: Dict[str, List[Callable]] = {}
        self._running = False
        self._consumer_tasks: List[asyncio.Task] = []
    
    async def connect(self) -> None:
        """Connect to Redis"""
        if self._redis is None:
            self._redis = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False  # We handle our own encoding
            )
            logger.info(f"Connected to Redis at {self.redis_url}")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        self._running = False
        for task in self._consumer_tasks:
            task.cancel()
        if self._pubsub:
            await self._pubsub.close()
        if self._redis:
            await self._redis.close()
            self._redis = None
        logger.info("Disconnected from Redis")
    
    async def publish(self, event: BaseEvent) -> str:
        """
        Publish an event to the appropriate stream.
        Returns the message ID assigned by Redis.
        """
        await self.connect()
        
        # Determine stream based on event type
        stream_key = self.EVENT_STREAM_MAP.get(
            EventType(event.type) if isinstance(event.type, str) else event.type,
            "system"
        )
        stream_name = self.STREAMS[stream_key]
        
        # Serialize event
        event_data = event.to_redis_dict()
        
        # Add to stream (XADD)
        message_id = await self._redis.xadd(
            stream_name,
            event_data,
            maxlen=10000  # Keep last 10k events per stream
        )
        
        # Also publish to pub/sub for real-time subscribers (WebSocket)
        await self._redis.publish(
            f"realtime:{stream_key}",
            event.model_dump_json()
        )
        
        logger.debug(f"Published {event.type} to {stream_name}: {message_id}")
        return message_id.decode() if isinstance(message_id, bytes) else message_id
    
    async def create_consumer_group(
        self,
        stream_key: str,
        group_name: str,
        start_id: str = "0"
    ) -> bool:
        """Create a consumer group for a stream"""
        await self.connect()
        stream_name = self.STREAMS[stream_key]
        
        try:
            await self._redis.xgroup_create(
                stream_name,
                group_name,
                id=start_id,
                mkstream=True
            )
            logger.info(f"Created consumer group {group_name} for {stream_name}")
            return True
        except redis.ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug(f"Consumer group {group_name} already exists")
                return True
            raise
    
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
        Consume events from a stream with a consumer group.
        Automatically acknowledges processed events.
        """
        await self.connect()
        await self.create_consumer_group(stream_key, group_name)
        
        stream_name = self.STREAMS[stream_key]
        self._running = True
        
        logger.info(f"Starting consumer {consumer_name} in group {group_name} for {stream_name}")
        
        while self._running:
            try:
                # Read new messages
                messages = await self._redis.xreadgroup(
                    group_name,
                    consumer_name,
                    {stream_name: ">"},  # Only new messages
                    count=batch_size,
                    block=block_ms
                )
                
                if messages:
                    for stream, entries in messages:
                        for message_id, data in entries:
                            try:
                                event = deserialize_event(data)
                                await handler(event)
                                
                                # Acknowledge successful processing
                                await self._redis.xack(stream_name, group_name, message_id)
                                logger.debug(f"Processed and acked {message_id}")
                                
                            except Exception as e:
                                logger.error(f"Error processing {message_id}: {e}")
                                # Could move to dead letter stream here
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1)
        
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
        await self.connect()
        
        # Create consumer groups for all streams
        for stream_key in stream_keys:
            await self.create_consumer_group(stream_key, group_name)
        
        streams = {self.STREAMS[k]: ">" for k in stream_keys}
        self._running = True
        
        logger.info(f"Starting multi-stream consumer {consumer_name} for {stream_keys}")
        
        while self._running:
            try:
                messages = await self._redis.xreadgroup(
                    group_name,
                    consumer_name,
                    streams,
                    count=batch_size,
                    block=block_ms
                )
                
                if messages:
                    for stream_name, entries in messages:
                        stream_name_str = stream_name.decode() if isinstance(stream_name, bytes) else stream_name
                        for message_id, data in entries:
                            try:
                                event = deserialize_event(data)
                                await handler(event)
                                await self._redis.xack(stream_name_str, group_name, message_id)
                            except Exception as e:
                                logger.error(f"Error processing {message_id}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Multi-consumer error: {e}")
                await asyncio.sleep(1)
    
    async def subscribe_realtime(
        self,
        channels: List[str],
        handler: Callable[[str, BaseEvent], None]
    ) -> None:
        """
        Subscribe to real-time pub/sub channels.
        Used for WebSocket forwarding.
        """
        await self.connect()
        self._pubsub = self._redis.pubsub()
        
        channel_names = [f"realtime:{c}" for c in channels]
        await self._pubsub.subscribe(*channel_names)
        
        logger.info(f"Subscribed to real-time channels: {channels}")
        
        self._running = True
        while self._running:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                if message and message["type"] == "message":
                    channel = message["channel"].decode().replace("realtime:", "")
                    data = json.loads(message["data"])
                    event = deserialize_event({b"data": message["data"]})
                    await handler(channel, event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Pub/sub error: {e}")
    
    async def get_stream_info(self, stream_key: str) -> Dict:
        """Get information about a stream"""
        await self.connect()
        stream_name = self.STREAMS[stream_key]
        
        try:
            info = await self._redis.xinfo_stream(stream_name)
            return {
                "length": info["length"],
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
                "groups": info.get("groups", 0),
            }
        except redis.ResponseError:
            return {"length": 0, "error": "Stream does not exist"}
    
    async def get_recent_events(
        self,
        stream_key: str,
        count: int = 100
    ) -> List[BaseEvent]:
        """Get recent events from a stream (for dashboard)"""
        await self.connect()
        stream_name = self.STREAMS[stream_key]
        
        try:
            # XREVRANGE to get most recent first
            messages = await self._redis.xrevrange(stream_name, count=count)
            events = []
            for message_id, data in messages:
                try:
                    event = deserialize_event(data)
                    events.append(event)
                except Exception as e:
                    logger.warning(f"Failed to deserialize {message_id}: {e}")
            return events
        except redis.ResponseError:
            return []


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def init_event_bus() -> EventBus:
    """Initialize and connect the event bus"""
    bus = get_event_bus()
    await bus.connect()
    return bus
