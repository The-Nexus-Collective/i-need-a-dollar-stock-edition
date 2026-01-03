"""
Concrete Agent Implementations

Each agent has a specific personality and focus:
- Scout: Scans X and web for opportunities
- Analyst: Deep research on specific projects
- Oracle: Sentiment and market analysis
- Tactician: Strategy formulation and decisions
- Operator: Trade execution
- Sage: Learning and memory management
"""

from .scout import ScoutAgent
from .analyst import AnalystAgent
from .oracle import OracleAgent
from .tactician import TacticianAgent
from .operator import OperatorAgent
from .sage import SageAgent

__all__ = [
    'ScoutAgent',
    'AnalystAgent',
    'OracleAgent',
    'TacticianAgent',
    'OperatorAgent',
    'SageAgent',
]


def create_default_swarm():
    """Create the default set of agents."""
    return [
        ScoutAgent(),
        AnalystAgent(),
        OracleAgent(),
        TacticianAgent(),
        OperatorAgent(),
        SageAgent(),
    ]

