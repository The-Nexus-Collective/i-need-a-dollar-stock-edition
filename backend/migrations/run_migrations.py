#!/usr/bin/env python3
"""
Database Migration Runner with Version Tracking

Features:
- Tracks applied migrations in schema_migrations table
- Only runs pending migrations
- Robust multi-statement SQL parsing
- Detailed logging and error handling
"""

import asyncio
import os
import sys
import re
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


def parse_sql_statements(sql_content: str) -> list:
    """
    Parse SQL content into individual executable statements.
    Handles:
    - Multi-line statements
    - Comments (-- and /* */)
    - CREATE FUNCTION/VIEW/TABLE with internal semicolons
    - Empty statements
    """
    statements = []
    current_stmt = []
    in_block = False  # Track if we're inside a function/view definition
    
    lines = sql_content.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            if current_stmt:  # Preserve empty lines within statements
                current_stmt.append(line)
            continue
        
        # Skip pure comment lines (but keep comments within statements)
        if stripped.startswith('--') and not current_stmt:
            continue
        
        # Track BEGIN/END for function definitions
        if 'CREATE OR REPLACE VIEW' in stripped.upper() or \
           'CREATE VIEW' in stripped.upper() or \
           'CREATE OR REPLACE FUNCTION' in stripped.upper() or \
           'CREATE FUNCTION' in stripped.upper():
            in_block = True
        
        current_stmt.append(line)
        
        # Check for statement terminator
        if stripped.endswith(';'):
            # For views/functions, wait for proper end
            if in_block and 'AS' in ''.join(current_stmt).upper():
                # Check if this is the final statement of a CREATE VIEW/FUNCTION
                full_text = '\n'.join(current_stmt).upper()
                # Simple heuristic: balanced AS ... ; for views
                if 'CREATE' in full_text and 'VIEW' in full_text:
                    in_block = False
            else:
                in_block = False
            
            if not in_block:
                full_stmt = '\n'.join(current_stmt).strip()
                # Remove the trailing semicolon for asyncpg
                full_stmt = full_stmt.rstrip(';').strip()
                
                if full_stmt and not full_stmt.startswith('--'):
                    statements.append(full_stmt)
                current_stmt = []
    
    # Handle any remaining statement without trailing semicolon
    if current_stmt:
        full_stmt = '\n'.join(current_stmt).strip().rstrip(';').strip()
        if full_stmt and not full_stmt.startswith('--'):
            statements.append(full_stmt)
    
    return statements


async def run_migrations():
    """Run all pending migrations."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        print("❌ DATABASE_URL not set!")
        sys.exit(1)
    
    print(f"📌 Database URL prefix: {db_url[:30]}...")
    
    # Convert to async URL
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    # Remove sslmode from URL (handled via connect_args)
    if 'sslmode=' in db_url:
        db_url = re.sub(r'[?&]sslmode=[^&]*', '', db_url)
        # Clean up any double ? or trailing ?
        db_url = db_url.replace('??', '?').rstrip('?')
    
    # Detect if we need SSL
    use_ssl = 'digitalocean' in db_url.lower() or 'ondigitalocean' in db_url.lower()
    
    print("🔄 Connecting to database...")
    print(f"   SSL: {'enabled' if use_ssl else 'disabled'}")
    
    try:
        engine = create_async_engine(
            db_url,
            echo=False,
            connect_args={"ssl": "require"} if use_ssl else {}
        )
    except Exception as e:
        print(f"❌ Failed to create engine: {e}")
        sys.exit(1)
    
    try:
        async with engine.begin() as conn:
            print("✅ Connected to database!")
            
            # Ensure tracking table exists
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(50) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            print("📋 Migration tracking table ready")
            
            # Get already-applied migrations
            result = await conn.execute(text("SELECT version FROM schema_migrations ORDER BY version"))
            applied = {row[0] for row in result.fetchall()}
            
            print(f"📋 Previously applied: {sorted(applied) if applied else 'none'}")
            
            # Determine pending migrations
            pending = [(v, f) for v, f in MIGRATIONS if v not in applied]
            
            if not pending:
                print("✅ All migrations already applied!")
            else:
                print(f"🚀 Running {len(pending)} pending migrations...")
                
                for version, filename in pending:
                    print(f"\n  ─────────────────────────────────────")
                    print(f"  → Applying {version}: {filename}")
                    
                    filepath = MIGRATIONS_DIR / filename
                    if not filepath.exists():
                        print(f"    ⚠️  File not found: {filepath}")
                        continue
                    
                    with open(filepath, 'r') as f:
                        sql_content = f.read()
                    
                    # Parse into individual statements
                    statements = parse_sql_statements(sql_content)
                    print(f"    📄 Found {len(statements)} statements")
                    
                    success_count = 0
                    skip_count = 0
                    error_count = 0
                    
                    for i, stmt in enumerate(statements, 1):
                        # Skip empty or comment-only statements
                        clean_stmt = '\n'.join(
                            line for line in stmt.split('\n') 
                            if line.strip() and not line.strip().startswith('--')
                        ).strip()
                        
                        if not clean_stmt:
                            skip_count += 1
                            continue
                        
                        try:
                            await conn.execute(text(clean_stmt))
                            success_count += 1
                        except Exception as e:
                            error_msg = str(e).lower()
                            # These are expected and OK
                            if any(msg in error_msg for msg in [
                                'already exists',
                                'duplicate',
                                'does not exist' if 'drop' in clean_stmt.lower() else 'NEVER_MATCH'
                            ]):
                                skip_count += 1
                            else:
                                error_count += 1
                                # Show first 100 chars of statement
                                stmt_preview = clean_stmt[:100].replace('\n', ' ')
                                print(f"    ⚠️  Statement {i}: {stmt_preview}...")
                                print(f"        Error: {str(e)[:200]}")
                    
                    print(f"    📊 Results: {success_count} applied, {skip_count} skipped, {error_count} errors")
                    
                    # Record migration as applied (even with errors, to prevent re-runs)
                    await conn.execute(
                        text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n) ON CONFLICT DO NOTHING"),
                        {"v": version, "n": filename}
                    )
                    print(f"    ✓ Migration {version} recorded")
                
                print("\n✅ Migrations complete!")
    
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await engine.dispose()
        print("🔌 Database connection closed")


async def verify_schema():
    """Verify critical columns exist after migration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        return
    
    if db_url.startswith('postgresql://'):
        db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://')
    
    if 'sslmode=' in db_url:
        db_url = re.sub(r'[?&]sslmode=[^&]*', '', db_url).rstrip('?')
    
    use_ssl = 'digitalocean' in db_url.lower() or 'ondigitalocean' in db_url.lower()
    
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"ssl": "require"} if use_ssl else {}
    )
    
    print("\n🔍 Verifying schema...")
    
    critical_checks = [
        ("positions", "leverage"),
        ("positions", "liquidation_price"),
        ("positions", "margin_required"),
        ("trades", "mode"),
        ("trades", "simulated_slippage"),
    ]
    
    try:
        async with engine.begin() as conn:
            for table, column in critical_checks:
                result = await conn.execute(text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = :table AND column_name = :column
                """), {"table": table, "column": column})
                exists = result.fetchone() is not None
                status = "✅" if exists else "❌"
                print(f"   {status} {table}.{column}")
    except Exception as e:
        print(f"   ⚠️  Verification error: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  Database Migration Runner")
    print("=" * 60)
    asyncio.run(run_migrations())
    asyncio.run(verify_schema())

