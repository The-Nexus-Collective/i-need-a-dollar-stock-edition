"""
Grok Analyst - Single Grok call that does everything

Uses Grok's real-time capabilities to:
1. Identify top 100 coins by market cap
2. Search X/Reddit for last 10 minutes sentiment
3. Evaluate open positions (KEEP or CLOSE)
4. Find new opportunities (LONG/SHORT with conviction)

Returns both human-readable text AND structured JSON.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PositionDecision:
    """
    Grok's decision for an existing position.
    
    Actions:
    - KEEP: Hold position unchanged
    - CLOSE: Fully close the position
    - EXTEND: Add to the position (scale_percent = % of current size to add)
    - REDUCE: Partially close (scale_percent = % of current size to sell)
    """
    symbol: str
    action: str  # "KEEP", "CLOSE", "EXTEND", or "REDUCE"
    reason: str
    current_sentiment: int  # -100 to +100
    scale_percent: int = 0  # For EXTEND/REDUCE: percentage to scale (e.g., 50 = 50%)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "reason": self.reason,
            "current_sentiment": self.current_sentiment,
            "scale_percent": self.scale_percent,
        }


@dataclass
class NewOpportunity:
    """Grok's recommendation for a new trade."""
    symbol: str
    direction: str  # "LONG" or "SHORT"
    conviction: int  # 0-100
    leverage: int  # 1-10
    sentiment_score: int  # -100 to +100
    narrative_strength: int  # 0-100
    reason: str
    key_signals: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "conviction": self.conviction,
            "leverage": self.leverage,
            "sentiment_score": self.sentiment_score,
            "narrative_strength": self.narrative_strength,
            "reason": self.reason,
            "key_signals": self.key_signals,
        }


@dataclass
class AnalysisResult:
    """Complete result from Grok analysis."""
    
    # Human-readable analysis (stored in logbook)
    analysis_text: str
    market_summary: str
    
    # Structured decisions
    position_decisions: List[PositionDecision]
    new_opportunities: List[NewOpportunity]
    
    # Metadata
    coins_analyzed: int
    coins_skipped: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tokens_used: int = 0
    
    # Debug: raw Grok prompt and response
    raw_prompt: str = ""
    raw_response: str = ""
    
    def to_dict(self) -> dict:
        return {
            "analysis_text": self.analysis_text,
            "market_summary": self.market_summary,
            "position_decisions": [d.to_dict() for d in self.position_decisions],
            "new_opportunities": [o.to_dict() for o in self.new_opportunities],
            "coins_analyzed": self.coins_analyzed,
            "coins_skipped": self.coins_skipped,
            "timestamp": self.timestamp.isoformat(),
            "tokens_used": self.tokens_used,
            "raw_prompt": self.raw_prompt,
            "raw_response": self.raw_response,
        }
    
    def get_positions_to_close(self) -> List[str]:
        """Get symbols that Grok recommends closing."""
        return [d.symbol for d in self.position_decisions if d.action == "CLOSE"]
    
    def get_positions_to_keep(self) -> List[str]:
        """Get symbols that Grok recommends keeping."""
        return [d.symbol for d in self.position_decisions if d.action == "KEEP"]
    
    def get_positions_to_extend(self) -> List[PositionDecision]:
        """Get positions that Grok recommends extending."""
        return [d for d in self.position_decisions if d.action == "EXTEND"]
    
    def get_positions_to_reduce(self) -> List[PositionDecision]:
        """Get positions that Grok recommends reducing."""
        return [d for d in self.position_decisions if d.action == "REDUCE"]


