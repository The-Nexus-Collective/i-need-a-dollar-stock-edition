-- Migration 006: Velocity Metrics for Aggressive Trading Mode
-- Adds tracking for trades/hour, trades/day, deployment %, rebalances

-- ═══════════════════════════════════════════════════════════════════════════════
-- ACCOUNT STATE - Add velocity tracking
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE account_state ADD COLUMN IF NOT EXISTS trades_today INTEGER DEFAULT 0;
ALTER TABLE account_state ADD COLUMN IF NOT EXISTS trades_this_hour INTEGER DEFAULT 0;
ALTER TABLE account_state ADD COLUMN IF NOT EXISTS rebalances_today INTEGER DEFAULT 0;
ALTER TABLE account_state ADD COLUMN IF NOT EXISTS last_trade_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE account_state ADD COLUMN IF NOT EXISTS force_trade_enabled BOOLEAN DEFAULT FALSE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PORTFOLIO SNAPSHOTS - Add deployment tracking
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS deployment_percent NUMERIC(5, 4);
ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS positions_count INTEGER DEFAULT 0;
ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS trades_this_cycle INTEGER DEFAULT 0;
ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS rebalances_this_cycle INTEGER DEFAULT 0;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADING DECISIONS - Enhanced tracking
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trading_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id VARCHAR(32) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Decision info
    decision VARCHAR(20) NOT NULL,  -- 'trade', 'filtered', 'flat', 'force_trade'
    filter_reason TEXT,
    
    -- Coins traded this cycle
    coins_selected INTEGER DEFAULT 0,
    trades_executed INTEGER DEFAULT 0,
    rebalances_executed INTEGER DEFAULT 0,
    
    -- Deployment
    deployment_before NUMERIC(5, 4),
    deployment_after NUMERIC(5, 4),
    target_deployment NUMERIC(5, 4) DEFAULT 0.80,
    
    -- Regime info
    volatility_regime VARCHAR(20),
    score_threshold NUMERIC(5, 2),
    btc_atr_percent NUMERIC(6, 4),
    
    -- Force trade mode
    force_traded BOOLEAN DEFAULT FALSE,
    
    -- Raw data
    grok_success BOOLEAN DEFAULT FALSE,
    request_hash VARCHAR(64),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decisions_timestamp ON trading_decisions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_batch ON trading_decisions(batch_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADES - Add rebalance flag
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE trades ADD COLUMN IF NOT EXISTS is_rebalance BOOLEAN DEFAULT FALSE;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_id UUID REFERENCES trading_decisions(id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADE VELOCITY VIEW - For dashboard
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW trade_velocity AS
SELECT 
    -- Last hour
    COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '1 hour') as trades_last_hour,
    COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '1 hour' AND is_rebalance = TRUE) as rebalances_last_hour,
    
    -- Today
    COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE) as trades_today,
    COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE AND is_rebalance = TRUE) as rebalances_today,
    
    -- Last 24 hours (rolling)
    COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '24 hours') as trades_24h,
    
    -- Averages
    ROUND(COUNT(*) FILTER (WHERE executed_at > NOW() - INTERVAL '24 hours')::NUMERIC / 24, 1) as avg_trades_per_hour,
    
    -- Target: 100+ trades/day
    CASE 
        WHEN COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE) >= 100 THEN 'ON_TARGET'
        WHEN COUNT(*) FILTER (WHERE executed_at > CURRENT_DATE) >= 50 THEN 'MODERATE'
        ELSE 'BELOW_TARGET'
    END as velocity_status
FROM trades
WHERE is_paper = TRUE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- DEPLOYMENT METRICS VIEW
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW deployment_metrics AS
SELECT 
    timestamp,
    deployment_percent,
    positions_count,
    total_equity,
    position_value,
    CASE 
        WHEN deployment_percent >= 0.80 THEN 'ON_TARGET'
        WHEN deployment_percent >= 0.60 THEN 'MODERATE'
        ELSE 'LOW'
    END as deployment_status
FROM portfolio_snapshots
ORDER BY timestamp DESC
LIMIT 100;

-- ═══════════════════════════════════════════════════════════════════════════════
-- HOURLY VELOCITY RESET FUNCTION
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION reset_hourly_velocity()
RETURNS void AS $$
BEGIN
    UPDATE account_state SET trades_this_hour = 0;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════════
-- DAILY VELOCITY RESET FUNCTION
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION reset_daily_velocity()
RETURNS void AS $$
BEGIN
    UPDATE account_state SET 
        trades_today = 0,
        rebalances_today = 0;
END;
$$ LANGUAGE plpgsql;

