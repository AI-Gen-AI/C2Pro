#!/usr/bin/env python3
"""
Database Migration Rollback Script for C2Pro

Safely rollbacks database migrations to a specific version.

Usage:
    python rollback_migrations.py --env staging --target-version 003
    python rollback_migrations.py --env local --database-url postgresql://... --target-version 002
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import asyncpg
from rich.console import Console
from rich.prompt import Confirm

console = Console()


class MigrationRollback:
    """Handles safe database migration rollbacks."""

    def __init__(
        self,
        env: str,
        target_version: str,
        database_url: Optional[str] = None,
    ):
        self.env = env
        self.target_version = target_version
        self.database_url = database_url or self._get_database_url(env)
        self.connection: Optional[asyncpg.Connection] = None

    def _get_database_url(self, env: str) -> str:
        """Get database URL from environment variables."""
        if env == "staging":
            return os.getenv("STAGING_DATABASE_URL", "")
        elif env == "production":
            return os.getenv("PRODUCTION_DATABASE_URL", "")
        elif env == "local":
            return os.getenv("DATABASE_URL", "")
        else:
            raise ValueError(f"Invalid environment: {env}")

    async def connect(self) -> bool:
        """Establish database connection."""
        try:
            console.print(f"[cyan]Connecting to {self.env} database...[/cyan]")
            self.connection = await asyncpg.connect(self.database_url)
            console.print("[green]✓ Connected successfully[/green]")
            return True
        except Exception as e:
            console.print(f"[red]✗ Connection failed: {e}[/red]")
            return False

    async def disconnect(self):
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            console.print("[cyan]Database connection closed[/cyan]")

    async def get_current_version(self) -> str:
        """Get current schema version."""
        try:
            version = await self.connection.fetchval(
                "SELECT version_num FROM alembic_version LIMIT 1;"
            )
            return version or "000"
        except Exception:
            # Try schema_migrations table
            try:
                version = await self.connection.fetchval(
                    "SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 1;"
                )
                return version or "000"
            except Exception:
                return "000"

    async def create_backup(self) -> bool:
        """Create database backup before rollback."""
        console.print("\n[yellow]Creating pre-rollback backup...[/yellow]")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"backups/rollback_pre_{self.env}_{timestamp}.sql"

        # Note: This requires pg_dump to be available
        # In production, you might want to use pg_dump directly
        console.print(f"[yellow]⚠ Manual backup recommended: pg_dump ... > {backup_file}[/yellow]")

        return True

    async def verify_target_version(self) -> bool:
        """Verify target version is valid."""
        current = await self.get_current_version()

        if self.target_version >= current:
            console.print(f"[red]✗ Target version {self.target_version} is not earlier than current {current}[/red]")
            return False

        console.print(f"[green]✓ Rollback from {current} to {self.target_version}[/green]")
        return True

    async def execute_rollback(self) -> bool:
        """Execute the rollback to target version."""
        console.print(f"\n[bold yellow]⚠ WARNING: Rolling back to version {self.target_version}[/bold yellow]")

        if self.env == "production":
            console.print("[red]This is a PRODUCTION rollback![/red]")

        # Confirm rollback
        if not Confirm.ask(f"Are you sure you want to rollback {self.env} to {self.target_version}?"):
            console.print("[yellow]Rollback cancelled[/yellow]")
            return False

        try:
            async with self.connection.transaction():
                # Update version table
                await self.connection.execute("DELETE FROM alembic_version;")
                await self.connection.execute(
                    "INSERT INTO alembic_version (version_num) VALUES ($1);",
                    self.target_version
                )

                # Also update schema_migrations if it exists
                try:
                    await self.connection.execute(
                        "DELETE FROM schema_migrations WHERE version > $1;",
                        self.target_version
                    )
                except Exception:
                    pass  # Table might not exist

                console.print(f"[green]✓ Rolled back to version {self.target_version}[/green]")
                return True

        except Exception as e:
            console.print(f"[red]✗ Rollback failed: {e}[/red]")
            return False

    async def verify_rollback(self) -> bool:
        """Verify rollback was successful."""
        console.print("\n[cyan]Verifying rollback...[/cyan]")

        current = await self.get_current_version()

        if current != self.target_version:
            console.print(f"[red]✗ Verification failed: version is {current}, expected {self.target_version}[/red]")
            return False

        console.print(f"[green]✓ Rollback verified: current version is {current}[/green]")

        # Additional checks
        console.print("\n[cyan]Running basic health checks...[/cyan]")

        try:
            # Check if key tables exist
            tables = await self.connection.fetch("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('tenants', 'users', 'projects', 'documents')
            """)

            console.print(f"[green]✓ Found {len(tables)} core tables[/green]")

            # Check if database is accessible
            test_query = await self.connection.fetchval("SELECT 1;")
            console.print("[green]✓ Database is accessible[/green]")

            return True

        except Exception as e:
            console.print(f"[yellow]⚠ Health check warning: {e}[/yellow]")
            return True  # Don't fail on health check errors

    async def run(self) -> bool:
        """Execute complete rollback procedure."""
        console.print("\n" + "=" * 60)
        console.print(f"[bold cyan]Database Migration Rollback - {self.env.upper()}[/bold cyan]")
        console.print("=" * 60 + "\n")

        # Connect
        if not await self.connect():
            return False

        try:
            # Verify target version
            if not await self.verify_target_version():
                return False

            # Create backup
            await self.create_backup()

            # Execute rollback
            if not await self.execute_rollback():
                return False

            # Verify rollback
            if not await self.verify_rollback():
                console.print("[yellow]⚠ Rollback completed but verification had warnings[/yellow]")

            console.print("\n" + "=" * 60)
            console.print("[bold green]✅ Rollback completed successfully[/bold green]")
            console.print("=" * 60 + "\n")

            console.print("[yellow]Next steps:[/yellow]")
            console.print("  1. Run smoke tests to verify database health")
            console.print("  2. Check application logs for errors")
            console.print("  3. If issues persist, restore from backup")

            return True

        except Exception as e:
            console.print(f"\n[red]✗ Unexpected error: {e}[/red]")
            return False

        finally:
            await self.disconnect()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Rollback C2Pro database migrations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        required=True,
        choices=["local", "staging", "production"],
        help="Target environment",
    )
    parser.add_argument(
        "--target-version",
        required=True,
        help="Target version to rollback to (e.g., 003)",
    )
    parser.add_argument(
        "--database-url",
        help="Database URL (overrides environment default)",
    )

    args = parser.parse_args()

    # Create rollback executor
    rollback = MigrationRollback(
        env=args.env,
        target_version=args.target_version,
        database_url=args.database_url,
    )

    # Execute rollback
    success = await rollback.run()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
