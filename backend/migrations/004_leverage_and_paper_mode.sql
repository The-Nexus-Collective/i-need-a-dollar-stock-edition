-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 004: Leverage and Paper Mode Tracking
-- 
-- Adds support for:
-- 1. Adaptive leverage (3-5x) on positions
-- 2. Enhanced paper mode tracking with slippage simulation
-- 3. Virtual pause tracking for circuit breaker simulation
-- 4. Stress test results logging
-- ═══════════════════════════════════════════════════════════════════════════════

-- ─── PART 1: Add leverage column to positions ────────────────────────────────────

ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS leverage NUMERIC(4, 1) DEFAULT 1.0;

ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS liquidation_price NUMERIC(20, 8);

ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS margin_required NUMERIC(20, 8);

-- Update existing positions to have default leverage
UPDATE positions SET leverage = 1.0 WHERE leverage IS NULL;

-- ─── PART 2: Add paper mode tracking columns to trades ───────────────────────────

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS mode VARCHAR(10) DEFAULT 'paper';

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS simulated_slippage NUMERIC(10, 6);

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS would_liquidate BOOLEAN DEFAULT FALSE;

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS stress_scenario VARCHAR(50);

ALTER TABLE trades 
ADD COLUMN IF NOT EXISTS leverage_used NUMERIC(4, 1) DEFAULT 1.0;

-- ─── PART 3: Virtual pause tracking for circuit breaker simulation ───────────────

CREATE TABLE IF NOT EXISTS virtual_pauses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    reason VARCHAR(100) NOT NULL,
    duration_hours INTEGER DEFAULT 24,
    resumed_at TIMESTAMP WITH TIME ZONE,
    paper_mode BOOLEAN DEFAULT TRUE,
    
    -- Context
    equity_at_trigger NUMERIC(20, 2),
    drawdown_pct NUMERIC(10, 4),
    daily_loss_pct NUMERIC(10, 4),
    
    -- Tracking
    trades_blocked INTEGER DEFAULT 0,
    signals_blocked INTEGER DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_virtual_pauses_triggered 
ON virtual_pauses(triggered_at DESC);

CREATE INDEX IF NOT EXISTS idx_virtual_pauses_active 
ON virtual_pauses(resumed_at) WHERE resumed_at IS NULL;

-- ─── PART 4: Stress test results logging ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stress_tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Scenario details
    scenario VARCHAR(100) NOT NULL,
    scenario_params JSONB,
    
    -- Results
    initial_equity NUMERIC(20, 2),
    final_equity NUMERIC(20, 2),
    max_drawdown NUMERIC(10, 4),
    would_survive BOOLEAN,
    positions_liquidated INTEGER DEFAULT 0,
    
    -- Position details at test time
    positions_tested JSONB,
    
    -- Analysis
    notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stress_tests_run_at 
ON stress_tests(run_at DESC);

CREATE INDEX IF NOT EXISTS idx_stress_tests_scenario 
ON stress_tests(scenario);

CREATE INDEX IF NOT EXISTS idx_stress_tests_survival 
ON stress_tests(would_survive);

-- ─── PART 5: Add leverage to signals table ───────────────────────────────────────

ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS leverage_calculated NUMERIC(4, 1);

ALTER TABLE signals 
ADD COLUMN IF NOT EXISTS market_regime VARCHAR(20);

-- ─── PART 6: Paper mode performance stats view ───────────────────────────────────

CREATE OR REPLACE VIEW paper_mode_stats AS
SELECT 
    date_trunc('day', created_at) as trade_date,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
    ROUND(100.0 * SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) as win_rate_pct,
    SUM(pnl) as total_pnl,
    AVG(simulated_slippage) as avg_slippage,
    AVG(leverage_used) as avg_leverage,
    SUM(CASE WHEN would_liquidate THEN 1 ELSE 0 END) as would_have_liquidated
FROM trades
WHERE mode = 'paper'
GROUP BY date_trunc('day', created_at)
ORDER BY trade_date DESC;

-- ─── PART 7: Add columns for readiness tracking ──────────────────────────────────

CREATE TABLE IF NOT EXISTS readiness_checks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Period analyzed
    days_analyzed INTEGER NOT NULL,
    trades_analyzed INTEGER NOT NULL,
    
    -- Metrics
    max_drawdown NUMERIC(10, 4),
    win_rate NUMERIC(10, 4),
    sharpe_ratio NUMERIC(10, 4),
    stress_liquidations INTEGER,
    
    -- Result
    is_ready BOOLEAN NOT NULL,
    recommendation TEXT,
    blockers JSONB,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_readiness_checks_date 
ON readiness_checks(checked_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- END MIGRATION 004
-- ═══════════════════════════════════════════════════════════════════════════════

