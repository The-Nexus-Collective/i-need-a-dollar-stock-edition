"""
Readiness Check - Auto go-live readiness assessment

Evaluates paper trading performance to determine if the strategy
is ready for live trading:
- Maximum drawdown < 15% over 30 days
- Win rate > 45%
- No liquidations in stress tests
- Minimum trade count for statistical significance
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import text

from models import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# READINESS THRESHOLDS
# ═══════════════════════════════════════════════════════════════════════════════

# Thresholds for "ready for live"
MAX_DRAWDOWN_THRESHOLD = 0.15      # 15% max drawdown
MIN_WIN_RATE_THRESHOLD = 0.45      # 45% win rate
MIN_TRADES_THRESHOLD = 50          # At least 50 trades
MAX_STRESS_LIQUIDATIONS = 0        # No liquidations in stress tests
MIN_SHARPE_RATIO = 0.5             # Minimum Sharpe ratio (if calculable)
MAX_AVG_SLIPPAGE = 0.003           # 0.3% max average slippage


@dataclass
class ReadinessMetrics:
    """Metrics used for readiness evaluation"""
    period_days: int
    trades_count: int
    win_rate: float
    total_pnl: float
    max_drawdown: float
    current_drawdown: float
    sharpe_ratio: Optional[float]
    avg_slippage: float
    avg_leverage: float
    stress_liquidations: int
    
    def to_dict(self) -> dict:
        return {
            "period_days": self.period_days,
            "trades_count": self.trades_count,
            "win_rate": round(self.win_rate * 100, 2),
            "total_pnl": round(self.total_pnl, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "current_drawdown": round(self.current_drawdown * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2) if self.sharpe_ratio else None,
            "avg_slippage": round(self.avg_slippage * 100, 4),
            "avg_leverage": round(self.avg_leverage, 1),
            "stress_liquidations": self.stress_liquidations
        }


@dataclass
class ReadinessBlocker:
    """A reason why the strategy is not ready for live"""
    metric: str
    current_value: float
    threshold_value: float
    severity: str  # 'critical', 'warning'
    message: str


@dataclass
class ReadinessResult:
    """Complete readiness assessment result"""
    checked_at: datetime
    is_ready: bool
    recommendation: str
    confidence: str  # 'low', 'medium', 'high'
    
    metrics: ReadinessMetrics
    blockers: List[ReadinessBlocker]
    
    def to_dict(self) -> dict:
        return {
            "checked_at": self.checked_at.isoformat(),
            "is_ready": self.is_ready,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "metrics": self.metrics.to_dict(),
            "blockers": [
                {
                    "metric": b.metric,
                    "current": b.current_value,
                    "threshold": b.threshold_value,
                    "severity": b.severity,
                    "message": b.message
                }
                for b in self.blockers
            ]
        }


class ReadinessChecker:
    """
    Evaluates paper trading performance for live readiness.
    
    Criteria for "ready":
    1. Max drawdown < 15% over 30 days
    2. Win rate > 45%
    3. At least 50 trades for statistical significance
    4. No liquidations in recent stress tests
    5. Sharpe ratio > 0.5 (if calculable)
    """
    
    async def get_paper_stats(self, days: int = 30) -> Dict:
        """Get paper trading statistics from database"""
        async with AsyncSessionLocal() as session:
            # Get trade statistics
            result = await session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_trades,
                        SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winners,
                        SUM(pnl) as total_pnl,
                        AVG(simulated_slippage) as avg_slippage,
                        AVG(leverage_used) as avg_leverage
                    FROM trades
                    WHERE mode = 'paper'
                      AND created_at >= NOW() - INTERVAL ':days days'
                """.replace(':days', str(days)))
            )
            trade_stats = result.fetchone()
            
            # Get drawdown from equity history
            result = await session.execute(
                text("""
                    SELECT 
                        MAX(equity) as peak,
                        MIN(equity) as trough,
                        (SELECT equity FROM account_equity_history 
                         ORDER BY recorded_at DESC LIMIT 1) as current
                    FROM account_equity_history
                    WHERE recorded_at >= NOW() - INTERVAL ':days days'
                """.replace(':days', str(days)))
            )
            equity_stats = result.fetchone()
            
            # Get stress test liquidations
            result = await session.execute(
                text("""
                    SELECT COALESCE(SUM(positions_liquidated), 0) as total_liq
                    FROM stress_tests
                    WHERE run_at >= NOW() - INTERVAL ':days days'
                """.replace(':days', str(days)))
            )
            stress_stats = result.fetchone()
            
            return {
                "trades": trade_stats,
                "equity": equity_stats,
                "stress": stress_stats
            }
    
    def calculate_sharpe_ratio(
        self,
        returns: List[float],
        risk_free_rate: float = 0.02
    ) -> Optional[float]:
        """Calculate annualized Sharpe ratio"""
        if not returns or len(returns) < 10:
            return None
        
        import statistics
        
        avg_return = statistics.mean(returns)
        std_return = statistics.stdev(returns)
        
        if std_return == 0:
            return None
        
        # Annualize (assuming daily returns)
        excess_return = avg_return - (risk_free_rate / 365)
        sharpe = (excess_return / std_return) * (365 ** 0.5)
        
        return sharpe
    
    async def check_live_readiness(
        self,
        days: int = 30
    ) -> ReadinessResult:
        """
        Perform complete readiness assessment.
        
        Args:
            days: Number of days to analyze
        
        Returns:
            ReadinessResult with assessment
        """
        stats = await self.get_paper_stats(days)
        
        trade_stats = stats["trades"]
        equity_stats = stats["equity"]
        stress_stats = stats["stress"]
        
        # Parse stats
        trades_count = int(trade_stats[0] or 0)
        winners = int(trade_stats[1] or 0)
        total_pnl = float(trade_stats[2] or 0)
        avg_slippage = float(trade_stats[3] or 0)
        avg_leverage = float(trade_stats[4] or 1.0)
        
        # Calculate win rate
        win_rate = winners / trades_count if trades_count > 0 else 0
        
        # Calculate drawdown
        peak = float(equity_stats[0] or 1) if equity_stats else 1
        trough = float(equity_stats[1] or 1) if equity_stats else 1
        current = float(equity_stats[2] or peak) if equity_stats else peak
        
        max_drawdown = (peak - trough) / peak if peak > 0 else 0
        current_drawdown = (peak - current) / peak if peak > 0 else 0
        
        # Stress test liquidations
        stress_liquidations = int(stress_stats[0] or 0) if stress_stats else 0
        
        # Build metrics
        metrics = ReadinessMetrics(
            period_days=days,
            trades_count=trades_count,
            win_rate=win_rate,
            total_pnl=total_pnl,
            max_drawdown=max_drawdown,
            current_drawdown=current_drawdown,
            sharpe_ratio=None,  # Would need daily returns
            avg_slippage=avg_slippage,
            avg_leverage=avg_leverage,
            stress_liquidations=stress_liquidations
        )
        
        # Evaluate blockers
        blockers = []
        
        # Check trade count
        if trades_count < MIN_TRADES_THRESHOLD:
            blockers.append(ReadinessBlocker(
                metric="trades_count",
                current_value=trades_count,
                threshold_value=MIN_TRADES_THRESHOLD,
                severity="critical",
                message=f"Need at least {MIN_TRADES_THRESHOLD} trades for statistical significance"
            ))
        
        # Check drawdown
        if max_drawdown > MAX_DRAWDOWN_THRESHOLD:
            blockers.append(ReadinessBlocker(
                metric="max_drawdown",
                current_value=max_drawdown,
                threshold_value=MAX_DRAWDOWN_THRESHOLD,
                severity="critical",
                message=f"Max drawdown {max_drawdown*100:.1f}% exceeds {MAX_DRAWDOWN_THRESHOLD*100:.0f}% threshold"
            ))
        
        # Check win rate
        if win_rate < MIN_WIN_RATE_THRESHOLD and trades_count >= 20:
            blockers.append(ReadinessBlocker(
                metric="win_rate",
                current_value=win_rate,
                threshold_value=MIN_WIN_RATE_THRESHOLD,
                severity="critical",
                message=f"Win rate {win_rate*100:.1f}% below {MIN_WIN_RATE_THRESHOLD*100:.0f}% threshold"
            ))
        
        # Check stress test liquidations
        if stress_liquidations > MAX_STRESS_LIQUIDATIONS:
            blockers.append(ReadinessBlocker(
                metric="stress_liquidations",
                current_value=stress_liquidations,
                threshold_value=MAX_STRESS_LIQUIDATIONS,
                severity="critical",
                message=f"{stress_liquidations} position(s) would have liquidated in stress tests"
            ))
        
        # Check slippage
        if avg_slippage > MAX_AVG_SLIPPAGE:
            blockers.append(ReadinessBlocker(
                metric="avg_slippage",
                current_value=avg_slippage,
                threshold_value=MAX_AVG_SLIPPAGE,
                severity="warning",
                message=f"Average slippage {avg_slippage*100:.2f}% is high"
            ))
        
        # Determine readiness
        critical_blockers = [b for b in blockers if b.severity == "critical"]
        is_ready = len(critical_blockers) == 0 and trades_count >= MIN_TRADES_THRESHOLD
        
        # Determine confidence
        if trades_count >= 100:
            confidence = "high"
        elif trades_count >= 50:
            confidence = "medium"
        else:
            confidence = "low"
        
        # Generate recommendation
        if is_ready:
            recommendation = (
                f"Ready for live trading! "
                f"Win rate: {win_rate*100:.1f}%, "
                f"Max drawdown: {max_drawdown*100:.1f}%, "
                f"Total PnL: ${total_pnl:,.2f} over {trades_count} trades."
            )
        else:
            if not blockers:
                recommendation = f"Continue paper trading. Need {MIN_TRADES_THRESHOLD} trades minimum."
            else:
                blocker_msgs = [b.message for b in critical_blockers[:2]]
                recommendation = f"Not ready: {'; '.join(blocker_msgs)}"
        
        result = ReadinessResult(
            checked_at=datetime.utcnow(),
            is_ready=is_ready,
            recommendation=recommendation,
            confidence=confidence,
            metrics=metrics,
            blockers=blockers
        )
        
        # Log result to database
        await self._log_result(result)
        
        logger.info(
            f"Readiness check: {'READY' if is_ready else 'NOT READY'} "
            f"({confidence} confidence). {recommendation}"
        )
        
        return result
    
    async def _log_result(self, result: ReadinessResult):
        """Log readiness check to database"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO readiness_checks 
                        (days_analyzed, trades_analyzed, max_drawdown, 
                         win_rate, sharpe_ratio, stress_liquidations,
                         is_ready, recommendation, blockers)
                    VALUES 
                        (:days, :trades, :drawdown, :winrate, :sharpe,
                         :stress, :ready, :rec, :blockers)
                """),
                {
                    "days": result.metrics.period_days,
                    "trades": result.metrics.trades_count,
                    "drawdown": result.metrics.max_drawdown,
                    "winrate": result.metrics.win_rate,
                    "sharpe": result.metrics.sharpe_ratio,
                    "stress": result.metrics.stress_liquidations,
                    "ready": result.is_ready,
                    "rec": result.recommendation,
                    "blockers": [b.metric for b in result.blockers]
                }
            )
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_checker: Optional[ReadinessChecker] = None


def get_readiness_checker() -> ReadinessChecker:
    """Get or create global readiness checker"""
    global _checker
    if _checker is None:
        _checker = ReadinessChecker()
    return _checker


async def check_live_readiness(days: int = 30) -> ReadinessResult:
    """Convenience function to check readiness"""
    checker = get_readiness_checker()
    return await checker.check_live_readiness(days=days)


async def is_ready_for_live(days: int = 30) -> bool:
    """Simple boolean check for readiness"""
    result = await check_live_readiness(days=days)
    return result.is_ready

