"""
Agentic Trading System - Multi-Agent Architecture

This module contains all specialized agents that work together
to discover, analyze, and trade cryptocurrencies autonomously.

Agents:
- Orchestrator: Central brain coordinating all agents
- Discovery: Finds new coins from CoinGecko and X
- Validation: Validates assets meet trading criteria
- Sentiment: Analyzes sentiment via Grok AI
- StrategyEnsemble: Manages 6 sub-strategies with meta-learning
- Execution: Executes trades with paper/live modes
- Learner: Reflects on trades and improves strategies
"""

from .base import BaseAgent, AgentOutput, AgentContext
from .logbook import AgentLogbook, LogEntry, get_logbook
from .orchestrator import Orchestrator
from .discovery import DiscoveryAgent
from .validation import ValidationAgent
from .sentiment import SentimentAgent
from .strategy_ensemble import StrategyEnsemble
from .execution import ExecutionAgent
from .learner import LearnerAgent

__all__ = [
    # Base
    'BaseAgent',
    'AgentOutput',
    'AgentContext',
    
    # Logbook
    'AgentLogbook',
    'LogEntry',
    'get_logbook',
    
    # Agents
    'Orchestrator',
    'DiscoveryAgent',
    'ValidationAgent',
    'SentimentAgent',
    'StrategyEnsemble',
    'ExecutionAgent',
    'LearnerAgent',
]

