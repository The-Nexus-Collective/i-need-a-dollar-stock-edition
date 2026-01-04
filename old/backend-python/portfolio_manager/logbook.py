"""
Trading Logbook - Human-readable analysis storage

Stores Grok's analysis text and recommendations for each cycle.
Accessible via API for frontend display.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """A single logbook entry from one analysis cycle."""
    
    id: str
    timestamp: datetime
    cycle_number: int
    
    # Human-readable content from Grok
    analysis_text: str
    market_summary: str
    
    # Actions taken
    positions_closed: List[Dict[str, Any]]
    positions_opened: List[Dict[str, Any]]
    positions_kept: List[str]
    positions_extended: List[Dict[str, Any]] = field(default_factory=list)
    positions_reduced: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metrics
    coins_analyzed: int = 0
    coins_skipped: int = 0
    tokens_used: int = 0
    
    # Portfolio state at this point
    total_equity: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: int = 0
    deployment_percent: float = 0.0
    
    # Debug: raw Grok prompt and response
    raw_prompt: str = ""
    raw_response: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "cycle_number": self.cycle_number,
            "analysis_text": self.analysis_text,
            "market_summary": self.market_summary,
            "positions_closed": self.positions_closed,
            "positions_opened": self.positions_opened,
            "positions_kept": self.positions_kept,
            "positions_extended": self.positions_extended,
            "positions_reduced": self.positions_reduced,
            "coins_analyzed": self.coins_analyzed,
            "coins_skipped": self.coins_skipped,
            "tokens_used": self.tokens_used,
            "total_equity": self.total_equity,
            "unrealized_pnl": self.unrealized_pnl,
            "open_positions": self.open_positions,
            "deployment_percent": self.deployment_percent,
            "raw_prompt": self.raw_prompt,
            "raw_response": self.raw_response,
        }
    
    def to_summary(self) -> dict:
        """Short summary for list views."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "cycle_number": self.cycle_number,
            "market_summary": self.market_summary,
            "actions": {
                "closed": len(self.positions_closed),
                "opened": len(self.positions_opened),
                "kept": len(self.positions_kept),
                "extended": len(self.positions_extended),
                "reduced": len(self.positions_reduced),
            },
            "total_equity": self.total_equity,
            "deployment_percent": self.deployment_percent,
        }


