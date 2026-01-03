"""
Sentiment Agent - Analyzes market sentiment via Grok AI.

Responsibilities:
1. Batch sentiment analysis for active universe
2. Fuse X sentiment + narrative momentum + market context
3. Generate conviction scores (-100 to +100)
4. Identify market regime and narratives

This is the primary reasoning engine using Grok-3.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .base import GrokAgent, AgentContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class CoinSentiment:
    """Sentiment analysis for a single coin."""
    coin: str
    
    # Scores
    sentiment_score: float = 0  # -100 to +100
    narrative_strength: float = 0  # 0 to 100
    combined_score: float = 0  # sentiment * (narrative/100)
    
    # Context
    key_driver: str = ""
    current_narrative: str = ""
    
    # Confidence
    confidence: float = 50
    
    # Action
    recommended_action: str = "hold"  # 'long', 'short', 'hold'
    
    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "sentiment_score": self.sentiment_score,
            "narrative_strength": self.narrative_strength,
            "combined_score": self.combined_score,
            "key_driver": self.key_driver,
            "current_narrative": self.current_narrative,
            "confidence": self.confidence,
            "recommended_action": self.recommended_action,
        }


@dataclass
class SentimentOutput:
    """Output from Sentiment Agent."""
    sentiments: Dict[str, CoinSentiment]
    market_regime: str
    dominant_narratives: List[str]
    overall_market_sentiment: float
    
    # Raw Grok response for logging
    raw_response: str = ""
    tokens_used: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "sentiments": {k: v.to_dict() for k, v in self.sentiments.items()},
            "market_regime": self.market_regime,
            "dominant_narratives": self.dominant_narratives,
            "overall_market_sentiment": self.overall_market_sentiment,
            "tokens_used": self.tokens_used,
        }


class SentimentAgent(GrokAgent):
    """
    Analyzes sentiment for the active trading universe.
    
    Uses Grok-3 for:
    - Real-time sentiment scoring
    - Narrative detection
    - Market regime classification
    """
    
    # System prompt for consistent responses
    SYSTEM_PROMPT = """You are an expert crypto market analyst. Your task is to analyze current market sentiment for cryptocurrencies.

For each coin, provide:
1. Sentiment score (-100 to +100): Negative = bearish, Positive = bullish
2. Narrative strength (0 to 100): How strong is the current narrative/hype
3. Key driver: Main factor driving sentiment (1-3 words)

Be precise and data-driven. Consider:
- Recent price action
- Social media buzz
- News and developments
- Technical levels
- Macro environment

Format your response as:
COIN: sentiment, narrative_strength, key_driver

