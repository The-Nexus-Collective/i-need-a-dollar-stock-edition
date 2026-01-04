-- ═══════════════════════════════════════════════════════════════════════════════
-- Migration 007: Agentic Trading System
-- 
-- Adds:
-- 1. pgvector extension for semantic memory
-- 2. agent_logs table for complete audit trail
-- 3. memories table for short/medium/long-term recall
-- 4. tradable_universe table for dynamic coin discovery
-- 5. strategy_performance table for meta-learning
-- ═══════════════════════════════════════════════════════════════════════════════

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ═══════════════════════════════════════════════════════════════════════════════
-- AGENT LOGBOOK
-- Central audit trail for all agent activities
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Cycle grouping (all logs in a 15-min cycle share this)
    cycle_id UUID NOT NULL,
    
    -- Agent identification
    agent_name VARCHAR(50) NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    
    -- Reasoning chain (the core of transparency)
    input_context JSONB,
    reasoning TEXT,
    decision TEXT,
    output_data JSONB,
    
    -- Metrics
    confidence DECIMAL(5,2),
    duration_ms INTEGER,
    tokens_used INTEGER,
    
    -- Traceability
    parent_log_id UUID REFERENCES agent_logs(id),
    triggered_by VARCHAR(100),
    
    -- Embedding for semantic search (OpenAI ada-002 dimension)
    reasoning_embedding vector(1536)
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_agent_logs_cycle ON agent_logs(cycle_id);
CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent_name, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_action ON agent_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_agent_logs_timestamp ON agent_logs(timestamp DESC);

-- Partial index for recent logs (last 7 days)
CREATE INDEX IF NOT EXISTS idx_agent_logs_recent ON agent_logs(timestamp DESC) 
    WHERE timestamp > NOW() - INTERVAL '7 days';

-- ═══════════════════════════════════════════════════════════════════════════════
-- MEMORY SYSTEM
-- Hierarchical memory for learning and recall
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Memory classification
    memory_type VARCHAR(20) NOT NULL CHECK (memory_type IN ('short', 'medium', 'long')),
    category VARCHAR(50) NOT NULL,  -- 'trade_outcome', 'market_regime', 'strategy_insight', etc.
    
    -- Content
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    
    -- Semantic embedding for similarity search
    embedding vector(1536),
    
    -- Metadata
    metadata JSONB,
    
    -- Lifecycle
    expires_at TIMESTAMPTZ,  -- NULL for long-term memories
    recall_count INTEGER DEFAULT 0,
    last_recalled_at TIMESTAMPTZ,
    importance_score DECIMAL(5,2) DEFAULT 50.0,
    
    -- Source tracing
    source_agent VARCHAR(50),
    source_cycle_id UUID,
    related_coins TEXT[]
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category);
CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance_score DESC);

