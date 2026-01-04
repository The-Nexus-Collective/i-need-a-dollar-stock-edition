"""
Database Configuration and Base Model

Uses lazy initialization to ensure DATABASE_URL is read when the engine
is first used, not at module import time. This fixes issues when the
environment variable is set after imports have already occurred.
"""

import logging
import os
import re
import ssl
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

# IMPORTANT: Import greenlet before SQLAlchemy to ensure async support works
import greenlet  # noqa: F401

from sqlalchemy import Column, DateTime, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# LAZY ENGINE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

# Private state for lazy initialization
_sync_engine = None
_async_engine = None
_async_session_factory = None


def _get_database_url() -> str:
    """Get DATABASE_URL from environment, with default for local development."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://trading_user:trading_secret_2024@localhost:5432/trading_platform"
    )


def _get_async_database_url() -> tuple[str, dict]:
    """
    Convert DATABASE_URL to async format and extract SSL settings.
    
    Returns:
        Tuple of (async_url, connect_args)
    """
    database_url = _get_database_url()
    async_url = database_url
    
    # Convert to asyncpg driver
    if async_url.startswith("postgresql://"):
        async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
    
    # Handle SSL for asyncpg (uses 'ssl' parameter instead of sslmode)
    # Digital Ocean uses ?sslmode=require which asyncpg doesn't understand
    use_ssl = "sslmode=require" in async_url or "sslmode=verify" in async_url
    async_url = re.sub(r'[?&]sslmode=[^&]*', '', async_url)
    # Clean up URL if it ends with ? or has double &&
    async_url = async_url.rstrip('?').replace('&&', '&').rstrip('&')
    
    # SSL context for asyncpg
    connect_args = {}
    if use_ssl:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ssl_context
    
    return async_url, connect_args


def get_sync_engine():
    """
    Get or create the sync engine (for migrations).
    
    Uses lazy initialization to ensure DATABASE_URL is read at first use.
    """
    global _sync_engine
    if _sync_engine is None:
        database_url = _get_database_url()
        logger.info(f"Creating sync database engine: {database_url[:50]}...")
        _sync_engine = create_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10
        )
    return _sync_engine


def get_async_engine():
    """
    Get or create the async engine (for application).
    
    Uses lazy initialization to ensure DATABASE_URL is read at first use,
    after environment variables have been properly set.
    """
    global _async_engine
    if _async_engine is None:
        async_url, connect_args = _get_async_database_url()
        logger.info(f"Creating async database engine: {async_url[:50]}...")
        _async_engine = create_async_engine(
            async_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            connect_args=connect_args
        )
    return _async_engine


def get_async_session_factory():
    """
    Get or create the async session factory.
    
    Uses lazy initialization to ensure engine is created first.
    """
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )
    return _async_session_factory


# ═══════════════════════════════════════════════════════════════════════════════
# BACKWARDS COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

# These are accessed by other modules - use property-like access via functions
# For modules that import these directly, we provide lazy wrappers

class _LazyEngine:
    """Lazy wrapper that creates engine on first attribute access."""
    
    def __getattr__(self, name):
        return getattr(get_async_engine(), name)
    
    def __await__(self):
        return get_async_engine().__await__()


class _LazySyncEngine:
    """Lazy wrapper that creates sync engine on first attribute access."""
    
    def __getattr__(self, name):
        return getattr(get_sync_engine(), name)


class _LazySessionFactory:
    """Lazy wrapper that creates session factory on first call."""
    
    def __call__(self):
        return get_async_session_factory()()
    
    def __getattr__(self, name):
        return getattr(get_async_session_factory(), name)


# Backwards-compatible exports (lazy wrappers)
engine = _LazyEngine()
sync_engine = _LazySyncEngine()
AsyncSessionLocal = _LazySessionFactory()


# ═══════════════════════════════════════════════════════════════════════════════
# BASE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    """Base class for all models"""
    
    @declared_attr.directive
    def __tablename__(cls) -> str:
        """Generate table name from class name"""
        # Convert CamelCase to snake_case
        name = cls.__name__
        return ''.join(
            ['_' + c.lower() if c.isupper() else c for c in name]
        ).lstrip('_') + 's'


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )


class UUIDMixin:
    """Mixin for UUID primary key"""
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE SESSION DEPENDENCY
# ═══════════════════════════════════════════════════════════════════════════════

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Uses lazy initialization - engine is created on first call,
    ensuring DATABASE_URL is read after environment is set up.
    """
    session = get_async_session_factory()()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database tables"""
    async with get_async_engine().begin() as conn:
        # Note: Using raw SQL init.sql for TimescaleDB features
        # This is just for basic table creation fallback
        await conn.run_sync(Base.metadata.create_all)
