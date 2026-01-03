"""
Trading Filters - Volume and market data filters for signal validation
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# AGGRESSIVE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Relaxed filter thresholds
VOLUME_FILTER_RATIO = 0.70  # Was 0.80 - more permissive
ATR_PERIODS = 14  # ATR calculation periods

# Funding rate filter (for perpetuals)
FUNDING_RATE_MAX = 0.0003  # 0.03% max funding rate

# On-chain and technical filters
ON_CHAIN_MIN = 0.05  # 5% minimum on-chain activity
TECHNICAL_BUFFER = 0.10  # 10% technical buffer

# ═══════════════════════════════════════════════════════════════════════════════
# DYNAMIC SCORE THRESHOLD - AGGRESSIVE MODE
# ═══════════════════════════════════════════════════════════════════════════════

# Volatility thresholds (BTC ATR as % of price)
HIGH_VOL_ATR_THRESHOLD = 1.2  # > 1.2% = high volatility
LOW_VOL_ATR_THRESHOLD = 0.8   # < 0.8% = low volatility / chop

# AGGRESSIVE: Lowered score thresholds (was 70/67/65)
SCORE_THRESHOLD_HIGH_VOL = 55  # High vol: still trade
SCORE_THRESHOLD_NORMAL = 50    # Normal: aggressive
SCORE_THRESHOLD_LOW_VOL = 45   # Low vol: very permissive (-5 dynamic)

# Current regime state (shared across strategy)
_current_regime: str = "normal"
_current_threshold: float = SCORE_THRESHOLD_NORMAL
_btc_atr_percent: float = 0.0


@dataclass
class MarketData:
    """Market data for a coin"""
    coin: str
    price: float
    volume_1h: float
    volume_24h_avg: float
    atr_1h: float
    volume_filter_pass: bool
    
    @property
    def volume_ratio(self) -> float:
        """Current volume as ratio of 24h average"""
        if self.volume_24h_avg == 0:
            return 0
        return self.volume_1h / self.volume_24h_avg


class BinanceMarketData:
    """
    Fetches market data from Binance for filtering decisions.
    Uses public endpoints only - no API keys required.
    """
    
    def __init__(self):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use perpetual futures
            }
        })
    
    async def get_current_price(self, coin: str) -> float:
        """Get current mid-price for a coin"""
        try:
            symbol = f"{coin}/USDT"
            ticker = await self.exchange.fetch_ticker(symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching price for {coin}: {e}")
            raise
    
    async def get_volume_data(self, coin: str) -> Tuple[float, float]:
        """
        Get volume data for filtering.
        
        Returns:
            (volume_1h, volume_24h_avg)
            - volume_1h: Volume of the last completed 1h candle
            - volume_24h_avg: Average 1h volume over the last 24 hours
        """
        try:
            symbol = f"{coin}/USDT"
            
            # Fetch last 25 1h candles (24 for average + 1 current incomplete)
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe='1h',
                limit=25
            )
            
            if len(ohlcv) < 25:
                logger.warning(f"Insufficient candle data for {coin}: {len(ohlcv)} candles")
                # Use what we have
                if len(ohlcv) < 2:
                    return 0, 0
            
            # Last completed candle (index -2, since -1 is current incomplete)
            volume_1h = float(ohlcv[-2][5])  # Volume is at index 5
            
            # Average of last 24 completed candles (excluding current)
            volumes_24h = [float(candle[5]) for candle in ohlcv[-25:-1]]
            volume_24h_avg = sum(volumes_24h) / len(volumes_24h) if volumes_24h else 0
            
            return volume_1h, volume_24h_avg
            
        except Exception as e:
            logger.error(f"Error fetching volume for {coin}: {e}")
            raise
    
    async def get_atr(self, coin: str, periods: int = ATR_PERIODS) -> float:
        """
        Calculate 1-hour ATR (Average True Range) for position sizing.
        
        Args:
            coin: Coin symbol (e.g., 'BTC')
            periods: Number of periods for ATR calculation (default 14)
        
        Returns:
            ATR value in USDT
        """
        try:
            symbol = f"{coin}/USDT"
            
            # Fetch enough candles for ATR calculation
            ohlcv = await self.exchange.fetch_ohlcv(
                symbol,
                timeframe='1h',
                limit=periods + 2  # Extra for TR calculation
            )
            
            if len(ohlcv) < periods + 1:
                logger.warning(f"Insufficient data for ATR: {len(ohlcv)} candles")
                # Fallback: estimate ATR as 2% of current price
                price = await self.get_current_price(coin)
                return price * 0.02
            
            # Calculate True Range for each period
            tr_values = []
            for i in range(1, len(ohlcv) - 1):  # Exclude current incomplete candle
                high = float(ohlcv[i][2])
                low = float(ohlcv[i][3])
                prev_close = float(ohlcv[i-1][4])
                
                # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_values.append(tr)
            
            # ATR = Simple Moving Average of True Range
            atr = sum(tr_values[-periods:]) / min(len(tr_values), periods)
            
            return atr
            
        except Exception as e:
            logger.error(f"Error calculating ATR for {coin}: {e}")
            raise
    
    async def get_full_market_data(self, coin: str) -> MarketData:
        """
        Fetch all market data needed for filtering and position sizing.
        
        Returns:
            MarketData object with all relevant data
        """
        try:
            # Fetch all data concurrently
            price_task = self.get_current_price(coin)
            volume_task = self.get_volume_data(coin)
            atr_task = self.get_atr(coin)
            
            price, (volume_1h, volume_24h_avg), atr = await asyncio.gather(
                price_task, volume_task, atr_task
            )
            
            # Check volume filter
            volume_filter_pass = False
            if volume_24h_avg > 0:
                volume_ratio = volume_1h / volume_24h_avg
                volume_filter_pass = volume_ratio >= VOLUME_FILTER_RATIO
            
            return MarketData(
                coin=coin,
                price=price,
                volume_1h=volume_1h,
                volume_24h_avg=volume_24h_avg,
                atr_1h=atr,
                volume_filter_pass=volume_filter_pass
            )
            
        except Exception as e:
            logger.error(f"Error fetching market data for {coin}: {e}")
            # Return data that fails filters on error
            return MarketData(
                coin=coin,
                price=0,
                volume_1h=0,
                volume_24h_avg=0,
                atr_1h=0,
                volume_filter_pass=False
            )
    
    async def get_all_market_data(self, coins: list[str]) -> Dict[str, MarketData]:
        """
        Fetch market data for all coins concurrently.
        
        Args:
            coins: List of coin symbols
        
        Returns:
            Dict mapping coin -> MarketData
        """
        tasks = [self.get_full_market_data(coin) for coin in coins]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        market_data = {}
        for coin, result in zip(coins, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to fetch market data for {coin}: {result}")
                market_data[coin] = MarketData(
                    coin=coin,
                    price=0,
                    volume_1h=0,
                    volume_24h_avg=0,
                    atr_1h=0,
                    volume_filter_pass=False
                )
            else:
                market_data[coin] = result
        
        return market_data
    
    async def close(self):
        """Close the exchange connection"""
        await self.exchange.close()


def determine_volatility_regime(btc_atr_percent: float) -> tuple:
    """
    Determine volatility regime based on BTC 1-hour ATR.
    
    Regime logic:
    - BTC ATR > 1.2% of price → High Volatility → threshold 70
    - BTC ATR < 0.8% of price → Low Vol/Chop → threshold 65  
    - Else → Normal → threshold 67
    
    Args:
        btc_atr_percent: BTC ATR as percentage of price (e.g., 1.0 = 1%)
    
    Returns:
        Tuple of (regime: str, threshold: float)
    """
    global _current_regime, _current_threshold, _btc_atr_percent
    
    old_regime = _current_regime
    old_threshold = _current_threshold
    _btc_atr_percent = btc_atr_percent
    
    if btc_atr_percent > HIGH_VOL_ATR_THRESHOLD:
        _current_regime = "high_vol"
        _current_threshold = SCORE_THRESHOLD_HIGH_VOL
    elif btc_atr_percent < LOW_VOL_ATR_THRESHOLD:
        _current_regime = "low_vol"
        _current_threshold = SCORE_THRESHOLD_LOW_VOL
    else:
        _current_regime = "normal"
        _current_threshold = SCORE_THRESHOLD_NORMAL
    
    # Log if threshold changed
    if old_threshold != _current_threshold:
        logger.info(
            f"THRESHOLD ADJUSTED: {old_regime}→{_current_regime} | "
            f"BTC ATR={btc_atr_percent:.2f}% | "
            f"Threshold: {old_threshold}→{_current_threshold}"
        )
    
    return _current_regime, _current_threshold


def get_current_regime_info() -> dict:
    """
    Get current volatility regime information for dashboard display.
    
    Returns:
        Dict with regime, threshold, and BTC ATR info
    """
    return {
        "regime": _current_regime,
        "regime_display": {
            "high_vol": "High Vol",
            "normal": "Normal",
            "low_vol": "Low Vol"
        }.get(_current_regime, "Unknown"),
        "threshold": _current_threshold,
        "btc_atr_percent": round(_btc_atr_percent, 2),
        "thresholds": {
            "high_vol": SCORE_THRESHOLD_HIGH_VOL,
            "normal": SCORE_THRESHOLD_NORMAL,
            "low_vol": SCORE_THRESHOLD_LOW_VOL
        }
    }


def check_score_filter(score: float, threshold: float = None) -> bool:
    """
    Check if absolute score meets the minimum threshold.
    
    Args:
        score: Combined score (sentiment * narrative/100)
        threshold: Minimum absolute score to trade. 
                   If None, uses the current dynamic threshold.
    
    Returns:
        True if |score| >= threshold
    """
    if threshold is None:
        threshold = _current_threshold
    return abs(score) >= threshold


def get_dynamic_threshold() -> float:
    """Get the current dynamic score threshold."""
    return _current_threshold


def check_volume_filter(volume_1h: float, volume_24h_avg: float, ratio: float = VOLUME_FILTER_RATIO) -> bool:
    """
    Check if 1h volume meets the filter threshold.
    
    Args:
        volume_1h: Last completed 1h candle volume
        volume_24h_avg: Average of last 24 1h candles
        ratio: Minimum ratio (default 0.80 = 80%)
    
    Returns:
        True if volume_1h >= ratio * volume_24h_avg
    """
    if volume_24h_avg <= 0:
        return False
    return volume_1h >= (ratio * volume_24h_avg)


# Singleton instance
_market_data_client: Optional[BinanceMarketData] = None


def get_market_data_client() -> BinanceMarketData:
    """Get or create the global market data client"""
    global _market_data_client
    if _market_data_client is None:
        _market_data_client = BinanceMarketData()
    return _market_data_client


async def init_market_data_client() -> BinanceMarketData:
    """Initialize the market data client"""
    return get_market_data_client()
