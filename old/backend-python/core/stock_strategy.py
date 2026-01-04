"""
Stock Trading Strategy - Sentiment-driven stock trading with X hype integration

Strategy Overview:
- Core Portfolio (80%): Top 10 tech stocks via Grok sentiment
- Reserved Portfolio (20%): High-growth/defense stocks via X hype detection
- Market hours: 9:30 AM - 4:00 PM ET
- Cycle: Every 4 hours during market hours
- Flatten at close

Harmonic with crypto strategy:
- Same risk limits (15% per-asset, 70% max deployed, 4% daily loss)
- Same leverage range (3-5x via CFDs)
- Same ATR-based SL/TP
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from models.asset import AssetType, AssetRegistry
from .stock_simulator import StockSimulator, StockQuote, get_stock_simulator
from .stock_regime import StockRegimeDetector, StockRegimeInfo, get_stock_regime_detector
from .market_hours import MarketHoursManager, MarketStatus, get_market_hours_manager
from integrations.x_client import XHypeDetector, HypeScore, get_x_hype_detector

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION (Harmonic with crypto)
# ═══════════════════════════════════════════════════════════════════════════════

# Risk Parameters (same as crypto for harmony)
RISK_PER_TRADE = 0.02          # 2% risk per trade
STOP_LOSS_ATR_MULT = 1.5       # SL at 1.5x ATR
TAKE_PROFIT_ATR_MULT = 2.0     # TP at 2.0x ATR

# Leverage (dynamic 3-5x)
MIN_LEVERAGE = 3.0
MAX_LEVERAGE = 5.0

# Portfolio Allocation
CORE_ALLOCATION = 0.80         # 80% for core stocks
RESERVED_ALLOCATION = 0.20     # 20% for hype plays

# Filter thresholds
MIN_HYPE_SCORE = 30            # Minimum X hype score for reserved


@dataclass
class StockSentiment:
    """Sentiment data for a stock"""
    symbol: str
    score: float              # -100 to +100
    narrative: float          # 0 to 100
    driver: str               # Key sentiment driver
    
    # Technical context
    price: float = 0
    atr_1d: float = 0         # Daily ATR (use daily for stocks)
    volume_ratio: float = 1.0  # Volume vs 20-day avg
    ema_20: float = 0
    rsi_14: float = 50
    
    # Hype (for reserved stocks)
    hype_score: float = 0
    
    @property
    def combined_score(self) -> float:
        """Combined score weighted by narrative strength"""
        return self.score * (self.narrative / 100)
    
    @property
    def passes_technical(self) -> bool:
        """Check technical filters"""
        if self.score > 0:  # Long
            return self.price > self.ema_20 and self.rsi_14 < 65
        else:  # Short
            return self.price < self.ema_20 and self.rsi_14 > 35
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": self.score,
            "narrative": self.narrative,
            "combined_score": self.combined_score,
            "driver": self.driver,
            "price": self.price,
            "hype_score": self.hype_score,
            "passes_technical": self.passes_technical,
        }


@dataclass
class StockDecision:
    """Trading decision for stocks"""
    timestamp: datetime
    
    # Selection
    core_picks: List[StockSentiment]
    reserved_picks: List[StockSentiment]
    
    # Market context
    market_status: MarketStatus
    regime_info: StockRegimeInfo
    
    # Decision
    action: str  # 'trade', 'skip', 'flatten'
    skip_reason: Optional[str] = None
    
    # Position sizing (if trading)
    total_position_size: float = 0
    leverage: float = 3.0
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "skip_reason": self.skip_reason,
            "core_picks": [p.to_dict() for p in self.core_picks],
            "reserved_picks": [p.to_dict() for p in self.reserved_picks],
            "market_open": self.market_status.is_open,
            "vix": self.regime_info.vix_value,
            "regime": self.regime_info.regime,
            "leverage": self.leverage,
        }


class StockStrategy:
    """
    Stock trading strategy with X hype integration.
    
    Flow:
    1. Check market hours - skip if closed
    2. Check regime (VIX) - skip if crisis
    3. Get Grok sentiment for core stocks
    4. Get X hype for reserved stocks
    5. Filter by score + technical
    6. Size positions with leverage
    7. Flatten at close
    """
    
    def __init__(self):
        self.config = AssetRegistry.get(AssetType.STOCK)
        self.simulator = get_stock_simulator()
        self.regime_detector = get_stock_regime_detector()
        self.market_hours = get_market_hours_manager()
        self.x_detector = get_x_hype_detector()
        
        # State
        self._last_decision: Optional[StockDecision] = None
        self._last_cycle: Optional[datetime] = None
    
    async def should_run_cycle(self) -> Tuple[bool, str]:
        """
        Check if strategy cycle should run.
        
        Returns:
            Tuple of (should_run, reason)
        """
        status = self.market_hours.get_status()
        
        if not status.is_open:
            return False, f"Market closed: {status.status_text}"
        
        if status.should_flatten:
            return True, "Flatten at close"
        
        if self._last_cycle is None:
            return True, "Initial cycle"
        
        # Check 4-hour interval
        if self.market_hours.should_run_cycle(self._last_cycle):
            return True, "4-hour cycle"
        
        return False, "Waiting for next cycle"
    
    async def get_core_sentiments(
        self,
        grok_client  # Pass in to avoid circular import
    ) -> List[StockSentiment]:
        """
        Get Grok sentiment for core stocks.
        
        Args:
            grok_client: GrokClient instance
        
        Returns:
            List of StockSentiment for core symbols
        """
        # Format prompt with stock symbols
        prompt = self.config.grok_prompt.format(
            symbols=", ".join(self.config.symbols)
        )
        
        # Get batch sentiment from Grok
        result = await grok_client.get_batch_sentiment(
            symbols=self.config.symbols,
            asset_type="stock"
        )
        
        # Check if we should reverse signals (contrarian mode)
        reverse_signals = os.getenv("REVERSE_SIGNALS", "").lower() == "true"
        
        sentiments = []
        if result.success and result.sentiments:
            for symbol, sentiment in result.sentiments.items():
                # Reverse signal if configured (contrarian mode)
                score = -sentiment.score if reverse_signals else sentiment.score
                
                sentiments.append(StockSentiment(
                    symbol=symbol,
                    score=score,
                    narrative=sentiment.narrative,
                    driver=sentiment.driver,
                ))
        
        return sentiments
    
    async def get_reserved_hype(self) -> List[StockSentiment]:
        """
        Get X hype scores for reserved stocks.
        
        Returns:
            List of StockSentiment for hyped reserved stocks
        """
        # Get hype scores from X
        top_hyped = await self.x_detector.get_top_hyped(
            symbols=self.config.reserved_symbols,
            min_score=MIN_HYPE_SCORE,
            limit=2
        )
        
        sentiments = []
        for hype in top_hyped:
            sentiments.append(StockSentiment(
                symbol=hype.symbol,
                score=hype.sentiment_score or 70,  # Default bullish if hyped
                narrative=70,  # Hype implies narrative
                driver="X hype",
                hype_score=hype.score,
            ))
        
        return sentiments
    
    async def enrich_with_quotes(
        self,
        sentiments: List[StockSentiment]
    ) -> List[StockSentiment]:
        """Add real-time price data to sentiments"""
        quotes = await self.simulator.get_quotes([s.symbol for s in sentiments])
        
        for sentiment in sentiments:
            quote = quotes.get(sentiment.symbol)
            if quote:
                sentiment.price = quote.price
                # TODO: Fetch ATR and EMA from data provider
                # For now, estimate ATR as 2% of price (typical stock volatility)
                sentiment.atr_1d = quote.price * 0.02
                sentiment.ema_20 = quote.price * 0.98  # Placeholder
        
        return sentiments
    
    def calculate_leverage(
        self,
        score: float,
        vix: float,
        regime: str
    ) -> float:
        """
        Calculate adaptive leverage based on conviction and volatility.
        
        Same logic as crypto for harmony.
        """
        # Base leverage from score conviction
        score_factor = min(abs(score), 85) / 85  # 0 to 1
        
        # Reduce leverage in high vol
        vol_factor = 1.0
        if regime == "high_vol":
            vol_factor = 0.7
        elif regime == "crisis":
            vol_factor = 0.0  # No leverage in crisis
        elif regime == "low_vol":
            vol_factor = 1.1  # Slightly higher in calm markets
        
        leverage = MIN_LEVERAGE + (MAX_LEVERAGE - MIN_LEVERAGE) * score_factor * vol_factor
        return max(MIN_LEVERAGE, min(MAX_LEVERAGE, leverage))
    
    def filter_candidates(
        self,
        sentiments: List[StockSentiment],
        threshold: float
    ) -> List[StockSentiment]:
        """Filter by score threshold and technical conditions"""
        qualified = []
        
        for s in sentiments:
            # Score filter
            if abs(s.combined_score) < threshold:
                logger.debug(f"{s.symbol}: Score {s.combined_score:.1f} < {threshold}")
                continue
            
            # Volume filter (when we have data)
            if s.volume_ratio < self.config.volume_filter_ratio:
                logger.debug(f"{s.symbol}: Volume {s.volume_ratio:.2f} < {self.config.volume_filter_ratio}")
                continue
            
            # Technical filter
            if not s.passes_technical:
                logger.debug(f"{s.symbol}: Failed technical filter")
                continue
            
            qualified.append(s)
        
        # Sort by absolute combined score
        qualified.sort(key=lambda s: abs(s.combined_score), reverse=True)
        
        return qualified
    
    async def run_cycle(
        self,
        equity: float,
        grok_client
    ) -> StockDecision:
        """
        Run one trading cycle.
        
        Args:
            equity: Current account equity in USD
            grok_client: GrokClient for sentiment
        
        Returns:
            StockDecision with picks and sizing
        """
        self._last_cycle = datetime.utcnow()
        
        # Get market status and regime
        market_status = self.market_hours.get_status()
        regime_info = await self.regime_detector.get_regime()
        
        # Check for flatten signal
        if market_status.should_flatten:
            logger.info("Flatten at close signal - closing all positions")
            return StockDecision(
                timestamp=datetime.utcnow(),
                core_picks=[],
                reserved_picks=[],
                market_status=market_status,
                regime_info=regime_info,
                action="flatten",
            )
        
        # Check regime
        if not regime_info.should_trade:
            logger.warning(f"Regime {regime_info.regime} - skipping trade")
            return StockDecision(
                timestamp=datetime.utcnow(),
                core_picks=[],
                reserved_picks=[],
                market_status=market_status,
                regime_info=regime_info,
                action="skip",
                skip_reason=f"VIX crisis: {regime_info.vix_value:.1f}",
            )
        
        # Get sentiments
        core_sentiments = await self.get_core_sentiments(grok_client)
        reserved_sentiments = await self.get_reserved_hype()
        
        # Enrich with quotes
        all_sentiments = core_sentiments + reserved_sentiments
        all_sentiments = await self.enrich_with_quotes(all_sentiments)
        
        core_sentiments = [s for s in all_sentiments if s.symbol in self.config.symbols]
        reserved_sentiments = [s for s in all_sentiments if s.symbol in self.config.reserved_symbols]
        
        # Filter by regime-adjusted threshold
        threshold = regime_info.score_threshold
        core_picks = self.filter_candidates(core_sentiments, threshold)[:2]  # Top 2
        reserved_picks = self.filter_candidates(reserved_sentiments, threshold * 0.8)[:1]  # Top 1
        
        if not core_picks and not reserved_picks:
            logger.info("No stocks passed filters")
            return StockDecision(
                timestamp=datetime.utcnow(),
                core_picks=[],
                reserved_picks=[],
                market_status=market_status,
                regime_info=regime_info,
                action="skip",
                skip_reason="No stocks passed filters",
            )
        
        # Calculate position sizing
        best = core_picks[0] if core_picks else reserved_picks[0]
        leverage = self.calculate_leverage(
            best.score,
            regime_info.vix_value,
            regime_info.regime
        )
        
        # Risk-based sizing
        risk_amount = equity * RISK_PER_TRADE
        stop_distance = best.atr_1d * STOP_LOSS_ATR_MULT
        position_size = (risk_amount * leverage) / stop_distance if stop_distance > 0 else 0
        
        decision = StockDecision(
            timestamp=datetime.utcnow(),
            core_picks=core_picks,
            reserved_picks=reserved_picks,
            market_status=market_status,
            regime_info=regime_info,
            action="trade",
            total_position_size=position_size,
            leverage=leverage,
        )
        
        self._last_decision = decision
        
        logger.info(
            f"Stock decision: {len(core_picks)} core, {len(reserved_picks)} reserved | "
            f"VIX: {regime_info.vix_value:.1f} | Leverage: {leverage:.1f}x"
        )
        
        return decision
    
    @property
    def last_decision(self) -> Optional[StockDecision]:
        """Get the last trading decision"""
        return self._last_decision


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_stock_strategy: Optional[StockStrategy] = None


def get_stock_strategy() -> StockStrategy:
    """Get or create global stock strategy"""
    global _stock_strategy
    if _stock_strategy is None:
        _stock_strategy = StockStrategy()
    return _stock_strategy

