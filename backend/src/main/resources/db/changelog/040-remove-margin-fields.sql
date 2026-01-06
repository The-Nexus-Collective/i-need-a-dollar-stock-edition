--liquibase formatted sql

--changeset system:040-remove-margin-fields
--comment: Remove leverage/margin fields (cash-only stock trading)

-- Remove margin fields from paper_positions
ALTER TABLE paper_positions DROP COLUMN IF EXISTS leverage;
ALTER TABLE paper_positions DROP COLUMN IF EXISTS liquidation_price;
ALTER TABLE paper_positions DROP COLUMN IF EXISTS isolated_margin;
ALTER TABLE paper_positions DROP COLUMN IF EXISTS maint_margin_rate;
ALTER TABLE paper_positions DROP COLUMN IF EXISTS margin_mode;

-- Remove leverage from paper_trades
ALTER TABLE paper_trades DROP COLUMN IF EXISTS leverage;

-- Drop margin-related index if exists
DROP INDEX IF EXISTS idx_positions_margin_mode;

--rollback ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS leverage INTEGER DEFAULT 1;
--rollback ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS liquidation_price DECIMAL(20,8);
--rollback ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS isolated_margin DECIMAL(20,8);
--rollback ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS maint_margin_rate DECIMAL(8,4);
--rollback ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS margin_mode VARCHAR(20) DEFAULT 'CASH';
--rollback ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS leverage INTEGER DEFAULT 1;

