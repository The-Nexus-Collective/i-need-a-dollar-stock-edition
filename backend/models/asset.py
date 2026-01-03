"""
Asset Types and Registry - Unified asset configuration for multi-asset trading

Supports:
- Crypto (100k USDT via Binance)
- Stocks (100k USD via CapTrader/IBKR)

Harmonic design: Same risk limits, leverage, and framework across asset types.
"""

from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Dict, List, Optional


class AssetType(str, Enum):
    """Asset type enumeration"""
    CRYPTO = "crypto"
    STOCK = "stock"


@dataclass
class MarketHoursConfig:
    """Market hours configuration for an asset"""
    open_time: time
    close_time: time
    timezone: str
    trading_days: List[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])  # Mon-Fri
    
    def __post_init__(self):
        if isinstance(self.open_time, str):
            h, m = map(int, self.open_time.split(':'))
            self.open_time = time(h, m)
        if isinstance(self.close_time, str):
            h, m = map(int, self.close_time.split(':'))
            self.close_time = time(h, m)


@dataclass
class AssetConfig:
    """Configuration for an asset type"""
    
    # Identity
    asset_type: AssetType
    currency: str
    
    # Symbols
    symbols: List[str]
    reserved_symbols: List[str] = field(default_factory=list)
    
    # Portfolio
    initial_equity: float = 100_000
    core_allocation: float = 1.0  # % of portfolio for core symbols
    reserved_allocation: float = 0.0  # % for reserved/hype symbols
    
    # Timing
    cycle_minutes: int = 60
    market_hours: Optional[MarketHoursConfig] = None
    flatten_at_close: bool = False
    
    # Strategy thresholds (harmonic defaults, can be overridden)
    score_threshold_base: float = 65
    volume_filter_ratio: float = 0.80
    
    # Grok prompt template
    grok_prompt: str = ""
    
    @property
    def is_24_7(self) -> bool:
        """True if asset trades 24/7 (no market hours)"""
        return self.market_hours is None
    
    @property
    def all_symbols(self) -> List[str]:
        """All tradeable symbols including reserved"""
        return self.symbols + self.reserved_symbols


class AssetRegistry:
    """
    Central registry for asset configurations.
    
    Ensures harmonic defaults across asset types while allowing
    asset-specific customization.
    """
    
    # ═══════════════════════════════════════════════════════════════════════════
    # CRYPTO CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    CRYPTO = AssetConfig(
        asset_type=AssetType.CRYPTO,
        currency="USDT",
        initial_equity=100_000,
        
        symbols=[
            "BTC", "ETH", "SOL", "XRP", "DOGE",
            "BNB", "ADA", "AVAX", "TRX", "LINK"
        ],
        
        cycle_minutes=60,  # Hourly cycles
        market_hours=None,  # 24/7 trading
        flatten_at_close=False,
        
        score_threshold_base=65,
        volume_filter_ratio=0.80,
        
        grok_prompt="""Right now, give sentiment (-100 to +100) and narrative strength (0-100) for each cryptocurrency. One line per coin with format: SYMBOL: sentiment, narrative, key_driver

Coins: {symbols}

Be concise. Current market conditions only."""
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # STOCK CONFIGURATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    STOCK = AssetConfig(
        asset_type=AssetType.STOCK,
        currency="USD",
        initial_equity=100_000,
        
        # Core tech stocks (80% of stock allocation)
        symbols=[
            "AAPL", "NVDA", "MSFT", "GOOGL", "AMZN",
            "META", "TSLA", "AVGO", "NFLX", "ADBE"
        ],
        
        # Reserved for hype plays (20% of stock allocation)
        reserved_symbols=[
            "PLTR", "RTX", "LMT", "NOC", "BA"
        ],
        
        core_allocation=0.80,
        reserved_allocation=0.20,
        
        cycle_minutes=240,  # 4-hour cycles
        market_hours=MarketHoursConfig(
            open_time=time(9, 30),
            close_time=time(16, 0),
            timezone="US/Eastern"
        ),
        flatten_at_close=True,
        
        score_threshold_base=70,  # Higher base for stocks
        volume_filter_ratio=0.85,  # 85% of 20-day avg
        
        grok_prompt="""Right now, give sentiment (-100 to +100) and narrative strength (0-100) for each stock. One line per stock with format: SYMBOL: sentiment, narrative, key_driver

Include drivers like: earnings outlook, analyst ratings, news catalysts, institutional activity.

Stocks: {symbols}

Be concise. Current market sentiment only."""
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # REGISTRY METHODS
    # ═══════════════════════════════════════════════════════════════════════════
    
    _configs: Dict[AssetType, AssetConfig] = {
        AssetType.CRYPTO: CRYPTO,
        AssetType.STOCK: STOCK,
    }
    
    @classmethod
    def get(cls, asset_type: AssetType) -> AssetConfig:
        """Get configuration for an asset type"""
        if asset_type not in cls._configs:
            raise ValueError(f"Unknown asset type: {asset_type}")
        return cls._configs[asset_type]
    
    @classmethod
    def all_types(cls) -> List[AssetType]:
        """Get all registered asset types"""
        return list(cls._configs.keys())
    
    @classmethod
    def get_account_id(cls, asset_type: AssetType) -> str:
        """Get account ID for an asset type"""
        return f"{asset_type.value}_main"


# ═══════════════════════════════════════════════════════════════════════════════
# HARMONIC RISK LIMITS - Same across all asset types
# ═══════════════════════════════════════════════════════════════════════════════

HARMONIC_RISK_LIMITS = {
    "per_asset": 0.15,          # 15% max in one position
    "max_deployed": 0.70,       # 70% total deployed
    "altcoin_limit": 0.40,      # 40% non-major assets
    "daily_loss": 0.04,         # 4% circuit breaker
    "min_leverage": 3.0,        # Minimum leverage
    "max_leverage": 5.0,        # Maximum leverage
}

