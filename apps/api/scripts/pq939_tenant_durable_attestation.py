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
# Known project-only tables must be represented; absence is not a PASS.
# Canonical project_id-only RLS tables from the deployed schema migrations.
# A missing SELECT grant must fail coverage, not silently yield a clean snapshot.
REQUIRED_PROJECT_TABLES = {
    "extractions",
    "procurement_bom_items",
    "procurement_budget_items",
    "procurement_wbs_items",
    "bom_revisions",
    "knowledge_graph_edges",
    "knowledge_graph_nodes",
    "procurement_plan_snapshots",
    "stakeholder_alerts",
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



def _table_scope(has_tenant_id: bool, has_project_id: bool) -> str:
    if has_tenant_id:
        return "tenant_id"
    if has_project_id:
        return "project_id"
    raise AttestationFailure("UNSCOPED_TABLE")


def _coverage_error(
    scoped: list[tuple[str, str]],
    catalog: dict[str, tuple[bool, bool]],
) -> str | None:
    """Classify only schema/privilege coverage, never inspect or report DB rows.

    pg_catalog describes physical columns even when information_schema hides
    a table from a verifier without SELECT grants. A category failure never
    relaxes the mandatory required-table and project-scope guarantees.
    """
    if len(scoped) > MAX_TABLES:
        return "TOO_MANY_SCOPED_TABLES"

    required = REQUIRED_TABLES | REQUIRED_PROJECT_TABLES
    if not required.issubset(catalog):
        return "REQUIRED_TABLE_NOT_DEPLOYED"

    # Catalog scope is independent of SELECT grants. Diagnose absent
    # project/scope columns before a privilege-filtered missing-table result.
    if any(not catalog[name][1] for name in REQUIRED_PROJECT_TABLES):
        return "REQUIRED_PROJECT_COLUMN_MISSING"

    if any(not any(catalog[name]) for name in required):
        return "REQUIRED_SCOPE_COLUMN_MISSING"

    visible = dict(scoped)
    if not required.issubset(visible):
        return "REQUIRED_TABLE_NOT_VISIBLE_TO_VERIFIER"

    if any(visible[name] != "project_id" for name in REQUIRED_PROJECT_TABLES):
        return "REQUIRED_PROJECT_SCOPE_MISMATCH"

    return None


def _selectable_columns(
    access: list[tuple[str, bool]], scope_column: str
) -> tuple[list[str], int]:
    """Project only columns allowed by the verifier's exact SELECT grants."""
    allowed = [name for name, can_select in access if can_select]
    if scope_column not in allowed:
        raise AttestationFailure("SCOPE_COLUMN_NOT_SELECTABLE")
    return allowed, len(access) - len(allowed)


def _fingerprint_sql(table: str, columns: list[str], scope_column: str) -> str:
    """Hash a granted-column projection, never an unprivileged full row."""
    if scope_column not in {"tenant_id", "project_id", "id"}:
        raise AttestationFailure("INVALID_SCOPE_COLUMN")
    if not columns or scope_column not in columns:
        raise AttestationFailure("SCOPE_COLUMN_NOT_SELECTABLE")
    projection = ", ".join(
        f"t.{_quoted(column)} AS {_quoted(column)}" for column in columns
    )
    if scope_column == "tenant_id":
        predicate = 't."tenant_id" = :tenant_id'
    elif scope_column == "project_id":
        predicate = (
            't."project_id" IN (SELECT p.id FROM public.projects AS p '
            'WHERE p.tenant_id = :tenant_id)'
        )
    else:
        predicate = 't."id" = :tenant_id'
    return (
        "SELECT encode(sha256(convert_to(row_to_json(scoped)::text, "
        "'UTF8')), 'hex') AS row_digest FROM "
        f"(SELECT {projection} FROM public.{_quoted(table)} AS t "
        f"WHERE {predicate}) AS scoped"
    )


async def _catalog_access(conn, table: str, scope_column: str):
    """Verify SELECT grants via PostgreSQL catalog (including column grants)."""
    catalog = await conn.execute(
        text(
            "SELECT a.attname, "
            "has_column_privilege(current_user, a.attrelid, a.attname, 'SELECT') "
            "AS readable FROM pg_catalog.pg_attribute AS a "
            "WHERE a.attrelid = to_regclass(:table_name) "
            "AND a.attnum > 0 AND NOT a.attisdropped ORDER BY a.attnum"
        ),
        {"table_name": f"public.{_quoted(table)}"},
    )
    return _selectable_columns(
        [(row.attname, bool(row.readable)) for row in catalog], scope_column
    )


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

                # Include both direct tenant_id and indirect project_id tables.
                discovery = await conn.execute(
                    text(
                        "SELECT c.table_name, "
                        "bool_or(c.column_name = 'tenant_id') AS has_tenant_id, "
                        "bool_or(c.column_name = 'project_id') AS has_project_id "
                        "FROM information_schema.columns AS c "
                        "JOIN information_schema.tables AS t "
                        "ON t.table_schema = c.table_schema "
                        "AND t.table_name = c.table_name "
                        "WHERE c.table_schema = 'public' "
                        "AND c.column_name IN ('tenant_id', 'project_id') "
                        "AND t.table_type = 'BASE TABLE' "
                        "GROUP BY c.table_name ORDER BY c.table_name"
                    )
                )
                scoped = [
                    (
                        row.table_name,
                        _table_scope(bool(row.has_tenant_id), bool(row.has_project_id)),
                    )
                    for row in discovery
                ]
                # Independent schema metadata only: pg_catalog is not
                # privilege-filtered the same way as information_schema.
                # Keep every production row unread and never print identifiers.
                catalog_result = await conn.execute(
                    text(
                        "SELECT cls.relname AS table_name, "
                        "bool_or(attr.attname = 'tenant_id') AS has_tenant_id, "
                        "bool_or(attr.attname = 'project_id') AS has_project_id "
                        "FROM pg_catalog.pg_class AS cls "
                        "JOIN pg_catalog.pg_namespace AS ns ON ns.oid = cls.relnamespace "
                        "JOIN pg_catalog.pg_attribute AS attr "
                        "ON attr.attrelid = cls.oid "
                        "AND attr.attnum > 0 AND NOT attr.attisdropped "
                        "WHERE ns.nspname = 'public' "
                        "AND cls.relkind IN ('r', 'p') "
                        "GROUP BY cls.relname ORDER BY cls.relname"
                    )
                )
                catalog_scope = {
                    row.table_name: (
                        bool(row.has_tenant_id),
                        bool(row.has_project_id),
                    )
                    for row in catalog_result
                }
                coverage_error = _coverage_error(scoped, catalog_scope)
                if coverage_error is not None:
                    raise AttestationFailure(coverage_error)

                output: dict[str, dict[str, object]] = {}
                for table, scope_column in scoped:
                    columns, inaccessible = await _catalog_access(
                        conn, table, scope_column
                    )
                    # Only verifier-readable columns are included in each row hash.
                    result = await conn.stream(
                        text(_fingerprint_sql(table, columns, scope_column)),
                        {"tenant_id": tenant},
                    )
                    digests: list[str] = []
                    async for row in result:
                        digests.append(row.row_digest)
                        if len(digests) > MAX_ROWS_PER_TABLE:
                            raise AttestationFailure("TENANT_SNAPSHOT_EXCEEDS_LIMIT")
                    digest_input = (table + "\n" + "\n".join(sorted(digests))).encode()
                    output[table] = {
                        "count": len(digests),
                        "scope_column": scope_column,
                        "readable_columns": len(columns),
                        "ungranted_columns": inaccessible,
                        "hmac": hmac.new(key, digest_input, hashlib.sha256).hexdigest(),
                    }

                # Include the tenant metadata record using granted columns.
                tenant_columns, tenant_inaccessible = await _catalog_access(
                    conn, "tenants", "id"
                )
                tenant_result = await conn.execute(
                    text(_fingerprint_sql("tenants", tenant_columns, "id")),
                    {"tenant_id": tenant},
                )
                tenant_digests = list(tenant_result.scalars())
                if len(tenant_digests) != 1:
                    raise AttestationFailure("TENANT_RECORD_NOT_VISIBLE")
                output["__synthetic_tenant__"] = {
                    "count": 1,
                    "scope_column": "id",
                    "readable_columns": len(tenant_columns),
                    "ungranted_columns": tenant_inaccessible,
                    "hmac": hmac.new(
                        key, tenant_digests[0].encode(), hashlib.sha256
                    ).hexdigest(),
                }
                await transaction.rollback()
                return {
                    "scope": "tenant_project_scoped_verifier_readable_columns_only",
                    "ungranted_column_tables": sum(
                        int(row["ungranted_columns"] > 0) for row in output.values()
                    ),
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
            print("PQ939_TENANT_PROJECT_SCOPED_READABLE_COLUMNS: UNCHANGED (read-only)")
            if after["ungranted_column_tables"]:
                print("PQ939_UNGRANTED_COLUMNS: NOT_VERIFIED")
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
