"""
CoinGecko Integration - Dynamic coin discovery and market data.

Provides:
- Top coins by market cap and volume
- Price and volume data
- Coin metadata (age, exchanges, etc.)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class CoinInfo:
    """Coin information from CoinGecko."""
    id: str  # CoinGecko ID (e.g., 'bitcoin')
    symbol: str  # Trading symbol (e.g., 'BTC')
    name: str
    
    # Market data
    price_usd: float = 0.0
    market_cap: float = 0.0
    volume_24h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0
    
    # Metadata
    market_cap_rank: int = 0
    
    # Derived
    @property
    def binance_symbol(self) -> str:
        """Get Binance trading pair symbol."""
        return f"{self.symbol.upper()}USDT"
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "symbol": self.symbol,
            "name": self.name,
            "price_usd": self.price_usd,
            "market_cap": self.market_cap,
            "volume_24h": self.volume_24h,
            "price_change_24h": self.price_change_24h,
            "price_change_7d": self.price_change_7d,
            "market_cap_rank": self.market_cap_rank,
            "binance_symbol": self.binance_symbol,
        }


class CoinGeckoClient:
    """
    CoinGecko API client for market data.
    
    Features:
    - Rate limiting (10-50 calls/min on free tier)
    - Caching to reduce API calls
    - Batch fetching of top coins
    """
    
    BASE_URL = "https://api.coingecko.com/api/v3"
    
    # Symbols to skip (stablecoins, wrapped tokens)
    SKIP_SYMBOLS = {
        'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDP', 'GUSD', 'FRAX',
        'WBTC', 'WETH', 'STETH', 'WBNB', 'WMATIC',
        'UST', 'USDD', 'USTC',  # Algorithmic stables
    }
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None
        self._cache: Dict[str, tuple[datetime, any]] = {}
        self._cache_ttl = timedelta(minutes=5)
        self._rate_limit_delay = 1.5  # seconds between calls
        self._last_call = datetime.min
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30)
        return self._client
    
    async def _rate_limited_call(self, endpoint: str, params: Dict = None) -> Dict:
        """Make rate-limited API call."""
        # Rate limiting
        now = datetime.utcnow()
        elapsed = (now - self._last_call).total_seconds()
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        
        self._last_call = datetime.utcnow()
        
        # Check cache
        cache_key = f"{endpoint}:{str(params)}"
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return cached_data
        
        # Make request
        client = await self._get_client()
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                self._cache[cache_key] = (datetime.utcnow(), data)
                return data
            elif response.status_code == 429:
                logger.warning("CoinGecko rate limited, waiting...")
                await asyncio.sleep(60)
                return await self._rate_limited_call(endpoint, params)
            else:
                logger.error(f"CoinGecko API error: {response.status_code}")
                return {}
                
        except Exception as e:
            logger.error(f"CoinGecko request failed: {e}")
            return {}
    
    async def get_top_coins(
        self,
        limit: int = 200,
        min_volume: float = 10_000_000,
    ) -> List[CoinInfo]:
        """
        Get top coins by market cap.
        
        Args:
            limit: Maximum coins to return
            min_volume: Minimum 24h volume in USD
        
        Returns:
            List of CoinInfo objects
        """
        coins = []
        per_page = 100
        pages_needed = (limit + per_page - 1) // per_page
        
        for page in range(1, pages_needed + 1):
            data = await self._rate_limited_call(
                "/coins/markets",
                {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": page,
                    "sparkline": "false",
                    "price_change_percentage": "24h,7d",
                }
            )
            
            if not data:
                break
            
            for item in data:
                symbol = item.get("symbol", "").upper()
                
                # Skip stablecoins and wrapped tokens
                if symbol in self.SKIP_SYMBOLS:
                    continue
                
                volume = item.get("total_volume", 0) or 0
                if volume < min_volume:
                    continue
                
                coin = CoinInfo(
                    id=item.get("id", ""),
                    symbol=symbol,
                    name=item.get("name", ""),
                    price_usd=item.get("current_price", 0) or 0,
                    market_cap=item.get("market_cap", 0) or 0,
                    volume_24h=volume,
                    price_change_24h=item.get("price_change_percentage_24h", 0) or 0,
                    price_change_7d=item.get("price_change_percentage_7d_in_currency", 0) or 0,
                    market_cap_rank=item.get("market_cap_rank", 0) or 0,
                )
                coins.append(coin)
                
                if len(coins) >= limit:
                    break
            
            if len(coins) >= limit:
                break
        
        logger.info(f"Fetched {len(coins)} coins from CoinGecko (min vol: ${min_volume:,.0f})")
        return coins
    
    async def get_top_gainers(self, limit: int = 20) -> List[CoinInfo]:
        """Get top gaining coins in last 24h."""
        all_coins = await self.get_top_coins(limit=200)
        
        # Sort by price change
        gainers = sorted(
            [c for c in all_coins if c.price_change_24h > 0],
            key=lambda c: c.price_change_24h,
            reverse=True
        )
        
        return gainers[:limit]
    
    async def get_top_volume(self, limit: int = 50) -> List[CoinInfo]:
        """Get coins with highest 24h volume."""
        all_coins = await self.get_top_coins(limit=200)
        
        # Sort by volume
        by_volume = sorted(
            all_coins,
            key=lambda c: c.volume_24h,
            reverse=True
        )
        
        return by_volume[:limit]
    
    async def get_coin_info(self, coin_id: str) -> Optional[CoinInfo]:
        """Get detailed info for a specific coin."""
        data = await self._rate_limited_call(f"/coins/{coin_id}")
        
        if not data:
            return None
        
        market_data = data.get("market_data", {})
        
        return CoinInfo(
            id=data.get("id", ""),
            symbol=data.get("symbol", "").upper(),
            name=data.get("name", ""),
            price_usd=market_data.get("current_price", {}).get("usd", 0),
            market_cap=market_data.get("market_cap", {}).get("usd", 0),
            volume_24h=market_data.get("total_volume", {}).get("usd", 0),
            price_change_24h=market_data.get("price_change_percentage_24h", 0) or 0,
            price_change_7d=market_data.get("price_change_percentage_7d", 0) or 0,
            market_cap_rank=data.get("market_cap_rank", 0) or 0,
        )
    
    async def search_coin(self, query: str) -> List[Dict]:
        """Search for coins by name or symbol."""
        data = await self._rate_limited_call("/search", {"query": query})
        
        coins = data.get("coins", [])
        return [
            {
                "id": c.get("id"),
                "symbol": c.get("symbol", "").upper(),
                "name": c.get("name"),
                "market_cap_rank": c.get("market_cap_rank"),
            }
            for c in coins[:10]
        ]
    
    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_client: Optional[CoinGeckoClient] = None


def get_coingecko_client() -> CoinGeckoClient:
    """Get or create global CoinGecko client."""
    global _client
    if _client is None:
        _client = CoinGeckoClient()
    return _client

