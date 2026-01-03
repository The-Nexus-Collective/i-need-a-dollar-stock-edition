"""
Trading Account - Persistent account state management

Manages paper/live trading account with:
- Balance tracking
- Fee and slippage accounting
- State persistence across restarts
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import AsyncSessionLocal

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Default paper account settings
PAPER_ACCOUNT_ID = os.getenv('PAPER_ACCOUNT_ID', 'paper_main')
INITIAL_BALANCE = float(os.getenv('INITIAL_BALANCE', '108000'))  # 100k EUR in USDT


@dataclass
class AccountPosition:
    """Active position in the account"""
    coin: str
    side: str  # 'long' or 'short'
    quantity: float
    entry_price: float
    current_price: float = 0
    stop_loss: float = 0
    take_profit: float = 0
    unrealized_pnl: float = 0
    position_id: str = ""
    leverage: float = 1.0  # 3-5x adaptive leverage
    
    @property
    def notional_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def margin_required(self) -> float:
        """Margin = notional / leverage (for perpetuals)"""
        if self.leverage <= 0:
            return self.notional_value
        return self.notional_value / self.leverage
    
    @property
    def liquidation_price(self) -> float:
        """
        Estimated liquidation price (80% margin loss).
        For 5x leverage, liquidation occurs at ~16% adverse move.
        """
        if self.leverage <= 0:
            return 0
        
        # Liquidation threshold: 80% of margin lost
        liq_threshold = 0.8 / self.leverage
        
        if self.side == 'long':
            return self.entry_price * (1 - liq_threshold)
        else:
            return self.entry_price * (1 + liq_threshold)
    
    def update_pnl(self, current_price: float):
        self.current_price = current_price
        if self.side == 'long':
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


def check_simulated_liquidation(
    position: AccountPosition,
    current_price: float
) -> tuple:
    """
    Check if a leveraged position would be liquidated at current price.
    
    Liquidation occurs when ~80% of margin is lost:
    - At 5x leverage: ~16% adverse price move
    - At 3x leverage: ~26.7% adverse price move
    
    Args:
        position: The position to check
        current_price: Current market price
    
    Returns:
        Tuple of (would_liquidate: bool, price_change_pct: float, distance_to_liq: float)
    """
    if position.leverage <= 0:
        return False, 0.0, float('inf')
    
    # Liquidation threshold as percentage of entry price
    liq_threshold = 0.8 / position.leverage
    
    # Calculate actual price change
    if position.side == 'long':
        price_change = (position.entry_price - current_price) / position.entry_price
    else:
        price_change = (current_price - position.entry_price) / position.entry_price
    
    # Distance to liquidation (negative = past liquidation)
    distance_to_liq = liq_threshold - price_change
    
    would_liquidate = price_change >= liq_threshold
    
    return would_liquidate, price_change, distance_to_liq


def simulate_margin_call_check(
    positions: Dict[str, AccountPosition],
    prices: Dict[str, float]
) -> Dict[str, dict]:
    """
    Run margin/liquidation check for all positions.
    
    Returns dict with status for each position:
    {
        'BTC': {
            'would_liquidate': False,
            'price_change_pct': 0.05,
            'distance_to_liq_pct': 0.11,
            'status': 'safe'  # 'safe', 'warning', 'danger', 'liquidated'
        }
    }
    """
    results = {}
    
    for coin, pos in positions.items():
        current_price = prices.get(coin, pos.current_price)
        would_liq, price_change, distance = check_simulated_liquidation(pos, current_price)
        
        # Determine status
        if would_liq:
            status = 'liquidated'
        elif distance < 0.05:  # Within 5% of liquidation
            status = 'danger'
        elif distance < 0.10:  # Within 10% of liquidation
            status = 'warning'
        else:
            status = 'safe'
        
        results[coin] = {
            'would_liquidate': would_liq,
            'price_change_pct': price_change * 100,
            'distance_to_liq_pct': distance * 100,
            'liquidation_price': pos.liquidation_price,
            'leverage': pos.leverage,
            'status': status
        }
        
        if would_liq:
            logger.warning(
                f"SIMULATED LIQUIDATION: {coin} {pos.side.upper()} @ {pos.leverage}x "
                f"would be liquidated at ${current_price:.2f} "
                f"(entry: ${pos.entry_price:.2f}, change: {price_change*100:.1f}%)"
            )
    
    return results


@dataclass
class AccountState:
    """Complete account state"""
    account_id: str
    account_type: str  # 'paper' or 'live'
    balance_usdt: float
    initial_balance: float
    
    # Cost tracking
    total_fees_paid: float = 0
    total_slippage_cost: float = 0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    # PnL
    realized_pnl: float = 0
    highest_equity: float = 0
    lowest_equity: float = 0
    max_drawdown: float = 0
    
    # Active positions
    positions: Dict[str, AccountPosition] = field(default_factory=dict)
    
    @property
    def positions_value(self) -> float:
        return sum(p.notional_value for p in self.positions.values())
    
    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    @property
    def equity(self) -> float:
        return self.balance_usdt + self.unrealized_pnl
    
    @property
    def margin_used(self) -> float:
        """Total margin used by open positions (notional / leverage)"""
        return sum(p.margin_required for p in self.positions.values())
    
    @property
    def available_balance(self) -> float:
        """Cash minus margin used for positions"""
        return self.balance_usdt - self.margin_used
    
    @property
    def total_return_pct(self) -> float:
        if self.initial_balance == 0:
            return 0
        return ((self.equity - self.initial_balance) / self.initial_balance) * 100
    
    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0
        return (self.winning_trades / self.total_trades) * 100


class TradingAccount:
    """
    Manages a trading account with persistent state.
    
    Features:
    - Loads state from database on startup
    - Saves state after every trade
    - Tracks fees, slippage, PnL
    - Real-time position updates
    """
    
    def __init__(self, account_id: str = PAPER_ACCOUNT_ID):
        self.account_id = account_id
        self._state: Optional[AccountState] = None
        self._loaded = False
    
    @property
    def state(self) -> AccountState:
        if not self._state:
            raise RuntimeError("Account state not loaded. Call load_state() first.")
        return self._state
    
    async def load_state(self) -> AccountState:
        """Load account state from database"""
        async with AsyncSessionLocal() as session:
            # Load account state
            result = await session.execute(
                text("""
                    SELECT account_id, account_type, balance_usdt, initial_balance,
                           total_fees_paid, total_slippage_cost, total_trades,
                           winning_trades, losing_trades, realized_pnl,
                           highest_equity, lowest_equity, max_drawdown
                    FROM account_state
                    WHERE account_id = :account_id
                """),
                {"account_id": self.account_id}
            )
            row = result.fetchone()
            
            if row:
                self._state = AccountState(
                    account_id=row[0],
                    account_type=row[1],
                    balance_usdt=float(row[2]),
                    initial_balance=float(row[3]),
                    total_fees_paid=float(row[4] or 0),
                    total_slippage_cost=float(row[5] or 0),
                    total_trades=int(row[6] or 0),
                    winning_trades=int(row[7] or 0),
                    losing_trades=int(row[8] or 0),
                    realized_pnl=float(row[9] or 0),
                    highest_equity=float(row[10] or row[3]),
                    lowest_equity=float(row[11] or row[3]),
                    max_drawdown=float(row[12] or 0)
                )
                logger.info(f"Loaded account {self.account_id}: ${self._state.balance_usdt:,.2f}")
            else:
                # Create new account
                await session.execute(
                    text("""
                        INSERT INTO account_state (account_id, account_type, balance_usdt, initial_balance, highest_equity, lowest_equity)
                        VALUES (:account_id, 'paper', :balance, :balance, :balance, :balance)
                    """),
                    {"account_id": self.account_id, "balance": INITIAL_BALANCE}
                )
                await session.commit()
                
                self._state = AccountState(
                    account_id=self.account_id,
                    account_type='paper',
                    balance_usdt=INITIAL_BALANCE,
                    initial_balance=INITIAL_BALANCE,
                    highest_equity=INITIAL_BALANCE,
                    lowest_equity=INITIAL_BALANCE
                )
                logger.info(f"Created new account {self.account_id}: ${INITIAL_BALANCE:,.2f}")
            
            # Load open positions
            await self._load_positions(session)
            
            self._loaded = True
            return self._state
    
    async def _load_positions(self, session: AsyncSession):
        """Load open positions from database"""
        result = await session.execute(
            text("""
                SELECT id, coin, side, quantity, entry_price, current_price,
                       stop_loss, take_profit, unrealized_pnl
                FROM positions
                WHERE status = 'open'
            """)
        )
        
        self._state.positions = {}
        for row in result.fetchall():
            pos = AccountPosition(
                position_id=str(row[0]),
                coin=row[1],
                side=row[2],
                quantity=float(row[3]),
                entry_price=float(row[4]),
                current_price=float(row[5] or row[4]),
                stop_loss=float(row[6] or 0),
                take_profit=float(row[7] or 0),
                unrealized_pnl=float(row[8] or 0)
            )
            self._state.positions[row[1]] = pos
        
        logger.info(f"Loaded {len(self._state.positions)} open positions")
    
    async def save_state(self):
        """Persist current account state to database"""
        if not self._state:
            return
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    UPDATE account_state SET
                        balance_usdt = :balance,
                        total_fees_paid = :fees,
                        total_slippage_cost = :slippage,
                        total_trades = :trades,
                        winning_trades = :wins,
                        losing_trades = :losses,
                        realized_pnl = :pnl,
                        highest_equity = :high,
                        lowest_equity = :low,
                        max_drawdown = :drawdown,
                        updated_at = NOW()
                    WHERE account_id = :account_id
                """),
                {
                    "account_id": self.account_id,
                    "balance": self._state.balance_usdt,
                    "fees": self._state.total_fees_paid,
                    "slippage": self._state.total_slippage_cost,
                    "trades": self._state.total_trades,
                    "wins": self._state.winning_trades,
                    "losses": self._state.losing_trades,
                    "pnl": self._state.realized_pnl,
                    "high": self._state.highest_equity,
                    "low": self._state.lowest_equity,
                    "drawdown": self._state.max_drawdown
                }
            )
            await session.commit()
    
    async def record_equity(self, btc_price: float = 0):
        """Record current equity snapshot for charting"""
        if not self._state:
            return
        
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO account_equity_history 
                        (account_id, equity, cash, positions_value, unrealized_pnl, btc_price)
                    VALUES (:account_id, :equity, :cash, :pos_value, :unrealized, :btc)
                """),
                {
                    "account_id": self.account_id,
                    "equity": self._state.equity,
                    "cash": self._state.balance_usdt,
                    "pos_value": self._state.positions_value,
                    "unrealized": self._state.unrealized_pnl,
                    "btc": btc_price
                }
            )
            await session.commit()
    
    def apply_trade(
        self,
        pnl: float,
        fees: float,
        slippage: float,
        is_winner: bool
    ):
        """Apply trade result to account state"""
        if not self._state:
            return
        
        # Update balance
        self._state.balance_usdt += pnl - fees
        
        # Track costs
        self._state.total_fees_paid += fees
        self._state.total_slippage_cost += slippage
        
        # Trade stats
        self._state.total_trades += 1
        if is_winner:
            self._state.winning_trades += 1
        else:
            self._state.losing_trades += 1
        
        # PnL
        self._state.realized_pnl += pnl
        
        # Update high/low watermarks
        current_equity = self._state.equity
        self._state.highest_equity = max(self._state.highest_equity, current_equity)
        self._state.lowest_equity = min(self._state.lowest_equity, current_equity)
        
        # Calculate drawdown
        if self._state.highest_equity > 0:
            drawdown = (self._state.highest_equity - current_equity) / self._state.highest_equity
            self._state.max_drawdown = max(self._state.max_drawdown, drawdown)
    
    def update_position_prices(self, prices: Dict[str, float]):
        """Update position prices and recalculate PnL"""
        if not self._state:
            return
        
        for coin, pos in self._state.positions.items():
            if coin in prices:
                pos.update_pnl(prices[coin])
    
    def add_position(self, position: AccountPosition):
        """Add a new position"""
        if self._state:
            self._state.positions[position.coin] = position
    
    def remove_position(self, coin: str):
        """Remove a closed position"""
        if self._state and coin in self._state.positions:
            del self._state.positions[coin]
    
    def get_position(self, coin: str) -> Optional[AccountPosition]:
        """Get position for a coin"""
        if self._state:
            return self._state.positions.get(coin)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_trading_account: Optional[TradingAccount] = None


def get_trading_account() -> TradingAccount:
    """Get or create global trading account"""
    global _trading_account
    if _trading_account is None:
        _trading_account = TradingAccount()
    return _trading_account


async def init_trading_account() -> TradingAccount:
    """Initialize and load trading account"""
    account = get_trading_account()
    await account.load_state()
    return account
