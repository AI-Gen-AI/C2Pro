#!/usr/bin/env python3
"""
Environment Configuration Checker for C2Pro

Validates that all required environment variables are configured
for database migrations.

Usage:
    python check_env.py --env staging
    python check_env.py --env production
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()


def check_environment(env: str) -> bool:
    """
    Check environment configuration.

    Args:
        env: Environment name (local, staging, production)

    Returns:
        True if all checks pass, False otherwise
    """
    console.print(f"\n[bold cyan]Checking {env} environment configuration...[/bold cyan]\n")

    # Load environment file
    project_root = Path(__file__).parent.parent.parent
    if env == "local":
        env_file = project_root / ".env"
    else:
        env_file = project_root / f".env.{env}"

    if not env_file.exists():
        console.print(f"[red]✗[/red] Environment file not found: {env_file}")
        return False

    console.print(f"[green]✓[/green] Environment file found: {env_file}")
    load_dotenv(env_file)

    # Required variables
    required_vars = {
        "DATABASE_URL": "PostgreSQL connection string",
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_SERVICE_ROLE_KEY": "Supabase service role key",
    }

    # Check each variable
    results = []
    all_present = True

    for var_name, description in required_vars.items():
        value = os.getenv(var_name)
        is_present = bool(value)

        if is_present:
            # Mask sensitive values
            if "KEY" in var_name or "PASSWORD" in var_name:
                display_value = value[:10] + "..." if len(value) > 10 else "***"
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value

            results.append((var_name, description, "✓", display_value))
        else:
            results.append((var_name, description, "✗", "Not set"))
            all_present = False

    # Display results table
    table = Table(title=f"{env.upper()} Environment Variables")
    table.add_column("Variable", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Status", style="green")
    table.add_column("Value", style="yellow")

    for row in results:
        style = "green" if row[2] == "✓" else "red"
        table.add_row(*row, style=style)

    console.print(table)

    # Validate DATABASE_URL format
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        if not database_url.startswith("postgresql://") and not database_url.startswith("postgres://"):
            console.print("\n[yellow]⚠[/yellow] DATABASE_URL should start with 'postgresql://' or 'postgres://'")
            all_present = False

        # Check for required components
        if "@" not in database_url or "/" not in database_url:
            console.print("\n[red]✗[/red] DATABASE_URL appears to be malformed")
            all_present = False

    # Final result
    console.print()
    if all_present:
        console.print("[bold green]✅ All environment variables are configured[/bold green]")
        console.print(f"[green]Environment: {env}[/green]")
        return True
    else:
        console.print("[bold red]❌ Some environment variables are missing[/bold red]")
        console.print("[yellow]Please configure missing variables before running migrations[/yellow]")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Check C2Pro environment configuration")
    parser.add_argument(
        "--env",
        choices=["local", "staging", "production"],
        default="local",
        help="Environment to check",
    )

    args = parser.parse_args()

    success = check_environment(args.env)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
