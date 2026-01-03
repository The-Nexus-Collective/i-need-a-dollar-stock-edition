"""
Global trading state singleton.

This module exists to solve the __main__ vs main module identity problem.
By keeping the global state here, it's always accessed via the same module
regardless of how main.py was invoked.
"""
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    # Avoid circular imports
    from main import TradingLoop

# Global singleton
_trading_loop: Optional["TradingLoop"] = None


def set_trading_loop(loop: "TradingLoop") -> None:
    """Set the global trading loop instance."""
    global _trading_loop
    _trading_loop = loop


def get_trading_loop() -> Optional["TradingLoop"]:
    """Get the global trading loop instance."""
    return _trading_loop

