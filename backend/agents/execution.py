"""
Execution Agent - Executes trades with paper/live modes.

Responsibilities:
1. Execute trades from StrategyEnsemble proposals
2. Smart order execution (slippage-aware)
3. Position management
4. Paper trading simulation
5. Risk checks before execution

Supports both paper trading and live trading via ccxt.
"""

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy import text

from .base import BaseAgent, AgentContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class ExecutedTrade:
    """Result of an executed trade."""
    order_id: str
    coin: str
    side: str
    
    # Execution
    quantity: float
    entry_price: float
    fill_price: float
    
    # Costs
    fee: float
    slippage_bps: float
    total_cost: float
    
    # Risk levels
    stop_loss: float
    take_profit: float
    leverage: float
    
    # Meta
    strategy: str
    is_paper: bool
    executed_at: datetime
    
    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "coin": self.coin,
            "side": self.side,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "fill_price": self.fill_price,
            "fee": self.fee,
            "slippage_bps": self.slippage_bps,
            "total_cost": self.total_cost,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "leverage": self.leverage,
            "strategy": self.strategy,
            "is_paper": self.is_paper,
            "executed_at": self.executed_at.isoformat(),
        }


@dataclass
class ExecutionOutput:
    """Output from Execution Agent."""
    executed_trades: List[ExecutedTrade]
    failed_trades: List[Dict]
    total_deployed: float
    total_fees: float
    
    def to_dict(self) -> Dict:
        return {
            "executed_trades": [t.to_dict() for t in self.executed_trades],
            "failed_trades": self.failed_trades,
            "total_deployed": self.total_deployed,
            "total_fees": self.total_fees,
        }


