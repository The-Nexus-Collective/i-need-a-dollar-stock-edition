-- Migration 005: Multi-Asset Trading Support
-- Adds support for separate crypto and stock trading accounts

-- ═══════════════════════════════════════════════════════════════════════════════
-- MODIFY ACCOUNT STATE FOR MULTI-ASSET
-- ═══════════════════════════════════════════════════════════════════════════════

-- Add asset_type column to account_state (if it doesn't exist via primary key change)
-- The account_id now includes asset type (e.g., 'crypto_main', 'stock_main')
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'account_state' AND column_name = 'asset_type') THEN
        ALTER TABLE account_state ADD COLUMN asset_type VARCHAR(20) DEFAULT 'crypto';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'account_state' AND column_name = 'currency') THEN
        ALTER TABLE account_state ADD COLUMN currency VARCHAR(10) DEFAULT 'USDT';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- MODIFY POSITIONS FOR MULTI-ASSET
-- ═══════════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    -- Asset type for positions
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'positions' AND column_name = 'asset_type') THEN
        ALTER TABLE positions ADD COLUMN asset_type VARCHAR(20) DEFAULT 'crypto';
    END IF;
    
    -- Account ID reference
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'positions' AND column_name = 'account_id') THEN
        ALTER TABLE positions ADD COLUMN account_id VARCHAR(50) DEFAULT 'crypto_main';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- MODIFY TRADES FOR MULTI-ASSET
-- ═══════════════════════════════════════════════════════════════════════════════

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'asset_type') THEN
        ALTER TABLE trades ADD COLUMN asset_type VARCHAR(20) DEFAULT 'crypto';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'account_id') THEN
        ALTER TABLE trades ADD COLUMN account_id VARCHAR(50) DEFAULT 'crypto_main';
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- CREATE STOCK-SPECIFIC TABLES
-- ═══════════════════════════════════════════════════════════════════════════════

-- Stock hype scores from X
CREATE TABLE IF NOT EXISTS stock_hype_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(10) NOT NULL,
    score NUMERIC(6, 2) NOT NULL,
    tweet_count INTEGER DEFAULT 0,
    total_engagement NUMERIC(12, 2) DEFAULT 0,
    avg_engagement NUMERIC(10, 2) DEFAULT 0,
    sentiment_score NUMERIC(6, 2) DEFAULT 0,
    top_tweets JSONB DEFAULT '[]',
    query_used TEXT,
    analyzed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_hype_symbol ON stock_hype_scores(symbol);
CREATE INDEX IF NOT EXISTS idx_stock_hype_analyzed ON stock_hype_scores(analyzed_at);

-- Market regime snapshots
CREATE TABLE IF NOT EXISTS market_regimes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_type VARCHAR(20) NOT NULL,
    
    -- Crypto regime (BTC ATR based)
    btc_atr_percent NUMERIC(6, 4),
    crypto_regime VARCHAR(20),
    crypto_threshold NUMERIC(6, 2),
    
    -- Stock regime (VIX based)
    vix_value NUMERIC(6, 2),
    stock_regime VARCHAR(20),
    stock_threshold NUMERIC(6, 2),
    stock_should_trade BOOLEAN DEFAULT TRUE,
    
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_market_regime_type ON market_regimes(asset_type);
CREATE INDEX IF NOT EXISTS idx_market_regime_time ON market_regimes(recorded_at);

-- Stock trading decisions
CREATE TABLE IF NOT EXISTS stock_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    action VARCHAR(20) NOT NULL,  -- 'trade', 'skip', 'flatten'
    skip_reason TEXT,
    
    -- Market context
    market_open BOOLEAN NOT NULL,
    vix_value NUMERIC(6, 2),
    regime VARCHAR(20),
    score_threshold NUMERIC(6, 2),
    
    -- Selections
    core_picks JSONB DEFAULT '[]',
    reserved_picks JSONB DEFAULT '[]',
    
    -- Sizing
    leverage NUMERIC(4, 2) DEFAULT 1.0,
    total_position_size NUMERIC(20, 8) DEFAULT 0,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stock_decisions_action ON stock_decisions(action);
CREATE INDEX IF NOT EXISTS idx_stock_decisions_time ON stock_decisions(created_at);

-- ═══════════════════════════════════════════════════════════════════════════════
-- INSERT DEFAULT ACCOUNTS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Create stock account if it doesn't exist
INSERT INTO account_state (account_id, account_type, asset_type, currency, balance_usdt, initial_balance, highest_equity, lowest_equity)
VALUES ('stock_main', 'paper', 'stock', 'USD', 100000, 100000, 100000, 100000)
ON CONFLICT (account_id) DO NOTHING;

-- Ensure crypto account exists with updated fields
INSERT INTO account_state (account_id, account_type, asset_type, currency, balance_usdt, initial_balance, highest_equity, lowest_equity)
VALUES ('crypto_main', 'paper', 'crypto', 'USDT', 100000, 100000, 100000, 100000)
ON CONFLICT (account_id) DO UPDATE SET asset_type = 'crypto', currency = 'USDT';

-- ═══════════════════════════════════════════════════════════════════════════════
-- PORTFOLIO SUMMARY VIEW
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW portfolio_summary AS
SELECT 
    a.account_id,
    a.asset_type,
    a.currency,
    a.balance_usdt as balance,
    a.initial_balance,
    COALESCE(p.open_positions, 0) as open_positions,
    COALESCE(p.positions_value, 0) as positions_value,
    a.balance_usdt + COALESCE(p.positions_value, 0) as equity,
    (a.balance_usdt + COALESCE(p.positions_value, 0) - a.initial_balance) as total_pnl,
    CASE WHEN a.initial_balance > 0 
         THEN ((a.balance_usdt + COALESCE(p.positions_value, 0) - a.initial_balance) / a.initial_balance * 100)
         ELSE 0 
    END as total_pnl_pct
FROM account_state a
LEFT JOIN (
    SELECT 
        account_id,
        COUNT(*) as open_positions,
        SUM(quantity * current_price) as positions_value
    FROM positions 
    WHERE status = 'open'
    GROUP BY account_id
) p ON a.account_id = p.account_id;

COMMENT ON VIEW portfolio_summary IS 'Multi-asset portfolio summary with P&L';

