--liquibase formatted sql

--changeset logbook:001-create-logbook-entry
-- Trading logbook entries - stores complete cycle analysis data

CREATE TABLE IF NOT EXISTS logbook_entry (
    id VARCHAR(50) PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cycle_number INT NOT NULL,
    
    -- Grok analysis content
    analysis_text TEXT,
    market_summary TEXT,
    
    -- Actions taken (JSON arrays stored as text)
    positions_closed TEXT,    -- JSON array of closed position details
    positions_opened TEXT,    -- JSON array of opened position details
    positions_kept TEXT,      -- JSON array of kept symbols
    positions_extended TEXT,  -- JSON array of extended positions
    positions_reduced TEXT,   -- JSON array of reduced positions
    
    -- Metrics
    coins_analyzed INT DEFAULT 0,
    coins_skipped INT DEFAULT 0,
    tokens_used INT DEFAULT 0,
    
    -- Portfolio state at this point
    total_equity DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    open_positions INT DEFAULT 0,
    deployment_percent DECIMAL(10, 4),
    
    -- Debug: raw Grok I/O
    raw_prompt TEXT,
    raw_response TEXT
);

-- Indexes for efficient querying
CREATE INDEX idx_logbook_timestamp ON logbook_entry(timestamp DESC);
CREATE INDEX idx_logbook_cycle ON logbook_entry(cycle_number DESC);

COMMENT ON TABLE logbook_entry IS 'Trading cycle logbook entries with Grok analysis and portfolio state';
COMMENT ON COLUMN logbook_entry.analysis_text IS 'Full human-readable analysis from Grok';
COMMENT ON COLUMN logbook_entry.market_summary IS 'Brief market summary from Grok';
COMMENT ON COLUMN logbook_entry.raw_prompt IS 'Raw prompt sent to Grok API (for debugging)';
COMMENT ON COLUMN logbook_entry.raw_response IS 'Raw response from Grok API (for debugging)';

