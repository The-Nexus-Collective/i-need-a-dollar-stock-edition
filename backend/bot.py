#!/usr/bin/env python3
"""
Main Trading Bot - Real-time sentiment trading with live market data

Integrates:
- Binance WebSocket for live prices and order book
- Grok AI for sentiment analysis
- Market simulator for realistic paper fills
- Persistent account state
- Real-time equity calculation
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, time as dt_time, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import pytz

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.websocket_manager import BinanceWSManager, get_ws_manager, start_ws_manager
from core.price_cache import init_caches, get_price_cache, get_book_cache
from core.account import TradingAccount, init_trading_account, AccountPosition
from core.market_simulator import MarketSimulator, get_market_simulator, Fill
from core.equity_calculator import EquityCalculator, init_equity_calculator
from core.strategy import StrategyEngine, run_trading_cycle, TradingDecision, CoinTrade
from core.signal_engine import TOP_COINS

from models import AsyncSessionLocal, Position, Trade
from sqlalchemy import select, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MODE = os.getenv('MODE', 'paper').lower()
FLATTEN_TIME_CET = os.getenv('FLATTEN_TIME_CET', '23:55')
CET = pytz.timezone('CET')

# AGGRESSIVE MODE - 15 minute cycles (was hourly)
CYCLE_MINUTES = int(os.getenv('CYCLE_MINUTES', '15'))
FORCE_TRADE = os.getenv('FORCE_TRADE', 'false').lower() == 'true'


class TradingBot:
    """
    AGGRESSIVE Trading Bot - High-Frequency Paper Testing
    
    Features:
    - Live price updates via WebSocket
    - Realistic paper trading with order book slippage
    - Persistent account state
    - 23:55 CET daily flatten
    - 15-minute strategy cycles (was hourly)
    - FORCE_TRADE mode for 100+ trades/day
    - 5-8 coins per cycle, 80-90% deployment
    """
    
    def __init__(self):
        self.running = False
        
        # Components (initialized in start())
        self.ws_manager: Optional[BinanceWSManager] = None
        self.account: Optional[TradingAccount] = None
        self.simulator: Optional[MarketSimulator] = None
        self.equity_calc: Optional[EquityCalculator] = None
        self.strategy: Optional[StrategyEngine] = None
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing trading bot components...")
        
        # 1. Start WebSocket manager for live prices
        self.ws_manager = get_ws_manager()
        asyncio.create_task(self.ws_manager.start())
        
        # Wait for first prices
        await asyncio.sleep(3)
        logger.info(f"WebSocket connected. Prices: {len(self.ws_manager.get_all_prices())}")
        
        # 2. Initialize price/book caches
        await init_caches()
        
        # 3. Load account state
        self.account = await init_trading_account()
        logger.info(f"Account loaded: ${self.account.state.balance_usdt:,.2f}")
        
        # 4. Initialize market simulator
        self.simulator = get_market_simulator()
        
        # 5. Start equity calculator
        self.equity_calc = await init_equity_calculator()
        
        # 6. Initialize strategy
        self.strategy = StrategyEngine()
        
        logger.info("All components initialized")
    
    async def run_trading_cycle(self):
        """
        Execute one trading cycle.
        
        AGGRESSIVE MODE: Handles 5-8 coin trades per cycle
        """
        logger.info("=" * 60)
        logger.info(f"AGGRESSIVE Trading Cycle (FORCE_TRADE={FORCE_TRADE})")
        logger.info("=" * 60)
        
        try:
            # Run strategy to get decision with multiple trades
            decision = await run_trading_cycle()
            
            if decision.decision in ['trade', 'force_trade']:
                # AGGRESSIVE: Handle multiple coin trades (5-8)
                logger.info(f"Processing {len(decision.trades)} trades, {decision.rebalance_count} rebalances")
                
                # Get coins we're trading this cycle
                trading_coins = {t.coin for t in decision.trades}
                
                # Close positions not in new trading set
                for coin in list(self.account.state.positions.keys()):
                    if coin not in trading_coins:
                        await self.close_position(coin, 'not_in_top_selection')
                
                # Process each trade
                for trade in decision.trades:
                    current_pos = self.account.get_position(trade.coin)
                    
                    # Skip if already holding same direction
                    if current_pos and current_pos.side == trade.side and not trade.is_rebalance:
                        logger.info(f"Already {trade.side} {trade.coin}, holding")
                        continue
                    
                    # Close if reversing
                    if current_pos and current_pos.side != trade.side:
                        await self.close_position(trade.coin, 'reverse_signal')
                    
                    # Close if rebalancing (adjust size)
                    if current_pos and trade.is_rebalance:
                        await self.close_position(trade.coin, 'rebalance')
                    
                    # Open new/rebalanced position
                    await self.open_position_from_trade(trade)
                
                logger.info(
                    f"Cycle complete: {decision.trades_this_cycle} trades | "
                    f"Deployment: {decision.deployment_percent*100:.1f}%"
                )
            
            elif decision.decision in ['filtered', 'flat']:
                # Close all positions only if no candidates at all
                if not decision.all_analyses:
                    for coin in list(self.account.state.positions.keys()):
                        await self.close_position(coin, decision.filter_reason or 'flat')
                else:
                    logger.info(f"Filtered: {decision.filter_reason} - keeping positions")
            
            # Save account state
            await self.account.save_state()
            
        except Exception as e:
            logger.error(f"Trading cycle error: {e}")
            import traceback
            traceback.print_exc()
    
    async def open_position(self, decision: TradingDecision):
        """Open a new position"""
        if not decision.selected_coin or not decision.position_size:
            return
        
        # Execute via market simulator
        fill = await self.simulator.execute_market_order(
            coin=decision.selected_coin,
            side='buy' if decision.side == 'long' else 'sell',
            quantity=decision.position_size
        )
        
        logger.info(
            f"OPENED: {decision.side.upper()} {decision.position_size:.4f} {decision.selected_coin} "
            f"@ ${fill.fill_price:,.2f} (slip: {fill.slippage_bps:.2f}bps, fee: ${fill.fee:.2f})"
        )
        
        # Create position in database
        async with AsyncSessionLocal() as session:
            position = Position(
                coin=decision.selected_coin,
                side=decision.side,
                quantity=Decimal(str(decision.position_size)),
                entry_price=Decimal(str(fill.fill_price)),
                current_price=Decimal(str(fill.fill_price)),
                stop_loss=Decimal(str(decision.stop_loss)) if decision.stop_loss else None,
                take_profit=Decimal(str(decision.take_profit)) if decision.take_profit else None,
                status='open'
            )
            session.add(position)
            await session.commit()
            await session.refresh(position)
            
            # Create trade record
            trade = Trade(
                position_id=position.id,
                order_id=fill.order_id,
                exchange_order_id=fill.order_id,
                coin=decision.selected_coin,
                side='buy' if decision.side == 'long' else 'sell',
                order_type='market',
                quantity=Decimal(str(decision.position_size)),
                price=Decimal(str(fill.fill_price)),
                fee=Decimal(str(fill.fee)),
                fee_currency='USDT',
                slippage_cost=Decimal(str(fill.slippage_cost)),
                fee_rate=Decimal(str(fill.fee_rate)),
                fill_vwap=Decimal(str(fill.fill_price)),
                book_depth_used=fill.book_depth_used,
                total_cost=Decimal(str(fill.total_cost)),
                status='filled',
                is_paper=True,
                executed_at=fill.timestamp
            )
            session.add(trade)
            await session.commit()
        
        # Update account
        self.account.add_position(AccountPosition(
            position_id=str(position.id),
            coin=decision.selected_coin,
            side=decision.side,
            quantity=decision.position_size,
            entry_price=fill.fill_price,
            current_price=fill.fill_price,
            stop_loss=decision.stop_loss or 0,
            take_profit=decision.take_profit or 0
        ))
        
        # Deduct cost from balance
        self.account.state.balance_usdt -= fill.fee
        self.account.state.total_fees_paid += fill.fee
        self.account.state.total_slippage_cost += fill.slippage_cost
    
    async def open_position_from_trade(self, trade: CoinTrade):
        """Open a position from a CoinTrade object (multi-coin support)"""
        if not trade.coin or not trade.position_size:
            return
        
        # Execute via market simulator
        fill = await self.simulator.execute_market_order(
            coin=trade.coin,
            side='buy' if trade.side == 'long' else 'sell',
            quantity=trade.position_size
        )
        
        trade_type = "REBAL" if trade.is_rebalance else "OPEN"
        logger.info(
            f"{trade_type}: {trade.side.upper()} {trade.position_size:.4f} {trade.coin} "
            f"@ ${fill.fill_price:,.2f} (lev: {trade.leverage}x, slip: {fill.slippage_bps:.2f}bps)"
        )
        
        # Create position in database
        async with AsyncSessionLocal() as session:
            position = Position(
                coin=trade.coin,
                side=trade.side,
                quantity=Decimal(str(trade.position_size)),
                entry_price=Decimal(str(fill.fill_price)),
                current_price=Decimal(str(fill.fill_price)),
                stop_loss=Decimal(str(trade.stop_loss)) if trade.stop_loss else None,
                take_profit=Decimal(str(trade.take_profit)) if trade.take_profit else None,
                leverage=Decimal(str(trade.leverage)),
                status='open'
            )
            session.add(position)
            await session.commit()
            await session.refresh(position)
            
            # Create trade record
            db_trade = Trade(
                position_id=position.id,
                order_id=fill.order_id,
                exchange_order_id=fill.order_id,
                coin=trade.coin,
                side='buy' if trade.side == 'long' else 'sell',
                order_type='market',
                quantity=Decimal(str(trade.position_size)),
                price=Decimal(str(fill.fill_price)),
                fee=Decimal(str(fill.fee)),
                fee_currency='USDT',
                slippage_cost=Decimal(str(fill.slippage_cost)),
                fee_rate=Decimal(str(fill.fee_rate)),
                fill_vwap=Decimal(str(fill.fill_price)),
                book_depth_used=fill.book_depth_used,
                total_cost=Decimal(str(fill.total_cost)),
                status='filled',
                is_paper=True,
                executed_at=fill.timestamp
            )
            session.add(db_trade)
            await session.commit()
        
        # Update account
        self.account.add_position(AccountPosition(
            position_id=str(position.id),
            coin=trade.coin,
            side=trade.side,
            quantity=trade.position_size,
            entry_price=fill.fill_price,
            current_price=fill.fill_price,
            stop_loss=trade.stop_loss or 0,
            take_profit=trade.take_profit or 0,
            leverage=trade.leverage
        ))
        
        # Deduct cost from balance
        self.account.state.balance_usdt -= fill.fee
        self.account.state.total_fees_paid += fill.fee
        self.account.state.total_slippage_cost += fill.slippage_cost
    
    async def close_position(self, coin: str, reason: str = 'manual'):
        """Close a position"""
        position = self.account.get_position(coin)
        if not position:
            return
        
        # Get current price
        current_price = get_price_cache().get(coin)
        if not current_price:
            current_price = position.current_price
        
        # Execute close order
        fill = await self.simulator.execute_market_order(
            coin=coin,
            side='sell' if position.side == 'long' else 'buy',
            quantity=position.quantity,
            is_reduce_only=True
        )
        
        # Calculate PnL
        if position.side == 'long':
            pnl = (fill.fill_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - fill.fill_price) * position.quantity
        
        net_pnl = pnl - fill.fee
        is_winner = pnl > 0
        
        logger.info(
            f"CLOSED: {position.side.upper()} {coin} @ ${fill.fill_price:,.2f} | "
            f"Reason: {reason} | PnL: ${pnl:+,.2f} (fee: ${fill.fee:.2f})"
        )
        
        # Update database
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Position).where(
                    Position.coin == coin,
                    Position.status == 'open'
                )
            )
            pos = result.scalar_one_or_none()
            
            if pos:
                pos.status = 'closed'
                pos.current_price = Decimal(str(fill.fill_price))
                pos.realized_pnl = Decimal(str(pnl))
                pos.closed_at = datetime.utcnow()
                
                # Create closing trade
                trade = Trade(
                    position_id=pos.id,
                    order_id=fill.order_id,
                    exchange_order_id=fill.order_id,
                    coin=coin,
                    side='sell' if position.side == 'long' else 'buy',
                    order_type='market',
                    quantity=pos.quantity,
                    price=Decimal(str(fill.fill_price)),
                    fee=Decimal(str(fill.fee)),
                    fee_currency='USDT',
                    slippage_cost=Decimal(str(fill.slippage_cost)),
                    fee_rate=Decimal(str(fill.fee_rate)),
                    fill_vwap=Decimal(str(fill.fill_price)),
                    book_depth_used=fill.book_depth_used,
                    total_cost=Decimal(str(fill.total_cost)),
                    status='filled',
                    is_paper=True,
                    executed_at=fill.timestamp
                )
                session.add(trade)
                await session.commit()
        
        # Update account
        self.account.apply_trade(pnl, fill.fee, fill.slippage_cost, is_winner)
        self.account.remove_position(coin)
    
    async def check_stops(self):
        """Check positions for stop loss / take profit"""
        prices = get_price_cache().get_all()
        
        for coin, position in list(self.account.state.positions.items()):
            current_price = prices.get(coin)
            if not current_price:
                continue
            
            # Update position price
            position.update_pnl(current_price)
            
            # Check stop loss
            if position.stop_loss > 0:
                if position.side == 'long' and current_price <= position.stop_loss:
                    logger.info(f"STOP LOSS triggered: {coin} @ ${current_price:,.2f}")
                    await self.close_position(coin, 'stop_loss')
                    continue
                
                if position.side == 'short' and current_price >= position.stop_loss:
                    logger.info(f"STOP LOSS triggered: {coin} @ ${current_price:,.2f}")
                    await self.close_position(coin, 'stop_loss')
                    continue
            
            # Check take profit
            if position.take_profit > 0:
                if position.side == 'long' and current_price >= position.take_profit:
                    logger.info(f"TAKE PROFIT triggered: {coin} @ ${current_price:,.2f}")
                    await self.close_position(coin, 'take_profit')
                    continue
                
                if position.side == 'short' and current_price <= position.take_profit:
                    logger.info(f"TAKE PROFIT triggered: {coin} @ ${current_price:,.2f}")
                    await self.close_position(coin, 'take_profit')
                    continue
    
    async def flatten_all(self, reason: str = 'end_of_day'):
        """Close all positions"""
        logger.info(f"FLATTEN ALL: {reason}")
        
        for coin in list(self.account.state.positions.keys()):
            await self.close_position(coin, reason)
        
        await self.account.save_state()
    
    def is_flatten_time(self) -> bool:
        """Check if it's 23:55 CET"""
        now_cet = datetime.now(CET)
        hour, minute = map(int, FLATTEN_TIME_CET.split(':'))
        return now_cet.hour == hour and now_cet.minute >= minute
    
    async def health_check_apis(self) -> dict:
        """
        Hourly health check with exponential backoff retry.
        
        Checks:
        - Grok API (xAI)
        - Binance WebSocket/API
        - Database connection
        
        Returns dict with status for each API.
        """
        apis = {
            'grok': self._ping_grok,
            'binance': self._ping_binance,
            'database': self._ping_database
        }
        results = {}
        
        for api_name, ping_func in apis.items():
            for attempt in range(3):  # 3 retries with exponential backoff
                try:
                    await ping_func()
                    results[api_name] = {
                        'status': 'healthy',
                        'attempts': attempt + 1,
                        'timestamp': datetime.utcnow().isoformat()
                    }
                    break
                except Exception as e:
                    wait_time = 2 ** attempt  # 1, 2, 4 seconds
                    logger.warning(
                        f"Health check {api_name} failed (attempt {attempt + 1}/3): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    
                    if attempt == 2:  # Last attempt
                        results[api_name] = {
                            'status': 'unhealthy',
                            'error': str(e),
                            'attempts': 3,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        logger.error(f"Health check FAILED for {api_name}: {e}")
        
        # Log summary
        healthy = sum(1 for r in results.values() if r['status'] == 'healthy')
        logger.info(f"Health check: {healthy}/{len(results)} APIs healthy")
        
        return results
    
    async def _ping_grok(self):
        """Ping Grok/xAI API"""
        from core.signal_engine import get_grok_client
        client = get_grok_client()
        # Just check if we can create the client and API key is set
        if not client._api_key:
            raise ValueError("XAI_API_KEY not configured")
        logger.debug("Grok API: OK")
    
    async def _ping_binance(self):
        """Ping Binance WebSocket connection"""
        if not self.ws_manager or not self.ws_manager.connected:
            raise ConnectionError("Binance WebSocket not connected")
        
        # Check if we're receiving prices
        prices = self.ws_manager.get_all_prices()
        if not prices:
            raise ConnectionError("No price data from Binance")
        
        logger.debug(f"Binance API: OK ({len(prices)} prices)")
    
    async def _ping_database(self):
        """Ping database connection"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1"))
            if not result.scalar():
                raise ConnectionError("Database query failed")
        logger.debug("Database: OK")
    
    async def run(self):
        """Main bot loop - AGGRESSIVE 15-minute cycles"""
        self.running = True
        
        logger.info("=" * 60)
        logger.info(f"AGGRESSIVE Trading Bot starting in {MODE.upper()} mode")
        logger.info(f"Cycle interval: {CYCLE_MINUTES} minutes")
        logger.info(f"FORCE_TRADE: {FORCE_TRADE}")
        logger.info(f"Flatten time: {FLATTEN_TIME_CET} CET")
        logger.info("=" * 60)
        
        # Initialize components
        await self.initialize()
        
        # Run initial health check
        await self.health_check_apis()
        
        # Run initial trading cycle
        await self.run_trading_cycle()
        
        # Track cycle timing
        last_stop_check = datetime.now()
        last_health_check = datetime.now()
        last_cycle_time = datetime.now()
        cycle_interval = timedelta(minutes=CYCLE_MINUTES)
        
        while self.running:
            try:
                now = datetime.now()
                
                # Check for flatten time (23:55 CET)
                if self.is_flatten_time():
                    await self.flatten_all('23:55_cet_flatten')
                    await asyncio.sleep(120)  # Wait past flatten time
                    continue
                
                # Check stops every 5 seconds
                if (now - last_stop_check).total_seconds() >= 5:
                    await self.check_stops()
                    last_stop_check = now
                
                # Hourly health check
                if (now - last_health_check).total_seconds() >= 3600:
                    health = await self.health_check_apis()
                    last_health_check = now
                    
                    # If critical APIs are down, log warning
                    if health.get('binance', {}).get('status') != 'healthy':
                        logger.warning("Binance API unhealthy - trading may be affected")
                
                # AGGRESSIVE: Run strategy every CYCLE_MINUTES (15 min default)
                if now - last_cycle_time >= cycle_interval:
                    logger.info(f"Starting cycle (every {CYCLE_MINUTES} min)")
                    await self.run_trading_cycle()
                    last_cycle_time = now
                
                await asyncio.sleep(1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(30)
        
        # Cleanup
        await self.shutdown()
    
    async def shutdown(self):
        """Clean shutdown"""
        logger.info("Shutting down bot...")
        
        if self.ws_manager:
            await self.ws_manager.stop()
        
        if self.equity_calc:
            await self.equity_calc.stop()
        
        if self.account:
            await self.account.save_state()
        
        logger.info("Bot stopped")
    
    async def stop(self):
        """Stop the bot"""
        self.running = False


async def main():
    """Entry point"""
    bot = TradingBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())