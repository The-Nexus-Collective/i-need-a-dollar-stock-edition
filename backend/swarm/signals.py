"""
Signal Network - Decentralized Agent Communication

Agents communicate through signals, not direct commands.
Each agent decides independently whether to respond to a signal.

Signal types emerge naturally from agent interactions:
- ALERT: Something important happening
- INSIGHT: Sharing a realization
- QUESTION: Seeking information
- PROPOSAL: Suggesting an action
- VOTE: Agreeing/disagreeing
- RESULT: Outcome of an action
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Types of signals agents can send."""
    
    # Discovery
    ALERT = "alert"              # Something important happening
    DISCOVERY = "discovery"      # Found something new
    
    # Communication
    INSIGHT = "insight"          # Sharing a realization
    QUESTION = "question"        # Seeking information
    RESPONSE = "response"        # Answering a question
    
    # Decision
    PROPOSAL = "proposal"        # Suggesting an action
    VOTE = "vote"                # Agreeing/disagreeing
    
    # Action
    ACTION = "action"            # Taking an action
    RESULT = "result"            # Outcome of action
    
    # System
    HEARTBEAT = "heartbeat"      # Agent alive check
    THOUGHT = "thought"          # Ongoing thinking (for UI)


@dataclass
class Signal:
    """
    A signal sent between agents.
    
    Signals are the only way agents communicate.
    Each agent independently decides how to respond.
    """
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Source
    sender_id: str = ""
    sender_name: str = ""
    
    # Content
    type: SignalType = SignalType.INSIGHT
    topic: str = ""              # What is this about?
    content: str = ""            # The actual message
    
    # Metadata
    confidence: float = 0.5      # How confident is the sender? (0-1)
    urgency: float = 0.5         # How urgent? (0-1)
    importance: float = 0.5      # How important? (0-1)
    
    # Targeting (optional)
    mentions: List[str] = field(default_factory=list)  # Specific agents mentioned
    tags: List[str] = field(default_factory=list)      # Topic tags
    
    # Context
    related_signals: List[UUID] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Serialize for WebSocket transmission."""
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "type": self.type.value,
            "topic": self.topic,
            "content": self.content,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "importance": self.importance,
            "mentions": self.mentions,
            "tags": self.tags,
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        """Deserialize from dict."""
        return cls(
            id=UUID(data["id"]) if isinstance(data.get("id"), str) else data.get("id", uuid4()),
            timestamp=datetime.fromisoformat(data["timestamp"]) if isinstance(data.get("timestamp"), str) else data.get("timestamp", datetime.utcnow()),
            sender_id=data.get("sender_id", ""),
            sender_name=data.get("sender_name", ""),
            type=SignalType(data.get("type", "insight")),
            topic=data.get("topic", ""),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.5),
            urgency=data.get("urgency", 0.5),
            importance=data.get("importance", 0.5),
            mentions=data.get("mentions", []),
            tags=data.get("tags", []),
            data=data.get("data", {}),
        )


class SignalNetwork:
    """
    Decentralized signal propagation network.
    
    No agent controls another - they only broadcast signals.
    Each agent decides independently whether to respond.
    """
    
    def __init__(self):
        self._agents: Dict[str, Any] = {}  # agent_id -> agent
        self._subscribers: List[Callable] = []  # External subscribers (UI)
        self._signal_history: List[Signal] = []  # Recent signals for context
        self._history_limit: int = 1000
        self._lock = asyncio.Lock()
    
    def register_agent(self, agent_id: str, agent: Any):
        """Register an agent to receive signals."""
        self._agents[agent_id] = agent
        logger.info(f"Agent {agent_id} joined the signal network")
    
    def unregister_agent(self, agent_id: str):
        """Remove an agent from the network."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Agent {agent_id} left the signal network")
    
    def subscribe(self, callback: Callable[[Signal], None]):
        """Subscribe to all signals (for UI)."""
        self._subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable[[Signal], None]):
        """Unsubscribe from signals."""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
    
    async def broadcast(self, signal: Signal):
        """
        Broadcast a signal to all agents.
        
        Each agent independently decides whether to respond.
        The sender never knows if/how agents will react.
        """
        async with self._lock:
            # Store in history
            self._signal_history.append(signal)
            if len(self._signal_history) > self._history_limit:
                self._signal_history = self._signal_history[-self._history_limit:]
        
        logger.debug(
            f"Signal broadcast: [{signal.type.value}] from {signal.sender_name}: "
            f"{signal.content[:100]}..."
        )
        
        # Notify all external subscribers (UI, logging, etc.)
        for callback in self._subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal)
                else:
                    callback(signal)
            except Exception as e:
                logger.warning(f"Signal subscriber error: {e}")
        
        # Deliver to agents (non-blocking)
        for agent_id, agent in list(self._agents.items()):
            # Don't send to self
            if agent_id == signal.sender_id:
                continue
            
            # Check if agent is interested
            try:
                if hasattr(agent, 'is_interested') and not agent.is_interested(signal):
                    continue
                
                # Deliver signal (fire and forget)
                if hasattr(agent, 'receive_signal'):
                    asyncio.create_task(
                        self._safe_deliver(agent, signal)
                    )
            except Exception as e:
                logger.warning(f"Signal delivery check failed for {agent_id}: {e}")
    
    async def _safe_deliver(self, agent: Any, signal: Signal):
        """Safely deliver a signal to an agent."""
        try:
            await agent.receive_signal(signal)
        except Exception as e:
            logger.warning(f"Signal delivery failed to {getattr(agent, 'name', 'unknown')}: {e}")
    
    def get_recent_signals(
        self,
        limit: int = 100,
        signal_type: Optional[SignalType] = None,
        sender_id: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> List[Signal]:
        """Get recent signals with optional filtering."""
        signals = self._signal_history[-limit:]
        
        if signal_type:
            signals = [s for s in signals if s.type == signal_type]
        if sender_id:
            signals = [s for s in signals if s.sender_id == sender_id]
        if topic:
            signals = [s for s in signals if topic.lower() in s.topic.lower()]
        
        return signals
    
    def get_active_agents(self) -> List[str]:
        """Get list of active agent IDs."""
        return list(self._agents.keys())
    
    def get_agent_count(self) -> int:
        """Get number of active agents."""
        return len(self._agents)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_signal_network: Optional[SignalNetwork] = None


def get_signal_network() -> SignalNetwork:
    """Get or create global signal network."""
    global _signal_network
    if _signal_network is None:
        _signal_network = SignalNetwork()
    return _signal_network

