-- Migration: Add trading costs columns to paper_trades
-- This tracks fees, spread, and slippage for each trade

-- Add cost columns to paper_trades
ALTER TABLE paper_trades 
ADD COLUMN IF NOT EXISTS fee_usdt NUMERIC(20,4) DEFAULT 0,
ADD COLUMN IF NOT EXISTS spread_cost_usdt NUMERIC(20,4) DEFAULT 0,
ADD COLUMN IF NOT EXISTS slippage_cost_usdt NUMERIC(20,4) DEFAULT 0;

-- Add index for cost analysis
CREATE INDEX IF NOT EXISTS idx_paper_trades_costs ON paper_trades(fee_usdt, spread_cost_usdt, slippage_cost_usdt);

-- Comment for documentation
COMMENT ON COLUMN paper_trades.fee_usdt IS 'Total taker fees paid for entry and exit (typically 0.04% each way)';
COMMENT ON COLUMN paper_trades.spread_cost_usdt IS 'Cost from bid-ask spread (typically 0.02%)';
COMMENT ON COLUMN paper_trades.slippage_cost_usdt IS 'Execution slippage cost (varies by market conditions)';

