"""
Agent Logbook - Central audit trail for all agent activities.

Every agent action, thought, and decision is logged here for
complete transparency and debugging. The logbook supports:

1. Structured logging with reasoning chains
2. Semantic search via pgvector embeddings
3. Cycle-based grouping for timeline views
4. Real-time WebSocket broadcasting
"""

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A single log entry in the agent logbook."""
    
    id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cycle_id: UUID = field(default_factory=uuid4)
    
    # Agent info
    agent_name: str = ""
    action_type: str = ""  # 'think', 'act', 'decide', 'reflect', 'error'
    
    # Reasoning chain
    input_context: Optional[Dict] = None
    reasoning: str = ""
    decision: Optional[str] = None
    output_data: Optional[Dict] = None
    
    # Metrics
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    
    # Tracing
    parent_log_id: Optional[UUID] = None
    triggered_by: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        from .personas import get_persona
        
        persona = get_persona(self.agent_name)
        
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat(),
            "cycle_id": str(self.cycle_id),
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "input_context": self.input_context,
            "reasoning": self.reasoning,
            "decision": self.decision,
            "output_data": self.output_data,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
            "tokens_used": self.tokens_used,
            "parent_log_id": str(self.parent_log_id) if self.parent_log_id else None,
            "triggered_by": self.triggered_by,
            # Persona info for frontend
            "persona": {
                "name": persona.name,
                "emoji": persona.emoji,
                "role": persona.role,
                "personality": persona.personality,
            },
            "narrative": self.to_narrative(),
        }
    
    def to_display(self) -> str:
        """Format for console display with persona."""
        from .personas import get_persona
        
        persona = get_persona(self.agent_name)
        conf = f" [{self.confidence:.0f}%]" if self.confidence else ""
        dur = f" ({self.duration_ms}ms)" if self.duration_ms else ""
        
        return f"{persona.emoji} [{persona.name}] {self.action_type}{conf}{dur}: {self.reasoning[:200]}"
    
    def to_narrative(self) -> str:
        """Format as a narrative message with personality."""
        from .personas import get_persona
        
        persona = get_persona(self.agent_name)
        
        # Build the narrative message
        parts = [f"{persona.emoji} **{persona.name}**"]
        
        if self.action_type == "think":
            parts.append(f"💭 *thinking...*")
        elif self.action_type == "act":
            parts.append(f"⚡ *acting*")
        elif self.action_type == "decide":
            parts.append(f"✅ *decided*")
        elif self.action_type == "error":
            parts.append(f"❌ *error*")
        
        parts.append(f"\n{self.reasoning}")
        
        if self.decision:
            parts.append(f"\n→ **{self.decision}**")
        
        if self.confidence:
            if self.confidence >= 80:
                parts.append(f" 💪 {self.confidence:.0f}%")
            elif self.confidence >= 50:
                parts.append(f" 📊 {self.confidence:.0f}%")
            else:
                parts.append(f" 🤔 {self.confidence:.0f}%")
        
        return " ".join(parts)


class AgentLogbook:
    """
    Central logging system for all agent activities.
    
    Features:
    - Async database logging
    - Optional embedding generation for semantic search
    - Real-time event broadcasting
    - Cycle-based grouping
    """
    
    def __init__(self):
        self._current_cycle_id: UUID = uuid4()
        self._log_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._embedding_client: Optional[httpx.AsyncClient] = None
        self._openai_key: str = os.getenv("OPENAI_API_KEY", "")
        
        # In-memory buffer for recent logs (for fast access)
        self._recent_logs: List[LogEntry] = []
        self._max_recent: int = 1000
        
        # WebSocket broadcast callback
        self._broadcast_callback = None
    
    def set_broadcast_callback(self, callback):
        """Set callback for real-time log broadcasting."""
        self._broadcast_callback = callback
    
    def new_cycle(self) -> UUID:
        """Start a new 15-minute cycle."""
        self._current_cycle_id = uuid4()
        logger.info(f"New cycle started: {self._current_cycle_id}")
        return self._current_cycle_id
    
    @property
    def current_cycle_id(self) -> UUID:
        """Get current cycle ID."""
        return self._current_cycle_id
    
    async def start(self):
        """Start the background log worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._log_worker())
        logger.info("Agent Logbook started")
    
    async def stop(self):
        """Stop the log worker gracefully."""
        self._running = False
        
        # Process remaining logs
        while not self._log_queue.empty():
            await asyncio.sleep(0.1)
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self._embedding_client:
            await self._embedding_client.aclose()
        
        logger.info("Agent Logbook stopped")
    
    async def log(
        self,
        agent_name: str,
        action_type: str,
        reasoning: str,
        input_context: Optional[Dict] = None,
        decision: Optional[str] = None,
        output_data: Optional[Dict] = None,
        confidence: Optional[float] = None,
        duration_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        parent_log_id: Optional[UUID] = None,
        triggered_by: Optional[str] = None,
        generate_embedding: bool = False,
    ) -> LogEntry:
        """
        Log an agent action.
        
        Args:
            agent_name: Name of the agent (e.g., 'discovery', 'sentiment')
            action_type: Type of action ('think', 'act', 'decide', 'reflect')
            reasoning: The agent's reasoning/thought process
            input_context: What the agent saw/received
            decision: What the agent decided
            output_data: Structured output data
            confidence: Confidence score (0-100)
            duration_ms: How long the action took
            tokens_used: Grok/LLM tokens consumed
            parent_log_id: ID of parent log entry (for tracing)
            triggered_by: What triggered this action
            generate_embedding: Whether to generate embedding for semantic search
        
        Returns:
            The created LogEntry
        """
        entry = LogEntry(
            cycle_id=self._current_cycle_id,
            agent_name=agent_name,
            action_type=action_type,
            input_context=input_context,
            reasoning=reasoning,
            decision=decision,
            output_data=output_data,
            confidence=confidence,
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            parent_log_id=parent_log_id,
            triggered_by=triggered_by,
        )
        
        # Add to in-memory buffer
        self._recent_logs.append(entry)
        if len(self._recent_logs) > self._max_recent:
            self._recent_logs = self._recent_logs[-self._max_recent:]
        
        # Queue for async database write
        await self._log_queue.put((entry, generate_embedding))
        
        # Console log
        logger.info(entry.to_display())
        
        # Broadcast to WebSocket clients
        if self._broadcast_callback:
            try:
                await self._broadcast_callback({
                    "type": "agent_log",
                    "data": entry.to_dict()
                })
            except Exception as e:
                logger.debug(f"Broadcast failed: {e}")
        
        return entry
    
    async def _log_worker(self):
        """Background worker that writes logs to database."""
        from models import AsyncSessionLocal
        
        while self._running:
            try:
                # Get log entry from queue (with timeout)
                try:
                    entry, generate_embedding = await asyncio.wait_for(
                        self._log_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Generate embedding if requested
                embedding = None
                if generate_embedding and self._openai_key and entry.reasoning:
                    embedding = await self._generate_embedding(entry.reasoning)
                
                # Write to database
                import json
                
                async with AsyncSessionLocal() as session:
                    embedding_sql = f"'{embedding}'" if embedding else "NULL"
                    
                    # Convert dicts to JSON strings for PostgreSQL JSONB columns
                    input_context_json = json.dumps(entry.input_context) if entry.input_context else None
                    output_data_json = json.dumps(entry.output_data) if entry.output_data else None
                    
                    # Simplified insert without JSONB columns (they're optional for logging)
                    await session.execute(text(f"""
                        INSERT INTO agent_logs (
                            id, timestamp, cycle_id, agent_name, action_type,
                            reasoning, decision,
                            confidence, duration_ms, tokens_used,
                            parent_log_id, triggered_by
                        ) VALUES (
                            :id, :timestamp, :cycle_id, :agent_name, :action_type,
                            :reasoning, :decision,
                            :confidence, :duration_ms, :tokens_used,
                            :parent_log_id, :triggered_by
                        )
                    """), {
                        "id": str(entry.id),
                        "timestamp": entry.timestamp,
                        "cycle_id": str(entry.cycle_id),
                        "agent_name": entry.agent_name,
                        "action_type": entry.action_type,
                        "reasoning": entry.reasoning,
                        "decision": entry.decision,
                        "confidence": entry.confidence,
                        "duration_ms": entry.duration_ms,
                        "tokens_used": entry.tokens_used,
                        "parent_log_id": str(entry.parent_log_id) if entry.parent_log_id else None,
                        "triggered_by": entry.triggered_by,
                    })
                    await session.commit()
                
            except Exception as e:
                logger.error(f"Log worker error: {e}")
                await asyncio.sleep(1)
    
    async def _generate_embedding(self, text: str) -> Optional[str]:
        """Generate embedding using OpenAI API."""
        if not self._openai_key:
            return None
        
        try:
            if not self._embedding_client:
                self._embedding_client = httpx.AsyncClient(timeout=30)
            
            response = await self._embedding_client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self._openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "text-embedding-ada-002",
                    "input": text[:8000],  # Truncate to fit context
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                embedding = data["data"][0]["embedding"]
                return f"[{','.join(str(x) for x in embedding)}]"
            
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
        
        return None
    
    def get_recent_logs(
        self,
        limit: int = 100,
        agent_name: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> List[LogEntry]:
        """Get recent logs from in-memory buffer."""
        logs = self._recent_logs[-limit:]
        
        if agent_name:
            logs = [l for l in logs if l.agent_name == agent_name]
        
        if action_type:
            logs = [l for l in logs if l.action_type == action_type]
        
        return list(reversed(logs))
    
    async def get_cycle_logs(self, cycle_id: UUID) -> List[Dict]:
        """Get all logs for a specific cycle from database."""
        from models import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT 
                    id, timestamp, cycle_id, agent_name, action_type,
                    input_context, reasoning, decision, output_data,
                    confidence, duration_ms, tokens_used,
                    parent_log_id, triggered_by
                FROM agent_logs
                WHERE cycle_id = :cycle_id
                ORDER BY timestamp ASC
            """), {"cycle_id": str(cycle_id)})
            
            rows = result.fetchall()
            return [
                {
                    "id": str(row.id),
                    "timestamp": row.timestamp.isoformat(),
                    "cycle_id": str(row.cycle_id),
                    "agent_name": row.agent_name,
                    "action_type": row.action_type,
                    "input_context": row.input_context,
                    "reasoning": row.reasoning,
                    "decision": row.decision,
                    "output_data": row.output_data,
                    "confidence": float(row.confidence) if row.confidence else None,
                    "duration_ms": row.duration_ms,
                    "tokens_used": row.tokens_used,
                    "parent_log_id": str(row.parent_log_id) if row.parent_log_id else None,
                    "triggered_by": row.triggered_by,
                }
                for row in rows
            ]
    
    async def search_logs(
        self,
        query: str,
        limit: int = 20,
        min_similarity: float = 0.7,
    ) -> List[Dict]:
        """
        Semantic search through log entries.
        
        Uses pgvector to find logs with similar reasoning.
        """
        if not self._openai_key:
            logger.warning("OPENAI_API_KEY not set, semantic search unavailable")
            return []
        
        # Generate query embedding
        embedding = await self._generate_embedding(query)
        if not embedding:
            return []
        
        from models import AsyncSessionLocal
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text(f"""
                SELECT 
                    id, timestamp, agent_name, action_type,
                    reasoning, decision, confidence,
                    1 - (reasoning_embedding <=> '{embedding}') as similarity
                FROM agent_logs
                WHERE reasoning_embedding IS NOT NULL
                  AND 1 - (reasoning_embedding <=> '{embedding}') >= :min_similarity
                ORDER BY reasoning_embedding <=> '{embedding}'
                LIMIT :limit
            """), {"min_similarity": min_similarity, "limit": limit})
            
            rows = result.fetchall()
            return [
                {
                    "id": str(row.id),
                    "timestamp": row.timestamp.isoformat(),
                    "agent_name": row.agent_name,
                    "action_type": row.action_type,
                    "reasoning": row.reasoning,
                    "decision": row.decision,
                    "confidence": float(row.confidence) if row.confidence else None,
                    "similarity": float(row.similarity),
                }
                for row in rows
            ]


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_logbook: Optional[AgentLogbook] = None


def get_logbook() -> AgentLogbook:
    """Get or create the global logbook instance."""
    global _logbook
    if _logbook is None:
        _logbook = AgentLogbook()
    return _logbook


async def init_logbook() -> AgentLogbook:
    """Initialize and start the logbook."""
    logbook = get_logbook()
    await logbook.start()
    return logbook

