"""
Core trading services

Note: The old signal_engine.py and strategy.py have been replaced by the
agentic system in backend/agents/. See:
- agents/sentiment.py - Replaces signal_engine (Grok sentiment)
- agents/strategy_ensemble.py - Replaces strategy (trading decisions)
"""

# Market Data
from .websocket_manager import (
    BinanceWSManager,
    get_ws_manager,
    start_ws_manager,
)

from .price_cache import (
    PriceCache,
    OrderBookCache,
    get_price_cache,
    get_book_cache,
    init_caches,
)

# Trading
from .account import (
    TradingAccount,
    get_trading_account,
    init_trading_account,
    check_simulated_liquidation,
    simulate_margin_call_check,
)

from .market_simulator import (
    MarketSimulator,
    get_market_simulator,
    Fill,
)

from .equity_calculator import (
    EquityCalculator,
    get_equity_calculator,
    init_equity_calculator,
)

# Filters
from .filters import (
    BinanceMarketData,
    check_score_filter,
    check_volume_filter,
    determine_volatility_regime,
    get_current_regime_info,
    get_dynamic_threshold,
)

# Stress Testing & Analysis
from .stress_tester import (
    StressTester,
    get_stress_tester,
    run_stress_test,
    run_all_stress_tests,
    STRESS_SCENARIOS,
)

from .ml_analyzer import (
    MLAnalyzer,
    get_ml_analyzer,
    analyze_paper_trades,
)

from .readiness_check import (
    ReadinessChecker,
    get_readiness_checker,
    check_live_readiness,
    is_ready_for_live,
)

# Health tracking
from .health_tracker import (
    install_health_logging,
    get_health_tracker,
)

# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-ASSET SUPPORT (Optional - for stock trading)
# ═══════════════════════════════════════════════════════════════════════════════

# Multi-Account Manager
from .multi_account import (
    MultiAccountManager,
    get_multi_account_manager,
    init_multi_account_manager,
)

# Market Hours
from .market_hours import (
    MarketHoursManager,
    get_market_hours_manager,
    MarketStatus,
)

# Stock Simulator
from .stock_simulator import (
    StockSimulator,
    get_stock_simulator,
    StockQuote,
    StockFill,
)

# Stock Regime Detection
from .stock_regime import (
    StockRegimeDetector,
    get_stock_regime_detector,
    StockRegimeInfo,
)

# Stock Strategy
from .stock_strategy import (
    StockStrategy,
    get_stock_strategy,
    StockSentiment,
    StockDecision,
)

__all__ = [
    # Market Data
    "BinanceWSManager",
    "get_ws_manager",
    "start_ws_manager",
    "PriceCache",
    "OrderBookCache",
    "get_price_cache",
    "get_book_cache",
    "init_caches",
    # Trading
    "TradingAccount",
    "get_trading_account",
    "init_trading_account",
    "MarketSimulator",
    "get_market_simulator",
    "Fill",
    "EquityCalculator",
    "get_equity_calculator",
    "init_equity_calculator",
    "check_simulated_liquidation",
    "simulate_margin_call_check",
    # Filters
    "BinanceMarketData",
    "check_score_filter",
    "check_volume_filter",
    "determine_volatility_regime",
    "get_current_regime_info",
    "get_dynamic_threshold",
    # Stress Testing & Analysis
    "StressTester",
    "get_stress_tester",
    "run_stress_test",
    "run_all_stress_tests",
    "STRESS_SCENARIOS",
    "MLAnalyzer",
    "get_ml_analyzer",
    "analyze_paper_trades",
    "ReadinessChecker",
    "get_readiness_checker",
    "check_live_readiness",
    "is_ready_for_live",
    # Health
    "install_health_logging",
    "get_health_tracker",
    # Multi-Asset Support
    "MultiAccountManager",
    "get_multi_account_manager",
    "init_multi_account_manager",
    "MarketHoursManager",
    "get_market_hours_manager",
    "MarketStatus",
    "StockSimulator",
    "get_stock_simulator",
    "StockQuote",
    "StockFill",
    "StockRegimeDetector",
    "get_stock_regime_detector",
    "StockRegimeInfo",
    "StockStrategy",
    "get_stock_strategy",
    "StockSentiment",
    "StockDecision",
]
