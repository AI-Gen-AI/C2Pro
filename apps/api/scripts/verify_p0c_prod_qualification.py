#!/usr/bin/env python
"""Read-only verifier for #686 P0c production qualification.

Reads the bounded PJ-01 production run, then verifies the exact project,
document, revision lineage and persisted revision.changed event in a fresh
read-only database transaction. It never repairs state or emits credentials.
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


def _load_run(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise VerificationFailure("run evidence must be an object")
    facts = data.get("facts")
    if not isinstance(facts, dict):
        raise VerificationFailure("run evidence facts are missing")
    prod = facts.get("p0cProduction")
    if not isinstance(prod, dict):
        raise VerificationFailure("p0cProduction facts are missing")
    no_change = facts.get("p0cNoChange")
    if not isinstance(no_change, dict):
        raise VerificationFailure("p0cNoChange facts are missing")
    if facts.get("p0cReloginVerified") is not True:
        raise VerificationFailure("browser relogin durability was not proven")
    return data


async def _one(conn: AsyncConnection, sql: str, params: dict) -> object:
    result = await conn.execute(text(sql), params)
    return result.one_or_none()


async def verify(
    *,
    database_url: str,
    tenant_id: UUID,
    run: dict,
) -> tuple[list[Check], dict[str, str]]:
    facts = run["facts"]["p0cProduction"]
    project_id = _uuid(str(facts["projectId"]), "project id")
    document_id = _uuid(str(facts["documentId"]), "document id")
    source_revision_id = _uuid(str(facts["sourceRevisionId"]), "source revision id")
    target_revision_id = _uuid(str(facts["targetRevisionId"]), "target revision id")
    change_event_id = _uuid(str(facts["changeEventId"]), "change event id")
    no_change_facts = run["facts"]["p0cNoChange"]
    no_change_event_id = _uuid(str(no_change_facts["eventId"]), "no-change event id")
    no_change_target_revision_id = _uuid(
        str(no_change_facts["targetRevisionId"]), "no-change target revision id"
    )

    params = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "document_id": document_id,
        "source_revision_id": source_revision_id,
        "target_revision_id": target_revision_id,
        "change_event_id": change_event_id,
        "no_change_event_id": no_change_event_id,
        "no_change_target_revision_id": no_change_target_revision_id,
    }
    checks: list[Check] = []
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

                project = await _one(
                    conn,
                    """
                    SELECT id
                      FROM projects
                     WHERE id=:project_id AND tenant_id=:tenant_id
                       AND name LIKE 'P0c PROD %'
                    """,
                    params,
                )
                checks.append(Check("synthetic project scope", project is not None, f"project_found={project is not None}"))

                document = await _one(
                    conn,
                    """
                    SELECT id
                      FROM documents
                     WHERE id=:document_id AND project_id=:project_id
                       AND tenant_id=:tenant_id
                    """,
                    params,
                )
                checks.append(Check("document identity persisted", document is not None, f"document_found={document is not None}"))

                revisions = await conn.execute(
                    text(
                        """
                        SELECT revision_id, rev_no, parent_revision_id, blob_hash
                          FROM document_revisions
                         WHERE tenant_id=:tenant_id
                           AND project_id=:project_id
                           AND document_id=:document_id
                           AND revision_id IN (:source_revision_id, :target_revision_id)
                         ORDER BY rev_no
                        """
                    ),
                    params,
                )
                rows = revisions.all()
                revision_ids = {row.revision_id for row in rows}
                lineage_ok = (
                    len(rows) == 2
                    and source_revision_id in revision_ids
                    and target_revision_id in revision_ids
                    and rows[0].blob_hash != rows[1].blob_hash
                    and any(
                        row.revision_id == target_revision_id
                        and row.parent_revision_id == source_revision_id
                        for row in rows
                    )
                )
                checks.append(Check("two-revision immutable lineage", lineage_ok, f"matched_revisions={len(rows)}"))

                event = await _one(
                    conn,
                    """
                    SELECT event_id, event_type, source_revision_id, payload, evidence_refs
                      FROM project_events
                     WHERE event_id=:change_event_id
                       AND project_id=:project_id
                       AND tenant_id=:tenant_id
                    """,
                    params,
                )
                event_ok = event is not None and event.event_type == "revision.changed"
                checks.append(Check("durable revision.changed event", event_ok, f"event_found={event is not None}"))

                provenance_ok = False
                evidence_ok = False
                if event is not None:
                    payload = event.payload if isinstance(event.payload, dict) else {}
                    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
                    changeset = payload.get("changeset") if isinstance(payload.get("changeset"), dict) else {}
                    changes = changeset.get("changes") if isinstance(changeset.get("changes"), list) else []
                    provenance_ok = (
                        provenance.get("source_revision_id") == str(source_revision_id)
                        and provenance.get("target_revision_id") == str(target_revision_id)
                        and provenance.get("source_blob_hash")
                        and provenance.get("target_blob_hash")
                        and provenance.get("source_blob_hash") != provenance.get("target_blob_hash")
                    )
                    evidence_ok = bool(changes) and all(
                        isinstance(change, dict)
                        and isinstance(change.get("evidence_refs"), list)
                        and len(change["evidence_refs"]) > 0
                        for change in changes
                    )
                checks.append(Check("persisted provenance exact", bool(provenance_ok), "source/target ids and hashes bound"))
                checks.append(Check("persisted changes evidence-backed", evidence_ok, "every stored change has evidence refs"))

                no_change_event = await _one(
                    conn,
                    """
                    SELECT event_id, event_type, payload
                      FROM project_events
                     WHERE event_id=:no_change_event_id
                       AND project_id=:project_id
                       AND tenant_id=:tenant_id
                    """,
                    params,
                )
                no_change_ok = False
                no_change_hash_ok = False
                if no_change_event is not None and no_change_event.event_type == "revision.changed":
                    payload = no_change_event.payload if isinstance(no_change_event.payload, dict) else {}
                    changeset = payload.get("changeset") if isinstance(payload.get("changeset"), dict) else {}
                    changes = changeset.get("changes") if isinstance(changeset.get("changes"), list) else []
                    provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
                    no_change_ok = (
                        payload.get("change_cause") is None
                        and len(changes) == 0
                        and provenance.get("target_revision_id") == str(no_change_target_revision_id)
                    )

                    revision_rows = await conn.execute(
                        text(
                            """
                            SELECT revision_id, parent_revision_id, blob_hash
                              FROM document_revisions
                             WHERE tenant_id=:tenant_id
                               AND project_id=:project_id
                               AND document_id=:document_id
                               AND revision_id IN (:target_revision_id, :no_change_target_revision_id)
                            """
                        ),
                        params,
                    )
                    revision_map = {
                        row.revision_id: {
                            "parent_revision_id": row.parent_revision_id,
                            "blob_hash": row.blob_hash,
                        }
                        for row in revision_rows.all()
                    }
                    target_row = revision_map.get(target_revision_id)
                    no_change_row = revision_map.get(no_change_target_revision_id)
                    no_change_hash_ok = (
                        target_row is not None
                        and no_change_row is not None
                        and target_row["blob_hash"] != no_change_row["blob_hash"]
                    )
                    no_change_lineage_ok = (
                        no_change_row is not None
                        and no_change_row["parent_revision_id"] == target_revision_id
                    )
                checks.append(Check(
                    "identical reupload persisted as no change",
                    no_change_ok,
                    f"event_found={no_change_event is not None}",
                ))
                checks.append(Check(
                    "semantic no-change probe is byte-distinct",
                    no_change_hash_ok,
                    "revision B and metadata-only revision have different blob hashes",
                ))
                checks.append(Check(
                    "semantic no-change probe extends revision B",
                    no_change_lineage_ok,
                    "metadata-only revision parent is the accepted revision B",
                ))

                failed_after = await conn.execute(
                    text(
                        """
                        SELECT count(*)
                          FROM project_events
                         WHERE tenant_id=:tenant_id
                           AND project_id=:project_id
                           AND event_type='revision.analysis_failed'
                           AND occurred_at >= (
                               SELECT occurred_at FROM project_events
                                WHERE event_id=:change_event_id
                           )
                        """
                    ),
                    params,
                )
                failures = int(failed_after.scalar_one())
                checks.append(Check("no later failed revision masks outcome", failures == 0, f"later_failures={failures}"))

                await tx.rollback()
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()

    identifiers = {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "source_revision_id": str(source_revision_id),
        "target_revision_id": str(target_revision_id),
        "change_event_id": str(change_event_id),
        "no_change_event_id": str(no_change_event_id),
        "no_change_target_revision_id": str(no_change_target_revision_id),
    }
    return checks, identifiers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-json", required=True)
    parser.add_argument("--tenant-id", default=os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID"))
    parser.add_argument("--write-evidence", action="store_true")
    args = parser.parse_args()

    database_url = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    if not database_url or not args.tenant_id:
        print("FAIL: protected production qualification configuration is missing.", file=sys.stderr)
        return 2

    try:
        run_path = Path(args.run_json).resolve(strict=True)
        run = _load_run(run_path)
        checks, identifiers = asyncio.run(
            verify(
                database_url=database_url,
                tenant_id=_uuid(args.tenant_id, "tenant id"),
                run=run,
            )
        )
    except Exception as exc:
        print(f"FAIL: P0c verifier execution failed ({type(exc).__name__}).", file=sys.stderr)
        return 2

    failed = any(not check.passed for check in checks)
    for check in checks:
        print(f"{'PASS' if check.passed else 'FAIL'}: {check.name} ({check.detail})")

    if args.write_evidence:
        output = REPO_ROOT / OUTPUT
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
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
