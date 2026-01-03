-- ═══════════════════════════════════════════════════════════════════════════
-- Migration: Persistent Account State
-- Version: 003
-- Description: Account state that survives restarts/rebuilds
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════
-- ACCOUNT STATE TABLE
-- Stores persistent trading account balance and statistics
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS account_state (
    -- Account identification
    account_id VARCHAR(50) PRIMARY KEY,
    account_type VARCHAR(20) NOT NULL DEFAULT 'paper' CHECK (account_type IN ('paper', 'live')),
    
    -- Balances
    balance_usdt DECIMAL(20, 8) NOT NULL,
    initial_balance DECIMAL(20, 8) NOT NULL,
    
    -- Cost tracking
    total_fees_paid DECIMAL(20, 8) DEFAULT 0,
    total_slippage_cost DECIMAL(20, 8) DEFAULT 0,
    total_funding_paid DECIMAL(20, 8) DEFAULT 0,
    
    -- Trade statistics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    total_volume_traded DECIMAL(20, 8) DEFAULT 0,
    
    -- PnL tracking
    realized_pnl DECIMAL(20, 8) DEFAULT 0,
    highest_equity DECIMAL(20, 8),
    lowest_equity DECIMAL(20, 8),
    max_drawdown DECIMAL(10, 6) DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_trade_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════
-- INITIALIZE PAPER TRADING ACCOUNT
-- 100k EUR ≈ 108,000 USDT at current rates
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO account_state (
    account_id,
    account_type,
    balance_usdt,
    initial_balance,
    highest_equity,
    lowest_equity
) VALUES (
    'paper_main',
    'paper',
    108000.00000000,  -- 100k EUR in USDT
    108000.00000000,
    108000.00000000,
    108000.00000000
) ON CONFLICT (account_id) DO NOTHING;

-- ═══════════════════════════════════════════════════════════════════════════
-- ACCOUNT HISTORY TABLE
-- Tracks equity snapshots for charting (every second when active)
-- ═══════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS account_equity_history (
    id BIGSERIAL,
    account_id VARCHAR(50) NOT NULL REFERENCES account_state(account_id),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Equity breakdown
    equity DECIMAL(20, 8) NOT NULL,
    cash DECIMAL(20, 8) NOT NULL,
    positions_value DECIMAL(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    
    -- Market state
    btc_price DECIMAL(20, 8),
    
    PRIMARY KEY (id, timestamp)
);

-- Index for time-series queries (standard PostgreSQL, no TimescaleDB)
CREATE INDEX IF NOT EXISTS idx_account_equity_timestamp 
    ON account_equity_history (timestamp DESC);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_account_equity_account 
    ON account_equity_history (account_id, timestamp DESC);

-- ═══════════════════════════════════════════════════════════════════════════
-- TRADE EXECUTION DETAILS
-- Extends trades table with realistic cost tracking
-- ═══════════════════════════════════════════════════════════════════════════

-- Add columns to existing trades table if they don't exist
DO $$
BEGIN
    -- Slippage tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'slippage_cost') THEN
        ALTER TABLE trades ADD COLUMN slippage_cost DECIMAL(20, 8);
    END IF;
    
    -- Fee rate used
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'fee_rate') THEN
        ALTER TABLE trades ADD COLUMN fee_rate DECIMAL(10, 6);
    END IF;
    
    -- Volume-weighted average price
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'fill_vwap') THEN
        ALTER TABLE trades ADD COLUMN fill_vwap DECIMAL(20, 8);
    END IF;
    
    -- Order book levels consumed
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'book_depth_used') THEN
        ALTER TABLE trades ADD COLUMN book_depth_used INTEGER;
    END IF;
    
    -- Requested vs filled price
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'requested_price') THEN
        ALTER TABLE trades ADD COLUMN requested_price DECIMAL(20, 8);
    END IF;
    
    -- Total cost including fees
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'trades' AND column_name = 'total_cost') THEN
        ALTER TABLE trades ADD COLUMN total_cost DECIMAL(20, 8);
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════
-- HELPER FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════

-- Function to update account state after trade
CREATE OR REPLACE FUNCTION update_account_after_trade(
    p_account_id VARCHAR(50),
    p_pnl DECIMAL(20, 8),
    p_fees DECIMAL(20, 8),
    p_slippage DECIMAL(20, 8),
    p_is_winner BOOLEAN
) RETURNS VOID AS $$
BEGIN
    UPDATE account_state SET
        balance_usdt = balance_usdt + p_pnl - p_fees,
        total_fees_paid = total_fees_paid + p_fees,
        total_slippage_cost = total_slippage_cost + p_slippage,
        total_trades = total_trades + 1,
        winning_trades = winning_trades + CASE WHEN p_is_winner THEN 1 ELSE 0 END,
        losing_trades = losing_trades + CASE WHEN NOT p_is_winner THEN 1 ELSE 0 END,
        realized_pnl = realized_pnl + p_pnl,
        highest_equity = GREATEST(highest_equity, balance_usdt + p_pnl - p_fees),
        lowest_equity = LEAST(lowest_equity, balance_usdt + p_pnl - p_fees),
        updated_at = NOW(),
        last_trade_at = NOW()
    WHERE account_id = p_account_id;
END;
$$ LANGUAGE plpgsql;

-- Function to record equity snapshot
CREATE OR REPLACE FUNCTION record_equity_snapshot(
    p_account_id VARCHAR(50),
    p_equity DECIMAL(20, 8),
    p_cash DECIMAL(20, 8),
    p_positions_value DECIMAL(20, 8),
    p_unrealized_pnl DECIMAL(20, 8),
    p_btc_price DECIMAL(20, 8)
) RETURNS VOID AS $$
BEGIN
    INSERT INTO account_equity_history (
        account_id, equity, cash, positions_value, unrealized_pnl, btc_price
    ) VALUES (
        p_account_id, p_equity, p_cash, p_positions_value, p_unrealized_pnl, p_btc_price
    );
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════
-- VIEW: Current Account Summary
-- ═══════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_account_summary AS
SELECT 
    a.account_id,
    a.account_type,
    a.balance_usdt,
    a.initial_balance,
    a.balance_usdt - a.initial_balance AS total_pnl,
    ((a.balance_usdt - a.initial_balance) / a.initial_balance * 100) AS total_return_pct,
    a.total_fees_paid,
    a.total_slippage_cost,
    a.total_fees_paid + a.total_slippage_cost AS total_costs,
    a.total_trades,
    a.winning_trades,
    a.losing_trades,
    CASE WHEN a.total_trades > 0 
         THEN (a.winning_trades::DECIMAL / a.total_trades * 100) 
         ELSE 0 END AS win_rate,
    a.max_drawdown * 100 AS max_drawdown_pct,
    a.created_at,
    a.last_trade_at
FROM account_state a;
