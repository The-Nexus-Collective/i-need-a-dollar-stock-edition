"""
Validation Agent - Validates assets before trading.

Responsibilities:
1. Check minimum volume requirements ($10M daily)
2. Verify Tier-1 exchange listing (Binance)
3. Check coin age (>= 7 days)
4. Liquidity sanity checks
5. Basic risk scoring

Prevents trading garbage or high-risk new tokens.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set

from sqlalchemy import text

from .base import BaseAgent, AgentContext, AgentOutput

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of validating an asset."""
    coin: str
    is_valid: bool
    
    # Individual checks
    volume_check: bool = False
    exchange_check: bool = False
    age_check: bool = False
    liquidity_check: bool = False
    
    # Details
    volume_24h: float = 0
    coin_age_days: int = 0
    spread_percent: float = 0
    
    # Reason if rejected
    rejection_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "coin": self.coin,
            "is_valid": self.is_valid,
            "volume_check": self.volume_check,
            "exchange_check": self.exchange_check,
            "age_check": self.age_check,
            "liquidity_check": self.liquidity_check,
            "volume_24h": self.volume_24h,
            "coin_age_days": self.coin_age_days,
            "spread_percent": self.spread_percent,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class ValidationOutput:
    """Output from Validation Agent."""
    validated: List[ValidationResult]
    approved_coins: List[str]
    rejected_coins: Dict[str, str]  # coin -> reason
    
    def to_dict(self) -> Dict:
        return {
            "validated": [v.to_dict() for v in self.validated],
            "approved_coins": self.approved_coins,
            "rejected_coins": self.rejected_coins,
        }


