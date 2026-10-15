#!/usr/bin/env python3
"""Fail-closed, tenant-scoped durable-state comparison for PQ-HITL-03.

This tool NEVER changes PostgreSQL data. It samples only the protected
synthetic tenant using the existing read-only account and RLS GUC, hashes
database rows INSIDE PostgreSQL, and keeps keyed table digests exclusively
in GitHub runner temporary files. It cannot prove that transient writes,
unscoped/global tables, or external side effects did not occur. Consequently
this evidence does NOT authorize a Next Server Action or G0 acceptance.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ASYNCPG = "postgresql+asyncpg://"
# A narrow, preauthorized synthetic project. Tenant is supplied by protected
# workflow secrets and checked against the synthetic project before scanning.
PROJECT_ID = UUID("e7c6031f-cd9e-4642-a5ea-35a0207ceaeb")
REQUIRED_TABLES = {
    "projects",
    "documents",
    "document_revisions",
    "document_artifacts",
    "clauses",
    "project_events",
}
MAX_TABLES = 200
MAX_ROWS_PER_TABLE = 50_000


class AttestationFailure(Exception):
    """Only an operational reason code is safe to expose to CI logs."""


def _pg_url(raw: str) -> str:
    if raw.startswith(ASYNCPG):
        return raw
    if raw.startswith("postgresql://"):
        return ASYNCPG + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        return ASYNCPG + raw[len("postgres://") :]
    raise AttestationFailure("INVALID_DATABASE_SCHEME")


def _quoted(name: str) -> str:
    """Identifiers MUST come exclusively from the trusted DB catalog."""
    return '"' + name.replace('"', '""') + '"'


def _runner_file(raw: str) -> Path:
    """Never place attestation secrets or digests in the repository/artifact."""
    temp = os.getenv("RUNNER_TEMP")
    if not temp:
        raise AttestationFailure("RUNNER_TEMP_MISSING")
    root = Path(temp).resolve()
    path = Path(raw).resolve()
    if not path.is_relative_to(root) or path == root:
        raise AttestationFailure("SNAPSHOT_PATH_OUTSIDE_RUNNER_TEMP")
    return path


async def _snapshot(tenant: UUID, key: bytes) -> dict[str, object]:
    url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY", "")
    if not url or os.getenv("PROD_ACCEPTANCE_TENANT_PREFLIGHT_VERIFIED") != "1":
        raise AttestationFailure("PROTECTED_TENANT_PREFLIGHT_MISSING")
    if os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID") != str(tenant):
        raise AttestationFailure("TENANT_SCOPE_MISMATCH")
    engine = create_async_engine(_pg_url(url), pool_size=1, max_overflow=0)
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(text("SET LOCAL statement_timeout = '30000ms'"))
                await conn.execute(text("SET LOCAL lock_timeout = '3000ms'"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": str(tenant)},
                )
                security = await conn.execute(
                    text(
                        "SELECT rolbypassrls, rolsuper "
                        "FROM pg_roles WHERE rolname = current_user"
                    )
                )
                role = security.one()
                if bool(role.rolbypassrls) or bool(role.rolsuper):
                    raise AttestationFailure("VERIFIER_ROLE_BYPASSES_RLS")

                scope = await conn.execute(
                    text(
                        "SELECT count(*) FROM projects "
                        "WHERE id = :project_id AND tenant_id = :tenant_id "
                        "AND name LIKE 'ACCEPT-706-%'"
                    ),
                    {"project_id": PROJECT_ID, "tenant_id": tenant},
                )
                if scope.scalar_one() != 1:
                    raise AttestationFailure("SYNTHETIC_PROJECT_NOT_BOUND")

                # information_schema is privilege-filtered. Required product
                # tables must be visible, otherwise FAIL; never skip silently.
                discovery = await conn.execute(
                    text(
                        "SELECT DISTINCT c.table_name "
                        "FROM information_schema.columns AS c "
                        "JOIN information_schema.tables AS t "
                        "ON t.table_schema = c.table_schema "
                        "AND t.table_name = c.table_name "
                        "WHERE c.table_schema = 'public' "
                        "AND c.column_name = 'tenant_id' "
                        "AND t.table_type = 'BASE TABLE' "
                        "ORDER BY c.table_name"
                    )
                )
                names = [row.table_name for row in discovery]
                if len(names) > MAX_TABLES or not REQUIRED_TABLES.issubset(names):
                    raise AttestationFailure("TENANT_TABLE_COVERAGE_UNVERIFIED")

                output: dict[str, dict[str, object]] = {}
                for table in names:
                    # SQL digest only: no contract rows leave PostgreSQL.
                    sql = text(
                        "SELECT encode(sha256(convert_to(row_to_json(t)::text, "
                        "'UTF8')), 'hex') AS row_digest "
                        "FROM public." + _quoted(table) + " AS t "
                        "WHERE t.tenant_id = :tenant_id"
                    )
                    result = await conn.stream(sql, {"tenant_id": tenant})
                    digests: list[str] = []
                    async for row in result:
                        digests.append(row.row_digest)
                        if len(digests) > MAX_ROWS_PER_TABLE:
                            raise AttestationFailure("TENANT_SNAPSHOT_EXCEEDS_LIMIT")
                    digest_input = (table + "\n" + "\n".join(sorted(digests))).encode()
                    output[table] = {
                        "count": len(digests),
                        "hmac": hmac.new(key, digest_input, hashlib.sha256).hexdigest(),
                    }

                # Tenants lack tenant_id; include its isolated metadata row.
                tenant_result = await conn.execute(
                    text(
                        "SELECT encode(sha256(convert_to(row_to_json(t)::text, "
                        "'UTF8')), 'hex') FROM tenants t WHERE t.id = :tenant"
                    ),
                    {"tenant": tenant},
                )
                tenant_digests = [x[0] for x in tenant_result]
                if len(tenant_digests) != 1:
                    raise AttestationFailure("TENANT_RECORD_NOT_VISIBLE")
                output["__synthetic_tenant__"] = {
                    "count": 1,
                    "hmac": hmac.new(
                        key, tenant_digests[0].encode(), hashlib.sha256
                    ).hexdigest(),
                }
                await transaction.rollback()
                return {
                    "scope": "tenant_visible_rows_plus_tenant_record",
                    "table_count": len(output),
                    "tables": output,
                }
            except Exception:
                await transaction.rollback()
                raise
    finally:
        await engine.dispose()


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("before", "after"))
    p.add_argument("--baseline", required=True)
    p.add_argument("--key-file", required=True)
    args = p.parse_args()
    try:
        baseline = _runner_file(args.baseline)
        key_file = _runner_file(args.key_file)
        tenant = UUID(os.environ["PROD_ACCEPTANCE_EXPECTED_TENANT_ID"])
        if args.mode == "before":
            if baseline.exists() or key_file.exists():
                raise AttestationFailure("SNAPSHOT_ALREADY_EXISTS")
            key = secrets.token_bytes(32)
            snapshot = asyncio.run(_snapshot(tenant, key))
            _write_private(key_file, key)
            _write_private(
                baseline, json.dumps(snapshot, sort_keys=True).encode("utf-8")
            )
            print("PQ939_TENANT_DURABLE_SNAPSHOT_BASELINE: CAPTURED (read-only)")
        else:
            key = key_file.read_bytes()
            if len(key) != 32:
                raise AttestationFailure("INVALID_SNAPSHOT_KEY")
            before = json.loads(baseline.read_text(encoding="utf-8"))
            after = asyncio.run(_snapshot(tenant, key))
            if not hmac.compare_digest(
                hashlib.sha256(json.dumps(before, sort_keys=True).encode()).digest(),
                hashlib.sha256(json.dumps(after, sort_keys=True).encode()).digest(),
            ):
                raise AttestationFailure("TENANT_DURABLE_STATE_CHANGED_OR_COVERAGE_CHANGED")
            print("PQ939_TENANT_VISIBLE_DURABLE_STATE: UNCHANGED (read-only)")
            print("PQ939_OTHER_DATABASE_OR_TRANSIENT_EFFECTS: NOT_VERIFIED")
        return 0
    except (AttestationFailure, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        reason = str(exc) if isinstance(exc, AttestationFailure) else type(exc).__name__
        print(f"PQ939_TENANT_ATTESTATION_FAIL: {reason}", file=sys.stderr)
        return 2
    except Exception as exc:
        # NEVER show SQL/URL/credentials/raw row content in errors.
        print(
            f"PQ939_TENANT_ATTESTATION_FAIL: INTERNAL_{type(exc).__name__}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
