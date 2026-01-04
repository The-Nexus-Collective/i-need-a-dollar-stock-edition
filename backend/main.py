"""
Simple 15-Minute Prediction Trader

Main entry point that:
1. Fetches top 10 coins by volume
2. Asks Grok for LONG/SHORT predictions
3. Opens positions with conviction-based leverage
4. Repeats every 15 minutes
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime

import uvicorn

from integrations.binance import get_binance
from integrations.binance_ws import get_binance_ws, start_price_streaming
from trader import Predictor, Executor
from trader.equity_tracker import get_equity_tracker, start_equity_tracking

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING SETUP
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ]
)

logger = logging.getLogger(__name__)

# Reduce noise from HTTP libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON ENFORCEMENT - Kill old instances before starting
# ═══════════════════════════════════════════════════════════════════════════════

def kill_old_instances():
    """
    Kill any other python main.py processes before starting.
    This ensures only ONE trading bot runs at a time, preventing:
    - Multiple processes writing to the same database
    - Conflicting cycle numbers
    - Inconsistent portfolio state
    """
    my_pid = os.getpid()
    killed_count = 0
    
    try:
        # Find all python main.py processes using ps (works on macOS and Linux)
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.strip().split('\n'):
            # Match lines containing python/Python and main.py
            if 'main.py' in line and ('python' in line.lower() or 'Python' in line):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        if pid != my_pid:
                            os.kill(pid, signal.SIGKILL)
                            logger.warning(f"🔪 Killed old trading bot instance (PID {pid})")
                            killed_count += 1
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
        
        # Also try to free up port 8000 if something else is using it
        try:
            port_result = subprocess.run(
                ["lsof", "-ti", ":8000"],
                capture_output=True,
                text=True,
                timeout=5
            )
            for pid_str in port_result.stdout.strip().split('\n'):
                if pid_str:
                    try:
                        pid = int(pid_str)
                        if pid != my_pid:
                            os.kill(pid, signal.SIGKILL)
                            logger.warning(f"🔪 Killed process on port 8000 (PID {pid})")
                            killed_count += 1
                    except (ValueError, ProcessLookupError, PermissionError):
                        pass
        except subprocess.TimeoutExpired:
            pass
        
        if killed_count > 0:
            logger.info(f"✅ Cleaned up {killed_count} old process(es). Waiting for ports to free...")
            import time
            time.sleep(2)  # Give OS time to release ports
        else:
            logger.info("✅ No old instances found - starting fresh")
            
    except subprocess.TimeoutExpired:
        logger.warning("Process check timed out, continuing anyway")
    except Exception as e:
        logger.warning(f"Could not check for old instances: {e}")


# Run singleton check immediately on import
kill_old_instances()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

CYCLE_INTERVAL_SECONDS = int(os.getenv("CYCLE_INTERVAL", "720"))  # 12 minutes for sentiment analysis
TOP_COINS_COUNT = int(os.getenv("TOP_COINS", "100"))  # Analyze top 100 coins by market cap
MAX_OPEN_POSITIONS = int(os.getenv("MAX_POSITIONS", "50"))  # Max 50 positions at once
POSITION_SIZE_PCT = float(os.getenv("POSITION_SIZE_PCT", "0.02"))  # 2% of capital per trade
STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))
API_PORT = int(os.getenv("API_PORT", "8000"))


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING LOOP
# ═══════════════════════════════════════════════════════════════════════════════

class TradingLoop:
    """
    Main trading loop.
    
    Runs prediction cycles every 15 minutes.
    """
    
    def __init__(self):
        self.binance = get_binance()
        self.predictor = Predictor()
        self.executor = Executor(
            starting_capital=STARTING_CAPITAL,
            binance=self.binance,
            max_positions=MAX_OPEN_POSITIONS,
            position_size_pct=POSITION_SIZE_PCT,
        )
        self._running = False
        self._cycle_count = 0
        self._ws = None
        self._equity_tracker = None
        self._current_phase = "idle"  # idle, fetching, analyzing, trading
    
    async def _broadcast_phase(self, phase: str, next_cycle_at: float = None):
        """Broadcast current phase to connected clients."""
        self._current_phase = phase
        try:
            # Broadcast to both realtime WebSocket and equity WebSocket
            from gateway.realtime import broadcast_phase
            from gateway.main import broadcast_phase_to_equity_ws
            
            await broadcast_phase(phase, next_cycle_at, self._cycle_count)
            await broadcast_phase_to_equity_ws(phase, next_cycle_at, self._cycle_count)
        except Exception as e:
            logger.debug(f"Could not broadcast phase: {e}")
    
    async def run_cycle(self):
        """Run a single prediction/trading cycle."""
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        
        logger.info("")
        logger.info("╔══════════════════════════════════════════════════════════════════╗")
        logger.info(f"║  CYCLE #{self._cycle_count} - {cycle_start.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info("╚══════════════════════════════════════════════════════════════════╝")
        
        try:
            # Step 1: Get top coins by market cap
            await self._broadcast_phase("fetching")
            logger.info(f"Fetching top {TOP_COINS_COUNT} coins by market cap...")
            coins = await self.binance.get_top_coins_by_market_cap(TOP_COINS_COUNT)
            logger.info(f"Top coins: {', '.join(coins)}")
            
            # Update WebSocket to track new coins
            if self._ws:
                symbols = [f"{coin}USDT" for coin in coins]
                self._ws.add_symbols(symbols)
            
            # Step 2: Get predictions from Grok
            await self._broadcast_phase("analyzing")
            logger.info("Getting predictions from Grok...")
            predictions = await self.predictor.predict_all(coins)
            
            for pred in predictions:
                arrow = "🟢" if pred.direction == "LONG" else "🔴"
                logger.info(
                    f"  {arrow} {pred.coin}: {pred.direction} ({pred.conviction}% conviction) "
                    f"→ {pred.leverage:.1f}x leverage | {pred.reason}"
                )
            
            # Step 3: Execute trades (smart cycle - only close on sentiment change)
            await self._broadcast_phase("trading")
            logger.info("Executing smart trades...")
            result = await self.executor.execute_cycle_smart(predictions)
            
            # Step 4: Log results
            cycle_time = (datetime.utcnow() - cycle_start).total_seconds()
            logger.info(f"Cycle completed in {cycle_time:.1f}s")
            logger.info(f"Capital: ${result.capital_after:,.2f} (PnL this cycle: ${result.total_pnl:+,.2f})")
            
            return result
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}", exc_info=True)
            await self._broadcast_phase("idle")  # Reset to idle on error
            return None
    
    async def run(self):
        """Main trading loop."""
        self._running = True
        
        logger.info("")
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info("        🚀 SIMPLE PREDICTION TRADER STARTING 🚀")
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info(f"  Coins Analyzed:   {TOP_COINS_COUNT} (by market cap)")
        logger.info(f"  Max Positions:    {MAX_OPEN_POSITIONS}")
        logger.info(f"  Position Size:    {POSITION_SIZE_PCT*100:.0f}% (${STARTING_CAPITAL * POSITION_SIZE_PCT:,.0f})")
        logger.info(f"  Starting Capital: ${STARTING_CAPITAL:,.0f}")
        logger.info(f"  Cycle Interval:   {CYCLE_INTERVAL_SECONDS}s ({CYCLE_INTERVAL_SECONDS//60}m)")
        logger.info(f"  Mode:             {'PAPER' if self.binance.paper_mode else 'LIVE'}")
        logger.info("═══════════════════════════════════════════════════════════════════")
        logger.info("")
        
        # Start real-time price streaming
        try:
            # Get initial coin list for WebSocket
            initial_coins = await self.binance.get_top_coins_by_volume(TOP_COINS_COUNT)
            symbols = [f"{coin}USDT" for coin in initial_coins]
            
            self._ws = get_binance_ws()
            self._ws.add_symbols(symbols)
            await self._ws.start()
            logger.info("Real-time price streaming started")
            
            # Start equity tracking
            self._equity_tracker = get_equity_tracker()
            self._equity_tracker.set_executor(self.executor)
            await self._equity_tracker.start()
            logger.info("Equity tracking started")
        except Exception as e:
            logger.warning(f"Failed to start real-time tracking: {e}")
        
        while self._running:
            try:
                # Run a cycle
                await self.run_cycle()
                
                if not self._running:
                    break
                
                # Broadcast idle phase with next cycle timestamp
                import time
                next_cycle_at = time.time() + CYCLE_INTERVAL_SECONDS
                await self._broadcast_phase("idle", next_cycle_at)
                
                # Wait for next cycle
                logger.info(f"Next cycle in {CYCLE_INTERVAL_SECONDS//60} minutes...")
                
                # Wait in small increments to allow graceful shutdown
                for _ in range(CYCLE_INTERVAL_SECONDS // 5):
                    if not self._running:
                        break
                    await asyncio.sleep(5)
                    
            except Exception as e:
                logger.error(f"Error in trading loop: {e}", exc_info=True)
                await self._broadcast_phase("idle")
                await asyncio.sleep(60)  # Wait a minute before retrying
        
        logger.info("Trading loop stopped")
    
    async def shutdown(self):
        """Gracefully shutdown the trading loop."""
        logger.info("Shutting down trading loop...")
        self._running = False
        
        # Stop equity tracking
        if self._equity_tracker:
            await self._equity_tracker.stop()
        
        # Stop WebSocket
        if self._ws:
            await self._ws.stop()
        
        # Close all positions before shutdown
        if self.executor.positions:
            logger.info("Closing all positions...")
            await self.executor._close_all_positions()
        
        # Close HTTP clients
        await self.predictor.close()
        await self.binance.close()
        
        logger.info("Trading loop shutdown complete")
    
    def get_status(self) -> dict:
        """Get current status for API."""
        status = {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "executor": self.executor.get_status(),
            "top_coins_count": TOP_COINS_COUNT,
            "cycle_interval_seconds": CYCLE_INTERVAL_SECONDS,
            "mode": "paper" if self.binance.paper_mode else "live",
        }
        
        # Add equity data if available
        if self._equity_tracker:
            latest = self._equity_tracker.get_latest()
            if latest:
                status["equity"] = latest.to_dict()
        
        # Add live price count
        if self._ws:
            status["live_prices_count"] = len(self._ws.get_all_prices())
        
        return status
    
    def reset_paper_trading(self):
        """
        Reset all paper trading state.
        
        Called from the API when user clicks reset button.
        Trading continues normally after reset.
        """
        old_capital = self.executor.capital
        old_positions = len(self.executor.positions)
        
        logger.warning(f"RESET: executor_id={id(self.executor)}, capital=${old_capital:,.2f}")
        
        # Reset executor (clears positions and resets capital)
        self.executor.reset_state()
        
        # Reset equity tracker
        if self._equity_tracker:
            self._equity_tracker._latest_snapshot = None
            self._equity_tracker._history = []
        
        # Reset cycle count
        self._cycle_count = 0
        
        logger.warning(
            f"PAPER TRADING RESET COMPLETE: ${old_capital:,.2f} -> ${self.executor.capital:,.2f}, "
            f"cleared {old_positions} positions"
        )
        
        return {
            "old_capital": old_capital,
            "new_capital": self.executor.capital,
            "positions_cleared": old_positions,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

# Import the singleton management from a separate module
# This avoids the __main__ vs main module identity problem
from trading_state import get_trading_loop, set_trading_loop


async def main():
    """Main entry point."""
    # Create and register the trading loop singleton
    loop = TradingLoop()
    set_trading_loop(loop)
    logger.info(f"Created TradingLoop id={id(loop)}, executor_id={id(loop.executor)}")
    
    # Setup signal handlers
    def handle_shutdown(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        asyncio.create_task(loop.shutdown())
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Create Uvicorn config for the API server
    config = uvicorn.Config(
        app="gateway.main:app",
        host="0.0.0.0",
        port=API_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    
    logger.info(f"Starting API server on port {API_PORT}...")
    
    # Run API server and trading loop concurrently
    try:
        await asyncio.gather(
            server.serve(),
            loop.run(),
        )
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        await loop.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)
