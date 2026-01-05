-- ═══════════════════════════════════════════════════════════════════════════
-- SELF-LEARNING SYSTEM: Pre-Mortem, Reflections, Wisdom
-- ═══════════════════════════════════════════════════════════════════════════

-- Trade Wisdom: Accumulated learnings from past trades
CREATE TABLE IF NOT EXISTS trade_wisdom (
    id VARCHAR(36) PRIMARY KEY,
    type VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    occurrences INT DEFAULT 1,
    first_occurred TIMESTAMP NOT NULL,
    last_occurred TIMESTAMP NOT NULL,
    symbol_pattern VARCHAR(20),
    direction_pattern VARCHAR(10)
);

CREATE INDEX IF NOT EXISTS idx_wisdom_type_occ ON trade_wisdom(type, occurrences DESC);
CREATE INDEX IF NOT EXISTS idx_wisdom_last_occurred ON trade_wisdom(last_occurred DESC);

-- Reflection Entries: Post-trade self-reflections for timeline
CREATE TABLE IF NOT EXISTS reflection_entries (
    id VARCHAR(36) PRIMARY KEY,
    position_id VARCHAR(32),
    symbol VARCHAR(20),
    direction VARCHAR(10),
    entry_price DECIMAL(20,8),
    exit_price DECIMAL(20,8),
    pnl_percent DECIMAL(10,4),
    hold_hours INT,
    pre_mortem TEXT,
    what_happened TEXT,
    pre_mortem_was_correct BOOLEAN,
    lesson_type VARCHAR(20),
    lesson_learned TEXT,
    reflected_at TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reflection_time ON reflection_entries(reflected_at DESC);
CREATE INDEX IF NOT EXISTS idx_reflection_position ON reflection_entries(position_id);

-- Extend paper_positions table with Pre-Mortem and expectations
ALTER TABLE paper_positions 
ADD COLUMN IF NOT EXISTS pre_mortem TEXT,
ADD COLUMN IF NOT EXISTS bull_case TEXT,
ADD COLUMN IF NOT EXISTS bear_case TEXT,
ADD COLUMN IF NOT EXISTS expected_hold_hours_min INT,
ADD COLUMN IF NOT EXISTS expected_hold_hours_max INT,
ADD COLUMN IF NOT EXISTS target_pnl_percent DECIMAL(10,4),
ADD COLUMN IF NOT EXISTS max_acceptable_loss_percent DECIMAL(10,4);

