#!/usr/bin/env python3
"""
Quick database state checker for CE-20
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def check_database_state():
    # Load environment
    load_dotenv('.env.staging')
    database_url = os.getenv('DATABASE_URL')

    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    print(f"Connecting to database...")
    print(f"URL: {database_url[:50]}...")

    try:
        # statement_cache_size=0 for pgbouncer compatibility
        conn = await asyncpg.connect(database_url, statement_cache_size=0)
        print("[OK] Connected successfully\n")

        # Check schema version
        print("--- Schema Version ---")
        try:
            result = await conn.fetch('SELECT * FROM alembic_version;')
            if result:
                for row in result:
                    print(f"Current version: {row['version_num']}")
            else:
                print("No version found (alembic_version table empty)")
        except Exception as e:
            print(f"Note: {e}")

        # Count tables
        print("\n--- Table Count ---")
        result = await conn.fetchrow('''
            SELECT COUNT(*) as table_count
            FROM information_schema.tables
            WHERE table_schema = 'public';
        ''')
        print(f"Tables: {result['table_count']}")

        # Count RLS policies
        print("\n--- RLS Policies ---")
        result = await conn.fetchrow('''
            SELECT COUNT(*) as policy_count
            FROM pg_policies
            WHERE schemaname = 'public';
        ''')
        print(f"RLS Policies: {result['policy_count']}")

        # Count foreign keys
        print("\n--- Foreign Keys ---")
        result = await conn.fetchrow('''
            SELECT COUNT(*) as fk_count
            FROM information_schema.table_constraints
            WHERE constraint_type = 'FOREIGN KEY'
            AND table_schema = 'public';
        ''')
        print(f"Foreign Keys: {result['fk_count']}")

        # Check applied migrations
        print("\n--- Applied Migrations ---")
        try:
            results = await conn.fetch('''
                SELECT version, applied_at
                FROM schema_migrations
                ORDER BY version;
            ''')
            if results:
                for row in results:
                    print(f"  {row['version']} - {row['applied_at']}")
            else:
                print("  (no migrations applied yet)")
        except Exception as e:
            print(f"  Note: {e}")

        # List all tables
        print("\n--- Tables in Public Schema ---")
        results = await conn.fetch('''
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename;
        ''')
        for row in results:
            print(f"  - {row['tablename']}")

        await conn.close()
        print("\n[OK] Database check complete")

    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(check_database_state())
    exit(exit_code if exit_code else 0)
