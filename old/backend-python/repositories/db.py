"""
Database Connection Pool - Singleton for async DB access.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Singleton pool
_db_pool = None


def get_database_url() -> str:
    """Get and normalize database URL."""
    url = os.getenv("DATABASE_URL", "")
    
    # Remove SQLAlchemy dialect prefix if present
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://")
    
    return url


class DatabasePool:
    """
    Async database connection pool wrapper.
    
    Usage:
        pool = await DatabasePool.get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM ...")
    """
    
    _pool = None
    
    @classmethod
    async def get_pool(cls):
        """Get or create the connection pool."""
        if cls._pool is None:
            try:
                import asyncpg
                
                url = get_database_url()
                if not url:
                    logger.warning("DATABASE_URL not set")
                    return None
                
                # Detect SSL requirement
                use_ssl = 'digitalocean' in url.lower() or 'ondigitalocean' in url.lower()
                
                cls._pool = await asyncpg.create_pool(
                    url,
                    min_size=2,
                    max_size=10,
                    ssl='require' if use_ssl else None,
                )
                logger.info("Database pool created")
            except ImportError:
                logger.warning("asyncpg not installed")
                return None
            except Exception as e:
                logger.error(f"Failed to create DB pool: {e}")
                return None
        
        return cls._pool
    
    @classmethod
    async def close(cls):
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database pool closed")


async def get_db_pool():
    """Convenience function to get the pool."""
    return await DatabasePool.get_pool()

