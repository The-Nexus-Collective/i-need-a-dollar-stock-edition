"""
Orchestrator Agent - The Central Brain.

Coordinates all specialized agents in the 15-minute trading cycle:
1. Discovery → Find new opportunities
2. Validation → Verify assets meet criteria
3. Sentiment → Analyze market sentiment
4. Strategy Ensemble → Propose trades
5. Execution → Execute trades
6. Learner → Reflect and improve

The Orchestrator is Grok-powered and makes final decisions.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID, uuid4

import pytz

from .base import GrokAgent, AgentContext, AgentOutput
from .logbook import get_logbook, init_logbook
from .discovery import DiscoveryAgent
from .validation import ValidationAgent
from .sentiment import SentimentAgent
from .strategy_ensemble import StrategyEnsemble
from .execution import ExecutionAgent
from .learner import LearnerAgent

logger = logging.getLogger(__name__)

# Timezone
CET = pytz.timezone('CET')


@dataclass
class CycleResult:
    """Result of a complete trading cycle."""
    cycle_id: UUID
    timestamp: datetime
    duration_ms: int
    
    # Agent results
    discoveries: int
    validated_coins: int
    sentiments_analyzed: int
    trades_proposed: int
    trades_executed: int
    reflections: int
    
    # Portfolio state
    equity_before: float
    equity_after: float
    pnl_cycle: float
    
    # Status
    success: bool
    errors: List[str]
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": str(self.cycle_id),
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "discoveries": self.discoveries,
            "validated_coins": self.validated_coins,
            "sentiments_analyzed": self.sentiments_analyzed,
            "trades_proposed": self.trades_proposed,
            "trades_executed": self.trades_executed,
            "reflections": self.reflections,
            "equity_before": self.equity_before,
            "equity_after": self.equity_after,
            "pnl_cycle": self.pnl_cycle,
            "success": self.success,
            "errors": self.errors,
        }


class Orchestrator(GrokAgent):
    """
    The Central Brain - coordinates all agents.
    
    Responsibilities:
    - Run the 15-minute trading cycle
    - Coordinate agent execution order
    - Make final trading decisions
    - Handle errors and recovery
    - Manage the flatten time (23:55 CET)
    """
    
    CYCLE_MINUTES = int(os.getenv('CYCLE_MINUTES', '15'))
    FLATTEN_TIME_CET = os.getenv('FLATTEN_TIME_CET', '23:55')
    
    def __init__(self):
        super().__init__("orchestrator")
        
        # Initialize agents
        self.discovery = DiscoveryAgent()
        self.validation = ValidationAgent()
        self.sentiment = SentimentAgent()
        self.strategy = StrategyEnsemble()
        self.execution = ExecutionAgent()
        self.learner = LearnerAgent()
        
        self._running = False
        self._last_cycle: Optional[datetime] = None
        self._cycle_count = 0
    
    async def initialize(self):
        """Initialize all agents."""
        logger.info("Initializing Orchestrator and all agents...")
        
        # Initialize logbook
        await init_logbook()
        
        # Initialize each agent
        await self.discovery.initialize()
        await self.validation.initialize()
        await self.sentiment.initialize()
        await self.strategy.initialize()
        await self.execution.initialize()
        await self.learner.initialize()
        
        await super().initialize()
        
        logger.info("All agents initialized successfully")
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Decide what to do this cycle."""
        # Check flatten time
        if self._is_flatten_time():
            return AgentOutput(
                success=True,
                data={"action": "flatten"},
                reasoning="23:55 CET - Time to flatten all positions",
                decision="flatten_all",
                confidence=100,
            )
        
        # Normal trading cycle
        return AgentOutput(
            success=True,
            data={"action": "trade"},
            reasoning=f"Starting cycle #{self._cycle_count + 1}",
            decision="run_full_cycle",
            confidence=95,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Execute the trading cycle."""
        action = thought.data.get("action", "trade")
        
        if action == "flatten":
            result = await self._flatten_all(context)
        else:
            result = await self._run_trading_cycle(context)
        
        return AgentOutput(
            success=result.success,
            data=result.to_dict(),
            reasoning=f"Cycle completed. Trades: {result.trades_executed}, PnL: ${result.pnl_cycle:+.2f}",
            decision="cycle_complete",
            confidence=90,
        )
    
    async def run(self):
        """Main run loop - executes every CYCLE_MINUTES."""
        self._running = True
        
        logger.info("=" * 60)
        logger.info("AGENTIC TRADING SYSTEM STARTING")
        logger.info(f"Cycle interval: {self.CYCLE_MINUTES} minutes")
        logger.info(f"Flatten time: {self.FLATTEN_TIME_CET} CET")
        logger.info("=" * 60)
        
        # Initialize all agents
        await self.initialize()
        
        # Get initial portfolio state
        portfolio = await self._get_portfolio()
        
        # Log startup
        await self.logbook.log(
            agent_name=self.name,
            action_type="startup",
            reasoning=f"Agentic Trading System started. Equity: ${portfolio.get('total_equity', 0):,.2f}",
            decision="ready_to_trade",
            confidence=100,
        )
        
        # Run initial cycle
        await self._execute_cycle()
        
        # Main loop
        cycle_interval = timedelta(minutes=self.CYCLE_MINUTES)
        
        while self._running:
            try:
                now = datetime.utcnow()
                
                # Check if it's time for next cycle
                if self._last_cycle and now - self._last_cycle < cycle_interval:
                    time_until_next = cycle_interval - (now - self._last_cycle)
                    logger.debug(f"Waiting for next cycle... {time_until_next.seconds}s remaining")
                    await asyncio.sleep(10)
                    continue
                
                logger.info(f"Starting cycle #{self._cycle_count + 1}")
                # Run cycle
                await self._execute_cycle()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                await self.logbook.log(
                    agent_name=self.name,
                    action_type="error",
                    reasoning=f"Cycle failed: {str(e)}",
                    confidence=0,
                )
                await asyncio.sleep(60)
        
        await self.shutdown()
    
    async def _execute_cycle(self):
        """Execute a single trading cycle."""
        import time
        
        start_time = time.time()
        self._cycle_count += 1
        
        # Start new cycle in logbook
        cycle_id = self.logbook.new_cycle()
        
        # Create context
        context = AgentContext(cycle_id=cycle_id)
        context.portfolio = await self._get_portfolio()
        context.open_positions = await self._get_open_positions()
        
        # Log cycle start
        await self.logbook.log(
            agent_name=self.name,
            action_type="cycle_start",
            reasoning=f"Starting cycle #{self._cycle_count}",
            input_context=context.to_dict(),
            decision=f"cycle_{self._cycle_count}",
            confidence=100,
        )
        
        # Run the cycle
        result = await self._run_trading_cycle(context)
        
        self._last_cycle = datetime.utcnow()
        
        duration = int((time.time() - start_time) * 1000)
        
        # Log cycle completion
        summary = (
            f"Cycle complete: {result.discoveries} discoveries, "
            f"{result.trades_executed}/{result.trades_proposed} trades, "
            f"PnL: ${result.pnl_cycle:+,.2f}"
        )
        await self.logbook.log(
            agent_name=self.name,
            action_type="cycle_complete",
            reasoning=summary,
            output_data=result.to_dict(),
            duration_ms=duration,
            confidence=100 if result.success else 50,
        )
        
        logger.info(f"Cycle #{self._cycle_count} completed in {duration}ms - {summary}")
    
    async def _run_trading_cycle(self, context: AgentContext) -> CycleResult:
        """Run the full trading cycle through all agents."""
        import time
        
        start_time = time.time()
        errors = []
        
        equity_before = context.portfolio.get("total_equity", 100000)
        
        # ═══════════════════════════════════════════════════════════════
        # 1. DISCOVERY - Find new opportunities
        # ═══════════════════════════════════════════════════════════════
        try:
            await self.logbook.log(
                agent_name=self.name,
                action_type="dispatch",
                reasoning="Dispatching Discovery Agent",
                decision="run_discovery",
            )
            
            discovery_result = await self.discovery.run(context)
            discoveries = len(discovery_result.data.get("new_candidates", []))
            
        except Exception as e:
            errors.append(f"Discovery: {str(e)}")
            discoveries = 0
        
        # ═══════════════════════════════════════════════════════════════
        # 2. VALIDATION - Validate discovered assets
        # ═══════════════════════════════════════════════════════════════
        try:
            await self.logbook.log(
                agent_name=self.name,
                action_type="dispatch",
                reasoning="Dispatching Validation Agent",
                decision="run_validation",
            )
            
            validation_result = await self.validation.run(context)
            validated = len(context.validated_coins)
            
        except Exception as e:
            errors.append(f"Validation: {str(e)}")
            validated = 0
        
        # ═══════════════════════════════════════════════════════════════
        # 3. SENTIMENT - Analyze market sentiment
        # ═══════════════════════════════════════════════════════════════
        try:
            await self.logbook.log(
                agent_name=self.name,
                action_type="dispatch",
                reasoning="Dispatching Sentiment Agent",
                decision="run_sentiment",
            )
            
            sentiment_result = await self.sentiment.run(context)
            sentiments = len(context.sentiments)
            
        except Exception as e:
            errors.append(f"Sentiment: {str(e)}")
            sentiments = 0
        
        # ═══════════════════════════════════════════════════════════════
        # 4. STRATEGY - Generate trade proposals
        # ═══════════════════════════════════════════════════════════════
        try:
            await self.logbook.log(
                agent_name=self.name,
                action_type="dispatch",
                reasoning="Dispatching Strategy Ensemble",
                decision="run_strategy",
            )
            
            strategy_result = await self.strategy.run(context)
            proposals = len(context.trade_proposals)
            
        except Exception as e:
            errors.append(f"Strategy: {str(e)}")
            proposals = 0
        
        # ═══════════════════════════════════════════════════════════════
        # 5. ORCHESTRATOR DECISION - Final approval
        # ═══════════════════════════════════════════════════════════════
        if proposals > 0:
            # Use Grok to make final decision
            decision = await self._make_final_decision(context)
            
            if not decision.get("approved", False):
                proposals = 0
                await self.logbook.log(
                    agent_name=self.name,
                    action_type="veto",
                    reasoning=decision.get("reason", "Trade proposals rejected"),
                    decision="no_trade",
                    confidence=decision.get("confidence", 50),
                )
        
        # ═══════════════════════════════════════════════════════════════
        # 6. EXECUTION - Execute approved trades
        # ═══════════════════════════════════════════════════════════════
        executed = 0
        if proposals > 0:
            try:
                await self.logbook.log(
                    agent_name=self.name,
                    action_type="dispatch",
                    reasoning="Dispatching Execution Agent",
                    decision="run_execution",
                )
                
                execution_result = await self.execution.run(context)
                executed = len(context.executed_trades)
                
            except Exception as e:
                errors.append(f"Execution: {str(e)}")
        
        # ═══════════════════════════════════════════════════════════════
        # 7. LEARNER - Reflect and learn
        # ═══════════════════════════════════════════════════════════════
        reflections = 0
        try:
            await self.logbook.log(
                agent_name=self.name,
                action_type="dispatch",
                reasoning="Dispatching Learner Agent",
                decision="run_learner",
            )
            
            learner_result = await self.learner.run(context)
            reflections = len(learner_result.data.get("reflections", []))
            
        except Exception as e:
            errors.append(f"Learner: {str(e)}")
        
        # Get final portfolio state
        portfolio_after = await self._get_portfolio()
        equity_after = portfolio_after.get("total_equity", equity_before)
        pnl = equity_after - equity_before
        
        duration = int((time.time() - start_time) * 1000)
        
        return CycleResult(
            cycle_id=context.cycle_id,
            timestamp=datetime.utcnow(),
            duration_ms=duration,
            discoveries=discoveries,
            validated_coins=validated,
            sentiments_analyzed=sentiments,
            trades_proposed=proposals,
            trades_executed=executed,
            reflections=reflections,
            equity_before=equity_before,
            equity_after=equity_after,
            pnl_cycle=pnl,
            success=len(errors) == 0,
            errors=errors,
        )
    
    async def _make_final_decision(self, context: AgentContext) -> Dict:
        """Use Grok to make final trading decision."""
        proposals = context.trade_proposals
        regime = context.market_regime
        
        # Build summary for Grok
        proposal_summary = []
        for p in proposals[:5]:
            proposal_summary.append(
                f"- {p.get('side', 'long').upper()} {p.get('coin')}: "
                f"confidence {p.get('confidence', 0):.0f}%, "
                f"size {p.get('size_percent', 0):.1f}%, "
                f"strategy: {p.get('strategy')}"
            )
        
        prompt = f"""Review these trade proposals and decide whether to approve:

Market Regime: {regime}
Open Positions: {len(context.open_positions)}
Current Deployment: {sum(p.get('size_percent', 0) for p in proposals):.1f}%

Proposals:
{chr(10).join(proposal_summary)}

Should these trades be executed? Consider:
1. Market regime appropriateness
2. Risk concentration
3. Strategy diversity
4. Overall conviction

Answer with: APPROVED or REJECTED followed by one-sentence reason."""

        response, tokens = await self.call_grok(prompt, temperature=0.2)
        
        approved = "APPROVED" in response.upper()
        reason = response.split('\n')[0] if response else "No response"
        
        return {
            "approved": approved,
            "reason": reason,
            "confidence": 80 if approved else 60,
            "tokens_used": tokens,
        }
    
    async def _flatten_all(self, context: AgentContext) -> CycleResult:
        """Close all positions for end-of-day."""
        await self.logbook.log(
            agent_name=self.name,
            action_type="flatten",
            reasoning="23:55 CET - Closing all positions",
            decision="close_all",
            confidence=100,
        )
        
        equity_before = context.portfolio.get("total_equity", 100000)
        closed = 0
        
        for position in context.open_positions:
            coin = position.get("coin")
            result = await self.execution.close_position(coin, "end_of_day")
            if result:
                closed += 1
        
        portfolio_after = await self._get_portfolio()
        equity_after = portfolio_after.get("total_equity", equity_before)
        
        return CycleResult(
            cycle_id=context.cycle_id,
            timestamp=datetime.utcnow(),
            duration_ms=0,
            discoveries=0,
            validated_coins=0,
            sentiments_analyzed=0,
            trades_proposed=0,
            trades_executed=closed,
            reflections=0,
            equity_before=equity_before,
            equity_after=equity_after,
            pnl_cycle=equity_after - equity_before,
            success=True,
            errors=[],
        )
    
    def _is_flatten_time(self) -> bool:
        """Check if it's 23:55 CET."""
        now_cet = datetime.now(CET)
        hour, minute = map(int, self.FLATTEN_TIME_CET.split(':'))
        return now_cet.hour == hour and now_cet.minute >= minute
    
    async def _get_portfolio(self) -> Dict:
        """Get current portfolio state."""
        from models import AsyncSessionLocal
        from sqlalchemy import text
        
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT * FROM account_state 
                    WHERE account_id = 'paper_main'
                """))
                row = result.fetchone()
                
                if row:
                    return {
                        "total_equity": float(row.balance_usdt),
                        "initial_balance": float(row.initial_balance),
                        "realized_pnl": float(row.realized_pnl or 0),
                        "total_trades": int(row.total_trades or 0),
                    }
        except Exception as e:
            logger.warning(f"Failed to get portfolio: {e}")
        
        return {"total_equity": 100000, "initial_balance": 100000}
    
    async def _get_open_positions(self) -> List[Dict]:
        """Get open positions."""
        from models import AsyncSessionLocal
        from sqlalchemy import text
        
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT coin, side, quantity, entry_price, current_price,
                           stop_loss, take_profit, leverage
                    FROM positions
                    WHERE status = 'open'
                """))
                
                return [
                    {
                        "coin": row.coin,
                        "side": row.side,
                        "quantity": float(row.quantity),
                        "entry_price": float(row.entry_price),
                        "current_price": float(row.current_price or row.entry_price),
                    }
                    for row in result.fetchall()
                ]
        except Exception as e:
            logger.warning(f"Failed to get positions: {e}")
        
        return []
    
    async def shutdown(self):
        """Shutdown all agents gracefully."""
        logger.info("Shutting down Orchestrator...")
        
        self._running = False
        
        # Shutdown agents
        await self.discovery.shutdown() if hasattr(self.discovery, 'shutdown') else None
        await self.sentiment.shutdown() if hasattr(self.sentiment, 'shutdown') else None
        await self.strategy.shutdown() if hasattr(self.strategy, 'shutdown') else None
        
        # Stop logbook
        logbook = get_logbook()
        await logbook.stop()
        
        logger.info("Orchestrator shutdown complete")
    
    async def stop(self):
        """Stop the orchestrator."""
        self._running = False


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

async def run_agentic_system():
    """Main entry point for the agentic trading system."""
    orchestrator = Orchestrator()
    
    try:
        await orchestrator.run()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
        await orchestrator.stop()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(run_agentic_system())

