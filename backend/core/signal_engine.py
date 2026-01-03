"""
Signal Engine - Batch Grok sentiment analysis with retry logic

This module handles:
1. Single batch API call to Grok for all 10 coins
2. Parsing multi-line responses
3. Retry logic with exponential backoff (3 attempts)
4. Score calculation: sentiment × (narrative / 100)
"""

import asyncio
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

TOP_COINS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX', 'TRX', 'LINK']

# Grok API settings
GROK_MAX_RETRIES = 3
GROK_RETRY_DELAY_BASE = 2  # Base delay in seconds (exponential backoff)
GROK_TIMEOUT = 60  # API timeout in seconds

# The exact prompt as specified
GROK_BATCH_PROMPT = """Right now, give me sentiment (-100 to +100) and narrative strength (0–100) for each of these coins, one short line per coin, nothing else:
BTC, ETH, SOL, XRP, DOGE, BNB, ADA, AVAX, TRX, LINK"""


@dataclass
class CoinSentiment:
    """Parsed sentiment data for a single coin"""
    coin: str
    sentiment: float  # -100 to +100
    narrative: float  # 0 to 100
    score: float  # sentiment × (narrative / 100)
    
    @classmethod
    def calculate_score(cls, sentiment: float, narrative: float) -> float:
        """Calculate combined score"""
        return sentiment * (narrative / 100)


@dataclass
class BatchSentimentResult:
    """Result from a batch Grok API call"""
    success: bool
    batch_id: str
    timestamp: datetime
    raw_response: str
    response_hash: str
    sentiments: Dict[str, CoinSentiment]  # coin -> CoinSentiment
    error_message: Optional[str] = None
    retry_count: int = 0


