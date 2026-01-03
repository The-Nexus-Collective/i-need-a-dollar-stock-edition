"""
Strategy Ensemble Agent - Multi-strategy trading with meta-learning.

Contains 6 sub-strategies that are dynamically weighted:
1. Momentum - Trend following
2. Mean Reversion - Oversold/overbought
3. Hype Following - X/social momentum
4. Contrarian - Against the crowd
5. Volatility Expansion - Breakout trades
6. Narrative Driven - Thematic plays

A meta-learner adjusts weights based on market regime and performance.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text

from .base import GrokAgent, AgentContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class TradeProposal:
    """A proposed trade from a strategy."""
    coin: str
    side: str  # 'long' or 'short'
    
    # Sizing
    confidence: float  # 0-100
    size_percent: float  # % of portfolio
    leverage: float  # 3-6x
    
    # Risk management
    stop_loss_percent: float  # % below/above entry
    take_profit_percent: float  # % above/below entry
    
    # Source
    strategy: str
    reasoning: str
    
    # Priority
    priority_score: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "side": self.side,
            "confidence": self.confidence,
            "size_percent": self.size_percent,
            "leverage": self.leverage,
            "stop_loss_percent": self.stop_loss_percent,
            "take_profit_percent": self.take_profit_percent,
            "strategy": self.strategy,
            "reasoning": self.reasoning,
            "priority_score": self.priority_score,
        }


class BaseStrategy(ABC):
    """Base class for trading strategies."""
    
    name: str = "base"
    
    # Regime affinity (how well strategy performs in each regime)
    affinity = {
        "low_vol": 50,
        "normal": 50,
        "high_vol": 50,
        "euphoria": 50,
        "panic": 50,
    }
    
    @abstractmethod
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        """Evaluate coin and optionally propose a trade."""
        pass


class MomentumStrategy(BaseStrategy):
    """
    Momentum Strategy - Ride the trend.
    
    Goes long on strong uptrends, short on strong downtrends.
    Works best in low-to-normal volatility regimes.
    """
    
    name = "momentum"
    affinity = {"low_vol": 70, "normal": 65, "high_vol": 40, "euphoria": 50, "panic": 30}
    
    # Thresholds
    SCORE_THRESHOLD = 50
    MIN_NARRATIVE = 40
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        score = sentiment.get("combined_score", 0)
        narrative = sentiment.get("narrative_strength", 0)
        
        # Need strong sentiment and narrative
        if abs(score) < self.SCORE_THRESHOLD or narrative < self.MIN_NARRATIVE:
            return None
        
        side = "long" if score > 0 else "short"
        
        # Size based on conviction
        confidence = min(90, 50 + abs(score) * 0.4)
        size = min(12, 4 + (confidence - 50) * 0.16)  # 4-12%
        
        # Leverage based on volatility
        regime = context.market_regime
        if regime in ["low_vol", "normal"]:
            leverage = 4 + (confidence - 50) * 0.04  # 4-6x
        else:
            leverage = 3  # Conservative in high vol
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=confidence,
            size_percent=size,
            leverage=round(leverage, 1),
            stop_loss_percent=2.5,
            take_profit_percent=7.5,
            strategy=self.name,
            reasoning=f"Strong momentum: score={score:.0f}, narrative={narrative:.0f}",
        )


class MeanReversionStrategy(BaseStrategy):
    """
    Mean Reversion Strategy - Fade extremes.
    
    Goes against extreme moves, expecting reversal.
    Works best in normal volatility, ranging markets.
    """
    
    name = "mean_reversion"
    affinity = {"low_vol": 50, "normal": 70, "high_vol": 40, "euphoria": 30, "panic": 60}
    
    EXTREME_THRESHOLD = 75
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        score = sentiment.get("combined_score", 0)
        
        # Look for extreme readings to fade
        if abs(score) < self.EXTREME_THRESHOLD:
            return None
        
        # Go opposite direction
        side = "short" if score > 0 else "long"
        
        # More confident fading bigger extremes
        confidence = 40 + (abs(score) - 75) * 1.0  # 40-65
        size = min(8, 3 + (abs(score) - 75) * 0.2)  # 3-8%
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=confidence,
            size_percent=size,
            leverage=3.5,
            stop_loss_percent=3.0,
            take_profit_percent=4.5,
            strategy=self.name,
            reasoning=f"Fading extreme: score={score:.0f} (expecting reversion)",
        )


class HypeFollowingStrategy(BaseStrategy):
    """
    Hype Following Strategy - Ride social momentum.
    
    Trades coins with high X engagement and narrative.
    Works in any regime where hype drives price.
    """
    
    name = "hype_following"
    affinity = {"low_vol": 60, "normal": 65, "high_vol": 55, "euphoria": 80, "panic": 30}
    
    MIN_NARRATIVE = 70
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        narrative = sentiment.get("narrative_strength", 0)
        score = sentiment.get("sentiment_score", 0)
        
        # Need strong narrative
        if narrative < self.MIN_NARRATIVE:
            return None
        
        # Check if coin is in X discoveries
        x_coins = [d.get("coin") for d in context.x_discoveries]
        is_trending = coin in x_coins
        
        if not is_trending and narrative < 80:
            return None
        
        side = "long" if score >= 0 else "short"
        
        # Higher confidence for trending coins
        confidence = 55 + (narrative - 70) * 0.5
        if is_trending:
            confidence += 10
        
        size = min(10, 5 + (narrative - 70) * 0.17)  # 5-10%
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=min(85, confidence),
            size_percent=size,
            leverage=4.5,
            stop_loss_percent=3.5,
            take_profit_percent=10.0,
            strategy=self.name,
            reasoning=f"High hype: narrative={narrative:.0f}, trending={is_trending}",
        )


class ContrarianStrategy(BaseStrategy):
    """
    Contrarian Strategy - Go against the crowd.
    
    Takes opposite positions when sentiment is extreme.
    Works best in high volatility and panic conditions.
    """
    
    name = "contrarian"
    affinity = {"low_vol": 35, "normal": 45, "high_vol": 70, "euphoria": 65, "panic": 80}
    
    EXTREME_THRESHOLD = 70
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        score = sentiment.get("combined_score", 0)
        regime = context.market_regime
        
        # Only in extreme regimes
        if regime not in ["high_vol", "euphoria", "panic"]:
            return None
        
        # Need extreme sentiment to fade
        if abs(score) < self.EXTREME_THRESHOLD:
            return None
        
        # Go opposite
        side = "short" if score > 0 else "long"
        
        # Higher confidence in panic (often oversold)
        base_conf = 60 if regime == "panic" else 50
        confidence = base_conf + (abs(score) - 70) * 0.5
        
        size = min(8, 4 + (abs(score) - 70) * 0.13)
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=min(75, confidence),
            size_percent=size,
            leverage=3.0,  # Conservative
            stop_loss_percent=4.0,
            take_profit_percent=6.0,
            strategy=self.name,
            reasoning=f"Contrarian in {regime}: fading {score:.0f}",
        )


class VolatilityExpansionStrategy(BaseStrategy):
    """
    Volatility Expansion Strategy - Catch breakouts.
    
    Enters when volatility is expanding from low levels.
    Rides the initial move direction.
    """
    
    name = "volatility_expansion"
    affinity = {"low_vol": 80, "normal": 50, "high_vol": 35, "euphoria": 45, "panic": 40}
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        regime = context.market_regime
        
        # Only in low vol transitioning to normal
        if regime not in ["low_vol"]:
            return None
        
        score = sentiment.get("combined_score", 0)
        
        # Need some directional bias
        if abs(score) < 40:
            return None
        
        side = "long" if score > 0 else "short"
        
        confidence = 55 + abs(score) * 0.2
        size = min(10, 5 + abs(score) * 0.05)
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=min(75, confidence),
            size_percent=size,
            leverage=5.0,
            stop_loss_percent=2.0,
            take_profit_percent=8.0,
            strategy=self.name,
            reasoning=f"Volatility expansion: low vol + direction ({score:.0f})",
        )


class NarrativeDrivenStrategy(BaseStrategy):
    """
    Narrative Driven Strategy - Trade themes.
    
    Identifies and trades dominant market narratives.
    Works in any regime with clear themes.
    """
    
    name = "narrative_driven"
    affinity = {"low_vol": 55, "normal": 60, "high_vol": 50, "euphoria": 70, "panic": 40}
    
    # Narrative mappings
    BULLISH_NARRATIVES = ["etf", "adoption", "institutional", "halving", "upgrade"]
    BEARISH_NARRATIVES = ["hack", "regulation", "ban", "sec", "crash"]
    
    def evaluate(
        self,
        coin: str,
        sentiment: Dict,
        context: AgentContext,
    ) -> Optional[TradeProposal]:
        driver = sentiment.get("key_driver", "").lower()
        narrative = sentiment.get("current_narrative", "").lower()
        
        if not driver and not narrative:
            return None
        
        # Check for bullish/bearish narratives
        is_bullish = any(n in driver or n in narrative for n in self.BULLISH_NARRATIVES)
        is_bearish = any(n in driver or n in narrative for n in self.BEARISH_NARRATIVES)
        
        if not is_bullish and not is_bearish:
            return None
        
        side = "long" if is_bullish else "short"
        
        narrative_strength = sentiment.get("narrative_strength", 50)
        confidence = 50 + (narrative_strength - 50) * 0.5
        size = min(8, 4 + (narrative_strength - 50) * 0.08)
        
        return TradeProposal(
            coin=coin,
            side=side,
            confidence=min(75, confidence),
            size_percent=size,
            leverage=4.0,
            stop_loss_percent=3.0,
            take_profit_percent=7.5,
            strategy=self.name,
            reasoning=f"Narrative: {driver or narrative} ({'bullish' if is_bullish else 'bearish'})",
        )


@dataclass
class EnsembleOutput:
    """Output from Strategy Ensemble."""
    proposals: List[TradeProposal]
    strategy_weights: Dict[str, float]
    selected_trades: List[TradeProposal]
    reasoning: str
    
    def to_dict(self) -> Dict:
        return {
            "proposals": [p.to_dict() for p in self.proposals],
            "strategy_weights": self.strategy_weights,
            "selected_trades": [t.to_dict() for t in self.selected_trades],
            "reasoning": self.reasoning,
        }


class StrategyEnsemble(GrokAgent):
    """
    Strategy Ensemble - Combines multiple strategies with meta-learning.
    
    Flow:
    1. Each strategy evaluates all coins
    2. Meta-learner weights strategies based on regime
    3. Proposals are scored and ranked
    4. Top trades are selected within risk limits
    """
    
    # Risk limits
    MAX_TRADES_PER_CYCLE = 8
    MAX_TOTAL_EXPOSURE = 0.90  # 90% max deployment
    MAX_PER_COIN = 0.12  # 12% per coin
    MAX_NEW_COINS = 0.08  # 8% per new coin
    NEW_COIN_BUCKET = 0.35  # 35% max in new coins
    
    def __init__(self):
        super().__init__("strategy_ensemble")
        
        # Initialize strategies
        self.strategies: List[BaseStrategy] = [
            MomentumStrategy(),
            MeanReversionStrategy(),
            HypeFollowingStrategy(),
            ContrarianStrategy(),
            VolatilityExpansionStrategy(),
            NarrativeDrivenStrategy(),
        ]
        
        # Current weights (updated by meta-learner)
        self.weights: Dict[str, float] = {
            "momentum": 0.20,
            "mean_reversion": 0.15,
            "hype_following": 0.20,
            "contrarian": 0.15,
            "volatility_expansion": 0.15,
            "narrative_driven": 0.15,
        }
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Prepare for strategy evaluation."""
        sentiments = context.sentiments
        regime = context.market_regime
        
        if not sentiments:
            return AgentOutput(
                success=False,
                reasoning="No sentiments available",
                decision="skip",
            )
        
        # Update weights based on regime
        self._update_weights_for_regime(regime)
        
        reasoning = f"Evaluating {len(sentiments)} coins with {len(self.strategies)} strategies. Regime: {regime}"
        
        return AgentOutput(
            success=True,
            data={"regime": regime, "coin_count": len(sentiments)},
            reasoning=reasoning,
            decision="evaluate_strategies",
            confidence=90,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Run all strategies and select best trades."""
        proposals: List[TradeProposal] = []
        
        # Run each strategy on each coin
        for coin, sentiment in context.sentiments.items():
            for strategy in self.strategies:
                try:
                    proposal = strategy.evaluate(coin, sentiment, context)
                    if proposal:
                        # Apply strategy weight to priority score
                        weight = self.weights.get(strategy.name, 0.1)
                        proposal.priority_score = proposal.confidence * weight * 100
                        proposals.append(proposal)
                except Exception as e:
                    logger.warning(f"Strategy {strategy.name} failed for {coin}: {e}")
        
        # Sort by priority score
        proposals.sort(key=lambda p: p.priority_score, reverse=True)
        
        # Select trades within risk limits
        selected = self._select_trades(proposals, context)
        
        # Update context
        context.trade_proposals = [p.to_dict() for p in selected]
        context.strategy_weights = self.weights.copy()
        
        # Build reasoning
        strategy_counts = {}
        for p in selected:
            strategy_counts[p.strategy] = strategy_counts.get(p.strategy, 0) + 1
        
        reasoning = f"Generated {len(proposals)} proposals, selected {len(selected)} trades. "
        reasoning += f"Strategies used: {strategy_counts}"
        
        output = EnsembleOutput(
            proposals=proposals,
            strategy_weights=self.weights.copy(),
            selected_trades=selected,
            reasoning=reasoning,
        )
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=reasoning,
            decision=f"selected_{len(selected)}_trades",
            confidence=85,
        )
    
    def _update_weights_for_regime(self, regime: str):
        """Adjust strategy weights based on market regime."""
        # Get affinity scores for current regime
        total_affinity = 0
        affinities = {}
        
        for strategy in self.strategies:
            affinity = strategy.affinity.get(regime, 50)
            affinities[strategy.name] = affinity
            total_affinity += affinity
        
        # Normalize to weights
        if total_affinity > 0:
            for name, affinity in affinities.items():
                self.weights[name] = affinity / total_affinity
        
        logger.debug(f"Updated weights for {regime}: {self.weights}")
    
    def _select_trades(
        self,
        proposals: List[TradeProposal],
        context: AgentContext,
    ) -> List[TradeProposal]:
        """Select trades within risk limits."""
        selected = []
        used_coins = set()
        total_exposure = 0
        new_coin_exposure = 0
        
        # Get existing positions
        existing_coins = {p.get("coin") for p in context.open_positions}
        
        for proposal in proposals:
            # Skip if already selected this coin
            if proposal.coin in used_coins:
                continue
            
            # Check per-coin limit
            if proposal.coin in existing_coins:
                max_size = self.MAX_PER_COIN
            else:
                max_size = self.MAX_NEW_COINS
                
                # Check new coin bucket
                if new_coin_exposure + proposal.size_percent / 100 > self.NEW_COIN_BUCKET:
                    continue
            
            # Apply limits
            actual_size = min(proposal.size_percent / 100, max_size)
            
            # Check total exposure
            if total_exposure + actual_size > self.MAX_TOTAL_EXPOSURE:
                continue
            
            # Accept trade
            proposal.size_percent = actual_size * 100
            selected.append(proposal)
            used_coins.add(proposal.coin)
            total_exposure += actual_size
            
            if proposal.coin not in existing_coins:
                new_coin_exposure += actual_size
            
            # Max trades per cycle
            if len(selected) >= self.MAX_TRADES_PER_CYCLE:
                break
        
        return selected
    
    async def update_performance(self, trade_result: Dict):
        """Update strategy performance from trade outcome."""
        from models import AsyncSessionLocal
        
        strategy = trade_result.get("strategy")
        pnl = trade_result.get("pnl", 0)
        is_win = pnl > 0
        
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO strategy_performance (
                        strategy_name, trades_24h, pnl_24h, 
                        win_rate_24h, current_weight
                    ) VALUES (
                        :strategy, 1, :pnl, 
                        :win_rate, :weight
                    )
                    ON CONFLICT (strategy_name) DO UPDATE SET
                        trades_24h = strategy_performance.trades_24h + 1,
                        pnl_24h = strategy_performance.pnl_24h + :pnl,
                        recorded_at = NOW()
                """), {
                    "strategy": strategy,
                    "pnl": pnl,
                    "win_rate": 100 if is_win else 0,
                    "weight": self.weights.get(strategy, 0.1),
                })
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to update strategy performance: {e}")

