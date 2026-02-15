"""Validate Alembic migration chain and rehearse clean upgrade on a fresh database."""

from __future__ import annotations

import argparse
import ast
import os
import subprocess
import sys
from pathlib import Path

import psycopg


def parse_migration_graph(versions_dir: Path) -> tuple[dict[str, str | None], list[str]]:
    nodes: dict[str, str | None] = {}
    files: list[str] = []

    for path in sorted(versions_dir.glob("*.py")):
        module = ast.parse(path.read_text(encoding="utf-8"))
        values: dict[str, str | None] = {}

        for stmt in module.body:
            target_name: str | None = None
            value_node: ast.expr | None = None

            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                target_name = stmt.targets[0].id
                value_node = stmt.value
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                target_name = stmt.target.id
                value_node = stmt.value

            if target_name not in {"revision", "down_revision"} or value_node is None:
                continue

            if isinstance(value_node, ast.Constant):
                values[target_name] = value_node.value if isinstance(value_node.value, str) else None
            else:
                values[target_name] = None

        revision = values.get("revision")
        if not revision:
            continue

        down_revision = values.get("down_revision")

        nodes[revision] = down_revision
        files.append(path.name)

    return nodes, files


def validate_linear_chain(nodes: dict[str, str | None]) -> str:
    if not nodes:
        raise RuntimeError("No Alembic revisions found.")

    roots = [rev for rev, down in nodes.items() if down is None]
    if len(roots) != 1:
        raise RuntimeError(f"Expected exactly one root revision, found {len(roots)}: {roots}")

    children: dict[str, list[str]] = {}
    for rev, down in nodes.items():
        if down is None:
            continue
        children.setdefault(down, []).append(rev)

    branches = {parent: kids for parent, kids in children.items() if len(kids) > 1}
    if branches:
        raise RuntimeError(f"Branching migration graph detected: {branches}")

    # Head is revision that is not referenced as down_revision by any other node.
    referenced = {down for down in nodes.values() if down is not None}
    heads = [rev for rev in nodes if rev not in referenced]
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one head revision, found {len(heads)}: {heads}")

    # Walk from head to root to ensure no broken link.
    current = heads[0]
    visited: set[str] = set()
    while current is not None:
        if current in visited:
            raise RuntimeError(f"Cycle detected at revision {current}")
        visited.add(current)
        current = nodes.get(current)

    if len(visited) != len(nodes):
        missing = set(nodes) - visited
        raise RuntimeError(f"Disconnected revisions detected: {sorted(missing)}")

    return heads[0]


def recreate_database(admin_url: str, database_name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
                """,
                (database_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
            cur.execute(f'CREATE DATABASE "{database_name}"')


def run_alembic_upgrade(api_dir: Path, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    subprocess.run(cmd, cwd=str(api_dir), env=env, check=True)


def assert_applied_head(database_url: str, expected_head: str) -> None:
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            if not row:
                raise RuntimeError("No alembic_version row found after upgrade.")
            applied = row[0]
            if applied != expected_head:
                raise RuntimeError(f"Applied head {applied} does not match expected {expected_head}.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default="postgresql://postgres:postgres@localhost:5433/c2pro_test",
        help="Target database URL for migration rehearsal.",
    )
    parser.add_argument(
        "--admin-url",
        default="postgresql://postgres:postgres@localhost:5433/postgres",
        help="Admin database URL used to create/drop target database.",
    )
    parser.add_argument(
        "--recreate-db",
        action="store_true",
        help="Drop and recreate target database before upgrade rehearsal.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    versions_dir = root / "alembic" / "versions"

    nodes, files = parse_migration_graph(versions_dir)
    head = validate_linear_chain(nodes)
    print(f"OK migration graph: {len(files)} files, head={head}")

    db_name = args.database_url.rsplit("/", 1)[-1]
    if args.recreate_db:
        recreate_database(args.admin_url, db_name)
        print(f"OK recreated database: {db_name}")

    run_alembic_upgrade(root, args.database_url)
    print("OK alembic upgrade head")

    assert_applied_head(args.database_url, head)
    print("OK alembic_version matches expected head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
