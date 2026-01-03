"""
Operator Agent - The Executor

Executes trades based on Tactician's proposals.
Uses real Binance prices and PositionManager for tracking.

Personality: Precise, disciplined, follows orders but flags concerns.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..agent import EmergentAgent, AgentPersona, Thought
from ..signals import Signal, SignalType
from ..positions import get_position_manager, PositionManager, Position, Trade
from integrations.binance import get_binance, BinanceClient

logger = logging.getLogger(__name__)


class OperatorAgent(EmergentAgent):
    """
    Operator executes trades from Tactician proposals.
    
    Responsibilities:
    1. Listen for PROPOSAL signals from Tactician
    2. Get real prices from Binance
    3. Execute trades via PositionManager
    4. Monitor positions for stops/take-profits
    5. Broadcast execution results
    
    Paper mode uses Binance real prices but simulates orders.
    """
    
    PERCEPTION_INTERVAL = 30   # Check every 30 seconds for stops
    SPEAK_THRESHOLD = 0.5      # Report important updates
    ACT_THRESHOLD = 0.5        # Lower threshold - executes Tactician's decisions
    
    def __init__(self, paper_mode: bool = True):
        persona = AgentPersona(
            id="operator",
            name="Operator",
            emoji="⚡",
            role="Trade Execution",
            personality="Precise, disciplined, efficient. Executes cleanly. "
                       "Reports status clearly. Flags execution concerns. "
                       "Monitors positions continuously.",
            focus_areas=["execution", "orders", "positions", "fills", "trade", "proposal"],
        )
        super().__init__(persona)
        
        self.paper_mode = paper_mode
        
        # Connections
        self.position_manager: PositionManager = get_position_manager()
        self.binance: BinanceClient = get_binance()
        
        # Queue of pending trade proposals from Tactician
        self._pending_proposals: List[Dict] = []
        
        # Track executed trades for reporting
        self._trades_executed_today = 0
        self._last_execution: Optional[Dict] = None
    
    def is_interested(self, signal: Signal) -> bool:
        """Operator listens for trade proposals from Tactician."""
        if super().is_interested(signal):
            return True
        
        # Interested in PROPOSAL signals
        if signal.type == SignalType.PROPOSAL:
            return True
        
        # Interested if mentioned
        if "operator" in signal.mentions:
            return True
        
        return False
    
    async def receive_signal(self, signal: Signal):
        """
        Handle incoming signals.
        
        Immediately queue PROPOSAL signals from Tactician.
        """
        await super().receive_signal(signal)
        
        # Queue trade proposals for execution
        if signal.type == SignalType.PROPOSAL:
            if signal.sender_id == "tactician" and signal.data:
                proposal = signal.data.copy()
                proposal["signal_id"] = str(signal.id)
                proposal["received_at"] = datetime.utcnow().isoformat()
                self._pending_proposals.append(proposal)
                
                logger.info(
                    f"⚡ Operator: Received trade proposal - "
                    f"{proposal.get('direction')} {proposal.get('coin')}"
                )
    
    async def perceive(self) -> Dict[str, Any]:
        """
        Operator perception = check positions and prices.
        
        1. Get current prices for open positions
        2. Check for stop-loss/take-profit triggers
        3. Calculate unrealized PnL
        """
        now = datetime.utcnow()
        
        # Get open positions
        open_positions = self.position_manager.get_open_positions()
        
        # Get current prices
        symbols = [p.symbol for p in open_positions]
        current_prices = {}
        
        if symbols:
            try:
                current_prices = await self.binance.get_prices(symbols)
            except Exception as e:
                logger.error(f"Error fetching prices: {e}")
        
        # Calculate PnL and check stops
        positions_data = []
        for pos in open_positions:
            price = current_prices.get(pos.symbol, pos.entry_price)
            pnl = pos.calculate_pnl(price)
            pnl_pct = pos.calculate_pnl_percent(price)
            
            positions_data.append({
                "id": pos.id,
                "symbol": pos.symbol,
                "direction": pos.direction,
                "entry": pos.entry_price,
                "current": price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "stop": pos.stop_loss_price,
                "target": pos.take_profit_price,
                "should_stop": pos.should_stop_out(price),
                "should_tp": pos.should_take_profit(price),
            })
        
        # Calculate totals
        total_unrealized = sum(p["pnl"] for p in positions_data)
        
        return {
            "pending_proposals": len(self._pending_proposals),
            "open_positions": len(open_positions),
            "positions": positions_data,
            "current_prices": current_prices,
            "total_unrealized_pnl": total_unrealized,
            "capital": self.position_manager.capital,
            "timestamp": now.isoformat(),
        }
    
    async def think(self, signals: List[Signal], perception: Dict) -> Thought:
        """
        Operator thinking:
        1. Execute pending proposals first (priority)
        2. Check and handle stops/take-profits
        3. Monitor position health
        """
        action_needed = False
        proposed_action = None
        summary = ""
        significance = 0.3
        
        # Priority 1: Execute pending proposals
        if self._pending_proposals:
            proposal = self._pending_proposals.pop(0)
            
            summary = f"⚡ Executing: {proposal.get('direction')} {proposal.get('coin')}"
            action_needed = True
            proposed_action = {
                "type": "execute_trade",
                "proposal": proposal,
            }
            significance = 0.9
            
        # Priority 2: Check stops/take-profits
        else:
            positions = perception.get("positions", [])
            
            for pos in positions:
                if pos.get("should_stop"):
                    summary = f"🛑 Stop triggered: {pos['symbol']}"
                    action_needed = True
                    proposed_action = {
                        "type": "close_position",
                        "position_id": pos["id"],
                        "reason": "stop_loss",
                        "price": pos["current"],
                    }
                    significance = 0.95
                    break
                    
                elif pos.get("should_tp"):
                    summary = f"🎯 Take profit: {pos['symbol']}"
                    action_needed = True
                    proposed_action = {
                        "type": "close_position",
                        "position_id": pos["id"],
                        "reason": "take_profit",
                        "price": pos["current"],
                    }
                    significance = 0.9
                    break
            
            # No action needed - just monitoring
            if not action_needed:
                open_count = perception.get("open_positions", 0)
                pnl = perception.get("total_unrealized_pnl", 0)
                
                if open_count > 0:
                    summary = f"📊 Monitoring {open_count} positions (${pnl:+,.2f})"
                else:
                    summary = "👀 No positions. Waiting for signals."
                significance = 0.2
        
        return Thought(
            content=summary,
            summary=summary,
            action_needed=action_needed,
            proposed_action=proposed_action,
            significance=significance,
            confidence=0.95,
            conviction=0.9 if action_needed else 0.2,
        )
    
    async def act(self, thought: Thought) -> Optional[Dict]:
        """Execute the action from thought."""
        if not thought.action_needed or not thought.proposed_action:
            return None
        
        action = thought.proposed_action
        action_type = action.get("type", "")
        
        if action_type == "execute_trade":
            return await self._execute_trade(action.get("proposal", {}))
            
        elif action_type == "close_position":
            return await self._close_position(
                action.get("position_id"),
                action.get("price"),
                action.get("reason", "manual"),
            )
        
        return None
    
    async def _execute_trade(self, proposal: Dict) -> Dict:
        """
        Execute a trade proposal from Tactician.
        
        Uses real Binance prices, executes via PositionManager.
        """
        coin = proposal.get("coin", "").upper()
        direction = proposal.get("direction", "LONG").upper()
        size_percent = proposal.get("size_percent", 5)
        stop_loss_pct = proposal.get("stop_loss_percent", 3)
        take_profit_pct = proposal.get("take_profit_percent", 6)
        conviction = proposal.get("conviction", 70)
        reasoning = proposal.get("reasoning", "")
        
        # Format symbol
        symbol = coin if coin.endswith("USDT") else f"{coin}USDT"
        
        try:
            # Get real price from Binance
            price = await self.binance.get_price(symbol)
            
            # Calculate position size
            available = self.position_manager.get_available_capital()
            size_usdt = available * (size_percent / 100)
            
            # Check if we can trade
            can_trade, reason = self.position_manager.can_open_position(
                size_usdt=size_usdt,
                conviction=conviction,
            )
            
            if not can_trade:
                logger.warning(f"⚡ Operator: Cannot execute - {reason}")
                await self._broadcast_signal(
                    SignalType.ALERT,
                    "execution_blocked",
                    f"❌ Trade blocked: {reason}",
                    confidence=1.0,
                    importance=0.7,
                )
                return {"status": "blocked", "reason": reason}
            
            # Open position via PositionManager
            position = self.position_manager.open_position(
                symbol=symbol,
                direction=direction,
                size_usdt=size_usdt,
                entry_price=price,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct,
                conviction=conviction,
                reasoning=reasoning,
            )
            
            # Execute on Binance (paper mode)
            order = await self.binance.open_position(
                symbol=symbol,
                side=direction,
                size_usdt=size_usdt,
            )
            
            self._trades_executed_today += 1
            self._last_execution = {
                "position_id": position.id,
                "order_id": order.order_id,
                "symbol": symbol,
                "direction": direction,
                "size": size_usdt,
                "price": price,
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Broadcast execution result
            await self._broadcast_signal(
                SignalType.RESULT,
                "trade_executed",
                f"✅ Opened {direction} {coin}: ${size_usdt:,.2f} @ ${price:,.2f} | "
                f"Stop: ${position.stop_loss_price:,.2f} | Target: ${position.take_profit_price:,.2f}",
                confidence=1.0,
                importance=0.9,
                tags=["trade", coin.lower(), direction.lower()],
                data={
                    "position_id": position.id,
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": price,
                    "size_usdt": size_usdt,
                    "stop_loss": position.stop_loss_price,
                    "take_profit": position.take_profit_price,
                    "paper": self.paper_mode,
                },
            )
            
            logger.info(
                f"⚡ TRADE EXECUTED: {direction} {symbol} @ ${price:,.2f} "
                f"(${size_usdt:,.2f}, conviction: {conviction}%)"
            )
            
            return {
                "status": "executed",
                "position_id": position.id,
                "order_id": order.order_id,
                "symbol": symbol,
                "direction": direction,
                "price": price,
                "size_usdt": size_usdt,
            }
            
        except Exception as e:
            logger.error(f"⚡ Operator: Execution error - {e}", exc_info=True)
            
            await self._broadcast_signal(
                SignalType.ALERT,
                "execution_error",
                f"❌ Execution failed: {str(e)}",
                confidence=1.0,
                importance=0.9,
            )
            
            return {"status": "error", "error": str(e)}
    
    async def _close_position(
        self,
        position_id: str,
        exit_price: float,
        reason: str = "manual",
    ) -> Dict:
        """
        Close a position (stop loss, take profit, or manual).
        """
        try:
            position = self.position_manager.get_position(position_id)
            if not position or not position.is_open:
                return {"status": "not_found", "position_id": position_id}
            
            # Get current price if not provided
            if not exit_price:
                exit_price = await self.binance.get_price(position.symbol)
            
            # Close via PositionManager
            trade = self.position_manager.close_position(
                position_id=position_id,
                exit_price=exit_price,
                exit_reason=reason,
            )
            
            # Close on Binance (paper mode)
            await self.binance.close_position(
                symbol=position.symbol,
                side=position.direction,
                quantity=position.quantity,
            )
            
            # Determine emoji based on result
            if trade.pnl_usdt > 0:
                emoji = "🟢"
                status = "WIN"
            else:
                emoji = "🔴"
                status = "LOSS"
            
            # Broadcast result
            await self._broadcast_signal(
                SignalType.RESULT,
                f"position_closed_{reason}",
                f"{emoji} Closed {position.direction} {position.symbol}: "
                f"${trade.pnl_usdt:+,.2f} ({trade.pnl_percent:+.1f}%) | {reason.upper()}",
                confidence=1.0,
                importance=0.9,
                mentions=["sage"],  # Sage learns from this
                tags=["trade_result", position.symbol.replace("USDT", "").lower(), status.lower()],
                data={
                    "trade_id": trade.id,
                    "position_id": position_id,
                    "symbol": position.symbol,
                    "direction": position.direction,
                    "entry_price": trade.entry_price,
                    "exit_price": trade.exit_price,
                    "pnl_usdt": trade.pnl_usdt,
                    "pnl_percent": trade.pnl_percent,
                    "duration_seconds": trade.duration_seconds,
                    "exit_reason": reason,
                },
            )
            
            logger.info(
                f"⚡ POSITION CLOSED: {position.symbol} | "
                f"PnL: ${trade.pnl_usdt:+,.2f} ({trade.pnl_percent:+.1f}%) | {reason}"
            )
            
            return {
                "status": "closed",
                "trade_id": trade.id,
                "pnl": trade.pnl_usdt,
                "reason": reason,
            }
            
        except Exception as e:
            logger.error(f"⚡ Operator: Close error - {e}", exc_info=True)
            return {"status": "error", "error": str(e)}
    
    async def _execute_action(self, action: Dict) -> Dict:
        """
        Fallback execution (called by base class).
        
        Most execution is handled in act() directly.
        """
        return {"status": "executed", "action": action}
    
    def get_status(self) -> Dict:
        """Get extended status."""
        status = super().get_status()
        stats = self.position_manager.get_statistics()
        
        status.update({
            "paper_mode": self.paper_mode,
            "pending_proposals": len(self._pending_proposals),
            "trades_today": self._trades_executed_today,
            "last_execution": self._last_execution,
            "portfolio": {
                "capital": stats["current_capital"],
                "total_pnl": stats["total_pnl"],
                "open_positions": stats["open_positions"],
                "win_rate": stats["win_rate"],
            },
        })
        return status
