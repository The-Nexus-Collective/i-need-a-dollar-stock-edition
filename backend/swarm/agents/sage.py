"""
Sage Agent - The Learner

Reflects on outcomes and stores lessons.
Manages long-term memory and pattern recognition.

Personality: Wise, patient, learns from everything. Remembers everything.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import Signal, SignalType
from ..memory import get_swarm_memory

logger = logging.getLogger(__name__)


class SageAgent(EmergentAgent):
    """
    Sage learns from experience and maintains memory.
    
    Responsibilities:
    - Reflect on trade outcomes
    - Extract lessons learned
    - Store insights in long-term memory
    - Recall relevant past experiences
    - Update hypotheses based on outcomes
    """
    
    PERCEPTION_INTERVAL = 600  # Less frequent - focused on reflection
    SPEAK_THRESHOLD = 0.6
    
    def __init__(self):
        persona = AgentPersona(
            id="sage",
            name="Sage",
            emoji="🧙",
            role="Learning & Memory",
            personality="Wise, patient, reflective. Finds patterns across time. "
                       "Speaks in lessons and wisdom. Remembers everything important.",
            focus_areas=["learning", "patterns", "memory", "lessons", "history"],
        )
        super().__init__(persona)
        
        self._memory = get_swarm_memory()
        
        # Track outcomes to reflect on
        self._pending_reflections: List[Dict] = []
    
    def is_interested(self, signal: Signal) -> bool:
        """Sage is interested in results and outcomes."""
        if super().is_interested(signal):
            return True
        
        # Interested in results (trade outcomes)
        if signal.type == SignalType.RESULT:
            return True
        
        # Interested in all significant insights
        if signal.importance > 0.7:
            return True
        
        return False
    
    async def receive_signal(self, signal: Signal):
        """Queue significant signals for reflection."""
        await super().receive_signal(signal)
        
        # Queue results for reflection
        if signal.type == SignalType.RESULT:
            self._pending_reflections.append({
                "type": "trade_result",
                "signal": signal.to_dict(),
            })
        
        # Store important insights in memory
        if signal.importance > 0.7 and signal.type == SignalType.INSIGHT:
            await self._memory.remember(
                insight=signal.content,
                category="insight",
                context={"sender": signal.sender_name, "topic": signal.topic},
                importance=signal.importance,
                source_agent=signal.sender_id,
            )
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Sage perception = review and reflection.
        
        Looks for patterns and lessons.
        """
        # If there are pending reflections, process them
        if self._pending_reflections:
            reflection = self._pending_reflections.pop(0)
            
            response = await self.grok.ask(
                question=f"""Reflect on this outcome:

{reflection}

What can we learn?
1. 📚 LESSON: What does this teach us?
2. 🔄 PATTERN: Does this match any known pattern?
3. ✅ WHAT WORKED: What should we repeat?
4. ❌ WHAT FAILED: What should we avoid?
5. 💡 INSIGHT: Any new hypothesis to test?

Be specific and actionable.""",
                agent_id=self.id,
                agent_name=self.name,
                system_prompt="You are a trading sage. Extract wisdom from experience. "
                             "Focus on actionable lessons.",
            )
            
            return {
                "reflection_type": reflection.get("type"),
                "reflection": response.content,
                "tokens_used": response.tokens_used,
            }
        
        # No pending reflections - do a general wisdom check
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        recent_memories = self._memory.get_recent(limit=5)
        memories_text = "\n".join([m.insight[:100] for m in recent_memories])
        
        response = await self.grok.ask(
            question=f"""CURRENT DATE AND TIME: {current_datetime}

Review recent observations and find patterns.

Recent memories:
{memories_text or "(No recent memories)"}

Current beliefs:
{self.beliefs.to_prompt()}

Look for:
1. Patterns across different events
2. Beliefs that need updating based on current market conditions ({current_datetime})
3. Lessons the team should remember

What wisdom should be shared?""",
            agent_id=self.id,
            agent_name=self.name,
            system_prompt=f"You are a pattern-finding sage. Current date: {current_datetime}. "
                         "Connect dots others miss.",
        )
        
        return {
            "wisdom": response.content,
            "memories_reviewed": len(recent_memories),
            "tokens_used": response.tokens_used,
        }
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Sage actions are memory operations."""
        action_type = action.get("type", "")
        
        if action_type == "store_memory":
            memory = await self._memory.remember(
                insight=action.get("insight", ""),
                category=action.get("category", "general"),
                importance=action.get("importance", 0.5),
                source_agent=self.id,
            )
            return {"stored": True, "memory_id": str(memory.id)}
        
        if action_type == "recall":
            situation = action.get("situation", "")
            memories = await self._memory.recall(situation, limit=5)
            return {
                "recalled": len(memories),
                "memories": [m.insight[:100] for m in memories],
            }
        
        return {"status": "executed"}

