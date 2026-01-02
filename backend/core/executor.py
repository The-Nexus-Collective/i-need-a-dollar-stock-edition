"""
Order Executor - Binance integration with paper/live modes
"""

import asyncio
import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
from uuid import uuid4

import ccxt.async_support as ccxt

from events import (
    get_event_bus,
    RiskApprovedEvent,
    OrderSubmittedEvent,
    OrderFilledEvent,
    PositionOpenedEvent,
    PositionClosedEvent,
    PositionUpdatedEvent,
    PortfolioSnapshotEvent,
    deserialize_event,
)
from models import AsyncSessionLocal, Position, Trade, PortfolioSnapshot
from models.audit import log_audit

logger = logging.getLogger(__name__)


class BinanceClient:
    """Binance exchange client for market data and execution"""
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True):
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Use futures for long/short
                'adjustForTimeDifference': True,
            }
        })
        
        if testnet:
            self.exchange.set_sandbox_mode(True)
    
    async def get_price(self, symbol: str) -> float:
        """Get current price for a symbol"""
        try:
            ticker = await self.exchange.fetch_ticker(f"{symbol}/USDT")
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            raise
    
    async def get_atr(self, symbol: str, timeframe: str = '1h', periods: int = 14) -> float:
        """Calculate ATR for a symbol"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                f"{symbol}/USDT",
                timeframe=timeframe,
                limit=periods + 1
            )
            
            if len(ohlcv) < periods:
                raise ValueError(f"Insufficient data for ATR: {len(ohlcv)} bars")
            
            tr_values = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]
                
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)
            
            return sum(tr_values) / len(tr_values)
            
        except Exception as e:
            logger.error(f"Error calculating ATR for {symbol}: {e}")
            # Return fallback ATR (2% of assumed price)
            return 100.0
    
    async def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float = None
    ) -> Dict:
        """Place an order on Binance"""
        try:
            params = {}
            
            if order_type == 'market':
                order = await self.exchange.create_market_order(
                    f"{symbol}/USDT",
                    side,
                    quantity
                )
            else:
                order = await self.exchange.create_limit_order(
                    f"{symbol}/USDT",
                    side,
                    quantity,
                    price
                )
            
            return order
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise
    
    async def close(self):
        await self.exchange.close()


class PaperExecutor:
    """Paper trading executor - simulates order execution"""
    
    def __init__(self, binance: BinanceClient):
        self.binance = binance
        self.paper_fills: Dict[str, Dict] = {}
    
    async def execute_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float = None
    ) -> Dict:
        """Simulate order execution at current market price"""
        try:
            # Get current price if not specified
            if price is None:
                price = await self.binance.get_price(symbol)
            
            # Simulate small slippage (0.05%)
            slippage = 0.0005
            if side == 'buy':
                fill_price = price * (1 + slippage)
            else:
                fill_price = price * (1 - slippage)
            
            # Simulate fee (0.04% for futures)
            fee = quantity * fill_price * 0.0004
            
            fill = {
                'order_id': order_id,
                'exchange_order_id': f"PAPER_{uuid4().hex[:8].upper()}",
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'fill_price': fill_price,
                'fee': fee,
                'fee_currency': 'USDT',
                'executed_at': datetime.utcnow(),
                'status': 'filled',
            }
            
            self.paper_fills[order_id] = fill
            
            logger.info(
                f"PAPER FILL: {side.upper()} {quantity:.4f} {symbol} @ ${fill_price:.2f} "
                f"(fee: ${fee:.4f})"
            )
            
            return fill
            
        except Exception as e:
            logger.error(f"Paper execution error: {e}")
            raise


class OrderExecutor:
    """
    Order Executor - Handles trade execution in paper or live mode.
    
    Workflow:
    1. Consume risk-approved events
    2. Execute orders (paper or live)
    3. Create/update positions
    4. Monitor positions for stop/target
    5. Publish execution events
    """
    
    def __init__(self):
        self.bus = get_event_bus()
        self.mode = os.getenv('MODE', 'paper').lower()
        
        self.binance = BinanceClient(
            api_key=os.getenv('BINANCE_API_KEY'),
            api_secret=os.getenv('BINANCE_API_SECRET'),
            testnet=self.mode == 'paper'
        )
        
        self.paper_executor = PaperExecutor(self.binance)
        
        # Portfolio state
        self.cash = 10000.0
        self.running = False
    
    async def load_portfolio_state(self):
        """Load current portfolio state from database"""
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select
            
            result = await session.execute(
                select(PortfolioSnapshot)
                .order_by(PortfolioSnapshot.timestamp.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            
            if snapshot:
                self.cash = float(snapshot.cash)
            else:
                self.cash = 10000.0
    
    async def handle_risk_approved(self, event: RiskApprovedEvent):
        """Handle risk-approved trade event"""
        logger.info(f"Executing approved trade: {event.action} {event.coin}")
        
        try:
            # Generate order ID
            order_id = uuid4()
            
            # Determine side
            side = 'buy' if event.action == 'long' else 'sell'
            
            # Publish order submitted event
            submitted_event = OrderSubmittedEvent(
                source="executor",
                correlation_id=event.id,
                order_id=order_id,
                signal_id=event.signal_id,
                coin=event.coin,
                side=side,
                order_type='market',
                quantity=event.approved_quantity,
                is_paper=self.mode == 'paper'
            )
            await self.bus.publish(submitted_event)
            
            # Execute order
            if self.mode == 'paper':
                fill = await self.paper_executor.execute_order(
                    str(order_id),
                    event.coin,
                    side,
                    event.approved_quantity,
                    event.entry_price
                )
            else:
                # Live execution
                order = await self.binance.place_order(
                    event.coin,
                    side,
                    'market',
                    event.approved_quantity
                )
                fill = {
                    'order_id': str(order_id),
                    'exchange_order_id': order['id'],
                    'symbol': event.coin,
                    'side': side,
                    'quantity': order['filled'],
                    'fill_price': float(order['average']),
                    'fee': float(order['fee']['cost']) if order.get('fee') else 0,
                    'fee_currency': order['fee']['currency'] if order.get('fee') else 'USDT',
                    'executed_at': datetime.utcnow(),
                    'status': 'filled',
                }
            
            # Create position
            position = await self.create_position(
                event,
                fill
            )
            
            # Create trade record
            await self.create_trade(
                event,
                fill,
                position.id
            )
            
            # Update cash
            position_value = fill['quantity'] * fill['fill_price']
            self.cash -= position_value + fill['fee']
            
            # Publish order filled event
            filled_event = OrderFilledEvent(
                source="executor",
                correlation_id=event.id,
                order_id=order_id,
                exchange_order_id=fill.get('exchange_order_id'),
                position_id=position.id,
                coin=event.coin,
                side=side,
                quantity=fill['quantity'],
                fill_price=fill['fill_price'],
                fee=fill['fee'],
                fee_currency=fill['fee_currency'],
                is_paper=self.mode == 'paper'
            )
            await self.bus.publish(filled_event)
            
            # Publish position opened event
            opened_event = PositionOpenedEvent(
                source="executor",
                position_id=position.id,
                coin=event.coin,
                side=event.action,
                quantity=fill['quantity'],
                entry_price=fill['fill_price'],
                stop_loss=event.stop_loss,
                take_profit=event.take_profit,
                signal_id=event.signal_id
            )
            await self.bus.publish(opened_event)
            
            # Update portfolio snapshot
            await self.update_portfolio_snapshot()
            
            logger.info(
                f"Position opened: {event.action} {event.coin} "
                f"qty={fill['quantity']:.4f} @ ${fill['fill_price']:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Execution error: {str(e)}")
    
    async def create_position(
        self,
        event: RiskApprovedEvent,
        fill: Dict
    ) -> Position:
        """Create a new position in the database"""
        async with AsyncSessionLocal() as session:
            position = Position(
                coin=event.coin,
                side=event.action,
                quantity=Decimal(str(fill['quantity'])),
                entry_price=Decimal(str(fill['fill_price'])),
                current_price=Decimal(str(fill['fill_price'])),
                stop_loss=Decimal(str(event.stop_loss)),
                take_profit=Decimal(str(event.take_profit)),
                status='open'
            )
            
            session.add(position)
            await session.commit()
            await session.refresh(position)
            
            # Audit log
            await log_audit(
                session,
                event_type="position.opened",
                actor="executor",
                action="create_position",
                entity_type="position",
                entity_id=str(position.id),
                after_state=position.to_dict(),
                reasoning=f"Signal {event.signal_id} approved and executed"
            )
            await session.commit()
            
            return position
    
    async def create_trade(
        self,
        event: RiskApprovedEvent,
        fill: Dict,
        position_id
    ) -> Trade:
        """Create a trade record in the database"""
        async with AsyncSessionLocal() as session:
            trade = Trade(
                position_id=position_id,
                order_id=fill['order_id'],
                exchange_order_id=fill.get('exchange_order_id'),
                coin=event.coin,
                side='buy' if event.action == 'long' else 'sell',
                order_type='market',
                quantity=Decimal(str(fill['quantity'])),
                price=Decimal(str(fill['fill_price'])),
                fee=Decimal(str(fill['fee'])),
                fee_currency=fill['fee_currency'],
                status='filled',
                is_paper=self.mode == 'paper',
                executed_at=fill['executed_at']
            )
            
            session.add(trade)
            await session.commit()
            await session.refresh(trade)
            
            return trade
    
    async def monitor_positions(self):
        """Monitor open positions for stop loss / take profit"""
        while self.running:
            try:
                async with AsyncSessionLocal() as session:
                    from sqlalchemy import select
                    
                    result = await session.execute(
                        select(Position).where(Position.status == 'open')
                    )
                    positions = result.scalars().all()
                    
                    for position in positions:
                        try:
                            # Get current price
                            current_price = await self.binance.get_price(position.coin)
                            
                            # Update position
                            position.current_price = Decimal(str(current_price))
                            pnl = position.calculate_pnl(position.current_price)
                            position.unrealized_pnl = pnl
                            
                            # Check stop loss
                            if position.check_stop_loss(position.current_price):
                                await self.close_position(
                                    session,
                                    position,
                                    current_price,
                                    'stop_loss'
                                )
                            # Check take profit
                            elif position.check_take_profit(position.current_price):
                                await self.close_position(
                                    session,
                                    position,
                                    current_price,
                                    'take_profit'
                                )
                            else:
                                # Just update
                                await session.commit()
                                
                                # Publish update event
                                update_event = PositionUpdatedEvent(
                                    source="executor",
                                    position_id=position.id,
                                    coin=position.coin,
                                    current_price=current_price,
                                    unrealized_pnl=float(pnl),
                                    unrealized_pnl_percent=float(position.calculate_pnl_percent(position.current_price)),
                                    distance_to_stop=abs(current_price - float(position.stop_loss)),
                                    distance_to_target=abs(current_price - float(position.take_profit))
                                )
                                await self.bus.publish(update_event)
                                
                        except Exception as e:
                            logger.error(f"Error monitoring position {position.id}: {e}")
                
                # Update portfolio snapshot periodically
                await self.update_portfolio_snapshot()
                
            except Exception as e:
                logger.error(f"Position monitoring error: {e}")
            
            await asyncio.sleep(60)  # Check every minute
    
    async def close_position(
        self,
        session,
        position: Position,
        exit_price: float,
        reason: str
    ):
        """Close a position"""
        # Calculate P&L
        pnl = position.calculate_pnl(Decimal(str(exit_price)))
        pnl_percent = position.calculate_pnl_percent(Decimal(str(exit_price)))
        
        # Update position
        position.status = 'closed'
        position.current_price = Decimal(str(exit_price))
        position.realized_pnl = pnl
        position.closed_at = datetime.utcnow()
        
        # Update cash
        position_value = float(position.quantity) * exit_price
        self.cash += position_value
        
        await session.commit()
        
        # Create closing trade
        trade = Trade(
            position_id=position.id,
            order_id=str(uuid4()),
            coin=position.coin,
            side='sell' if position.side == 'long' else 'buy',
            order_type='market',
            quantity=position.quantity,
            price=Decimal(str(exit_price)),
            fee=Decimal('0'),
            status='filled',
            is_paper=self.mode == 'paper',
            executed_at=datetime.utcnow()
        )
        session.add(trade)
        
        # Audit log
        await log_audit(
            session,
            event_type="position.closed",
            actor="executor",
            action="close_position",
            entity_type="position",
            entity_id=str(position.id),
            before_state={"status": "open"},
            after_state=position.to_dict(),
            reasoning=f"Position closed: {reason}"
        )
        await session.commit()
        
        # Publish closed event
        closed_event = PositionClosedEvent(
            source="executor",
            position_id=position.id,
            coin=position.coin,
            side=position.side,
            quantity=float(position.quantity),
            entry_price=float(position.entry_price),
            exit_price=exit_price,
            realized_pnl=float(pnl),
            realized_pnl_percent=float(pnl_percent),
            close_reason=reason,
            duration_seconds=int((position.closed_at - position.opened_at).total_seconds())
        )
        await self.bus.publish(closed_event)
        
        logger.info(
            f"CLOSED {position.coin}: {reason.upper()} | "
            f"PnL: ${float(pnl):.2f} ({float(pnl_percent):.2f}%)"
        )
    
    async def update_portfolio_snapshot(self):
        """Create a portfolio snapshot"""
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select, func
                
                # Get open positions
                result = await session.execute(
                    select(Position).where(Position.status == 'open')
                )
                positions = result.scalars().all()
                
                # Calculate values
                positions_value = sum(
                    float(p.quantity) * float(p.current_price or p.entry_price)
                    for p in positions
                )
                unrealized_pnl = sum(
                    float(p.unrealized_pnl or 0)
                    for p in positions
                )
                
                # Get realized P&L
                result = await session.execute(
                    select(func.sum(Position.realized_pnl))
                    .where(Position.status == 'closed')
                )
                realized_pnl = float(result.scalar() or 0)
                
                # Get trade stats
                result = await session.execute(
                    select(func.count(Position.id))
                    .where(Position.status == 'closed')
                )
                total_trades = result.scalar() or 0
                
                result = await session.execute(
                    select(func.count(Position.id))
                    .where(Position.status == 'closed')
                    .where(Position.realized_pnl > 0)
                )
                winning_trades = result.scalar() or 0
                
                total_equity = self.cash + positions_value
                
                # Create snapshot
                snapshot = PortfolioSnapshot(
                    total_equity=Decimal(str(total_equity)),
                    cash=Decimal(str(self.cash)),
                    positions_value=Decimal(str(positions_value)),
                    unrealized_pnl=Decimal(str(unrealized_pnl)),
                    realized_pnl=Decimal(str(realized_pnl)),
                    daily_pnl=Decimal('0'),  # Would calculate from start of day
                    daily_pnl_percent=Decimal('0'),
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=total_trades - winning_trades
                )
                
                session.add(snapshot)
                await session.commit()
                
                # Publish event
                event = PortfolioSnapshotEvent(
                    source="executor",
                    total_equity=total_equity,
                    cash=self.cash,
                    positions_value=positions_value,
                    unrealized_pnl=unrealized_pnl,
                    realized_pnl=realized_pnl,
                    daily_pnl=0,
                    daily_pnl_percent=0,
                    total_trades=total_trades,
                    winning_trades=winning_trades,
                    losing_trades=total_trades - winning_trades,
                    open_positions=len(positions)
                )
                await self.bus.publish(event)
                
        except Exception as e:
            logger.error(f"Portfolio snapshot error: {e}")
    
    async def run(self):
        """Main run loop"""
        self.running = True
        logger.info(f"Order Executor started in {self.mode.upper()} mode")
        
        await self.bus.connect()
        await self.load_portfolio_state()
        
        # Start position monitoring in background
        monitor_task = asyncio.create_task(self.monitor_positions())
        
        async def handle_event(event):
            if isinstance(event, RiskApprovedEvent):
                await self.handle_risk_approved(event)
        
        try:
            # Consume from risk stream (for approved trades)
            await self.bus.consume(
                "risk",
                "executor_group",
                f"executor_{os.getpid()}",
                handle_event
            )
        finally:
            monitor_task.cancel()
            await self.binance.close()
    
    async def stop(self):
        """Stop the executor"""
        self.running = False


async def main():
    """Entry point"""
    executor = OrderExecutor()
    try:
        await executor.run()
    except KeyboardInterrupt:
        await executor.stop()


if __name__ == "__main__":
    asyncio.run(main())
