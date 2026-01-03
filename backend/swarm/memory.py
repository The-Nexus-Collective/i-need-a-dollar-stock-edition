"""
Swarm Memory - Collective Long-Term Memory

A vector-based memory system using pgvector.
Agents can store and retrieve insights based on semantic similarity.

Features:
- Store insights with embeddings
- Recall similar past experiences
- Track memory importance and usage
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from .grok import get_grok

logger = logging.getLogger(__name__)


@dataclass
class Memory:
    """A single memory entry."""
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # Content
    insight: str = ""
    category: str = "general"  # trade, market, strategy, pattern
    
    # Context
    context: Dict[str, Any] = field(default_factory=dict)
    related_coins: List[str] = field(default_factory=list)
    
    # Importance
    importance: float = 0.5  # 0-1
    recall_count: int = 0
    last_recalled: Optional[datetime] = None
    
    # Source
    source_agent: str = ""
    
    # Lifecycle
    expires_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "created_at": self.created_at.isoformat(),
            "insight": self.insight,
            "category": self.category,
            "context": self.context,
            "related_coins": self.related_coins,
            "importance": self.importance,
            "recall_count": self.recall_count,
            "source_agent": self.source_agent,
        }


class SwarmMemory:
    """
    Collective memory using vector embeddings.
    
    Agents can store and retrieve insights.
    Similar situations trigger recall of relevant past experiences.
    """
    
    def __init__(self, db_pool=None):
        self._db_pool = db_pool
        self._local_cache: Dict[UUID, Memory] = {}  # In-memory cache
        self._lock = asyncio.Lock()
        self._grok = get_grok()
    
    async def remember(
        self,
        insight: str,
        category: str = "general",
        context: Dict = None,
        related_coins: List[str] = None,
        importance: float = 0.5,
        source_agent: str = "",
        ttl_days: Optional[int] = None,
    ) -> Memory:
        """
        Store a new insight in memory.
        
        Args:
            insight: The insight to remember
            category: Category of memory
            context: Additional context
            related_coins: Coins this relates to
            importance: How important (0-1)
            source_agent: Agent that created this memory
            ttl_days: Days until expiration (None = permanent)
        
        Returns:
            The created Memory
        """
        memory = Memory(
            insight=insight,
            category=category,
            context=context or {},
            related_coins=related_coins or [],
            importance=importance,
            source_agent=source_agent,
            expires_at=datetime.utcnow() + timedelta(days=ttl_days) if ttl_days else None,
        )
        
        # Cache locally
        async with self._lock:
            self._local_cache[memory.id] = memory
        
        # Persist to database if available
        if self._db_pool:
            await self._persist_memory(memory)
        
        logger.debug(f"Memory stored: {insight[:50]}...")
        return memory
    
    async def _persist_memory(self, memory: Memory):
        """Persist memory to PostgreSQL with vector embedding."""
        try:
            # Get embedding for the insight
            embedding = await self._grok.get_embedding(memory.insight)
            
            async with self._db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO memories (
                        id, created_at, memory_type, category, title, content,
                        embedding, metadata, expires_at, importance_score,
                        source_agent, related_coins
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6,
                        $7, $8, $9, $10,
                        $11, $12
                    )
                """,
                    memory.id,
                    memory.created_at,
                    "medium",  # Default type
                    memory.category,
                    memory.insight[:200],  # Title
                    memory.insight,
                    embedding,
                    memory.context,
                    memory.expires_at,
                    memory.importance,
                    memory.source_agent,
                    memory.related_coins,
                )
        except Exception as e:
            logger.warning(f"Failed to persist memory: {e}")
    
    async def recall(
        self,
        situation: str,
        limit: int = 5,
        category: Optional[str] = None,
        min_importance: float = 0.0,
    ) -> List[Memory]:
        """
        Recall relevant memories based on current situation.
        
        Uses vector similarity to find relevant past experiences.
        
        Args:
            situation: Current situation to match against
            limit: Maximum memories to return
            category: Filter by category
            min_importance: Minimum importance threshold
        
        Returns:
            List of relevant memories, most relevant first
        """
        # First try database recall
        if self._db_pool:
            memories = await self._recall_from_db(situation, limit, category, min_importance)
            if memories:
                return memories
        
        # Fallback to local cache
        return await self._recall_from_cache(situation, limit, category, min_importance)
    
    async def _recall_from_db(
        self,
        situation: str,
        limit: int,
        category: Optional[str],
        min_importance: float,
    ) -> List[Memory]:
        """Recall memories from PostgreSQL using vector similarity."""
        try:
            # Get embedding for the situation
            embedding = await self._grok.get_embedding(situation)
            
            async with self._db_pool.acquire() as conn:
                query = """
                    SELECT 
                        id, created_at, category, title, content,
                        metadata, importance_score, recall_count,
                        source_agent, related_coins
                    FROM memories
                    WHERE (expires_at IS NULL OR expires_at > NOW())
                        AND importance_score >= $3
                """
                
                if category:
                    query += " AND category = $4"
                    query += " ORDER BY embedding <-> $1 LIMIT $2"
                    rows = await conn.fetch(query, embedding, limit, min_importance, category)
                else:
                    query += " ORDER BY embedding <-> $1 LIMIT $2"
                    rows = await conn.fetch(query, embedding, limit, min_importance)
                
                memories = []
                for row in rows:
                    memory = Memory(
                        id=row['id'],
                        created_at=row['created_at'],
                        category=row['category'],
                        insight=row['content'],
                        context=row['metadata'] or {},
                        importance=float(row['importance_score'] or 0.5),
                        recall_count=row['recall_count'] or 0,
                        source_agent=row['source_agent'] or "",
                        related_coins=row['related_coins'] or [],
                    )
                    memories.append(memory)
                    
                    # Update recall stats
                    await self._touch_memory(conn, memory.id)
                
                return memories
                
        except Exception as e:
            logger.warning(f"Database recall failed: {e}")
            return []
    
    async def _touch_memory(self, conn, memory_id: UUID):
        """Update memory recall stats."""
        try:
            await conn.execute("""
                UPDATE memories
                SET recall_count = recall_count + 1,
                    last_recalled_at = NOW()
                WHERE id = $1
            """, memory_id)
        except Exception as e:
            logger.debug(f"Failed to touch memory: {e}")
    
    async def _recall_from_cache(
        self,
        situation: str,
        limit: int,
        category: Optional[str],
        min_importance: float,
    ) -> List[Memory]:
        """Recall from local cache using simple keyword matching."""
        async with self._lock:
            memories = list(self._local_cache.values())
        
        # Filter
        if category:
            memories = [m for m in memories if m.category == category]
        memories = [m for m in memories if m.importance >= min_importance]
        
        # Filter expired
        now = datetime.utcnow()
        memories = [m for m in memories if m.expires_at is None or m.expires_at > now]
        
        # Simple keyword relevance
        situation_words = set(situation.lower().split())
        
        def relevance(m: Memory) -> float:
            memory_words = set(m.insight.lower().split())
            overlap = len(situation_words & memory_words)
            return overlap / max(len(situation_words), 1)
        
        # Sort by relevance
        memories.sort(key=relevance, reverse=True)
        
        return memories[:limit]
    
    async def forget_expired(self) -> int:
        """Remove expired memories."""
        now = datetime.utcnow()
        count = 0
        
        async with self._lock:
            expired_ids = [
                mid for mid, m in self._local_cache.items()
                if m.expires_at and m.expires_at < now
            ]
            for mid in expired_ids:
                del self._local_cache[mid]
                count += 1
        
        # Also clean database
        if self._db_pool:
            try:
                async with self._db_pool.acquire() as conn:
                    result = await conn.execute("""
                        DELETE FROM memories 
                        WHERE expires_at IS NOT NULL AND expires_at < NOW()
                    """)
                    # Get count from result if available
            except Exception as e:
                logger.warning(f"Database cleanup failed: {e}")
        
        return count
    
    def get_recent(self, limit: int = 20) -> List[Memory]:
        """Get most recent memories."""
        memories = list(self._local_cache.values())
        memories.sort(key=lambda m: m.created_at, reverse=True)
        return memories[:limit]
    
    def get_important(self, limit: int = 10) -> List[Memory]:
        """Get most important memories."""
        memories = list(self._local_cache.values())
        memories.sort(key=lambda m: m.importance, reverse=True)
        return memories[:limit]
    
    def __len__(self) -> int:
        return len(self._local_cache)


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_swarm_memory: Optional[SwarmMemory] = None


def get_swarm_memory(db_pool=None) -> SwarmMemory:
    """Get or create global swarm memory."""
    global _swarm_memory
    if _swarm_memory is None:
        _swarm_memory = SwarmMemory(db_pool)
    return _swarm_memory

