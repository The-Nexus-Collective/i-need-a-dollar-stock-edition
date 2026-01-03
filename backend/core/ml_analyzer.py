"""
ML Trade Analyzer - Paper trade analysis and optimization suggestions

Analyzes paper trading performance and suggests parameter tweaks:
- Score threshold optimization
- Leverage adjustment recommendations
- Filter effectiveness analysis
- Win rate by regime analysis
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from sqlalchemy import text

from models import AsyncSessionLocal

logger = logging.getLogger(__name__)


@dataclass
class TradeStats:
    """Statistics for a subset of trades"""
    count: int
    winners: int
    losers: int
    total_pnl: float
    avg_pnl: float
    max_win: float
    max_loss: float
    avg_leverage: float
    avg_slippage: float
    
    @property
    def win_rate(self) -> float:
        if self.count == 0:
            return 0
        return (self.winners / self.count) * 100
    
    @property
    def profit_factor(self) -> float:
        """Ratio of gross profit to gross loss"""
        if self.max_loss == 0:
            return float('inf') if self.max_win > 0 else 0
        return abs(self.max_win / self.max_loss) if self.max_loss != 0 else 0


@dataclass
class AnalysisSuggestion:
    """A suggested parameter change"""
    parameter: str
    current_value: float
    suggested_value: float
    expected_improvement: str
    confidence: str  # 'low', 'medium', 'high'
    reasoning: str


@dataclass
class AnalysisResult:
    """Complete analysis result"""
    analyzed_at: datetime
    trades_analyzed: int
    period_days: int
    
    # Overall stats
    overall_stats: TradeStats
    
    # Suggestions
    suggestions: List[AnalysisSuggestion]
    
    # Detailed breakdowns
    stats_by_threshold: Dict[int, TradeStats]
    stats_by_leverage: Dict[str, TradeStats]
    stats_by_regime: Dict[str, TradeStats]
    
    def to_dict(self) -> dict:
        return {
            "analyzed_at": self.analyzed_at.isoformat(),
            "trades_analyzed": self.trades_analyzed,
            "period_days": self.period_days,
            "overall_win_rate": self.overall_stats.win_rate,
            "overall_pnl": self.overall_stats.total_pnl,
            "suggestions": [
                {
                    "parameter": s.parameter,
                    "current": s.current_value,
                    "suggested": s.suggested_value,
                    "improvement": s.expected_improvement,
                    "confidence": s.confidence,
                    "reasoning": s.reasoning
                }
                for s in self.suggestions
            ]
        }


class MLAnalyzer:
    """
    Analyzes paper trades to find optimization opportunities.
    
    Methods:
    - analyze_paper_trades: Full analysis with suggestions
    - get_stats_by_threshold: Performance at different score thresholds
    - get_stats_by_leverage: Performance at different leverage levels
    """
    
    async def get_recent_trades(
        self,
        days: int = 30,
        mode: str = 'paper',
        min_trades: int = 0
    ) -> List[Dict]:
        """Fetch recent trades from database"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT 
                        t.id, t.coin, t.side, t.quantity, t.price,
                        t.pnl, t.fee, t.simulated_slippage, t.leverage_used,
                        t.created_at, t.mode,
                        s.combined_score, s.market_regime
                    FROM trades t
                    LEFT JOIN signals s ON t.coin = s.coin 
                        AND DATE(t.created_at) = DATE(s.created_at)
                    WHERE t.mode = :mode
                      AND t.created_at >= NOW() - INTERVAL ':days days'
                      AND t.pnl IS NOT NULL
                    ORDER BY t.created_at DESC
                """.replace(':days', str(days))),
                {"mode": mode}
            )
            
            trades = []
            for row in result.fetchall():
                trades.append({
                    "id": str(row[0]),
                    "coin": row[1],
                    "side": row[2],
                    "quantity": float(row[3]),
                    "price": float(row[4]),
                    "pnl": float(row[5]) if row[5] else 0,
                    "fee": float(row[6]) if row[6] else 0,
                    "slippage": float(row[7]) if row[7] else 0,
                    "leverage": float(row[8]) if row[8] else 1.0,
                    "created_at": row[9],
                    "mode": row[10],
                    "score": float(row[11]) if row[11] else 0,
                    "regime": row[12] or "normal"
                })
            
            return trades
    
    def calculate_stats(self, trades: List[Dict]) -> TradeStats:
        """Calculate statistics for a set of trades"""
        if not trades:
            return TradeStats(
                count=0, winners=0, losers=0,
                total_pnl=0, avg_pnl=0, max_win=0, max_loss=0,
                avg_leverage=1.0, avg_slippage=0
            )
        
        winners = [t for t in trades if t['pnl'] > 0]
        losers = [t for t in trades if t['pnl'] < 0]
        
        total_pnl = sum(t['pnl'] for t in trades)
        pnls = [t['pnl'] for t in trades]
        
        return TradeStats(
            count=len(trades),
            winners=len(winners),
            losers=len(losers),
            total_pnl=total_pnl,
            avg_pnl=total_pnl / len(trades),
            max_win=max(pnls) if pnls else 0,
            max_loss=min(pnls) if pnls else 0,
            avg_leverage=sum(t['leverage'] for t in trades) / len(trades),
            avg_slippage=sum(t['slippage'] for t in trades) / len(trades)
        )
    
    async def analyze_by_threshold(
        self,
        trades: List[Dict],
        thresholds: List[int] = [60, 65, 70, 75, 80]
    ) -> Dict[int, TradeStats]:
        """Analyze performance at different score thresholds"""
        results = {}
        
        for threshold in thresholds:
            filtered = [t for t in trades if abs(t['score']) >= threshold]
            results[threshold] = self.calculate_stats(filtered)
        
        return results
    
    async def analyze_by_leverage(
        self,
        trades: List[Dict]
    ) -> Dict[str, TradeStats]:
        """Analyze performance at different leverage levels"""
        buckets = {
            "1x-2x": (0, 2),
            "2x-3x": (2, 3),
            "3x-4x": (3, 4),
            "4x-5x": (4, 6)
        }
        
        results = {}
        for label, (low, high) in buckets.items():
            filtered = [t for t in trades if low < t['leverage'] <= high]
            if filtered:
                results[label] = self.calculate_stats(filtered)
        
        return results
    
    async def analyze_by_regime(
        self,
        trades: List[Dict]
    ) -> Dict[str, TradeStats]:
        """Analyze performance in different market regimes"""
        regimes = defaultdict(list)
        
        for trade in trades:
            regimes[trade['regime']].append(trade)
        
        return {
            regime: self.calculate_stats(trades)
            for regime, trades in regimes.items()
        }
    
    def generate_suggestions(
        self,
        overall_stats: TradeStats,
        threshold_stats: Dict[int, TradeStats],
        leverage_stats: Dict[str, TradeStats],
        regime_stats: Dict[str, TradeStats]
    ) -> List[AnalysisSuggestion]:
        """Generate parameter optimization suggestions"""
        suggestions = []
        
        # 1. Score threshold analysis
        if threshold_stats:
            best_threshold = max(
                threshold_stats.items(),
                key=lambda x: x[1].win_rate if x[1].count >= 10 else 0
            )
            current_threshold = 65  # Default
            
            if best_threshold[0] != current_threshold and best_threshold[1].count >= 10:
                improvement = best_threshold[1].win_rate - overall_stats.win_rate
                if improvement > 2:  # At least 2% improvement
                    suggestions.append(AnalysisSuggestion(
                        parameter="SCORE_THRESHOLD",
                        current_value=current_threshold,
                        suggested_value=best_threshold[0],
                        expected_improvement=f"+{improvement:.1f}% win rate",
                        confidence="medium" if best_threshold[1].count >= 30 else "low",
                        reasoning=f"Threshold {best_threshold[0]} has {best_threshold[1].win_rate:.1f}% win rate vs current {overall_stats.win_rate:.1f}%"
                    ))
        
        # 2. Leverage analysis
        if leverage_stats:
            best_leverage = max(
                leverage_stats.items(),
                key=lambda x: x[1].total_pnl / x[1].count if x[1].count >= 5 else float('-inf')
            )
            
            worst_leverage = min(
                leverage_stats.items(),
                key=lambda x: x[1].total_pnl / x[1].count if x[1].count >= 5 else float('inf')
            )
            
            if worst_leverage[1].count >= 5 and worst_leverage[1].avg_pnl < 0:
                suggestions.append(AnalysisSuggestion(
                    parameter="MAX_LEVERAGE",
                    current_value=5.0,
                    suggested_value=3.0 if "4x" in worst_leverage[0] else 4.0,
                    expected_improvement=f"Avoid {abs(worst_leverage[1].total_pnl):.2f} USDT losses",
                    confidence="medium",
                    reasoning=f"Leverage {worst_leverage[0]} has avg PnL of {worst_leverage[1].avg_pnl:.2f}"
                ))
        
        # 3. Regime analysis
        if regime_stats and "stress" in regime_stats:
            stress_stats = regime_stats["stress"]
            if stress_stats.count >= 5 and stress_stats.win_rate < 40:
                suggestions.append(AnalysisSuggestion(
                    parameter="STRESS_REGIME_SKIP",
                    current_value=0,
                    suggested_value=1,
                    expected_improvement=f"Avoid {abs(stress_stats.total_pnl):.2f} USDT in stress losses",
                    confidence="high" if stress_stats.count >= 15 else "medium",
                    reasoning=f"Stress regime has {stress_stats.win_rate:.1f}% win rate - consider skipping trades"
                ))
        
        # 4. Overall performance suggestions
        if overall_stats.count >= 50:
            if overall_stats.win_rate < 45:
                suggestions.append(AnalysisSuggestion(
                    parameter="RISK_PER_TRADE",
                    current_value=0.02,
                    suggested_value=0.015,
                    expected_improvement="Reduce risk while optimizing strategy",
                    confidence="medium",
                    reasoning=f"Win rate of {overall_stats.win_rate:.1f}% suggests reducing position sizes"
                ))
            
            if overall_stats.avg_slippage > 0.002:  # > 0.2%
                suggestions.append(AnalysisSuggestion(
                    parameter="POSITION_SIZE_CAP",
                    current_value=0,
                    suggested_value=0.15,
                    expected_improvement=f"Reduce slippage from {overall_stats.avg_slippage*100:.2f}%",
                    confidence="low",
                    reasoning="High average slippage suggests position sizes may be too large"
                ))
        
        return suggestions
    
    async def analyze_paper_trades(
        self,
        days: int = 30,
        min_trades: int = 20
    ) -> AnalysisResult:
        """
        Run full analysis on paper trades.
        
        Args:
            days: Number of days to analyze
            min_trades: Minimum trades required for analysis
        
        Returns:
            AnalysisResult with stats and suggestions
        """
        trades = await self.get_recent_trades(days=days, mode='paper')
        
        if len(trades) < min_trades:
            logger.info(
                f"Only {len(trades)} trades found (need {min_trades}). "
                "Continue paper trading for more data."
            )
            return AnalysisResult(
                analyzed_at=datetime.utcnow(),
                trades_analyzed=len(trades),
                period_days=days,
                overall_stats=self.calculate_stats(trades),
                suggestions=[],
                stats_by_threshold={},
                stats_by_leverage={},
                stats_by_regime={}
            )
        
        # Calculate all statistics
        overall_stats = self.calculate_stats(trades)
        threshold_stats = await self.analyze_by_threshold(trades)
        leverage_stats = await self.analyze_by_leverage(trades)
        regime_stats = await self.analyze_by_regime(trades)
        
        # Generate suggestions
        suggestions = self.generate_suggestions(
            overall_stats, threshold_stats, leverage_stats, regime_stats
        )
        
        logger.info(
            f"Analyzed {len(trades)} trades over {days} days. "
            f"Win rate: {overall_stats.win_rate:.1f}%, "
            f"Total PnL: ${overall_stats.total_pnl:.2f}. "
            f"Generated {len(suggestions)} suggestions."
        )
        
        return AnalysisResult(
            analyzed_at=datetime.utcnow(),
            trades_analyzed=len(trades),
            period_days=days,
            overall_stats=overall_stats,
            suggestions=suggestions,
            stats_by_threshold=threshold_stats,
            stats_by_leverage=leverage_stats,
            stats_by_regime=regime_stats
        )


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_analyzer: Optional[MLAnalyzer] = None


def get_ml_analyzer() -> MLAnalyzer:
    """Get or create global ML analyzer"""
    global _analyzer
    if _analyzer is None:
        _analyzer = MLAnalyzer()
    return _analyzer


async def analyze_paper_trades(
    days: int = 30,
    min_trades: int = 20
) -> AnalysisResult:
    """Convenience function to run analysis"""
    analyzer = get_ml_analyzer()
    return await analyzer.analyze_paper_trades(days=days, min_trades=min_trades)


async def get_suggestions(days: int = 30) -> List[Dict]:
    """Get just the suggestions as dicts"""
    result = await analyze_paper_trades(days=days)
    return [
        {
            "parameter": s.parameter,
            "current": s.current_value,
            "suggested": s.suggested_value,
            "improvement": s.expected_improvement,
            "confidence": s.confidence,
            "reasoning": s.reasoning
        }
        for s in result.suggestions
    ]

