#!/usr/bin/env python3
"""Read-only preflight for governed #686 P0c recovery of an existing failed revision B."""

from __future__ import annotations

import argparse
import asyncio
import os
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ASYNCPG_URL_PREFIX = "postgresql+asyncpg://"


def _url(raw: str) -> str:
    if raw.startswith(ASYNCPG_URL_PREFIX):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", ASYNCPG_URL_PREFIX, 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", ASYNCPG_URL_PREFIX, 1)
    raise SystemExit("FAIL: database URL must use PostgreSQL")


async def main_async(args: argparse.Namespace) -> None:
    db = os.getenv("PROD_ACCEPTANCE_DATABASE_URL_READONLY")
    tenant = os.getenv("PROD_ACCEPTANCE_EXPECTED_TENANT_ID")
    if not db or not tenant:
        raise SystemExit("FAIL: protected read-only DB/tenant prerequisite missing")

    engine = create_async_engine(_url(db))
    try:
        async with engine.connect() as conn:
            tx = await conn.begin()
            try:
                await conn.execute(text("SET TRANSACTION READ ONLY"))
                await conn.execute(
                    text("SELECT set_config('app.current_tenant', :tenant, true)"),
                    {"tenant": tenant},
                )
                p = {
                    "tenant": UUID(tenant),
                    "project": UUID(args.project_id),
                    "document": UUID(args.document_id),
                    "source": UUID(args.source_revision_id),
                    "target": UUID(args.target_revision_id),
                    "document_text": args.document_id,
                    "source_text": args.source_revision_id,
                    "target_text": args.target_revision_id,
                }
                revisions = (
                    await conn.execute(
                        text("""
                        SELECT revision_id, parent_revision_id, rev_no, valid_to
                          FROM document_revisions
                         WHERE tenant_id=:tenant AND project_id=:project
                           AND document_id=:document
                         ORDER BY rev_no
                        """),
                        p,
                    )
                ).mappings().all()
                doc = (
                    await conn.execute(
                        text("""
                        SELECT upload_status
                          FROM documents
                         WHERE tenant_id=:tenant AND project_id=:project AND id=:document
                        """),
                        p,
                    )
                ).mappings().one_or_none()
                op = (
                    await conn.execute(
                        text("""
                        SELECT revision_id, generation, stage, phase, outcome
                          FROM document_processing_operations
                         WHERE tenant_id=:tenant AND document_id=:document
                        """),
                        p,
                    )
                ).mappings().one_or_none()
                event_count = int(
                    (
                        await conn.execute(
                            text("""
                            SELECT count(*)
                              FROM project_events
                             WHERE tenant_id=:tenant AND project_id=:project
                               AND event_type='revision.changed'
                               AND payload->>'document_id'=:document_text
                               AND payload->'provenance'->>'source_revision_id'=:source_text
                               AND payload->'provenance'->>'target_revision_id'=:target_text
                            """),
                            p,
                        )
                    ).scalar_one()
                )

                failures: list[str] = []
                if len(revisions) != 2:
                    failures.append(f"expected exactly A+B revisions, got {len(revisions)}")
                else:
                    a, b = revisions
                    if a["revision_id"] != p["source"] or int(a["rev_no"]) != 1 or a["valid_to"] is None:
                        failures.append("revision A identity/lifecycle mismatch")
                    if (
                        b["revision_id"] != p["target"]
                        or b["parent_revision_id"] != p["source"]
                        or int(b["rev_no"]) != 2
                        or b["valid_to"] is not None
                    ):
                        failures.append("revision B identity/parent/current-state mismatch")
                if not doc or str(doc["upload_status"]) != "error":
                    failures.append(f"document must be error before recovery, got {doc}")
                if (
                    not op
                    or op["revision_id"] != p["target"]
                    or int(op["generation"]) != 2
                    or str(op["stage"]) != "INGESTION"
                    or str(op["phase"]) != "PENDING"
                    or str(op["outcome"]) != "ingestion_failed"
                ):
                    failures.append(f"processing authority is not the expected failed B state: {op}")
                if event_count != 0:
                    failures.append(f"A→B revision.changed must not pre-exist, got {event_count}")

                if failures:
                    raise SystemExit("FAIL: " + " | ".join(failures))
                print("P0C_RECOVERY_PREFLIGHT=PASS")
                print(f"TARGET_REVISION_ID={args.target_revision_id}")
                await tx.rollback()
            except Exception:
                await tx.rollback()
                raise
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--document-id", required=True)
    parser.add_argument("--source-revision-id", required=True)
    parser.add_argument("--target-revision-id", required=True)
    args = parser.parse_args()
    asyncio.run(main_async(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
