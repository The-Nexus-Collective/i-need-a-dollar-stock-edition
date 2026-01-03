#!/usr/bin/env python3
"""
Database Migration Runner with Version Tracking

Features:
- Tracks applied migrations in schema_migrations table
- Only runs pending migrations
- Runs each statement independently (no cascading failures)
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
    ("007", "007_agentic_system.sql"),
    ("008", "008_swarm.sql"),
    ("009", "009_trading_engine.sql"),
    ("010", "010_simple_trader.sql"),
    ("011", "011_add_trading_costs.sql"),
]


def parse_sql_statements(sql_content: str) -> list:
    """
    Parse SQL content into individual executable statements.
    Handles multi-line statements and comments.
    """
    statements = []
    current_stmt = []
    in_dollar_quote = False
    
    lines = sql_content.split('\n')
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines at statement boundaries
        if not stripped and not current_stmt:
            continue
        
        # Skip pure comment lines at statement boundaries
        if stripped.startswith('--') and not current_stmt:
            continue
        
        # Track $$ blocks (functions, triggers)
        if '$$' in line:
            count = line.count('$$')
            if count % 2 == 1:  # Odd number means toggle
                in_dollar_quote = not in_dollar_quote
        
        current_stmt.append(line)
        
        # Check for statement terminator (only if not in $$ block)
        if stripped.endswith(';') and not in_dollar_quote:
            full_stmt = '\n'.join(current_stmt).strip()
            # Remove trailing semicolon for asyncpg
            full_stmt = full_stmt.rstrip(';').strip()
            
            # Skip empty or comment-only statements
            non_comment_lines = [l for l in full_stmt.split('\n') 
                               if l.strip() and not l.strip().startswith('--')]
            
            if non_comment_lines:
                statements.append(full_stmt)
            
            current_stmt = []
    
    # Handle any remaining statement
    if current_stmt:
        full_stmt = '\n'.join(current_stmt).strip().rstrip(';').strip()
        non_comment_lines = [l for l in full_stmt.split('\n') 
                           if l.strip() and not l.strip().startswith('--')]
        if non_comment_lines:
            statements.append(full_stmt)
    
    return statements


async def run_migrations():
    """Run all pending migrations with independent statement execution."""
    import asyncpg
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        print("❌ DATABASE_URL not set!")
        sys.exit(1)
    
    print(f"📌 Database URL prefix: {db_url[:30]}...")
    
    # Parse the connection string for asyncpg
    # Format: postgresql://user:password@host:port/database?sslmode=require
    if db_url.startswith('postgresql://'):
        db_url_clean = db_url
    else:
        print(f"❌ Unexpected URL format: {db_url[:20]}...")
        sys.exit(1)
    
    # Detect if we need SSL
    use_ssl = 'digitalocean' in db_url.lower() or 'ondigitalocean' in db_url.lower()
    
    print("🔄 Connecting to database...")
    print(f"   SSL: {'enabled' if use_ssl else 'disabled'}")
    
    try:
        # Use asyncpg directly for better control
        conn = await asyncpg.connect(
            db_url_clean,
            ssl='require' if use_ssl else None
        )
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)
    
    print("✅ Connected to database!")
    
    try:
        # Ensure tracking table exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(50) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                applied_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        print("📋 Migration tracking table ready")
        
        # Get already-applied migrations
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        applied = {row['version'] for row in rows}
        
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
                    try:
                        # Execute each statement independently
                        await conn.execute(stmt)
                        success_count += 1
                    except Exception as e:
                        error_msg = str(e).lower()
                        # These are expected and OK
                        if any(msg in error_msg for msg in [
                            'already exists',
                            'duplicate',
                            'does not exist',  # DROP IF EXISTS
                            'nothing to alter',
                        ]):
                            skip_count += 1
                        else:
                            error_count += 1
                            # Show first 80 chars of statement
                            stmt_preview = stmt[:80].replace('\n', ' ')
                            print(f"    ⚠️  Statement {i}: {stmt_preview}...")
                            print(f"        Error: {str(e)[:150]}")
                
                print(f"    📊 Results: {success_count} applied, {skip_count} skipped, {error_count} errors")
                
                # Record migration as applied
                await conn.execute(
                    "INSERT INTO schema_migrations (version, name) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    version, filename
                )
                print(f"    ✓ Migration {version} recorded")
            
            print("\n✅ Migrations complete!")
    
    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await conn.close()
        print("🔌 Database connection closed")


async def verify_schema():
    """Verify critical columns exist after migration."""
    import asyncpg
    
    db_url = os.getenv('DATABASE_URL', '')
    if not db_url:
        return
    
    use_ssl = 'digitalocean' in db_url.lower() or 'ondigitalocean' in db_url.lower()
    
    try:
        conn = await asyncpg.connect(db_url, ssl='require' if use_ssl else None)
    except:
        return
    
    print("\n🔍 Verifying schema...")
    
    critical_checks = [
        ("positions", "id"),
        ("positions", "leverage"),
        ("positions", "liquidation_price"),
        ("positions", "margin_required"),
        ("trades", "id"),
        ("trades", "mode"),
        ("trades", "simulated_slippage"),
        ("signals", "id"),
        ("portfolio_snapshots", "timestamp"),
        ("account_state", "account_id"),  # Primary key is account_id, not id
    ]
    
    try:
        for table, column in critical_checks:
            result = await conn.fetchrow("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = $1 AND column_name = $2
            """, table, column)
            exists = result is not None
            status = "✅" if exists else "❌"
            print(f"   {status} {table}.{column}")
    except Exception as e:
        print(f"   ⚠️  Verification error: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("🗄️  Database Migration Runner")
    print("=" * 60)
    asyncio.run(run_migrations())
    asyncio.run(verify_schema())
