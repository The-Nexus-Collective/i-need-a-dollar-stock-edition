#!/usr/bin/env python3
"""
Database Migration Runner with Version Tracking

Features:
- Tracks applied migrations in schema_migrations table
- Only runs pending migrations
- Supports both sync and async execution
- Handles multi-statement SQL files
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


MIGRATIONS_DIR = Path(__file__).parent
MIGRATIONS = [
    ("001", "init.sql"),
    ("002", "002_add_filter_columns.sql"),
    ("003", "003_account_state.sql"),
    ("004", "004_leverage_and_paper_mode.sql"),
    ("005", "005_multi_asset.sql"),
    ("006", "006_velocity_metrics.sql"),
]


async def ensure_migrations_table(conn):
    """Create the schema_migrations tracking table if it doesn't exist."""
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)


async def get_applied_migrations(conn) -> set:
    """Get set of already-applied migration versions."""
    result = await conn.execute("SELECT version FROM schema_migrations")
    rows = await result.fetchall()
    return {row[0] for row in rows}


async def apply_migration(conn, version: str, filename: str) -> bool:
    """Apply a single migration file."""
    filepath = MIGRATIONS_DIR / filename
    
    if not filepath.exists():
        print(f"  ⚠️  Migration file not found: {filename}")
        return False
    
    with open(filepath, 'r') as f:
        sql_content = f.read()
    
    # Split by semicolons, handling comments
    statements = []
    current_stmt = []
    
    for line in sql_content.split('\n'):
        stripped = line.strip()
        
        # Skip pure comment lines at statement boundaries
        if not current_stmt and stripped.startswith('--'):
            continue
        
        current_stmt.append(line)
        
        # Check if line ends a statement
        if stripped.endswith(';'):
            full_stmt = '\n'.join(current_stmt).strip()
            if full_stmt and not full_stmt.startswith('--'):
                # Remove trailing semicolon for execution
                statements.append(full_stmt.rstrip(';'))
            current_stmt = []
    
    # Execute each statement
    for stmt in statements:
        stmt = stmt.strip()
        if stmt:
            try:
                await conn.execute(stmt)
            except Exception as e:
                # Log but continue - likely "already exists" errors
                error_msg = str(e).lower()
                if 'already exists' in error_msg or 'duplicate' in error_msg:
                    pass  # Expected for idempotent migrations
                else:
                    print(f"  ⚠️  Statement warning: {e}")
    
    # Record migration as applied
    await conn.execute(
        "INSERT INTO schema_migrations (version, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
        version, filename
    )
    
    return True


async def run_migrations():
    """Run all pending migrations."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        print("❌ DATABASE_URL not set!")
        sys.exit(1)
    
    # Convert to async URL
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    # Remove sslmode from URL (handled via connect_args)
    if 'sslmode=' in db_url:
        import re
        db_url = re.sub(r'[?&]sslmode=[^&]*', '', db_url)
    
    print("🔄 Connecting to database...")
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"ssl": "require"} if 'digitalocean' in db_url else {}
    )
    
    async with engine.begin() as conn:
        # Ensure tracking table exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Get already-applied migrations
        result = await conn.execute(text("SELECT version FROM schema_migrations"))
        applied = {row[0] for row in result.fetchall()}
        
        print(f"📋 Found {len(applied)} previously applied migrations")
        
        # Run pending migrations
        pending = [(v, f) for v, f in MIGRATIONS if v not in applied]
        
        if not pending:
            print("✅ All migrations already applied!")
        else:
            print(f"🚀 Running {len(pending)} pending migrations...")
            
            for version, filename in pending:
                print(f"  → Applying {version}: {filename}")
                
                filepath = MIGRATIONS_DIR / filename
                if not filepath.exists():
                    print(f"    ⚠️  File not found, skipping")
                    continue
                
                with open(filepath, 'r') as f:
                    sql_content = f.read()
                
                # Split and execute statements
                for stmt in sql_content.split(';'):
                    stmt = stmt.strip()
                    # Skip empty statements and pure comments
                    if stmt and not all(line.strip().startswith('--') or not line.strip() for line in stmt.split('\n')):
                        try:
                            await conn.execute(text(stmt))
                        except Exception as e:
                            error_msg = str(e).lower()
                            if 'already exists' in error_msg or 'duplicate' in error_msg:
                                pass  # Expected
                            else:
                                print(f"    ⚠️  {e}")
                
                # Record as applied
                await conn.execute(
                    text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n) ON CONFLICT DO NOTHING"),
                    {"v": version, "n": filename}
                )
                print(f"    ✓ Applied")
            
            print("✅ Migrations complete!")
    
    await engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  Database Migration Runner")
    print("=" * 60)
    asyncio.run(run_migrations())

