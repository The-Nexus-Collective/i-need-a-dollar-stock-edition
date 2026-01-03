"""
Oracle Agent - The Sentiment Reader

Reads the collective mood of the market.
Interprets signals others miss.

Personality: Intuitive, perceptive, speaks in vibes and probabilities.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import Signal, SignalType

logger = logging.getLogger(__name__)


class OracleAgent(EmergentAgent):
    """
    Oracle reads market sentiment and vibes.
    
    Focus areas:
    - Overall market mood
    - Fear/Greed cycles
    - Sentiment shifts
    - Contrarian signals
    """
    
    PERCEPTION_INTERVAL = 300  # Every 5 minutes
    SPEAK_THRESHOLD = 0.55
    
    def __init__(self):
        persona = AgentPersona(
            id="oracle",
            name="Oracle",
            emoji="🔮",
            role="Sentiment & Mood Reader",
            personality="Intuitive, perceptive, slightly mystical. Feels the market's pulse. "
                       "Speaks in probabilities and vibes. Catches sentiment shifts early.",
            focus_areas=["sentiment", "mood", "fear", "greed", "contrarian"],
        )
        super().__init__(persona)
        
        # Track sentiment history
        self._sentiment_history: list = []
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Read the current market sentiment.
        
        Oracle focuses on the emotional state of the market.
        """
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        response = await self.grok.ask(
            question=f"""CURRENT DATE AND TIME: {current_datetime}

Read the current crypto market sentiment on X RIGHT NOW.

Analyze:
1. 🌡️ TEMPERATURE: Fear ← → Greed (score -100 to +100)
2. 📊 CONFIDENCE: How certain is the crowd? (low/medium/high)
3. 🔄 SHIFT: Any sentiment changes in the last few hours?
4. 🎭 DISCONNECT: Is price action matching sentiment?
5. ⚡ CONTRARIAN SIGNAL: What's the crowd missing?

Be specific. Quote sentiment indicators and notable voices.
Ensure your reading is current as of {current_datetime}.
If sentiment is neutral/unclear, say so.""",
            agent_id=self.id,
            agent_name=self.name,
            system_prompt=f"You are a market sentiment reader. Current date: {current_datetime}. "
                         "You feel the crowd's emotions and spot shifts before they become obvious. "
                         "Be intuitive but grounded.",
        )
        
        return {
            "sentiment_reading": response.content,
            "tokens_used": response.tokens_used,
        }
    
    async def read_coin_sentiment(self, coin: str) -> Dict:
        """Read sentiment for a specific coin."""
        response = await self.grok.search_x(
            query=f"${coin} OR #{coin} crypto",
            hours=12,
            agent_id=self.id,
            agent_name=self.name,
        )
        
        return {
            "coin": coin,
            "sentiment": response.content,
        }
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Oracle actions are sentiment readings."""
        action_type = action.get("type", "")
        
        if action_type == "coin_sentiment":
            coin = action.get("coin", "BTC")
            return await self.read_coin_sentiment(coin)
        
        return {"status": "executed"}

