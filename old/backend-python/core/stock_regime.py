"""
Stock Market Regime Detection - VIX-based volatility regime for stocks

Uses VIX (CBOE Volatility Index) to determine market regime:
- Low Vol: VIX < 15 - Complacent market, lower thresholds
- Normal: VIX 15-25 - Standard market conditions
- High Vol: VIX > 25 - Stressed market, higher thresholds
- Crisis: VIX > 35 - Extreme stress, skip trading
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


@dataclass
class StockRegimeInfo:
    """Current stock market regime information"""
    vix_value: float
    regime: str  # 'low_vol', 'normal', 'high_vol', 'crisis'
    regime_display: str
    score_threshold: float
    should_trade: bool
    
    # Context
    timestamp: datetime
    vix_change_24h: float = 0.0
    spy_price: Optional[float] = None
    
    def to_dict(self) -> dict:
        return {
            "vix_value": self.vix_value,
            "regime": self.regime,
            "regime_display": self.regime_display,
            "score_threshold": self.score_threshold,
            "should_trade": self.should_trade,
            "timestamp": self.timestamp.isoformat(),
            "vix_change_24h": self.vix_change_24h,
        }


class StockRegimeDetector:
    """
    Detects stock market regime using VIX.
    
    VIX Thresholds:
    - < 15: Low volatility (complacent market)
    - 15-25: Normal
    - 25-35: Elevated (caution)
    - > 35: Crisis (stop trading)
    """
    
    # VIX thresholds
    LOW_VOL_THRESHOLD = 15
    HIGH_VOL_THRESHOLD = 25
    CRISIS_THRESHOLD = 35
    
    # Score thresholds by regime (higher threshold = more conservative)
    SCORE_THRESHOLDS = {
        "low_vol": 65,   # Lower bar when market is calm
        "normal": 70,    # Standard threshold
        "high_vol": 75,  # Higher bar when volatile
        "crisis": 999,   # Don't trade
    }
    
    def __init__(self):
        self._last_vix: float = 20.0  # Default
        self._last_update: Optional[datetime] = None
        self._cache_ttl = 300  # 5 minutes
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    async def fetch_vix(self) -> float:
        """
        Fetch current VIX value from Yahoo Finance.
        
        VIX symbol: ^VIX
        """
        # Check cache
        if self._last_update:
            age = (datetime.utcnow() - self._last_update).total_seconds()
            if age < self._cache_ttl:
                return self._last_vix
        
        client = await self._get_client()
        
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX"
            response = await client.get(url, params={"interval": "1m", "range": "1d"})
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch VIX: {response.status_code}")
                return self._last_vix
            
            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            meta = result.get("meta", {})
            
            vix = meta.get("regularMarketPrice", self._last_vix)
            self._last_vix = vix
            self._last_update = datetime.utcnow()
            
            logger.info(f"VIX updated: {vix:.2f}")
            return vix
            
        except Exception as e:
            logger.error(f"Error fetching VIX: {e}")
            return self._last_vix
    
    def determine_regime(self, vix: float) -> Tuple[str, str, float, bool]:
        """
        Determine market regime from VIX value.
        
        Args:
            vix: Current VIX value
        
        Returns:
            Tuple of (regime, display_name, score_threshold, should_trade)
        """
        if vix >= self.CRISIS_THRESHOLD:
            return "crisis", "Crisis - Trading Paused", self.SCORE_THRESHOLDS["crisis"], False
        elif vix >= self.HIGH_VOL_THRESHOLD:
            return "high_vol", "High Volatility", self.SCORE_THRESHOLDS["high_vol"], True
        elif vix >= self.LOW_VOL_THRESHOLD:
            return "normal", "Normal", self.SCORE_THRESHOLDS["normal"], True
        else:
            return "low_vol", "Low Volatility", self.SCORE_THRESHOLDS["low_vol"], True
    
    async def get_regime(self) -> StockRegimeInfo:
        """Get current stock market regime"""
        vix = await self.fetch_vix()
        regime, display, threshold, should_trade = self.determine_regime(vix)
        
        return StockRegimeInfo(
            vix_value=vix,
            regime=regime,
            regime_display=display,
            score_threshold=threshold,
            should_trade=should_trade,
            timestamp=datetime.utcnow(),
        )
    
    async def close(self):
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED REGIME INTERFACE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class UnifiedRegimeInfo:
    """Unified regime info across asset types"""
    
    # Crypto regime (BTC ATR based)
    crypto_regime: str
    crypto_threshold: float
    crypto_btc_atr_pct: float
    
    # Stock regime (VIX based)
    stock_regime: str
    stock_threshold: float
    stock_vix: float
    stock_should_trade: bool
    
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            "crypto": {
                "regime": self.crypto_regime,
                "threshold": self.crypto_threshold,
                "btc_atr_pct": self.crypto_btc_atr_pct,
            },
            "stock": {
                "regime": self.stock_regime,
                "threshold": self.stock_threshold,
                "vix": self.stock_vix,
                "should_trade": self.stock_should_trade,
            },
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_stock_regime_detector: Optional[StockRegimeDetector] = None


def get_stock_regime_detector() -> StockRegimeDetector:
    """Get or create global stock regime detector"""
    global _stock_regime_detector
    if _stock_regime_detector is None:
        _stock_regime_detector = StockRegimeDetector()
    return _stock_regime_detector

