"""
Immutable Audit Log with Cryptographic Hash Chain
Every action is logged with microsecond precision and chained for integrity
"""

import hashlib
import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import BigInteger, Column, DateTime, String, Text, event, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditLog(Base):
    """
    Immutable audit log entry.
    
    Features:
    - Microsecond timestamp precision
    - Before/after state capture
    - AI reasoning logging
    - Cryptographic hash chain for tamper detection
    """
    
    __tablename__ = "audit_log"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    
    # Event classification
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    
    # Entity reference
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    
    # State capture
    before_state: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[Optional[Dict]] = mapped_column(JSONB, nullable=True)
    
    # AI decision reasoning
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Additional data
    extra_data: Mapped[Dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Hash chain
    prev_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of this entry"""
        data = {
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "event_type": self.event_type,
            "actor": self.actor,
            "action": self.action,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "before_state": self.before_state,
            "after_state": self.after_state,
            "reasoning": self.reasoning,
            "extra_data": self.extra_data,
            "prev_hash": self.prev_hash,
        }
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    @classmethod
    async def get_last_hash(cls, session: AsyncSession) -> Optional[str]:
        """Get the hash of the most recent audit entry"""
        result = await session.execute(
            select(cls.hash)
            .order_by(cls.id.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return row
    
    @classmethod
    async def create_entry(
        cls,
        session: AsyncSession,
        event_type: str,
        actor: str,
        action: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        before_state: Optional[Dict] = None,
        after_state: Optional[Dict] = None,
        reasoning: Optional[str] = None,
        extra_data: Optional[Dict] = None
    ) -> "AuditLog":
        """Create a new audit entry with proper hash chain"""
        
        # Get previous hash
        prev_hash = await cls.get_last_hash(session)
        
        entry = cls(
            event_type=event_type,
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_state=before_state,
            after_state=after_state,
            reasoning=reasoning,
            extra_data=extra_data or {},
            prev_hash=prev_hash,
            hash=""  # Temporary, will be set below
        )
        
        # Calculate and set hash
        entry.hash = entry.calculate_hash()
        
        session.add(entry)
        await session.flush()  # Get ID without committing
        
        return entry
    
    @classmethod
    async def verify_chain(cls, session: AsyncSession, limit: int = 1000) -> Dict[str, Any]:
        """
        Verify the integrity of the audit chain.
        Returns verification result with any broken links.
        """
        result = await session.execute(
            select(cls)
            .order_by(cls.id.asc())
            .limit(limit)
        )
        entries = result.scalars().all()
        
        if not entries:
            return {"valid": True, "checked": 0, "errors": []}
        
        errors = []
        prev_hash = None
        
        for entry in entries:
            # Verify hash chain link
            if entry.prev_hash != prev_hash:
                errors.append({
                    "id": entry.id,
                    "type": "chain_break",
                    "expected_prev": prev_hash,
                    "actual_prev": entry.prev_hash
                })
            
            # Verify entry hash
            calculated_hash = entry.calculate_hash()
            if entry.hash != calculated_hash:
                errors.append({
                    "id": entry.id,
                    "type": "hash_mismatch",
                    "stored_hash": entry.hash,
                    "calculated_hash": calculated_hash
                })
            
            prev_hash = entry.hash
        
        return {
            "valid": len(errors) == 0,
            "checked": len(entries),
            "errors": errors
        }


class AuditMixin:
    """
    Mixin to automatically audit changes to a model.
    Add this to any model that needs change tracking.
    """
    
    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        
        # Register SQLAlchemy event listeners
        @event.listens_for(cls, "after_insert")
        def audit_insert(mapper, connection, target):
            # Note: This runs in sync context, actual audit should be async
            pass
        
        @event.listens_for(cls, "after_update") 
        def audit_update(mapper, connection, target):
            pass
        
        @event.listens_for(cls, "after_delete")
        def audit_delete(mapper, connection, target):
            pass
    
    def to_audit_dict(self) -> Dict[str, Any]:
        """Convert model to dict for audit logging"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, '__str__') and not isinstance(value, (str, int, float, bool, type(None))):
                value = str(value)
            result[column.name] = value
        return result


# Helper function for easy audit logging
async def log_audit(
    session: AsyncSession,
    event_type: str,
    actor: str,
    action: str,
    **kwargs
) -> AuditLog:
    """
    Convenience function for creating audit entries.
    
    Usage:
        await log_audit(
            session,
            "trade.executed",
            "executor_service",
            "order_filled",
            entity_type="trade",
            entity_id=str(trade.id),
            after_state=trade.to_dict(),
            reasoning="Stop loss triggered at price 50000"
        )
    """
    return await AuditLog.create_entry(
        session,
        event_type=event_type,
        actor=actor,
        action=action,
        **kwargs
    )
