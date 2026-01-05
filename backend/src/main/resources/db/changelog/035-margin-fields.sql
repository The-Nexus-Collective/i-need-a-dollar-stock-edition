--liquibase formatted sql

--changeset system:035-margin-fields
--comment: Add margin-related fields to positions and trades for stock trading

-- Add margin fields to paper_positions
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS leverage INTEGER DEFAULT 1;
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS liquidation_price DECIMAL(20,8);
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS isolated_margin DECIMAL(20,8);
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS maint_margin_rate DECIMAL(8,4);
ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS margin_mode VARCHAR(20) DEFAULT 'CASH';

-- Add leverage to paper_trades
ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS leverage INTEGER DEFAULT 1;

-- Add total_slippage_cost to trader_state
ALTER TABLE trader_state ADD COLUMN IF NOT EXISTS total_slippage_cost DECIMAL(18,4) DEFAULT 0;

--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS leverage;
--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS liquidation_price;
--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS isolated_margin;
--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS maint_margin_rate;
--rollback ALTER TABLE paper_positions DROP COLUMN IF EXISTS margin_mode;
--rollback ALTER TABLE paper_trades DROP COLUMN IF EXISTS leverage;
--rollback ALTER TABLE trader_state DROP COLUMN IF EXISTS total_slippage_cost;

