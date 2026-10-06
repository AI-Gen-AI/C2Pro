#!/usr/bin/env python3
"""Read-only fail-closed preflight for #686 partial-revision production recovery."""

from __future__ import annotations

import argparse
import asyncio
import os
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


class RecoveryPreflightFailure(RuntimeError):
    pass


def _db_url(raw: str) -> str:
    if raw.startswith("postgresql+asyncpg://"):
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+asyncpg://", 1)
    raise RecoveryPreflightFailure("database URL must use PostgreSQL")


async def verify(*, project_id: UUID, document_id: UUID, source_revision_id: UUID, recovery_revision_id: UUID) -> None:
    database_url = os.environ["PROD_ACCEPTANCE_DATABASE_URL_READONLY"]
    tenant_id = UUID(os.environ["PROD_ACCEPTANCE_EXPECTED_TENANT_ID"])
    engine = create_async_engine(_db_url(database_url))
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SET TRANSACTION READ ONLY"))
            await conn.execute(
                text("SELECT set_config('app.current_tenant', :tenant, true)"),
                {"tenant": str(tenant_id)},
            )
            p = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "document_id": document_id,
                "source_revision_id": source_revision_id,
                "recovery_revision_id": recovery_revision_id,
                "document_id_text": str(document_id),
                "source_revision_id_text": str(source_revision_id),
                "recovery_revision_id_text": str(recovery_revision_id),
            }
            row = (
                await conn.execute(
                    text(
                        """
                        SELECT
                          (SELECT count(*) FROM projects
                            WHERE id=:project_id AND tenant_id=:tenant_id) AS project_count,
                          (SELECT count(*) FROM documents
                            WHERE id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id) AS document_count,
                          (SELECT upload_status::text FROM documents
                            WHERE id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id) AS upload_status,
                          (SELECT count(*) FROM document_revisions
                            WHERE document_id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id) AS revision_count,
                          (SELECT count(*) FROM document_revisions
                            WHERE revision_id=:source_revision_id
                              AND document_id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id) AS source_count,
                          (SELECT count(*) FROM document_revisions
                            WHERE revision_id=:recovery_revision_id
                              AND parent_revision_id=:source_revision_id
                              AND document_id=:document_id AND project_id=:project_id AND tenant_id=:tenant_id
                              AND valid_to IS NULL) AS recovery_count,
                          (SELECT count(*) FROM clauses
                            WHERE tenant_id=:tenant_id AND project_id=:project_id
                              AND document_id=:document_id AND revision_id=:recovery_revision_id) AS recovery_clause_count,
                          (SELECT count(*) FROM project_events
                            WHERE tenant_id=:tenant_id AND project_id=:project_id
                              AND event_type='revision.changed'
                              AND payload->>'document_id'=:document_id_text
                              AND payload->'provenance'->>'source_revision_id'=:source_revision_id_text
                              AND payload->'provenance'->>'target_revision_id'=:recovery_revision_id_text) AS qualified_change_count
                        """
                    ),
                    p,
                )
            ).mappings().one()

            failures: list[str] = []
            if int(row["project_count"]) != 1:
                failures.append(f"project_count={row['project_count']}")
            if int(row["document_count"]) != 1:
                failures.append(f"document_count={row['document_count']}")
            if row["upload_status"] != "error":
                failures.append(f"upload_status={row['upload_status']}")
            revision_count = int(row["revision_count"])
            if revision_count != 2:
                failures.append(f"revision_count={revision_count}")
            if int(row["source_count"]) != 1:
                failures.append(f"source_count={row['source_count']}")
            if int(row["recovery_count"]) != 1:
                failures.append(f"recovery_count={row['recovery_count']}")
            recovery_clause_count = int(row["recovery_clause_count"])
            if recovery_clause_count != 0:
                failures.append(f"recovery_clause_count={recovery_clause_count}")
            if int(row["qualified_change_count"]) != 0:
                failures.append(f"qualified_change_count={row['qualified_change_count']}")

            if failures:
                raise RecoveryPreflightFailure("; ".join(failures))

            print(
                "P0C_RECOVERY_PREFLIGHT=PASS "
                f"source_revision_id={source_revision_id} "
                f"recovery_revision_id={recovery_revision_id} "
                f"revision_count={revision_count} "
                f"upload_status={row['upload_status']} "
                f"recovery_clause_count={recovery_clause_count}"
            )
    finally:
        await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", required=True, type=UUID)
    parser.add_argument("--document-id", required=True, type=UUID)
    parser.add_argument("--source-revision-id", required=True, type=UUID)
    parser.add_argument("--recovery-revision-id", required=True, type=UUID)
    args = parser.parse_args()
    asyncio.run(
        verify(
            project_id=args.project_id,
            document_id=args.document_id,
            source_revision_id=args.source_revision_id,
            recovery_revision_id=args.recovery_revision_id,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
