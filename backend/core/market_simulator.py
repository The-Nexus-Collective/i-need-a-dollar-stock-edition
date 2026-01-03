"""
Market Simulator - Realistic paper trade execution

Simulates order execution with:
- Real order book data for slippage calculation
- VIP 0 Binance Futures fees
- Gaussian noise for realistic variance
- Funding rate simulation for perpetuals
"""

import asyncio
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import uuid4

from .price_cache import get_book_cache, get_price_cache

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# FEE CONFIGURATION - Binance Futures VIP 0
# ═══════════════════════════════════════════════════════════════════════════════

# VIP 0 (default tier)
MAKER_FEE = 0.0002   # 0.02%
TAKER_FEE = 0.0005   # 0.05%

# Funding rate simulation parameters (every 8 hours)
FUNDING_RATE_MEAN = 0.0001    # 0.01% average
FUNDING_RATE_STD = 0.0002     # ±0.02% std deviation

# ═══════════════════════════════════════════════════════════════════════════════
# SLIPPAGE SIMULATION - Gaussian distribution
# ═══════════════════════════════════════════════════════════════════════════════

# Slippage follows Gaussian distribution for realism
SLIPPAGE_MEAN = 0.001     # 0.1% mean slippage
SLIPPAGE_STD = 0.0005     # 0.05% std deviation
SLIPPAGE_MIN = 0.0005     # 0.05% minimum (spread)
SLIPPAGE_MAX = 0.002      # 0.2% maximum (caps extreme values)

# Minimum spread to apply even with deep liquidity
MIN_SPREAD_BPS = 1  # 0.01% minimum spread


def gaussian_slippage() -> float:
    """
    Generate realistic slippage using Gaussian distribution.
    
    Returns slippage as a decimal (e.g., 0.001 = 0.1%)
    Clamped to [SLIPPAGE_MIN, SLIPPAGE_MAX] to avoid extreme values.
    """
    slippage = random.gauss(SLIPPAGE_MEAN, SLIPPAGE_STD)
    return max(SLIPPAGE_MIN, min(SLIPPAGE_MAX, slippage))


def simulate_funding_rate() -> float:
    """
    Simulate funding rate for perpetual futures.
    
    Returns funding rate as a decimal (e.g., 0.0001 = 0.01%)
    Can be negative (shorts pay longs) or positive (longs pay shorts).
    """
    return random.gauss(FUNDING_RATE_MEAN, FUNDING_RATE_STD)


@dataclass
class Fill:
    """
    Represents an order fill with full cost breakdown.
    
    This is what both paper and live execution return,
    ensuring identical behavior.
    """
    order_id: str
    coin: str
    side: str  # 'buy' or 'sell'
    quantity: float
    
    # Pricing
    requested_price: float  # Price at order submission
    fill_price: float       # Actual fill price (VWAP)
    
    # Cost breakdown
    slippage_cost: float    # Price impact in USDT
    slippage_bps: float     # Price impact in basis points
    fee: float              # Trading fee in USDT
    fee_rate: float         # Fee rate applied
    total_cost: float       # Total order cost including fees
    
    # Execution details
    book_depth_used: int    # Order book levels consumed
    timestamp: datetime
    is_paper: bool = True
    
    # Enhanced paper mode tracking
    simulated_slippage: float = 0.0   # Slippage rate used (for DB tracking)
    funding_rate: float = 0.0          # Simulated funding rate
    leverage: float = 1.0              # Leverage used for this trade
    
    @property
    def net_cost(self) -> float:
        """Total cost to execute this order"""
        return (self.fill_price * self.quantity) + self.fee
    
    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "coin": self.coin,
            "side": self.side,
            "quantity": self.quantity,
            "requested_price": self.requested_price,
            "fill_price": self.fill_price,
            "slippage_cost": self.slippage_cost,
            "slippage_bps": self.slippage_bps,
            "simulated_slippage": self.simulated_slippage,
            "fee": self.fee,
            "fee_rate": self.fee_rate,
            "total_cost": self.total_cost,
            "book_depth_used": self.book_depth_used,
            "timestamp": self.timestamp.isoformat(),
            "is_paper": self.is_paper,
            "funding_rate": self.funding_rate,
            "leverage": self.leverage
        }


