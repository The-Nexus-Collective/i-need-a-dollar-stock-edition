"""
Database Configuration and Base Model
"""

import os
from datetime import datetime
from typing import AsyncGenerator
from uuid import uuid4

from sqlalchemy import Column, DateTime, create_engine, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, declared_attr


# Database URL
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://trading_user:trading_secret_2024@localhost:5432/trading_platform"
)

# Convert to async URL if needed
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Sync engine (for migrations)
sync_engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

# Async engine (for application)
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
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
    async with engine.begin() as conn:
        # Note: Using raw SQL init.sql for TimescaleDB features
        # This is just for basic table creation fallback
        await conn.run_sync(Base.metadata.create_all)
