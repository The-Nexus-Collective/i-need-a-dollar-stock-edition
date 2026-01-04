"""
Position Repository - DB-first position management.

All position data comes from the database.
No in-memory state as source of truth.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from .db import get_db_pool

logger = logging.getLogger(__name__)


@dataclass
class PositionDTO:
    """
    Position Data Transfer Object.
    
    Represents a position from the database with computed properties.
    """
    id: str
    symbol: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    quantity: float
    size_usdt: float
    leverage: int
    conviction: int
    status: str  # 'OPEN', 'CLOSED', etc.
    entry_time: datetime
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    realized_pnl: float = 0.0
    reasoning: str = ""
    
    # Live price (set externally)
    current_price: float = 0.0
    
    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL based on current price."""
        if self.current_price <= 0 or self.status != 'OPEN':
            return 0.0
        
        if self.direction == 'LONG':
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - self.current_price) / self.entry_price
        
        return self.size_usdt * pnl_pct * self.leverage
    
    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized PnL as percentage."""
        if self.current_price <= 0 or self.status != 'OPEN':
            return 0.0
        
        if self.direction == 'LONG':
            pnl_pct = (self.current_price - self.entry_price) / self.entry_price
        else:
            pnl_pct = (self.entry_price - self.current_price) / self.entry_price
        
        return pnl_pct * self.leverage * 100
    
    @property
    def liquidation_price(self) -> float:
        """Approximate liquidation price (80% margin loss)."""
        if self.leverage <= 0:
            return 0.0
        
        liq_threshold = 0.8 / self.leverage
        
        if self.direction == 'LONG':
            return self.entry_price * (1 - liq_threshold)
        else:
            return self.entry_price * (1 + liq_threshold)
    
    @property
    def margin_risk_pct(self) -> float:
        """How close to liquidation (0-100%)."""
        if self.current_price <= 0:
            return 0.0
        
        liq_price = self.liquidation_price
        if liq_price <= 0:
            return 0.0
        
        if self.direction == 'LONG':
            if self.current_price >= self.entry_price:
                return 0.0
            distance_to_liq = self.entry_price - liq_price
            current_loss = self.entry_price - self.current_price
        else:
            if self.current_price <= self.entry_price:
                return 0.0
            distance_to_liq = liq_price - self.entry_price
            current_loss = self.current_price - self.entry_price
        
        if distance_to_liq <= 0:
            return 100.0
        
        return min(100.0, (current_loss / distance_to_liq) * 100)
    
    def to_dict(self) -> dict:
        """Convert to API-friendly dictionary."""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "direction": self.direction,
            "entry_price": self.entry_price,
            "current_price": self.current_price,
            "quantity": self.quantity,
            "size_usdt": self.size_usdt,
            "leverage": self.leverage,
            "conviction": self.conviction,
            "status": self.status,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "liquidation_price": self.liquidation_price,
            "margin_risk_pct": self.margin_risk_pct,
            "reasoning": self.reasoning,
        }


class PositionRepository:
    """
    Repository for position database operations.
    
    All position queries go through this class.
    """
    
    @staticmethod
    async def get_open_positions() -> List[PositionDTO]:
        """
        Get all open positions from the database.
        
        Returns:
            List of PositionDTO objects
        """
        pool = await get_db_pool()
        if not pool:
            logger.warning("No database pool available")
            return []
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, symbol, direction, entry_price, quantity, size_usdt,
                           leverage, conviction, status, entry_time, exit_time,
                           exit_price, realized_pnl, reasoning
                    FROM paper_positions
                    WHERE status = 'OPEN'
                    ORDER BY entry_time DESC
                """)
                
                positions = []
                for row in rows:
                    pos = PositionDTO(
                        id=row['id'],
                        symbol=row['symbol'],
                        direction=row['direction'],
                        entry_price=float(row['entry_price']),
                        quantity=float(row['quantity']),
                        size_usdt=float(row['size_usdt']),
                        leverage=int(row['leverage'] or 1),
                        conviction=int(row['conviction'] or 50),
                        status=row['status'],
                        entry_time=row['entry_time'],
                        exit_time=row['exit_time'],
                        exit_price=float(row['exit_price']) if row['exit_price'] else None,
                        realized_pnl=float(row['realized_pnl'] or 0),
                        reasoning=row['reasoning'] or "",
                    )
                    positions.append(pos)
                
                return positions
        except Exception as e:
            logger.error(f"Failed to get open positions: {e}")
            return []
    
    @staticmethod
    async def get_position_by_symbol(symbol: str) -> Optional[PositionDTO]:
        """Get open position by symbol."""
        pool = await get_db_pool()
        if not pool:
            return None
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT id, symbol, direction, entry_price, quantity, size_usdt,
                           leverage, conviction, status, entry_time, exit_time,
                           exit_price, realized_pnl, reasoning
                    FROM paper_positions
                    WHERE symbol = $1 AND status = 'OPEN'
                """, symbol)
                
                if not row:
                    return None
                
                return PositionDTO(
                    id=row['id'],
                    symbol=row['symbol'],
                    direction=row['direction'],
                    entry_price=float(row['entry_price']),
                    quantity=float(row['quantity']),
                    size_usdt=float(row['size_usdt']),
                    leverage=int(row['leverage'] or 1),
                    conviction=int(row['conviction'] or 50),
                    status=row['status'],
                    entry_time=row['entry_time'],
                    exit_time=row['exit_time'],
                    exit_price=float(row['exit_price']) if row['exit_price'] else None,
                    realized_pnl=float(row['realized_pnl'] or 0),
                    reasoning=row['reasoning'] or "",
                )
        except Exception as e:
            logger.error(f"Failed to get position {symbol}: {e}")
            return None
    
    @staticmethod
    async def get_closed_positions(limit: int = 50) -> List[PositionDTO]:
        """Get closed positions (trade history)."""
        pool = await get_db_pool()
        if not pool:
            return []
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT id, symbol, direction, entry_price, quantity, size_usdt,
                           leverage, conviction, status, entry_time, exit_time,
                           exit_price, realized_pnl, reasoning
                    FROM paper_positions
                    WHERE status != 'OPEN'
                    ORDER BY exit_time DESC
                    LIMIT $1
                """, limit)
                
                positions = []
                for row in rows:
                    pos = PositionDTO(
                        id=row['id'],
                        symbol=row['symbol'],
                        direction=row['direction'],
                        entry_price=float(row['entry_price']),
                        quantity=float(row['quantity']),
                        size_usdt=float(row['size_usdt']),
                        leverage=int(row['leverage'] or 1),
                        conviction=int(row['conviction'] or 50),
                        status=row['status'],
                        entry_time=row['entry_time'],
                        exit_time=row['exit_time'],
                        exit_price=float(row['exit_price']) if row['exit_price'] else None,
                        realized_pnl=float(row['realized_pnl'] or 0),
                        reasoning=row['reasoning'] or "",
                    )
                    positions.append(pos)
                
                return positions
        except Exception as e:
            logger.error(f"Failed to get closed positions: {e}")
            return []
    
    @staticmethod
    async def create_position(
        position_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        quantity: float,
        size_usdt: float,
        leverage: int,
        conviction: int,
        reasoning: str = "",
    ) -> bool:
        """
        Create a new open position in the database.
        
        Returns:
            True if successful, False otherwise
        """
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO paper_positions 
                        (id, symbol, direction, entry_price, quantity, size_usdt,
                         leverage, conviction, reasoning, status, entry_time)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'OPEN', NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        status = 'OPEN',
                        updated_at = NOW()
                """,
                    position_id, symbol, direction, entry_price, quantity,
                    size_usdt, leverage, conviction, reasoning
                )
                logger.info(f"Created position {position_id} for {symbol}")
                return True
        except Exception as e:
            logger.error(f"Failed to create position: {e}")
            return False
    
    @staticmethod
    async def close_position(
        position_id: str,
        exit_price: float,
        realized_pnl: float,
        status: str = "CLOSED",
    ) -> bool:
        """
        Close a position in the database.
        
        Args:
            position_id: The position ID
            exit_price: Exit price
            realized_pnl: Realized PnL
            status: New status (CLOSED, STOPPED_OUT, TAKE_PROFIT, etc.)
        
        Returns:
            True if successful, False otherwise
        """
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    UPDATE paper_positions
                    SET status = $1,
                        exit_price = $2,
                        exit_time = NOW(),
                        realized_pnl = $3,
                        updated_at = NOW()
                    WHERE id = $4
                """, status, exit_price, realized_pnl, position_id)
                logger.info(f"Closed position {position_id} with PnL ${realized_pnl:.2f}")
                return True
        except Exception as e:
            logger.error(f"Failed to close position: {e}")
            return False
    
    @staticmethod
    async def update_position(
        position_id: str,
        **updates
    ) -> bool:
        """Update position fields."""
        pool = await get_db_pool()
        if not pool:
            return False
        
        if not updates:
            return True
        
        try:
            # Build dynamic UPDATE query
            set_clauses = []
            values = []
            idx = 1
            
            for key, value in updates.items():
                if key in ('quantity', 'size_usdt', 'entry_price', 'conviction', 'leverage'):
                    set_clauses.append(f"{key} = ${idx}")
                    values.append(value)
                    idx += 1
            
            if not set_clauses:
                return True
            
            set_clauses.append("updated_at = NOW()")
            values.append(position_id)
            
            query = f"""
                UPDATE paper_positions
                SET {', '.join(set_clauses)}
                WHERE id = ${idx}
            """
            
            async with pool.acquire() as conn:
                await conn.execute(query, *values)
                return True
        except Exception as e:
            logger.error(f"Failed to update position: {e}")
            return False
    
    @staticmethod
    async def get_position_count() -> int:
        """Get count of open positions."""
        pool = await get_db_pool()
        if not pool:
            return 0
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT COUNT(*) FROM paper_positions WHERE status = 'OPEN'
                """)
                return result or 0
        except Exception as e:
            logger.error(f"Failed to get position count: {e}")
            return 0
    
    @staticmethod
    async def has_position(symbol: str) -> bool:
        """Check if we have an open position for this symbol."""
        pool = await get_db_pool()
        if not pool:
            return False
        
        try:
            async with pool.acquire() as conn:
                result = await conn.fetchval("""
                    SELECT EXISTS(
                        SELECT 1 FROM paper_positions 
                        WHERE symbol = $1 AND status = 'OPEN'
                    )
                """, symbol)
                return result or False
        except Exception as e:
            logger.error(f"Failed to check position: {e}")
            return False