class GrokAnalyst:
    """
    Single Grok call that handles all analysis.
    
    Grok internally:
    - Finds top 100 coins by market cap
    - Searches X/Reddit from last 10 minutes
    - Evaluates positions and finds opportunities
    """
    
    XAI_BASE_URL = "https://api.x.ai/v1"
    MODEL = "grok-3"
    
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        
        if not self.api_key:
            logger.warning("XAI_API_KEY not set - analyst will fail!")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=300.0,  # 5 minute timeout for comprehensive analysis
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    def _build_prompt(self, positions_context: str, available_slots: int, deployment_info: str = "") -> str:
        """Build the comprehensive analysis prompt."""
        
        now = datetime.utcnow()
        timestamp = now.strftime("%Y-%m-%d %H:%M UTC")
        
        return f"""You are a professional crypto portfolio manager. Your task is to manage the portfolio in real-time.

═══════════════════════════════════════════════════════════════════
CURRENT TIME: {timestamp}
═══════════════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════════════
TASK 1: MARKET ANALYSIS (Top 100 Coins)
═══════════════════════════════════════════════════════════════════

Analyze the top 100 cryptocurrencies by market cap that are tradable on Binance Futures.

IMPORTANT RULES:
1. Base your analysis EXCLUSIVELY on X posts, Reddit trends, and market narratives from the LAST 10 MINUTES
2. Use your real-time search functions (x_keyword_search, web_search) for current data
3. Skip coins where data is too thin or noisy - DO NOT FORCE A RATING
4. Only coins with significant current discussion volume should be rated

═══════════════════════════════════════════════════════════════════
TASK 2: PORTFOLIO EVALUATION WITH RISK MANAGEMENT
═══════════════════════════════════════════════════════════════════

{positions_context}

{deployment_info}

═══════════════════════════════════════════════════════════════════
RISK ASSESSMENT FOR OPEN POSITIONS (IMPORTANT!)
═══════════════════════════════════════════════════════════════════

The positions above contain detailed risk data. Follow these rules:

🔴 DANGER (Margin Risk > 70%): CLOSE IMMEDIATELY - Position near liquidation!
🟡 WARNING (Margin Risk 50-70%): WATCH CLOSELY - Consider closing if sentiment not clearly bullish
🟠 ELEVATED (Margin Risk 30-50%): CAUTION - Only hold with strong sentiment
🟢 OK (Margin Risk < 30%): Continue normal analysis

ADDITIONAL RISK FACTORS:
- PnL < -15%: Heavy losses - Check stop-loss, consider CLOSE
- PnL < -25%: Critical losses - CLOSE recommended unless very strong reversal signal
- Hold time > 24h without movement: Capital locked - CLOSE if no catalyst in sight
- Hold time > 48h: Check if better to rotate into other opportunities

For each open position, decide one of the following actions:
- KEEP: Hold without changes
- CLOSE: Close position completely (sentiment reversed or risk too high)
- EXTEND: Add to position (sentiment strengthening, scale_percent = percent of current size to add)
- REDUCE: Partially close position (take partial profits or reduce risk, scale_percent = percent to sell)

Use EXTEND when:
- Strong positive momentum and sentiment
- Position already profitable and trend confirms
- Conviction for the trade increases
- Margin Risk < 30% (green zone)

Use REDUCE when:
- Good profits exist but uncertainty rises
- Take partial profits at 20%+ PnL
- Reduce risk without fully closing position
- Margin Risk in ELEVATED range (30-50%)

═══════════════════════════════════════════════════════════════════
LONG AND SHORT STRATEGY - ACTIVELY USE BOTH DIRECTIONS!
═══════════════════════════════════════════════════════════════════

You can go both LONG (betting on rising prices) and SHORT (betting on falling 
prices). USE BOTH DIRECTIONS ACTIVELY!

LONG SIGNALS (bullish):
- Positive breaking news, partnerships, listings
- Strong whale accumulation
- Bullish sentiment on X/Reddit (>60)
- Upward momentum, new highs
- FOMO indicators (broad retail attention)

SHORT SIGNALS (bearish):
- Negative news: Hacks, regulation, insolvency, rug pull rumors
- Whale selling, large transfers to exchanges
- Bearish sentiment on X/Reddit (<-30)
- Downward momentum, new lows, trend break
- Overheating after pump (RSI overbought, exhaustion)
- FUD campaigns, coordinated criticism

WHEN TO PREFER SHORT:
- Overall market bearish (BTC/ETH falling)
- Coin just pumped hard without fundamental reason
- Negative news with substance (not just FUD)
- Sentiment turning from positive to negative

IMPORTANT: A balanced portfolio has BOTH long and short positions! 
In a bear market, shorts can be the main profit source.

═══════════════════════════════════════════════════════════════════
PROFIT-TAKING & CAPITAL ROTATION STRATEGY
═══════════════════════════════════════════════════════════════════

GOAL: Actively rotate capital from "exhausted" positions into trades with 
stronger momentum. Don't wait for full recovery - trade agilely!

RECOGNIZING MOMENTUM EXHAUSTION:
1. Sentiment decline: Position has >15% profit, but current sentiment 
   is weaker than at entry (e.g., dropped from 80 to 50)
2. Volume decrease: Discussions on X/Reddit declining despite profitable position
3. Narrative shift: Attention moving to other coins
4. Sideways movement: Price consolidating for multiple cycles despite profit

PROACTIVE REDUCE RULES (take profits, free up capital):

+10-20% PnL + fading momentum -> REDUCE 30-40%
   Rationale: Early profit-taking at first signs of exhaustion

+20-40% PnL + sentiment below 50 -> REDUCE 50%
   Rationale: Lock in solid profits, let half the position run

+40%+ PnL -> REDUCE 50-70% (regardless of sentiment)
   Rationale: Realize exceptional gains, rotate capital

Position in profit + new opportunity with +30 higher conviction:
   -> REDUCE 50-100% of old position for the new one
   Rationale: Capital follows the strongest momentum

PRIORITIZE CAPITAL ROTATION:
- When new high-conviction opportunities are waiting (>75 conviction)
- And existing positions show profits but momentum is fading
- -> Actively use REDUCE to free up capital for new trades
- -> Don't wait until positions are "finished" - momentum is fleeting!

ANTI-PATTERNS (AVOID):
- Holding profitable positions forever hoping for more
- Only reacting at trend reversal instead of momentum exhaustion
- Missing new opportunities because capital is locked

═══════════════════════════════════════════════════════════════════
TASK 3: NEW OPPORTUNITIES
═══════════════════════════════════════════════════════════════════

Available slots for new positions: {available_slots}

PORTFOLIO LIMITS (both are checked):
1. Position limit: Maximum 50 open positions
2. Capital limit: Maximum 90% of capital deployed

Search for new trading opportunities:
- Only coins with clear sentiment signal (bullish → LONG, bearish → SHORT)
- Conviction must be > 60

REPLACEMENT RULES (when limits reached):
- New position is ONLY opened if conviction is at least +25 HIGHER than the lowest existing position
- On replacement: Explicitly name which position to replace and why
- Example: New opportunity with conviction 85 can replace position with conviction 60 (85 >= 60+25)

═══════════════════════════════════════════════════════════════════
OUTPUT FORMAT (STRICTLY FOLLOW!)
═══════════════════════════════════════════════════════════════════

Respond with a JSON object. The "analysis_text" field contains your human-readable analysis.

```json
{{
  "analysis_text": "📊 **Portfolio Update {timestamp}**\\n\\n[Your detailed, human-readable market analysis and recommendations. Explain why you want to close, extend, or reduce certain positions. At least 200 words.]",
  
  "market_summary": "Brief summary of the overall market in 1-2 sentences",
  
  "position_decisions": [
    {{
      "symbol": "BTCUSDT",
      "action": "KEEP",
      "reason": "Strong bullish sentiment on X",
      "current_sentiment": 65,
      "scale_percent": 0
    }},
    {{
      "symbol": "ETHUSDT",
      "action": "EXTEND",
      "reason": "Momentum strengthening, adding to position",
      "current_sentiment": 75,
      "scale_percent": 50
    }},
    {{
      "symbol": "SOLUSDT",
      "action": "REDUCE",
      "reason": "+35% profit, sentiment dropped from 75 to 45 - freeing capital for AVAXUSDT (Conv. 82)",
      "current_sentiment": 45,
      "scale_percent": 60
    }}
  ],
  
  "new_opportunities": [
    {{
      "symbol": "AVAXUSDT",
      "direction": "LONG",
      "conviction": 82,
      "leverage": 5,
      "sentiment_score": 72,
      "narrative_strength": 85,
      "reason": "Breaking: Avalanche update, strong whale accumulation",
      "key_signals": ["@whale_alert: Large buy", "Avalanche Foundation announcement"]
    }},
    {{
      "symbol": "DOGEUSDT",
      "direction": "SHORT",
      "conviction": 72,
      "leverage": 4,
      "sentiment_score": -55,
      "narrative_strength": 70,
      "reason": "Pump exhausted after 3-day rally, whale selling to exchanges, bearish sentiment",
      "key_signals": ["Large DOGE transfer to Binance", "Meme fatigue on X", "RSI overbought"]
    }}
  ],
  
  "coins_analyzed": 47,
  "coins_skipped": 53
}}
```

IMPORTANT:
- "analysis_text" MUST be a detailed, human-readable analysis (for the logbook)
- All prices and symbols must be in Binance Futures format (e.g., BTCUSDT)
- Leverage between 1-10 based on conviction
- scale_percent only used with EXTEND/REDUCE (10-100)
- For KEEP and CLOSE, scale_percent is always 0
- Skipped coins have insufficient 10-minute data

═══════════════════════════════════════════════════════════════════
ANALYZE NOW - OUTPUT JSON ONLY
═══════════════════════════════════════════════════════════════════"""

    async def analyze(
        self,
        positions_context: str,
        available_slots: int,
        deployment_info: str = "",
    ) -> AnalysisResult:
        """
        Run comprehensive Grok analysis.
        
        Args:
            positions_context: Formatted string of current positions
            available_slots: Number of slots available for new positions
            deployment_info: Deployment status message (below minimum warning)
            
        Returns:
            AnalysisResult with decisions and human-readable text
        """
        prompt = self._build_prompt(positions_context, available_slots, deployment_info)
        
        system_prompt = """You are a professional crypto portfolio manager with real-time access to market data.

CRITICAL: You MUST use your search tools (x_keyword_search, x_semantic_search, web_search) to gather CURRENT data from the last 10 minutes.

Your internal knowledge is outdated. Only real-time search results matter.

Always output valid JSON as specified in the prompt."""

        # Build full prompt for debugging (system + user)
        full_prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{prompt}"
        
        if not self.api_key:
            logger.error("No XAI_API_KEY - returning empty analysis")
            return self._empty_result("API key not configured", raw_prompt=full_prompt)

        try:
            client = await self._get_client()
            
            request_body = {
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,  # Lower for more consistent output
                "max_tokens": 8000,  # Large response for comprehensive analysis
                "search_parameters": {
                    "mode": "auto",
                    "return_citations": True,
                }
            }
            
            logger.info("Calling Grok for portfolio analysis...")
            
            response = await client.post(
                f"{self.XAI_BASE_URL}/chat/completions",
                json=request_body
            )
            
            if response.status_code != 200:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return self._empty_result(f"API error: {response.status_code}", raw_prompt=full_prompt, raw_response=response.text)
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            tokens_used = data.get("usage", {}).get("total_tokens", 0)
            
            logger.info(f"Grok response received ({tokens_used} tokens)")
            
            return self._parse_response(content, tokens_used, raw_prompt=full_prompt, raw_response=content)
            
        except Exception as e:
            logger.error(f"Grok analysis failed: {e}", exc_info=True)
            return self._empty_result(f"Analysis failed: {str(e)}", raw_prompt=full_prompt)
    
    def _parse_response(self, content: str, tokens_used: int, raw_prompt: str = "", raw_response: str = "") -> AnalysisResult:
        """Parse Grok's JSON response into AnalysisResult."""
        try:
            # Extract JSON from markdown code block if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            # Find JSON object
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                content = content[json_start:json_end]
            
            data = json.loads(content)
            
            # Parse position decisions
            position_decisions = []
            for pd in data.get("position_decisions", []):
                action = pd.get("action", "KEEP").upper()
                # Validate action
                if action not in ["KEEP", "CLOSE", "EXTEND", "REDUCE"]:
                    action = "KEEP"
                
                # Get scale_percent for EXTEND/REDUCE
                scale_percent = 0
                if action in ["EXTEND", "REDUCE"]:
                    scale_percent = int(pd.get("scale_percent", 50))
                    # Clamp to valid range
                    scale_percent = max(10, min(100, scale_percent))
                
                position_decisions.append(PositionDecision(
                    symbol=pd.get("symbol", ""),
                    action=action,
                    reason=pd.get("reason", ""),
                    current_sentiment=int(pd.get("current_sentiment", 0)),
                    scale_percent=scale_percent,
                ))
            
            # Parse new opportunities
            new_opportunities = []
            for opp in data.get("new_opportunities", []):
                direction = opp.get("direction", "").upper()
                if direction not in ["LONG", "SHORT"]:
                    continue  # Skip invalid directions
                
                conviction = int(opp.get("conviction", 0))
                if conviction < 60:
                    continue  # Skip low conviction
                
                new_opportunities.append(NewOpportunity(
                    symbol=opp.get("symbol", ""),
                    direction=direction,
                    conviction=conviction,
                    leverage=min(10, max(1, int(opp.get("leverage", 3)))),
                    sentiment_score=int(opp.get("sentiment_score", 0)),
                    narrative_strength=int(opp.get("narrative_strength", 0)),
                    reason=opp.get("reason", ""),
                    key_signals=opp.get("key_signals", [])[:5],
                ))
            
            # Sort opportunities by conviction (highest first)
            new_opportunities.sort(key=lambda x: x.conviction, reverse=True)
            
            return AnalysisResult(
                analysis_text=data.get("analysis_text", "No analysis text provided"),
                market_summary=data.get("market_summary", ""),
                position_decisions=position_decisions,
                new_opportunities=new_opportunities,
                coins_analyzed=int(data.get("coins_analyzed", 0)),
                coins_skipped=int(data.get("coins_skipped", 0)),
                tokens_used=tokens_used,
                raw_prompt=raw_prompt,
                raw_response=raw_response,
            )
            
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse Grok response: {e}")
            logger.debug(f"Raw content: {content[:1000]}")
            return self._empty_result(f"Parse error: {str(e)}", raw_prompt=raw_prompt, raw_response=raw_response)
    
    def _empty_result(self, reason: str, raw_prompt: str = "", raw_response: str = "") -> AnalysisResult:
        """Return an empty result when analysis fails."""
        return AnalysisResult(
            analysis_text=f"⚠️ Analysis could not be completed: {reason}",
            market_summary="Analysis unavailable",
            position_decisions=[],
            new_opportunities=[],
            coins_analyzed=0,
            coins_skipped=0,
            raw_prompt=raw_prompt,
            raw_response=raw_response,
        )
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

