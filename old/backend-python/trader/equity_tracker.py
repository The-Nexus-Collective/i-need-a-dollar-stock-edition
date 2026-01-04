"""
Equity Tracker - Compatibility stub.

The equity tracking is now done by PositionTracker in portfolio_manager.
This stub provides backwards compatibility for legacy gateway endpoints.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class EquitySnapshot:
    """Snapshot of portfolio equity at a point in time."""
    
    timestamp: datetime
    total_equity: float
    cash: float
    positions_value: float
    unrealized_pnl: float
    position_details: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "total_equity": self.total_equity,
            "cash": self.cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl,
            "position_details": self.position_details,
        }


class EquityTracker:
    """
    Compatibility layer for legacy equity tracking.
    
    Now wraps the PositionTracker from portfolio_manager.
    """
    
    def __init__(self):
        self._history: List[EquitySnapshot] = []
    
    def get_latest(self) -> Optional[EquitySnapshot]:
        """Get latest equity snapshot."""
        try:
            from portfolio_manager import get_portfolio_manager
            manager = get_portfolio_manager()
            if manager:
                tracker = manager.positions
                return EquitySnapshot(
                    timestamp=datetime.utcnow(),
                    total_equity=tracker.total_equity,
                    cash=tracker.capital,
                    positions_value=sum(p.size_usdt for p in tracker.positions.values()),
                    unrealized_pnl=tracker.total_unrealized_pnl,
                    position_details=[
                        {
                            "symbol": p.symbol,
                            "direction": p.direction,
                            "size_usdt": p.size_usdt,
                            "unrealized_pnl": p.unrealized_pnl,
                        }
                        for p in tracker.positions.values()
                    ],
                )
        except Exception:
            pass
        
        # Return default if no manager
        return EquitySnapshot(
            timestamp=datetime.utcnow(),
            total_equity=100000,
            cash=100000,
            positions_value=0,
            unrealized_pnl=0,
        )
    
    def get_history(self, limit: int = 60) -> List[EquitySnapshot]:
        """Get equity history."""
        return self._history[-limit:]


# Global instance
_tracker: Optional[EquityTracker] = None


def get_equity_tracker() -> EquityTracker:
    """Get or create the global equity tracker."""
    global _tracker
    if _tracker is None:
        _tracker = EquityTracker()
    return _tracker
