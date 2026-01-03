"""
Base Agent - Foundation for all specialized agents.

Every agent follows the same lifecycle:
1. THINK - Analyze context and reason about what to do
2. ACT - Execute the decided action
3. LOG - Record everything for transparency

Agents communicate through the Orchestrator and share
context via the AgentContext dataclass.
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, TypeVar, Generic
from uuid import UUID, uuid4

from .logbook import AgentLogbook, LogEntry, get_logbook

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class AgentContext:
    """
    Shared context passed between agents in a cycle.
    
    Contains all the information agents need to make decisions.
    """
    cycle_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    # Universe state
    active_coins: List[str] = field(default_factory=list)
    coin_data: Dict[str, Dict] = field(default_factory=dict)
    
    # Market state
    market_regime: str = "normal"  # 'low_vol', 'normal', 'high_vol', 'crisis'
    btc_price: float = 0.0
    btc_change_24h: float = 0.0
    
    # Sentiment data (from SentimentAgent)
    sentiments: Dict[str, Dict] = field(default_factory=dict)
    
    # Strategy proposals (from StrategyEnsemble)
    trade_proposals: List[Dict] = field(default_factory=list)
    strategy_weights: Dict[str, float] = field(default_factory=dict)
    
    # Execution results (from ExecutionAgent)
    executed_trades: List[Dict] = field(default_factory=list)
    
    # Current portfolio state
    portfolio: Dict = field(default_factory=dict)
    open_positions: List[Dict] = field(default_factory=list)
    
    # X discoveries (from DiscoveryAgent)
    x_discoveries: List[Dict] = field(default_factory=list)
    
    # Validation results (from ValidationAgent)
    validated_coins: List[str] = field(default_factory=list)
    rejected_coins: Dict[str, str] = field(default_factory=dict)  # coin -> reason
    
    # Memory recalls (from Learner)
    relevant_memories: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Serialize context for logging."""
        return {
            "cycle_id": str(self.cycle_id),
            "timestamp": self.timestamp.isoformat(),
            "active_coins": self.active_coins,
            "market_regime": self.market_regime,
            "btc_price": self.btc_price,
            "num_sentiments": len(self.sentiments),
            "num_proposals": len(self.trade_proposals),
            "num_positions": len(self.open_positions),
        }


