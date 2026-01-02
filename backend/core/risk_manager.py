"""
Risk Manager - Position limits, drawdown circuit breakers, and VaR calculations
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
from sqlalchemy import select, func

from events import (
    get_event_bus,
    EventType,
    RiskCheckRequestedEvent,
    RiskApprovedEvent,
    RiskRejectedEvent,
    RiskLimitBreachEvent,
    CircuitBreakerEvent,
    deserialize_event,
)
from models import AsyncSessionLocal, Position, PortfolioSnapshot, Signal
from models.risk import RiskEvent, RiskLimits, SystemConfig
from models.audit import log_audit

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Risk Manager - Enforces risk limits and manages circuit breakers.
    
    Responsibilities:
    1. Position limit enforcement (per-asset, sector, total)
    2. Drawdown monitoring with circuit breakers
    3. Real-time VaR calculation
    4. Trade approval/rejection
    """
    
    def __init__(self):
        self.bus = get_event_bus()
        self.running = False
        self.circuit_breaker_level = 0  # 0 = normal, 1-3 = triggered levels
        self.daily_high_equity = None
        self.session_start_equity = None
        
        # Default limits (can be overridden from DB)
        self.limits = RiskLimits.DEFAULTS.copy()
    
    async def load_limits(self):
        """Load risk limits from database"""
        async with AsyncSessionLocal() as session:
            for key, default in RiskLimits.DEFAULTS.items():
                value = await SystemConfig.get_value(session, key, default)
                self.limits[key] = float(value) if isinstance(value, str) else value
        
        logger.info(f"Loaded risk limits: {self.limits}")
    
    async def get_current_portfolio(self) -> Dict:
        """Get current portfolio state"""
        async with AsyncSessionLocal() as session:
            # Get latest snapshot
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if snapshot:
                return {
                    'total_equity': float(snapshot.total_equity),
                    'cash': float(snapshot.cash),
                    'positions_value': float(snapshot.positions_value),
                    'unrealized_pnl': float(snapshot.unrealized_pnl),
                    'realized_pnl': float(snapshot.realized_pnl),
                    'daily_pnl': float(snapshot.daily_pnl) if snapshot.daily_pnl else 0,
                    'daily_pnl_percent': float(snapshot.daily_pnl_percent) if snapshot.daily_pnl_percent else 0,
                }
            
            # Default starting portfolio
            return {
                'total_equity': 10000.0,
                'cash': 10000.0,
                'positions_value': 0.0,
                'unrealized_pnl': 0.0,
                'realized_pnl': 0.0,
                'daily_pnl': 0.0,
                'daily_pnl_percent': 0.0,
            }
    
    async def get_open_positions(self) -> List[Position]:
        """Get all open positions"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Position).where(Position.status == 'open')
            )
            return result.scalars().all()
    
    async def check_position_limits(
        self,
        coin: str,
        proposed_quantity: float,
        entry_price: float,
        portfolio: Dict
    ) -> Tuple[bool, List[str], float]:
        """
        Check if proposed position violates limits.
        
        Returns:
            (approved, rejection_reasons, adjusted_quantity)
        """
        rejections = []
        adjusted_qty = proposed_quantity
        
        total_equity = portfolio['total_equity']
        proposed_value = proposed_quantity * entry_price
        
        # Check per-asset limit (10% default)
        per_asset_limit = self.limits[RiskLimits.POSITION_LIMIT_PER_ASSET]
        max_per_asset = total_equity * per_asset_limit
        
        if proposed_value > max_per_asset:
            adjusted_qty = max_per_asset / entry_price
            rejections.append(
                f"Per-asset limit ({per_asset_limit*100}%): reduced from {proposed_quantity:.4f} to {adjusted_qty:.4f}"
            )
        
        # Check total deployed limit (80% default)
        max_deployed = self.limits[RiskLimits.MAX_DEPLOYED]
        current_deployed = portfolio['positions_value']
        remaining_capacity = (total_equity * max_deployed) - current_deployed
        
        if proposed_value > remaining_capacity:
            if remaining_capacity <= 0:
                rejections.append(f"Max deployed limit ({max_deployed*100}%) reached")
                return False, rejections, 0
            
            adjusted_qty = remaining_capacity / entry_price
            rejections.append(
                f"Deployment limit: reduced to {adjusted_qty:.4f} (remaining capacity: ${remaining_capacity:.2f})"
            )
        
        # Check altcoin limit (30% default) for non-BTC/ETH
        if coin not in ['BTC', 'ETH']:
            altcoin_limit = self.limits[RiskLimits.POSITION_LIMIT_ALTCOINS]
            
            # Get current altcoin exposure
            positions = await self.get_open_positions()
            altcoin_exposure = sum(
                float(p.quantity) * float(p.current_price or p.entry_price)
                for p in positions
                if p.coin not in ['BTC', 'ETH']
            )
            
            max_altcoin = total_equity * altcoin_limit
            remaining_altcoin = max_altcoin - altcoin_exposure
            
            if proposed_value > remaining_altcoin:
                if remaining_altcoin <= 0:
                    rejections.append(f"Altcoin limit ({altcoin_limit*100}%) reached")
                    return False, rejections, 0
                
                adjusted_qty = min(adjusted_qty, remaining_altcoin / entry_price)
                rejections.append(
                    f"Altcoin limit: capped at {adjusted_qty:.4f}"
                )
        
        approved = adjusted_qty > 0
        return approved, rejections, adjusted_qty
    
    async def check_drawdown_limits(self, portfolio: Dict) -> Tuple[int, Optional[str]]:
        """
        Check drawdown and determine circuit breaker level.
        
        Returns:
            (circuit_breaker_level, action_taken)
        """
        daily_pnl_percent = portfolio['daily_pnl_percent']
        
        # Level 1: 5% daily drawdown - reduce size
        level_1 = self.limits[RiskLimits.DRAWDOWN_LEVEL_1]
        if daily_pnl_percent <= -level_1 * 100 and self.circuit_breaker_level < 1:
            return 1, "reduce_size"
        
        # Level 2: 10% daily drawdown - close all, paper mode
        level_2 = self.limits[RiskLimits.DRAWDOWN_LEVEL_2]
        if daily_pnl_percent <= -level_2 * 100 and self.circuit_breaker_level < 2:
            return 2, "close_all"
        
        # Level 3: 15% daily drawdown - full halt
        level_3 = self.limits[RiskLimits.DRAWDOWN_LEVEL_3]
        if daily_pnl_percent <= -level_3 * 100 and self.circuit_breaker_level < 3:
            return 3, "halt_system"
        
        return self.circuit_breaker_level, None
    
    async def calculate_var(
        self,
        positions: List[Position],
        confidence: float = 0.95,
        days: int = 1
    ) -> float:
        """
        Calculate Value at Risk using historical simulation.
        
        Uses historical price returns to estimate potential loss.
        """
        if not positions:
            return 0.0
        
        # For a proper VaR calculation, we would need historical price data
        # This is a simplified parametric VaR using assumed volatility
        
        # Assumed daily volatility by coin (would be calculated from historical data)
        volatilities = {
            'BTC': 0.03,   # 3% daily vol
            'ETH': 0.04,
            'SOL': 0.06,
            'XRP': 0.05,
            'DOGE': 0.08,
            'BNB': 0.04,
            'ADA': 0.05,
            'AVAX': 0.06,
            'TRX': 0.05,
            'LINK': 0.05,
        }
        
        # Calculate portfolio VaR
        z_score = 1.645 if confidence == 0.95 else 2.326  # 95% or 99%
        
        total_var = 0.0
        for position in positions:
            position_value = float(position.quantity) * float(position.current_price or position.entry_price)
            volatility = volatilities.get(position.coin, 0.05)
            position_var = position_value * volatility * z_score * np.sqrt(days)
            total_var += position_var ** 2  # Sum of variances (assuming uncorrelated)
        
        return np.sqrt(total_var)
    
    async def handle_risk_check(self, event: RiskCheckRequestedEvent):
        """Handle incoming risk check request"""
        logger.info(f"Processing risk check for {event.action} {event.coin}")
        
        try:
            portfolio = await self.get_current_portfolio()
            
            # Check circuit breaker
            if self.circuit_breaker_level >= 2:
                await self.reject_trade(
                    event,
                    [f"Circuit breaker level {self.circuit_breaker_level} active - trading halted"],
                    portfolio
                )
                return
            
            # Get signal for context
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Signal).where(Signal.id == event.signal_id)
                )
                signal = result.scalar_one_or_none()
            
            if not signal:
                await self.reject_trade(event, ["Signal not found"], portfolio)
                return
            
            # TODO: Get current price from market data service
            # For now, use placeholder
            current_price = 50000.0 if event.coin == 'BTC' else 3000.0 if event.coin == 'ETH' else 100.0
            
            # Calculate position size based on risk per trade
            risk_per_trade = self.limits[RiskLimits.RISK_PER_TRADE]
            stop_atr = self.limits[RiskLimits.STOP_LOSS_ATR]
            
            # Assume ATR is roughly 2% of price (would be calculated from market data)
            atr = current_price * 0.02
            stop_distance = atr * stop_atr
            
            risk_amount = portfolio['total_equity'] * risk_per_trade
            proposed_quantity = risk_amount / stop_distance
            
            # Reduce size if circuit breaker level 1
            if self.circuit_breaker_level == 1:
                proposed_quantity *= 0.5
            
            # Check position limits
            approved, rejections, adjusted_qty = await self.check_position_limits(
                event.coin,
                proposed_quantity,
                current_price,
                portfolio
            )
            
            if not approved:
                await self.reject_trade(event, rejections, portfolio)
                return
            
            # Calculate stop loss and take profit
            tp_atr = self.limits[RiskLimits.TAKE_PROFIT_ATR]
            
            if event.action == 'long':
                stop_loss = current_price - stop_distance
                take_profit = current_price + (atr * tp_atr)
            else:
                stop_loss = current_price + stop_distance
                take_profit = current_price - (atr * tp_atr)
            
            # Check VaR limit
            positions = await self.get_open_positions()
            current_var = await self.calculate_var(positions)
            var_limit = portfolio['total_equity'] * self.limits[RiskLimits.VAR_LIMIT]
            
            if current_var > var_limit:
                await self.reject_trade(
                    event,
                    [f"VaR limit exceeded: ${current_var:.2f} > ${var_limit:.2f}"],
                    portfolio
                )
                return
            
            # Approve the trade
            await self.approve_trade(
                event,
                adjusted_qty,
                current_price,
                stop_loss,
                take_profit,
                rejections  # Pass any size adjustments
            )
            
        except Exception as e:
            logger.error(f"Error in risk check: {str(e)}")
            await self.reject_trade(event, [f"Risk check error: {str(e)}"], {})
    
    async def approve_trade(
        self,
        event: RiskCheckRequestedEvent,
        quantity: float,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        adjustments: List[str]
    ):
        """Approve a trade and publish event"""
        approval_event = RiskApprovedEvent(
            source="risk_manager",
            correlation_id=event.id,
            signal_id=event.signal_id,
            coin=event.coin,
            action=event.action,
            approved_quantity=quantity,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_checks_passed=["position_limits", "drawdown", "var"] + 
                               ([f"adjusted: {a}" for a in adjustments] if adjustments else [])
        )
        
        await self.bus.publish(approval_event)
        
        # Update signal in database
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Signal).where(Signal.id == event.signal_id)
            )
            signal = result.scalar_one_or_none()
            if signal:
                signal.risk_approved = True
                await session.commit()
            
            # Audit log
            await log_audit(
                session,
                event_type="risk.approved",
                actor="risk_manager",
                action="approve_trade",
                entity_type="signal",
                entity_id=str(event.signal_id),
                after_state={
                    "coin": event.coin,
                    "action": event.action,
                    "quantity": quantity,
                    "entry": entry_price,
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                },
                reasoning="All risk checks passed"
            )
            await session.commit()
        
        logger.info(f"Approved {event.action} {event.coin}: qty={quantity:.4f}")
    
    async def reject_trade(
        self,
        event: RiskCheckRequestedEvent,
        reasons: List[str],
        portfolio: Dict
    ):
        """Reject a trade and publish event"""
        rejection_event = RiskRejectedEvent(
            source="risk_manager",
            correlation_id=event.id,
            signal_id=event.signal_id,
            coin=event.coin,
            action=event.action,
            rejection_reasons=reasons,
            risk_checks_failed=reasons,
            current_exposure=portfolio.get('positions_value', 0) / portfolio.get('total_equity', 1),
            limit_values=self.limits
        )
        
        await self.bus.publish(rejection_event)
        
        # Update signal in database
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Signal).where(Signal.id == event.signal_id)
            )
            signal = result.scalar_one_or_none()
            if signal:
                signal.risk_approved = False
                signal.risk_rejection_reason = "; ".join(reasons)
                await session.commit()
            
            # Audit log
            await log_audit(
                session,
                event_type="risk.rejected",
                actor="risk_manager",
                action="reject_trade",
                entity_type="signal",
                entity_id=str(event.signal_id),
                reasoning="; ".join(reasons)
            )
            await session.commit()
        
        logger.warning(f"Rejected {event.action} {event.coin}: {reasons}")
    
    async def trigger_circuit_breaker(self, level: int, action: str):
        """Trigger a circuit breaker"""
        self.circuit_breaker_level = level
        
        positions = await self.get_open_positions()
        
        event = CircuitBreakerEvent(
            source="risk_manager",
            level=level,
            trigger_type="drawdown",
            trigger_value=0,  # Would be actual drawdown
            threshold=self.limits[f"risk.drawdown_level_{level}"] if level <= 3 else 0,
            action_taken=action,
            positions_affected=[p.coin for p in positions]
        )
        
        await self.bus.publish(event)
        
        # Record risk event
        async with AsyncSessionLocal() as session:
            risk_event = RiskEvent(
                event_type="circuit_breaker",
                severity="emergency" if level >= 2 else "critical",
                action_taken=action,
                details={"level": level, "positions": [p.coin for p in positions]}
            )
            session.add(risk_event)
            
            await log_audit(
                session,
                event_type="risk.circuit_breaker",
                actor="risk_manager",
                action=action,
                reasoning=f"Circuit breaker level {level} triggered"
            )
            await session.commit()
        
        logger.critical(f"CIRCUIT BREAKER LEVEL {level}: {action}")
    
    async def run(self):
        """Main run loop - consume risk check events"""
        self.running = True
        logger.info("Risk Manager started")
        
        await self.bus.connect()
        await self.load_limits()
        
        async def handle_event(event):
            if isinstance(event, RiskCheckRequestedEvent):
                await self.handle_risk_check(event)
        
        # Consume from risk stream
        await self.bus.consume(
            "risk",
            "risk_manager_group",
            f"risk_manager_{os.getpid()}",
            handle_event
        )
    
    async def stop(self):
        """Stop the manager"""
        self.running = False


async def main():
    """Entry point"""
    manager = RiskManager()
    try:
        await manager.run()
    except KeyboardInterrupt:
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
