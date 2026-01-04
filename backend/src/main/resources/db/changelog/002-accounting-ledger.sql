--liquibase formatted sql

--changeset accounting:001-create-accounting-ledger
-- Double-entry accounting ledger for auditable financial tracking

CREATE TABLE IF NOT EXISTS accounting_ledger (
    id BIGSERIAL PRIMARY KEY,
    transaction_id UUID NOT NULL,                    -- Groups related entries for one transaction
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    transaction_type VARCHAR(30) NOT NULL,           -- OPEN, CLOSE, FEE, RESET, ADJUSTMENT
    position_id VARCHAR(50),                         -- Reference to position (nullable)
    account VARCHAR(30) NOT NULL,                    -- CASH, POSITIONS, REALIZED_PNL, TRADING_COSTS
    debit DECIMAL(20, 8) DEFAULT 0,                  -- Increases for assets/expenses
    credit DECIMAL(20, 8) DEFAULT 0,                 -- Increases for equity/liabilities
    running_balance DECIMAL(20, 8),                  -- Running balance for this account after entry
    description TEXT,
    metadata TEXT,                                   -- Additional context (JSON as text)
    
    CONSTRAINT valid_entry CHECK (
        (debit > 0 AND credit = 0) OR (credit > 0 AND debit = 0) OR (debit = 0 AND credit = 0)
    )
);

-- Indexes for efficient querying
CREATE INDEX idx_ledger_transaction_id ON accounting_ledger(transaction_id);
CREATE INDEX idx_ledger_timestamp ON accounting_ledger(timestamp);
CREATE INDEX idx_ledger_account ON accounting_ledger(account);
CREATE INDEX idx_ledger_position_id ON accounting_ledger(position_id);
CREATE INDEX idx_ledger_type ON accounting_ledger(transaction_type);

-- View for account balances (debits - credits for asset accounts, credits - debits for equity)
CREATE OR REPLACE VIEW account_balances AS
SELECT 
    account,
    SUM(debit) as total_debits,
    SUM(credit) as total_credits,
    CASE 
        WHEN account IN ('CASH', 'POSITIONS', 'TRADING_COSTS') THEN SUM(debit) - SUM(credit)
        ELSE SUM(credit) - SUM(debit)
    END as balance
FROM accounting_ledger
GROUP BY account;

-- View for transaction summary
CREATE OR REPLACE VIEW transaction_summary AS
SELECT 
    transaction_id,
    MIN(timestamp) as timestamp,
    MAX(transaction_type) as transaction_type,
    MAX(position_id) as position_id,
    SUM(debit) as total_debits,
    SUM(credit) as total_credits,
    ABS(SUM(debit) - SUM(credit)) as imbalance
FROM accounting_ledger
GROUP BY transaction_id;

COMMENT ON TABLE accounting_ledger IS 'Double-entry accounting ledger for all financial transactions';
COMMENT ON COLUMN accounting_ledger.transaction_id IS 'Groups related debit/credit entries for one logical transaction';
COMMENT ON COLUMN accounting_ledger.account IS 'Account type: CASH, POSITIONS, REALIZED_PNL, TRADING_COSTS, STARTING_CAPITAL';