class TradingLogbook:
    """
    Stores and retrieves trading analysis logs.
    
    For now, uses in-memory storage.
    Can be extended to use database for persistence.
    """
    
    MAX_ENTRIES = 1000  # Keep last 1000 entries in memory
    
    def __init__(self):
        self._entries: List[LogEntry] = []
        self._cycle_counter = 0
        self._broadcast_callback = None
    
    def set_broadcast_callback(self, callback):
        """Set callback for real-time log broadcasting."""
        self._broadcast_callback = callback
    
    @property
    def cycle_count(self) -> int:
        return self._cycle_counter
    
    async def log(
        self,
        analysis_text: str,
        market_summary: str,
        positions_closed: List[Dict[str, Any]],
        positions_opened: List[Dict[str, Any]],
        positions_kept: List[str],
        positions_extended: List[Dict[str, Any]] = None,
        positions_reduced: List[Dict[str, Any]] = None,
        coins_analyzed: int = 0,
        coins_skipped: int = 0,
        tokens_used: int = 0,
        total_equity: float = 0.0,
        unrealized_pnl: float = 0.0,
        open_positions: int = 0,
        deployment_percent: float = 0.0,
        raw_prompt: str = "",
        raw_response: str = "",
    ) -> LogEntry:
        """
        Add a new entry to the logbook.
        
        Args:
            analysis_text: Human-readable analysis from Grok
            market_summary: Brief market summary
            positions_closed: List of closed position details
            positions_opened: List of opened position details
            positions_kept: List of kept position symbols
            positions_extended: List of extended position details
            positions_reduced: List of reduced position details
            coins_analyzed: Number of coins analyzed
            coins_skipped: Number of coins skipped (sparse data)
            tokens_used: Grok tokens consumed
            total_equity: Current portfolio equity
            unrealized_pnl: Current unrealized PnL
            open_positions: Number of open positions
            deployment_percent: Current capital deployment percentage
            raw_prompt: Raw prompt sent to Grok (for debugging)
            raw_response: Raw response from Grok (for debugging)
            
        Returns:
            The created LogEntry
        """
        self._cycle_counter += 1
        
        entry = LogEntry(
            id=f"LOG_{uuid4().hex[:8].upper()}",
            timestamp=datetime.utcnow(),
            cycle_number=self._cycle_counter,
            analysis_text=analysis_text,
            market_summary=market_summary,
            positions_closed=positions_closed,
            positions_opened=positions_opened,
            positions_kept=positions_kept,
            positions_extended=positions_extended or [],
            positions_reduced=positions_reduced or [],
            coins_analyzed=coins_analyzed,
            coins_skipped=coins_skipped,
            tokens_used=tokens_used,
            total_equity=total_equity,
            unrealized_pnl=unrealized_pnl,
            open_positions=open_positions,
            deployment_percent=deployment_percent,
            raw_prompt=raw_prompt,
            raw_response=raw_response,
        )
        
        # Add to list
        self._entries.append(entry)
        
        # Trim if too many
        if len(self._entries) > self.MAX_ENTRIES:
            self._entries = self._entries[-self.MAX_ENTRIES:]
        
        # Log to console
        logger.info(f"📝 Logbook entry #{self._cycle_counter}: {market_summary}")
        
        # Broadcast to WebSocket clients
        if self._broadcast_callback:
            try:
                await self._broadcast_callback({
                    "type": "logbook_entry",
                    "data": entry.to_dict()
                })
            except Exception as e:
                logger.debug(f"Broadcast failed: {e}")
        
        return entry
    
    def get_latest(self, limit: int = 10) -> List[LogEntry]:
        """Get the most recent entries."""
        return list(reversed(self._entries[-limit:]))
    
    def get_entry(self, entry_id: str) -> Optional[LogEntry]:
        """Get a specific entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None
    
    def get_by_cycle(self, cycle_number: int) -> Optional[LogEntry]:
        """Get entry by cycle number."""
        for entry in self._entries:
            if entry.cycle_number == cycle_number:
                return entry
        return None
    
    def get_summaries(self, limit: int = 50) -> List[dict]:
        """Get summaries of recent entries (for list views)."""
        return [e.to_summary() for e in reversed(self._entries[-limit:])]
    
    def search(self, query: str, limit: int = 20) -> List[LogEntry]:
        """Simple text search through analysis text."""
        query_lower = query.lower()
        matches = []
        
        for entry in reversed(self._entries):
            if query_lower in entry.analysis_text.lower():
                matches.append(entry)
                if len(matches) >= limit:
                    break
        
        return matches
    
    def get_statistics(self) -> dict:
        """Get logbook statistics."""
        if not self._entries:
            return {
                "total_entries": 0,
                "total_cycles": self._cycle_counter,
            }
        
        total_tokens = sum(e.tokens_used for e in self._entries)
        total_closed = sum(len(e.positions_closed) for e in self._entries)
        total_opened = sum(len(e.positions_opened) for e in self._entries)
        
        return {
            "total_entries": len(self._entries),
            "total_cycles": self._cycle_counter,
            "total_tokens_used": total_tokens,
            "total_positions_closed": total_closed,
            "total_positions_opened": total_opened,
            "oldest_entry": self._entries[0].timestamp.isoformat() if self._entries else None,
            "newest_entry": self._entries[-1].timestamp.isoformat() if self._entries else None,
        }
    
    def reset(self):
        """Clear all entries (for paper trading reset)."""
        old_count = len(self._entries)
        self._entries.clear()
        self._cycle_counter = 0
        logger.warning(f"Logbook reset: cleared {old_count} entries")
    
    def to_dict(self) -> dict:
        """Serialize logbook state."""
        return {
            "statistics": self.get_statistics(),
            "recent_entries": [e.to_dict() for e in self.get_latest(5)],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_logbook: Optional[TradingLogbook] = None


def get_logbook() -> TradingLogbook:
    """Get or create the global logbook instance."""
    global _logbook
    if _logbook is None:
        _logbook = TradingLogbook()
    return _logbook

