#!/usr/bin/env python
"""Read-only verifier for the #706 synthetic production journey.

Never repairs state and never emits credential values. Every post-run query
is scoped by both tenant and project even if the read-only verifier account
could see more rows.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine
from sqlalchemy.sql.elements import TextClause

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"
REPO_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_VERIFIER_OUTPUT = Path("evidence/product-qualification/runtime/verifier.json")
CHECK_SYNTHETIC_PROJECT_SCOPE = "synthetic project scope"
CHECK_DOCUMENT_PERSISTED = "document persisted"
CHECK_DOCUMENT_TERMINAL = "document terminal"
CHECK_CLAUSES_PERSISTED = "clauses persisted"
CHECK_RAG_CHUNKS_PERSISTED = "RAG chunks persisted"
CHECK_ANALYSIS_PERSISTED = "analysis persisted"
CHECK_TRUSTED_CANONICAL_ARTIFACT = "trusted canonical artifact"
CHECK_PROJECT_GRAPH_COMPLETED = "ProjectGraph completed"
CHECK_SIX_CATEGORY_HEALTH_SNAPSHOT = "six-category Health snapshot"
TENANT_ID_KEY = "tenant_id"
PROJECT_ID_KEY = "project_id"


class VerificationFailure(Exception):
    """Synthetic production contract is not satisfied."""


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str



def _verifier_output_path(*, repo_root: Path = REPO_ROOT) -> Path:
    """Return the single canonical verifier evidence path."""
    return repo_root.resolve() / CANONICAL_VERIFIER_OUTPUT


def _normalize_database_url(raw: str) -> str:
    if raw.startswith(ASYNCPG_URL_PREFIX):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", ASYNCPG_URL_PREFIX, 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", ASYNCPG_URL_PREFIX, 1)
    raise VerificationFailure("database URL must use a PostgreSQL scheme")


def _uuid(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure(f"{label} must be a UUID") from exc


async def _scalar(
    conn: AsyncConnection, statement: TextClause, params: dict[str, object]
) -> int:
    result = await conn.execute(statement, params)
    return int(result.scalar_one())


async def _preflight_checks(
    conn: AsyncConnection, *, tenant_id: UUID, clerk_org_id: str
) -> list[Check]:
    eligible = await _scalar(
        conn,
        text(
            """
        SELECT count(*)
          FROM tenants
         WHERE id = :tenant_id
           AND is_active IS TRUE
           AND clerk_org_id = :clerk_org_id
           AND coalesce((settings ->> 'synthetic_acceptance')::boolean, false) IS TRUE
            """
        ),
        {TENANT_ID_KEY: tenant_id, "clerk_org_id": clerk_org_id},
    )
    foreign_projects = await _scalar(
        conn,
        text(
            """
        SELECT count(*)
          FROM projects
         WHERE tenant_id = :tenant_id
           AND name NOT LIKE 'ACCEPT-706-%'
            """
        ),
        {TENANT_ID_KEY: tenant_id},
    )
    return [
        Check("synthetic tenant binding", eligible == 1, f"eligible_tenants={eligible}"),
        Check(
            "dedicated tenant contains no non-acceptance projects",
            foreign_projects == 0,
            f"non_acceptance_projects={foreign_projects}",
        ),
    ]


async def _journey_checks(
    conn: AsyncConnection, *, tenant_id: UUID, project_id: UUID, require_hitl: bool
) -> list[Check]:
    p = {TENANT_ID_KEY: tenant_id, PROJECT_ID_KEY: project_id}
    queries = {
        CHECK_SYNTHETIC_PROJECT_SCOPE: text("""
            SELECT count(*) FROM projects
             WHERE id = :project_id AND tenant_id = :tenant_id
               AND name LIKE 'ACCEPT-706-%'
        """),
        CHECK_DOCUMENT_PERSISTED: text("""
            SELECT count(*) FROM documents
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """),
        CHECK_DOCUMENT_TERMINAL: text("""
            SELECT count(*) FROM documents
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND upload_status::text IN ('analyzed','needs_changes')
        """),
        CHECK_CLAUSES_PERSISTED: text("""
            SELECT count(*) FROM clauses
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """),
        CHECK_RAG_CHUNKS_PERSISTED: text("""
            SELECT count(*) FROM document_chunks
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """),
        CHECK_ANALYSIS_PERSISTED: text("""
            SELECT count(*) FROM analyses
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """),
        CHECK_TRUSTED_CANONICAL_ARTIFACT: text("""
            SELECT count(*) FROM document_artifacts
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND trust_state = 'trusted' AND lifecycle_status = 'active'
        """),
        CHECK_PROJECT_GRAPH_COMPLETED: text("""
            SELECT count(*) FROM project_events
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND event_type = 'graph.completed'
        """),
        CHECK_SIX_CATEGORY_HEALTH_SNAPSHOT: text("""
            SELECT count(*) FROM project_snapshots
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND health_vector IS NOT NULL
               AND jsonb_array_length(
                     health_vector -> 'single_document_coverage' -> 'assessments'
                   ) = 6
        """),
    }
    values = {name: await _scalar(conn, sql, p) for name, sql in queries.items()}
    checks = [
        Check(CHECK_SYNTHETIC_PROJECT_SCOPE, values[CHECK_SYNTHETIC_PROJECT_SCOPE] == 1, f"projects={values[CHECK_SYNTHETIC_PROJECT_SCOPE]}"),
        Check(CHECK_DOCUMENT_PERSISTED, values[CHECK_DOCUMENT_PERSISTED] >= 1, f"documents={values[CHECK_DOCUMENT_PERSISTED]}"),
        Check(CHECK_DOCUMENT_TERMINAL, values[CHECK_DOCUMENT_TERMINAL] >= 1, f"terminal_documents={values[CHECK_DOCUMENT_TERMINAL]}"),
        Check(CHECK_CLAUSES_PERSISTED, values[CHECK_CLAUSES_PERSISTED] > 0, f"clauses={values[CHECK_CLAUSES_PERSISTED]}"),
        Check(CHECK_RAG_CHUNKS_PERSISTED, values[CHECK_RAG_CHUNKS_PERSISTED] > 0, f"chunks={values[CHECK_RAG_CHUNKS_PERSISTED]}"),
        Check(CHECK_ANALYSIS_PERSISTED, values[CHECK_ANALYSIS_PERSISTED] > 0, f"analyses={values[CHECK_ANALYSIS_PERSISTED]}"),
        Check(CHECK_TRUSTED_CANONICAL_ARTIFACT, values[CHECK_TRUSTED_CANONICAL_ARTIFACT] > 0, f"trusted_artifacts={values[CHECK_TRUSTED_CANONICAL_ARTIFACT]}"),
        Check(CHECK_PROJECT_GRAPH_COMPLETED, values[CHECK_PROJECT_GRAPH_COMPLETED] > 0, f"graph_completed={values[CHECK_PROJECT_GRAPH_COMPLETED]}"),
        Check(CHECK_SIX_CATEGORY_HEALTH_SNAPSHOT, values[CHECK_SIX_CATEGORY_HEALTH_SNAPSHOT] > 0, f"health_snapshots={values[CHECK_SIX_CATEGORY_HEALTH_SNAPSHOT]}"),
    ]
    if require_hitl:
        finalized = await _scalar(
            conn,
            text(
                """
                SELECT count(*) FROM review_items
                 WHERE project_id = :project_id AND tenant_id = :tenant_id
                   AND current_status::text IN ('APPROVED','REJECTED','CLOSED')
                """
            ),
            p,
        )
        corrections = await _scalar(
            conn,
            text(
                """
                SELECT count(*) FROM project_events
                 WHERE project_id = :project_id AND tenant_id = :tenant_id
                   AND event_type = 'hitl.correction'
                """
            ),
            p,
        )
        checks.extend([
            Check("HITL decision finalized", finalized > 0, f"finalized_reviews={finalized}"),
            Check("HITL event persisted", corrections > 0, f"hitl_events={corrections}"),
        ])
    return checks


async def _journey_identifiers(
    conn: AsyncConnection, *, tenant_id: UUID, project_id: UUID
) -> tuple[dict[str, str], Check]:
    result = await conn.execute(
        text(
            """
            SELECT d.id AS document_id, r.revision_id
              FROM documents d
              JOIN document_revisions r
                ON r.document_id = d.id
               AND r.tenant_id = d.tenant_id
             WHERE d.project_id = :project_id
               AND d.tenant_id = :tenant_id
               AND r.project_id = :project_id
               AND r.tenant_id = :tenant_id
               AND r.valid_to IS NULL
             ORDER BY r.rev_no DESC
            """
        ),
        {TENANT_ID_KEY: tenant_id, PROJECT_ID_KEY: project_id},
    )
    rows = result.all()
    if len(rows) != 1:
        return (
            {PROJECT_ID_KEY: str(project_id)},
            Check(
                "source revision resolved",
                False,
                f"current_source_revisions={len(rows)}",
            ),
        )
    row = rows[0]
    return (
        {
            PROJECT_ID_KEY: str(project_id),
            "document_id": str(row.document_id),
            "source_revision_id": str(row.revision_id),
        },
        Check("source revision resolved", True, "current_source_revisions=1"),
    )


async def verify(
    *,
    database_url: str,
    tenant_id: UUID,
    clerk_org_id: str,
    project_id: UUID | None,
    require_hitl: bool,
) -> tuple[list[Check], dict[str, str]]:
    engine = create_async_engine(_normalize_database_url(database_url))
    identifiers: dict[str, str] = {}
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                checks = await _preflight_checks(
                    conn,
                    tenant_id=tenant_id,
                    clerk_org_id=clerk_org_id,
                )
                if project_id is not None:
                    checks.extend(
                        await _journey_checks(
                            conn,
                            tenant_id=tenant_id,
                            project_id=project_id,
                            require_hitl=require_hitl,
                        )
                    )
                    identifiers, revision_check = await _journey_identifiers(
                        conn,
                        tenant_id=tenant_id,
                        project_id=project_id,
                    )
                    checks.append(revision_check)
                await transaction.rollback()
                return checks, identifiers
            except Exception:
                await transaction.rollback()
                raise
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--clerk-org-id", default=os.getenv("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"))
    parser.add_argument("--project-id", default=os.getenv("PROD_ACCEPTANCE_PROJECT_ID"))
    parser.add_argument("--require-hitl", action="store_true")
    parser.add_argument(
        "--write-evidence",
        action="store_true",
        help="Write bounded verifier evidence to the canonical repository path.",
    )
    args = parser.parse_args()
    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: required production acceptance configuration is missing.", file=sys.stderr)
        return 2
    try:
        tenant_id = _uuid(args.tenant_id, "tenant id")
        project_id = _uuid(args.project_id, "project id") if args.project_id else None
        checks, identifiers = asyncio.run(
            verify(
                database_url=database_url,
                tenant_id=tenant_id,
                clerk_org_id=args.clerk_org_id,
                project_id=project_id,
                require_hitl=args.require_hitl,
            )
        )
    except Exception as exc:
        print(f"FAIL: verifier execution failed ({type(exc).__name__}).", file=sys.stderr)
        return 2
    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed

    if args.write_evidence:
        output = {
            "verdict": "FAIL" if failed else "PASS",
            "identifiers": identifiers,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in checks
            ],
        }
        output_path = _verifier_output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
