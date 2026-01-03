"""
Simple Prediction Trader

A straightforward trading system that:
- Fetches top 10 coins by volume every 15 minutes
- Asks Grok for LONG/SHORT predictions with conviction
- Opens positions with conviction-based leverage (1x-10x)
- Closes all positions before each new cycle
"""

from .predictor import Predictor, Prediction
from .executor import Executor

__all__ = [
    'Predictor',
    'Prediction',
    'Executor',
]

