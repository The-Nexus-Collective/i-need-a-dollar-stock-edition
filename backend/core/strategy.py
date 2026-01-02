"""
Strategy Engine - Main trading strategy orchestrator

Implements the #1 proven strategy:
1. Fetch batch sentiment from Grok
2. Apply score threshold filter (|Score| >= 65)
3. Apply volume filter (1h vol >= 80% of 24h avg)
4. Select coin with highest |Score| that passes all filters
5. Calculate position size: 2% equity / (1.5 × ATR)
6. Set stop loss (1.5 × ATR) and take profit (4 × ATR)
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
)
from models import AsyncSessionLocal, Signal, Position, PortfolioSnapshot

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Strategy parameters (can be overridden via environment)
SCORE_THRESHOLD = float(os.getenv('SCORE_THRESHOLD', '65'))
VOLUME_FILTER_RATIO = float(os.getenv('VOLUME_FILTER_RATIO', '0.80'))
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2%
STOP_LOSS_ATR_MULT = float(os.getenv('STOP_LOSS_ATR_MULT', '1.5'))
TAKE_PROFIT_ATR_MULT = float(os.getenv('TAKE_PROFIT_ATR_MULT', '4.0'))
INITIAL_EQUITY = float(os.getenv('INITIAL_EQUITY', '10000'))


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
    
    @property
    def passes_all_filters(self) -> bool:
        return self.filter_score_pass and self.filter_volume_pass
    
    @property
    def volume_ratio(self) -> float:
        if self.volume_24h_avg == 0:
            return 0
        return self.volume_1h / self.volume_24h_avg


@dataclass
class TradingDecision:
    """The final trading decision for this cycle"""
    timestamp: datetime
    batch_id: str
    
    # Decision outcome
    decision: str  # 'long', 'short', 'flat', 'filtered'
    filter_reason: Optional[str] = None
    
    # Selected coin (if trading)
    selected_coin: Optional[str] = None
    selected_score: Optional[float] = None
    
    # Position details (if trading)
    side: Optional[str] = None  # 'long' or 'short'
    position_size: Optional[float] = None
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    atr_value: Optional[float] = None
    
    # Portfolio state
    equity: float = INITIAL_EQUITY
    risk_amount: Optional[float] = None
    
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
        
        Returns:
            TradingDecision with all details
        """
        timestamp = datetime.utcnow()
        batch_id = uuid4().hex[:16]
        
        logger.info(f"Starting trading cycle {batch_id}")
        
        # Step 1: Fetch sentiment from Grok
        sentiment_result = await fetch_all_sentiments()
        
        if not sentiment_result.success:
            logger.error(f"Grok API failed: {sentiment_result.error_message}")
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
        
        # Step 3: Combine and analyze
        analyses: Dict[str, CoinAnalysis] = {}
        
        for coin in TOP_COINS:
            sentiment_data = sentiment_result.sentiments.get(coin)
            md = market_data.get(coin)
            
            if sentiment_data and md:
                # Check filters
                score_pass = check_score_filter(sentiment_data.score, SCORE_THRESHOLD)
                volume_pass = check_volume_filter(md.volume_1h, md.volume_24h_avg, VOLUME_FILTER_RATIO)
                
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
                    filter_volume_pass=volume_pass
                )
                
                logger.info(
                    f"{coin}: score={sentiment_data.score:.1f}, "
                    f"score_pass={score_pass}, volume_pass={volume_pass}"
                )
        
        # Step 4: Select best coin that passes all filters
        candidates = [a for a in analyses.values() if a.passes_all_filters]
        
        if not candidates:
            # Determine filter reason
            all_analyses = list(analyses.values())
            score_fails = sum(1 for a in all_analyses if not a.filter_score_pass)
            volume_fails = sum(1 for a in all_analyses if a.filter_score_pass and not a.filter_volume_pass)
            
            if score_fails == len(all_analyses):
                filter_reason = f"score_filter: no coin has |Score| >= {SCORE_THRESHOLD}"
            elif volume_fails > 0:
                filter_reason = f"volume_filter: {volume_fails} coins failed volume check"
            else:
                filter_reason = "no_candidates"
            
            logger.info(f"No valid candidates. Reason: {filter_reason}")
            
            decision = TradingDecision(
                timestamp=timestamp,
                batch_id=batch_id,
                decision='filtered',
                filter_reason=filter_reason,
                all_analyses=analyses,
                grok_raw_response=sentiment_result.raw_response,
                request_hash=sentiment_result.response_hash,
                grok_success=True,
                equity=await self.get_current_equity()
            )
            await self._log_decision(decision)
            return decision
        
        # Select coin with highest absolute score
        best = max(candidates, key=lambda a: abs(a.score))
        
        logger.info(f"Selected {best.coin} with score {best.score:.1f}")
        
        # Step 5: Calculate position sizing
        equity = await self.get_current_equity()
        risk_amount = equity * RISK_PER_TRADE
        
        # Position size = risk_amount / (stop_distance in USDT)
        stop_distance = best.atr_1h * STOP_LOSS_ATR_MULT
        position_size = risk_amount / stop_distance
        
        # Determine direction
        side = 'long' if best.score > 0 else 'short'
        
        # Calculate stop loss and take profit
        if side == 'long':
            stop_loss = best.price - (best.atr_1h * STOP_LOSS_ATR_MULT)
            take_profit = best.price + (best.atr_1h * TAKE_PROFIT_ATR_MULT)
        else:
            stop_loss = best.price + (best.atr_1h * STOP_LOSS_ATR_MULT)
            take_profit = best.price - (best.atr_1h * TAKE_PROFIT_ATR_MULT)
        
        decision = TradingDecision(
            timestamp=timestamp,
            batch_id=batch_id,
            decision=side,
            selected_coin=best.coin,
            selected_score=best.score,
            side=side,
            position_size=position_size,
            entry_price=best.price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            atr_value=best.atr_1h,
            equity=equity,
            risk_amount=risk_amount,
            all_analyses=analyses,
            grok_raw_response=sentiment_result.raw_response,
            request_hash=sentiment_result.response_hash,
            grok_success=True
        )
        
        await self._log_decision(decision)
        
        logger.info(
            f"Decision: {side.upper()} {best.coin} | "
            f"Size: {position_size:.4f} | Entry: ${best.price:.2f} | "
            f"SL: ${stop_loss:.2f} | TP: ${take_profit:.2f}"
        )
        
        return decision
    
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
    import schedule
    import time
    
    engine = StrategyEngine()
    
    logger.info("Strategy Engine started. Running hourly cycles...")
    
    # Run initial cycle
    await engine.run_cycle()
    
    # Schedule hourly runs
    while True:
        # Wait until next hour
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0)
        if next_hour <= now:
            next_hour = next_hour.replace(hour=next_hour.hour + 1)
        
        wait_seconds = (next_hour - now).total_seconds()
        logger.info(f"Next cycle in {wait_seconds:.0f} seconds at {next_hour}")
        
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
