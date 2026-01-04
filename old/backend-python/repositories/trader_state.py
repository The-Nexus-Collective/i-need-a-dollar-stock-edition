"""
Trader State Repository - DB-first account state management.

Account balance, statistics, and trading state from database.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .db import get_db_pool

logger = logging.getLogger(__name__)

STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "100000"))


@dataclass
class TraderStateDTO:
    """
    Trader state data transfer object.
    
    Represents account state from the database.
    """
    account_id: str
    current_capital: float
    starting_capital: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    total_cycles: int
    total_fees: float
    total_spread: float
    total_slippage: float
    updated_at: Optional[datetime] = None
    
    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    @property
    def total_trading_costs(self) -> float:
        """Total trading costs."""
        return self.total_fees + self.total_spread + self.total_slippage
    
    def to_dict(self) -> dict:
        """Convert to API-friendly dictionary."""
        return {
            "account_id": self.account_id,
            "current_capital": self.current_capital,
            "starting_capital": self.starting_capital,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_pnl": self.total_pnl,
            "total_cycles": self.total_cycles,
            "win_rate": self.win_rate,
            "total_fees": self.total_fees,
            "total_spread": self.total_spread,
            "total_slippage": self.total_slippage,
            "total_trading_costs": self.total_trading_costs,
        }


class TraderStateRepository:
    """
    Repository for trader state database operations.
    
    Manages account balance, statistics, and trading metrics.
    """
    
    MAIN_ACCOUNT_ID = "main"
    
    @classmethod
    async def get_state(cls) -> Optional[TraderStateDTO]:
        """
        Get the current trader state from database.
        
        Returns:
            TraderStateDTO or None if not found
        """
        pool = await get_db_pool()
        if not pool:
            logger.warning("No database pool available")
            return None
        
        try:
            async with pool.acquire() as conn:
                # Try to get with cost columns (after migration 014)
                try:
                    row = await conn.fetchrow("""
                        SELECT id, current_capital, starting_capital,
                               total_trades, winning_trades, losing_trades,
                               total_pnl, total_cycles, 
                               total_fees, total_spread, total_slippage,
                               updated_at
                        FROM trader_state
                        WHERE id = $1
                    """, cls.MAIN_ACCOUNT_ID)
                    
                    if row:
                        return TraderStateDTO(
                            account_id=row['id'],
                            current_capital=float(row['current_capital'] or STARTING_CAPITAL),
                            starting_capital=float(row['starting_capital'] or STARTING_CAPITAL),
                            total_trades=int(row['total_trades'] or 0),
                            winning_trades=int(row['winning_trades'] or 0),
                            losing_trades=int(row['losing_trades'] or 0),
                            total_pnl=float(row['total_pnl'] or 0),
                            total_cycles=int(row['total_cycles'] or 0),
                            total_fees=float(row['total_fees'] or 0),
                            total_spread=float(row['total_spread'] or 0),
                            total_slippage=float(row['total_slippage'] or 0),
                            updated_at=row['updated_at'],
                        )
                except Exception:
                    # Fallback for older schema without cost columns
                    row = await conn.fetchrow("""
                        SELECT id, current_capital, starting_capital,
                               total_trades, winning_trades, losing_trades,
                               total_pnl, total_cycles, updated_at
                        FROM trader_state
                        WHERE id = $1
                    """, cls.MAIN_ACCOUNT_ID)
                    
                    if row:
                        return TraderStateDTO(
                            account_id=row['id'],
                            current_capital=float(row['current_capital'] or STARTING_CAPITAL),
                            starting_capital=float(row['starting_capital'] or STARTING_CAPITAL),
                            total_trades=int(row['total_trades'] or 0),
                            winning_trades=int(row['winning_trades'] or 0),
                            losing_trades=int(row['losing_trades'] or 0),
                            total_pnl=float(row['total_pnl'] or 0),
                            total_cycles=int(row['total_cycles'] or 0),
                            total_fees=0.0,
                            total_spread=0.0,
                            total_slippage=0.0,
                            updated_at=row['updated_at'],
                        )
                
                # Create default state if not exists
                return await cls._create_default_state(conn)
        except Exception as e:
            logger.error(f"Failed to get trader state: {e}")
            return None
    
    @classmethod
    async def _create_default_state(cls, conn) -> TraderStateDTO:
        """Create default trader state if not exists."""
        try:
            await conn.execute("""
                INSERT INTO trader_state (id, current_capital, starting_capital)
                VALUES ($1, $2, $2)
                ON CONFLICT (id) DO NOTHING
            """, cls.MAIN_ACCOUNT_ID, STARTING_CAPITAL)
            
            return TraderStateDTO(
                account_id=cls.MAIN_ACCOUNT_ID,
                current_capital=STARTING_CAPITAL,
                starting_capital=STARTING_CAPITAL,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                total_cycles=0,
                total_fees=0.0,
                total_spread=0.0,
                total_slippage=0.0,
            )
        except Exception as e:
            logger.error(f"Failed to create default state: {e}")
            return TraderStateDTO(
                account_id=cls.MAIN_ACCOUNT_ID,
                current_capital=STARTING_CAPITAL,
                starting_capital=STARTING_CAPITAL,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_pnl=0.0,
                total_cycles=0,
                total_fees=0.0,
                total_spread=0.0,
                total_slippage=0.0,
            )
    
    @classmethod
    async def update_capital(cls, new_capital: float, pnl_delta: float = 0) -> bool:
        """
        Update account capital.
        
        Args:
            new_capital: New capital amount
            pnl_delta: Change in PnL to add to total
        
        Returns:
            True if successful
        """
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE trader_state
                    SET current_capital = $1,
                        total_pnl = total_pnl + $2,
                        updated_at = NOW()
                    WHERE id = $3
                """, new_capital, pnl_delta, cls.MAIN_ACCOUNT_ID)
                return True
        except Exception as e:
            logger.error(f"Failed to update capital: {e}")
            return False
    
    @classmethod
    async def record_trade(
        cls,
        pnl: float,
        is_win: bool,
        fee: float = 0,
        spread: float = 0,
        slippage: float = 0,
    ) -> bool:
        """
        Record a completed trade in statistics.
        
        Args:
            pnl: Trade PnL
            is_win: Whether the trade was profitable
            fee: Trading fee
            spread: Spread cost
            slippage: Slippage cost
        
        Returns:
            True if successful
        """
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                # Try with cost columns first (after migration 014)
                try:
                    await conn.execute("""
                        UPDATE trader_state
                        SET current_capital = current_capital + $1,
                            total_pnl = total_pnl + $1,
                            total_trades = total_trades + 1,
                            winning_trades = winning_trades + $2,
                            losing_trades = losing_trades + $3,
                            total_fees = COALESCE(total_fees, 0) + $4,
                            total_spread = COALESCE(total_spread, 0) + $5,
                            total_slippage = COALESCE(total_slippage, 0) + $6,
                            updated_at = NOW()
                        WHERE id = $7
                    """, 
                        pnl,
                        1 if is_win else 0,
                        0 if is_win else 1,
                        fee,
                        spread,
                        slippage,
                        cls.MAIN_ACCOUNT_ID
                    )
                except Exception:
                    # Fallback for older schema
                    await conn.execute("""
                        UPDATE trader_state
                        SET current_capital = current_capital + $1,
                            total_pnl = total_pnl + $1,
                            total_trades = total_trades + 1,
                            winning_trades = winning_trades + $2,
                            losing_trades = losing_trades + $3,
                            updated_at = NOW()
                        WHERE id = $4
                    """, 
                        pnl,
                        1 if is_win else 0,
                        0 if is_win else 1,
                        cls.MAIN_ACCOUNT_ID
                    )
                return True
        except Exception as e:
            logger.error(f"Failed to record trade: {e}")
            return False
    
    @classmethod
    async def increment_cycle(cls) -> int:
        """
        Increment cycle count and return new value.
        
        Returns:
            New cycle count
        """
        pool = await get_db_pool()
        if not pool:
            return 0
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval("""
                    UPDATE trader_state
                    SET total_cycles = total_cycles + 1,
                        updated_at = NOW()
                    WHERE id = $1
                    RETURNING total_cycles
                """, cls.MAIN_ACCOUNT_ID)
                return result or 0
        except Exception as e:
            logger.error(f"Failed to increment cycle: {e}")
            return 0
    
    @classmethod
    async def reset(cls) -> bool:
        """
        Reset trader state to initial values.
        
        Returns:
            True if successful
        """
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE trader_state
                    SET current_capital = starting_capital,
                        total_trades = 0,
                        winning_trades = 0,
                        losing_trades = 0,
                        total_pnl = 0,
                        total_cycles = 0,
                        total_fees = 0,
                        total_spread = 0,
                        total_slippage = 0,
                        updated_at = NOW()
                    WHERE id = $1
                """, cls.MAIN_ACCOUNT_ID)
                
                # Also close all open positions
                await conn.execute("""
                    UPDATE paper_positions
                    SET status = 'CLOSED',
                        exit_time = NOW(),
                        updated_at = NOW()
                    WHERE status = 'OPEN'
                """)
                
                logger.warning("Trader state reset to initial values")
                return True
        except Exception as e:
            logger.error(f"Failed to reset trader state: {e}")
            return False

