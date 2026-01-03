"""
Strategy Engine - Aggressive Trading Strategy (Testing Mode)

AGGRESSIVE CONFIGURATION:
1. Cycle every 15 minutes (was 60)
2. Select top 5-8 coins by |Score| (was 1-2)
3. Target 80-90% deployment (was 70%)
4. Relaxed filters: score>=50, vol>=70%
5. Leverage: 4-7x dynamic (was 3-5x)
6. Rebalance on 15% score shift
7. Risk: 2% new / 1.5% rebalance
8. Per-asset 20%, max deployed 90%, daily loss 6%
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select

from .signal_engine import (
    TOP_COINS,
    BatchSentimentResult,
    CoinSentiment,
    fetch_all_sentiments,
)
from .filters import (
    MarketData,
    get_market_data_client,
    check_score_filter,
    check_volume_filter,
    determine_volatility_regime,
    get_current_regime_info,
    get_dynamic_threshold,
)
from models import AsyncSessionLocal, Signal, Position, PortfolioSnapshot

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# AGGRESSIVE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Cycle timing
CYCLE_MINUTES = int(os.getenv('CYCLE_MINUTES', '15'))  # 15 min cycles (was 60)

# Coin selection
MIN_COINS_PER_CYCLE = int(os.getenv('MIN_COINS_PER_CYCLE', '5'))
MAX_COINS_PER_CYCLE = int(os.getenv('MAX_COINS_PER_CYCLE', '8'))
TARGET_DEPLOYMENT = float(os.getenv('TARGET_DEPLOYMENT', '0.80'))  # 80% minimum

# Relaxed thresholds
SCORE_THRESHOLD = float(os.getenv('SCORE_THRESHOLD', '50'))  # Was 65
VOLUME_FILTER_RATIO = float(os.getenv('VOLUME_FILTER_RATIO', '0.70'))  # Was 0.80
FUNDING_RATE_MAX = float(os.getenv('FUNDING_RATE_MAX', '0.0003'))  # 0.03%
ON_CHAIN_MIN = float(os.getenv('ON_CHAIN_MIN', '0.05'))  # 5%
TECHNICAL_BUFFER = float(os.getenv('TECHNICAL_BUFFER', '0.10'))  # 10%

# Risk parameters
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% for new
RISK_PER_REBALANCE = float(os.getenv('RISK_PER_REBALANCE', '0.015'))  # 1.5% for rebalance
REBALANCE_THRESHOLD = float(os.getenv('REBALANCE_THRESHOLD', '0.15'))  # 15% score shift

# Stop loss / Take profit
STOP_LOSS_ATR_MULT = float(os.getenv('STOP_LOSS_ATR_MULT', '1.5'))
TAKE_PROFIT_ATR_MULT = float(os.getenv('TAKE_PROFIT_ATR_MULT', '4.0'))
INITIAL_EQUITY = float(os.getenv('INITIAL_EQUITY', '100000'))

# Leverage parameters (4-7x aggressive)
MIN_LEVERAGE = float(os.getenv('MIN_LEVERAGE', '4.0'))  # Was 3.0
MAX_LEVERAGE = float(os.getenv('MAX_LEVERAGE', '7.0'))  # Was 5.0

# Risk limits (aggressive)
MAX_DEPLOYED = float(os.getenv('MAX_DEPLOYED', '0.90'))  # Was 0.70
PER_ASSET_LIMIT = float(os.getenv('PER_ASSET_LIMIT', '0.20'))  # Was 0.15
DAILY_LOSS_LIMIT = float(os.getenv('DAILY_LOSS_LIMIT', '0.06'))  # Was 0.04

# Force trade mode for paper testing (100+ trades/day)
FORCE_TRADE = os.getenv('FORCE_TRADE', 'false').lower() == 'true'


def calculate_adaptive_leverage(
    sentiment_score: float,
    atr_percent: float,
    regime: str = "normal"
) -> float:
    """
    Calculate adaptive leverage based on conviction, volatility, and market regime.
    
    AGGRESSIVE: Leverage scales from 4x to 7x (was 3x-5x):
    - High conviction (|score| close to 100) + low volatility = higher leverage
    - Low conviction (|score| close to 50) + high volatility = lower leverage
    - Never skip for regime (always trade)
    
    Args:
        sentiment_score: Sentiment score from -100 to +100
        atr_percent: ATR as percentage of price (e.g., 0.5 = 0.5%)
        regime: Market regime ('normal' or 'stress') - stress reduces leverage
    
    Returns:
        Calculated leverage between MIN_LEVERAGE (4x) and MAX_LEVERAGE (7x)
    
    Examples:
        | Score | ATR % | Conviction | Vol Factor | Leverage |
        |-------|-------|------------|------------|----------|
        | 50    | 1.5%  | 0.0        | 0.0        | 4.0x     |
        | 70    | 0.8%  | 0.40       | 0.70       | 5.2x     |
        | 90    | 0.5%  | 0.80       | 1.00       | 6.4x     |
        | 100   | 0.3%  | 1.0        | 1.00       | 7.0x     |
    """
    # In stress, use minimum but don't skip (aggressive mode)
    if regime == "stress":
        return MIN_LEVERAGE
    
    # Conviction factor: 0.0 to 1.0 (|score| from 50 to 100) - lowered from 65
    conviction = min(1.0, max(0.0, (abs(sentiment_score) - 50) / 50))
    
    # Volatility factor: 0.0 to 1.0 (lower ATR% = higher factor)
    # ATR% of 1.5% = high vol (factor 0), ATR% of 0.5% = low vol (factor 1)
    vol_factor = max(0.0, min(1.0, (1.5 - atr_percent) / 1.0))
    
    # Combined factor (weighted average: 60% conviction, 40% volatility)
    combined = (conviction * 0.6) + (vol_factor * 0.4)
    
    # Scale to leverage range (4x to 7x)
    leverage = MIN_LEVERAGE + (combined * (MAX_LEVERAGE - MIN_LEVERAGE))
    return round(leverage, 1)


def detect_market_regime(atr_percent: float, recent_drawdown: float = 0.0) -> str:
    """
    Detect current market regime for leverage adjustment.
    
    Args:
        atr_percent: Current ATR as percentage of price
        recent_drawdown: Recent portfolio drawdown (0.0 to 1.0)
    
    Returns:
        'stress' if high volatility or drawdown, otherwise 'normal'
    """
    # High volatility regime (ATR > 3% of price)
    if atr_percent > 3.0:
        return "stress"
    
    # High drawdown regime (> 10% drawdown)
    if recent_drawdown > 0.10:
        return "stress"
    
    return "normal"


@dataclass
class CoinAnalysis:
    """Complete analysis for a single coin"""
    coin: str
    sentiment: float
    narrative: float
    score: float
    price: float
    volume_1h: float
    volume_24h_avg: float
    atr_1h: float
    filter_score_pass: bool
    filter_volume_pass: bool
    
    # Previous score for rebalance detection
    prev_score: Optional[float] = None
    
    @property
    def passes_all_filters(self) -> bool:
        return self.filter_score_pass and self.filter_volume_pass
    
    @property
    def volume_ratio(self) -> float:
        if self.volume_24h_avg == 0:
            return 0
        return self.volume_1h / self.volume_24h_avg
    
    @property
    def score_shift(self) -> float:
        """Calculate score shift from previous cycle"""
        if self.prev_score is None:
            return 0
        if self.prev_score == 0:
            return abs(self.score)
        return abs(self.score - self.prev_score) / abs(self.prev_score)
    
    @property
    def needs_rebalance(self) -> bool:
        """Check if score shifted more than threshold"""
        return self.score_shift >= REBALANCE_THRESHOLD


@dataclass
class CoinTrade:
    """Individual coin trade within a decision"""
    coin: str
    side: str  # 'long' or 'short'
    score: float
    position_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    leverage: float
    is_rebalance: bool = False  # True if this is a rebalance trade


@dataclass
class TradingDecision:
    """The final trading decision for this cycle - supports 5-8 coins"""
    timestamp: datetime
    batch_id: str
    
    # Decision outcome
    decision: str  # 'trade', 'flat', 'filtered', 'force_trade'
    filter_reason: Optional[str] = None
    
    # AGGRESSIVE: Multiple coin trades (5-8 per cycle)
    trades: List[CoinTrade] = field(default_factory=list)
    
    # Legacy single-coin fields for backwards compat
    selected_coin: Optional[str] = None
    selected_score: Optional[float] = None
    side: Optional[str] = None
    position_size: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    atr_value: Optional[float] = None
    
    # Leverage (4-7x aggressive)
    leverage: float = MIN_LEVERAGE
    market_regime: str = "normal"
    
    # Dynamic score threshold (based on BTC volatility)
    volatility_regime: str = "normal"  # 'high_vol', 'normal', 'low_vol'
    score_threshold: float = 50.0  # Lowered from 67
    btc_atr_percent: float = 0.0
    
    # Portfolio state
    equity: float = INITIAL_EQUITY
    risk_amount: Optional[float] = None
    
    # Deployment tracking
    deployment_percent: float = 0.0  # Current % deployed
    target_deployment: float = TARGET_DEPLOYMENT
    
    # Velocity tracking
    trades_this_cycle: int = 0
    rebalance_count: int = 0
    force_traded: bool = False
    
    # All coin analyses
    all_analyses: Dict[str, CoinAnalysis] = field(default_factory=dict)
    
    # Grok response
    grok_raw_response: str = ""
    request_hash: str = ""
    grok_success: bool = False


class StrategyEngine:
    """
    Main strategy orchestrator.
    
    Runs every hour to:
    1. Fetch sentiment from Grok (batch)
    2. Fetch market data from Binance
    3. Apply filters
    4. Make trading decision
    5. Log everything to database
    """
    
    def __init__(self):
        self.market_data = get_market_data_client()
    
    async def get_current_equity(self) -> float:
        """Get current portfolio equity"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if snapshot:
                return float(snapshot.total_equity)
            
            return INITIAL_EQUITY
    
    async def get_open_position(self) -> Optional[Position]:
        """Get current open position if any"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Position)
                .where(Position.status == 'open')
                .order_by(Position.opened_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
    
    async def run_cycle(self) -> TradingDecision:
        """
        Execute one complete trading cycle.
        
        AGGRESSIVE MODE:
        - Select top 5-8 coins by |Score|
        - Fallback to add more if deployment < 80%
        - Rebalance if score shift > 15%
        - Force trade if FORCE_TRADE env is set
        
        Returns:
            TradingDecision with all details
        """
        import random
        
        timestamp = datetime.utcnow()
        batch_id = uuid4().hex[:16]
        
        logger.info(f"Starting AGGRESSIVE trading cycle {batch_id}")
        
        # Step 1: Fetch sentiment from Grok
        sentiment_result = await fetch_all_sentiments()
        
        if not sentiment_result.success:
            logger.error(f"Grok API failed: {sentiment_result.error_message}")
            
            # FORCE_TRADE: Generate random trades even if Grok fails
            if FORCE_TRADE:
                logger.warning("FORCE_TRADE enabled - generating synthetic trades")
                return await self._generate_force_trades(timestamp, batch_id)
            
            decision = TradingDecision(
                timestamp=timestamp,
                batch_id=batch_id,
                decision='flat',
                filter_reason=f"api_error: {sentiment_result.error_message}",
                grok_success=False
            )
            await self._log_decision(decision)
            return decision
        
        # Step 2: Fetch market data for all coins
        market_data = await self.market_data.get_all_market_data(TOP_COINS)
        
        # Step 2.5: Determine volatility regime based on BTC ATR
        btc_data = market_data.get('BTC')
        if btc_data and btc_data.price > 0:
            btc_atr_percent = (btc_data.atr_1h / btc_data.price) * 100
        else:
            btc_atr_percent = 1.0  # Default to normal if no data
        
        vol_regime, dynamic_threshold = determine_volatility_regime(btc_atr_percent)
        regime_info = get_current_regime_info()
        
        # AGGRESSIVE: Apply -5 in low vol for more opportunities
        if vol_regime == "low_vol":
            dynamic_threshold = max(45, dynamic_threshold - 5)
        
        logger.info(
            f"AGGRESSIVE Regime: {regime_info['regime_display']} | "
            f"BTC ATR: {btc_atr_percent:.2f}% | "
            f"Score Threshold: {dynamic_threshold}"
        )
        
        # Step 3: Combine and analyze
        analyses: Dict[str, CoinAnalysis] = {}
        
        for coin in TOP_COINS:
            sentiment_data = sentiment_result.sentiments.get(coin)
            md = market_data.get(coin)
            
            if sentiment_data and md:
                # Relaxed filters for aggressive mode
                score_pass = check_score_filter(sentiment_data.score, dynamic_threshold)
                volume_pass = check_volume_filter(md.volume_1h, md.volume_24h_avg, VOLUME_FILTER_RATIO)
                
                # Get previous score for rebalance detection
                prev_score = self._get_prev_score(coin)
                
                analyses[coin] = CoinAnalysis(
                    coin=coin,
                    sentiment=sentiment_data.sentiment,
                    narrative=sentiment_data.narrative,
                    score=sentiment_data.score,
                    price=md.price,
                    volume_1h=md.volume_1h,
                    volume_24h_avg=md.volume_24h_avg,
                    atr_1h=md.atr_1h,
                    filter_score_pass=score_pass,
                    filter_volume_pass=volume_pass,
                    prev_score=prev_score
                )
                
                # Store for next cycle
                self._store_score(coin, sentiment_data.score)
                
                logger.debug(
                    f"{coin}: score={sentiment_data.score:.1f}, "
                    f"score_pass={score_pass}, volume_pass={volume_pass}"
                )
        
        # Step 4: AGGRESSIVE - Select top 5-8 coins
        candidates = [a for a in analyses.values() if a.passes_all_filters]
        
        # Sort by absolute score descending
        candidates.sort(key=lambda a: abs(a.score), reverse=True)
        
        # Get current equity and deployment
        equity = await self.get_current_equity()
        current_positions = await self.get_open_positions_value()
        current_deployment = current_positions / equity if equity > 0 else 0
        
        # If not enough candidates, relax filters for deployment target
        if len(candidates) < MIN_COINS_PER_CYCLE and current_deployment < TARGET_DEPLOYMENT:
            logger.info(f"Only {len(candidates)} candidates, relaxing filters for 80%+ deployment")
            # Add coins that only fail volume (keep score filter)
            extras = [
                a for a in analyses.values() 
                if a.filter_score_pass and not a.filter_volume_pass
            ]
            extras.sort(key=lambda a: abs(a.score), reverse=True)
            candidates.extend(extras[:MAX_COINS_PER_CYCLE - len(candidates)])
        
        # FORCE_TRADE: If still no candidates, pick random coins
        if not candidates and FORCE_TRADE:
            logger.warning("FORCE_TRADE: No candidates, selecting top by raw score")
            candidates = sorted(analyses.values(), key=lambda a: abs(a.score), reverse=True)[:MIN_COINS_PER_CYCLE]
        
        if not candidates:
            filter_reason = f"no_candidates: 0 coins passed filters (threshold={dynamic_threshold})"
            logger.info(filter_reason)
            
            decision = TradingDecision(
                timestamp=timestamp,
                batch_id=batch_id,
                decision='filtered',
                filter_reason=filter_reason,
                volatility_regime=vol_regime,
                score_threshold=dynamic_threshold,
                btc_atr_percent=btc_atr_percent,
                deployment_percent=current_deployment,
                all_analyses=analyses,
                grok_raw_response=sentiment_result.raw_response,
                request_hash=sentiment_result.response_hash,
                grok_success=True,
                equity=equity
            )
            await self._log_decision(decision)
            return decision
        
        # Take top 5-8
        selected = candidates[:MAX_COINS_PER_CYCLE]
        logger.info(f"Selected {len(selected)} coins for trading")
        
        # Step 5: Calculate position sizing for each coin
        trades: List[CoinTrade] = []
        rebalance_count = 0
        
        for analysis in selected:
            # Check if this is a rebalance
            is_rebalance = analysis.needs_rebalance
            if is_rebalance:
                rebalance_count += 1
                risk = equity * RISK_PER_REBALANCE
            else:
                risk = equity * RISK_PER_TRADE
            
            # Calculate leverage for this coin
            atr_pct = (analysis.atr_1h / analysis.price) * 100 if analysis.price > 0 else 1.0
            market_regime = detect_market_regime(atr_pct)
            leverage = calculate_adaptive_leverage(analysis.score, atr_pct, market_regime)
            
            # Position size
            stop_distance = analysis.atr_1h * STOP_LOSS_ATR_MULT
            position_size = (risk * leverage) / stop_distance if stop_distance > 0 else 0
            
            # Direction and SL/TP
            side = 'long' if analysis.score > 0 else 'short'
            if side == 'long':
                stop_loss = analysis.price - (analysis.atr_1h * STOP_LOSS_ATR_MULT)
                take_profit = analysis.price + (analysis.atr_1h * TAKE_PROFIT_ATR_MULT)
            else:
                stop_loss = analysis.price + (analysis.atr_1h * STOP_LOSS_ATR_MULT)
                take_profit = analysis.price - (analysis.atr_1h * TAKE_PROFIT_ATR_MULT)
            
            trade = CoinTrade(
                coin=analysis.coin,
                side=side,
                score=analysis.score,
                position_size=position_size,
                entry_price=analysis.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                is_rebalance=is_rebalance
            )
            trades.append(trade)
            
            logger.info(
                f"  {trade.side.upper()} {trade.coin}: size={trade.position_size:.4f}, "
                f"lev={trade.leverage}x, rebal={trade.is_rebalance}"
            )
        
        # Calculate new deployment
        new_positions_value = sum(t.position_size * t.entry_price for t in trades)
        new_deployment = (current_positions + new_positions_value) / equity if equity > 0 else 0
        
        # Build decision with all trades
        best = selected[0]  # For backwards compat
        decision = TradingDecision(
            timestamp=timestamp,
            batch_id=batch_id,
            decision='trade',
            trades=trades,
            # Legacy fields
            selected_coin=best.coin,
            selected_score=best.score,
            side='long' if best.score > 0 else 'short',
            position_size=trades[0].position_size if trades else 0,
            entry_price=best.price,
            stop_loss=trades[0].stop_loss if trades else 0,
            take_profit=trades[0].take_profit if trades else 0,
            atr_value=best.atr_1h,
            leverage=trades[0].leverage if trades else MIN_LEVERAGE,
            market_regime=market_regime,
            volatility_regime=vol_regime,
            score_threshold=dynamic_threshold,
            btc_atr_percent=btc_atr_percent,
            equity=equity,
            risk_amount=equity * RISK_PER_TRADE,
            deployment_percent=new_deployment,
            trades_this_cycle=len(trades),
            rebalance_count=rebalance_count,
            force_traded=FORCE_TRADE and len(candidates) == 0,
            all_analyses=analyses,
            grok_raw_response=sentiment_result.raw_response,
            request_hash=sentiment_result.response_hash,
            grok_success=True
        )
        
        await self._log_decision(decision)
        
        logger.info(
            f"AGGRESSIVE Decision: {len(trades)} trades | "
            f"Deployment: {new_deployment*100:.1f}% | "
            f"Rebalances: {rebalance_count}"
        )
        
        return decision
    
    async def _generate_force_trades(self, timestamp, batch_id) -> TradingDecision:
        """Generate random trades for FORCE_TRADE mode testing"""
        import random
        
        equity = await self.get_current_equity()
        market_data = await self.market_data.get_all_market_data(TOP_COINS)
        
        # Select 5-8 random coins
        coins = random.sample(TOP_COINS, min(random.randint(5, 8), len(TOP_COINS)))
        trades = []
        
        for coin in coins:
            md = market_data.get(coin)
            if not md or md.price == 0:
                continue
            
            # Random score and direction
            score = random.uniform(50, 90) * random.choice([1, -1])
            side = 'long' if score > 0 else 'short'
            leverage = random.uniform(MIN_LEVERAGE, MAX_LEVERAGE)
            
            risk = equity * RISK_PER_TRADE
            stop_distance = md.atr_1h * STOP_LOSS_ATR_MULT if md.atr_1h > 0 else md.price * 0.02
            position_size = (risk * leverage) / stop_distance if stop_distance > 0 else 0
            
            if side == 'long':
                stop_loss = md.price - stop_distance
                take_profit = md.price + (stop_distance * 2.5)
            else:
                stop_loss = md.price + stop_distance
                take_profit = md.price - (stop_distance * 2.5)
            
            trades.append(CoinTrade(
                coin=coin,
                side=side,
                score=score,
                position_size=position_size,
                entry_price=md.price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=round(leverage, 1),
                is_rebalance=False
            ))
        
        decision = TradingDecision(
            timestamp=timestamp,
            batch_id=batch_id,
            decision='force_trade',
            trades=trades,
            selected_coin=trades[0].coin if trades else None,
            selected_score=trades[0].score if trades else None,
            equity=equity,
            trades_this_cycle=len(trades),
            force_traded=True,
            grok_success=False
        )
        
        await self._log_decision(decision)
        logger.warning(f"FORCE_TRADE: Generated {len(trades)} synthetic trades")
        
        return decision
    
    def _get_prev_score(self, coin: str) -> Optional[float]:
        """Get previous cycle score for rebalance detection"""
        if not hasattr(self, '_prev_scores'):
            self._prev_scores = {}
        return self._prev_scores.get(coin)
    
    def _store_score(self, coin: str, score: float):
        """Store score for next cycle comparison"""
        if not hasattr(self, '_prev_scores'):
            self._prev_scores = {}
        self._prev_scores[coin] = score
    
    async def get_open_positions_value(self) -> float:
        """Get total value of open positions"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Position).where(Position.status == 'open')
            )
            positions = result.scalars().all()
            return sum(
                float(p.quantity) * float(p.current_price or p.entry_price)
                for p in positions
            )
    
    async def _log_decision(self, decision: TradingDecision):
        """Log the decision and all signals to database"""
        async with AsyncSessionLocal() as session:
            # Log individual signals for each coin
            for coin, analysis in decision.all_analyses.items():
                signal = Signal(
                    coin=coin,
                    sentiment_score=Decimal(str(analysis.sentiment)),
                    narrative_strength=Decimal(str(analysis.narrative)),
                    combined_score=Decimal(str(analysis.score)),
                    confidence=Decimal('0.5'),  # Not used in this strategy
                    recommended_action='long' if analysis.score > 0 else 'short' if analysis.score < 0 else 'hold',
                    raw_response=decision.grok_raw_response if coin == decision.selected_coin else None,
                    response_hash=decision.request_hash,
                    filter_score_pass=analysis.filter_score_pass,
                    filter_volume_pass=analysis.filter_volume_pass,
                    volume_1h=Decimal(str(analysis.volume_1h)) if analysis.volume_1h else None,
                    volume_24h_avg=Decimal(str(analysis.volume_24h_avg)) if analysis.volume_24h_avg else None,
                    atr_1h=Decimal(str(analysis.atr_1h)) if analysis.atr_1h else None,
                    price_at_signal=Decimal(str(analysis.price)) if analysis.price else None,
                    batch_id=decision.batch_id,
                    executed=(coin == decision.selected_coin and decision.decision in ['long', 'short'])
                )
                session.add(signal)
            
            await session.commit()
            
        logger.info(f"Logged {len(decision.all_analyses)} signals to database")
    
    async def close(self):
        """Cleanup resources"""
        await self.market_data.close()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_strategy_engine: Optional[StrategyEngine] = None


