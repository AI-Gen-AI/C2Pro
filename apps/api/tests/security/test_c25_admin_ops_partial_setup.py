"""Fault injection through the real gate setup and teardown orchestration."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import c25_admin_ops_gate as gate


class Cluster:
    """In-memory catalog at the psycopg boundary; DDL changes observable state."""

    def __init__(self, failure, preexisting):
        self.failure = failure
        self.roles = set(preexisting)
        self.databases = {"c25_admin_ops_gate"} if failure == "db_collision" else set()
        if failure == "login_collision":
            self.roles.add(f"c25_gate_app_{os.getpid()}")
        self.initial_roles = self.roles.copy()
        self.initial_databases = self.databases.copy()
        self.queries = []
        self.created = []
        self.injected = False
        self.result = []
        self.connections = 0

    def connect(self, *args, **kwargs):
        self.connections += 1
        if self.failure == "connect" and not self.injected:
            self.injected = True
            raise RuntimeError("injected connect")
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self.failure == "after_db" and not self.injected:
            self.injected = True
            raise RuntimeError("injected after_db")

    def execute(self, query, params=None):
        query = query if isinstance(query, str) else query.as_string()
        self.queries.append(query)
        triggers = {
            "snapshot": "rolname = 'c2pro_app'",
            "after_ops": "rolname = 'c25_gate_app_",
            "before_db": "CREATE DATABASE",
            "after_app": 'CREATE ROLE "c25_gate_admin_',
            "after_admin": "GRANT c2pro_admin_ops",
            "members": "SELECT r.rolname FROM pg_auth_members",
        }
        if not self.injected and self.failure in triggers and triggers[self.failure] in query:
            self.injected = True
            raise RuntimeError(f"injected {self.failure}")
        self.result = [(False,)]
        if "SELECT EXISTS" in query:
            catalog = self.databases if "pg_database" in query else self.roles
            self.result = [(any(f"'{name}'" in query for name in catalog),)]
        elif "SELECT rolsuper" in query:
            self.result = [(False,) * 5]
        elif "SELECT r.rolname" in query:
            self.result = []
        elif query.startswith("CREATE ROLE"):
            name = query.split()[2].strip('"')
            self.roles.add(name)
            self.created.append(name)
        elif query.startswith("DROP ROLE"):
            self.roles.discard(query.split()[-1].strip('"'))
        elif query.startswith("CREATE DATABASE"):
            name = query.split()[-1]
            self.databases.add(name)
            self.created.append(name)
        elif query.startswith("DROP DATABASE"):
            self.databases.discard(query.split()[-1])
        elif "SELECT current_database()" in query:
            self.result = [("c25_admin_ops_gate",)]
        return self

    def fetchone(self):
        return self.result[0]

    def fetchall(self):
        return self.result


class AsyncConnection:
    def __init__(self, cluster):
        self.cluster = cluster

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def execute(self, query):
        self.cluster.execute(query)
        result = AsyncMock()
        result.fetchone.return_value = self.cluster.fetchone()
        return result


@pytest.mark.asyncio
@pytest.mark.parametrize("preexisting_ops", [False, True])
@pytest.mark.parametrize(
    "failure,created_count",
    [
        ("connect", 0),
        ("snapshot", 0),
        ("after_ops", 0),
        ("before_db", 0),
        ("after_db", 1),
        ("after_app", 2),
        ("after_admin", 3),
        ("db_collision", 0),
        ("login_collision", 0),
    ],
)
async def test_partial_setup_cleans_only_owned_resources(
    monkeypatch, capsys, failure, created_count, preexisting_ops
):
    preexisting = {"c2pro_app", "c2pro_admin_login"}
    if preexisting_ops:
        preexisting.add("c2pro_admin_ops")
    cluster = Cluster(failure, preexisting)
    monkeypatch.setattr(
        gate, "_resolve_admin_dsn_impl", lambda _: "postgresql://localhost/postgres"
    )
    monkeypatch.setattr(gate.psycopg, "connect", cluster.connect)
    monkeypatch.setattr(gate, "_run_alembic_migrations", lambda _: None)
    pool = AsyncMock()
    pool.connection = lambda: AsyncConnection(cluster)
    monkeypatch.setattr(gate, "_connect", AsyncMock(return_value=pool))

    assert await gate.main() == 1

    output = capsys.readouterr().out
    if failure in {"db_collision", "login_collision"}:
        assert "already exists" in output
    else:
        assert cluster.injected
        assert f"GATE LIFECYCLE EXECUTION FAILURE: injected {failure}" in output
    assert "UnboundLocalError" not in output
    assert "NameError" not in output
    assert "HYGIENE FAILURE" not in output
    assert cluster.connections == 2, "teardown must connect even after partial setup"
    assert cluster.roles == cluster.initial_roles
    assert cluster.databases == cluster.initial_databases
    owned_ops = int(not preexisting_ops and failure not in {"connect", "snapshot"})
    assert len(cluster.created) == created_count + owned_ops
    if failure in {"after_app", "after_admin"}:
        pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_partial_membership_snapshot_preserves_existing_role(monkeypatch, capsys):
    cluster = Cluster("members", {"c2pro_app", "c2pro_admin_login", "c2pro_admin_ops"})
    monkeypatch.setattr(
        gate, "_resolve_admin_dsn_impl", lambda _: "postgresql://localhost/postgres"
    )
    monkeypatch.setattr(gate.psycopg, "connect", cluster.connect)
    assert await gate.main() == 1
    assert "GATE LIFECYCLE EXECUTION FAILURE: injected members" in capsys.readouterr().out
    assert cluster.connections == 2
    assert cluster.roles == cluster.initial_roles
    assert not any("DROP ROLE" in query for query in cluster.queries)
