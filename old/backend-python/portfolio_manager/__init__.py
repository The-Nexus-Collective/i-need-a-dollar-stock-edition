"""
Portfolio Manager - Grok-Powered Trading System

A simplified trading bot that uses Grok for all decision making:
- Identifies top 100 coins by market cap internally
- Analyzes X/Reddit sentiment from last 10 minutes
- Manages up to 50 positions (2% each)
- Logs human-readable analysis to logbook

Now with DB-first architecture:
- Restores capital and positions from database on startup
- Saves portfolio snapshots every minute
- Tracks position PnL history for trend analysis
"""

from .manager import PortfolioManager, run_portfolio_manager
from .positions import PositionTracker, Position
from .analyst import GrokAnalyst, AnalysisResult
from .logbook import TradingLogbook, LogEntry, get_logbook
from .snapshot_service import SnapshotService

# Import from trading_state - single source of truth for global instance
from trading_state import get_portfolio_manager, set_portfolio_manager

__all__ = [
    "PortfolioManager",
    "run_portfolio_manager",
    "get_portfolio_manager",
    "set_portfolio_manager",
    "PositionTracker",
    "Position",
    "GrokAnalyst",
    "AnalysisResult",
    "TradingLogbook",
    "LogEntry",
    "get_logbook",
    "SnapshotService",
]

