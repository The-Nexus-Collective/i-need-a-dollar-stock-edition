"""
EmergentAgent - The Foundation of Autonomous Behavior

Each agent has simple core rules that produce complex emergent behavior:
1. PERCEIVE - Observe the world through Grok
2. THINK - Form beliefs, update hypotheses
3. SPEAK - Share insights when significant
4. ACT - Take action when conviction is high

Agents operate independently in their own loops.
They communicate only through signals.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from uuid import UUID, uuid4

from .grok import Grok, get_grok, GrokResponse, ThoughtChunk
from .signals import Signal, SignalType, SignalNetwork, get_signal_network
from .beliefs import Belief, BeliefSystem
from .hypotheses import Hypothesis

logger = logging.getLogger(__name__)


@dataclass
class Thought:
    """Result of agent thinking."""
    content: str
    summary: str = ""
    
    # Decisions
    action_needed: bool = False
    proposed_action: Optional[Dict] = None
    
    # Metrics
    significance: float = 0.5      # How significant is this thought? (0-1)
    confidence: float = 0.5        # How confident are we? (0-1)
    conviction: float = 0.5        # Confidence * significance
    
    # Updates
    belief_updates: List[Dict] = field(default_factory=list)
    hypothesis_updates: List[Dict] = field(default_factory=list)
    
    # Raw data
    tokens_used: int = 0
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "summary": self.summary,
            "action_needed": self.action_needed,
            "proposed_action": self.proposed_action,
            "significance": self.significance,
            "confidence": self.confidence,
            "conviction": self.conviction,
            "tokens_used": self.tokens_used,
        }


@dataclass
class AgentPersona:
    """The identity and personality of an agent."""
    id: str
    name: str
    emoji: str
    role: str
    personality: str
    focus_areas: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "emoji": self.emoji,
            "role": self.role,
            "personality": self.personality,
            "focus_areas": self.focus_areas,
        }


class EmergentAgent(ABC):
    """
    Base class for all emergent agents.
    
    Each agent has:
    - A unique persona (identity)
    - Beliefs about the world
    - Hypotheses being tested
    - Energy level (attention/activity)
    
    Agents run in their own async loops, perceiving/thinking/acting.
    """
    
    # Thresholds for behavior
    SPEAK_THRESHOLD = 0.6      # Speak if significance > this
    ACT_THRESHOLD = 0.7        # Act if conviction > this
    
    # Timing
    PERCEPTION_INTERVAL = 60   # Seconds between perception cycles
    
    def __init__(self, persona: AgentPersona):
        self.persona = persona
        self.id = persona.id
        self.name = persona.name
        
        # Core state
        self.beliefs = BeliefSystem()
        self.hypotheses: List[Hypothesis] = []
        self.energy: float = 0.5  # Activity level (0-1)
        
        # Context
        self._pending_signals: asyncio.Queue = asyncio.Queue()
        self._interests: Set[str] = set(persona.focus_areas)
        
        # Status
        self._running: bool = False
        self._last_perception: Optional[datetime] = None
        self._last_thought: Optional[Thought] = None
        
        # Connections
        self.grok: Grok = get_grok()
        self.network: SignalNetwork = get_signal_network()
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # CORE LOOP
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def run(self):
        """
        Main agent loop - perceive, think, speak, act.
        
        Runs until stopped.
        """
        self._running = True
        logger.info(f"Agent {self.name} starting...")
        
        # Register with signal network
        self.network.register_agent(self.id, self)
        
        # Announce presence
        await self._broadcast_signal(
            SignalType.HEARTBEAT,
            "status",
            f"{self.persona.emoji} {self.name} is online and ready.",
            confidence=1.0,
        )
        
        try:
            while self._running:
                await self._cycle()
                await asyncio.sleep(self.PERCEPTION_INTERVAL)
        except asyncio.CancelledError:
            logger.info(f"Agent {self.name} cancelled")
        except Exception as e:
            logger.error(f"Agent {self.name} error: {e}", exc_info=True)
        finally:
            self.network.unregister_agent(self.id)
            logger.info(f"Agent {self.name} stopped")
    
    async def _cycle(self):
        """Single perception-thought-action cycle."""
        logger.info(f"Agent {self.name} starting perception cycle...")
        
        try:
            # 1. Process pending signals
            signals = await self._collect_signals()
            logger.debug(f"Agent {self.name} collected {len(signals)} signals")
            
            # 2. Perceive the world
            perception = await self.perceive()
            logger.info(f"Agent {self.name} perceived: {str(perception)[:100]}...")
            
            # 3. Think about signals + perception
            thought = await self.think(signals, perception)
            self._last_thought = thought
            logger.info(f"Agent {self.name} thought: {thought.summary[:100] if thought.summary else 'no summary'}")
            
            # 4. Maybe speak
            message = await self.speak(thought)
            if message:
                logger.info(f"Agent {self.name} spoke: {message.content[:100]}...")
            
            # 5. Maybe act
            action = await self.act(thought)
            if action:
                logger.info(f"Agent {self.name} acted: {action}")
            
            # Update timestamps
            self._last_perception = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Agent {self.name} cycle error: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the agent loop."""
        self._running = False
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # THE FOUR CORE METHODS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    @abstractmethod
    async def perceive(self) -> Dict[str, Any]:
        """
        Rule 1: PERCEIVE
        
        Ask Grok what's happening. No predefined queries.
        The question depends on current beliefs and energy.
        
        Override this to define what the agent pays attention to.
        
        Returns:
            Observations from the world
        """
        pass
    
    async def think(
        self,
        signals: List[Signal],
        perception: Dict[str, Any]
    ) -> Thought:
        """
        Rule 2: THINK
        
        Form beliefs, update hypotheses, consider actions.
        Thinking is streamed to observers in real-time.
        """
        # Build context from signals and perception
        context = self._build_thinking_context(signals, perception)
        
        # Get current date/time
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        # Ask Grok to think
        system_prompt = f"""You are {self.name}, {self.persona.role}.
Personality: {self.persona.personality}

CURRENT DATE AND TIME: {current_datetime}

Current beliefs:
{self.beliefs.to_prompt()}

Your task is to think out loud about the situation and decide what to do.
Be yourself - think in character. Consider the current date when analyzing news and market conditions."""

        response = await self.grok.ask(
            question=context,
            agent_id=self.id,
            agent_name=self.name,
            system_prompt=system_prompt,
            stream=True,
        )
        
        # Parse the thought
        thought = self._parse_thought(response)
        
        # Update beliefs based on thought
        await self._update_beliefs(thought)
        
        return thought
    
    async def speak(self, thought: Thought) -> Optional[Signal]:
        """
        Rule 3: SPEAK (maybe)
        
        Only speak if you have something worth sharing.
        Other agents are listening.
        """
        if thought.significance < self.SPEAK_THRESHOLD:
            return None
        
        # Create a signal
        signal = await self._broadcast_signal(
            SignalType.INSIGHT,
            self._get_current_topic(),
            thought.summary or thought.content[:500],
            confidence=thought.confidence,
            importance=thought.significance,
        )
        
        return signal
    
    async def act(self, thought: Thought) -> Optional[Dict]:
        """
        Rule 4: ACT (maybe)
        
        Only act if conviction is high enough.
        Actions affect the shared state.
        """
        if not thought.action_needed or thought.conviction < self.ACT_THRESHOLD:
            return None
        
        action = thought.proposed_action
        if not action:
            return None
        
        # Execute the action
        result = await self._execute_action(action)
        
        # Broadcast result
        await self._broadcast_signal(
            SignalType.ACTION,
            action.get("type", "action"),
            f"Executed: {action.get('description', 'unknown action')}",
            confidence=thought.confidence,
            data=result,
        )
        
        return result
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SIGNAL HANDLING
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def is_interested(self, signal: Signal) -> bool:
        """Check if this agent is interested in a signal."""
        # Always interested if mentioned
        if self.id in signal.mentions or self.name in signal.mentions:
            return True
        
        # Check topic/tags against interests
        topic_words = set(signal.topic.lower().split())
        tag_set = set(t.lower() for t in signal.tags)
        
        for interest in self._interests:
            if interest.lower() in topic_words or interest.lower() in tag_set:
                return True
        
        # High importance signals are always interesting
        if signal.importance > 0.8:
            return True
        
        return False
    
    async def receive_signal(self, signal: Signal):
        """Receive a signal from the network."""
        await self._pending_signals.put(signal)
    
    async def _collect_signals(self) -> List[Signal]:
        """Collect all pending signals."""
        signals = []
        while not self._pending_signals.empty():
            try:
                signal = self._pending_signals.get_nowait()
                signals.append(signal)
            except asyncio.QueueEmpty:
                break
        return signals
    
    async def _broadcast_signal(
        self,
        signal_type: SignalType,
        topic: str,
        content: str,
        confidence: float = 0.5,
        urgency: float = 0.5,
        importance: float = 0.5,
        mentions: List[str] = None,
        tags: List[str] = None,
        data: Dict = None,
    ) -> Signal:
        """Broadcast a signal to the network."""
        signal = Signal(
            sender_id=self.id,
            sender_name=self.name,
            type=signal_type,
            topic=topic,
            content=content,
            confidence=confidence,
            urgency=urgency,
            importance=importance,
            mentions=mentions or [],
            tags=tags or [],
            data=data or {},
        )
        
        await self.network.broadcast(signal)
        return signal
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # HELPER METHODS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def _build_thinking_context(
        self,
        signals: List[Signal],
        perception: Dict[str, Any]
    ) -> str:
        """Build context prompt for thinking."""
        parts = []
        
        # Current timestamp at the top
        now = datetime.utcnow()
        parts.append(f"## Current Time: {now.strftime('%A, %B %d, %Y at %H:%M:%S UTC')}\n")
        
        # Perception
        if perception:
            parts.append("## What I just observed:\n")
            for key, value in perception.items():
                if isinstance(value, str):
                    parts.append(f"- {key}: {value[:500]}...")
                else:
                    parts.append(f"- {key}: {value}")
            parts.append("")
        
        # Signals from other agents
        if signals:
            parts.append("## Messages from other agents:\n")
            for signal in signals[-10:]:  # Last 10 signals
                parts.append(
                    f"- {signal.sender_name}: [{signal.type.value}] {signal.content[:200]}..."
                )
            parts.append("")
        
        # Thinking prompt
        parts.append("""## Think out loud:
- What does this mean given the current date and market context?
- Does this change any of my beliefs?
- Any hypotheses confirmed or disproven?
- Should I share something with the team?
- Should I take action?

If action is needed, describe what action and why.""")
        
        return "\n".join(parts)
    
    def _parse_thought(self, response: GrokResponse) -> Thought:
        """Parse Grok response into a Thought."""
        import json
        import re
        
        content = response.content
        
        # Extract summary (first sentence or line)
        lines = content.strip().split('\n')
        summary = lines[0][:200] if lines else ""
        
        # Try to extract JSON trade decision from response
        proposed_action = None
        action_needed = False
        conviction = 0.5
        
        # Look for JSON block in response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if not json_match:
            json_match = re.search(r'```\s*([\s\S]*?)\s*```', content)
        if not json_match:
            # Try to find raw JSON object
            json_match = re.search(r'\{[\s\S]*?"decision"[\s\S]*?\}', content)
        
        if json_match:
            try:
                json_str = json_match.group(1) if json_match.lastindex else json_match.group(0)
                decision_data = json.loads(json_str.strip())
                
                if decision_data.get("decision") == "TRADE":
                    # This is a trade proposal
                    proposed_action = {
                        "type": "trade",
                        "description": f"{decision_data.get('direction', 'LONG')} {decision_data.get('coin', 'BTC')}",
                        "coin": decision_data.get("coin"),
                        "direction": decision_data.get("direction"),
                        "size_percent": decision_data.get("size_percent", 5),
                        "stop_loss_percent": decision_data.get("stop_loss_percent", 3),
                        "take_profit_percent": decision_data.get("take_profit_percent", 6),
                        "conviction": decision_data.get("conviction", 0),
                        "reasoning": decision_data.get("reasoning", ""),
                    }
                    action_needed = True
                    conviction = decision_data.get("conviction", 50) / 100.0  # Convert to 0-1 scale
                elif decision_data.get("decision") in ["WAIT", "PASS"]:
                    conviction = decision_data.get("conviction", 30) / 100.0
                    
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.debug(f"Failed to parse JSON from thought: {e}")
        
        # Fallback heuristics for action detection if no JSON
        if not proposed_action:
            action_keywords = [
                "should take action", "need to act", "execute",
                "buy", "sell", "trade", "alert the team"
            ]
            action_needed = any(kw in content.lower() for kw in action_keywords)
        
        # Estimate significance based on language
        high_significance_words = [
            "important", "critical", "breaking", "urgent",
            "significant", "major", "alert", "warning", "trade", "opportunity"
        ]
        word_count = sum(1 for w in high_significance_words if w in content.lower())
        significance = min(0.9, 0.4 + word_count * 0.1)
        
        # Confidence from Grok's language (if no JSON conviction)
        if conviction == 0.5:
            confident_words = ["clearly", "definitely", "certain", "confident", "strong"]
            uncertain_words = ["maybe", "perhaps", "uncertain", "unclear", "might"]
            confident_count = sum(1 for w in confident_words if w in content.lower())
            uncertain_count = sum(1 for w in uncertain_words if w in content.lower())
            confidence = min(0.9, max(0.2, 0.5 + confident_count * 0.1 - uncertain_count * 0.1))
        else:
            confidence = conviction
        
        return Thought(
            content=content,
            summary=summary,
            action_needed=action_needed,
            proposed_action=proposed_action,
            significance=significance,
            confidence=confidence,
            conviction=significance * conviction if proposed_action else significance * confidence,
            tokens_used=response.tokens_used,
        )
    
    async def _update_beliefs(self, thought: Thought):
        """Update beliefs based on thought."""
        # This is a placeholder - beliefs should be updated based on
        # the content of the thought and its outcomes
        pass
    
    def _get_current_topic(self) -> str:
        """Get current focus topic."""
        if self._interests:
            return list(self._interests)[0]
        return "general"
    
    async def _execute_action(self, action: Dict) -> Dict:
        """
        Execute an action. Override in subclasses.
        
        Default implementation just logs the action.
        """
        logger.info(f"Agent {self.name} executing action: {action}")
        return {"status": "executed", "action": action}
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # STATUS
    # ═══════════════════════════════════════════════════════════════════════════════
    
    def get_status(self) -> Dict:
        """Get agent status."""
        return {
            "id": self.id,
            "name": self.name,
            "emoji": self.persona.emoji,
            "role": self.persona.role,
            "running": self._running,
            "energy": self.energy,
            "beliefs_count": len(self.beliefs._beliefs),
            "hypotheses_count": len(self.hypotheses),
            "last_perception": self._last_perception.isoformat() if self._last_perception else None,
            "pending_signals": self._pending_signals.qsize(),
        }

