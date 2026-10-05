#!/usr/bin/env python
"""Read-only verifier for the P0c production qualification continuation.

The verifier never repairs production state. It proves that the accepted P0b
project still contains one logical contract document before mutation and, after
the browser run, that Contract B became revision 2 of that SAME document and
that one durable revision.changed event binds the exact immutable revisions.

All queries are tenant + project scoped and execute in a READ ONLY transaction.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"
REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_JSON = REPO_ROOT / "apps/web/playwright/.p0c-prod/run.json"
EVIDENCE_JSON = REPO_ROOT / "evidence/product-qualification/runtime/p0c-verifier.json"


class VerificationFailure(RuntimeError):
    """The bounded P0c production contract is not satisfied."""


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


def _load_run() -> dict[str, Any]:
    if not RUN_JSON.is_file():
        raise VerificationFailure("canonical P0c browser run evidence is missing")
    value = json.loads(RUN_JSON.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise VerificationFailure("canonical P0c browser run evidence must be an object")
    return value


def _require_run_string(run: dict[str, Any], key: str) -> str:
    value = run.get(key)
    if not isinstance(value, str) or not value.strip():
        raise VerificationFailure(f"browser run missing {key}")
    return value.strip()


async def _one(conn: AsyncConnection, query: str, params: dict[str, object]) -> Any:
    result = await conn.execute(text(query), params)
    rows = result.mappings().all()
    if len(rows) != 1:
        raise VerificationFailure(f"expected one row, got {len(rows)}")
    return rows[0]


async def _preflight_checks(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
) -> tuple[list[Check], dict[str, str]]:
    p = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
    }

    scope = await _one(
        conn,
        """
        SELECT
          count(*) FILTER (
            WHERE p.id = :project_id
              AND p.tenant_id = :tenant_id
              AND p.name LIKE 'ACCEPT-706-%'
          ) AS project_ok,
          count(DISTINCT d.id) FILTER (
            WHERE d.project_id = :project_id
              AND d.tenant_id = :tenant_id
          ) AS documents,
          count(DISTINCT r.revision_id) FILTER (
            WHERE r.project_id = :project_id
              AND r.tenant_id = :tenant_id
              AND r.document_id = :document_id
          ) AS revisions,
          count(*) FILTER (
            WHERE d.id = :document_id
              AND d.project_id = :project_id
              AND d.tenant_id = :tenant_id
              AND d.document_type::text = 'contract'
              AND d.upload_status::text = 'analyzed'
              AND d.version = 1
          ) AS document_ok
        FROM projects p
        LEFT JOIN documents d
          ON d.project_id = p.id AND d.tenant_id = p.tenant_id
        LEFT JOIN document_revisions r
          ON r.document_id = d.id
         AND r.project_id = p.id
         AND r.tenant_id = p.tenant_id
        WHERE p.id = :project_id AND p.tenant_id = :tenant_id
        """,
        p,
    )

    source = await _one(
        conn,
        """
        SELECT
          count(*) FILTER (
            WHERE revision_id = :source_revision_id
              AND document_id = :document_id
              AND project_id = :project_id
              AND tenant_id = :tenant_id
              AND rev_no = 1
              AND parent_revision_id IS NULL
              AND valid_to IS NULL
          ) AS source_ok,
          max(blob_hash) FILTER (WHERE revision_id = :source_revision_id) AS source_blob_hash
        FROM document_revisions
        WHERE project_id = :project_id
          AND tenant_id = :tenant_id
          AND document_id = :document_id
        """,
        p,
    )

    existing_changes = await _one(
        conn,
        """
        SELECT count(*) AS n
        FROM project_events
        WHERE project_id = :project_id
          AND tenant_id = :tenant_id
          AND event_type IN ('revision.changed','revision.recomputed','revision.reinterpreted')
          AND payload ->> 'document_id' = CAST(:document_id AS text)
        """,
        p,
    )

    source_hash = str(source["source_blob_hash"] or "")
    checks = [
        Check("accepted synthetic project scope", int(scope["project_ok"]) == 1, f"projects={scope['project_ok']}"),
        Check("one logical document before P0c", int(scope["documents"]) == 1, f"documents={scope['documents']}"),
        Check("one source revision before P0c", int(scope["revisions"]) == 1, f"revisions={scope['revisions']}"),
        Check("accepted contract A remains analyzed version 1", int(scope["document_ok"]) == 1, f"documents={scope['document_ok']}"),
        Check("accepted revision A identity is current", int(source["source_ok"]) == 1, f"matching_revisions={source['source_ok']}"),
        Check("no pre-existing temporal outcome for Contract A", int(existing_changes["n"]) == 0, f"outcomes={existing_changes['n']}"),
        Check("source revision has immutable blob hash", bool(source_hash), f"blob_hash_present={bool(source_hash)}"),
    ]
    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "from_revision_id": str(source_revision_id),
        "source_blob_hash": source_hash,
    }
    return checks, identifiers


async def _post_checks(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
    run: dict[str, Any],
) -> tuple[list[Check], dict[str, str]]:
    run_project = _uuid(_require_run_string(run, "project_id"), "run project id")
    run_document = _uuid(_require_run_string(run, "document_id"), "run document id")
    run_source = _uuid(_require_run_string(run, "from_revision_id"), "run source revision id")
    target_revision_id = _uuid(_require_run_string(run, "to_revision_id"), "run target revision id")
    change_event_id = _uuid(_require_run_string(run, "change_event_id"), "run change event id")
    source_blob_hash = _require_run_string(run, "source_blob_hash")
    target_blob_hash = _require_run_string(run, "target_blob_hash")

    if (run_project, run_document, run_source) != (project_id, document_id, source_revision_id):
        raise VerificationFailure("browser run identifiers disagree with the bound P0b project")
    if target_revision_id == source_revision_id:
        raise VerificationFailure("target revision must differ from source revision")
    if source_blob_hash == target_blob_hash:
        raise VerificationFailure("Contract A and B blob hashes must differ")

    p = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "change_event_id": change_event_id,
    }

    scope = await _one(
        conn,
        """
        SELECT
          count(DISTINCT d.id) AS documents,
          count(DISTINCT r.revision_id) AS revisions,
          count(*) FILTER (
            WHERE d.id = :document_id
              AND d.document_type::text = 'contract'
              AND d.upload_status::text = 'analyzed'
              AND d.version = 2
          ) AS document_v2
        FROM documents d
        LEFT JOIN document_revisions r
          ON r.document_id = d.id
         AND r.project_id = d.project_id
         AND r.tenant_id = d.tenant_id
        WHERE d.project_id = :project_id
          AND d.tenant_id = :tenant_id
        """,
        p,
    )

    revisions = await _one(
        conn,
        """
        SELECT
          count(*) FILTER (
            WHERE revision_id = :source_revision_id
              AND rev_no = 1
              AND parent_revision_id IS NULL
              AND blob_hash = :source_blob_hash
          ) AS source_ok,
          count(*) FILTER (
            WHERE revision_id = :target_revision_id
              AND rev_no = 2
              AND parent_revision_id = :source_revision_id
              AND blob_hash = :target_blob_hash
              AND valid_to IS NULL
          ) AS target_ok,
          count(*) FILTER (
            WHERE revision_id = :source_revision_id
              AND valid_to IS NOT NULL
          ) AS source_closed
        FROM document_revisions
        WHERE project_id = :project_id
          AND tenant_id = :tenant_id
          AND document_id = :document_id
        """,
        {**p, "source_blob_hash": source_blob_hash, "target_blob_hash": target_blob_hash},
    )

    event = await _one(
        conn,
        """
        SELECT
          count(*) AS event_count,
          count(*) FILTER (
            WHERE event_type = 'revision.changed'
              AND source_revision_id = :target_revision_id
              AND payload ->> 'document_id' = CAST(:document_id AS text)
              AND payload ->> 'state' = 'ready'
              AND payload #>> '{provenance,source_revision_id}' = CAST(:source_revision_id AS text)
              AND payload #>> '{provenance,target_revision_id}' = CAST(:target_revision_id AS text)
              AND payload #>> '{provenance,source_blob_hash}' = :source_blob_hash
              AND payload #>> '{provenance,target_blob_hash}' = :target_blob_hash
              AND jsonb_typeof(payload -> 'changeset' -> 'changes') = 'array'
              AND jsonb_array_length(payload -> 'changeset' -> 'changes') > 0
              AND jsonb_array_length(evidence_refs) > 0
          ) AS canonical_event_ok,
          max(payload ->> 'change_cause') AS change_cause
        FROM project_events
        WHERE event_id = :change_event_id
          AND project_id = :project_id
          AND tenant_id = :tenant_id
        """,
        {
            **p,
            "source_blob_hash": source_blob_hash,
            "target_blob_hash": target_blob_hash,
        },
    )

    duplicate = await _one(
        conn,
        """
        SELECT count(*) AS n
        FROM project_events
        WHERE project_id = :project_id
          AND tenant_id = :tenant_id
          AND event_type = 'revision.changed'
          AND payload ->> 'document_id' = CAST(:document_id AS text)
          AND payload #>> '{provenance,target_revision_id}' = CAST(:target_revision_id AS text)
        """,
        p,
    )

    checks = [
        Check("one logical document after revision B", int(scope["documents"]) == 1, f"documents={scope['documents']}"),
        Check("exactly two revisions after revision B", int(scope["revisions"]) == 2, f"revisions={scope['revisions']}"),
        Check("logical document is analyzed version 2", int(scope["document_v2"]) == 1, f"documents={scope['document_v2']}"),
        Check("source revision A blob identity preserved", int(revisions["source_ok"]) == 1, f"source_matches={revisions['source_ok']}"),
        Check("target revision B parent/blob identity exact", int(revisions["target_ok"]) == 1, f"target_matches={revisions['target_ok']}"),
        Check("source revision closed when B became current", int(revisions["source_closed"]) == 1, f"closed_sources={revisions['source_closed']}"),
        Check("exact revision.changed event exists", int(event["event_count"]) == 1, f"events={event['event_count']}"),
        Check("revision.changed durable provenance/evidence is exact", int(event["canonical_event_ok"]) == 1, f"matching_events={event['canonical_event_ok']}"),
        Check("revision B has one canonical change outcome", int(duplicate["n"]) == 1, f"revision_changed_events={duplicate['n']}"),
        Check("change cause is business-state change", event["change_cause"] == "BUSINESS_STATE_CHANGED", f"change_cause={event['change_cause']}"),
        Check("browser PJ-01 classification is usable", run.get("pj01_classification") == "USABLE", f"classification={run.get('pj01_classification')}"),
        Check("browser recorded no blocking findings", run.get("blocking_findings") == [], f"blocking_findings={len(run.get('blocking_findings') or [])}"),
        Check("same logical document remained listed", run.get("documents_listed") == 1, f"documents_listed={run.get('documents_listed')}"),
        Check("revision processing settled analyzed", run.get("processing_outcome") == "analyzed", f"outcome={run.get('processing_outcome')}"),
    ]
    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "from_revision_id": str(source_revision_id),
        "to_revision_id": str(target_revision_id),
        "change_event_id": str(change_event_id),
    }
    return checks, identifiers


async def verify(
    *,
    database_url: str,
    phase: str,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
) -> tuple[list[Check], dict[str, str]]:
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )
                if phase == "preflight":
                    result = await _preflight_checks(
                        conn,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=document_id,
                        source_revision_id=source_revision_id,
                    )
                else:
                    result = await _post_checks(
                        conn,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=document_id,
                        source_revision_id=source_revision_id,
                        run=_load_run(),
                    )
                await tx.rollback()
                return result
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("preflight", "post"), required=True)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source-revision-id", required=True)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id:
        print("FAIL: required P0c qualification configuration is missing.", file=sys.stderr)
        return 2

    try:
        tenant_id = _uuid(args.tenant_id, "tenant id")
        project_id = _uuid(args.project_id, "project id")
        document_id = _uuid(args.document_id, "document id")
        source_revision_id = _uuid(args.source_revision_id, "source revision id")
        checks, identifiers = asyncio.run(
            verify(
                database_url=database_url,
                phase=args.phase,
                tenant_id=tenant_id,
                project_id=project_id,
                document_id=document_id,
                source_revision_id=source_revision_id,
            )
        )
    except Exception as exc:
        print(
            f"FAIL: P0c verifier execution failed ({type(exc).__name__}: {exc}).",
            file=sys.stderr,
        )
        return 2

    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed

    if args.write_evidence:
        if args.phase != "post":
            print("FAIL: evidence output is valid only for post-run verification.", file=sys.stderr)
            return 2
        output = {
            "schema": "c2pro-p0c-production-verifier/v1",
            "verdict": "FAIL" if failed else "PASS",
            "identifiers": identifiers,
            "checks": [
                {"name": check.name, "passed": check.passed, "detail": check.detail}
                for check in checks
            ],
        }
        EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_JSON.write_text(json.dumps(output, indent=2, sort_keys=True), encoding="utf-8")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
