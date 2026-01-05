--liquibase formatted sql

--changeset trading:015-margin-system
--comment: Add margin tracking columns for Binance-style leverage management

-- Add margin tracking columns to paper_positions
ALTER TABLE paper_positions
ADD COLUMN IF NOT EXISTS margin_mode VARCHAR(10) DEFAULT 'ISOLATED',
ADD COLUMN IF NOT EXISTS isolated_margin DECIMAL(20,8),
ADD COLUMN IF NOT EXISTS maint_margin_rate DECIMAL(10,6) DEFAULT 0.004,
ADD COLUMN IF NOT EXISTS liquidation_price DECIMAL(20,8);

-- Migrate existing open positions with calculated values
UPDATE paper_positions 
SET isolated_margin = size_usdt / NULLIF(leverage, 0),
    maint_margin_rate = 0.004,
    liquidation_price = CASE 
        WHEN direction = 'LONG' THEN entry_price * (1 - (1.0 / NULLIF(leverage, 0)) + 0.004)
        WHEN direction = 'SHORT' THEN entry_price * (1 + (1.0 / NULLIF(leverage, 0)) - 0.004)
        ELSE entry_price
    END
WHERE status = 'OPEN' AND isolated_margin IS NULL;

-- Create index for margin queries
CREATE INDEX IF NOT EXISTS idx_positions_margin_mode ON paper_positions(margin_mode) WHERE status = 'OPEN';

--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS margin_mode, DROP COLUMN IF EXISTS isolated_margin, DROP COLUMN IF EXISTS maint_margin_rate, DROP COLUMN IF EXISTS liquidation_price;

