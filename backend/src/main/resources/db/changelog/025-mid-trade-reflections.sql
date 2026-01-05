-- ═══════════════════════════════════════════════════════════════════════════════
-- MID-TRADE REFLECTIONS
-- Tracks evaluations of open positions against their Pre-Mortem predictions
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS mid_trade_reflections (
    id VARCHAR(64) PRIMARY KEY,
    position_id VARCHAR(64) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Current state at evaluation time
    current_price DECIMAL(20, 8),
    current_pnl_percent DECIMAL(10, 4),
    current_hold_hours INTEGER,
    
    -- Pre-Mortem expectations
    target_pnl_percent DECIMAL(10, 4),
    max_acceptable_loss DECIMAL(10, 4),
    expected_hold_hours_max INTEGER,
    
    -- Evaluation results
    within_pnl_expectations BOOLEAN,
    within_time_expectations BOOLEAN,
    approaching_max_loss BOOLEAN,
    exceeding_target BOOLEAN,
    
    -- Health assessment
    health_status VARCHAR(20),
    recommendation VARCHAR(30),
    health_reason TEXT,
    
    -- Pre-Mortem content for reference
    pre_mortem TEXT,
    bear_case TEXT,
    
    -- Whether this evaluation led to an action
    action_taken VARCHAR(30),
    cycle_number INTEGER
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_mid_trade_reflections_position ON mid_trade_reflections(position_id);
CREATE INDEX IF NOT EXISTS idx_mid_trade_reflections_evaluated ON mid_trade_reflections(evaluated_at DESC);
CREATE INDEX IF NOT EXISTS idx_mid_trade_reflections_status ON mid_trade_reflections(health_status);
CREATE INDEX IF NOT EXISTS idx_mid_trade_reflections_cycle ON mid_trade_reflections(cycle_number);

COMMENT ON TABLE mid_trade_reflections IS 'Records mid-trade evaluations of open positions against their Pre-Mortem predictions';