@dataclass
class AgentOutput(Generic[T]):
    """
    Standard output format for all agents.
    
    Contains both the result and the reasoning behind it.
    """
    success: bool = True
    
    # The actual result (agent-specific type)
    data: Optional[T] = None
    
    # Reasoning chain for transparency
    reasoning: str = ""
    decision: str = ""
    
    # Metrics
    confidence: float = 50.0  # 0-100
    duration_ms: int = 0
    tokens_used: int = 0
    
    # Errors
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Serialize for logging."""
        return {
            "success": self.success,
            "data": self.data if isinstance(self.data, (dict, list, str, int, float, bool, type(None))) else str(self.data),
            "reasoning": self.reasoning,
            "decision": self.decision,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "error": self.error,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Every agent must implement:
    - think(): Analyze context and decide what to do
    - act(): Execute the decision
    
    The run() method orchestrates think -> act -> log.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logbook: AgentLogbook = get_logbook()
        self._initialized: bool = False
        self._last_run: Optional[datetime] = None
    
    async def initialize(self):
        """
        Initialize the agent (load models, connect to services, etc.)
        Override in subclasses if needed.
        """
        self._initialized = True
        logger.info(f"Agent {self.name} initialized")
    
    @abstractmethod
    async def think(self, context: AgentContext) -> AgentOutput:
        """
        Analyze context and decide what to do.
        
        This is where Grok/LLM calls happen.
        Must return an AgentOutput with reasoning.
        """
        pass
    
    @abstractmethod
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """
        Execute the decision from think().
        
        Performs actual actions (API calls, trades, etc.)
        Returns the final output with results.
        """
        pass
    
    async def run(self, context: AgentContext) -> AgentOutput:
        """
        Main agent lifecycle: think -> act -> log.
        
        This is the only method called by the Orchestrator.
        All activities are logged for transparency.
        """
        start_time = time.time()
        
        if not self._initialized:
            await self.initialize()
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # THINK - Analyze and reason
            # ═══════════════════════════════════════════════════════════════
            think_start = time.time()
            
            thought = await self.think(context)
            
            think_duration = int((time.time() - think_start) * 1000)
            thought.duration_ms = think_duration
            
            # Log the thinking
            await self.logbook.log(
                agent_name=self.name,
                action_type="think",
                reasoning=thought.reasoning,
                input_context=context.to_dict(),
                decision=thought.decision,
                confidence=thought.confidence,
                duration_ms=think_duration,
                tokens_used=thought.tokens_used,
                triggered_by="orchestrator",
            )
            
            # If thinking failed, don't act
            if not thought.success:
                return thought
            
            # ═══════════════════════════════════════════════════════════════
            # ACT - Execute the decision
            # ═══════════════════════════════════════════════════════════════
            act_start = time.time()
            
            result = await self.act(context, thought)
            
            act_duration = int((time.time() - act_start) * 1000)
            result.duration_ms = act_duration
            
            # Log the action
            await self.logbook.log(
                agent_name=self.name,
                action_type="act",
                reasoning=result.reasoning,
                input_context={"thought": thought.decision},
                decision=result.decision,
                output_data=result.to_dict(),
                confidence=result.confidence,
                duration_ms=act_duration,
            )
            
            self._last_run = datetime.utcnow()
            
            # Calculate total duration
            total_duration = int((time.time() - start_time) * 1000)
            result.duration_ms = total_duration
            
            return result
            
        except Exception as e:
            # Log error
            error_msg = f"Agent {self.name} error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            await self.logbook.log(
                agent_name=self.name,
                action_type="error",
                reasoning=error_msg,
                input_context=context.to_dict(),
                confidence=0,
            )
            
            return AgentOutput(
                success=False,
                error=error_msg,
                reasoning=f"Agent failed with error: {str(e)}",
            )
    
    async def reflect(self, context: AgentContext, result: AgentOutput) -> str:
        """
        Optional post-action reflection.
        
        Override to add learning/reflection capabilities.
        Called by Orchestrator after all agents have run.
        """
        return ""
    
    def get_status(self) -> Dict:
        """Get agent status for monitoring."""
        return {
            "name": self.name,
            "initialized": self._initialized,
            "last_run": self._last_run.isoformat() if self._last_run else None,
        }


class GrokAgent(BaseAgent):
    """
    Base class for agents that use Grok AI for reasoning.
    
    Provides common Grok API functionality.
    """
    
    def __init__(self, name: str):
        super().__init__(name)
        self._grok_client = None
    
    async def initialize(self):
        """Initialize Grok client."""
        import os
        import httpx
        
        api_key = os.getenv("XAI_API_KEY", "")
        if not api_key:
            logger.warning(f"Agent {self.name}: XAI_API_KEY not set!")
        
        self._grok_client = httpx.AsyncClient(timeout=60)
        self._grok_api_key = api_key
        self._grok_base_url = "https://api.x.ai/v1"
        
        await super().initialize()
    
    async def call_grok(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> tuple[str, int]:
        """
        Call Grok API for reasoning.
        
        Returns:
            Tuple of (response_text, tokens_used)
        """
        if not self._grok_api_key:
            return "Grok API key not configured", 0
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await self._grok_client.post(
                f"{self._grok_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._grok_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "grok-3",
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                return content, tokens
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return f"API error: {response.status_code}", 0
                
        except Exception as e:
            logger.error(f"Grok call failed: {e}")
            return f"Error: {str(e)}", 0
    
    async def shutdown(self):
        """Close Grok client."""
        if self._grok_client:
            await self._grok_client.aclose()