class GrokBatchClient:
    """
    Grok API client for batch sentiment analysis.
    
    Features:
    - Single API call for all 10 coins
    - 3x retry with exponential backoff
    - Robust response parsing
    """
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.x.ai/v1"
        self.client = httpx.AsyncClient(timeout=GROK_TIMEOUT)
    
    async def get_batch_sentiment(self) -> BatchSentimentResult:
        """
        Get sentiment for all coins in a single API call.
        
        Returns:
            BatchSentimentResult with all parsed sentiments
        """
        batch_id = uuid4().hex[:16]
        timestamp = datetime.utcnow()
        
        last_error = None
        
        for attempt in range(GROK_MAX_RETRIES):
            try:
                logger.info(f"Grok API call attempt {attempt + 1}/{GROK_MAX_RETRIES}")
                
                response = await self._call_api()
                
                if response:
                    # Parse the response
                    sentiments = self._parse_response(response)
                    response_hash = hashlib.sha256(response.encode()).hexdigest()
                    
                    logger.info(f"Successfully parsed {len(sentiments)} coin sentiments")
                    
                    return BatchSentimentResult(
                        success=True,
                        batch_id=batch_id,
                        timestamp=timestamp,
                        raw_response=response,
                        response_hash=response_hash,
                        sentiments=sentiments,
                        retry_count=attempt
                    )
                    
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Grok API attempt {attempt + 1} failed: {last_error}")
                
                if attempt < GROK_MAX_RETRIES - 1:
                    # Exponential backoff
                    delay = GROK_RETRY_DELAY_BASE ** (attempt + 1)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(f"All {GROK_MAX_RETRIES} Grok API attempts failed")
        
        return BatchSentimentResult(
            success=False,
            batch_id=batch_id,
            timestamp=timestamp,
            raw_response="",
            response_hash="",
            sentiments={},
            error_message=f"API failed after {GROK_MAX_RETRIES} attempts: {last_error}",
            retry_count=GROK_MAX_RETRIES
        )
    
    async def _call_api(self) -> str:
        """Make the actual API call to Grok"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": GROK_BATCH_PROMPT
                }
            ],
            "model": "grok-3",  # Updated from grok-beta (deprecated)
            "stream": False,
            "temperature": 0.1  # Low temperature for consistent responses
        }
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return data['choices'][0]['message']['content']
        else:
            raise Exception(f"API error {response.status_code}: {response.text}")
    
    def _parse_response(self, response: str) -> Dict[str, CoinSentiment]:
        """
        Parse multi-line Grok response into coin sentiments.
        
        Expected format (one line per coin):
        BTC: 45, 80
        ETH: -20, 65
        ...
        
        Handles various formats flexibly.
        """
        sentiments = {}
        
        # Split into lines
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try to find coin and extract numbers
            parsed = self._parse_line(line)
            if parsed:
                coin, sentiment, narrative = parsed
                if coin in TOP_COINS:
                    score = CoinSentiment.calculate_score(sentiment, narrative)
                    sentiments[coin] = CoinSentiment(
                        coin=coin,
                        sentiment=sentiment,
                        narrative=narrative,
                        score=score
                    )
        
        # Validate we got all coins (or log warning)
        missing = set(TOP_COINS) - set(sentiments.keys())
        if missing:
            logger.warning(f"Missing coins in response: {missing}")
        
        return sentiments
    
    def _parse_line(self, line: str) -> Optional[Tuple[str, float, float]]:
        """
        Parse a single line to extract coin, sentiment, and narrative.
        
        Handles formats like:
        - "BTC: 45, 80"
        - "BTC - sentiment: 45, narrative: 80"
        - "BTC 45 80"
        - "Bitcoin (BTC): +45, 80%"
        """
        line_upper = line.upper()
        
        # Find which coin this line is about
        coin = None
        for c in TOP_COINS:
            if c in line_upper:
                coin = c
                break
        
        if not coin:
            return None
        
        # Extract all numbers from the line
        numbers = re.findall(r'-?\d+(?:\.\d+)?', line)
        
        if len(numbers) >= 2:
            try:
                sentiment = float(numbers[0])
                narrative = float(numbers[1])
                
                # Clamp to valid ranges
                sentiment = max(-100, min(100, sentiment))
                narrative = max(0, min(100, narrative))
                
                return (coin, sentiment, narrative)
            except ValueError:
                pass
        
        return None
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_grok_client: Optional[GrokBatchClient] = None


def get_grok_client() -> GrokBatchClient:
    """Get or create the global Grok client"""
    global _grok_client
    if _grok_client is None:
        api_key = os.getenv('XAI_API_KEY', '')
        if not api_key:
            logger.warning("XAI_API_KEY not set!")
        _grok_client = GrokBatchClient(api_key)
    return _grok_client


async def fetch_all_sentiments() -> BatchSentimentResult:
    """
    Convenience function to fetch all sentiments in one call.
    
    Returns:
        BatchSentimentResult with all coin data
    """
    client = get_grok_client()
    return await client.get_batch_sentiment()


async def close_grok_client():
    """Close the global Grok client"""
    global _grok_client
    if _grok_client:
        await _grok_client.close()
        _grok_client = None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SERVICE LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def run_signal_engine():
    """
    Main signal engine service loop.
    Periodically fetches sentiments from Grok and publishes to Redis.
    """
    from events import get_event_bus, SignalGeneratedEvent
    
    logger.info("Starting Signal Engine service...")
    
    # Check for API key
    api_key = os.getenv('XAI_API_KEY', '')
    if not api_key:
        logger.error("XAI_API_KEY not set! Signal engine cannot run.")
        return
    
    bus = get_event_bus()
    await bus.connect()
    
    # Fetch interval (every 60 seconds)
    FETCH_INTERVAL = 60
    
    logger.info(f"Signal engine running. Fetching every {FETCH_INTERVAL}s")
    
    while True:
        try:
            # Fetch sentiments from Grok
            result = await fetch_all_sentiments()
            
            if result.success and result.sentiments:
                logger.info(f"Fetched {len(result.sentiments)} coin sentiments")
                
                # Publish each signal to Redis
                for coin, sentiment in result.sentiments.items():
                    event = SignalGeneratedEvent(
                        signal_id=uuid4(),
                        symbol=f"{coin}USDT",
                        direction="long" if sentiment.score > 0 else "short",
                        score=abs(sentiment.score),
                        sentiment_raw=sentiment.sentiment,
                        narrative_strength=sentiment.narrative,
                        grok_response=f"Sentiment: {sentiment.sentiment}, Narrative: {sentiment.narrative}",
                        filters_passed=True,
                        source="grok_batch"
                    )
                    await bus.publish(event)
                    logger.debug(f"Published signal for {coin}: score={sentiment.score:.1f}")
            else:
                logger.warning(f"Failed to fetch sentiments: {result.error_message}")
            
        except Exception as e:
            logger.error(f"Error in signal engine loop: {e}")
        
        # Wait before next fetch
        await asyncio.sleep(FETCH_INTERVAL)


async def main():
    """Main entry point for the signal engine service"""
    logger.info("=" * 60)
    logger.info("Signal Engine starting")
    logger.info("=" * 60)
    
    try:
        await run_signal_engine()
    except KeyboardInterrupt:
        logger.info("Signal engine stopped by user")
    finally:
        await close_grok_client()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())