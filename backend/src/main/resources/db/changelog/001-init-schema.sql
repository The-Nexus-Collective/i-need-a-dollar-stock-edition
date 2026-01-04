-- ═══════════════════════════════════════════════════════════════════════════════
-- Trading Platform - Consolidated Database Schema
-- Single migration with all tables matching JPA entities
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAPER POSITIONS
-- Tracks all open and closed trading positions
-- Entity: Position.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS paper_positions (
    id VARCHAR(32) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    size_usdt DECIMAL(20, 2) NOT NULL,
    leverage INTEGER DEFAULT 10,
    stop_loss_price DECIMAL(20, 8),
    take_profit_price DECIMAL(20, 8),
    status VARCHAR(20) DEFAULT 'OPEN',
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(20, 8),
    realized_pnl DECIMAL(20, 2) DEFAULT 0,
    conviction DECIMAL(5, 2) DEFAULT 0,
    reasoning TEXT,
    prediction_id VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol ON paper_positions(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_positions_status ON paper_positions(status);
CREATE INDEX IF NOT EXISTS idx_paper_positions_entry_time ON paper_positions(entry_time DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAPER TRADES
-- Complete trade records with entry and exit
-- Entity: Trade.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS paper_trades (
    id VARCHAR(32) PRIMARY KEY,
    position_id VARCHAR(32),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    size_usdt DECIMAL(20, 2) NOT NULL,
    leverage INTEGER DEFAULT 10,
    pnl_usdt DECIMAL(20, 2) NOT NULL,
    pnl_percent DECIMAL(10, 4) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER,
    exit_reason VARCHAR(20) NOT NULL,
    conviction DECIMAL(5, 2) DEFAULT 0,
    reasoning TEXT,
    entry_fee DECIMAL(20, 8),
    exit_fee DECIMAL(20, 8),
    total_fees DECIMAL(20, 8),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_time ON paper_trades(exit_time DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SIGNALS
-- AI-generated trading signals
-- Entity: Signal.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    coin VARCHAR(10) NOT NULL,
    sentiment_score DECIMAL(5, 2) NOT NULL,
    narrative_strength DECIMAL(5, 2) NOT NULL,
    combined_score DECIMAL(8, 4) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    recommended_action VARCHAR(20),
    raw_response TEXT,
    response_hash VARCHAR(64),
    risk_approved BOOLEAN,
    risk_rejection_reason TEXT,
    executed BOOLEAN DEFAULT FALSE,
    leverage_calculated DECIMAL(4, 1),
    market_regime VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_coin ON signals(coin);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADER STATE
-- Singleton table for account state
-- Entity: TraderState.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trader_state (
    id VARCHAR(50) PRIMARY KEY DEFAULT 'main',
    current_capital DECIMAL(18, 2) NOT NULL DEFAULT 100000,
    starting_capital DECIMAL(18, 2) NOT NULL DEFAULT 100000,
    total_cycles INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(18, 4) DEFAULT 0,
    max_drawdown DECIMAL(8, 4) DEFAULT 0,
    peak_capital DECIMAL(18, 2) DEFAULT 100000,
    total_fees_paid DECIMAL(18, 4) DEFAULT 0,
    total_slippage_cost DECIMAL(18, 4) DEFAULT 0,
    last_cycle_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize default trader state
INSERT INTO trader_state (id, current_capital, starting_capital, peak_capital)
VALUES ('main', 100000, 100000, 100000)
ON CONFLICT (id) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- AUDIT LOG
-- Immutable audit trail with hash chaining
-- Entity: AuditLog.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    actor VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id VARCHAR(100),
    before_state JSONB,
    after_state JSONB,
    reasoning TEXT,
    extra_data JSONB DEFAULT '{}',
    prev_hash VARCHAR(64),
    hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor);

-- ═══════════════════════════════════════════════════════════════════════════════
-- RISK EVENTS
-- Risk alerts and circuit breaker events
-- Entity: RiskEvent.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    trigger_value DECIMAL(20, 8),
    threshold_value DECIMAL(20, 8),
    action_taken VARCHAR(100),
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events(severity);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PORTFOLIO SNAPSHOTS
-- Equity curve data points
-- Entity: PortfolioSnapshot.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    timestamp TIMESTAMPTZ PRIMARY KEY,
    total_equity DECIMAL(20, 8) NOT NULL,
    cash DECIMAL(20, 8) NOT NULL,
    positions_value DECIMAL(20, 8) NOT NULL,
    unrealized_pnl DECIMAL(20, 8) NOT NULL,
    realized_pnl DECIMAL(20, 8) NOT NULL,
    daily_pnl DECIMAL(20, 8),
    daily_pnl_percent DECIMAL(8, 4),
    var_95 DECIMAL(20, 8),
    max_drawdown DECIMAL(8, 4),
    win_rate DECIMAL(5, 2),
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_ts ON portfolio_snapshots(timestamp DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADING DECISIONS
-- AI trading decision audit trail
-- Entity: TradingDecision.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trading_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    decision VARCHAR(10) NOT NULL,
    coin VARCHAR(20),
    direction VARCHAR(10),
    size_percent DECIMAL(5, 2),
    stop_loss_percent DECIMAL(5, 2),
    take_profit_percent DECIMAL(5, 2),
    conviction INTEGER,
    reasoning TEXT,
    available_capital DECIMAL(20, 2),
    open_positions_count INTEGER,
    market_context JSONB,
    was_executed BOOLEAN DEFAULT FALSE,
    position_id VARCHAR(32),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trading_decisions_created ON trading_decisions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trading_decisions_decision ON trading_decisions(decision);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTION CYCLES
-- 15-minute trading cycles
-- Entity: PredictionCycle.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS prediction_cycles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cycle_number INTEGER NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    capital_before DECIMAL(18, 2) NOT NULL,
    capital_after DECIMAL(18, 2),
    total_pnl DECIMAL(18, 4),
    coins_traded TEXT[],
    status VARCHAR(20) DEFAULT 'running',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_cycles_started ON prediction_cycles(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_cycles_status ON prediction_cycles(status);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTIONS
-- Individual coin predictions per cycle
-- Entity: Prediction.java
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cycle_id UUID,
    coin VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    conviction INTEGER NOT NULL,
    leverage DECIMAL(4, 2) NOT NULL,
    reason TEXT,
    position_id VARCHAR(50),
    entry_price DECIMAL(18, 8),
    quantity DECIMAL(18, 8),
    size_usdt DECIMAL(18, 2),
    exit_price DECIMAL(18, 8),
    pnl DECIMAL(18, 4),
    pnl_pct DECIMAL(8, 4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_cycle ON predictions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_predictions_coin ON predictions(coin);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);

