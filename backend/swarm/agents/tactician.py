"""
Tactician Agent - The Strategy Mind

Formulates trading strategies and makes STRUCTURED trade decisions.
Outputs JSON trade proposals that Operator can directly execute.

Personality: Calculated, strategic, decisive. Thinks in probabilities.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import Signal, SignalType
from ..positions import get_position_manager, PositionManager
from integrations.binance import get_binance, BinanceClient

logger = logging.getLogger(__name__)


class TacticianAgent(EmergentAgent):
    """
    Tactician makes strategic trading decisions.
    
    Key responsibilities:
    1. Gather insights from Scout, Analyst, Oracle
    2. Synthesize into trading context
    3. Ask Grok for structured trade decision (JSON)
    4. Broadcast PROPOSAL signal for Operator to execute
    
    Does NOT execute trades - that's Operator's job.
    """
    
    PERCEPTION_INTERVAL = 120  # Every 2 minutes
    SPEAK_THRESHOLD = 0.5      # Share insights more often
    ACT_THRESHOLD = 0.7        # Conviction 70+ to propose trade
    
    def __init__(self):
        persona = AgentPersona(
            id="tactician",
            name="Tactician",
            emoji="🎯",
            role="Strategy & Decision Making",
            personality="Calculated, strategic, decisive. Thinks in risk/reward ratios. "
                       "Weighs probabilities carefully. Makes clear recommendations. "
                       "Only trades when conviction is HIGH.",
            focus_areas=["strategy", "risk", "opportunity", "decision", "trade", 
                        "insight", "discovery", "sentiment", "analysis"],
        )
        super().__init__(persona)
        
        # Connections
        self.position_manager: PositionManager = get_position_manager()
        self.binance: BinanceClient = get_binance()
        
        # Track recent decisions
        self._last_decision: Optional[Dict] = None
        self._decisions_today = 0
    
    def is_interested(self, signal: Signal) -> bool:
        """Tactician listens to ALL agent insights."""
        if super().is_interested(signal):
            return True
        
        # Interested in insights from analysis agents
        relevant_types = [
            SignalType.INSIGHT, 
            SignalType.DISCOVERY, 
            SignalType.ALERT,
            SignalType.HEARTBEAT,
        ]
        if signal.type in relevant_types:
            return True
        
        # Interested in signals from specific agents
        if signal.sender_id in ["scout", "analyst", "oracle", "sage"]:
            return True
        
        return False
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Tactician perception = build trading context from team signals.
        
        Collects all recent insights and synthesizes into a decision prompt.
        """
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        # 1. Collect recent signals from team
        recent_signals = self.network.get_recent_signals(limit=30)
        
        # Build context from signals
        context_parts = []
        
        # Group signals by sender
        signals_by_sender: Dict[str, List[Signal]] = {}
        for signal in recent_signals:
            if signal.sender_id != self.id:  # Exclude own signals
                if signal.sender_id not in signals_by_sender:
                    signals_by_sender[signal.sender_id] = []
                signals_by_sender[signal.sender_id].append(signal)
        
        # Build context
        for sender_id, signals in signals_by_sender.items():
            sender_name = signals[0].sender_name if signals else sender_id
            context_parts.append(f"\n### {sender_name}'s Observations:")
            for signal in signals[-3:]:  # Last 3 from each
                context_parts.append(f"- [{signal.type.value}] {signal.content[:300]}")
                if signal.confidence > 0.7:
                    context_parts.append(f"  (Confidence: {signal.confidence:.0%})")
        
        team_context = "\n".join(context_parts) if context_parts else "(No team signals yet)"
        
        # 2. Get portfolio status
        available_capital = self.position_manager.get_available_capital()
        open_positions = self.position_manager.get_open_positions()
        positions_data = [
            {
                "symbol": p.symbol,
                "direction": p.direction,
                "size": p.size_usdt,
                "entry": p.entry_price,
                "pnl": p.calculate_pnl(await self.binance.get_price(p.symbol)) if p.is_open else p.realized_pnl,
            }
            for p in open_positions[:5]
        ]
        
        # 3. Get tradable coins
        tradable_coins = self.binance.get_tradable_coins()
        
        return {
            "team_context": team_context,
            "available_capital": available_capital,
            "open_positions": positions_data,
            "tradable_coins": tradable_coins,
            "signals_analyzed": len(recent_signals),
            "timestamp": current_datetime,
        }
    
    async def think(
        self,
        signals: List[Signal],
        perception: Dict[str, Any]
    ) -> Thought:
        """
        Tactician thinking = structured trade decision.
        
        Uses Grok's ask_for_trade_decision() for JSON output.
        """
        now = datetime.utcnow()
        current_datetime = now.strftime("%A, %B %d, %Y at %H:%M UTC")
        
        # Build comprehensive context
        context = f"""## Current Time: {current_datetime}

## Team Analysis
{perception.get('team_context', 'No team context')}

## My Current Beliefs
{self.beliefs.to_prompt()}

## Portfolio Status
- Available Capital: ${perception.get('available_capital', 0):,.2f}
- Open Positions: {len(perception.get('open_positions', []))}
"""
        
        # Add details of open positions
        open_positions = perception.get('open_positions', [])
        if open_positions:
            context += "\n### Open Positions:\n"
            for pos in open_positions:
                context += f"- {pos['direction']} {pos['symbol']}: ${pos['size']:,.0f} @ ${pos['entry']:,.2f} (PnL: ${pos['pnl']:+,.2f})\n"
        
        # Ask Grok for structured decision
        decision = await self.grok.ask_for_trade_decision(
            context=context,
            available_capital=perception.get('available_capital', 0),
            open_positions=open_positions,
            tradable_coins=perception.get('tradable_coins', []),
            agent_id=self.id,
            agent_name=self.name,
        )
        
        self._last_decision = decision
        
        # Convert decision to Thought
        decision_str = decision.get("decision", "PASS")
        conviction = decision.get("conviction", 0) / 100.0  # Convert to 0-1
        reasoning = decision.get("reasoning", "No reasoning provided")
        
        # Build summary
        if decision_str == "TRADE":
            coin = decision.get("coin", "?")
            direction = decision.get("direction", "?")
            summary = f"🎯 TRADE: {direction} {coin} with {conviction:.0%} conviction - {reasoning}"
            action_needed = True
            proposed_action = {
                "type": "trade",
                "description": f"{direction} {coin}",
                "coin": decision.get("coin"),
                "direction": decision.get("direction"),
                "size_percent": decision.get("size_percent", 5),
                "stop_loss_percent": decision.get("stop_loss_percent", 3),
                "take_profit_percent": decision.get("take_profit_percent", 6),
                "conviction": decision.get("conviction", 0),
                "reasoning": reasoning,
            }
        else:
            summary = f"⏸️ {decision_str}: {reasoning}"
            action_needed = False
            proposed_action = None
        
        # Create thought
        thought = Thought(
            content=f"Decision: {decision_str}\n\nContext analyzed: {context[:500]}...\n\nReasoning: {reasoning}",
            summary=summary,
            action_needed=action_needed,
            proposed_action=proposed_action,
            significance=0.8 if action_needed else 0.4,
            confidence=conviction,
            conviction=conviction,
            tokens_used=0,  # Not available from ask_for_trade_decision
        )
        
        return thought
    
    async def act(self, thought: Thought) -> Optional[Dict]:
        """
        Tactician action = broadcast PROPOSAL signal for Operator.
        
        Only acts if conviction >= ACT_THRESHOLD and there's a valid proposal.
        """
        if not thought.action_needed:
            logger.info(f"{self.persona.emoji} Tactician: No trade action needed")
            return None
        
        if thought.conviction < self.ACT_THRESHOLD:
            logger.info(
                f"{self.persona.emoji} Tactician: Conviction {thought.conviction:.0%} "
                f"below threshold {self.ACT_THRESHOLD:.0%}"
            )
            return None
        
        proposal = thought.proposed_action
        if not proposal:
            return None
        
        # Check if we can actually trade this
        coin = proposal.get("coin", "").upper()
        if not coin:
            logger.warning(f"{self.persona.emoji} Tactician: No coin specified in proposal")
            return None
        
        # Check if already have position
        if self.position_manager.has_open_position(coin):
            logger.info(f"{self.persona.emoji} Tactician: Already have position in {coin}, skipping")
            return None
        
        # Calculate actual size in USDT
        available = self.position_manager.get_available_capital()
        size_pct = proposal.get("size_percent", 5)
        size_usdt = available * (size_pct / 100)
        
        # Check if we can open position
        can_trade, reason = self.position_manager.can_open_position(
            size_usdt=size_usdt,
            conviction=proposal.get("conviction", 0),
        )
        
        if not can_trade:
            logger.warning(f"{self.persona.emoji} Tactician: Cannot trade - {reason}")
            return None
        
        # Enrich proposal with actual values
        proposal["size_usdt"] = size_usdt
        proposal["available_capital"] = available
        
        # Broadcast PROPOSAL signal for Operator
        signal = await self._broadcast_signal(
            SignalType.PROPOSAL,
            "trade",
            thought.summary,
            confidence=thought.conviction,
            urgency=0.8,
            importance=0.9,
            mentions=["operator"],
            tags=["trade", proposal.get("coin", ""), proposal.get("direction", "").lower()],
            data=proposal,
        )
        
        self._decisions_today += 1
        
        logger.info(
            f"{self.persona.emoji} Tactician: Proposed {proposal.get('direction')} "
            f"{proposal.get('coin')} (${size_usdt:,.2f}, conviction: {thought.conviction:.0%})"
        )
        
        return {
            "status": "proposed",
            "signal_id": str(signal.id),
            "proposal": proposal,
        }
    
    async def _execute_action(self, action: Dict) -> Dict:
        """
        Execute action (called by base class if act() returns action).
        
        For Tactician, this is handled in act() already.
        """
        return {"status": "executed", "action": action}
    
    def get_status(self) -> Dict:
        """Get extended status including last decision."""
        status = super().get_status()
        status.update({
            "last_decision": self._last_decision,
            "decisions_today": self._decisions_today,
            "available_capital": self.position_manager.get_available_capital(),
            "open_positions": len(self.position_manager.get_open_positions()),
        })
        return status
