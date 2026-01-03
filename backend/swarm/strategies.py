"""
Strategy Genes - Evolutionary Trading Strategies

Strategies are genes that can mutate and reproduce.
Successful strategies reproduce; failures are discarded.

This implements a genetic algorithm for strategy evolution.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass
class StrategyGene:
    """
    A trading strategy represented as a gene.
    
    Strategies have:
    - Parameters that can mutate
    - Fitness scores based on performance
    - Lineage tracking
    """
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Identity
    name: str = ""
    description: str = ""
    
    # Parameters (the "DNA")
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Performance
    fitness: float = 0.0  # Overall fitness score
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    
    @property
    def win_rate(self) -> float:
        if self.trades_count == 0:
            return 0.5
        return self.wins / self.trades_count
    
    @property
    def avg_pnl(self) -> float:
        if self.trades_count == 0:
            return 0.0
        return self.total_pnl / self.trades_count
    
    # Lineage
    generation: int = 0
    parents: List[UUID] = field(default_factory=list)
    
    # Flags
    is_active: bool = True
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "fitness": self.fitness,
            "trades_count": self.trades_count,
            "win_rate": self.win_rate,
            "total_pnl": self.total_pnl,
            "generation": self.generation,
            "is_active": self.is_active,
        }
    
    def record_trade(self, pnl: float):
        """Record a trade outcome."""
        self.trades_count += 1
        self.total_pnl += pnl
        
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        
        # Update fitness
        self._update_fitness()
    
    def _update_fitness(self):
        """Update fitness score based on performance."""
        # Fitness = combination of win rate, avg pnl, and trade count
        if self.trades_count < 3:
            self.fitness = 0.5  # Neutral until enough trades
            return
        
        # Components
        win_rate_score = self.win_rate
        pnl_score = min(1.0, max(0.0, (self.avg_pnl + 5) / 10))  # Normalize -5 to +5 -> 0 to 1
        volume_score = min(1.0, self.trades_count / 100)  # More trades = more confidence
        
        # Weighted average
        self.fitness = (
            win_rate_score * 0.4 +
            pnl_score * 0.4 +
            volume_score * 0.2
        )
    
    def mutate(self, mutation_rate: float = 0.2) -> "StrategyGene":
        """
        Create a mutated copy of this strategy.
        
        Each parameter has a chance to mutate slightly.
        """
        new_params = {}
        
        for key, value in self.parameters.items():
            if random.random() < mutation_rate:
                # Mutate this parameter
                new_params[key] = self._mutate_value(value)
            else:
                new_params[key] = value
        
        return StrategyGene(
            name=f"{self.name}_m{self.generation + 1}",
            description=f"Mutation of {self.name}",
            parameters=new_params,
            generation=self.generation + 1,
            parents=[self.id],
        )
    
    def _mutate_value(self, value: Any) -> Any:
        """Mutate a single parameter value."""
        if isinstance(value, float):
            # Add gaussian noise
            return value * (1 + random.gauss(0, 0.1))
        elif isinstance(value, int):
            # Add/subtract small amount
            return value + random.randint(-1, 1)
        elif isinstance(value, bool):
            # Flip with some probability
            return not value if random.random() < 0.3 else value
        elif isinstance(value, str):
            # Keep string parameters
            return value
        else:
            return value
    
    def crossover(self, other: "StrategyGene") -> "StrategyGene":
        """
        Create offspring by combining parameters from two parents.
        """
        new_params = {}
        
        all_keys = set(self.parameters.keys()) | set(other.parameters.keys())
        
        for key in all_keys:
            if key in self.parameters and key in other.parameters:
                # Both parents have this param - pick randomly
                new_params[key] = random.choice([
                    self.parameters[key],
                    other.parameters[key]
                ])
            elif key in self.parameters:
                new_params[key] = self.parameters[key]
            else:
                new_params[key] = other.parameters[key]
        
        return StrategyGene(
            name=f"cross_{self.name[:10]}_{other.name[:10]}",
            description=f"Crossover of {self.name} and {other.name}",
            parameters=new_params,
            generation=max(self.generation, other.generation) + 1,
            parents=[self.id, other.id],
        )


class StrategyEvolution:
    """
    Genetic algorithm for strategy evolution.
    
    Manages a population of strategies:
    - Evaluates fitness
    - Selects best performers
    - Reproduces with mutation
    - Replaces worst performers
    """
    
    POPULATION_SIZE = 20
    ELITE_SIZE = 5  # Top strategies that always survive
    MUTATION_RATE = 0.2
    CROSSOVER_RATE = 0.3
    
    def __init__(self):
        self.population: List[StrategyGene] = []
        self._lock = asyncio.Lock()
        self._generation = 0
    
    async def initialize_population(self, seed_strategies: List[Dict] = None):
        """Initialize population with seed strategies."""
        async with self._lock:
            if seed_strategies:
                for seed in seed_strategies:
                    self.population.append(StrategyGene(
                        name=seed.get("name", f"strategy_{len(self.population)}"),
                        description=seed.get("description", ""),
                        parameters=seed.get("parameters", {}),
                    ))
            
            # Fill remaining with random variations
            while len(self.population) < self.POPULATION_SIZE:
                base = random.choice(self.population) if self.population else None
                if base:
                    self.population.append(base.mutate(0.5))
                else:
                    self.population.append(StrategyGene(
                        name=f"random_{len(self.population)}",
                        parameters=self._generate_random_params(),
                    ))
    
    def _generate_random_params(self) -> Dict:
        """Generate random strategy parameters."""
        return {
            "entry_threshold": random.uniform(0.5, 0.9),
            "exit_threshold": random.uniform(0.3, 0.7),
            "stop_loss_pct": random.uniform(0.02, 0.10),
            "take_profit_pct": random.uniform(0.05, 0.20),
            "position_size_pct": random.uniform(0.05, 0.20),
            "use_momentum": random.choice([True, False]),
            "use_sentiment": random.choice([True, False]),
            "use_volume": random.choice([True, False]),
            "timeframe_hours": random.choice([1, 4, 24, 168]),
        }
    
    async def evolve(self):
        """
        Run one generation of evolution.
        
        1. Evaluate fitness (already done via trade recording)
        2. Select parents (best performers)
        3. Reproduce (crossover + mutation)
        4. Replace worst performers
        """
        async with self._lock:
            if len(self.population) < 2:
                return
            
            self._generation += 1
            
            # Sort by fitness
            self.population.sort(key=lambda s: s.fitness, reverse=True)
            
            # Elite always survive
            elite = self.population[:self.ELITE_SIZE]
            
            # Create offspring
            offspring = []
            
            # Crossover
            if random.random() < self.CROSSOVER_RATE and len(elite) >= 2:
                parent1, parent2 = random.sample(elite, 2)
                offspring.append(parent1.crossover(parent2))
            
            # Mutation from elite
            for _ in range(self.POPULATION_SIZE - len(elite) - len(offspring)):
                parent = random.choice(elite)
                offspring.append(parent.mutate(self.MUTATION_RATE))
            
            # Replace worst performers
            self.population = elite + offspring
            
            logger.info(
                f"Evolution generation {self._generation}: "
                f"Best fitness = {elite[0].fitness:.3f}, "
                f"Population = {len(self.population)}"
            )
    
    def get_best(self, n: int = 5) -> List[StrategyGene]:
        """Get top n strategies by fitness."""
        sorted_pop = sorted(self.population, key=lambda s: s.fitness, reverse=True)
        return sorted_pop[:n]
    
    def get_active(self) -> List[StrategyGene]:
        """Get all active strategies."""
        return [s for s in self.population if s.is_active]
    
    def get_strategy(self, strategy_id: UUID) -> Optional[StrategyGene]:
        """Get strategy by ID."""
        for s in self.population:
            if s.id == strategy_id:
                return s
        return None
    
    def record_trade(self, strategy_id: UUID, pnl: float):
        """Record a trade for a strategy."""
        for s in self.population:
            if s.id == strategy_id:
                s.record_trade(pnl)
                return
    
    def to_dict(self) -> Dict:
        """Export evolution state."""
        return {
            "generation": self._generation,
            "population_size": len(self.population),
            "strategies": [s.to_dict() for s in self.population],
        }

