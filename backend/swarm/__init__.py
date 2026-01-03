"""
Emergent AI Swarm - Self-Evolving Agent System

A swarm of autonomous agents that:
- Perceive the world through Grok (web + X search)
- Think and reason in real-time (streamed)
- Speak to each other via signals
- Act on high-conviction insights
- Evolve through beliefs, hypotheses, and strategy mutations

No scripts. No fixed queries. Just simple rules that produce complex behavior.
"""

from .grok import Grok, get_grok
from .agent import EmergentAgent
from .signals import Signal, SignalType, SignalNetwork, get_signal_network
from .beliefs import Belief, BeliefSystem
from .hypotheses import Hypothesis, HypothesisPool
from .strategies import StrategyGene, StrategyEvolution
from .memory import SwarmMemory, get_swarm_memory
from .network import SwarmNetwork, get_swarm_network

__all__ = [
    'Grok', 'get_grok',
    'EmergentAgent',
    'Signal', 'SignalType', 'SignalNetwork', 'get_signal_network',
    'Belief', 'BeliefSystem',
    'Hypothesis', 'HypothesisPool',
    'StrategyGene', 'StrategyEvolution',
    'SwarmMemory', 'get_swarm_memory',
    'SwarmNetwork', 'get_swarm_network',
]

