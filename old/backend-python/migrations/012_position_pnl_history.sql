-- Migration 012: Position PnL History
-- Tracks position PnL over time for historical analysis and Grok context

-- ═══════════════════════════════════════════════════════════════════════════════
-- POSITION PNL HISTORY
-- Records position PnL snapshots every minute for trend analysis
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS position_pnl_history (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    position_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    
    -- Price data
    entry_price DECIMAL(20, 8) NOT NULL,
    current_price DECIMAL(20, 8) NOT NULL,
    
    -- PnL metrics
    unrealized_pnl DECIMAL(20, 4) NOT NULL,
    unrealized_pnl_pct DECIMAL(10, 4) NOT NULL,
    
    -- Risk metrics
    leverage INTEGER NOT NULL DEFAULT 1,
    margin_risk_pct DECIMAL(8, 4) NOT NULL DEFAULT 0,
    liquidation_price DECIMAL(20, 8),
    
    -- Position sizing
    size_usdt DECIMAL(20, 2) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_position_pnl_history_ts ON position_pnl_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_position_pnl_history_pos ON position_pnl_history(position_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_position_pnl_history_symbol ON position_pnl_history(symbol, timestamp DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- EQUITY SNAPSHOTS ENHANCEMENTS
-- Add missing columns to portfolio_snapshots if they don't exist
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS open_positions_count INTEGER DEFAULT 0;
ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS total_margin_used DECIMAL(20, 8) DEFAULT 0;
ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS avg_margin_risk_pct DECIMAL(8, 4) DEFAULT 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEW: Recent Position PnL Trend
-- Shows PnL evolution for each position over time
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_position_pnl_trend AS
SELECT 
    position_id,
    symbol,
    direction,
    timestamp,
    current_price,
    unrealized_pnl,
    unrealized_pnl_pct,
    margin_risk_pct,
    LAG(unrealized_pnl) OVER (PARTITION BY position_id ORDER BY timestamp) as prev_pnl,
    unrealized_pnl - LAG(unrealized_pnl) OVER (PARTITION BY position_id ORDER BY timestamp) as pnl_change
FROM position_pnl_history
ORDER BY timestamp DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- CLEANUP: Auto-delete old history (keep 7 days)
-- ═══════════════════════════════════════════════════════════════════════════════

-- Function to clean up old position history
CREATE OR REPLACE FUNCTION cleanup_position_pnl_history() RETURNS void AS $$
BEGIN
    DELETE FROM position_pnl_history WHERE timestamp < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Comment for documentation
COMMENT ON TABLE position_pnl_history IS 'Minute-by-minute position PnL snapshots for trend analysis';
COMMENT ON COLUMN position_pnl_history.margin_risk_pct IS 'How close to liquidation (0=safe, 100=liquidated)';

