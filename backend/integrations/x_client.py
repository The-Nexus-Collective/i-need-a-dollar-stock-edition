"""
X (Twitter) API Client - Hype detection and sentiment analysis for stocks

Uses X API v2 for:
- Searching tweets about stocks
- Engagement-based hype scoring
- Sentiment analysis via Grok

Environment Variables:
- X_BEARER_TOKEN: X API Bearer token
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class Tweet:
    """Represents a tweet with engagement metrics"""
    id: str
    text: str
    author_id: str
    created_at: datetime
    
    # Engagement metrics
    like_count: int = 0
    retweet_count: int = 0
    reply_count: int = 0
    quote_count: int = 0
    
    # Computed
    @property
    def engagement_score(self) -> float:
        """Weighted engagement score"""
        return (
            self.like_count * 1.0 +
            self.retweet_count * 2.0 +
            self.reply_count * 1.5 +
            self.quote_count * 2.5
        )


@dataclass
class HypeScore:
    """Hype score for a stock based on X activity"""
    symbol: str
    score: float  # 0-100 normalized hype score
    tweet_count: int
    total_engagement: float
    avg_engagement: float
    top_tweets: List[Tweet] = field(default_factory=list)
    
    # Sentiment from Grok analysis
    sentiment_score: float = 0  # -100 to +100
    
    # Metadata
    query_used: str = ""
    analyzed_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score,
            "tweet_count": self.tweet_count,
            "total_engagement": self.total_engagement,
            "avg_engagement": self.avg_engagement,
            "sentiment_score": self.sentiment_score,
            "analyzed_at": self.analyzed_at.isoformat(),
            "top_tweets": [
                {"id": t.id, "text": t.text[:100], "engagement": t.engagement_score}
                for t in self.top_tweets[:3]
            ]
        }


class XHypeDetector:
    """
    Detects hyped stocks via X/Twitter API.
    
    Features:
    - Search for stock mentions with engagement thresholds
    - Hype keyword detection
    - Engagement-based scoring
    - Integration with Grok for sentiment
    """
    
    BASE_URL = "https://api.twitter.com/2"
    
    # Hype keywords that indicate bullish momentum
    HYPE_KEYWORDS = [
        "breakout", "moon", "moonshot", "rocket", "explosion",
        "massive gains", "undervalued", "gem", "going parabolic",
        "all time high", "ATH", "bullish", "buy the dip",
        "100x", "1000x", "sleeping giant", "accumulating"
    ]
    
    # Crypto-specific keywords
    CRYPTO_KEYWORDS = [
        "altcoin", "memecoin", "defi", "nft", "web3",
        "pump", "ape", "degen", "airdrop", "listing",
        "binance", "coinbase", "launch", "presale"
    ]
    
    # Narrative keywords for crypto
    CRYPTO_NARRATIVES = {
        "ai": ["AI crypto", "artificial intelligence", "machine learning", "LLM"],
        "meme": ["meme coin", "doge", "shib", "pepe", "wojak", "frog"],
        "defi": ["defi", "yield", "staking", "lending", "liquidity"],
        "l2": ["layer 2", "L2", "rollup", "zk", "optimistic"],
        "rwa": ["RWA", "real world asset", "tokenized", "tokenization"],
        "gaming": ["gamefi", "P2E", "play to earn", "gaming"],
    }
    
    # Defense/tech specific keywords (for stocks)
    SECTOR_KEYWORDS = {
        "defense": ["contract", "Pentagon", "DoD", "military", "defense AI"],
        "tech": ["AI", "artificial intelligence", "machine learning", "chip", "semiconductor"],
    }
    
    # Minimum engagement thresholds
    MIN_LIKES = 50
    MIN_RETWEETS = 10
    
    def __init__(self):
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, HypeScore] = {}
        self._cache_ttl = 900  # 15 minutes
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.bearer_token}",
                    "Content-Type": "application/json",
                },
                timeout=30.0
            )
        return self._client
    
    async def search_tweets(
        self,
        query: str,
        max_results: int = 100
    ) -> List[Tweet]:
        """
        Search for recent tweets matching query.
        
        Args:
            query: X search query
            max_results: Maximum tweets to return (10-100)
        
        Returns:
            List of Tweet objects
        """
        if not self.bearer_token:
            logger.warning("X_BEARER_TOKEN not set, returning empty results")
            return []
        
        client = await self._get_client()
        
        try:
            response = await client.get(
                f"{self.BASE_URL}/tweets/search/recent",
                params={
                    "query": query,
                    "max_results": min(max_results, 100),
                    "tweet.fields": "created_at,public_metrics,author_id",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"X API error: {response.status_code} - {response.text}")
                return []
            
            data = response.json()
            tweets = []
            
            for tweet_data in data.get("data", []):
                metrics = tweet_data.get("public_metrics", {})
                tweets.append(Tweet(
                    id=tweet_data["id"],
                    text=tweet_data["text"],
                    author_id=tweet_data.get("author_id", ""),
                    created_at=datetime.fromisoformat(
                        tweet_data["created_at"].replace("Z", "+00:00")
                    ),
                    like_count=metrics.get("like_count", 0),
                    retweet_count=metrics.get("retweet_count", 0),
                    reply_count=metrics.get("reply_count", 0),
                    quote_count=metrics.get("quote_count", 0),
                ))
            
            logger.info(f"Found {len(tweets)} tweets for query: {query[:50]}...")
            return tweets
            
        except Exception as e:
            logger.error(f"Error searching X: {e}")
            return []
    
    def _build_stock_query(self, symbol: str, include_hype: bool = True) -> str:
        """Build search query for a stock symbol"""
        parts = [f"${symbol}"]  # Cashtag
        
        if include_hype:
            # Add some hype keywords
            hype_terms = " OR ".join(self.HYPE_KEYWORDS[:5])
            parts.append(f"({hype_terms})")
        
        # Engagement filter
        parts.append(f"-is:retweet lang:en")
        
        return " ".join(parts)
    
    async def get_hype_score(self, symbol: str) -> HypeScore:
        """
        Get hype score for a single stock.
        
        Args:
            symbol: Stock symbol (e.g., "PLTR")
        
        Returns:
            HypeScore with engagement metrics
        """
        # Check cache
        cache_key = f"{symbol}_{datetime.utcnow().strftime('%Y%m%d%H')}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        query = self._build_stock_query(symbol)
        tweets = await self.search_tweets(query, max_results=100)
        
        # Filter by engagement
        high_engagement = [
            t for t in tweets
            if t.like_count >= self.MIN_LIKES or t.retweet_count >= self.MIN_RETWEETS
        ]
        
        if not high_engagement:
            # Fallback to all tweets if none meet threshold
            high_engagement = tweets
        
        # Calculate scores
        total_engagement = sum(t.engagement_score for t in high_engagement)
        avg_engagement = total_engagement / len(high_engagement) if high_engagement else 0
        
        # Normalize to 0-100 score
        # Use log scale for engagement (1000 engagement = ~70 score)
        import math
        raw_score = math.log10(max(1, total_engagement)) * 20
        normalized_score = min(100, max(0, raw_score))
        
        # Sort by engagement for top tweets
        high_engagement.sort(key=lambda t: t.engagement_score, reverse=True)
        
        result = HypeScore(
            symbol=symbol,
            score=normalized_score,
            tweet_count=len(tweets),
            total_engagement=total_engagement,
            avg_engagement=avg_engagement,
            top_tweets=high_engagement[:5],
            query_used=query,
        )
        
        # Cache result
        self._cache[cache_key] = result
        
        logger.info(
            f"Hype score for {symbol}: {normalized_score:.1f} "
            f"({len(tweets)} tweets, {total_engagement:.0f} engagement)"
        )
        
        return result
    
    async def get_hype_scores(
        self,
        symbols: List[str]
    ) -> Dict[str, HypeScore]:
        """
        Get hype scores for multiple stocks.
        
        Args:
            symbols: List of stock symbols
        
        Returns:
            Dict mapping symbol -> HypeScore
        """
        results = {}
        
        # Process in parallel with rate limiting
        for symbol in symbols:
            try:
                score = await self.get_hype_score(symbol)
                results[symbol] = score
                await asyncio.sleep(0.5)  # Rate limit
            except Exception as e:
                logger.error(f"Error getting hype for {symbol}: {e}")
                results[symbol] = HypeScore(
                    symbol=symbol,
                    score=0,
                    tweet_count=0,
                    total_engagement=0,
                    avg_engagement=0,
                )
        
        return results
    
    async def get_top_hyped(
        self,
        symbols: List[str],
        min_score: float = 30,
        limit: int = 2
    ) -> List[HypeScore]:
        """
        Get the top hyped stocks from a list.
        
        Args:
            symbols: Candidate symbols
            min_score: Minimum hype score to consider
            limit: Max stocks to return
        
        Returns:
            Top hyped stocks sorted by score
        """
        scores = await self.get_hype_scores(symbols)
        
        # Filter and sort
        qualified = [
            s for s in scores.values()
            if s.score >= min_score
        ]
        qualified.sort(key=lambda s: s.score, reverse=True)
        
        return qualified[:limit]
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    def _build_crypto_query(self, coin: str, include_hype: bool = True) -> str:
        """Build search query for a cryptocurrency"""
        parts = [f"${coin}"]  # Cashtag
        
        if include_hype:
            hype_terms = " OR ".join(self.HYPE_KEYWORDS[:5] + self.CRYPTO_KEYWORDS[:3])
            parts.append(f"({hype_terms})")
        
        parts.append("-is:retweet lang:en")
        return " ".join(parts)
    
    async def search_crypto_hype(
        self,
        coins: List[str],
        queries: Optional[List[str]] = None,
    ) -> Dict[str, List[Tweet]]:
        """
        Search for crypto hype across multiple coins.
        
        Args:
            coins: List of coin symbols (e.g., ['BTC', 'ETH', 'SOL'])
            queries: Optional custom queries to add
        
        Returns:
            Dict mapping coin -> list of tweets
        """
        results = {}
        
        # Search for each coin
        for coin in coins:
            query = self._build_crypto_query(coin)
            tweets = await self.search_tweets(query, max_results=50)
            results[coin] = tweets
            await asyncio.sleep(0.5)  # Rate limiting
        
        # Run custom queries if provided
        if queries:
            for query in queries[:3]:  # Limit queries
                tweets = await self.search_tweets(query, max_results=50)
                # Extract coins from tweets
                for tweet in tweets:
                    for coin in self._extract_coins(tweet.text):
                        if coin not in results:
                            results[coin] = []
                        results[coin].append(tweet)
                await asyncio.sleep(0.5)
        
        return results
    
    def _extract_coins(self, text: str) -> List[str]:
        """Extract cryptocurrency symbols from tweet text."""
        import re
        
        # Match $SYMBOL patterns (2-10 uppercase letters)
        cashtags = re.findall(r'\$([A-Z]{2,10})\b', text.upper())
        
        # Filter out non-crypto
        skip = {'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'INR', 'AUD', 'CAD', 'SPY', 'QQQ'}
        coins = [c for c in cashtags if c not in skip]
        
        return list(set(coins))
    
    async def detect_trending_narratives(self) -> Dict[str, List[Tweet]]:
        """
        Detect trending crypto narratives on X.
        
        Returns:
            Dict mapping narrative -> top tweets
        """
        narratives = {}
        
        for narrative, keywords in self.CRYPTO_NARRATIVES.items():
            query = f"({' OR '.join(keywords)}) crypto -is:retweet lang:en min_faves:50"
            tweets = await self.search_tweets(query, max_results=30)
            
            if tweets:
                narratives[narrative] = sorted(
                    tweets,
                    key=lambda t: t.engagement_score,
                    reverse=True
                )[:5]
            
            await asyncio.sleep(0.5)
        
        return narratives
    
    async def get_crypto_hype_score(self, coin: str) -> HypeScore:
        """
        Get hype score for a cryptocurrency.
        
        Similar to stock hype score but with crypto-specific query.
        """
        cache_key = f"crypto_{coin}_{datetime.utcnow().strftime('%Y%m%d%H')}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        query = self._build_crypto_query(coin)
        tweets = await self.search_tweets(query, max_results=100)
        
        # Filter by engagement
        high_engagement = [
            t for t in tweets
            if t.like_count >= 20 or t.retweet_count >= 5  # Lower thresholds for crypto
        ]
        
        if not high_engagement:
            high_engagement = tweets
        
        total_engagement = sum(t.engagement_score for t in high_engagement)
        avg_engagement = total_engagement / len(high_engagement) if high_engagement else 0
        
        import math
        raw_score = math.log10(max(1, total_engagement)) * 20
        normalized_score = min(100, max(0, raw_score))
        
        high_engagement.sort(key=lambda t: t.engagement_score, reverse=True)
        
        result = HypeScore(
            symbol=coin,
            score=normalized_score,
            tweet_count=len(tweets),
            total_engagement=total_engagement,
            avg_engagement=avg_engagement,
            top_tweets=high_engagement[:5],
            query_used=query,
        )
        
        self._cache[cache_key] = result
        
        logger.info(
            f"Crypto hype score for {coin}: {normalized_score:.1f} "
            f"({len(tweets)} tweets, {total_engagement:.0f} engagement)"
        )
        
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_x_detector: Optional[XHypeDetector] = None


def get_x_hype_detector() -> XHypeDetector:
    """Get or create global X hype detector"""
    global _x_detector
    if _x_detector is None:
        _x_detector = XHypeDetector()
    return _x_detector

