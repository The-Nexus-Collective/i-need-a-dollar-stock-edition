-- Trading Engine Tables
-- Adds tables for paper trading positions, trade history, and trade signals

-- Enable UUID extension if not already
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAPER POSITIONS
-- Tracks all open and closed positions
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS paper_positions (
    id VARCHAR(32) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    
    -- Entry details
    entry_price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    size_usdt DECIMAL(20, 2) NOT NULL,
    leverage INTEGER DEFAULT 10,
    
    -- Stop/Target
    stop_loss_price DECIMAL(20, 8),
    take_profit_price DECIMAL(20, 8),
    
    -- Status
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'STOPPED_OUT', 'TAKE_PROFIT')),
    entry_time TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    exit_time TIMESTAMP WITH TIME ZONE,
    exit_price DECIMAL(20, 8),
    
    -- PnL
    realized_pnl DECIMAL(20, 2) DEFAULT 0,
    
    -- Metadata
    conviction DECIMAL(5, 2) DEFAULT 0,
    reasoning TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_positions_symbol ON paper_positions(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_positions_status ON paper_positions(status);
CREATE INDEX IF NOT EXISTS idx_paper_positions_entry_time ON paper_positions(entry_time);

-- ═══════════════════════════════════════════════════════════════════════════════
-- PAPER TRADES
-- Complete trade records with entry and exit
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS paper_trades (
    id VARCHAR(32) PRIMARY KEY,
    position_id VARCHAR(32) REFERENCES paper_positions(id),
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    
    -- Prices
    entry_price DECIMAL(20, 8) NOT NULL,
    exit_price DECIMAL(20, 8) NOT NULL,
    
    -- Size
    quantity DECIMAL(20, 8) NOT NULL,
    size_usdt DECIMAL(20, 2) NOT NULL,
    leverage INTEGER DEFAULT 10,
    
    -- PnL
    pnl_usdt DECIMAL(20, 2) NOT NULL,
    pnl_percent DECIMAL(10, 4) NOT NULL,
    
    -- Timing
    entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
    exit_time TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_seconds INTEGER,
    
    -- Exit type
    exit_reason VARCHAR(20) NOT NULL CHECK (exit_reason IN ('manual', 'stop_loss', 'take_profit', 'liquidation', 'cycle_close')),
    
    -- Metadata
    conviction DECIMAL(5, 2) DEFAULT 0,
    reasoning TEXT,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_exit_time ON paper_trades(exit_time);
CREATE INDEX IF NOT EXISTS idx_paper_trades_pnl ON paper_trades(pnl_usdt);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADE SIGNALS
-- Records the signals that led to trades
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trade_signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id VARCHAR(32) REFERENCES paper_trades(id),
    position_id VARCHAR(32) REFERENCES paper_positions(id),
    
    -- Signal details
    signal_type VARCHAR(50) NOT NULL,
    sender_id VARCHAR(50) NOT NULL,
    sender_name VARCHAR(100),
    topic VARCHAR(100),
    content TEXT,
    
    -- Metrics
    confidence DECIMAL(5, 4) DEFAULT 0.5,
    urgency DECIMAL(5, 4) DEFAULT 0.5,
    importance DECIMAL(5, 4) DEFAULT 0.5,
    
    -- Data
    signal_data JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_signals_position ON trade_signals(position_id);
CREATE INDEX IF NOT EXISTS idx_trade_signals_trade ON trade_signals(trade_id);
CREATE INDEX IF NOT EXISTS idx_trade_signals_created ON trade_signals(created_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- ACCOUNT STATE
-- Tracks paper trading account state
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS account_state (
    account_id VARCHAR(50) PRIMARY KEY DEFAULT 'paper_main',
    balance_usdt DECIMAL(20, 2) DEFAULT 100000,
    initial_balance DECIMAL(20, 2) DEFAULT 100000,
    
    -- Statistics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(20, 2) DEFAULT 0,
    
    -- Daily tracking
    daily_start_balance DECIMAL(20, 2) DEFAULT 100000,
    daily_pnl DECIMAL(20, 2) DEFAULT 0,
    daily_trades INTEGER DEFAULT 0,
    last_daily_reset DATE DEFAULT CURRENT_DATE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default paper account if not exists
INSERT INTO account_state (account_id, balance_usdt, initial_balance)
VALUES ('paper_main', 100000, 100000)
ON CONFLICT (account_id) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADING DECISIONS
-- Records Tactician's structured trade decisions
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trading_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    -- Decision
    decision VARCHAR(10) NOT NULL CHECK (decision IN ('TRADE', 'WAIT', 'PASS')),
    coin VARCHAR(20),
    direction VARCHAR(10) CHECK (direction IN ('LONG', 'SHORT') OR direction IS NULL),
    
    -- Sizing
    size_percent DECIMAL(5, 2),
    stop_loss_percent DECIMAL(5, 2),
    take_profit_percent DECIMAL(5, 2),
    
    -- Confidence
    conviction INTEGER CHECK (conviction >= 0 AND conviction <= 100),
    reasoning TEXT,
    
    -- Context
    available_capital DECIMAL(20, 2),
    open_positions_count INTEGER,
    market_context JSONB,
    
    -- Execution
    was_executed BOOLEAN DEFAULT FALSE,
    position_id VARCHAR(32) REFERENCES paper_positions(id),
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trading_decisions_created ON trading_decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_trading_decisions_decision ON trading_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_trading_decisions_executed ON trading_decisions(was_executed);

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEWS
-- Helpful aggregations
-- ═══════════════════════════════════════════════════════════════════════════════

-- View: Recent performance summary
CREATE OR REPLACE VIEW trading_performance AS
SELECT 
    COUNT(*) as total_trades,
    COUNT(*) FILTER (WHERE pnl_usdt > 0) as winning_trades,
    COUNT(*) FILTER (WHERE pnl_usdt < 0) as losing_trades,
    COALESCE(SUM(pnl_usdt), 0) as total_pnl,
    COALESCE(AVG(pnl_usdt), 0) as avg_pnl,
    COALESCE(AVG(pnl_percent), 0) as avg_pnl_percent,
    COALESCE(AVG(duration_seconds), 0) as avg_duration_seconds,
    CASE 
        WHEN COUNT(*) > 0 THEN 
            ROUND(COUNT(*) FILTER (WHERE pnl_usdt > 0)::DECIMAL / COUNT(*)::DECIMAL * 100, 2)
        ELSE 0 
    END as win_rate
FROM paper_trades
WHERE exit_time >= NOW() - INTERVAL '30 days';

-- View: Open positions with current value
CREATE OR REPLACE VIEW open_positions_view AS
SELECT 
    p.*,
    a.balance_usdt as account_balance,
    ROUND((p.size_usdt / a.balance_usdt) * 100, 2) as position_percent
FROM paper_positions p
CROSS JOIN account_state a
WHERE p.status = 'OPEN'
ORDER BY p.entry_time DESC;

-- View: Daily trading summary
CREATE OR REPLACE VIEW daily_trading_summary AS
SELECT 
    DATE(exit_time) as trade_date,
    COUNT(*) as trades,
    COUNT(*) FILTER (WHERE pnl_usdt > 0) as wins,
    COUNT(*) FILTER (WHERE pnl_usdt < 0) as losses,
    SUM(pnl_usdt) as total_pnl,
    ROUND(AVG(pnl_percent), 2) as avg_pnl_percent,
    CASE 
        WHEN COUNT(*) > 0 THEN 
            ROUND(COUNT(*) FILTER (WHERE pnl_usdt > 0)::DECIMAL / COUNT(*)::DECIMAL * 100, 2)
        ELSE 0 
    END as win_rate
FROM paper_trades
GROUP BY DATE(exit_time)
ORDER BY trade_date DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Function: Update account state after trade
CREATE OR REPLACE FUNCTION update_account_after_trade(
    p_pnl DECIMAL,
    p_is_win BOOLEAN
) RETURNS VOID AS $$
BEGIN
    UPDATE account_state
    SET 
        balance_usdt = balance_usdt + p_pnl,
        total_trades = total_trades + 1,
        winning_trades = winning_trades + CASE WHEN p_is_win THEN 1 ELSE 0 END,
        total_pnl = total_pnl + p_pnl,
        daily_pnl = CASE 
            WHEN last_daily_reset = CURRENT_DATE THEN daily_pnl + p_pnl
            ELSE p_pnl
        END,
        daily_trades = CASE 
            WHEN last_daily_reset = CURRENT_DATE THEN daily_trades + 1
            ELSE 1
        END,
        daily_start_balance = CASE 
            WHEN last_daily_reset != CURRENT_DATE THEN balance_usdt - p_pnl
            ELSE daily_start_balance
        END,
        last_daily_reset = CURRENT_DATE,
        updated_at = NOW()
    WHERE account_id = 'paper_main';
END;
$$ LANGUAGE plpgsql;

