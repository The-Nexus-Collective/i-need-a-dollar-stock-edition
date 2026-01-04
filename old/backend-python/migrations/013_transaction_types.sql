-- Migration 013: Add transaction types for position scaling
-- Supports OPEN, CLOSE, EXTEND, and REDUCE transaction types

-- Add transaction_type column to paper_trades
ALTER TABLE paper_trades 
ADD COLUMN IF NOT EXISTS transaction_type VARCHAR(10) DEFAULT 'CLOSE';

-- Add position size tracking columns for scaling context
ALTER TABLE paper_trades 
ADD COLUMN IF NOT EXISTS position_size_before NUMERIC(20,4) DEFAULT 0,
ADD COLUMN IF NOT EXISTS position_size_after NUMERIC(20,4) DEFAULT 0,
ADD COLUMN IF NOT EXISTS avg_entry_before NUMERIC(20,8) DEFAULT 0,
ADD COLUMN IF NOT EXISTS avg_entry_after NUMERIC(20,8) DEFAULT 0;

-- Add constraint for valid transaction types
DO $$
BEGIN
    ALTER TABLE paper_trades DROP CONSTRAINT IF EXISTS paper_trades_transaction_type_check;
    ALTER TABLE paper_trades ADD CONSTRAINT paper_trades_transaction_type_check 
        CHECK (transaction_type IN ('OPEN', 'CLOSE', 'EXTEND', 'REDUCE'));
EXCEPTION WHEN OTHERS THEN
    NULL; -- Ignore if constraint doesn't exist
END
$$;

-- Add index for transaction type filtering
CREATE INDEX IF NOT EXISTS idx_paper_trades_transaction_type ON paper_trades(transaction_type);

-- Update existing records to have appropriate transaction types
-- Existing closed trades should be marked as CLOSE
UPDATE paper_trades SET transaction_type = 'CLOSE' WHERE transaction_type IS NULL;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRANSACTIONS TABLE (NEW)
-- Standalone transactions table for all position operations
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS position_transactions (
    id VARCHAR(32) PRIMARY KEY,
    position_id VARCHAR(32) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('LONG', 'SHORT')),
    transaction_type VARCHAR(10) NOT NULL CHECK (transaction_type IN ('OPEN', 'CLOSE', 'EXTEND', 'REDUCE')),
    
    -- Transaction details
    price NUMERIC(20,8) NOT NULL,
    quantity NUMERIC(20,8) NOT NULL,
    size_usdt NUMERIC(20,4) NOT NULL,
    leverage INTEGER DEFAULT 1,
    
    -- Position state
    position_size_before NUMERIC(20,4) DEFAULT 0,
    position_size_after NUMERIC(20,4) DEFAULT 0,
    avg_entry_before NUMERIC(20,8) DEFAULT 0,
    avg_entry_after NUMERIC(20,8) DEFAULT 0,
    
    -- PnL (for CLOSE and REDUCE)
    realized_pnl NUMERIC(20,4) DEFAULT 0,
    realized_pnl_pct NUMERIC(10,4) DEFAULT 0,
    
    -- Costs
    fee NUMERIC(20,4) DEFAULT 0,
    spread NUMERIC(20,4) DEFAULT 0,
    slippage NUMERIC(20,4) DEFAULT 0,
    
    -- Metadata
    reason TEXT,
    conviction INTEGER CHECK (conviction >= 0 AND conviction <= 100),
    
    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_position_transactions_symbol ON position_transactions(symbol);
CREATE INDEX IF NOT EXISTS idx_position_transactions_type ON position_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_position_transactions_created ON position_transactions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_position_transactions_position_id ON position_transactions(position_id);

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEW: All transactions with summary
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_all_transactions AS
SELECT 
    id,
    position_id,
    symbol,
    direction,
    transaction_type,
    price,
    quantity,
    size_usdt,
    leverage,
    position_size_before,
    position_size_after,
    realized_pnl,
    realized_pnl_pct,
    fee + spread + slippage as total_cost,
    reason,
    conviction,
    created_at
FROM position_transactions
ORDER BY created_at DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEW: Transaction summary by type
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW v_transaction_summary AS
SELECT 
    transaction_type,
    COUNT(*) as count,
    SUM(size_usdt) as total_volume,
    SUM(realized_pnl) as total_pnl,
    AVG(realized_pnl_pct) as avg_pnl_pct,
    SUM(fee + spread + slippage) as total_costs
FROM position_transactions
GROUP BY transaction_type;

-- Comments for documentation
COMMENT ON COLUMN paper_trades.transaction_type IS 'Type of transaction: OPEN, CLOSE, EXTEND, or REDUCE';
COMMENT ON COLUMN paper_trades.position_size_before IS 'Position size in USDT before this transaction';
COMMENT ON COLUMN paper_trades.position_size_after IS 'Position size in USDT after this transaction';
COMMENT ON COLUMN paper_trades.avg_entry_before IS 'Average entry price before this transaction';
COMMENT ON COLUMN paper_trades.avg_entry_after IS 'Average entry price after this transaction (for EXTEND)';

COMMENT ON TABLE position_transactions IS 'All position transactions including OPEN, CLOSE, EXTEND, and REDUCE operations';