-- Vector similarity index (IVFFlat for fast approximate search)
CREATE INDEX IF NOT EXISTS idx_memories_embedding ON memories 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADABLE UNIVERSE
-- Dynamic coin discovery and validation tracking
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS tradable_universe (
    coin VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    
    -- Discovery
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    discovery_source VARCHAR(50) NOT NULL,  -- 'coingecko', 'x_hype', 'manual'
    discovery_reason TEXT,
    
    -- Validation
    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    validated_at TIMESTAMPTZ,
    validation_notes TEXT,
    
    -- Market data cache
    volume_24h DECIMAL(20,2),
    market_cap DECIMAL(20,2),
    price_usd DECIMAL(20,8),
    price_change_24h DECIMAL(10,4),
    
    -- Exchange info
    binance_symbol VARCHAR(20),
    is_binance_perp BOOLEAN DEFAULT FALSE,
    
    -- Lifecycle
    coin_age_days INTEGER,
    first_seen_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    deactivated_at TIMESTAMPTZ,
    deactivation_reason TEXT,
    
    -- Scoring
    hype_score DECIMAL(5,2) DEFAULT 0,
    sentiment_score DECIMAL(5,2) DEFAULT 0,
    narrative_strength DECIMAL(5,2) DEFAULT 0,
    
    -- Last updates
    last_price_update TIMESTAMPTZ,
    last_sentiment_update TIMESTAMPTZ,
    
    -- Constraints
    CHECK (validation_status IN ('pending', 'approved', 'rejected', 'expired'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_universe_status ON tradable_universe(validation_status, is_active);
CREATE INDEX IF NOT EXISTS idx_universe_volume ON tradable_universe(volume_24h DESC) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_universe_discovery ON tradable_universe(discovery_source, discovered_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- STRATEGY PERFORMANCE
-- Track performance of each sub-strategy for meta-learning
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Strategy identification
    strategy_name VARCHAR(50) NOT NULL,
    
    -- Performance metrics (rolling windows)
    trades_1h INTEGER DEFAULT 0,
    trades_24h INTEGER DEFAULT 0,
    trades_7d INTEGER DEFAULT 0,
    
    win_rate_1h DECIMAL(5,2),
    win_rate_24h DECIMAL(5,2),
    win_rate_7d DECIMAL(5,2),
    
    pnl_1h DECIMAL(20,2) DEFAULT 0,
    pnl_24h DECIMAL(20,2) DEFAULT 0,
    pnl_7d DECIMAL(20,2) DEFAULT 0,
    
    avg_trade_duration_mins INTEGER,
    
    -- Current weight assigned by meta-learner
    current_weight DECIMAL(5,4) DEFAULT 0.1667,  -- 1/6 = equal weight
    
    -- Regime affinity scores (how well does this strategy perform in each regime)
    affinity_low_vol DECIMAL(5,2) DEFAULT 50,
    affinity_normal_vol DECIMAL(5,2) DEFAULT 50,
    affinity_high_vol DECIMAL(5,2) DEFAULT 50,
    affinity_crisis DECIMAL(5,2) DEFAULT 50,
    
    -- Meta
    last_trade_at TIMESTAMPTZ,
    consecutive_wins INTEGER DEFAULT 0,
    consecutive_losses INTEGER DEFAULT 0
);

-- Index for latest performance per strategy
CREATE INDEX IF NOT EXISTS idx_strategy_perf_latest ON strategy_performance(strategy_name, recorded_at DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- TRADE REFLECTIONS
-- Post-trade analysis by Learner Agent
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trade_reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Trade reference
    trade_id UUID NOT NULL,
    position_id UUID,
    coin VARCHAR(20) NOT NULL,
    
    -- Trade outcome
    side VARCHAR(10) NOT NULL,
    entry_price DECIMAL(20,8),
    exit_price DECIMAL(20,8),
    pnl DECIMAL(20,2),
    pnl_percent DECIMAL(10,4),
    hold_duration_mins INTEGER,
    
    -- Strategy that suggested this trade
    strategy_used VARCHAR(50),
    strategy_confidence DECIMAL(5,2),
    
    -- Learner Agent reflection
    reflection TEXT NOT NULL,
    what_worked TEXT,
    what_failed TEXT,
    lessons_learned TEXT[],
    
    -- Strategy variants generated
    new_variants JSONB,  -- Array of suggested strategy modifications
    
    -- Scores
    execution_quality DECIMAL(5,2),  -- How well was the trade executed
    timing_quality DECIMAL(5,2),     -- Entry/exit timing
    sizing_quality DECIMAL(5,2),     -- Position sizing
    
    -- Embedding for pattern matching
    reflection_embedding vector(1536)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_reflections_coin ON trade_reflections(coin, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reflections_strategy ON trade_reflections(strategy_used);
CREATE INDEX IF NOT EXISTS idx_reflections_pnl ON trade_reflections(pnl_percent DESC);

-- ═══════════════════════════════════════════════════════════════════════════════
-- X DISCOVERIES
-- Track coins discovered from X/Twitter
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS x_discoveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Coin info
    coin VARCHAR(20) NOT NULL,
    
    -- Tweet info
    tweet_id VARCHAR(50),
    tweet_text TEXT,
    tweet_author VARCHAR(100),
    
    -- Engagement metrics
    like_count INTEGER DEFAULT 0,
    retweet_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    quote_count INTEGER DEFAULT 0,
    engagement_score DECIMAL(10,2),
    
    -- Analysis
    detected_narrative TEXT,
    sentiment_raw DECIMAL(5,2),
    hype_keywords TEXT[],
    
    -- Processing status
    processed BOOLEAN DEFAULT FALSE,
    added_to_universe BOOLEAN DEFAULT FALSE,
    rejection_reason TEXT
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_x_discoveries_coin ON x_discoveries(coin, discovered_at DESC);
CREATE INDEX IF NOT EXISTS idx_x_discoveries_engagement ON x_discoveries(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_x_discoveries_unprocessed ON x_discoveries(processed) WHERE processed = FALSE;

-- ═══════════════════════════════════════════════════════════════════════════════
-- VIEWS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Active tradable coins with latest scores
CREATE OR REPLACE VIEW v_active_universe AS
SELECT 
    coin,
    name,
    volume_24h,
    market_cap,
    price_usd,
    price_change_24h,
    hype_score,
    sentiment_score,
    narrative_strength,
    discovery_source,
    discovered_at,
    coin_age_days,
    is_binance_perp
FROM tradable_universe
WHERE is_active = TRUE 
  AND validation_status = 'approved'
ORDER BY volume_24h DESC;

-- Latest strategy weights
CREATE OR REPLACE VIEW v_strategy_weights AS
SELECT DISTINCT ON (strategy_name)
    strategy_name,
    current_weight,
    win_rate_24h,
    pnl_24h,
    trades_24h,
    affinity_low_vol,
    affinity_normal_vol,
    affinity_high_vol,
    recorded_at
FROM strategy_performance
ORDER BY strategy_name, recorded_at DESC;

-- Recent agent activity summary
CREATE OR REPLACE VIEW v_agent_activity AS
SELECT 
    agent_name,
    action_type,
    COUNT(*) as action_count,
    AVG(confidence) as avg_confidence,
    AVG(duration_ms) as avg_duration_ms,
    MAX(timestamp) as last_activity
FROM agent_logs
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY agent_name, action_type
ORDER BY agent_name, action_count DESC;

-- ═══════════════════════════════════════════════════════════════════════════════
-- FUNCTIONS
-- ═══════════════════════════════════════════════════════════════════════════════

-- Function to find similar memories using vector similarity
CREATE OR REPLACE FUNCTION find_similar_memories(
    query_embedding vector(1536),
    limit_count INTEGER DEFAULT 5,
    min_similarity FLOAT DEFAULT 0.7
)
RETURNS TABLE (
    id UUID,
    title VARCHAR(200),
    content TEXT,
    category VARCHAR(50),
    memory_type VARCHAR(20),
    similarity FLOAT,
    importance_score DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        m.id,
        m.title,
        m.content,
        m.category,
        m.memory_type,
        1 - (m.embedding <=> query_embedding) as similarity,
        m.importance_score
    FROM memories m
    WHERE m.embedding IS NOT NULL
      AND (m.expires_at IS NULL OR m.expires_at > NOW())
      AND 1 - (m.embedding <=> query_embedding) >= min_similarity
    ORDER BY m.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup expired memories
CREATE OR REPLACE FUNCTION cleanup_expired_memories()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM memories 
    WHERE expires_at IS NOT NULL 
      AND expires_at < NOW()
      AND memory_type != 'long';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Function to update memory recall stats
CREATE OR REPLACE FUNCTION touch_memory(memory_id UUID)
RETURNS VOID AS $$
BEGIN
    UPDATE memories
    SET recall_count = recall_count + 1,
        last_recalled_at = NOW(),
        importance_score = LEAST(100, importance_score + 1)
    WHERE id = memory_id;
END;
$$ LANGUAGE plpgsql;

-- ═══════════════════════════════════════════════════════════════════════════════
-- SEED DATA
-- ═══════════════════════════════════════════════════════════════════════════════

-- Initialize strategy performance for all 6 strategies
INSERT INTO strategy_performance (strategy_name, current_weight) VALUES
    ('momentum', 0.20),
    ('mean_reversion', 0.15),
    ('hype_following', 0.20),
    ('contrarian', 0.15),
    ('volatility_expansion', 0.15),
    ('narrative_driven', 0.15)
ON CONFLICT DO NOTHING;

-- Add initial coins to universe (will be updated by Discovery Agent)
INSERT INTO tradable_universe (coin, name, discovery_source, validation_status, is_active) VALUES
    ('BTC', 'Bitcoin', 'seed', 'approved', TRUE),
    ('ETH', 'Ethereum', 'seed', 'approved', TRUE),
    ('SOL', 'Solana', 'seed', 'approved', TRUE),
    ('BNB', 'Binance Coin', 'seed', 'approved', TRUE)
ON CONFLICT (coin) DO NOTHING;

COMMIT;

