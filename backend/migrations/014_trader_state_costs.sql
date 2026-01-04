-- Migration 014: Add trading costs columns to trader_state
-- Tracks fees, spread, and slippage for better cost analysis

-- Add cost tracking columns to trader_state
ALTER TABLE trader_state ADD COLUMN IF NOT EXISTS total_fees DECIMAL(18,4) DEFAULT 0;
ALTER TABLE trader_state ADD COLUMN IF NOT EXISTS total_spread DECIMAL(18,4) DEFAULT 0;
ALTER TABLE trader_state ADD COLUMN IF NOT EXISTS total_slippage DECIMAL(18,4) DEFAULT 0;

-- Add comment for documentation
COMMENT ON COLUMN trader_state.total_fees IS 'Total trading fees paid';
COMMENT ON COLUMN trader_state.total_spread IS 'Total spread costs incurred';
COMMENT ON COLUMN trader_state.total_slippage IS 'Total slippage costs incurred';

