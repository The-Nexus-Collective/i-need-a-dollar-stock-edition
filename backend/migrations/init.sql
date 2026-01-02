-- ═══════════════════════════════════════════════════════════════════════════
-- Production Trading Platform - Database Initialization
-- ═══════════════════════════════════════════════════════════════════════════

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════════════
-- AUDIT LOG (Immutable, Hash-Chained)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL,
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
    hash VARCHAR(64) NOT NULL,
    
    PRIMARY KEY (id, timestamp),
    CONSTRAINT audit_log_immutable CHECK (TRUE)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('audit_log', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log (actor);

-- ═══════════════════════════════════════════════════════════════════════════
-- POSITIONS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    coin VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('long', 'short')),
    quantity DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    status VARCHAR(20) NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'liquidated')),
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_coin ON positions (coin);

-- ═══════════════════════════════════════════════════════════════════════════
-- TRADES (Execution Records)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID REFERENCES positions(id),
    order_id VARCHAR(100),
    exchange_order_id VARCHAR(100),
    coin VARCHAR(10) NOT NULL,
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('market', 'limit', 'stop', 'take_profit')),
    quantity DECIMAL(20, 8) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    fee DECIMAL(20, 8) DEFAULT 0,
    fee_currency VARCHAR(10),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected')),
    is_paper BOOLEAN NOT NULL DEFAULT TRUE,
    executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Note: Not using hypertable for trades since UUID primary key is needed for foreign key references

CREATE INDEX IF NOT EXISTS idx_trades_position ON trades (position_id);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status);

-- ═══════════════════════════════════════════════════════════════════════════
-- SIGNALS (AI-Generated Trading Signals)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    coin VARCHAR(10) NOT NULL,
    sentiment_score DECIMAL(5, 2) NOT NULL,
    narrative_strength DECIMAL(5, 2) NOT NULL,
    combined_score DECIMAL(8, 4) NOT NULL,
    confidence DECIMAL(5, 4) NOT NULL,
    recommended_action VARCHAR(20) CHECK (recommended_action IN ('long', 'short', 'hold', 'close')),
    raw_response TEXT,
    response_hash VARCHAR(64),
    risk_approved BOOLEAN,
    risk_rejection_reason TEXT,
    executed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Note: Not using hypertable for signals since UUID primary key is needed
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals (timestamp);
CREATE INDEX IF NOT EXISTS idx_signals_coin ON signals (coin);
CREATE INDEX IF NOT EXISTS idx_signals_executed ON signals (executed);

-- ═══════════════════════════════════════════════════════════════════════════
-- PORTFOLIO SNAPSHOTS (For Equity Curve)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    timestamp TIMESTAMPTZ NOT NULL,
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
    losing_trades INTEGER DEFAULT 0,
    PRIMARY KEY (timestamp)
);

-- Convert to hypertable
SELECT create_hypertable('portfolio_snapshots', 'timestamp', if_not_exists => TRUE);

-- ═══════════════════════════════════════════════════════════════════════════
-- RISK EVENTS
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('info', 'warning', 'critical', 'emergency')),
    trigger_value DECIMAL(20, 8),
    threshold_value DECIMAL(20, 8),
    action_taken VARCHAR(100),
    details JSONB,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by VARCHAR(100),
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Note: Not using hypertable for risk_events since UUID primary key is needed
CREATE INDEX IF NOT EXISTS idx_risk_events_timestamp ON risk_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON risk_events (event_type);
CREATE INDEX IF NOT EXISTS idx_risk_events_severity ON risk_events (severity);

-- ═══════════════════════════════════════════════════════════════════════════
-- MARKET DATA (Price Cache)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS market_data (
    timestamp TIMESTAMPTZ NOT NULL,
    coin VARCHAR(10) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    volume_24h DECIMAL(30, 8),
    price_change_24h DECIMAL(10, 4),
    high_24h DECIMAL(20, 8),
    low_24h DECIMAL(20, 8),
    PRIMARY KEY (timestamp, coin)
);

-- Convert to hypertable
SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

-- ═══════════════════════════════════════════════════════════════════════════
-- SYSTEM CONFIG
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Insert default risk parameters
INSERT INTO system_config (key, value, description) VALUES
    ('risk.position_limit_per_asset', '0.10', 'Max portfolio % in single asset'),
    ('risk.position_limit_altcoins', '0.30', 'Max portfolio % in altcoins'),
    ('risk.max_deployed', '0.80', 'Max portfolio % deployed'),
    ('risk.drawdown_level_1', '0.05', 'Level 1 circuit breaker threshold'),
    ('risk.drawdown_level_2', '0.10', 'Level 2 circuit breaker threshold'),
    ('risk.drawdown_level_3', '0.15', 'Level 3 circuit breaker threshold'),
    ('risk.var_limit', '0.03', 'Max VaR as % of portfolio'),
    ('trading.stop_loss_atr', '1.5', 'Stop loss as ATR multiple'),
    ('trading.take_profit_atr', '4.0', 'Take profit as ATR multiple'),
    ('trading.risk_per_trade', '0.02', 'Risk % per trade')
ON CONFLICT (key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to positions
CREATE TRIGGER positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════════════════════════════════════════════
-- VIEWS
-- ═══════════════════════════════════════════════════════════════════════════

-- Current portfolio state
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT 
    (SELECT COALESCE(SUM(quantity * current_price), 0) FROM positions WHERE status = 'open') as positions_value,
    (SELECT COALESCE(SUM(unrealized_pnl), 0) FROM positions WHERE status = 'open') as unrealized_pnl,
    (SELECT COALESCE(SUM(realized_pnl), 0) FROM positions) as total_realized_pnl,
    (SELECT COUNT(*) FROM positions WHERE status = 'open') as open_positions,
    (SELECT COUNT(*) FROM trades WHERE created_at > NOW() - INTERVAL '24 hours') as trades_24h;

-- Open positions with current P&L
CREATE OR REPLACE VIEW v_open_positions AS
SELECT 
    p.*,
    CASE 
        WHEN p.side = 'long' THEN (p.current_price - p.entry_price) * p.quantity
        ELSE (p.entry_price - p.current_price) * p.quantity
    END as calculated_pnl,
    CASE 
        WHEN p.side = 'long' THEN ((p.current_price - p.entry_price) / p.entry_price) * 100
        ELSE ((p.entry_price - p.current_price) / p.entry_price) * 100
    END as pnl_percent
FROM positions p
WHERE p.status = 'open';

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO trading_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO trading_user;
