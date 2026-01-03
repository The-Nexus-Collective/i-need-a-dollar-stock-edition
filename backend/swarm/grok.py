"""
Grok - The Single Window to Reality

All agents interact with the world exclusively through Grok.
Grok has:
- Web search capabilities
- Real-time X (Twitter) access
- Reasoning and analysis

No other APIs needed. Grok is the single source of truth.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Callable, Dict, List, Optional, Any
from uuid import UUID, uuid4

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ThoughtChunk:
    """A chunk of streamed thought from Grok."""
    agent_id: str
    agent_name: str
    content: str
    is_final: bool = False
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class GrokResponse:
    """Complete response from Grok."""
    content: str
    tokens_used: int
    model: str
    finish_reason: str = "stop"
    
    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "tokens_used": self.tokens_used,
            "model": self.model,
            "finish_reason": self.finish_reason,
        }


class Grok:
    """
    Single interface to Grok for all agent needs.
    
    Grok handles web search, X analysis, and reasoning.
    All external world interaction goes through this class.
    """
    
    BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-3"  # or "grok-3-mini" for faster responses
    
    def __init__(self):
        self.api_key = os.getenv("XAI_API_KEY", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._thought_subscribers: List[Callable[[ThoughtChunk], None]] = []
        
        if not self.api_key:
            logger.warning("XAI_API_KEY not set - Grok will not function!")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # Long timeout for complex queries
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
            )
        return self._client
    
    def subscribe_to_thoughts(self, callback: Callable[[ThoughtChunk], None]):
        """Subscribe to thought stream for UI updates."""
        self._thought_subscribers.append(callback)
    
    def unsubscribe_from_thoughts(self, callback: Callable[[ThoughtChunk], None]):
        """Unsubscribe from thought stream."""
        if callback in self._thought_subscribers:
            self._thought_subscribers.remove(callback)
    
    async def _broadcast_thought(self, chunk: ThoughtChunk):
        """Broadcast thought chunk to all subscribers."""
        logger.debug(f"Broadcasting thought chunk from {chunk.agent_name}: {chunk.content[:50] if chunk.content else '[final]'}...")
        
        if not self._thought_subscribers:
            logger.debug("No thought subscribers registered")
            return
            
        for callback in self._thought_subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(chunk)
                else:
                    callback(chunk)
            except Exception as e:
                logger.warning(f"Thought subscriber error: {e}")
    
    async def ask(
        self,
        question: str,
        agent_id: str = "grok",
        agent_name: str = "Grok",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        stream: bool = True,
        model: Optional[str] = None,
    ) -> GrokResponse:
        """
        Ask Grok anything - it will search the web/X as needed.
        
        Args:
            question: The question or task for Grok
            agent_id: ID of the agent asking (for thought attribution)
            agent_name: Name of the agent asking
            system_prompt: Optional system context
            temperature: Creativity level (0.0-1.0)
            max_tokens: Maximum response length
            stream: Whether to stream the response (for UI)
            model: Model to use (defaults to grok-3)
        
        Returns:
            GrokResponse with content and token usage
        """
        if not self.api_key:
            return GrokResponse(
                content="[Grok API key not configured]",
                tokens_used=0,
                model="none",
            )
        
        client = await self._get_client()
        model = model or self.DEFAULT_MODEL
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": question})
        
        try:
            if stream:
                return await self._ask_streaming(
                    client, messages, agent_id, agent_name,
                    temperature, max_tokens, model
                )
            else:
                return await self._ask_direct(
                    client, messages, temperature, max_tokens, model
                )
        except Exception as e:
            logger.error(f"Grok API error: {e}")
            return GrokResponse(
                content=f"[Error: {str(e)}]",
                tokens_used=0,
                model=model,
                finish_reason="error",
            )
    
    async def _ask_direct(
        self,
        client: httpx.AsyncClient,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> GrokResponse:
        """Non-streaming API call."""
        response = await client.post(
            f"{self.BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text}")
        
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        tokens = data.get("usage", {}).get("total_tokens", 0)
        finish = data["choices"][0].get("finish_reason", "stop")
        
        return GrokResponse(
            content=content,
            tokens_used=tokens,
            model=model,
            finish_reason=finish,
        )
    
    async def _ask_streaming(
        self,
        client: httpx.AsyncClient,
        messages: List[dict],
        agent_id: str,
        agent_name: str,
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> GrokResponse:
        """Streaming API call with thought broadcast."""
        full_content = ""
        tokens_used = 0
        finish_reason = "stop"
        
        async with client.stream(
            "POST",
            f"{self.BASE_URL}/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                raise Exception(f"API error {response.status_code}: {error_text}")
            
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                
                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break
                
                try:
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    
                    if content:
                        full_content += content
                        
                        # Broadcast thought chunk
                        chunk = ThoughtChunk(
                            agent_id=agent_id,
                            agent_name=agent_name,
                            content=content,
                            is_final=False,
                        )
                        await self._broadcast_thought(chunk)
                    
                    # Check for finish
                    if data["choices"][0].get("finish_reason"):
                        finish_reason = data["choices"][0]["finish_reason"]
                    
                    # Get token usage if available
                    if "usage" in data:
                        tokens_used = data["usage"].get("total_tokens", 0)
                        
                except json.JSONDecodeError:
                    continue
        
        # Broadcast final chunk
        final_chunk = ThoughtChunk(
            agent_id=agent_id,
            agent_name=agent_name,
            content="",
            is_final=True,
        )
        await self._broadcast_thought(final_chunk)
        
        return GrokResponse(
            content=full_content,
            tokens_used=tokens_used,
            model=model,
            finish_reason=finish_reason,
        )
    
    # ═══════════════════════════════════════════════════════════════════════════════
    # SPECIALIZED QUERY METHODS
    # These wrap the base ask() with domain-specific prompts
    # ═══════════════════════════════════════════════════════════════════════════════
    
    async def search_x(
        self,
        query: str,
        hours: int = 24,
        agent_id: str = "grok",
        agent_name: str = "Grok",
    ) -> GrokResponse:
        """
        Ask Grok to analyze recent X posts.
        
        Args:
            query: What to search for on X
            hours: Time range to search
        """
        prompt = f"""Search X/Twitter for: {query}
