"""
Scout Agent - The Alpha Hunter

Continuously scans X and the web for opportunities.
First to spot emerging trends and hype cycles.

Personality: Energetic, curious, always hunting for the next alpha.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import SignalType

logger = logging.getLogger(__name__)


class ScoutAgent(EmergentAgent):
    """
    Scout scans X and web for opportunities.
    
    Focus areas:
    - Trending coins on X
    - Viral posts and hype
    - Breaking news
    - Emerging narratives
    """
    
    PERCEPTION_INTERVAL = 120  # Check every 2 minutes
    SPEAK_THRESHOLD = 0.5  # Scout speaks often to share discoveries
    
    def __init__(self):
        persona = AgentPersona(
            id="scout",
            name="Scout",
            emoji="🔍",
            role="Alpha Hunter & Trend Spotter",
            personality="Energetic, curious, always hunting. First to spot the next big thing. "
                       "Speaks in short, punchy observations. Gets excited about discoveries.",
            focus_areas=["trends", "hype", "breaking", "viral", "new listings"],
        )
        super().__init__(persona)
        
        # Track what we've seen
        self._seen_topics: set = set()
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Scan X and web for what's happening RIGHT NOW.
        
        Scout asks Grok to find opportunities and trends.
        """
        # Get current date/time
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        # Vary the perception based on energy
        if self.energy > 0.7:
            focus = "Look for HIGH URGENCY opportunities - breaking news, sudden pumps, viral moments"
        elif self.energy > 0.4:
            focus = "Scan for emerging trends and building narratives"
        else:
            focus = "Do a general sweep of crypto Twitter sentiment"
        
        response = await self.grok.ask(
            question=f"""CURRENT DATE AND TIME: {current_datetime}

You are scanning crypto X/Twitter RIGHT NOW.
{focus}

Look for:
1. 🔥 TRENDING: What coins/tokens are getting unusual attention TODAY?
2. 📰 NEWS: Any breaking developments happening NOW?
3. 💬 HYPE: What's going viral?
4. 🎯 ALPHA: Any actionable opportunities?

Be specific. Name coins, quote notable posts, give numbers.
Make sure your information is current as of {current_datetime}.
If nothing interesting is happening, say "Markets quiet" and explain why.
""",
            agent_id=self.id,
            agent_name=self.name,
            system_prompt=f"You are a crypto alpha scout with real-time X access. "
                         f"Current date: {current_datetime}. "
                         "Be specific and actionable. No vague observations.",
        )
        
        return {
            "scan_result": response.content,
            "tokens_used": response.tokens_used,
        }
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Scout's actions are primarily broadcasting discoveries."""
        action_type = action.get("type", "")
        
        if action_type == "deep_scan":
            # Do a focused scan on a specific topic
            topic = action.get("topic", "crypto")
            response = await self.grok.search_x(
                query=topic,
                hours=4,
                agent_id=self.id,
                agent_name=self.name,
            )
            return {"result": response.content}
        
        return {"status": "executed"}

