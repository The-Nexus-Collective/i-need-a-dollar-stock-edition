#!/usr/bin/env python3
"""
Stock Trading Bot - Sentiment-driven stock trading with X hype integration

Integrates:
- Yahoo Finance for live stock quotes
- Grok AI for sentiment analysis
- X (Twitter) for hype detection
- Market hours awareness
- IBKR-style paper simulation

Trading Hours: 9:30 AM - 4:00 PM ET
Cycle: Every 4 hours during market hours
Flatten: Before market close
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

import pytz

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.multi_account import get_multi_account_manager, init_multi_account_manager
from core.stock_strategy import StockStrategy, get_stock_strategy
from core.stock_simulator import get_stock_simulator
from core.market_hours import get_market_hours_manager
from core.stock_regime import get_stock_regime_detector
from core.signal_engine import get_grok_client

from models.asset import AssetType, AssetRegistry

from models import AsyncSessionLocal
from sqlalchemy import text

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
ET = pytz.timezone('US/Eastern')


class StockTradingBot:
    """
    Stock trading bot with market hours awareness.
    
    Features:
    - 4-hour cycles during market hours
    - Flatten at close
    - X hype detection for reserved stocks
    - VIX-based regime detection
    - IBKR-style paper trading
    """
    
    def __init__(self):
        self.running = False
        
        # Components
        self.account_manager = None
        self.strategy: Optional[StockStrategy] = None
        self.simulator = None
        self.market_hours = None
        self.regime_detector = None
        self.grok_client = None
        
        # State
        self.last_cycle: Optional[datetime] = None
        self.trades_today = 0
        self.pnl_today = 0.0
    
    async def initialize(self):
        """Initialize all components"""
        logger.info("Initializing stock trading bot...")
        
        # 1. Initialize multi-account manager
        self.account_manager = await init_multi_account_manager()
        stock_account = self.account_manager.get_account(AssetType.STOCK)
        logger.info(f"Stock account loaded: ${stock_account.state.balance_usdt:,.2f} USD")
        
        # 2. Initialize stock simulator
        self.simulator = get_stock_simulator()
        
        # 3. Initialize market hours manager
        self.market_hours = get_market_hours_manager()
        
        # 4. Initialize regime detector
        self.regime_detector = get_stock_regime_detector()
        
        # 5. Initialize Grok client
        self.grok_client = get_grok_client()
        
        # 6. Initialize strategy
        self.strategy = get_stock_strategy()
        
        logger.info("Stock bot initialization complete")
    
    async def run_trading_cycle(self):
        """Run one stock trading cycle"""
        try:
            # Get current account equity
            stock_account = self.account_manager.get_account(AssetType.STOCK)
            equity = stock_account.state.equity
            
            # Run strategy
            decision = await self.strategy.run_cycle(
                equity=equity,
                grok_client=self.grok_client
            )
            
            # Log decision
            logger.info(
                f"Stock Decision: {decision.action} | "
                f"Core: {len(decision.core_picks)} | "
                f"Reserved: {len(decision.reserved_picks)} | "
                f"Leverage: {decision.leverage:.1f}x"
            )
            
            # Handle decision
            if decision.action == "trade":
                await self._execute_trades(decision)
            elif decision.action == "flatten":
                await self._flatten_positions()
            else:
                logger.info(f"Skipping: {decision.skip_reason}")
            
            self.last_cycle = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error in stock trading cycle: {e}", exc_info=True)
    
    async def _execute_trades(self, decision):
        """Execute trades based on decision"""
        stock_account = self.account_manager.get_account(AssetType.STOCK)
        
        # Execute core picks (80% allocation)
        for i, pick in enumerate(decision.core_picks):
            allocation = 0.60 if i == 0 else 0.40  # 60/40 if two picks
            notional = stock_account.state.equity * 0.80 * allocation
            
            side = "long" if pick.score > 0 else "short"
            
            fill = await self.simulator.simulate_cfd_position(
                symbol=pick.symbol,
                side=side,
                notional_value=notional,
                leverage=decision.leverage
            )
            
            if fill:
                logger.info(
                    f"Simulated {side} {pick.symbol}: "
                    f"${notional:,.2f} notional @ ${fill.fill_price:.2f} "
                    f"(margin: ${fill.margin_required:,.2f})"
                )
                self.trades_today += 1
        
        # Execute reserved picks (20% allocation)
        for pick in decision.reserved_picks:
            notional = stock_account.state.equity * 0.20
            
            side = "long"  # Reserved are typically hype plays (long only)
            
            fill = await self.simulator.simulate_cfd_position(
                symbol=pick.symbol,
                side=side,
                notional_value=notional,
                leverage=decision.leverage
            )
            
            if fill:
                logger.info(
                    f"Simulated hype {side} {pick.symbol}: "
                    f"${notional:,.2f} notional @ ${fill.fill_price:.2f} "
                    f"(hype score: {pick.hype_score:.1f})"
                )
                self.trades_today += 1
    
    async def _flatten_positions(self):
        """Close all positions at market close"""
        logger.info("Flattening all stock positions...")
        
        stock_account = self.account_manager.get_account(AssetType.STOCK)
        positions = stock_account.state.positions
        
        for symbol, position in positions.items():
            side = "sell" if position.side == "long" else "cover"
            fill = await self.simulator.simulate_order(
                symbol=symbol,
                side=side,
                quantity=position.quantity,
                leverage=position.leverage
            )
            
            if fill:
                pnl = (fill.fill_price - position.entry_price) * position.quantity
                if position.side == "short":
                    pnl = -pnl
                
                self.pnl_today += pnl
                logger.info(f"Closed {symbol}: P&L ${pnl:,.2f}")
        
        logger.info(f"Flatten complete. Day P&L: ${self.pnl_today:,.2f}")
    
    async def run(self):
        """Main bot loop"""
        self.running = True
        
        logger.info("=" * 60)
        logger.info(f"Stock Trading Bot starting in {MODE.upper()} mode")
        logger.info("Market hours: 9:30 AM - 4:00 PM ET")
        logger.info("=" * 60)
        
        while self.running:
            try:
                # Get market status
                market_status = self.market_hours.get_status()
                
                if market_status.is_open:
                    # Check if we should run a cycle
                    should_run, reason = await self.strategy.should_run_cycle()
                    
                    if should_run:
                        logger.info(f"Running cycle: {reason}")
                        await self.run_trading_cycle()
                    else:
                        logger.debug(f"Waiting: {reason}")
                else:
                    logger.info(f"Market closed: {market_status.status_text} | {market_status.next_event}")
                    
                    # Reset daily counters at end of day
                    if market_status.status_text == "After Hours" and self.trades_today > 0:
                        logger.info(f"Day complete. Trades: {self.trades_today}, P&L: ${self.pnl_today:,.2f}")
                        self.trades_today = 0
                        self.pnl_today = 0.0
                
                # Wait before next check
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in stock bot loop: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def stop(self):
        """Stop the bot gracefully"""
        logger.info("Stopping stock trading bot...")
        self.running = False
        
        # Close resources
        if self.simulator:
            await self.simulator.close()
        
        if self.regime_detector:
            await self.regime_detector.close()
        
        logger.info("Stock bot stopped")


async def main():
    """Main entry point"""
    bot = StockTradingBot()
    
    try:
        await bot.initialize()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())

