"""
Hypothesis Pool - Testable Market Theories

Agents form hypotheses about market behavior.
Hypotheses are tested with predictions.
Successful hypotheses are reinforced; failed ones are mutated or discarded.

Examples:
- "Meme coins pump after Elon tweets"
- "BTC rallies when funding goes negative"
- "New listings pump 50% in first week"
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class Prediction:
    """A prediction made to test a hypothesis."""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # What is predicted
    statement: str = ""
    target: str = ""  # e.g., "BTC", "PEPE"
    
    # Prediction details
    direction: str = "up"  # up, down, sideways
    magnitude: float = 0.0  # Expected % change
    timeframe_hours: int = 24
    
    # Outcome
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    outcome_correct: Optional[bool] = None
    actual_result: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "statement": self.statement,
            "target": self.target,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "timeframe_hours": self.timeframe_hours,
            "resolved": self.resolved,
            "outcome_correct": self.outcome_correct,
        }


@dataclass
class Hypothesis:
    """
    A testable hypothesis about market behavior.
    
    Hypotheses:
    - Make specific predictions
    - Track their success rate
    - Evolve through mutation when they fail
    """
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # The hypothesis
    statement: str = ""
    category: str = "market"  # market, sentiment, strategy, narrative
    
    # Confidence
    confidence: float = 0.5  # Current confidence (0-1)
    initial_confidence: float = 0.5
    
    # Testing
    predictions: List[Prediction] = field(default_factory=list)
    tests_total: int = 0
    tests_passed: int = 0
    
    @property
    def success_rate(self) -> float:
        if self.tests_total == 0:
            return 0.5  # Prior
        return self.tests_passed / self.tests_total
    
    # Source
    source_agent: str = ""
    parent_hypothesis: Optional[UUID] = None  # For mutations
    generation: int = 0
    
    # Flags
    is_active: bool = True
    discarded_at: Optional[datetime] = None
    discard_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "statement": self.statement,
            "category": self.category,
            "confidence": self.confidence,
            "success_rate": self.success_rate,
            "tests_total": self.tests_total,
            "tests_passed": self.tests_passed,
            "is_active": self.is_active,
            "generation": self.generation,
        }
    
    def make_prediction(
        self,
        target: str,
        direction: str = "up",
        magnitude: float = 5.0,
        timeframe_hours: int = 24,
    ) -> Prediction:
        """Make a prediction to test this hypothesis."""
        prediction = Prediction(
            statement=f"Based on '{self.statement}': {target} will go {direction} {magnitude}% in {timeframe_hours}h",
            target=target,
            direction=direction,
            magnitude=magnitude,
            timeframe_hours=timeframe_hours,
        )
        self.predictions.append(prediction)
        return prediction
    
    def record_outcome(self, prediction_id: UUID, correct: bool, actual_result: str = ""):
        """Record the outcome of a prediction."""
        for pred in self.predictions:
            if pred.id == prediction_id:
                pred.resolved = True
                pred.resolved_at = datetime.utcnow()
                pred.outcome_correct = correct
                pred.actual_result = actual_result
                
                self.tests_total += 1
                if correct:
                    self.tests_passed += 1
                
                # Update confidence
                self._update_confidence()
                break
    
    def _update_confidence(self):
        """Update confidence based on track record."""
        if self.tests_total == 0:
            return
        
        # Simple Bayesian update
        # Start from initial_confidence, adjust based on success rate
        prior = self.initial_confidence
        evidence_weight = min(0.5, self.tests_total * 0.05)  # More tests = more weight
        
        self.confidence = prior * (1 - evidence_weight) + self.success_rate * evidence_weight
        self.updated_at = datetime.utcnow()
    
    def mutate(self) -> "Hypothesis":
        """
        Create a mutated version of this hypothesis.
        
        Used when the hypothesis is underperforming.
        """
        # Simple mutation: slightly modify the statement
        mutations = [
            lambda s: s.replace("always", "often"),
            lambda s: s.replace("often", "sometimes"),
            lambda s: s.replace("pump", "move"),
            lambda s: s.replace("50%", "30%"),
            lambda s: s.replace("week", "few days"),
            lambda s: s.replace("after", "within 24h of"),
        ]
        
        new_statement = self.statement
        for mutation in random.sample(mutations, min(2, len(mutations))):
            new_statement = mutation(new_statement)
        
        return Hypothesis(
            statement=new_statement,
            category=self.category,
            confidence=0.5,  # Reset confidence
            initial_confidence=0.5,
            source_agent=self.source_agent,
            parent_hypothesis=self.id,
            generation=self.generation + 1,
        )
    
    def discard(self, reason: str):
        """Mark hypothesis as discarded."""
        self.is_active = False
        self.discarded_at = datetime.utcnow()
        self.discard_reason = reason


class HypothesisPool:
    """
    Shared pool of hypotheses.
    
    Agents can:
    - Add new hypotheses
    - Adopt existing hypotheses
    - Test hypotheses
    - Evolve hypotheses through mutation
    """
    
    MIN_CONFIDENCE_THRESHOLD = 0.3  # Discard below this
    MIN_TESTS_BEFORE_MUTATION = 5  # Need this many tests before mutating
    
    def __init__(self):
        self._hypotheses: Dict[UUID, Hypothesis] = {}
        self._lock = asyncio.Lock()
    
    async def add(self, hypothesis: Hypothesis) -> Hypothesis:
        """Add a hypothesis to the pool."""
        async with self._lock:
            self._hypotheses[hypothesis.id] = hypothesis
            return hypothesis
    
    async def create(
        self,
        statement: str,
        category: str = "market",
        source_agent: str = "",
        initial_confidence: float = 0.5,
    ) -> Hypothesis:
        """Create and add a new hypothesis."""
        hypothesis = Hypothesis(
            statement=statement,
            category=category,
            confidence=initial_confidence,
            initial_confidence=initial_confidence,
            source_agent=source_agent,
        )
        return await self.add(hypothesis)
    
    def get(self, hypothesis_id: UUID) -> Optional[Hypothesis]:
        """Get a hypothesis by ID."""
        return self._hypotheses.get(hypothesis_id)
    
    def get_active(self) -> List[Hypothesis]:
        """Get all active hypotheses."""
        return [h for h in self._hypotheses.values() if h.is_active]
    
    def get_by_category(self, category: str) -> List[Hypothesis]:
        """Get hypotheses by category."""
        return [
            h for h in self._hypotheses.values()
            if h.category == category and h.is_active
        ]
    
    def get_best(self, limit: int = 10) -> List[Hypothesis]:
        """Get top performing hypotheses."""
        active = self.get_active()
        return sorted(
            active,
            key=lambda h: (h.success_rate, h.tests_total),
            reverse=True
        )[:limit]
    
    async def evolve(self):
        """
        Evolve the hypothesis pool.
        
        - Discard underperformers
        - Mutate struggling hypotheses
        - Crossover successful ones
        """
        async with self._lock:
            mutations = []
            
            for hypothesis in list(self._hypotheses.values()):
                if not hypothesis.is_active:
                    continue
                
                # Discard very low confidence
                if hypothesis.confidence < self.MIN_CONFIDENCE_THRESHOLD:
                    if hypothesis.tests_total >= self.MIN_TESTS_BEFORE_MUTATION:
                        hypothesis.discard(f"Confidence dropped to {hypothesis.confidence:.2f}")
                        continue
                
                # Mutate struggling hypotheses
                if (hypothesis.tests_total >= self.MIN_TESTS_BEFORE_MUTATION and
                    hypothesis.success_rate < 0.4):
                    # Create a mutation
                    mutated = hypothesis.mutate()
                    mutations.append(mutated)
            
            # Add mutations to pool
            for mutation in mutations:
                self._hypotheses[mutation.id] = mutation
                logger.info(f"Created mutation: {mutation.statement}")
    
    def crossover(self, h1: Hypothesis, h2: Hypothesis) -> Hypothesis:
        """
        Combine two hypotheses into a new one.
        
        This is a simple implementation - more sophisticated
        crossover could analyze the structure of the statements.
        """
        # Simple: combine parts of both statements
        words1 = h1.statement.split()
        words2 = h2.statement.split()
        
        mid = len(words1) // 2
        new_words = words1[:mid] + words2[mid:]
        
        return Hypothesis(
            statement=" ".join(new_words),
            category=h1.category,
            confidence=0.5,
            initial_confidence=0.5,
            source_agent=f"crossover({h1.source_agent}, {h2.source_agent})",
            parent_hypothesis=h1.id,
            generation=max(h1.generation, h2.generation) + 1,
        )
    
    def to_dict(self) -> Dict[str, dict]:
        """Export all hypotheses."""
        return {
            str(h.id): h.to_dict()
            for h in self._hypotheses.values()
        }
    
    def __len__(self) -> int:
        return len(self._hypotheses)

