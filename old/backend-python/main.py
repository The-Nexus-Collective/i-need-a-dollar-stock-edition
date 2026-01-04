"""
Portfolio Manager Trading Bot

Main entry point that:
1. Runs the Grok-powered portfolio manager
2. Serves the API for frontend
3. Broadcasts real-time updates via WebSocket
"""

import asyncio
import logging
import os
import signal
import subprocess
import sys
from datetime import datetime

import uvicorn

from portfolio_manager import PortfolioManager
from trading_state import set_portfolio_manager

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
    This ensures only ONE trading bot runs at a time.
    """
    my_pid = os.getpid()
    killed_count = 0
    
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        for line in result.stdout.strip().split('\n'):
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
        
        # Free up port 8000
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
            time.sleep(2)
        else:
            logger.info("✅ No old instances found - starting fresh")
            
    except subprocess.TimeoutExpired:
        logger.warning("Process check timed out, continuing anyway")
    except Exception as e:
        logger.warning(f"Could not check for old instances: {e}")


# Run singleton check immediately
kill_old_instances()


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

API_PORT = int(os.getenv("API_PORT", "8000"))


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point."""
    # Create and register the portfolio manager (single source of truth in trading_state)
    manager = PortfolioManager()
    set_portfolio_manager(manager)
    logger.info(f"Created PortfolioManager")
    
    # Setup signal handlers
    def handle_shutdown(sig, frame):
        logger.info(f"Received signal {sig}, initiating shutdown...")
        asyncio.create_task(manager.shutdown())
    
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Import the app directly to share the same module state
    from gateway.main import app as gateway_app
    
    # Create Uvicorn config for the API server
    config = uvicorn.Config(
        app=gateway_app,
        host="0.0.0.0",
        port=API_PORT,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    
    logger.info(f"Starting API server on port {API_PORT}...")
    
    # Run API server and portfolio manager concurrently
    try:
        await asyncio.gather(
            server.serve(),
            manager.run(),
        )
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
    finally:
        await manager.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated by user")
    except Exception as e:
        logger.error(f"Application crashed: {e}", exc_info=True)
        sys.exit(1)
