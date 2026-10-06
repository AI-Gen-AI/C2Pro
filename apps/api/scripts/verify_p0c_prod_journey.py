#!/usr/bin/env python3
"""Read-only durable verifier for #686 P0c production qualification."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"
REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = REPO_ROOT / "evidence/product-qualification/runtime/p0c-verifier.json"


class VerificationFailure(RuntimeError):
    pass


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
    raise VerificationFailure("database URL must use PostgreSQL")


def _uuid(raw: str | None, label: str) -> UUID:
    try:
        return UUID(str(raw))
    except (TypeError, ValueError) as exc:
        raise VerificationFailure(f"{label} must be UUID") from exc


async def _scalar(conn: AsyncConnection, sql: str, params: dict[str, object]) -> int:
    return int((await conn.execute(text(sql), params)).scalar_one())


async def verify_pre(
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
    project_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM projects
         WHERE id=:project_id AND tenant_id=:tenant_id
        """,
        p,
    )
    document_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM documents
         WHERE id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id
        """,
        p,
    )
    source_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM document_revisions
         WHERE revision_id=:source_revision_id
           AND document_id=:document_id
           AND project_id=:project_id
           AND tenant_id=:tenant_id
           AND valid_to IS NULL
        """,
        p,
    )
    revision_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM document_revisions
         WHERE document_id=:document_id
           AND project_id=:project_id
           AND tenant_id=:tenant_id
        """,
        p,
    )
    change_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM project_events
         WHERE project_id=:project_id
           AND tenant_id=:tenant_id
           AND event_type='revision.changed'
           AND payload->>'document_id'=CAST(:document_id AS text)
           AND payload->'provenance'->>'target_revision_id'<>CAST(:source_revision_id AS text)
        """,
        p,
    )
    checks = [
        Check("qualification project exists", project_count == 1, f"projects={project_count}"),
        Check("accepted document exists", document_count == 1, f"documents={document_count}"),
        Check("source revision is current", source_count == 1, f"current_source={source_count}"),
        Check("document has exactly one revision before mutation", revision_count == 1, f"revisions={revision_count}"),
        Check("revision B has not already been qualified", change_count == 0, f"later_change_events={change_count}"),
    ]
    return checks, {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "source_revision_id": str(source_revision_id),
    }


