"""
Analyst Agent - The Deep Researcher

Does thorough due diligence on projects.
Skeptical and detail-oriented.

Personality: Methodical, skeptical, thorough. Finds the truth.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import Signal, SignalType

logger = logging.getLogger(__name__)


class AnalystAgent(EmergentAgent):
    """
    Analyst does deep research on opportunities.
    
    Triggered by Scout discoveries or team mentions.
    Takes time but provides thorough analysis.
    """
    
    PERCEPTION_INTERVAL = 180  # Less frequent perception
    SPEAK_THRESHOLD = 0.6
    ACT_THRESHOLD = 0.75
    
    def __init__(self):
        persona = AgentPersona(
            id="analyst",
            name="Analyst",
            emoji="🔬",
            role="Due Diligence & Research",
            personality="Methodical, skeptical, thorough. Digs deep. Always looks for red flags. "
                       "Speaks in structured analysis. Values data over hype.",
            focus_areas=["research", "due diligence", "tokenomics", "team", "red flags"],
        )
        super().__init__(persona)
        
        # Queue of projects to research
        self._research_queue: List[str] = []
    
    def is_interested(self, signal: Signal) -> bool:
        """Analyst is interested in discoveries and research requests."""
        # Interested if mentioned
        if super().is_interested(signal):
            return True
        
        # Interested in discoveries from Scout
        if signal.type == SignalType.DISCOVERY and signal.sender_id == "scout":
            return True
        
        return False
    
    async def receive_signal(self, signal: Signal):
        """Handle incoming signals, especially research requests."""
        await super().receive_signal(signal)
        
        # If this is a discovery, queue it for research
        if signal.type == SignalType.DISCOVERY:
            # Extract coin/project name from signal
            coins = signal.data.get("coins", [])
            for coin in coins:
                if coin not in self._research_queue:
                    self._research_queue.append(coin)
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Analyst perception is triggered by research queue.
        
        If there's something to research, do deep research.
        Otherwise, look for things that need analysis.
        """
        if self._research_queue:
            # Research the next item in queue
            project = self._research_queue.pop(0)
            
            response = await self.grok.research_project(
                name=project,
                agent_id=self.id,
                agent_name=self.name,
            )
            
            return {
                "research_target": project,
                "research_result": response.content,
                "tokens_used": response.tokens_used,
            }
        
        # No queue - look for things to analyze
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        response = await self.grok.ask(
            question=f"""CURRENT DATE AND TIME: {current_datetime}

Review recent crypto developments and identify:

1. Projects that need deeper research
2. Claims that should be fact-checked
3. Narratives that seem overhyped vs reality

Focus on things that could affect trading decisions TODAY.
Be skeptical and critical. Ensure your analysis is current as of {current_datetime}.""",
            agent_id=self.id,
            agent_name=self.name,
            system_prompt=f"You are a crypto research analyst. Current date: {current_datetime}. "
                         "Be thorough and skeptical.",
        )
        
        return {
            "analysis": response.content,
            "tokens_used": response.tokens_used,
        }
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Execute research actions."""
        action_type = action.get("type", "")
        
        if action_type == "deep_research":
            target = action.get("target", "")
            if target:
                response = await self.grok.research_project(
                    name=target,
                    agent_id=self.id,
                    agent_name=self.name,
                )
                return {
                    "target": target,
                    "research": response.content,
                }
        
        return {"status": "executed"}

