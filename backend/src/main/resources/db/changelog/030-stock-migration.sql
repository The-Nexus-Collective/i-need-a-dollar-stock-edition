--liquibase formatted sql

-- ═══════════════════════════════════════════════════════════════════════════════
-- POSITIONS TABLE: Add stock-specific fields
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-add-exchange-column splitStatements:false
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'paper_positions' AND column_name = 'exchange') THEN
        ALTER TABLE paper_positions ADD COLUMN exchange VARCHAR(20) DEFAULT 'UNKNOWN';
    END IF;
END $$;

--changeset trading-platform:030-add-sector-column splitStatements:false
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'paper_positions' AND column_name = 'sector') THEN
        ALTER TABLE paper_positions ADD COLUMN sector VARCHAR(20) DEFAULT 'OTHER';
    END IF;
END $$;

--changeset trading-platform:030-rename-size-usdt-positions splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'size_usdt') THEN
        ALTER TABLE paper_positions RENAME COLUMN size_usdt TO size_usd;
    END IF;
END $$;

--changeset trading-platform:030-drop-crypto-columns-positions splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'leverage') THEN
        ALTER TABLE paper_positions DROP COLUMN IF EXISTS leverage;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'margin_mode') THEN
        ALTER TABLE paper_positions DROP COLUMN IF EXISTS margin_mode;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'isolated_margin') THEN
        ALTER TABLE paper_positions DROP COLUMN IF EXISTS isolated_margin;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'maint_margin_rate') THEN
        ALTER TABLE paper_positions DROP COLUMN IF EXISTS maint_margin_rate;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_positions' AND column_name = 'liquidation_price') THEN
        ALTER TABLE paper_positions DROP COLUMN IF EXISTS liquidation_price;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADES TABLE: Update for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-add-sector-trades splitStatements:false
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'paper_trades' AND column_name = 'sector') THEN
        ALTER TABLE paper_trades ADD COLUMN sector VARCHAR(20) DEFAULT 'OTHER';
    END IF;
END $$;

--changeset trading-platform:030-rename-usdt-columns-trades splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_trades' AND column_name = 'size_usdt') THEN
        ALTER TABLE paper_trades RENAME COLUMN size_usdt TO size_usd;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_trades' AND column_name = 'pnl_usdt') THEN
        ALTER TABLE paper_trades RENAME COLUMN pnl_usdt TO pnl_usd;
    END IF;
END $$;

--changeset trading-platform:030-drop-leverage-trades splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'paper_trades' AND column_name = 'leverage') THEN
        ALTER TABLE paper_trades DROP COLUMN IF EXISTS leverage;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SIGNALS TABLE: Update for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-rename-coin-signals splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'signals' AND column_name = 'coin') THEN
        ALTER TABLE signals RENAME COLUMN coin TO symbol;
    END IF;
END $$;

--changeset trading-platform:030-drop-leverage-signals splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'signals' AND column_name = 'leverage_calculated') THEN
        ALTER TABLE signals DROP COLUMN IF EXISTS leverage_calculated;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- LOGBOOK: Update field names for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-rename-coins-logbook splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'logbook_entry' AND column_name = 'coins_analyzed') THEN
        ALTER TABLE logbook_entry RENAME COLUMN coins_analyzed TO stocks_analyzed;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'logbook_entry' AND column_name = 'coins_skipped') THEN
        ALTER TABLE logbook_entry RENAME COLUMN coins_skipped TO stocks_skipped;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTIONS TABLE: Update for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-rename-coin-predictions splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'predictions' AND column_name = 'coin') THEN
        ALTER TABLE predictions RENAME COLUMN coin TO symbol;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'predictions' AND column_name = 'size_usdt') THEN
        ALTER TABLE predictions RENAME COLUMN size_usdt TO size_usd;
    END IF;
END $$;

--changeset trading-platform:030-drop-leverage-predictions splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'predictions' AND column_name = 'leverage') THEN
        ALTER TABLE predictions DROP COLUMN IF EXISTS leverage;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADING DECISIONS: Update for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-rename-coin-decisions splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'trading_decisions' AND column_name = 'coin') THEN
        ALTER TABLE trading_decisions RENAME COLUMN coin TO symbol;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- PREDICTION CYCLES: Update for stocks
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-rename-coins-cycles splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'prediction_cycles' AND column_name = 'coins_traded') THEN
        ALTER TABLE prediction_cycles RENAME COLUMN coins_traded TO stocks_traded;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADER STATE: Remove crypto-specific fields
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-drop-slippage-trader-state splitStatements:false
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'trader_state' AND column_name = 'total_slippage_cost') THEN
        ALTER TABLE trader_state DROP COLUMN IF EXISTS total_slippage_cost;
    END IF;
END $$;

-- ═══════════════════════════════════════════════════════════════════════════════
-- ACCOUNTING LEDGER: Clean up crypto-specific entries
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-cleanup-margin-ledger
DELETE FROM accounting_ledger WHERE account = 'MARGIN_USED';

--changeset trading-platform:030-cleanup-crypto-transactions
UPDATE accounting_ledger SET transaction_type = 'FEE' 
WHERE transaction_type IN ('SPREAD', 'SLIPPAGE', 'FUNDING', 'LEVERAGE_CHANGE', 'MARGIN_CALL');

-- ═══════════════════════════════════════════════════════════════════════════════
-- ADD INDEXES FOR STOCK TRADING
-- ═══════════════════════════════════════════════════════════════════════════════

--changeset trading-platform:030-add-sector-indexes
CREATE INDEX IF NOT EXISTS idx_positions_sector ON paper_positions(sector);
CREATE INDEX IF NOT EXISTS idx_trades_sector ON paper_trades(sector);

--changeset trading-platform:030-add-table-comments
COMMENT ON TABLE paper_positions IS 'Stock trading positions (paper trading mode)';
COMMENT ON TABLE paper_trades IS 'Completed stock trades (paper trading mode)';