Time range: last {hours} hours

Analyze and summarize:
1. KEY NARRATIVES: What are people saying?
2. SENTIMENT: Bullish / Bearish / Neutral (with confidence)
3. NOTABLE VOICES: Any influential accounts discussing this?
4. ENGAGEMENT: Are posts getting traction?
5. EMERGING PATTERNS: Any new trends or shifts?

Be specific. Quote actual insights when possible.
If you can't find relevant data, say so honestly."""

        return await self.ask(
            question=prompt,
            agent_id=agent_id,
            agent_name=agent_name,
            system_prompt="You are a crypto market analyst with real-time access to X/Twitter. Provide accurate, actionable insights.",
        )
    
    async def research_project(
        self,
        name: str,
        agent_id: str = "grok",
        agent_name: str = "Grok",
    ) -> GrokResponse:
        """
        Ask Grok to deeply research a crypto project.
        
        Args:
            name: Name or symbol of the project
        """
        prompt = f"""Research the crypto project: {name}

Find and analyze:
1. WHAT IS IT: Core purpose in 1-2 sentences
2. TEAM: Who's behind it? Background, credibility
3. BACKERS: VCs, investors, notable supporters
4. TOKENOMICS: Supply, distribution, vesting
5. RECENT NEWS: Last 7 days of developments
6. RED FLAGS: Any concerns, controversies, risks?
7. X SENTIMENT: What's the community saying?

Be critical and skeptical. Flag anything suspicious.
If information is uncertain, say so."""

        return await self.ask(
            question=prompt,
            agent_id=agent_id,
            agent_name=agent_name,
            system_prompt="You are a crypto due diligence analyst. Be thorough but skeptical. Your job is to protect capital.",
        )
    
    async def analyze_market(
        self,
        agent_id: str = "grok",
        agent_name: str = "Grok",
    ) -> GrokResponse:
        """Ask Grok for current market analysis."""
        prompt = """Analyze the current crypto market RIGHT NOW:

1. OVERALL SENTIMENT: Fear/Greed on X
2. TRENDING TOPICS: What's dominating crypto Twitter?
3. MARKET MOVERS: Which coins are getting unusual attention?
4. NEWS IMPACT: Any breaking news moving markets?
5. NARRATIVE SHIFTS: Any emerging themes or dying narratives?

Base this on real-time X data and recent news.
Be specific with examples and metrics when possible."""

        return await self.ask(
            question=prompt,
            agent_id=agent_id,
            agent_name=agent_name,
            system_prompt="You are a market sentiment analyst with real-time data access. Provide actionable market insights.",
        )
    
    async def discover_opportunities(
        self,
        focus: str = "any",
        agent_id: str = "grok",
        agent_name: str = "Grok",
    ) -> GrokResponse:
        """
        Ask Grok to find trading opportunities.
        
        Args:
            focus: Focus area (e.g., "meme coins", "AI tokens", "any")
        """
        focus_text = f"Focus: {focus}" if focus != "any" else "Look across all crypto sectors"
        
        prompt = f"""Find trading opportunities in crypto RIGHT NOW.
{focus_text}

Look for:
1. TRENDING COINS: Unusual X activity, breaking news
2. CATALYST EVENTS: Launches, listings, partnerships
3. HYPE PATTERNS: Early momentum before mainstream attention
4. CONTRARIAN PLAYS: Oversold gems with positive developments

For each opportunity:
- Name/Symbol
- Why it's interesting
- Risk level (1-5)
- Time sensitivity (urgent/moderate/can wait)

Only include opportunities with clear catalysts.
Skip anything that looks like a scam or pump-and-dump."""

        return await self.ask(
            question=prompt,
            agent_id=agent_id,
            agent_name=agent_name,
            system_prompt="You are an alpha hunter with real-time market access. Find actionable opportunities but prioritize capital protection.",
        )
    
    async def ask_for_trade_decision(
        self,
        context: str,
        available_capital: float,
        open_positions: List[Dict],
        tradable_coins: List[str],
        agent_id: str = "tactician",
        agent_name: str = "Tactician",
    ) -> Dict[str, Any]:
        """
        Ask Grok for a structured trade decision.
        
        This method forces Grok to output a specific JSON format
        that can be directly parsed and executed.
        
        Args:
            context: Analysis context from other agents
            available_capital: Cash available for new positions
            open_positions: List of currently open positions
            tradable_coins: List of coins we can trade
            
        Returns:
            Dict with structured trade decision
        """
        positions_str = json.dumps(open_positions, indent=2) if open_positions else "None"
        coins_str = ", ".join(tradable_coins[:20]) if tradable_coins else "BTC, ETH, SOL, BNB"
        
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        prompt = f"""CURRENT DATE AND TIME: {current_datetime}

Based on the following market analysis, make a trading decision.

## MARKET CONTEXT
{context}

## PORTFOLIO STATUS
Available Capital: ${available_capital:,.2f}
Open Positions: {positions_str}
Tradable Coins: {coins_str}

## YOUR TASK
Analyze the context and decide whether to trade. Consider:
1. Is there a clear opportunity with an edge?
2. What is the risk/reward ratio?
3. What is your conviction level (0-100)?
4. Only trade if conviction > 70

## REQUIRED OUTPUT FORMAT
You MUST respond with ONLY this JSON object (no other text before or after):

```json
{{
  "decision": "TRADE" or "WAIT" or "PASS",
  "coin": "SYMBOL" or null,
  "direction": "LONG" or "SHORT" or null,
  "size_percent": 1 to 10,
  "stop_loss_percent": 1 to 5,
  "take_profit_percent": 2 to 15,
  "conviction": 0 to 100,
  "reasoning": "One sentence explanation"
}}
```

DECISION MEANINGS:
- TRADE: Open a new position (requires coin, direction, size, stops)
- WAIT: Good opportunity but timing not right (no trade)
- PASS: No clear opportunity (no trade)

RULES:
- Only TRADE if conviction >= 70
- size_percent is percentage of available capital (1-10%)
- stop_loss_percent is from entry price (1-5%)
- take_profit_percent is from entry price (2-15%)
- If decision is WAIT or PASS, set coin/direction/size to null

Respond with ONLY the JSON object:"""

        system_prompt = f"""You are a professional crypto trader making real trading decisions.
Current date: {current_datetime}

You analyze markets and output structured trading decisions.
You MUST output valid JSON in the exact format requested.
No explanations before or after the JSON - ONLY the JSON object.

Risk Rules:
- Never risk more than 10% of capital on one trade
- Always set stop losses
- Minimum conviction of 70 to trade
- When uncertain, WAIT or PASS"""

        response = await self.ask(
            question=prompt,
            agent_id=agent_id,
            agent_name=agent_name,
            system_prompt=system_prompt,
            temperature=0.3,  # Lower temperature for more consistent output
            max_tokens=500,
            stream=False,  # No streaming for structured output
        )
        
        # Parse the JSON response
        try:
            content = response.content.strip()
            
            # Try to extract JSON from markdown code block if present
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                content = content[start:end].strip()
            elif "```" in content:
                start = content.find("```") + 3
                end = content.find("```", start)
                content = content[start:end].strip()
            
            decision = json.loads(content)
            
            # Validate required fields
            required_fields = ["decision", "conviction", "reasoning"]
            for field in required_fields:
                if field not in decision:
                    raise ValueError(f"Missing required field: {field}")
            
            # Normalize decision
            decision["decision"] = decision.get("decision", "PASS").upper()
            if decision["decision"] not in ["TRADE", "WAIT", "PASS"]:
                decision["decision"] = "PASS"
            
            # Validate trade-specific fields if TRADE decision
            if decision["decision"] == "TRADE":
                if not decision.get("coin"):
                    decision["decision"] = "PASS"
                    decision["reasoning"] = "Trade requested but no coin specified"
                elif decision.get("conviction", 0) < 70:
                    decision["decision"] = "WAIT"
                    decision["reasoning"] = f"Conviction {decision.get('conviction')} below threshold"
            
            return decision
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse trade decision: {e}, content: {response.content[:200]}")
            return {
                "decision": "PASS",
                "coin": None,
                "direction": None,
                "size_percent": None,
                "stop_loss_percent": None,
                "take_profit_percent": None,
                "conviction": 0,
                "reasoning": f"Failed to parse response: {str(e)}",
            }
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Get embedding vector for text (for memory similarity search).
        
        Note: xAI may not have an embedding endpoint yet.
        Falls back to a simple hash-based approach if not available.
        """
        # TODO: Use xAI embedding API when available
        # For now, return a placeholder that allows the system to work
        import hashlib
        
        # Create a deterministic pseudo-embedding from text hash
        hash_bytes = hashlib.sha256(text.encode()).digest()
        
        # Expand to 1536 dimensions (OpenAI ada-002 compatible)
        embedding = []
        for i in range(1536):
            byte_idx = i % len(hash_bytes)
            embedding.append((hash_bytes[byte_idx] - 128) / 128.0)
        
        return embedding
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_grok: Optional[Grok] = None


def get_grok() -> Grok:
    """Get or create global Grok instance."""
    global _grok
    if _grok is None:
        _grok = Grok()
    return _grok

