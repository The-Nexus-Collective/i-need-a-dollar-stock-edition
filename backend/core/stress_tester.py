"""
Stress Test Engine - Historical crash scenario simulation

Tests the trading strategy against historical crash scenarios:
- Flash crashes (10%, 20%, 30% drops)
- Volatility spikes
- Extended drawdown periods

Helps validate that the strategy would survive extreme market conditions
before going live.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text

from models import AsyncSessionLocal
from .account import AccountPosition, check_simulated_liquidation

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# STRESS SCENARIOS - Historical and synthetic crash events
# ═══════════════════════════════════════════════════════════════════════════════

STRESS_SCENARIOS = {
    "flash_crash_10": {
        "name": "10% Flash Crash",
        "description": "Sudden 10% price drop in 5 minutes",
        "price_drop": 0.10,
        "duration_minutes": 5,
        "recovery_minutes": 30,
        "volatility_multiplier": 2.0,
    },
    "flash_crash_20": {
        "name": "20% Flash Crash",
        "description": "Severe 20% price drop in 15 minutes (like May 2021)",
        "price_drop": 0.20,
        "duration_minutes": 15,
        "recovery_minutes": 120,
        "volatility_multiplier": 3.0,
    },
    "flash_crash_30": {
        "name": "30% Black Swan Crash",
        "description": "Extreme 30% price drop in 60 minutes (like March 2020)",
        "price_drop": 0.30,
        "duration_minutes": 60,
        "recovery_minutes": 480,
        "volatility_multiplier": 5.0,
    },
    "volatility_spike": {
        "name": "Volatility Spike",
        "description": "3x normal volatility for 24 hours",
        "price_drop": 0.05,
        "duration_minutes": 1440,
        "recovery_minutes": 2880,
        "volatility_multiplier": 3.0,
    },
    "slow_bleed": {
        "name": "Slow Bleed Drawdown",
        "description": "Gradual 25% decline over a week",
        "price_drop": 0.25,
        "duration_minutes": 10080,  # 7 days
        "recovery_minutes": 20160,
        "volatility_multiplier": 1.5,
    },
    "leverage_cascade": {
        "name": "Leverage Cascade",
        "description": "Cascading liquidations causing 40% drop",
        "price_drop": 0.40,
        "duration_minutes": 30,
        "recovery_minutes": 240,
        "volatility_multiplier": 6.0,
    },
}


@dataclass
class StressTestResult:
    """Result of a stress test simulation"""
    scenario: str
    scenario_name: str
    run_at: datetime
    
    # Initial state
    initial_equity: float
    positions_tested: int
    
    # Results
    final_equity: float
    max_drawdown: float
    would_survive: bool
    positions_liquidated: int
    
    # Details
    liquidated_positions: List[str]
    pnl_breakdown: Dict[str, float]
    notes: str
    
    @property
    def equity_change_pct(self) -> float:
        if self.initial_equity == 0:
            return 0
        return ((self.final_equity - self.initial_equity) / self.initial_equity) * 100
    
    def to_dict(self) -> dict:
        return {
            "scenario": self.scenario,
            "scenario_name": self.scenario_name,
            "run_at": self.run_at.isoformat(),
            "initial_equity": self.initial_equity,
            "positions_tested": self.positions_tested,
            "final_equity": self.final_equity,
            "max_drawdown": self.max_drawdown,
            "would_survive": self.would_survive,
            "positions_liquidated": self.positions_liquidated,
            "liquidated_positions": self.liquidated_positions,
            "equity_change_pct": self.equity_change_pct,
            "notes": self.notes,
        }


class StressTester:
    """
    Runs stress test simulations against current positions.
    
    Tests each scenario by:
    1. Taking a snapshot of current positions
    2. Applying the stress scenario price changes
    3. Checking for liquidations
    4. Calculating final equity and drawdown
    5. Logging results to database
    """
    
    async def get_current_positions(self) -> List[Dict]:
        """Get all open positions from database"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT id, coin, side, quantity, entry_price, 
                           current_price, leverage, stop_loss, take_profit
                    FROM positions
                    WHERE status = 'open'
                """)
            )
            
            positions = []
            for row in result.fetchall():
                positions.append({
                    "id": str(row[0]),
                    "coin": row[1],
                    "side": row[2],
                    "quantity": float(row[3]),
                    "entry_price": float(row[4]),
                    "current_price": float(row[5] or row[4]),
                    "leverage": float(row[6] or 1.0),
                    "stop_loss": float(row[7]) if row[7] else None,
                    "take_profit": float(row[8]) if row[8] else None,
                })
            
            return positions
    
    async def get_current_equity(self) -> float:
        """Get current portfolio equity"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT balance_usdt FROM account_state 
                    WHERE account_id = 'paper_main'
                    LIMIT 1
                """)
            )
            row = result.fetchone()
            return float(row[0]) if row else 108000.0
    
    def simulate_scenario(
        self,
        positions: List[Dict],
        equity: float,
        scenario: dict
    ) -> StressTestResult:
        """
        Simulate a stress scenario against positions.
        
        Args:
            positions: List of position dicts
            equity: Current portfolio equity
            scenario: Scenario parameters dict
        
        Returns:
            StressTestResult with simulation results
        """
        price_drop = scenario["price_drop"]
        scenario_key = scenario.get("key", "unknown")
        scenario_name = scenario["name"]
        
        initial_equity = equity
        liquidated = []
        pnl_breakdown = {}
        total_pnl = 0
        
        for pos in positions:
            # Calculate stressed price
            current_price = pos["current_price"]
            stressed_price = current_price * (1 - price_drop)
            
            # Create AccountPosition for liquidation check
            account_pos = AccountPosition(
                coin=pos["coin"],
                side=pos["side"],
                quantity=pos["quantity"],
                entry_price=pos["entry_price"],
                current_price=current_price,
                leverage=pos["leverage"],
                position_id=pos["id"]
            )
            
            # Check for liquidation
            would_liq, price_change, _ = check_simulated_liquidation(
                account_pos, stressed_price
            )
            
            # Calculate PnL
            if pos["side"] == "long":
                pnl = (stressed_price - pos["entry_price"]) * pos["quantity"]
            else:
                pnl = (pos["entry_price"] - stressed_price) * pos["quantity"]
            
            # If liquidated, PnL is capped at margin loss
            if would_liq:
                margin = (pos["quantity"] * pos["entry_price"]) / pos["leverage"]
                pnl = -margin * 0.95  # Lose ~95% of margin on liquidation
                liquidated.append(pos["coin"])
                logger.warning(
                    f"STRESS TEST: {pos['coin']} would be LIQUIDATED "
                    f"at ${stressed_price:.2f} ({price_drop*100:.0f}% drop, {pos['leverage']}x)"
                )
            
            pnl_breakdown[pos["coin"]] = pnl
            total_pnl += pnl
        
        final_equity = initial_equity + total_pnl
        max_drawdown = (initial_equity - final_equity) / initial_equity if initial_equity > 0 else 0
        
        # Strategy survives if no liquidations and drawdown < 30%
        would_survive = len(liquidated) == 0 and max_drawdown < 0.30
        
        # Generate notes
        if len(liquidated) > 0:
            notes = f"FAILED: {len(liquidated)} position(s) would be liquidated: {', '.join(liquidated)}"
        elif max_drawdown > 0.20:
            notes = f"WARNING: High drawdown ({max_drawdown*100:.1f}%) but no liquidations"
        else:
            notes = f"PASSED: Would survive with {max_drawdown*100:.1f}% drawdown"
        
        return StressTestResult(
            scenario=scenario_key,
            scenario_name=scenario_name,
            run_at=datetime.utcnow(),
            initial_equity=initial_equity,
            positions_tested=len(positions),
            final_equity=final_equity,
            max_drawdown=max_drawdown,
            would_survive=would_survive,
            positions_liquidated=len(liquidated),
            liquidated_positions=liquidated,
            pnl_breakdown=pnl_breakdown,
            notes=notes
        )
    
    async def run_stress_test(
        self,
        scenario_key: str
    ) -> StressTestResult:
        """
        Run a specific stress test scenario.
        
        Args:
            scenario_key: Key from STRESS_SCENARIOS
        
        Returns:
            StressTestResult
        """
        if scenario_key not in STRESS_SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario_key}")
        
        scenario = STRESS_SCENARIOS[scenario_key].copy()
        scenario["key"] = scenario_key
        
        positions = await self.get_current_positions()
        equity = await self.get_current_equity()
        
        if not positions:
            logger.info("No open positions to stress test")
            return StressTestResult(
                scenario=scenario_key,
                scenario_name=scenario["name"],
                run_at=datetime.utcnow(),
                initial_equity=equity,
                positions_tested=0,
                final_equity=equity,
                max_drawdown=0,
                would_survive=True,
                positions_liquidated=0,
                liquidated_positions=[],
                pnl_breakdown={},
                notes="No open positions to test"
            )
        
        logger.info(
            f"Running stress test: {scenario['name']} on {len(positions)} positions"
        )
        
        result = self.simulate_scenario(positions, equity, scenario)
        
        # Log result to database
        await self._log_result(result, scenario)
        
        return result
    
    async def run_all_scenarios(self) -> List[StressTestResult]:
        """Run all stress test scenarios"""
        results = []
        
        for scenario_key in STRESS_SCENARIOS:
            try:
                result = await self.run_stress_test(scenario_key)
                results.append(result)
            except Exception as e:
                logger.error(f"Stress test {scenario_key} failed: {e}")
        
        # Summary
        passed = sum(1 for r in results if r.would_survive)
        failed = len(results) - passed
        
        logger.info(
            f"Stress test complete: {passed}/{len(results)} scenarios passed, "
            f"{failed} failed"
        )
        
        return results
    
    async def _log_result(self, result: StressTestResult, scenario: dict):
        """Log stress test result to database"""
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO stress_tests 
                        (scenario, scenario_params, initial_equity, final_equity,
                         max_drawdown, would_survive, positions_liquidated,
                         positions_tested, notes)
                    VALUES 
                        (:scenario, :params, :initial, :final, :drawdown,
                         :survive, :liquidated, :positions, :notes)
                """),
                {
                    "scenario": result.scenario,
                    "params": scenario,
                    "initial": result.initial_equity,
                    "final": result.final_equity,
                    "drawdown": result.max_drawdown,
                    "survive": result.would_survive,
                    "liquidated": result.positions_liquidated,
                    "positions": {"breakdown": result.pnl_breakdown},
                    "notes": result.notes
                }
            )
            await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

_stress_tester: Optional[StressTester] = None


def get_stress_tester() -> StressTester:
    """Get or create global stress tester"""
    global _stress_tester
    if _stress_tester is None:
        _stress_tester = StressTester()
    return _stress_tester


async def run_stress_test(scenario: str = "flash_crash_20") -> StressTestResult:
    """Convenience function to run a stress test"""
    tester = get_stress_tester()
    return await tester.run_stress_test(scenario)


async def run_all_stress_tests() -> List[StressTestResult]:
    """Convenience function to run all stress tests"""
    tester = get_stress_tester()
    return await tester.run_all_scenarios()

