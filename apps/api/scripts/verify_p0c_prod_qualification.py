#!/usr/bin/env python
"""Read-only verifier for #686 P0c production qualification.

The verifier never repairs state, never reads unrelated tenants, and never
prints credentials. It proves that the browser-created PJ-01 project contains
one logical document, exactly two canonical revisions, and one durable
revision.changed event with exact provenance.
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

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path("evidence/product-qualification/runtime/p0c-verifier.json")


class VerificationFailure(Exception):
    """P0c production contract is not satisfied."""


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


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
    conn: AsyncConnection, sql: str, params: dict[str, object]
) -> int:
    result = await conn.execute(text(sql), params)
    return int(result.scalar_one())


async def verify(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    clerk_org_id: str,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
    target_revision_id: UUID,
    change_event_id: UUID,
    source_blob_hash: str,
    target_blob_hash: str,
) -> tuple[list[Check], dict[str, str]]:
    p = {
        "tenant_id": tenant_id,
        "clerk_org_id": clerk_org_id,
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "change_event_id": change_event_id,
        "source_blob_hash": source_blob_hash,
        "target_blob_hash": target_blob_hash,
    }

    change_params = {
        **p,
        "document_id_text": str(document_id),
        "source_revision_id_text": str(source_revision_id),
        "target_revision_id_text": str(target_revision_id),
    }
    duplicate_change_params = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id_text": str(document_id),
        "source_revision_id_text": str(source_revision_id),
        "target_revision_id_text": str(target_revision_id),
    }

    eligible_tenant = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM tenants
         WHERE id = :tenant_id
           AND is_active IS TRUE
           AND clerk_org_id = :clerk_org_id
           AND coalesce((settings ->> 'synthetic_acceptance')::boolean, false) IS TRUE
        """,
        p,
    )
    project = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM projects
         WHERE id = :project_id
           AND tenant_id = :tenant_id
           AND name LIKE 'P0c Qualification %'
        """,
        p,
    )
    documents = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM documents
         WHERE project_id = :project_id AND tenant_id = :tenant_id
        """,
        p,
    )
    exact_document = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM documents
         WHERE id = :document_id
           AND project_id = :project_id
           AND tenant_id = :tenant_id
        """,
        p,
    )
    revisions = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM document_revisions
         WHERE document_id = :document_id
           AND project_id = :project_id
           AND tenant_id = :tenant_id
        """,
        p,
    )
    lineage = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM document_revisions src
          JOIN document_revisions dst
            ON dst.parent_revision_id = src.revision_id
           AND dst.document_id = src.document_id
           AND dst.project_id = src.project_id
           AND dst.tenant_id = src.tenant_id
         WHERE src.revision_id = :source_revision_id
           AND dst.revision_id = :target_revision_id
           AND src.document_id = :document_id
           AND src.project_id = :project_id
           AND src.tenant_id = :tenant_id
           AND src.valid_to IS NOT NULL
           AND dst.valid_to IS NULL
           AND src.blob_hash = :source_blob_hash
           AND dst.blob_hash = :target_blob_hash
        """,
        p,
    )
    change = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM project_events
         WHERE event_id = :change_event_id
           AND project_id = :project_id
           AND tenant_id = :tenant_id
           AND event_type = 'revision.changed'
           AND source_revision_id = :target_revision_id
           AND payload ->> 'state' = 'ready'
           AND payload ->> 'document_id' = :document_id_text
           AND payload ->> 'change_cause' = 'BUSINESS_STATE_CHANGED'
           AND payload #>> '{provenance,source_revision_id}' = :source_revision_id_text
           AND payload #>> '{provenance,target_revision_id}' = :target_revision_id_text
           AND payload #>> '{provenance,source_blob_hash}' = :source_blob_hash
           AND payload #>> '{provenance,target_blob_hash}' = :target_blob_hash
        """,
        change_params,
    )
    event_evidence = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM project_events
         WHERE event_id = :change_event_id
           AND project_id = :project_id
           AND tenant_id = :tenant_id
           AND jsonb_array_length(evidence_refs) > 0
        """,
        p,
    )
    duplicate_change = await _scalar(
        conn,
        """
        SELECT count(*)
          FROM project_events
         WHERE project_id = :project_id
           AND tenant_id = :tenant_id
           AND event_type = 'revision.changed'
           AND payload ->> 'document_id' = :document_id_text
           AND payload #>> '{provenance,source_revision_id}' = :source_revision_id_text
           AND payload #>> '{provenance,target_revision_id}' = :target_revision_id_text
        """,
        duplicate_change_params,
    )

    checks = [
        Check("synthetic tenant binding", eligible_tenant == 1, f"eligible_tenants={eligible_tenant}"),
        Check("fresh P0c qualification project belongs to tenant", project == 1, f"projects={project}"),
        Check("same logical document preserved", documents == 1, f"documents={documents}"),
        Check("browser document is canonical project document", exact_document == 1, f"matching_documents={exact_document}"),
        Check("exactly two revisions after Contract B", revisions == 2, f"revisions={revisions}"),
        Check("source-target lineage and blob hashes durable", lineage == 1, f"lineage_matches={lineage}"),
        Check("revision.changed event durable and provenance exact", change == 1, f"matching_change_events={change}"),
        Check("change event carries evidence refs", event_evidence == 1, f"events_with_evidence={event_evidence}"),
        Check("no duplicate revision.changed outcome", duplicate_change == 1, f"matching_family_events={duplicate_change}"),
    ]
    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "source_revision_id": str(source_revision_id),
        "target_revision_id": str(target_revision_id),
        "change_event_id": str(change_event_id),
    }
    return checks, identifiers


async def _run(args: argparse.Namespace, database_url: str) -> tuple[list[Check], dict[str, str]]:
    tenant_id = _uuid(args.tenant_id, "tenant id")
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            transaction = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                checks, identifiers = await verify(
                    conn,
                    tenant_id=tenant_id,
                    clerk_org_id=args.clerk_org_id,
                    project_id=_uuid(args.project_id, "project id"),
                    document_id=_uuid(args.document_id, "document id"),
                    source_revision_id=_uuid(args.source_revision_id, "source revision id"),
                    target_revision_id=_uuid(args.target_revision_id, "target revision id"),
                    change_event_id=_uuid(args.change_event_id, "change event id"),
                    source_blob_hash=args.source_blob_hash,
                    target_blob_hash=args.target_blob_hash,
                )
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
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source-revision-id", required=True)
    parser.add_argument("--target-revision-id", required=True)
    parser.add_argument("--change-event-id", required=True)
    parser.add_argument("--source-blob-hash", required=True)
    parser.add_argument("--target-blob-hash", required=True)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: required production qualification configuration is missing.", file=sys.stderr)
        return 2

    try:
        checks, identifiers = asyncio.run(_run(args, database_url))
    except Exception as exc:
        print(
            f"FAIL: P0c verifier execution failed ({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed

    if args.write_evidence:
        output = {
            "schema": "c2pro-p0c-prod-verifier/v1",
            "verdict": "FAIL" if failed else "PASS",
            "identifiers": identifiers,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in checks
            ],
        }
        output_path = REPO_ROOT / OUTPUT
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
