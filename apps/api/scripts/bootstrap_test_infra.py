"""Canonical bootstrap for local/CI test infrastructure."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import psycopg

from verify_migration_health import parse_migration_graph, validate_linear_chain


def is_port_open(host: str, port: int, timeout_seconds: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_seconds)
        return sock.connect_ex((host, port)) == 0


def wait_for_port(host: str, port: int, timeout_seconds: int) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_port_open(host, port):
            return True
        time.sleep(1)
    return False


def run_command(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def start_postgres_with_docker_compose(root: Path) -> None:
    run_command(["docker", "compose", "-f", "docker-compose.test.yml", "up", "-d", "postgres-test"], cwd=root)


def start_redis_with_docker_compose(root: Path) -> None:
    run_command(["docker", "compose", "-f", "docker-compose.test.yml", "up", "-d", "redis-test"], cwd=root)


def ensure_database_exists(admin_url: str, database_name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database_name,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{database_name}"')


def run_alembic_upgrade(api_dir: Path, database_url: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=str(api_dir), env=env, check=True)


def assert_head_revision(database_url: str, api_dir: Path) -> str:
    versions_dir = api_dir / "alembic" / "versions"
    nodes, _ = parse_migration_graph(versions_dir)
    expected_head = validate_linear_chain(nodes)

    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version_num FROM alembic_version")
            row = cur.fetchone()
            if not row:
                raise RuntimeError("alembic_version table is missing rows.")
            applied = row[0]
            if applied != expected_head:
                raise RuntimeError(f"Alembic head mismatch. expected={expected_head}, applied={applied}")
    return expected_head


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", type=int, default=5433)
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument(
        "--database-url",
        default="postgresql://postgres:postgres@localhost:5433/c2pro_test",
    )
    parser.add_argument(
        "--admin-url",
        default="postgresql://postgres:postgres@localhost:5433/postgres",
    )
    parser.add_argument("--database-name", default="c2pro_test")
    parser.add_argument("--start-services", action="store_true")
    parser.add_argument("--wait-seconds", type=int, default=45)
    parser.add_argument("--require-redis", action="store_true")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[3]
    api_dir = repo_root / "apps" / "api"

    print("== Preflight: DB port ==")
    if not is_port_open(args.db_host, args.db_port):
        if args.start_services:
            print("DB port closed. Starting postgres-test via docker compose...")
            try:
                start_postgres_with_docker_compose(repo_root)
            except Exception as exc:
                raise RuntimeError(f"Failed to start postgres-test with docker compose: {exc}") from exc
            if not wait_for_port(args.db_host, args.db_port, args.wait_seconds):
                raise RuntimeError(f"DB port {args.db_host}:{args.db_port} did not become reachable.")
        else:
            raise RuntimeError(
                f"DB port {args.db_host}:{args.db_port} is not reachable. "
                "Use --start-services or start test DB manually."
            )
    print(f"OK DB port reachable: {args.db_host}:{args.db_port}")

    print("== Preflight: Ensure DB exists ==")
    ensure_database_exists(args.admin_url, args.database_name)
    print(f"OK DB exists: {args.database_name}")

    print("== Apply migrations ==")
    run_alembic_upgrade(api_dir, args.database_url)
    head = assert_head_revision(args.database_url, api_dir)
    print(f"OK migrations at head: {head}")

    print("== Preflight: Redis ==")
    redis_ok = is_port_open(args.redis_host, args.redis_port)
    if not redis_ok and args.start_services:
        print("Redis port closed. Starting redis-test via docker compose...")
        try:
            start_redis_with_docker_compose(repo_root)
        except Exception as exc:
            raise RuntimeError(f"Failed to start redis-test with docker compose: {exc}") from exc
        redis_ok = wait_for_port(args.redis_host, args.redis_port, args.wait_seconds)

    if redis_ok:
        print(f"OK Redis reachable: {args.redis_host}:{args.redis_port}")
    elif args.require_redis:
        raise RuntimeError(
            f"Redis not reachable at {args.redis_host}:{args.redis_port} and --require-redis is set."
        )
    else:
        print(
            f"WARN Redis not reachable at {args.redis_host}:{args.redis_port}. "
            "Continuing (soft fail policy)."
        )

    print("== Test infra bootstrap complete ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
