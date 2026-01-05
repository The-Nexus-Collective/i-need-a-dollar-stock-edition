-- ═══════════════════════════════════════════════════════════════════════════════
-- FIX: Increase exit_reason column length from 20 to 100 characters
-- The exit_reason field stores AI-generated reasons which can exceed 20 chars
-- ═══════════════════════════════════════════════════════════════════════════════

ALTER TABLE paper_trades ALTER COLUMN exit_reason TYPE VARCHAR(100);

