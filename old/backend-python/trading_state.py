"""
Trading State - Global singleton for Portfolio Manager

DB-FIRST ARCHITECTURE:
- This module provides access to the running Portfolio Manager instance
- The Portfolio Manager reads all data from the database
- No in-memory state is the source of truth

For production systems managing millions of dollars:
- All data comes from PostgreSQL
- No data loss on process crash
- Single source of truth
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from portfolio_manager import PortfolioManager

# Global instance - just a reference to the running manager
_portfolio_manager: Optional["PortfolioManager"] = None


def get_portfolio_manager() -> Optional["PortfolioManager"]:
    """Get the running Portfolio Manager instance."""
    return _portfolio_manager


def set_portfolio_manager(manager: "PortfolioManager"):
    """Set the global Portfolio Manager instance."""
    global _portfolio_manager
    _portfolio_manager = manager


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

def get_trading_loop():
    """
    Legacy compatibility function.
    
    Returns a wrapper that provides minimal backwards-compatible interface.
    Most data should now be read directly from repositories.
    """
    manager = get_portfolio_manager()
    if not manager:
        return None
    
    return PortfolioManagerWrapper(manager)


class PortfolioManagerWrapper:
    """
    Minimal wrapper for backwards compatibility.
    
    DB-FIRST: Most functionality should use repositories directly.
    This wrapper exists only for legacy code that hasn't been migrated.
    """
    
    def __init__(self, manager: "PortfolioManager"):
        self._manager = manager
    
    @property
    def _current_phase(self) -> str:
        return self._manager._current_phase
    
    @property
    def _cycle_count(self) -> int:
        return self._manager._cycle_count
    
    @property
    def executor(self):
        """
        DEPRECATED: Use repositories directly.
        Returns minimal executor interface.
        """
        return ExecutorWrapper(self._manager)
    
    def get_status(self) -> dict:
        return self._manager.get_status()
    
    def reset_paper_trading(self) -> dict:
        """
        DEPRECATED: Use TraderStateRepository.reset() via API.
        This is a no-op since we have no in-memory state.
        """
        return {
            "status": "db_first",
            "message": "DB-First architecture - use API reset endpoint",
            "positions_cleared": 0,
        }


class ExecutorWrapper:
    """
    Minimal executor wrapper for backwards compatibility.
    
    DEPRECATED: Use repositories directly.
    """
    
    def __init__(self, manager: "PortfolioManager"):
        self._manager = manager
    
    @property
    def capital(self) -> float:
        """
        DEPRECATED: Use await positions.get_capital()
        Returns starting capital as fallback.
        """
        return self._manager._starting_capital
    
    @property
    def starting_capital(self) -> float:
        return self._manager._starting_capital
    
    @property
    def positions(self):
        """
        DEPRECATED: Use await positions.get_positions()
        Returns empty dict.
        """
        return {}
    
    @property
    def closed_positions(self):
        """DEPRECATED: Use PositionRepository.get_closed_positions()"""
        return []
    
    @property
    def cycles(self):
        return []
    
    @property
    def total_fees_paid(self) -> float:
        return 0.0
    
    @property
    def total_spread_cost(self) -> float:
        return 0.0
    
    @property
    def total_slippage_cost(self) -> float:
        return 0.0
    
    def reset_state(self):
        """DEPRECATED: Use TraderStateRepository.reset()"""
        pass