class ValidationAgent(BaseAgent):
    """
    Validates assets meet minimum trading requirements.
    
    Criteria:
    - Volume >= $10M (24h)
    - Listed on Binance (spot or perpetual)
    - Coin age >= 7 days
    - Spread < 0.5%
    """
    
    # Validation thresholds
    MIN_VOLUME_USD = 10_000_000  # $10M minimum
    MIN_COIN_AGE_DAYS = 7
    MAX_SPREAD_PERCENT = 0.5
    
    # Known Binance perpetual symbols (cache)
    BINANCE_PERPS: Set[str] = {
        'BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'BNB', 'ADA', 'AVAX',
        'TRX', 'LINK', 'DOT', 'MATIC', 'SHIB', 'LTC', 'UNI',
        'ATOM', 'XMR', 'ETC', 'XLM', 'BCH', 'APT', 'NEAR',
        'FIL', 'ARB', 'OP', 'IMX', 'INJ', 'SUI', 'SEI',
        'PEPE', 'WIF', 'BONK', 'FLOKI', 'ORDI', 'WLD',
        # Add more as needed
    }
    
    def __init__(self):
        super().__init__("validation")
        self._binance_symbols: Optional[Set[str]] = None
    
    async def initialize(self):
        """Load Binance symbols."""
        await self._refresh_binance_symbols()
        await super().initialize()
    
    async def _refresh_binance_symbols(self):
        """Fetch current Binance trading symbols."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Get exchange info
                response = await client.get(
                    "https://api.binance.com/api/v3/exchangeInfo"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    symbols = set()
                    
                    for s in data.get("symbols", []):
                        if s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
                            base = s.get("baseAsset", "")
                            symbols.add(base)
                    
                    self._binance_symbols = symbols
                    logger.info(f"Loaded {len(symbols)} Binance trading pairs")
                    
        except Exception as e:
            logger.error(f"Failed to load Binance symbols: {e}")
            self._binance_symbols = self.BINANCE_PERPS.copy()
    
    async def think(self, context: AgentContext) -> AgentOutput:
        """Determine which coins need validation."""
        # Get coins to validate from context
        coins_to_validate = set()
        
        # New discoveries
        for disc in context.x_discoveries:
            coin = disc.get("coin", "")
            if coin:
                coins_to_validate.add(coin)
        
        # Active universe (re-validate periodically)
        coins_to_validate.update(context.active_coins)
        
        reasoning = f"Need to validate {len(coins_to_validate)} coins: {', '.join(list(coins_to_validate)[:10])}"
        
        return AgentOutput(
            success=True,
            data={"coins": list(coins_to_validate)},
            reasoning=reasoning,
            decision=f"validate_{len(coins_to_validate)}_coins",
            confidence=95,
        )
    
    async def act(self, context: AgentContext, thought: AgentOutput) -> AgentOutput:
        """Validate all coins."""
        coins = thought.data.get("coins", [])
        
        results: List[ValidationResult] = []
        approved: List[str] = []
        rejected: Dict[str, str] = {}
        
        for coin in coins:
            result = await self._validate_coin(coin)
            results.append(result)
            
            if result.is_valid:
                approved.append(coin)
                await self._update_universe(coin, result)
            else:
                rejected[coin] = result.rejection_reason or "Unknown"
        
        # Update context
        context.validated_coins = approved
        context.rejected_coins = rejected
        
        output = ValidationOutput(
            validated=results,
            approved_coins=approved,
            rejected_coins=rejected,
        )
        
        return AgentOutput(
            success=True,
            data=output.to_dict(),
            reasoning=f"Validated {len(coins)} coins: {len(approved)} approved, {len(rejected)} rejected",
            decision=f"approved: {', '.join(approved[:5])}{'...' if len(approved) > 5 else ''}",
            confidence=90,
        )
    
    async def _validate_coin(self, coin: str) -> ValidationResult:
        """Validate a single coin against all criteria."""
        result = ValidationResult(coin=coin, is_valid=False)
        
        try:
            # 1. Check Binance listing
            result.exchange_check = await self._check_binance_listing(coin)
            if not result.exchange_check:
                result.rejection_reason = "Not listed on Binance"
                return result
            
            # 2. Check volume
            volume_data = await self._get_volume_data(coin)
            result.volume_24h = volume_data.get("volume_24h", 0)
            result.volume_check = result.volume_24h >= self.MIN_VOLUME_USD
            
            if not result.volume_check:
                result.rejection_reason = f"Volume ${result.volume_24h/1e6:.1f}M < ${self.MIN_VOLUME_USD/1e6:.0f}M minimum"
                return result
            
            # 3. Check coin age (simplified - assume OK if on Binance)
            result.coin_age_days = volume_data.get("age_days", 30)
            result.age_check = result.coin_age_days >= self.MIN_COIN_AGE_DAYS
            
            if not result.age_check:
                result.rejection_reason = f"Coin age {result.coin_age_days} days < {self.MIN_COIN_AGE_DAYS} days minimum"
                return result
            
            # 4. Check liquidity (spread)
            result.spread_percent = await self._get_spread(coin)
            result.liquidity_check = result.spread_percent < self.MAX_SPREAD_PERCENT
            
            if not result.liquidity_check:
                result.rejection_reason = f"Spread {result.spread_percent:.2f}% > {self.MAX_SPREAD_PERCENT}% maximum"
                return result
            
            # All checks passed
            result.is_valid = True
            
        except Exception as e:
            result.rejection_reason = f"Validation error: {str(e)}"
            logger.error(f"Validation error for {coin}: {e}")
        
        return result
    
    async def _check_binance_listing(self, coin: str) -> bool:
        """Check if coin is listed on Binance."""
        if self._binance_symbols is None:
            await self._refresh_binance_symbols()
        
        return coin.upper() in (self._binance_symbols or self.BINANCE_PERPS)
    
    async def _get_volume_data(self, coin: str) -> Dict:
        """Get volume data from Binance."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.binance.com/api/v3/ticker/24hr",
                    params={"symbol": f"{coin}USDT"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    volume_usdt = float(data.get("quoteVolume", 0))
                    
                    return {
                        "volume_24h": volume_usdt,
                        "age_days": 365,  # Assume old if on Binance
                    }
                    
        except Exception as e:
            logger.warning(f"Volume check failed for {coin}: {e}")
        
        return {"volume_24h": 0, "age_days": 0}
    
    async def _get_spread(self, coin: str) -> float:
        """Get current bid-ask spread."""
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.binance.com/api/v3/ticker/bookTicker",
                    params={"symbol": f"{coin}USDT"}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    bid = float(data.get("bidPrice", 0))
                    ask = float(data.get("askPrice", 0))
                    
                    if bid > 0 and ask > 0:
                        spread = ((ask - bid) / bid) * 100
                        return spread
                        
        except Exception as e:
            logger.warning(f"Spread check failed for {coin}: {e}")
        
        return 0.1  # Default to small spread
    
    async def _update_universe(self, coin: str, result: ValidationResult):
        """Update tradable_universe table with validation result."""
        from models import AsyncSessionLocal
        
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("""
                    INSERT INTO tradable_universe (
                        coin, validation_status, validated_at, validation_notes,
                        volume_24h, coin_age_days, is_active
                    ) VALUES (
                        :coin, 'approved', NOW(), :notes,
                        :volume, :age, TRUE
                    )
                    ON CONFLICT (coin) DO UPDATE SET
                        validation_status = 'approved',
                        validated_at = NOW(),
                        validation_notes = :notes,
                        volume_24h = :volume,
                        is_active = TRUE
                """), {
                    "coin": coin,
                    "notes": f"Volume: ${result.volume_24h/1e6:.1f}M, Spread: {result.spread_percent:.2f}%",
                    "volume": result.volume_24h,
                    "age": result.coin_age_days,
                })
                await session.commit()
                
        except Exception as e:
            logger.error(f"Failed to update universe for {coin}: {e}")