def get_strategy_engine() -> StrategyEngine:
    """Get or create the global strategy engine"""
    global _strategy_engine
    if _strategy_engine is None:
        _strategy_engine = StrategyEngine()
    return _strategy_engine


async def run_trading_cycle() -> TradingDecision:
    """
    Convenience function to run a complete trading cycle.
    
    Returns:
        TradingDecision with all details
    """
    engine = get_strategy_engine()
    return await engine.run_cycle()


async def main():
    """Entry point for strategy engine service"""
    
    engine = StrategyEngine()
    
    logger.info(f"AGGRESSIVE Strategy Engine started. Running every {CYCLE_MINUTES} minutes...")
    logger.info(f"Config: coins={MIN_COINS_PER_CYCLE}-{MAX_COINS_PER_CYCLE}, "
                f"score>={SCORE_THRESHOLD}, vol>={VOLUME_FILTER_RATIO}, "
                f"leverage={MIN_LEVERAGE}-{MAX_LEVERAGE}x")
    logger.info(f"FORCE_TRADE={FORCE_TRADE}")
    
    # Run initial cycle
    await engine.run_cycle()
    
    # Run every CYCLE_MINUTES (15 min default)
    while True:
        wait_seconds = CYCLE_MINUTES * 60
        logger.info(f"Next cycle in {wait_seconds} seconds ({CYCLE_MINUTES} minutes)")
        
        await asyncio.sleep(wait_seconds)
        
        try:
            await engine.run_cycle()
        except Exception as e:
            logger.error(f"Cycle error: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
