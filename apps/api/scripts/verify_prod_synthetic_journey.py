#!/usr/bin/env python
"""Read-only verifier for the #706 synthetic production journey.

Never repairs state and never emits credential values. Every post-run query
is scoped by both tenant and project even if the read-only verifier account
could see more rows.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine


class VerificationFailure(Exception):
    """Synthetic production contract is not satisfied."""


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def _normalize_database_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    return raw


def _uuid(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure(f"{label} must be a UUID") from exc


async def _scalar(conn: AsyncConnection, sql: str, params: dict[str, object]) -> int:
    result = await conn.execute(text(sql), params)
    return int(result.scalar_one())


async def _preflight_checks(
    conn: AsyncConnection, *, tenant_id: UUID, clerk_org_id: str
) -> list[Check]:
    eligible = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM tenants
         WHERE id = :tenant_id
           AND is_active IS TRUE
           AND clerk_org_id = :clerk_org_id
           AND coalesce((settings ->> 'synthetic_acceptance')::boolean, false) IS TRUE
        """,
        {"tenant_id": tenant_id, "clerk_org_id": clerk_org_id},
    )
    foreign_projects = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM projects
         WHERE tenant_id = :tenant_id
           AND name NOT LIKE 'ACCEPT-706-%'
        """,
        {"tenant_id": tenant_id},
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
    p = {"tenant_id": tenant_id, "project_id": project_id}
    queries = {
        "synthetic project scope": """
            SELECT count(*) FROM projects
             WHERE id = :project_id AND tenant_id = :tenant_id
               AND name LIKE 'ACCEPT-706-%'
        """,
        "document persisted": """
            SELECT count(*) FROM documents
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """,
        "document terminal": """
            SELECT count(*) FROM documents
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND upload_status::text IN ('analyzed','needs_changes')
        """,
        "clauses persisted": """
            SELECT count(*) FROM clauses
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """,
        "RAG chunks persisted": """
            SELECT count(*) FROM document_chunks
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """,
        "analysis persisted": """
            SELECT count(*) FROM analyses
             WHERE project_id = :project_id AND tenant_id = :tenant_id
        """,
        "trusted canonical artifact": """
            SELECT count(*) FROM document_artifacts
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND trust_state = 'trusted' AND lifecycle_status = 'active'
        """,
        "ProjectGraph completed": """
            SELECT count(*) FROM project_events
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND event_type = 'graph.completed'
        """,
        "six-category Health snapshot": """
            SELECT count(*) FROM project_snapshots
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND health_vector IS NOT NULL
               AND jsonb_array_length(
                     health_vector -> 'single_document_coverage' -> 'assessments'
                   ) = 6
        """,
    }
    values = {name: await _scalar(conn, sql, p) for name, sql in queries.items()}
    checks = [
        Check("synthetic project scope", values["synthetic project scope"] == 1, f"projects={values['synthetic project scope']}"),
        Check("document persisted", values["document persisted"] >= 1, f"documents={values['document persisted']}"),
        Check("document terminal", values["document terminal"] >= 1, f"terminal_documents={values['document terminal']}"),
        Check("clauses persisted", values["clauses persisted"] > 0, f"clauses={values['clauses persisted']}"),
        Check("RAG chunks persisted", values["RAG chunks persisted"] > 0, f"chunks={values['RAG chunks persisted']}"),
        Check("analysis persisted", values["analysis persisted"] > 0, f"analyses={values['analysis persisted']}"),
        Check("trusted canonical artifact", values["trusted canonical artifact"] > 0, f"trusted_artifacts={values['trusted canonical artifact']}"),
        Check("ProjectGraph completed", values["ProjectGraph completed"] > 0, f"graph_completed={values['ProjectGraph completed']}"),
        Check("six-category Health snapshot", values["six-category Health snapshot"] > 0, f"health_snapshots={values['six-category Health snapshot']}"),
    ]
    if require_hitl:
        finalized = await _scalar(
            conn,
            """
            SELECT count(*) FROM review_items
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND current_status::text IN ('APPROVED','REJECTED','CLOSED')
            """,
            p,
        )
        corrections = await _scalar(
            conn,
            """
            SELECT count(*) FROM project_events
             WHERE project_id = :project_id AND tenant_id = :tenant_id
               AND event_type = 'hitl.correction'
            """,
            p,
        )
        checks.extend([
            Check("HITL decision finalized", finalized > 0, f"finalized_reviews={finalized}"),
            Check("HITL event persisted", corrections > 0, f"hitl_events={corrections}"),
        ])
    return checks


async def verify(*, database_url: str, tenant_id: UUID, clerk_org_id: str, project_id: UUID | None, require_hitl: bool) -> list[Check]:
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                checks = await _preflight_checks(conn, tenant_id=tenant_id, clerk_org_id=clerk_org_id)
                if project_id is not None:
                    checks.extend(await _journey_checks(conn, tenant_id=tenant_id, project_id=project_id, require_hitl=require_hitl))
                await transaction.rollback()
                return checks
            except Exception:
                await transaction.rollback()
                raise
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default=os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY"))
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--clerk-org-id", default=os.getenv("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"))
    parser.add_argument("--project-id", default=os.getenv("PROD_ACCEPTANCE_PROJECT_ID"))
    parser.add_argument("--require-hitl", action="store_true")
    args = parser.parse_args()
    if not args.database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: required production acceptance configuration is missing.", file=sys.stderr)
        return 2
    try:
        tenant_id = _uuid(args.tenant_id, "tenant id")
        project_id = _uuid(args.project_id, "project id") if args.project_id else None
        checks = asyncio.run(verify(database_url=args.database_url, tenant_id=tenant_id, clerk_org_id=args.clerk_org_id, project_id=project_id, require_hitl=args.require_hitl))
    except Exception as exc:
        print(f"FAIL: verifier execution failed ({type(exc).__name__}).", file=sys.stderr)
        return 2
    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
