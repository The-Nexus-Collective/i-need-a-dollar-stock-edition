"""
Learner Agent - Self-improvement through reflection and memory.

Responsibilities:
1. Post-trade reflection (What worked? What failed?)
2. Strategy variant generation
3. Memory storage and retrieval
4. Performance tracking
5. Meta-learning updates

This agent enables the system to learn and improve over time.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import text

from .base import GrokAgent, AgentContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class TradeReflection:
    """Reflection on a completed trade."""
    trade_id: str
    coin: str
    strategy: str
    
    # Outcome
    side: str
    pnl: float
    pnl_percent: float
    hold_duration_mins: int
    
    # Analysis
    what_worked: str
    what_failed: str
    lessons_learned: List[str]
    
    # Scores
    execution_quality: float  # 0-100
    timing_quality: float
    sizing_quality: float
    
    # New variants
    strategy_variants: List[Dict]
    
    def to_dict(self) -> Dict:
        return {
            "trade_id": self.trade_id,
            "coin": self.coin,
            "strategy": self.strategy,
            "side": self.side,
            "pnl": self.pnl,
            "pnl_percent": self.pnl_percent,
            "hold_duration_mins": self.hold_duration_mins,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "lessons_learned": self.lessons_learned,
            "execution_quality": self.execution_quality,
            "timing_quality": self.timing_quality,
            "sizing_quality": self.sizing_quality,
            "strategy_variants": self.strategy_variants,
        }


@dataclass
class Memory:
    """A memory to store for future recall."""
    title: str
    content: str
    category: str  # 'trade_outcome', 'market_regime', 'strategy_insight'
    memory_type: str  # 'short', 'medium', 'long'
    importance: float  # 0-100
    related_coins: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "memory_type": self.memory_type,
            "importance": self.importance,
            "related_coins": self.related_coins,
        }


@dataclass
class LearnerOutput:
    """Output from Learner Agent."""
    reflections: List[TradeReflection]
    memories_created: List[Memory]
    memories_recalled: List[Dict]
    strategy_updates: Dict[str, float]
    insights: str
    
    def to_dict(self) -> Dict:
        return {
            "reflections": [r.to_dict() for r in self.reflections],
            "memories_created": [m.to_dict() for m in self.memories_created],
            "memories_recalled": self.memories_recalled,
            "strategy_updates": self.strategy_updates,
            "insights": self.insights,
        }


class LearnerAgent(GrokAgent):
    """
    Learns from trading experience and improves strategies.
    
    Memory Types:
    - Short-term: Last 24 hours (recent trades, signals)
    - Medium-term: Last 7 days (patterns, regimes)
    - Long-term: Persistent (major learnings, strategy archetypes)
    
    Learning Methods:
    - Post-trade reflection via Grok
    - Strategy weight adjustments
    - Pattern recognition via embeddings
    """
    
    REFLECTION_PROMPT = """Analyze this trade and provide insights:

Trade Details:
- Coin: {coin}
- Strategy: {strategy}
- Side: {side}
- PnL: {pnl:+.2f} ({pnl_pct:+.2f}%)
- Hold Duration: {duration} minutes
- Entry: ${entry:.4f}
- Exit: ${exit:.4f}
- Market Regime: {regime}

Provide:
1. What worked well (1-2 sentences)
2. What could be improved (1-2 sentences)
3. Three specific lessons learned (bullet points)
4. Rate execution, timing, and sizing (0-100 each)
5. Suggest one strategy variant to test

