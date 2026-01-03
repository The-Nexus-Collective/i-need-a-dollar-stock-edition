"""
Discovery Agent - Finds new trading opportunities.

Responsibilities:
1. Pull top coins from CoinGecko (daily/4-hourly)
2. Scan X for emerging coins and hype events
3. Extract narrative and strategy ideas from social discourse
4. Add candidates to validation queue

This agent expands the opportunity space continuously.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from .base import GrokAgent, AgentContext, AgentOutput
from integrations.coingecko import get_coingecko_client, CoinInfo

logger = logging.getLogger(__name__)


@dataclass
class Discovery:
    """A discovered coin or opportunity."""
    coin: str
    source: str  # 'coingecko', 'x_viral', 'x_keyword', 'x_narrative'
    reason: str
    
    # Metrics
    volume_24h: float = 0
    price_change_24h: float = 0
    engagement_score: float = 0
    
    # X-specific
    tweet_id: Optional[str] = None
    tweet_text: Optional[str] = None
    narrative: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "source": self.source,
            "reason": self.reason,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "engagement_score": self.engagement_score,
            "tweet_id": self.tweet_id,
            "narrative": self.narrative,
        }


@dataclass
class DiscoveryOutput:
    """Output from Discovery Agent."""
    # New coins to validate
    new_candidates: List[Discovery]
    
    # Coins to keep in universe (confirmed volume)
    confirmed_coins: List[str]
    
    # Top narratives detected
    narratives: List[str]
    
    # Stats
    coingecko_count: int = 0
    x_discovery_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "new_candidates": [d.to_dict() for d in self.new_candidates],
            "confirmed_coins": self.confirmed_coins,
            "narratives": self.narratives,
            "coingecko_count": self.coingecko_count,
            "x_discovery_count": self.x_discovery_count,
        }


class DiscoveryAgent(GrokAgent):
    """
    Discovers new trading opportunities from CoinGecko and X.
    
    Runs every cycle but only does full CoinGecko refresh every 4 hours.
    X scanning happens every cycle (15 min).
    """
    
    # Hype keywords for X search
    HYPE_KEYWORDS = [
        "breakout", "gem", "moonshot", "100x", "next big",
        "undervalued", "sleeping giant", "accumulating",
        "bullish", "pump", "going parabolic", "ath",
    ]
    
    # Crypto-specific X queries
    X_QUERIES = [
        "crypto gem 2026 min_faves:100",
        "altcoin breakout min_faves:50",
        "$BTC $ETH bullish min_faves:200",
        "crypto narrative min_faves:100",
        "meme coin pump min_faves:100",
    ]
    
    def __init__(self):
        super().__init__("discovery")
        self._last_coingecko_refresh: Optional[datetime] = None
        self._coingecko_refresh_interval = timedelta(hours=4)
        self._known_coins: Set[str] = set()
        self._coingecko = get_coingecko_client()
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """
        Decide what to discover this cycle.
        
        - Full CoinGecko refresh every 4 hours
        - X scan every cycle
        - Grok analysis of findings
        """
        now = datetime.utcnow()
        
        # Determine what to do
        do_coingecko = (
            self._last_coingecko_refresh is None or
            now - self._last_coingecko_refresh > self._coingecko_refresh_interval
        )
        
        reasoning = []
        if do_coingecko:
            reasoning.append("Time for CoinGecko refresh (every 4h)")
        reasoning.append("Scanning X for new opportunities")
        reasoning.append(f"Currently tracking {len(self._known_coins)} coins")
        
        return AgentOutput(
            success=True,
            data={"do_coingecko": do_coingecko},
            reasoning=" | ".join(reasoning),
            decision="refresh_and_scan" if do_coingecko else "scan_x_only",
            confidence=90,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Execute discovery actions."""
        discoveries: List[Discovery] = []
        confirmed: List[str] = []
        narratives: List[str] = []
        
        do_coingecko = thought.data.get("do_coingecko", False)
        
        # ═══════════════════════════════════════════════════════════════
        # 1. CoinGecko Discovery
        # ═══════════════════════════════════════════════════════════════
        if do_coingecko:
            cg_discoveries = await self._discover_from_coingecko()
            discoveries.extend(cg_discoveries)
            self._last_coingecko_refresh = datetime.utcnow()
            
            # Update known coins
            for d in cg_discoveries:
                self._known_coins.add(d.coin)
            
            # Confirmed = all coins from CoinGecko with good volume
            confirmed = [d.coin for d in cg_discoveries if d.volume_24h >= 10_000_000]
        
        # ═══════════════════════════════════════════════════════════════
        # 2. X/Twitter Discovery
        # ═══════════════════════════════════════════════════════════════
        x_discoveries, detected_narratives = await self._discover_from_x()
        discoveries.extend(x_discoveries)
        narratives = detected_narratives
        
        # ═══════════════════════════════════════════════════════════════
        # 3. Analyze findings with Grok
        # ═══════════════════════════════════════════════════════════════
        if discoveries:
            analysis, tokens = await self._analyze_discoveries(discoveries)
        else:
            analysis = "No new discoveries this cycle"
            tokens = 0
        
        # Build output
        output = DiscoveryOutput(
            new_candidates=[d for d in discoveries if d.coin not in self._known_coins],
            confirmed_coins=confirmed,
            narratives=narratives,
            coingecko_count=len([d for d in discoveries if d.source == 'coingecko']),
            x_discovery_count=len([d for d in discoveries if d.source.startswith('x_')]),
        )
        
        # Update context
        context.x_discoveries = [d.to_dict() for d in x_discoveries]
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=analysis,
            decision=f"Found {len(output.new_candidates)} new candidates, {len(confirmed)} confirmed",
            confidence=85,
            tokens_used=tokens,
        )
    
    async def _discover_from_coingecko(self) -> List[Discovery]:
        """Pull top coins from CoinGecko."""
        discoveries = []
        
        try:
            # Get top 200 coins by market cap with volume filter
            coins = await self._coingecko.get_top_coins(
                limit=200,
                min_volume=5_000_000  # $5M minimum
            )
            
            for coin in coins:
                discovery = Discovery(
                    coin=coin.symbol,
                    source="coingecko",
                    reason=f"Top {coin.market_cap_rank} by market cap",
                    volume_24h=coin.volume_24h,
                    price_change_24h=coin.price_change_24h,
                )
                discoveries.append(discovery)
            
            logger.info(f"CoinGecko: Found {len(discoveries)} coins")
            
        except Exception as e:
            logger.error(f"CoinGecko discovery failed: {e}")
        
        return discoveries
    
    async def _discover_from_x(self) -> tuple[List[Discovery], List[str]]:
        """Scan X for crypto opportunities."""
        discoveries = []
        narratives = []
        
        try:
            from integrations.x_client import get_x_hype_detector
            x_client = get_x_hype_detector()
            
            # Search for each query
            for query in self.X_QUERIES[:3]:  # Limit to avoid rate limits
                try:
                    tweets = await x_client.search_tweets(query, max_results=50)
                    
                    for tweet in tweets:
                        # Extract coin mentions
                        coins = self._extract_coins(tweet.text)
                        
                        for coin in coins:
                            discovery = Discovery(
                                coin=coin,
                                source="x_viral" if tweet.engagement_score > 1000 else "x_keyword",
                                reason=f"Found in X with {tweet.engagement_score:.0f} engagement",
                                engagement_score=tweet.engagement_score,
                                tweet_id=tweet.id,
                                tweet_text=tweet.text[:200],
                            )
                            discoveries.append(discovery)
                        
                        # Extract narratives
                        narrative = self._extract_narrative(tweet.text)
                        if narrative and narrative not in narratives:
                            narratives.append(narrative)
                    
                    await asyncio.sleep(1)  # Rate limiting
                    
                except Exception as e:
                    logger.warning(f"X query failed: {e}")
            
            logger.info(f"X Discovery: Found {len(discoveries)} mentions, {len(narratives)} narratives")
            
        except Exception as e:
            logger.error(f"X discovery failed: {e}")
        
        return discoveries, narratives
    
    def _extract_coins(self, text: str) -> List[str]:
        """Extract coin symbols from text."""
        # Match $SYMBOL patterns
        cashtags = re.findall(r'\$([A-Z]{2,10})\b', text.upper())
        
        # Filter out non-crypto
        skip = {'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'INR', 'AUD', 'CAD'}
        coins = [c for c in cashtags if c not in skip]
        
        return list(set(coins))
    
    def _extract_narrative(self, text: str) -> Optional[str]:
        """Extract market narrative from text."""
        narratives = {
            "AI crypto": ["ai", "artificial intelligence", "machine learning"],
            "meme coins": ["meme", "doge", "shib", "pepe", "wojak"],
            "DeFi": ["defi", "yield", "staking", "lending"],
            "L2 scaling": ["layer 2", "l2", "rollup", "zk"],
            "RWA": ["rwa", "real world asset", "tokenized"],
            "gaming": ["gamefi", "p2e", "play to earn", "gaming"],
        }
        
        text_lower = text.lower()
        for narrative, keywords in narratives.items():
            if any(kw in text_lower for kw in keywords):
                return narrative
        
        return None
    
    async def _analyze_discoveries(self, discoveries: List[Discovery]) -> tuple[str, int]:
        """Use Grok to analyze discoveries and prioritize."""
        # Summarize discoveries
        summary = []
        for d in discoveries[:20]:  # Limit for context
            summary.append(f"- {d.coin}: {d.source} - {d.reason}")
        
        prompt = f"""Analyze these crypto discoveries and identify the most promising opportunities:

{chr(10).join(summary)}

Consider:
1. Volume and liquidity
2. Social momentum (X engagement)
3. Emerging narratives
4. Risk factors

Provide a brief analysis (2-3 sentences) and rank top 5 coins to investigate."""

        response, tokens = await self.call_grok(prompt, temperature=0.3)
        return response, tokens

