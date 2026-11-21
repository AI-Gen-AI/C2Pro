"""Seed ONLY a disposable, real-PostgreSQL VS-1 browser QA fixture.

No PDF import, no inference, no legacy product data, no approval, no N12/HITL.
Every generated N4 finding is synthetic and explicitly not contract-verified.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import text

from src.core.database import close_db, get_raw_session, init_db
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from tests.e2e_seed.seed_wedge import (
    FOREIGN_PROJECT_ID,
    seed_wedge_e2e,
)

OUT = Path("../web/playwright-report/vs1-browser-fixture.json")


def _require_disposable() -> None:
    if os.getenv("ENVIRONMENT") != "test" or os.getenv("STORAGE_PROVIDER") != "local":
        raise RuntimeError("VS1_REQUIRES_TEST_LOCAL_STORAGE")
    if os.getenv("C2PRO_AI_MOCK") != "1" or os.getenv("C2PRO_EMBEDDINGS_MOCK") != "1":
        raise RuntimeError("VS1_REQUIRES_NO_PROVIDER_MODE")
    raw = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
    address = urlparse(raw)
    if (
        (address.hostname not in {"localhost", "127.0.0.1", "::1"})
        or (address.path.rstrip("/") != "/c2pro_test")
    ):
        raise RuntimeError("VS1_REQUIRES_DISPOSABLE_LOCAL_DATABASE")


async def seed() -> dict[str, object]:
    _require_disposable()
    await init_db()
    try:
        async with get_raw_session() as db:
            ids = await seed_wedge_e2e(db)
            tenant, project = ids["tenant_id"], ids["project_id"]
            # A separate document avoids the wedge's unrelated pre-existing HITL
            # review, which must not mask this isolated partial-N4 UI state.
            document_id, revision, run = uuid4(), uuid4(), uuid4()
            document = DocumentORM(
                id=document_id, tenant_id=tenant, project_id=project,
                document_type=DocumentType.CONTRACT,
                filename="vs1-synthetic-contract.pdf",
                storage_url=f"synthetic/vs1/{document_id}",
                file_size_bytes=10240, upload_status=DocumentStatus.PARSED_PENDING_ANALYSIS,
                created_by=ids["user_id"],
            )
            db.add(document)
            digest = hashlib.sha256(b"synthetic-N2-projection-for-VS1-no-real-contract").hexdigest()
            now = datetime.now(UTC).replace(tzinfo=None)
            document.upload_status = DocumentStatus.PARSED_PENDING_ANALYSIS
            document.document_metadata = {
                "analysis_last_attempt_incomplete": True,
                "analysis_blocker_code": "N4_PARTIAL_RESULTS",
                "analysis_n4_run_id": str(run),
                "analysis_n4_revision_id": str(revision),
                "analysis_n4_source_sha256": digest,
            }
            db.add(DocumentRevisionORM(
                revision_id=revision, document_id=document_id,
                tenant_id=tenant, project_id=project, rev_no=1,
                blob_hash="a" * 64, blob_key="synthetic/vs1/not-a-real-document",
                valid_from=now, created_at=now,
            ))
            await db.flush()
            bound = {
                "tenant": str(tenant), "project": str(project),
                "document": str(document_id), "revision": str(revision),
                "run": str(run), "source": digest,
            }
            await db.execute(text("""
                INSERT INTO public.document_processing_operations (
                    document_id, tenant_id, revision_id, generation, stage,
                    phase, fencing_token
                ) VALUES (
                    CAST(:document AS uuid), CAST(:tenant AS uuid),
                    CAST(:revision AS uuid), 2, 'ANALYSIS', 'FAILED', 1
                )
            """), bound)
            await db.execute(text("""
                INSERT INTO public.n4_extraction_runs (
                    run_id, tenant_id, project_id, document_id, document_revision_id,
                    source_sha256, config_sha256, generation, fencing_token,
                    status, total_windows, budget_cap_usd
                ) VALUES (
                    CAST(:run AS uuid), CAST(:tenant AS uuid),
                    CAST(:project AS uuid), CAST(:document AS uuid),
                    CAST(:revision AS uuid), :source, :config,
                    1, 1, 'PARTIAL', 2, 1.00
                )
            """), {**bound, "config": "b" * 64})
            await db.execute(text("""
                INSERT INTO public.n4_extraction_windows (
                    tenant_id, run_id, ordinal,
                    core_start, core_end, context_start, context_end,
                    context_sha256, findings_sha256, status, committed_at,
                    blocked_reason, unresolved_refs
                ) VALUES
                (CAST(:tenant AS uuid), CAST(:run AS uuid), 0,
                 0, 100, 0, 120,
                 :context, :result, 'BLOCKED', clock_timestamp(),
                 'REFERENCES_UNRESOLVED', '["Annex C"]'::jsonb),
                (CAST(:tenant AS uuid), CAST(:run AS uuid), 1,
                 100, 200, 80, 200,
                 :context, :result, 'EXAMINED', clock_timestamp(),
                 NULL, '[]'::jsonb)
            """), {**bound, "context": "c" * 64, "result": "d" * 64})
            for ordinal, title, quote, status in (
                (0, "FAT milestone exposure", "The FAT shall be inspected", "EXACT_MODEL_SAFE_MATCH"),
                (0, "Missing technical Annex", None, "MISSING_SOURCE_QUOTE"),
                (1, "Payment milestone", "Payment follows delivery", "EXACT_MODEL_SAFE_MATCH"),
                (1, "Delay liability", "Delay triggers damages", "EXACT_MODEL_SAFE_MATCH"),
            ):
                index = {"FAT milestone exposure": 0, "Missing technical Annex": 1,
                         "Payment milestone": 2, "Delay liability": 3}[title]
                ref = {
                    "document_revision_id": str(revision),
                    "source_sha256": digest,
                    "source_kind": "MODEL_SAFE_PROJECTION",
                    "evidence_status": status,
                    "analysis_span": [index * 40, index * 40 + len(quote)] if quote else None,
                }
                claim = {
                    "title": title,
                    "risk_reason": "Synthetic VS-1 UI-only evidence (not verified against a contract)",
                    "category": "contractual",
                    "clause_ref": "4.3",
                    "source_quote": quote,
                    "source_evidence_status": status,
                    "review_status": "PROPOSED",
                }
                await db.execute(text("""
                    INSERT INTO public.n4_candidate_findings (
                        finding_id, tenant_id, run_id, window_ordinal,
                        finding_key, source_refs, claim, candidate_state
                    ) VALUES (
                        CAST(:finding_id AS uuid), CAST(:tenant AS uuid),
                        CAST(:run AS uuid), :ordinal, :key,
                        CAST(:refs AS jsonb), CAST(:claim AS jsonb), 'PROPOSED'
                    )
                """), {
                    **bound, "finding_id": str(uuid4()), "ordinal": ordinal,
                    "key": hashlib.sha256(title.encode()).hexdigest(),
                    "refs": json.dumps([ref]), "claim": json.dumps(claim),
                })
            await db.execute(text("""
                INSERT INTO public.n4_usage_reservations (
                    reservation_id, tenant_id, run_id, window_ordinal,
                    idempotency_key, bucket_scopes, reserved_usd, spent_usd,
                    status, model_name, settled_at
                ) VALUES (
                    CAST(:reservation AS uuid), CAST(:tenant AS uuid),
                    CAST(:run AS uuid), 0, 'vs1-synthetic-receipt',
                    CAST(:scopes AS jsonb), 0.01, 0.01,
                    'SETTLED', 'test-no-provider', clock_timestamp()
                )
            """), {
                **bound, "reservation": str(uuid4()),
                "scopes": json.dumps(["TEST", "TEST", "TEST", "TEST"]),
            })
            await db.commit()
            return {
                "projectId": str(project), "documentId": str(document_id),
                "tenantId": str(tenant), "runId": str(run),
                "revisionId": str(revision), "foreignProjectId": str(FOREIGN_PROJECT_ID),
                "fixtureMode": "SYNTHETIC_N4_NO_MODEL", "findingsCount": 4,
                "preexistingReceipts": 1,
            }
    finally:
        await close_db()


if __name__ == "__main__":
    result = asyncio.run(seed())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("VS1_SYNTHETIC_DATA_SEEDED_NO_INFERENCE")