class MarketSimulator:
    """
    Simulates realistic market order execution.
    
    Uses live order book data to calculate:
    - Volume-weighted average fill price (VWAP)
    - Slippage based on order size vs liquidity
    - Maker/taker fees
    
    Ensures paper trading matches live trading behavior.
    """
    
    def __init__(self):
        self.book_cache = get_book_cache()
        self.price_cache = get_price_cache()
    
    async def execute_market_order(
        self,
        coin: str,
        side: str,
        quantity: float,
        is_reduce_only: bool = False,
        leverage: float = 1.0
    ) -> Fill:
        """
        Execute a simulated market order with realistic slippage.
        
        Uses Gaussian distribution for slippage to add realistic variance
        to paper trading results.
        
        Args:
            coin: Trading pair base (e.g., 'BTC')
            side: 'buy' or 'sell'
            quantity: Order size in base currency
            is_reduce_only: True if closing position (affects fee)
            leverage: Leverage used for this trade (for tracking)
        
        Returns:
            Fill object with complete execution details
        """
        order_id = f"PAPER_{uuid4().hex[:12].upper()}"
        timestamp = datetime.utcnow()
        
        # Get current mid price as reference
        current_price = self.price_cache.get(coin)
        if not current_price:
            # Fallback to book mid price
            book = self.book_cache.get(coin)
            if book:
                current_price = book['mid_price']
            else:
                raise ValueError(f"No price data available for {coin}")
        
        # Calculate fill using order book OR Gaussian simulation
        vwap, slippage_pct, levels_used = self._simulate_fill(coin, side, quantity)
        
        # Track the simulated slippage rate for database
        simulated_slippage_rate = 0.0
        
        if vwap == 0:
            # No order book data - use Gaussian slippage simulation
            simulated_slippage_rate = gaussian_slippage()
            vwap = self._estimate_fill_price_gaussian(current_price, side, simulated_slippage_rate)
            slippage_pct = simulated_slippage_rate * 100
            levels_used = 0
            
            logger.debug(
                f"Using Gaussian slippage for {coin}: {simulated_slippage_rate*100:.4f}%"
            )
        else:
            # Order book available - add small Gaussian noise for realism
            noise = gaussian_slippage() * 0.3  # 30% of normal Gaussian slippage as noise
            simulated_slippage_rate = slippage_pct / 100 + noise
            vwap = vwap * (1 + noise if side == 'buy' else 1 - noise)
            slippage_pct = simulated_slippage_rate * 100
        
        # Calculate costs
        notional = quantity * vwap
        
        # Apply taker fee (market orders always take)
        fee_rate = TAKER_FEE
        fee = notional * fee_rate
        
        # Calculate slippage cost
        if side == 'buy':
            slippage_cost = (vwap - current_price) * quantity
        else:
            slippage_cost = (current_price - vwap) * quantity
        
        # Ensure slippage is non-negative (cost)
        slippage_cost = max(0, slippage_cost)
        
        total_cost = notional + fee
        
        # Simulate funding rate for perpetuals
        funding = simulate_funding_rate()
        
        logger.info(
            f"PAPER FILL: {side.upper()} {quantity:.6f} {coin} @ ${vwap:,.2f} "
            f"(slip: {slippage_pct:.4f}%, fee: ${fee:.2f}, leverage: {leverage}x)"
        )
        
        return Fill(
            order_id=order_id,
            coin=coin,
            side=side,
            quantity=quantity,
            requested_price=current_price,
            fill_price=vwap,
            slippage_cost=slippage_cost,
            slippage_bps=slippage_pct * 100,
            simulated_slippage=simulated_slippage_rate,
            fee=fee,
            fee_rate=fee_rate,
            total_cost=total_cost,
            book_depth_used=levels_used,
            timestamp=timestamp,
            is_paper=True,
            funding_rate=funding,
            leverage=leverage
        )
    
    def _simulate_fill(
        self,
        coin: str,
        side: str,
        quantity: float
    ) -> tuple:
        """
        Simulate order fill using live order book.
        
        Returns:
            (vwap, slippage_percent, levels_used)
        """
        book = self.book_cache.get(coin)
        if not book:
            return (0, 0, 0)
        
        # Select appropriate side of book
        levels = book['asks'] if side == 'buy' else book['bids']
        if not levels:
            return (0, 0, 0)
        
        best_price = levels[0][0]
        
        # Walk through order book levels
        filled = 0
        total_cost = 0
        levels_used = 0
        
        for price, qty in levels:
            fill_qty = min(quantity - filled, qty)
            total_cost += fill_qty * price
            filled += fill_qty
            levels_used += 1
            
            if filled >= quantity:
                break
        
        if filled == 0:
            return (0, 0, 0)
        
        # Handle partial fill (order larger than book depth)
        if filled < quantity:
            # Extrapolate price for remaining quantity
            # Add 0.1% per level beyond book depth
            remaining = quantity - filled
            last_price = levels[-1][0] if levels else best_price
            
            if side == 'buy':
                extrapolated_price = last_price * (1 + 0.001 * (remaining / filled))
            else:
                extrapolated_price = last_price * (1 - 0.001 * (remaining / filled))
            
            total_cost += remaining * extrapolated_price
            filled = quantity
            
            logger.warning(f"Order exceeded book depth for {coin}, extrapolating price")
        
        vwap = total_cost / filled
        slippage_pct = abs(vwap - best_price) / best_price * 100
        
        return (vwap, slippage_pct, levels_used)
    
    def _estimate_fill_price(
        self,
        mid_price: float,
        side: str,
        quantity: float
    ) -> float:
        """
        Estimate fill price when order book is unavailable.
        
        Uses conservative slippage assumptions:
        - Base spread: 0.02%
        - Size impact: 0.01% per $100k notional
        
        Note: For Gaussian slippage, use _estimate_fill_price_gaussian instead.
        """
        notional = quantity * mid_price
        
        # Base half-spread
        base_slippage = 0.0001  # 0.01% (half of 0.02% spread)
        
        # Size-based impact
        size_impact = (notional / 100000) * 0.0001  # 0.01% per $100k
        
        total_slippage = base_slippage + size_impact
        
        if side == 'buy':
            return mid_price * (1 + total_slippage)
        else:
            return mid_price * (1 - total_slippage)
    
    def _estimate_fill_price_gaussian(
        self,
        mid_price: float,
        side: str,
        slippage_rate: float
    ) -> float:
        """
        Estimate fill price using a pre-computed Gaussian slippage rate.
        
        Args:
            mid_price: Current mid price
            side: 'buy' or 'sell'
            slippage_rate: Pre-computed slippage as decimal (e.g., 0.001 = 0.1%)
        
        Returns:
            Estimated fill price with slippage applied
        """
        if side == 'buy':
            return mid_price * (1 + slippage_rate)
        else:
            return mid_price * (1 - slippage_rate)
    
    async def estimate_slippage(
        self,
        coin: str,
        side: str,
        quantity: float
    ) -> dict:
        """
        Estimate slippage for an order without executing.
        
        Useful for pre-trade analysis.
        """
        vwap, slippage_pct, levels = self._simulate_fill(coin, side, quantity)
        
        current_price = self.price_cache.get(coin) or 0
        
        if vwap == 0 and current_price > 0:
            vwap = self._estimate_fill_price(current_price, side, quantity)
            slippage_pct = abs(vwap - current_price) / current_price * 100
        
        notional = quantity * vwap
        fee = notional * TAKER_FEE
        
        return {
            "coin": coin,
            "side": side,
            "quantity": quantity,
            "current_price": current_price,
            "estimated_fill": vwap,
            "slippage_pct": slippage_pct,
            "slippage_cost": abs(vwap - current_price) * quantity if current_price else 0,
            "fee": fee,
            "total_cost": notional + fee,
            "book_levels_needed": levels
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_simulator: Optional[MarketSimulator] = None


def get_market_simulator() -> MarketSimulator:
    """Get or create global market simulator"""
    global _simulator
    if _simulator is None:
        _simulator = MarketSimulator()
    return _simulator
