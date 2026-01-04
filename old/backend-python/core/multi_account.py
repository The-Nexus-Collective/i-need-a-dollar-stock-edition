"""
Multi-Account Manager - Manages separate accounts for each asset type

Portfolios:
- Crypto: 100,000 USDT (crypto_main account)
- Stocks: 100,000 USD (stock_main account)

Each account has independent equity, positions, and P&L tracking.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import text

from models import AsyncSessionLocal
from models.asset import AssetType, AssetRegistry
from .account import TradingAccount, AccountState, AccountPosition

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSummary:
    """Summary of all portfolios"""
    timestamp: datetime
    
    # Crypto
    crypto_equity: float
    crypto_currency: str
    crypto_positions: int
    crypto_pnl: float
    crypto_pnl_pct: float
    
    # Stocks
    stock_equity: float
    stock_currency: str
    stock_positions: int
    stock_pnl: float
    stock_pnl_pct: float
    
    # Combined (converted to USD)
    total_equity_usd: float
    total_pnl_usd: float
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "crypto": {
                "equity": self.crypto_equity,
                "currency": self.crypto_currency,
                "positions": self.crypto_positions,
                "pnl": self.crypto_pnl,
                "pnl_pct": self.crypto_pnl_pct,
            },
            "stock": {
                "equity": self.stock_equity,
                "currency": self.stock_currency,
                "positions": self.stock_positions,
                "pnl": self.stock_pnl,
                "pnl_pct": self.stock_pnl_pct,
            },
            "total": {
                "equity_usd": self.total_equity_usd,
                "pnl_usd": self.total_pnl_usd,
            }
        }


class MultiAccountManager:
    """
    Manages separate trading accounts for each asset type.
    
    Each account operates independently with its own:
    - Balance and equity
    - Open positions
    - P&L tracking
    - Risk limits (applied per account)
    
    The manager provides unified views across all accounts.
    """
    
    # USDT/USD conversion rate (approximate, could be made dynamic)
    USDT_USD_RATE = 1.0  # Assume 1:1 for simplicity
    
    def __init__(self):
        self._accounts: Dict[AssetType, TradingAccount] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all accounts from database"""
        if self._initialized:
            return
        
        for asset_type in AssetRegistry.all_types():
            account_id = AssetRegistry.get_account_id(asset_type)
            config = AssetRegistry.get(asset_type)
            
            # Create account instance
            account = TradingAccount(account_id)
            
            # Ensure account exists in database
            await self._ensure_account_exists(account_id, config)
            
            # Load state
            await account.load_state()
            
            self._accounts[asset_type] = account
            logger.info(
                f"Initialized {asset_type.value} account: "
                f"{account.state.balance_usdt:,.2f} {config.currency}"
            )
        
        self._initialized = True
    
    async def _ensure_account_exists(self, account_id: str, config):
        """Create account in database if it doesn't exist"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT account_id FROM account_state WHERE account_id = :id"),
                {"id": account_id}
            )
            if not result.fetchone():
                await session.execute(
                    text("""
                        INSERT INTO account_state 
                            (account_id, account_type, balance_usdt, initial_balance, 
                             highest_equity, lowest_equity)
                        VALUES 
                            (:id, 'paper', :balance, :balance, :balance, :balance)
                    """),
                    {"id": account_id, "balance": config.initial_equity}
                )
                await session.commit()
                logger.info(f"Created new account: {account_id} with {config.initial_equity} {config.currency}")
    
    def get_account(self, asset_type: AssetType) -> TradingAccount:
        """Get the trading account for an asset type"""
        if not self._initialized:
            raise RuntimeError("MultiAccountManager not initialized. Call initialize() first.")
        
        if asset_type not in self._accounts:
            raise ValueError(f"No account for asset type: {asset_type}")
        
        return self._accounts[asset_type]
    
    async def get_equity(self, asset_type: AssetType) -> float:
        """Get current equity for an asset type"""
        account = self.get_account(asset_type)
        return account.state.equity
    
    async def get_available_balance(self, asset_type: AssetType) -> float:
        """Get available balance for new positions"""
        account = self.get_account(asset_type)
        return account.state.available_balance
    
    async def get_positions(self, asset_type: AssetType) -> Dict[str, AccountPosition]:
        """Get all open positions for an asset type"""
        account = self.get_account(asset_type)
        return account.state.positions
    
    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get summary across all portfolios"""
        crypto_account = self.get_account(AssetType.CRYPTO)
        stock_account = self.get_account(AssetType.STOCK)
        
        crypto_config = AssetRegistry.get(AssetType.CRYPTO)
        stock_config = AssetRegistry.get(AssetType.STOCK)
        
        # Calculate P&L
        crypto_pnl = crypto_account.state.equity - crypto_account.state.initial_balance
        crypto_pnl_pct = (crypto_pnl / crypto_account.state.initial_balance) * 100
        
        stock_pnl = stock_account.state.equity - stock_account.state.initial_balance
        stock_pnl_pct = (stock_pnl / stock_account.state.initial_balance) * 100
        
        # Convert to USD for totals
        crypto_usd = crypto_account.state.equity * self.USDT_USD_RATE
        total_usd = crypto_usd + stock_account.state.equity
        total_pnl_usd = (crypto_pnl * self.USDT_USD_RATE) + stock_pnl
        
        return PortfolioSummary(
            timestamp=datetime.utcnow(),
            crypto_equity=crypto_account.state.equity,
            crypto_currency=crypto_config.currency,
            crypto_positions=len(crypto_account.state.positions),
            crypto_pnl=crypto_pnl,
            crypto_pnl_pct=crypto_pnl_pct,
            stock_equity=stock_account.state.equity,
            stock_currency=stock_config.currency,
            stock_positions=len(stock_account.state.positions),
            stock_pnl=stock_pnl,
            stock_pnl_pct=stock_pnl_pct,
            total_equity_usd=total_usd,
            total_pnl_usd=total_pnl_usd,
        )
    
    async def save_all(self):
        """Save state for all accounts"""
        for asset_type, account in self._accounts.items():
            await account.save_state()
            logger.debug(f"Saved {asset_type.value} account state")
    
    async def record_equity_all(self, prices: Dict[str, Dict[str, float]] = None):
        """Record equity snapshot for all accounts"""
        for asset_type, account in self._accounts.items():
            btc_price = 0
            if prices and asset_type == AssetType.CRYPTO:
                btc_price = prices.get("BTC", {}).get("price", 0)
            await account.record_equity(btc_price)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_multi_account_manager: Optional[MultiAccountManager] = None


def get_multi_account_manager() -> MultiAccountManager:
    """Get or create global multi-account manager"""
    global _multi_account_manager
    if _multi_account_manager is None:
        _multi_account_manager = MultiAccountManager()
    return _multi_account_manager


async def init_multi_account_manager() -> MultiAccountManager:
    """Initialize and return the multi-account manager"""
    manager = get_multi_account_manager()
    await manager.initialize()
    return manager