Example:
BTC: 65, 80, ETF inflows
ETH: -15, 45, L2 competition"""

    def __init__(self):
        super().__init__("sentiment")
        self._last_sentiments: Dict[str, CoinSentiment] = {}
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Prepare sentiment analysis request."""
        coins = context.validated_coins or context.active_coins
        
        if not coins:
            return AgentOutput(
                success=False,
                reasoning="No coins to analyze",
                decision="skip",
                confidence=0,
            )
        
        # Limit batch size for API efficiency
        coins_to_analyze = coins[:30]
        
        reasoning = f"Analyzing sentiment for {len(coins_to_analyze)} coins: {', '.join(coins_to_analyze[:10])}"
        
        return AgentOutput(
            success=True,
            data={"coins": coins_to_analyze},
            reasoning=reasoning,
            decision="analyze_batch",
            confidence=90,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Execute sentiment analysis via Grok."""
        coins = thought.data.get("coins", [])
        
        if not coins:
            return AgentOutput(
                success=False,
                reasoning="No coins provided for analysis",
                decision="skip",
            )
        
        # Build prompt
        prompt = self._build_analysis_prompt(coins, context)
        
        # Call Grok
        response, tokens = await self.call_grok(
            prompt,
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2000,
        )
        
        # Parse response
        sentiments = self._parse_response(response, coins)
        
        # Determine market regime
        market_regime = self._determine_regime(sentiments, context)
        
        # Extract narratives
        narratives = self._extract_narratives(sentiments)
        
        # Calculate overall sentiment
        scores = [s.combined_score for s in sentiments.values()]
        overall = sum(scores) / len(scores) if scores else 0
        
        # Update context
        context.sentiments = {k: v.to_dict() for k, v in sentiments.items()}
        context.market_regime = market_regime
        
        # Cache sentiments
        self._last_sentiments = sentiments
        
        output = SentimentOutput(
            sentiments=sentiments,
            market_regime=market_regime,
            dominant_narratives=narratives,
            overall_market_sentiment=overall,
            raw_response=response,
            tokens_used=tokens,
        )
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=f"Analyzed {len(sentiments)} coins. Market regime: {market_regime}. Overall sentiment: {overall:.1f}",
            decision=f"regime_{market_regime}_sentiment_{int(overall)}",
            confidence=85,
            tokens_used=tokens,
        )
    
    def _build_analysis_prompt(self, coins: List[str], context: AgentContext) -> str:
        """Build the analysis prompt with context."""
        # Add market context
        market_context = []
        if context.btc_price:
            market_context.append(f"BTC price: ${context.btc_price:,.0f}")
        if context.btc_change_24h:
            market_context.append(f"BTC 24h change: {context.btc_change_24h:+.1f}%")
        
        # Add X discoveries if any
        x_context = ""
        if context.x_discoveries:
            trending = [d.get("coin", "") for d in context.x_discoveries[:5]]
            x_context = f"\nTrending on X: {', '.join(trending)}"
        
        prompt = f"""Analyze current sentiment for these cryptocurrencies:

{', '.join(coins)}

Market context:
{' | '.join(market_context) if market_context else 'Standard market conditions'}
{x_context}

Provide sentiment (-100 to +100), narrative strength (0-100), and key driver for each coin.
Format: COIN: sentiment, narrative_strength, key_driver"""

        return prompt
    
    def _parse_response(self, response: str, expected_coins: List[str]) -> Dict[str, CoinSentiment]:
        """Parse Grok response into structured sentiment data."""
        sentiments = {}
        
        # Parse each line
        for line in response.strip().split('\n'):
            line = line.strip()
            if not line or ':' not in line:
                continue
            
            try:
                # Parse format: COIN: sentiment, narrative, driver
                parts = line.split(':', 1)
                if len(parts) != 2:
                    continue
                
                coin = parts[0].strip().upper()
                values = parts[1].strip()
                
                # Extract numbers
                numbers = re.findall(r'-?\d+(?:\.\d+)?', values)
                
                if len(numbers) >= 2:
                    sentiment = float(numbers[0])
                    narrative = float(numbers[1])
                    
                    # Clamp values
                    sentiment = max(-100, min(100, sentiment))
                    narrative = max(0, min(100, narrative))
                    
                    # Extract driver (text after numbers)
                    driver_match = re.search(r',\s*\d+\s*,\s*(.+)$', values)
                    driver = driver_match.group(1).strip() if driver_match else ""
                    
                    # Calculate combined score
                    combined = sentiment * (narrative / 100)
                    
                    # Determine action
                    if abs(combined) < 20:
                        action = "hold"
                    elif combined > 0:
                        action = "long"
                    else:
                        action = "short"
                    
                    sentiments[coin] = CoinSentiment(
                        coin=coin,
                        sentiment_score=sentiment,
                        narrative_strength=narrative,
                        combined_score=combined,
                        key_driver=driver,
                        recommended_action=action,
                        confidence=min(90, 50 + abs(sentiment) * 0.4),
                    )
                    
            except Exception as e:
                logger.debug(f"Failed to parse line: {line} - {e}")
        
        # Fill in missing coins with neutral sentiment
        for coin in expected_coins:
            if coin not in sentiments:
                sentiments[coin] = CoinSentiment(
                    coin=coin,
                    confidence=30,
                )
        
        return sentiments
    
    def _determine_regime(
        self,
        sentiments: Dict[str, CoinSentiment],
        context: AgentContext
    ) -> str:
        """Determine current market regime."""
        if not sentiments:
            return "normal"
        
        # Calculate average absolute sentiment
        avg_abs_sentiment = sum(abs(s.sentiment_score) for s in sentiments.values()) / len(sentiments)
        
        # Calculate sentiment dispersion
        scores = [s.sentiment_score for s in sentiments.values()]
        avg_score = sum(scores) / len(scores)
        
        # High volatility = high dispersion or extreme readings
        if avg_abs_sentiment > 60:
            if avg_score > 40:
                return "euphoria"
            elif avg_score < -40:
                return "panic"
            else:
                return "high_vol"
        elif avg_abs_sentiment > 40:
            return "normal"
        else:
            return "low_vol"
    
    def _extract_narratives(self, sentiments: Dict[str, CoinSentiment]) -> List[str]:
        """Extract dominant market narratives."""
        drivers = [s.key_driver for s in sentiments.values() if s.key_driver]
        
        # Count driver occurrences
        driver_counts = {}
        for driver in drivers:
            driver_lower = driver.lower()
            driver_counts[driver_lower] = driver_counts.get(driver_lower, 0) + 1
        
        # Sort by frequency
        sorted_drivers = sorted(driver_counts.items(), key=lambda x: x[1], reverse=True)
        
        return [d[0] for d in sorted_drivers[:5]]

