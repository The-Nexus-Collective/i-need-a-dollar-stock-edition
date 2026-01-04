-- Migration 010: Simple Prediction Trader
-- Simplified schema for the 15-minute prediction trading system

-- Fix paper_trades exit_reason constraint to include 'cycle_close'
DO $$
BEGIN
    ALTER TABLE paper_trades DROP CONSTRAINT IF EXISTS paper_trades_exit_reason_check;
    ALTER TABLE paper_trades ADD CONSTRAINT paper_trades_exit_reason_check 
        CHECK (exit_reason IN ('manual', 'stop_loss', 'take_profit', 'liquidation', 'cycle_close'));
EXCEPTION WHEN OTHERS THEN
    NULL; -- Ignore if constraint doesn't exist
END
$$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTION CYCLES
-- Each 15-minute trading cycle
-- ═══════════════════════════════════════════════════════════════════════════════

-- Create sequence for cycle numbers that persists across restarts
CREATE SEQUENCE IF NOT EXISTS prediction_cycle_seq START 1;

CREATE TABLE IF NOT EXISTS prediction_cycles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_number INTEGER NOT NULL DEFAULT nextval('prediction_cycle_seq'),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    
    -- Capital tracking
    capital_before DECIMAL(18,2) NOT NULL,
    capital_after DECIMAL(18,2),
    total_pnl DECIMAL(18,4),
    
    -- Coins traded this cycle
    coins_traded TEXT[] DEFAULT '{}',
    
    -- Status
    status VARCHAR(20) DEFAULT 'running', -- running, completed, failed
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prediction_cycles_started ON prediction_cycles(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_prediction_cycles_status ON prediction_cycles(status);


-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTIONS
-- Individual coin predictions for each cycle
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cycle_id UUID REFERENCES prediction_cycles(id),
    
    -- Prediction details
    coin VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL, -- LONG or SHORT
    conviction INTEGER NOT NULL CHECK (conviction >= 0 AND conviction <= 100),
    leverage DECIMAL(4,2) NOT NULL,
    reason TEXT,
    
    -- Position info (filled after execution)
    position_id VARCHAR(50),
    entry_price DECIMAL(18,8),
    quantity DECIMAL(18,8),
    size_usdt DECIMAL(18,2),
    
    -- Result (filled when position closes)
    exit_price DECIMAL(18,8),
    pnl DECIMAL(18,4),
    pnl_pct DECIMAL(8,4),
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_cycle ON predictions(cycle_id);
CREATE INDEX IF NOT EXISTS idx_predictions_coin ON predictions(coin);
CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at DESC);


-- ═══════════════════════════════════════════════════════════════════════════════
-- PAPER POSITIONS (Updated for simple trader)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Add columns to existing paper_positions if they don't exist
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'paper_positions' AND column_name = 'prediction_id') THEN
        ALTER TABLE paper_positions ADD COLUMN prediction_id UUID REFERENCES predictions(id);
    END IF;
END
$$;


-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADER STATE
-- Track overall trading system state
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trader_state (
    id VARCHAR(50) PRIMARY KEY DEFAULT 'main',
    current_capital DECIMAL(18,2) NOT NULL DEFAULT 100000,
    starting_capital DECIMAL(18,2) NOT NULL DEFAULT 100000,
    total_cycles INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(18,4) DEFAULT 0,
    max_drawdown DECIMAL(8,4) DEFAULT 0,
    peak_capital DECIMAL(18,2) DEFAULT 100000,
    last_cycle_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Initialize trader state if not exists
INSERT INTO trader_state (id, current_capital, starting_capital)
VALUES ('main', 100000, 100000)
ON CONFLICT (id) DO NOTHING;


-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEWS
-- Useful aggregate views
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_recent_predictions AS
SELECT 
    p.id,
    p.cycle_id,
    c.cycle_number,
    p.coin,
    p.direction,
    p.conviction,
    p.leverage,
    p.reason,
    p.entry_price,
    p.size_usdt,
    p.pnl,
    p.pnl_pct,
    p.created_at
FROM predictions p
LEFT JOIN prediction_cycles c ON p.cycle_id = c.id
ORDER BY p.created_at DESC;


CREATE OR REPLACE VIEW v_cycle_summary AS
SELECT 
    c.id,
    c.cycle_number,
    c.started_at,
    c.completed_at,
    c.capital_before,
    c.capital_after,
    c.total_pnl,
    c.status,
    COUNT(p.id) as prediction_count,
    COUNT(*) FILTER (WHERE p.pnl > 0) as winning_predictions,
    COUNT(*) FILTER (WHERE p.pnl < 0) as losing_predictions,
    AVG(p.conviction) as avg_conviction,
    AVG(p.leverage) as avg_leverage
FROM prediction_cycles c
LEFT JOIN predictions p ON c.id = p.cycle_id
GROUP BY c.id
ORDER BY c.started_at DESC;


-- ═══════════════════════════════════════════════════════════════════════════════
-- GRANTS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Grant permissions if running as superuser
DO $$
BEGIN
    -- These may fail if role doesn't exist, which is fine
    EXECUTE 'GRANT ALL ON prediction_cycles TO trading_app';
    EXECUTE 'GRANT ALL ON predictions TO trading_app';
    EXECUTE 'GRANT ALL ON trader_state TO trading_app';
EXCEPTION WHEN OTHERS THEN
    NULL; -- Ignore role errors
END
$$;