Format your response as:
WORKED: [explanation]
FAILED: [explanation]
LESSONS:
- Lesson 1
- Lesson 2
- Lesson 3
SCORES: execution=X, timing=Y, sizing=Z
VARIANT: [description of variant]"""

    def __init__(self):
        super().__init__("learner")
        self._pending_reflections: List[Dict] = []
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Determine what to learn this cycle."""
        tasks = []
        
        # Check for closed trades to reflect on
        closed_trades = await self._get_recent_closed_trades()
        if closed_trades:
            tasks.append(f"Reflect on {len(closed_trades)} closed trades")
        
        # Recall relevant memories for current context
        if context.market_regime:
            tasks.append(f"Recall memories for {context.market_regime} regime")
        
        if not tasks:
            return AgentOutput(
                success=True,
                data={"closed_trades": [], "recall_needed": False},
                reasoning="No learning tasks this cycle",
                decision="idle",
                confidence=100,
            )
        
        return AgentOutput(
            success=True,
            data={
                "closed_trades": closed_trades,
                "recall_needed": True,
                "regime": context.market_regime,
            },
            reasoning=" | ".join(tasks),
            decision="learn_and_reflect",
            confidence=85,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Execute learning tasks."""
        closed_trades = thought.data.get("closed_trades", [])
        recall_needed = thought.data.get("recall_needed", False)
        regime = thought.data.get("regime", "normal")
        
        reflections: List[TradeReflection] = []
        memories_created: List[Memory] = []
        memories_recalled: List[Dict] = []
        strategy_updates: Dict[str, float] = {}
        
        # ═══════════════════════════════════════════════════════════════
        # 1. Reflect on closed trades
        # ═══════════════════════════════════════════════════════════════
        for trade in closed_trades[:5]:  # Limit to 5 per cycle
            reflection = await self._reflect_on_trade(trade, regime)
            if reflection:
                reflections.append(reflection)
                
                # Create memory from reflection
                memory = Memory(
                    title=f"{trade['coin']} {trade['side']} - {'+' if trade['pnl'] > 0 else ''}{trade['pnl']:.0f}",
                    content=f"Strategy: {trade['strategy']}. {reflection.what_worked} {reflection.what_failed}",
                    category="trade_outcome",
                    memory_type="short" if abs(trade["pnl"]) < 100 else "medium",
                    importance=min(90, 50 + abs(trade["pnl_percent"]) * 2),
                    related_coins=[trade["coin"]],
                )
                memories_created.append(memory)
                
                # Update strategy performance
                strategy = trade.get("strategy", "unknown")
                if strategy not in strategy_updates:
                    strategy_updates[strategy] = 0
                
                # Adjust weight based on outcome
                adjustment = 0.01 if trade["pnl"] > 0 else -0.005
                strategy_updates[strategy] = adjustment
        
        # ═══════════════════════════════════════════════════════════════
        # 2. Recall relevant memories
        # ═══════════════════════════════════════════════════════════════
        if recall_needed:
            memories_recalled = await self._recall_memories(
                regime=regime,
                coins=context.validated_coins[:5],
            )
            
            # Update context with recalled memories
            context.relevant_memories = memories_recalled
        
        # ═══════════════════════════════════════════════════════════════
        # 3. Store new memories
        # ═══════════════════════════════════════════════════════════════
        for memory in memories_created:
            await self._store_memory(memory, context.cycle_id)
        
        # ═══════════════════════════════════════════════════════════════
        # 4. Generate insights
        # ═══════════════════════════════════════════════════════════════
        insights = await self._generate_insights(reflections, memories_recalled, regime)
        
        output = LearnerOutput(
            reflections=reflections,
            memories_created=memories_created,
            memories_recalled=memories_recalled,
            strategy_updates=strategy_updates,
            insights=insights,
        )
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=f"Reflected on {len(reflections)} trades, recalled {len(memories_recalled)} memories, created {len(memories_created)} new memories",
            decision=f"learned_{len(reflections)}_trades",
            confidence=80,
        )
    
    async def _get_recent_closed_trades(self) -> List[Dict]:
        """Get recently closed trades that haven't been reflected on."""
        from models import AsyncSessionLocal
        
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("""
                    SELECT 
                        p.id, p.coin, p.side, p.quantity,
                        p.entry_price, p.current_price as exit_price,
                        p.realized_pnl as pnl, p.leverage,
                        p.opened_at, p.closed_at,
                        EXTRACT(EPOCH FROM (p.closed_at - p.opened_at)) / 60 as duration_mins
                    FROM positions p
                    LEFT JOIN trade_reflections tr ON tr.position_id = p.id
                    WHERE p.status = 'closed'
                      AND p.closed_at > NOW() - INTERVAL '1 hour'
                      AND tr.id IS NULL
                    ORDER BY p.closed_at DESC
                    LIMIT 10
                """))
                
                rows = result.fetchall()
                trades = []
                
                for row in rows:
                    entry = float(row.entry_price or 0)
                    pnl = float(row.pnl or 0)
                    qty = float(row.quantity or 0)
                    pnl_pct = (pnl / (entry * qty) * 100) if entry and qty else 0
                    
                    trades.append({
                        "id": str(row.id),
                        "coin": row.coin,
                        "side": row.side,
                        "entry": entry,
                        "exit": float(row.exit_price or 0),
                        "pnl": pnl,
                        "pnl_percent": pnl_pct,
                        "duration_mins": int(row.duration_mins or 0),
                        "strategy": "unknown",  # Would come from trade record
                    })
                
                return trades
                
        except Exception as e:
            logger.error(f"Failed to get closed trades: {e}")
            return []
    
    async def _reflect_on_trade(self, trade: Dict, regime: str) -> Optional[TradeReflection]:
        """Use Grok to reflect on a trade."""
        prompt = self.REFLECTION_PROMPT.format(
            coin=trade["coin"],
            strategy=trade.get("strategy", "unknown"),
            side=trade["side"],
            pnl=trade["pnl"],
            pnl_pct=trade["pnl_percent"],
            duration=trade["duration_mins"],
            entry=trade["entry"],
            exit=trade["exit"],
            regime=regime,
        )
        
        response, tokens = await self.call_grok(prompt, temperature=0.4)
        
        # Parse response
        try:
            return self._parse_reflection(trade, response)
        except Exception as e:
            logger.warning(f"Failed to parse reflection: {e}")
            return None
    
    def _parse_reflection(self, trade: Dict, response: str) -> TradeReflection:
        """Parse Grok reflection response."""
        import re
        
        # Extract sections
        worked = ""
        failed = ""
        lessons = []
        scores = {"execution": 50, "timing": 50, "sizing": 50}
        variant = ""
        
        lines = response.strip().split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("WORKED:"):
                worked = line.replace("WORKED:", "").strip()
            elif line.startswith("FAILED:"):
                failed = line.replace("FAILED:", "").strip()
            elif line.startswith("LESSONS:"):
                current_section = "lessons"
            elif line.startswith("SCORES:"):
                # Parse scores
                score_match = re.findall(r'(\w+)=(\d+)', line)
                for key, val in score_match:
                    if key in scores:
                        scores[key] = int(val)
            elif line.startswith("VARIANT:"):
                variant = line.replace("VARIANT:", "").strip()
            elif current_section == "lessons" and line.startswith("-"):
                lessons.append(line[1:].strip())
        
        return TradeReflection(
            trade_id=trade["id"],
            coin=trade["coin"],
            strategy=trade.get("strategy", "unknown"),
            side=trade["side"],
            pnl=trade["pnl"],
            pnl_percent=trade["pnl_percent"],
            hold_duration_mins=trade["duration_mins"],
            what_worked=worked,
            what_failed=failed,
            lessons_learned=lessons[:3],
            execution_quality=scores["execution"],
            timing_quality=scores["timing"],
            sizing_quality=scores["sizing"],
            strategy_variants=[{"description": variant}] if variant else [],
        )
    
    async def _recall_memories(
        self,
        regime: str,
        coins: List[str],
    ) -> List[Dict]:
        """Recall relevant memories for current context."""
        from models import AsyncSessionLocal
        
        try:
            async with AsyncSessionLocal() as session:
                # Recall by regime and coins
                result = await session.execute(text("""
                    SELECT 
                        id, title, content, category, memory_type,
                        importance_score, recall_count, related_coins
                    FROM memories
                    WHERE (expires_at IS NULL OR expires_at > NOW())
                      AND (
                        category = 'market_regime' AND content ILIKE :regime
                        OR related_coins && :coins
                        OR importance_score > 75
                      )
                    ORDER BY importance_score DESC, recall_count DESC
                    LIMIT 10
                """), {
                    "regime": f"%{regime}%",
                    "coins": coins,
                })
                
                rows = result.fetchall()
                memories = []
                
                for row in rows:
                    memories.append({
                        "id": str(row.id),
                        "title": row.title,
                        "content": row.content,
                        "category": row.category,
                        "importance": float(row.importance_score or 0),
                    })
                    
                    # Touch memory (update recall count)
                    await session.execute(text(
                        "SELECT touch_memory(:id)"
                    ), {"id": row.id})
                
                await session.commit()
                return memories
                
        except Exception as e:
            logger.error(f"Memory recall failed: {e}")
            return []
    
    async def _store_memory(self, memory: Memory, cycle_id: UUID):
        """Store a new memory in the database."""
        from models import AsyncSessionLocal
        
        # Calculate expiry based on type
        if memory.memory_type == "short":
            expires = datetime.utcnow() + timedelta(hours=24)
        elif memory.memory_type == "medium":
            expires = datetime.utcnow() + timedelta(days=7)
        else:
            expires = None  # Long-term
        
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO memories (
                        memory_type, category, title, content,
                        importance_score, expires_at, source_agent,
                        source_cycle_id, related_coins
                    ) VALUES (
                        :type, :category, :title, :content,
                        :importance, :expires, 'learner',
                        :cycle_id, :coins
                    )
                """), {
                    "type": memory.memory_type,
                    "category": memory.category,
                    "title": memory.title,
                    "content": memory.content,
                    "importance": memory.importance,
                    "expires": expires,
                    "cycle_id": str(cycle_id),
                    "coins": memory.related_coins,
                })
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
    
    async def _generate_insights(
        self,
        reflections: List[TradeReflection],
        memories: List[Dict],
        regime: str,
    ) -> str:
        """Generate meta-insights from reflections and memories."""
        if not reflections and not memories:
            return "No insights this cycle"
        
        # Summarize
        wins = [r for r in reflections if r.pnl > 0]
        losses = [r for r in reflections if r.pnl < 0]
        
        insights = []
        
        if reflections:
            win_rate = len(wins) / len(reflections) * 100
            insights.append(f"Win rate this cycle: {win_rate:.0f}%")
            
            # Common lessons
            all_lessons = [l for r in reflections for l in r.lessons_learned]
            if all_lessons:
                insights.append(f"Key lessons: {all_lessons[0]}")
        
        if memories:
            insights.append(f"Recalled {len(memories)} relevant memories")
        
        insights.append(f"Current regime: {regime}")
        
        return " | ".join(insights)

