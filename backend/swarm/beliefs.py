"""
Belief System - What the Agent Thinks is True

Agents form beliefs about the world that influence their behavior.
Beliefs are updated based on evidence and outcomes.

Examples:
- "BTC is in a bull market": 0.75
- "Meme coins are hot right now": 0.60
- "High volume = good opportunity": 0.80
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class Belief:
    """
    A single belief about the world.
    
    Beliefs have:
    - A statement (what is believed)
    - A probability (how strongly believed, 0-1)
    - Evidence that supports/contradicts
    - Decay over time without reinforcement
    """
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # The belief
    statement: str = ""
    category: str = "general"  # market, sentiment, strategy, etc.
    
    # Probability (0-1)
    probability: float = 0.5
    
    # Confidence in this probability
    confidence: float = 0.5
    
    # Evidence tracking
    supporting_evidence: List[str] = field(default_factory=list)
    contradicting_evidence: List[str] = field(default_factory=list)
    
    # Decay
    last_reinforced: datetime = field(default_factory=datetime.utcnow)
    decay_rate: float = 0.01  # Probability decays toward 0.5 over time
    
    # Source
    source_agent: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "statement": self.statement,
            "category": self.category,
            "probability": self.probability,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "supporting_count": len(self.supporting_evidence),
            "contradicting_count": len(self.contradicting_evidence),
        }
    
    def update(self, evidence: str, supports: bool, weight: float = 0.1):
        """
        Update belief based on new evidence.
        
        Uses a simple Bayesian-ish update:
        - Supporting evidence increases probability
        - Contradicting evidence decreases probability
        - Weight determines how much to update
        """
        if supports:
            self.probability = min(0.99, self.probability + weight * (1 - self.probability))
            self.supporting_evidence.append(evidence[:200])
        else:
            self.probability = max(0.01, self.probability - weight * self.probability)
            self.contradicting_evidence.append(evidence[:200])
        
        # Update confidence based on evidence volume
        total_evidence = len(self.supporting_evidence) + len(self.contradicting_evidence)
        self.confidence = min(0.95, 0.5 + total_evidence * 0.05)
        
        self.updated_at = datetime.utcnow()
        self.last_reinforced = datetime.utcnow()
    
    def decay(self):
        """
        Apply decay - beliefs decay toward 0.5 (uncertainty) over time.
        """
        hours_since_update = (datetime.utcnow() - self.last_reinforced).total_seconds() / 3600
        
        if hours_since_update > 1:
            decay_amount = self.decay_rate * hours_since_update
            
            if self.probability > 0.5:
                self.probability = max(0.5, self.probability - decay_amount)
            else:
                self.probability = min(0.5, self.probability + decay_amount)


class BeliefSystem:
    """
    Manages all beliefs for an agent.
    
    Features:
    - Create and update beliefs
    - Query beliefs by category
    - Decay old beliefs
    - Export for prompts
    """
    
    def __init__(self):
        self._beliefs: Dict[str, Belief] = {}  # statement -> belief
        self._lock = asyncio.Lock()
    
    async def add_belief(
        self,
        statement: str,
        category: str = "general",
        initial_probability: float = 0.5,
        source_agent: str = "",
    ) -> Belief:
        """Add a new belief."""
        async with self._lock:
            if statement in self._beliefs:
                return self._beliefs[statement]
            
            belief = Belief(
                statement=statement,
                category=category,
                probability=initial_probability,
                source_agent=source_agent,
            )
            self._beliefs[statement] = belief
            return belief
    
    async def update_belief(
        self,
        statement: str,
        evidence: str,
        supports: bool,
        weight: float = 0.1,
    ) -> Optional[Belief]:
        """Update a belief with new evidence."""
        async with self._lock:
            if statement not in self._beliefs:
                # Create new belief
                self._beliefs[statement] = Belief(statement=statement)
            
            belief = self._beliefs[statement]
            belief.update(evidence, supports, weight)
            return belief
    
    def get_belief(self, statement: str) -> Optional[Belief]:
        """Get a specific belief."""
        return self._beliefs.get(statement)
    
    def get_beliefs_by_category(self, category: str) -> List[Belief]:
        """Get all beliefs in a category."""
        return [b for b in self._beliefs.values() if b.category == category]
    
    def get_strong_beliefs(self, threshold: float = 0.7) -> List[Belief]:
        """Get beliefs with probability > threshold or < (1 - threshold)."""
        return [
            b for b in self._beliefs.values()
            if b.probability > threshold or b.probability < (1 - threshold)
        ]
    
    async def apply_decay(self):
        """Apply decay to all beliefs."""
        async with self._lock:
            for belief in self._beliefs.values():
                belief.decay()
    
    def to_prompt(self, max_beliefs: int = 10) -> str:
        """
        Export beliefs for use in prompts.
        
        Shows the strongest beliefs.
        """
        if not self._beliefs:
            return "No strong beliefs yet."
        
        # Sort by distance from 0.5 (strength of belief)
        sorted_beliefs = sorted(
            self._beliefs.values(),
            key=lambda b: abs(b.probability - 0.5),
            reverse=True
        )[:max_beliefs]
        
        lines = []
        for belief in sorted_beliefs:
            # Format probability as percentage
            pct = int(belief.probability * 100)
            indicator = "✓" if belief.probability > 0.5 else "✗"
            lines.append(f"- {indicator} {belief.statement}: {pct}%")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, dict]:
        """Export all beliefs as dict."""
        return {
            statement: belief.to_dict()
            for statement, belief in self._beliefs.items()
        }
    
    def __len__(self) -> int:
        return len(self._beliefs)

