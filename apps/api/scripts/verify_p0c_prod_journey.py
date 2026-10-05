#!/usr/bin/env python
"""Read-only verifier for #686 P0c exact-runtime production qualification.

The verifier never repairs state. It is tenant/project/document scoped, runs in
an explicit read-only transaction, and emits only bounded non-secret evidence.
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
    raise VerificationFailure("database URL must use a PostgreSQL scheme")


def _uuid(raw: str, label: str) -> UUID:
    try:
        return UUID(raw)
    except (TypeError, ValueError) as exc:
        raise VerificationFailure(f"{label} must be a UUID") from exc


async def _scalar(conn: AsyncConnection, sql: str, params: dict[str, object]) -> int:
    return int((await conn.execute(text(sql), params)).scalar_one())


async def verify(
    *,
    database_url: str,
    tenant_id: UUID,
    clerk_org_id: str,
    project_id: UUID,
    document_id: UUID,
    expected_from_revision_id: UUID,
    expected_to_revision_id: UUID,
    expected_change_event_id: UUID,
) -> tuple[list[Check], dict[str, str]]:
    engine = create_async_engine(_normalize_database_url(database_url))
    p = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
    }
    checks: list[Check] = []
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
                    {"tenant_id": str(tenant_id)},
                )

                tenant_ok = await _scalar(
                    conn,
                    """
                    SELECT count(*) FROM tenants
                     WHERE id = :tenant_id
                       AND is_active IS TRUE
                       AND clerk_org_id = :clerk_org_id
                       AND coalesce((settings ->> 'synthetic_acceptance')::boolean, false) IS TRUE
                    """,
                    {"tenant_id": tenant_id, "clerk_org_id": clerk_org_id},
                )
                checks.append(Check("synthetic tenant binding", tenant_ok == 1, f"eligible_tenants={tenant_ok}"))

                project_ok = await _scalar(
                    conn,
                    """
                    SELECT count(*) FROM projects
                     WHERE id = :project_id AND tenant_id = :tenant_id
                       AND name LIKE 'ACCEPT-686-%'
                    """,
                    p,
                )
                checks.append(Check("bounded P0c project scope", project_ok == 1, f"projects={project_ok}"))

                documents = await _scalar(
                    conn,
                    """
                    SELECT count(*) FROM documents
                     WHERE id = :document_id AND project_id = :project_id AND tenant_id = :tenant_id
                    """,
                    p,
                )
                checks.append(Check("same logical document", documents == 1, f"documents={documents}"))

                revisions_result = await conn.execute(
                    text(
                        """
                        SELECT revision_id, parent_revision_id, blob_hash, rev_no
                          FROM document_revisions
                         WHERE document_id = :document_id
                           AND project_id = :project_id
                           AND tenant_id = :tenant_id
                         ORDER BY rev_no ASC
                        """
                    ),
                    p,
                )
                revisions = list(revisions_result.mappings())
                two_revisions = len(revisions) == 2
                checks.append(Check("exact two-revision lineage", two_revisions, f"revisions={len(revisions)}"))

                if two_revisions:
                    source, target = revisions
                    source_id = UUID(str(source["revision_id"]))
                    target_id = UUID(str(target["revision_id"]))
                    identity_ok = (
                        source_id == expected_from_revision_id
                        and target_id == expected_to_revision_id
                        and target["parent_revision_id"] == source["revision_id"]
                        and source["blob_hash"] != target["blob_hash"]
                        and int(source["rev_no"]) == 1
                        and int(target["rev_no"]) == 2
                    )
                    checks.append(
                        Check(
                            "revision identity and immutable blobs",
                            identity_ok,
                            f"source={source_id} target={target_id}",
                        )
                    )
                else:
                    checks.append(Check("revision identity and immutable blobs", False, "lineage_not_exactly_two"))

                event_result = await conn.execute(
                    text(
                        """
                        SELECT event_id, source_revision_id, payload, evidence_refs
                          FROM project_events
                         WHERE event_id = :event_id
                           AND project_id = :project_id
                           AND tenant_id = :tenant_id
                           AND event_type = 'revision.changed'
                        """
                    ),
                    {**p, "event_id": expected_change_event_id},
                )
                event = event_result.mappings().one_or_none()
                checks.append(Check("durable revision.changed event", event is not None, f"event_found={event is not None}"))

                payload: dict[str, object] = dict(event["payload"]) if event is not None and isinstance(event["payload"], dict) else {}
                provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
                changeset = payload.get("changeset") if isinstance(payload.get("changeset"), dict) else {}
                changes = changeset.get("changes") if isinstance(changeset, dict) else None

                provenance_ok = bool(
                    event is not None
                    and event["source_revision_id"] == expected_to_revision_id
                    and provenance.get("source_revision_id") == str(expected_from_revision_id)
                    and provenance.get("target_revision_id") == str(expected_to_revision_id)
                    and isinstance(provenance.get("source_blob_hash"), str)
                    and isinstance(provenance.get("target_blob_hash"), str)
                    and provenance.get("source_blob_hash") != provenance.get("target_blob_hash")
                )
                checks.append(Check("semantic change source traceable", provenance_ok, "revision/blob provenance bound"))

                outcome_ok = (
                    payload.get("state") == "ready"
                    and payload.get("change_cause") == "BUSINESS_STATE_CHANGED"
                    and isinstance(changes, list)
                    and len(changes) > 0
                )
                checks.append(Check("timeline outcome is actionable", outcome_ok, f"state={payload.get('state')} cause={payload.get('change_cause')}"))

                evidence_backed = bool(
                    isinstance(changes, list)
                    and changes
                    and all(
                        isinstance(change, dict)
                        and isinstance(change.get("evidence_refs"), list)
                        and len(change.get("evidence_refs")) > 0
                        for change in changes
                    )
                )
                checks.append(Check("all semantic changes carry evidence", evidence_backed, f"changes={len(changes) if isinstance(changes, list) else 0}"))

                duplicate_events = await _scalar(
                    conn,
                    """
                    SELECT count(*) FROM project_events
                     WHERE project_id = :project_id
                       AND tenant_id = :tenant_id
                       AND event_type = 'revision.changed'
                       AND source_revision_id = :to_revision_id
                    """,
                    {**p, "to_revision_id": expected_to_revision_id},
                )
                checks.append(Check("single original comparison event", duplicate_events == 1, f"events={duplicate_events}"))

                await tx.rollback()
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()

    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "from_revision_id": str(expected_from_revision_id),
        "to_revision_id": str(expected_to_revision_id),
        "change_event_id": str(expected_change_event_id),
    }
    return checks, identifiers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--clerk-org-id", default=os.getenv("PROD_ACCEPTANCE_CLERK_ORGANIZATION_ID"))
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--from-revision-id", required=True)
    parser.add_argument("--to-revision-id", required=True)
    parser.add_argument("--change-event-id", required=True)
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id or not args.clerk_org_id:
        print("FAIL: required production qualification configuration is missing.", file=sys.stderr)
        return 2

    try:
        checks, identifiers = asyncio.run(
            verify(
                database_url=database_url,
                tenant_id=_uuid(args.tenant_id, "tenant id"),
                clerk_org_id=args.clerk_org_id,
                project_id=_uuid(args.project_id, "project id"),
                document_id=_uuid(args.document_id, "document id"),
                expected_from_revision_id=_uuid(args.from_revision_id, "from revision id"),
                expected_to_revision_id=_uuid(args.to_revision_id, "to revision id"),
                expected_change_event_id=_uuid(args.change_event_id, "change event id"),
            )
        )
    except Exception as exc:
        print(f"FAIL: P0c verifier execution failed ({type(exc).__name__}).", file=sys.stderr)
        return 2

    failed = False
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(f"{state}: {check.name} ({check.detail})")
        failed = failed or not check.passed

    if args.write_evidence:
        out = REPO_ROOT / OUTPUT
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "verdict": "FAIL" if failed else "PASS",
                    "identifiers": identifiers,
                    "checks": [
                        {"name": c.name, "passed": c.passed, "detail": c.detail}
                        for c in checks
                    ],
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
