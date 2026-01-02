-- ═══════════════════════════════════════════════════════════════════════════
-- Migration: Add filter columns to signals table
-- Version: 002
-- Description: Add columns for score/volume filters and market data
-- ═══════════════════════════════════════════════════════════════════════════

-- Add filter result columns
ALTER TABLE signals ADD COLUMN IF NOT EXISTS filter_score_pass BOOLEAN;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS filter_volume_pass BOOLEAN;

-- Add market data columns
ALTER TABLE signals ADD COLUMN IF NOT EXISTS volume_1h DECIMAL(20, 8);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS volume_24h_avg DECIMAL(20, 8);
ALTER TABLE signals ADD COLUMN IF NOT EXISTS atr_1h DECIMAL(20, 8);

-- Add current price at signal time
ALTER TABLE signals ADD COLUMN IF NOT EXISTS price_at_signal DECIMAL(20, 8);

-- Add batch tracking (all signals from same Grok call share this)
ALTER TABLE signals ADD COLUMN IF NOT EXISTS batch_id VARCHAR(64);

-- Create index for batch queries
CREATE INDEX IF NOT EXISTS idx_signals_batch_id ON signals (batch_id);

-- Create index for filter analysis
CREATE INDEX IF NOT EXISTS idx_signals_filters ON signals (filter_score_pass, filter_volume_pass);

-- ═══════════════════════════════════════════════════════════════════════════
-- Add trading_decisions table for detailed decision logging
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trading_decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    batch_id VARCHAR(64) NOT NULL,
    
    -- Selected coin (or null if filtered out)
    selected_coin VARCHAR(10),
    selected_score DECIMAL(10, 4),
    
    -- Decision outcome
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('long', 'short', 'flat', 'filtered')),
    filter_reason VARCHAR(100),
    
    -- Position details (if trading)
    position_size DECIMAL(20, 8),
    entry_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    atr_value DECIMAL(20, 8),
    
    -- Portfolio state
    equity_before DECIMAL(20, 8),
    risk_amount DECIMAL(20, 8),
    
    -- All scores snapshot (JSON)
    all_scores JSONB,
    
    -- Grok response
    grok_raw_response TEXT,
    request_hash VARCHAR(64),
    
    -- Execution
    executed BOOLEAN DEFAULT FALSE,
    execution_id UUID,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Note: Not using hypertable since UUID primary key is needed
CREATE INDEX IF NOT EXISTS idx_trading_decisions_timestamp ON trading_decisions (timestamp);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trading_decisions_batch ON trading_decisions (batch_id);
CREATE INDEX IF NOT EXISTS idx_trading_decisions_decision ON trading_decisions (decision);
CREATE INDEX IF NOT EXISTS idx_trading_decisions_coin ON trading_decisions (selected_coin);

-- ═══════════════════════════════════════════════════════════════════════════
-- Add filter_stats view for dashboard
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_filter_stats_today AS
SELECT 
    COUNT(*) as total_hours,
    COUNT(*) FILTER (WHERE decision = 'long' OR decision = 'short') as traded_hours,
    COUNT(*) FILTER (WHERE decision = 'flat') as flat_hours,
    COUNT(*) FILTER (WHERE decision = 'filtered') as filtered_hours,
    COUNT(*) FILTER (WHERE filter_reason LIKE '%score%') as filtered_score,
    COUNT(*) FILTER (WHERE filter_reason LIKE '%volume%') as filtered_volume,
    COUNT(*) FILTER (WHERE filter_reason LIKE '%api%') as filtered_api_error
FROM trading_decisions
WHERE timestamp >= CURRENT_DATE;
