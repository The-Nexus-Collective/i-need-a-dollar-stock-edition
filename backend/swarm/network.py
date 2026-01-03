"""
Swarm Network - Manages the Agent Swarm

Responsible for:
- Spawning and managing agents
- Connecting agents to signals/memory
- Running the swarm loop
- Providing status/metrics
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Type
from uuid import UUID

from .agent import EmergentAgent, AgentPersona
from .signals import SignalNetwork, get_signal_network
from .memory import SwarmMemory, get_swarm_memory
from .grok import Grok, get_grok, ThoughtChunk

logger = logging.getLogger(__name__)


@dataclass
class SwarmConfig:
    """Configuration for the swarm."""
    perception_interval: int = 60  # Seconds between agent perception cycles
    evolution_interval: int = 3600  # Seconds between strategy evolution
    memory_cleanup_interval: int = 3600  # Seconds between memory cleanup
    max_agents: int = 10


class SwarmNetwork:
    """
    Manages the agent swarm.
    
    Features:
    - Spawn and manage agents
    - Run agents concurrently
    - Broadcast signals
    - Handle thought streaming to UI
    """
    
    def __init__(self, config: SwarmConfig = None):
        self.config = config or SwarmConfig()
        
        # Core components
        self.signal_network = get_signal_network()
        self.memory = get_swarm_memory()
        self.grok = get_grok()
        
        # Agents
        self._agents: Dict[str, EmergentAgent] = {}
        self._agent_tasks: Dict[str, asyncio.Task] = {}
        
        # State
        self._running = False
        self._started_at: Optional[datetime] = None
        
        # UI connections
        self._thought_callbacks: List[callable] = []
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # AGENT MANAGEMENT
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def spawn_agent(self, agent: EmergentAgent) -> bool:
        """
        Add an agent to the swarm.
        
        Returns:
            True if spawned, False if already exists or at capacity
        """
        if agent.id in self._agents:
            logger.warning(f"Agent {agent.id} already in swarm")
            return False
        
        if len(self._agents) >= self.config.max_agents:
            logger.warning(f"Swarm at capacity ({self.config.max_agents})")
            return False
        
        self._agents[agent.id] = agent
        logger.info(f"Agent {agent.name} spawned into swarm")
        
        # If already running, start the agent
        if self._running:
            self._start_agent(agent.id)
        
        return True
    
    def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent from the swarm."""
        if agent_id not in self._agents:
            return False
        
        # Stop agent task if running
        if agent_id in self._agent_tasks:
            self._agent_tasks[agent_id].cancel()
            del self._agent_tasks[agent_id]
        
        del self._agents[agent_id]
        logger.info(f"Agent {agent_id} removed from swarm")
        return True
    
    def get_agent(self, agent_id: str) -> Optional[EmergentAgent]:
        """Get an agent by ID."""
        return self._agents.get(agent_id)
    
    def get_all_agents(self) -> List[EmergentAgent]:
        """Get all agents."""
        return list(self._agents.values())
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SWARM LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def start(self):
        """Start the swarm."""
        if self._running:
            logger.warning("Swarm already running")
            return
        
        self._running = True
        self._started_at = datetime.utcnow()
        
        logger.info("=" * 60)
        logger.info("  EMERGENT AI SWARM STARTING")
        logger.info("=" * 60)
        logger.info(f"  Agents: {len(self._agents)}")
        logger.info(f"  Perception interval: {self.config.perception_interval}s")
        logger.info("=" * 60)
        
        # Subscribe to thought stream for UI
        self.grok.subscribe_to_thoughts(self._handle_thought)
        
        # Start all agents
        for agent_id in self._agents:
            self._start_agent(agent_id)
        
        # Start background tasks
        asyncio.create_task(self._evolution_loop())
        asyncio.create_task(self._memory_cleanup_loop())
        
        logger.info("Swarm started successfully")
    
    async def stop(self):
        """Stop the swarm."""
        if not self._running:
            return
        
        logger.info("Stopping swarm...")
        self._running = False
        
        # Stop all agents
        for agent_id, task in list(self._agent_tasks.items()):
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        self._agent_tasks.clear()
        
        # Unsubscribe from thoughts
        self.grok.unsubscribe_from_thoughts(self._handle_thought)
        
        logger.info("Swarm stopped")
    
    def _start_agent(self, agent_id: str):
        """Start an agent's run loop."""
        if agent_id not in self._agents:
            return
        
        agent = self._agents[agent_id]
        task = asyncio.create_task(agent.run())
        self._agent_tasks[agent_id] = task
        
        logger.info(f"Started agent: {agent.name}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # BACKGROUND TASKS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def _evolution_loop(self):
        """Periodically evolve strategies."""
        while self._running:
            try:
                await asyncio.sleep(self.config.evolution_interval)
                
                # Decay beliefs for all agents
                for agent in self._agents.values():
                    await agent.beliefs.apply_decay()
                
                logger.debug("Evolution cycle completed")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Evolution loop error: {e}")
    
    async def _memory_cleanup_loop(self):
        """Periodically clean up expired memories."""
        while self._running:
            try:
                await asyncio.sleep(self.config.memory_cleanup_interval)
                
                count = await self.memory.forget_expired()
                if count > 0:
                    logger.info(f"Cleaned up {count} expired memories")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory cleanup error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # THOUGHT STREAMING
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def subscribe_to_thoughts(self, callback: callable):
        """Subscribe to thought stream for UI."""
        self._thought_callbacks.append(callback)
    
    def unsubscribe_from_thoughts(self, callback: callable):
        """Unsubscribe from thought stream."""
        if callback in self._thought_callbacks:
            self._thought_callbacks.remove(callback)
    
    async def _handle_thought(self, chunk: ThoughtChunk):
        """Handle incoming thought chunk and forward to subscribers."""
        for callback in self._thought_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(chunk)
                else:
                    callback(chunk)
            except Exception as e:
                logger.warning(f"Thought callback error: {e}")
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def get_status(self) -> Dict:
        """Get swarm status."""
        return {
            "running": self._running,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "agent_count": len(self._agents),
            "agents": [
                agent.get_status() for agent in self._agents.values()
            ],
            "signal_network": {
                "active_agents": self.signal_network.get_agent_count(),
                "recent_signals": len(self.signal_network.get_recent_signals(limit=100)),
            },
            "memory": {
                "cached_memories": len(self.memory),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_swarm_network: Optional[SwarmNetwork] = None


def get_swarm_network(config: SwarmConfig = None) -> SwarmNetwork:
    """Get or create global swarm network."""
    global _swarm_network
    if _swarm_network is None:
        _swarm_network = SwarmNetwork(config)
    return _swarm_network

