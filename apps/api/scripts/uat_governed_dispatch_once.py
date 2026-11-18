"""One-shot UAT analysis dispatcher, owner-authorized on 2026-11-18.

Only for the known failed synthetic-contract revision and exact isolated
Railway pilot. Requires three $5 N4 budget buckets, closed invalid review,
and zero prior N4 runs. An append-only dispatch-intent project event prevents
a second enqueue on an image restart. No human approval is performed.
"""
from __future__ import annotations

import asyncio
import json
import os
from uuid import UUID

import asyncpg
from celery import Celery

REVIEW_ID = UUID("490deaaf-548f-40c7-97be-979f308c1006")
SOURCE_SHA = "1b4bae3850ce160a825b0459ac6e9a3fec6f2a58"
INTENT_EVENT = "analysis.uat_dispatch_intent"


async def _verify_and_mark_intent() -> tuple[str, str, int]:
    if os.environ.get("C2PRO_UAT_SCOPE") != "pilot":
        raise RuntimeError("UAT dispatcher requires explicit pilot scope")
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        async with conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(774108633057::bigint)")
            row = await conn.fetchrow(
                """
                SELECT r.tenant_id, r.project_id, r.document_id,
                       r.current_status::text AS review_state,
                       d.filename, d.upload_status::text AS doc_state,
                       d.document_metadata, o.stage::text AS stage,
                       o.phase::text AS phase, o.generation, o.revision_id,
                       t.ai_budget_monthly, t.ai_spend_current,
                       t.ai_spend_reserved_usd
                  FROM public.review_items r
                  JOIN public.documents d ON d.id=r.document_id AND d.tenant_id=r.tenant_id
                  JOIN public.document_processing_operations o
                    ON o.document_id=r.document_id AND o.tenant_id=r.tenant_id
                  JOIN public.tenants t ON t.id=r.tenant_id
                 WHERE r.id=$1
                """,
                REVIEW_ID,
            )
            if row is None:
                raise RuntimeError("Exact UAT review not found")
            if row["review_state"] != "CLOSED":
                raise RuntimeError("Failed review has not been quarantined")
            if row["doc_state"] != "parsed_pending_analysis":
                raise RuntimeError("Document is not retryable")
            if row["filename"] != "triplet-contract.docx":
                raise RuntimeError("Unexpected source document")
            if row["stage"] != "ANALYSIS" or row["phase"] != "PENDING":
                raise RuntimeError("Analysis processing authority is not available")
            if row["revision_id"] is None:
                raise RuntimeError("Unpinned source revision")
            if (row["document_metadata"] or {}).get("analysis_last_attempt_incomplete") is not True:
                raise RuntimeError("No operator-confirmed failed prior analysis")
            if (
                float(row["ai_budget_monthly"]) != 5
                or float(row["ai_spend_current"]) != 0
                or float(row["ai_spend_reserved_usd"]) != 0
            ):
                raise RuntimeError("Global $5 UAT budget does not match authorization")

            await conn.execute(
                "SELECT set_config('app.current_tenant', $1, true)",
                str(row["tenant_id"]),
            )
            buckets = await conn.fetchval(
                """
                SELECT count(*) FROM public.n4_budget_buckets
                 WHERE tenant_id=$1
                   AND period_key=to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM')
                   AND cap_usd=5 AND spent_usd=0 AND reserved_usd=0
                   AND ((scope_kind='TENANT' AND scope_id=$1)
                      OR (scope_kind='PROJECT' AND scope_id=$2)
                      OR (scope_kind='DOCUMENT' AND scope_id=$3))
                """,
                row["tenant_id"], row["project_id"], row["document_id"],
            )
            if buckets != 3:
                raise RuntimeError("All three budget scopes must be ready")
            prior = await conn.fetchval(
                """
                SELECT count(*) FROM public.project_events
                 WHERE tenant_id=$1 AND project_id=$2 AND event_type=$3
                   AND payload->>'source_review_id'=$4
                """,
                row["tenant_id"], row["project_id"], INTENT_EVENT, str(REVIEW_ID),
            )
            if prior:
                raise RuntimeError("Dispatch already recorded for this review")
            existing = await conn.fetchval(
                """
                SELECT count(*) FROM public.n4_extraction_runs
                 WHERE tenant_id=$1 AND document_id=$2
                """,
                row["tenant_id"], row["document_id"],
            )
            if existing:
                raise RuntimeError("Existing N4 run; refuse duplicate inference")

            payload = {
                "source_review_id": str(REVIEW_ID),
                "document_id": str(row["document_id"]),
                "document_revision_id": str(row["revision_id"]),
                "sha": SOURCE_SHA,
                "generation": int(row["generation"]),
                "scope": "pilot",
                "cap_usd": 5,
                "state": "DISPATCH_INTENT",
            }
            await conn.execute(
                """
                INSERT INTO public.project_events
                    (event_id, project_id, tenant_id, event_type,
                     payload, actor, evidence_refs, occurred_at, created_at)
                VALUES
                    (gen_random_uuid(), $1, $2, $3, $4::jsonb,
                     'owner_authorized_20261118', '[]'::jsonb,
                     now() AT TIME ZONE 'utc', now() AT TIME ZONE 'utc')
                """,
                row["project_id"], row["tenant_id"], INTENT_EVENT, json.dumps(payload),
            )
            return (
                str(row["tenant_id"]),
                str(row["document_id"]),
                int(row["generation"]),
            )
    finally:
        await conn.close()


def main() -> None:
    tenant_id, document_id, generation = asyncio.run(_verify_and_mark_intent())
    app = Celery("c2pro-uat-one-shot", broker=os.environ["CELERY_BROKER_URL"])
    result = app.send_task(
        "documents.analyze_document",
        kwargs={
            "tenant_id": tenant_id,
            "document_id": document_id,
            "generation": generation,
        },
        queue="document_parsing",
    )
    print("C2PRO_UAT_ONE_SHOT_SENT=" + json.dumps({
        "task_id": str(result.id),
        "generation": generation,
        "source_code_sha": SOURCE_SHA,
        "scope": "pilot",
        "authorized_max_usd": 5,
    }), flush=True)


if __name__ == "__main__":
    main()