class ExecutionAgent(BaseAgent):
    """
    Executes trades with paper/live mode support.
    
    Paper Mode:
    - Uses simulated order book
    - Realistic fees (0.02% maker, 0.05% taker)
    - Slippage simulation
    
    Live Mode:
    - Uses ccxt for Binance
    - Real order execution
    - (Disabled by default)
    """
    
    # Fee structure (Binance Futures VIP 0)
    TAKER_FEE = 0.0005  # 0.05%
    MAKER_FEE = 0.0002  # 0.02%
    
    # Risk limits (hard stops)
    DAILY_LOSS_LIMIT = 0.05  # 5% daily loss = kill switch
    MAX_SINGLE_TRADE = 0.12  # 12% of equity
    
    def __init__(self):
        super().__init__("execution")
        self._mode = os.getenv("MODE", "paper").lower()
        self._daily_pnl = 0.0
        self._killed = False
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Prepare for trade execution."""
        proposals = context.trade_proposals
        
        if not proposals:
            return AgentOutput(
                success=True,
                data={"proposals": []},
                reasoning="No trade proposals to execute",
                decision="no_trades",
                confidence=100,
            )
        
        # Check kill switch
        if self._killed:
            return AgentOutput(
                success=False,
                reasoning="Kill switch active - daily loss limit breached",
                decision="blocked",
                confidence=100,
            )
        
        # Get current prices
        prices = await self._get_current_prices([p.get("coin") for p in proposals])
        
        reasoning = f"Preparing to execute {len(proposals)} trades in {self._mode.upper()} mode"
        
        return AgentOutput(
            success=True,
            data={"proposals": proposals, "prices": prices},
            reasoning=reasoning,
            decision=f"execute_{len(proposals)}_trades",
            confidence=90,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Execute the trades."""
        proposals = thought.data.get("proposals", [])
        prices = thought.data.get("prices", {})
        
        executed: List[ExecutedTrade] = []
        failed: List[Dict] = []
        total_fees = 0.0
        total_deployed = 0.0
        
        # Get portfolio for sizing
        portfolio = context.portfolio or {}
        equity = portfolio.get("total_equity", 100000)
        
        for proposal in proposals:
            try:
                coin = proposal.get("coin")
                side = proposal.get("side")
                size_pct = proposal.get("size_percent", 5) / 100
                leverage = proposal.get("leverage", 4)
                
                # Get current price
                price = prices.get(coin, 0)
                if price <= 0:
                    failed.append({"coin": coin, "reason": "No price data"})
                    continue
                
                # Calculate position size
                notional = equity * size_pct * leverage
                quantity = notional / price
                
                # Risk checks
                if size_pct > self.MAX_SINGLE_TRADE:
                    size_pct = self.MAX_SINGLE_TRADE
                    notional = equity * size_pct * leverage
                    quantity = notional / price
                
                # Execute trade
                if self._mode == "live":
                    trade = await self._execute_live(coin, side, quantity, price, proposal)
                else:
                    trade = await self._execute_paper(coin, side, quantity, price, proposal)
                
                if trade:
                    executed.append(trade)
                    total_fees += trade.fee
                    total_deployed += trade.total_cost
                    
                    # Save to database
                    await self._save_trade(trade, context.cycle_id)
                    
            except Exception as e:
                logger.error(f"Trade execution failed for {proposal.get('coin')}: {e}")
                failed.append({"coin": proposal.get("coin"), "reason": str(e)})
        
        # Update context
        context.executed_trades = [t.to_dict() for t in executed]
        
        output = ExecutionOutput(
            executed_trades=executed,
            failed_trades=failed,
            total_deployed=total_deployed,
            total_fees=total_fees,
        )
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=f"Executed {len(executed)} trades, {len(failed)} failed. Fees: ${total_fees:.2f}",
            decision=f"executed_{len(executed)}_failed_{len(failed)}",
            confidence=95 if not failed else 75,
        )
    
    async def _execute_paper(
        self,
        coin: str,
        side: str,
        quantity: float,
        price: float,
        proposal: Dict,
    ) -> ExecutedTrade:
        """Execute paper trade with simulated slippage."""
        import random
        
        # Simulate slippage (0.01% - 0.1%)
        slippage_bps = random.uniform(1, 10)
        slippage_mult = 1 + (slippage_bps / 10000) * (1 if side == "buy" or side == "long" else -1)
        fill_price = price * slippage_mult
        
        # Calculate costs
        notional = quantity * fill_price
        fee = notional * self.TAKER_FEE
        total_cost = notional + fee
        
        # Calculate SL/TP prices
        sl_pct = proposal.get("stop_loss_percent", 2.5) / 100
        tp_pct = proposal.get("take_profit_percent", 7.5) / 100
        
        if side in ["long", "buy"]:
            stop_loss = fill_price * (1 - sl_pct)
            take_profit = fill_price * (1 + tp_pct)
        else:
            stop_loss = fill_price * (1 + sl_pct)
            take_profit = fill_price * (1 - tp_pct)
        
        return ExecutedTrade(
            order_id=f"PAPER_{uuid4().hex[:12]}",
            coin=coin,
            side=side,
            quantity=quantity,
            entry_price=price,
            fill_price=fill_price,
            fee=fee,
            slippage_bps=slippage_bps,
            total_cost=total_cost,
            stop_loss=stop_loss,
            take_profit=take_profit,
            leverage=proposal.get("leverage", 4),
            strategy=proposal.get("strategy", "unknown"),
            is_paper=True,
            executed_at=datetime.utcnow(),
        )
    
    async def _execute_live(
        self,
        coin: str,
        side: str,
        quantity: float,
        price: float,
        proposal: Dict,
    ) -> Optional[ExecutedTrade]:
        """Execute live trade via ccxt (placeholder)."""
        logger.warning("Live trading not implemented yet")
        return None
    
    async def _get_current_prices(self, coins: List[str]) -> Dict[str, float]:
        """Get current prices from Binance."""
        import httpx
        
        prices = {}
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.binance.com/api/v3/ticker/price"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    price_map = {
                        t["symbol"].replace("USDT", ""): float(t["price"])
                        for t in data
                        if t["symbol"].endswith("USDT")
                    }
                    
                    for coin in coins:
                        if coin in price_map:
                            prices[coin] = price_map[coin]
                            
        except Exception as e:
            logger.error(f"Price fetch failed: {e}")
        
        return prices
    
    async def _save_trade(self, trade: ExecutedTrade, cycle_id):
        """Save trade to database."""
        from models import AsyncSessionLocal
        
        try:
            async with AsyncSessionLocal() as session:
                # Create position
                await session.execute(text("""
                    INSERT INTO positions (
                        coin, side, quantity, entry_price, current_price,
                        stop_loss, take_profit, leverage, status, opened_at
                    ) VALUES (
                        :coin, :side, :qty, :entry, :current,
                        :sl, :tp, :lev, 'open', NOW()
                    )
                    RETURNING id
                """), {
                    "coin": trade.coin,
                    "side": trade.side,
                    "qty": trade.quantity,
                    "entry": trade.fill_price,
                    "current": trade.fill_price,
                    "sl": trade.stop_loss,
                    "tp": trade.take_profit,
                    "lev": trade.leverage,
                })
                
                position_result = await session.execute(text(
                    "SELECT id FROM positions WHERE coin = :coin AND status = 'open' ORDER BY opened_at DESC LIMIT 1"
                ), {"coin": trade.coin})
                position_row = position_result.fetchone()
                position_id = position_row[0] if position_row else None
                
                # Create trade record
                await session.execute(text("""
                    INSERT INTO trades (
                        position_id, order_id, coin, side, order_type,
                        quantity, price, fee, fee_currency,
                        slippage_cost, total_cost, status, is_paper, executed_at
                    ) VALUES (
                        :pos_id, :order_id, :coin, :side, 'market',
                        :qty, :price, :fee, 'USDT',
                        :slip, :total, 'filled', :paper, :exec_at
                    )
                """), {
                    "pos_id": position_id,
                    "order_id": trade.order_id,
                    "coin": trade.coin,
                    "side": "buy" if trade.side in ["long", "buy"] else "sell",
                    "qty": trade.quantity,
                    "price": trade.fill_price,
                    "fee": trade.fee,
                    "slip": trade.slippage_bps * trade.fill_price * trade.quantity / 10000,
                    "total": trade.total_cost,
                    "paper": trade.is_paper,
                    "exec_at": trade.executed_at,
                })
                
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")
    
    async def check_daily_loss(self, current_equity: float, initial_equity: float) -> bool:
        """Check if daily loss limit is breached."""
        daily_pnl_pct = (current_equity - initial_equity) / initial_equity
        
        if daily_pnl_pct <= -self.DAILY_LOSS_LIMIT:
            logger.critical(f"KILL SWITCH ACTIVATED: Daily loss {daily_pnl_pct*100:.2f}%")
            self._killed = True
            
            # Log to database
            await self.logbook.log(
                agent_name=self.name,
                action_type="kill_switch",
                reasoning=f"Daily loss limit breached: {daily_pnl_pct*100:.2f}% loss",
                decision="halt_trading",
                confidence=100,
            )
            
            return True
        
        return False
    
    async def close_position(self, coin: str, reason: str = "manual") -> Optional[Dict]:
        """Close an open position."""
        from models import AsyncSessionLocal
        
        # Get current price
        prices = await self._get_current_prices([coin])
        price = prices.get(coin, 0)
        
        if price <= 0:
            return None
        
        try:
            async with AsyncSessionLocal() as session:
                # Get open position
                result = await session.execute(text("""
                    SELECT id, side, quantity, entry_price, leverage
                    FROM positions
                    WHERE coin = :coin AND status = 'open'
                    ORDER BY opened_at DESC LIMIT 1
                """), {"coin": coin})
                
                row = result.fetchone()
                if not row:
                    return None
                
                pos_id, side, qty, entry, leverage = row
                
                # Calculate PnL
                if side in ["long", "buy"]:
                    pnl = (price - entry) * qty * leverage
                else:
                    pnl = (entry - price) * qty * leverage
                
                # Close position
                await session.execute(text("""
                    UPDATE positions
                    SET status = 'closed',
                        current_price = :price,
                        realized_pnl = :pnl,
                        closed_at = NOW()
                    WHERE id = :id
                """), {"price": price, "pnl": pnl, "id": pos_id})
                
                await session.commit()
                
                return {
                    "coin": coin,
                    "pnl": pnl,
                    "exit_price": price,
                    "reason": reason,
                }
                
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return None