async def verify_post(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
    target_revision_id: UUID,
    no_change_target_revision_id: UUID,
) -> tuple[list[Check], dict[str, str]]:
    p = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "no_change_target_revision_id": no_change_target_revision_id,
    }
    target_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM document_revisions
         WHERE revision_id=:target_revision_id
           AND parent_revision_id=:source_revision_id
           AND document_id=:document_id
           AND project_id=:project_id
           AND tenant_id=:tenant_id
        """,
        p,
    )
    no_change_target_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM document_revisions
         WHERE revision_id=:no_change_target_revision_id
           AND parent_revision_id=:target_revision_id
           AND document_id=:document_id
           AND project_id=:project_id
           AND tenant_id=:tenant_id
           AND valid_to IS NULL
        """,
        p,
    )
    revision_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM document_revisions
         WHERE document_id=:document_id
           AND project_id=:project_id
           AND tenant_id=:tenant_id
        """,
        p,
    )
    result = await conn.execute(
        text(
            """
            SELECT event_id,
                   payload->>'state' AS state,
                   payload->>'change_cause' AS change_cause,
                   jsonb_array_length(coalesce(payload->'changeset'->'changes','[]'::jsonb)) AS changes,
                   jsonb_array_length(coalesce(evidence_refs,'[]'::jsonb)) AS evidence_count,
                   (
                     SELECT count(*)
                     FROM jsonb_array_elements(coalesce(payload->'changeset'->'changes','[]'::jsonb)) ch
                     WHERE jsonb_array_length(coalesce(ch->'evidence_refs','[]'::jsonb)) = 0
                   ) AS changes_without_evidence
              FROM project_events
             WHERE project_id=:project_id
               AND tenant_id=:tenant_id
               AND event_type='revision.changed'
               AND payload->>'document_id'=CAST(:document_id AS text)
               AND payload->'provenance'->>'source_revision_id'=CAST(:source_revision_id AS text)
               AND payload->'provenance'->>'target_revision_id'=CAST(:target_revision_id AS text)
             ORDER BY occurred_at, event_id
            """
        ),
        p,
    )
    events = result.mappings().all()
    event = events[0] if len(events) == 1 else None

    no_change_result = await conn.execute(
        text(
            """
            SELECT event_id,
                   payload->>'state' AS state,
                   payload->>'change_cause' AS change_cause,
                   jsonb_array_length(coalesce(payload->'changeset'->'changes','[]'::jsonb)) AS changes
              FROM project_events
             WHERE project_id=:project_id
               AND tenant_id=:tenant_id
               AND event_type='revision.changed'
               AND payload->>'document_id'=CAST(:document_id AS text)
               AND payload->'provenance'->>'source_revision_id'=CAST(:target_revision_id AS text)
               AND payload->'provenance'->>'target_revision_id'=CAST(:no_change_target_revision_id AS text)
             ORDER BY occurred_at, event_id
            """
        ),
        p,
    )
    no_change_events = no_change_result.mappings().all()
    no_change_event = no_change_events[0] if len(no_change_events) == 1 else None

    hash_result = await conn.execute(
        text(
            """
            SELECT revision_id, blob_hash
              FROM document_revisions
             WHERE tenant_id=:tenant_id
               AND project_id=:project_id
               AND document_id=:document_id
               AND revision_id IN (:target_revision_id, :no_change_target_revision_id)
            """
        ),
        p,
    )
    hashes = {row.revision_id: row.blob_hash for row in hash_result.all()}
    no_change_hash_distinct = (
        target_revision_id in hashes
        and no_change_target_revision_id in hashes
        and bool(hashes[target_revision_id])
        and bool(hashes[no_change_target_revision_id])
        and hashes[target_revision_id] != hashes[no_change_target_revision_id]
    )

    failure_count = await _scalar(
        conn,
        """
        SELECT count(*) FROM project_events
         WHERE project_id=:project_id
           AND tenant_id=:tenant_id
           AND event_type='revision.analysis_failed'
           AND payload->>'document_id'=CAST(:document_id AS text)
        """,
        p,
    )

    checks = [
        Check("target revision persists as child of source", target_count == 1, f"target_revisions={target_count}"),
        Check(
            "semantic no-change revision persists as child of target",
            no_change_target_count == 1,
            f"no_change_target_revisions={no_change_target_count}",
        ),
        Check("document has exactly three revisions", revision_count == 3, f"revisions={revision_count}"),
        Check("one durable revision.changed event", len(events) == 1, f"change_events={len(events)}"),
        Check("change event is ready", bool(event and event["state"] == "ready"), f"state={event['state'] if event else None}"),
        Check(
            "business change cause is canonical",
            bool(event and event["change_cause"] in {"BUSINESS_STATE_CHANGED", "NEWLY_DISCOVERED"}),
            f"change_cause={event['change_cause'] if event else None}",
        ),
        Check("semantic changes persist", bool(event and int(event["changes"]) > 0), f"changes={event['changes'] if event else 0}"),
        Check("event carries evidence", bool(event and int(event["evidence_count"]) > 0), f"evidence_refs={event['evidence_count'] if event else 0}"),
        Check(
            "every reported change carries evidence",
            bool(event and int(event["changes_without_evidence"]) == 0),
            f"changes_without_evidence={event['changes_without_evidence'] if event else None}",
        ),
        Check(
            "one durable semantic no-change event",
            len(no_change_events) == 1,
            f"no_change_events={len(no_change_events)}",
        ),
        Check(
            "semantic no-change event is ready",
            bool(no_change_event and no_change_event["state"] == "ready"),
            f"state={no_change_event['state'] if no_change_event else None}",
        ),
        Check(
            "semantic no-change event has null cause",
            bool(no_change_event and no_change_event["change_cause"] is None),
            f"change_cause={no_change_event['change_cause'] if no_change_event else None}",
        ),
        Check(
            "semantic no-change event has empty changeset",
            bool(no_change_event and int(no_change_event["changes"]) == 0),
            f"changes={no_change_event['changes'] if no_change_event else None}",
        ),
        Check(
            "semantic no-change revision is byte-distinct",
            no_change_hash_distinct,
            "revision B and parser-equivalent revision C have different blob hashes",
        ),
        Check(
            "no revision analysis failure masks accepted outcome",
            failure_count == 0,
            f"analysis_failures={failure_count}",
        ),
    ]
    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "from_revision_id": str(source_revision_id),
        "to_revision_id": str(target_revision_id),
        "no_change_target_revision_id": str(no_change_target_revision_id),
    }
    if event:
        identifiers["change_event_id"] = str(event["event_id"])
    if no_change_event:
        identifiers["no_change_event_id"] = str(no_change_event["event_id"])
    return checks, identifiers

async def verify(
    *,
    database_url: str,
    tenant_id: UUID,
    project_id: UUID,
    document_id: UUID,
    source_revision_id: UUID,
    target_revision_id: UUID | None,
    no_change_target_revision_id: UUID | None,
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
                if target_revision_id is None:
                    result = await verify_pre(
                        conn,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=document_id,
                        source_revision_id=source_revision_id,
                    )
                else:
                    if no_change_target_revision_id is None:
                        raise VerificationFailure(
                            "no-change target revision id required for post verification"
                        )
                    result = await verify_post(
                        conn,
                        tenant_id=tenant_id,
                        project_id=project_id,
                        document_id=document_id,
                        source_revision_id=source_revision_id,
                        target_revision_id=target_revision_id,
                        no_change_target_revision_id=no_change_target_revision_id,
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
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source-revision-id", required=True)
    parser.add_argument("--target-revision-id")
    parser.add_argument("--no-change-target-revision-id")
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url:
        raise SystemExit("FAIL: PROD_ACCEPTANCE_DATABASE_URL_READONLY missing")

    checks, identifiers = asyncio.run(
        verify(
            database_url=database_url,
            tenant_id=_uuid(args.tenant_id, "tenant id"),
            project_id=_uuid(args.project_id, "project id"),
            document_id=_uuid(args.document_id, "document id"),
            source_revision_id=_uuid(args.source_revision_id, "source revision id"),
            target_revision_id=(
                _uuid(args.target_revision_id, "target revision id")
                if args.target_revision_id
                else None
            ),
            no_change_target_revision_id=(
                _uuid(args.no_change_target_revision_id, "no-change target revision id")
                if args.no_change_target_revision_id
                else None
            ),
        )
    )
    verdict = "PASS" if all(check.passed for check in checks) else "FAIL"
    payload = {
        "schema": "c2pro-p0c-prod-verifier/v1",
        "verdict": verdict,
        "phase": "post" if args.target_revision_id else "pre",
        "identifiers": identifiers,
        "checks": [asdict(check) for check in checks],
    }
    print(json.dumps(payload, indent=2))
    if args.write_evidence:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if verdict == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
