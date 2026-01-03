-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 008: Emergent AI Swarm
-- 
-- Extends the database for the self-evolving agent swarm:
-- 1. Agent state tracking
-- 2. Belief storage
-- 3. Hypothesis tracking
-- 4. Strategy gene evolution
-- 5. Signal history
-- ═══════════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════════════════════
-- AGENT STATE
-- Track agent beliefs and state over time
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_beliefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Agent identification
    agent_id VARCHAR(50) NOT NULL,
    
    -- Belief content
    statement TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    
    -- Probability and confidence
    probability DECIMAL(5,4) NOT NULL DEFAULT 0.5,
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0.5,
    
    -- Evidence tracking
    supporting_count INTEGER DEFAULT 0,
    contradicting_count INTEGER DEFAULT 0,
    
    -- Decay
    last_reinforced TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    decay_rate DECIMAL(5,4) DEFAULT 0.01,
    
    -- Unique constraint: one belief per statement per agent
    UNIQUE(agent_id, statement)
);

CREATE INDEX IF NOT EXISTS idx_beliefs_agent ON agent_beliefs(agent_id);
CREATE INDEX IF NOT EXISTS idx_beliefs_category ON agent_beliefs(category);
CREATE INDEX IF NOT EXISTS idx_beliefs_probability ON agent_beliefs(probability);

-- ═══════════════════════════════════════════════════════════════════════════════
-- HYPOTHESES
-- Track testable hypotheses and their outcomes
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS swarm_hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Content
    statement TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'market',
    
    -- Confidence
    confidence DECIMAL(5,4) NOT NULL DEFAULT 0.5,
    initial_confidence DECIMAL(5,4) NOT NULL DEFAULT 0.5,
    
    -- Testing
    tests_total INTEGER DEFAULT 0,
    tests_passed INTEGER DEFAULT 0,
    
    -- Source
    source_agent VARCHAR(50),
    parent_hypothesis_id UUID REFERENCES swarm_hypotheses(id),
    generation INTEGER DEFAULT 0,
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    discarded_at TIMESTAMPTZ,
    discard_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_active ON swarm_hypotheses(is_active);
CREATE INDEX IF NOT EXISTS idx_hypotheses_category ON swarm_hypotheses(category);
CREATE INDEX IF NOT EXISTS idx_hypotheses_agent ON swarm_hypotheses(source_agent);

-- ═══════════════════════════════════════════════════════════════════════════════
-- HYPOTHESIS PREDICTIONS
-- Track predictions made to test hypotheses
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS hypothesis_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Link to hypothesis
    hypothesis_id UUID NOT NULL REFERENCES swarm_hypotheses(id),
    
    -- Prediction content
    statement TEXT NOT NULL,
    target VARCHAR(50) NOT NULL,
    direction VARCHAR(20) NOT NULL,
    magnitude DECIMAL(10,4),
    timeframe_hours INTEGER NOT NULL DEFAULT 24,
    
    -- Resolution
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    outcome_correct BOOLEAN,
    actual_result TEXT
);

CREATE INDEX IF NOT EXISTS idx_predictions_hypothesis ON hypothesis_predictions(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_predictions_unresolved ON hypothesis_predictions(resolved) WHERE resolved = FALSE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- STRATEGY GENES
-- Evolutionary strategy tracking
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS strategy_genes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Identity
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Parameters (the DNA)
    parameters JSONB NOT NULL DEFAULT '{}',
    
    -- Performance
    fitness DECIMAL(5,4) DEFAULT 0.0,
    trades_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    total_pnl DECIMAL(20,2) DEFAULT 0,
    
    -- Lineage
    generation INTEGER DEFAULT 0,
    parent_ids UUID[],
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_genes_fitness ON strategy_genes(fitness DESC);
CREATE INDEX IF NOT EXISTS idx_genes_active ON strategy_genes(is_active);
CREATE INDEX IF NOT EXISTS idx_genes_generation ON strategy_genes(generation);

-- ═══════════════════════════════════════════════════════════════════════════════
-- SIGNAL HISTORY
-- Archive of agent signals for analysis
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS signal_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Source
    sender_id VARCHAR(50) NOT NULL,
    sender_name VARCHAR(100) NOT NULL,
    
    -- Content
    signal_type VARCHAR(50) NOT NULL,
    topic VARCHAR(200),
    content TEXT,
    
    -- Metrics
    confidence DECIMAL(5,4),
    urgency DECIMAL(5,4),
    importance DECIMAL(5,4),
    
    -- Metadata
    mentions TEXT[],
    tags TEXT[],
    data JSONB
);

CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signal_history(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_sender ON signal_history(sender_id);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signal_history(signal_type);

-- Partial index for recent signals
CREATE INDEX IF NOT EXISTS idx_signals_recent ON signal_history(timestamp DESC) 
    WHERE timestamp > NOW() - INTERVAL '24 hours';

-- ═══════════════════════════════════════════════════════════════════════════════
-- SWARM METRICS
-- Aggregate metrics for the swarm over time
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS swarm_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Agent counts
    active_agents INTEGER DEFAULT 0,
    
    -- Signal metrics
    signals_1h INTEGER DEFAULT 0,
    signals_24h INTEGER DEFAULT 0,
    
    -- Belief metrics
    total_beliefs INTEGER DEFAULT 0,
    strong_beliefs INTEGER DEFAULT 0,  -- probability > 0.7 or < 0.3
    
    -- Hypothesis metrics
    active_hypotheses INTEGER DEFAULT 0,
    hypothesis_success_rate DECIMAL(5,4),
    
    -- Strategy metrics
    active_strategies INTEGER DEFAULT 0,
    best_strategy_fitness DECIMAL(5,4),
    
    -- Memory metrics
    memory_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_swarm_metrics_time ON swarm_metrics(recorded_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEWS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Active hypotheses with success rate
CREATE OR REPLACE VIEW v_active_hypotheses AS
SELECT 
    id,
    statement,
    category,
    confidence,
    tests_total,
    tests_passed,
    CASE WHEN tests_total > 0 
        THEN tests_passed::DECIMAL / tests_total 
        ELSE 0.5 
    END as success_rate,
    source_agent,
    generation,
    created_at
FROM swarm_hypotheses
WHERE is_active = TRUE
ORDER BY confidence DESC;

-- Top strategy genes
CREATE OR REPLACE VIEW v_top_strategies AS
SELECT 
    id,
    name,
    parameters,
    fitness,
    trades_count,
    CASE WHEN trades_count > 0 
        THEN wins::DECIMAL / trades_count * 100 
        ELSE 0 
    END as win_rate,
    total_pnl,
    generation
FROM strategy_genes
WHERE is_active = TRUE
ORDER BY fitness DESC
LIMIT 20;

-- Recent signals summary
CREATE OR REPLACE VIEW v_signal_summary AS
SELECT 
    sender_name,
    signal_type,
    COUNT(*) as signal_count,
    AVG(confidence) as avg_confidence,
    AVG(importance) as avg_importance,
    MAX(timestamp) as last_signal
FROM signal_history
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY sender_name, signal_type
ORDER BY signal_count DESC;

COMMIT;

