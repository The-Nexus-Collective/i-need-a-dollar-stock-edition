"""Core trading services"""

# Signal Engine (Grok API)
from .signal_engine import (
    GrokBatchClient,
    fetch_all_sentiments,
    TOP_COINS,
)

# Strategy
from .strategy import (
    StrategyEngine,
    run_trading_cycle,
    TradingDecision,
)

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

# Leverage calculation
from .strategy import (
    calculate_adaptive_leverage,
    detect_market_regime,
)

# Liquidation simulation
from .account import (
    check_simulated_liquidation,
    simulate_margin_call_check,
)

__all__ = [
    # Signal
    "GrokBatchClient",
    "fetch_all_sentiments",
    "TOP_COINS",
    # Strategy
    "StrategyEngine",
    "run_trading_cycle",
    "TradingDecision",
    "calculate_adaptive_leverage",
    "detect_market_regime",
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
]