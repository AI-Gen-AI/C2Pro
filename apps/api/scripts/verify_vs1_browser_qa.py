"""Verify FG-1a did not mutate the synthetic N4 ledger or promote approvals."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import text

from src.core.database import close_db, get_raw_session, init_db

FIXTURE = Path("../web/playwright-report/vs1-browser-fixture.json")


async def verify() -> None:
    url = urlparse(os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL") or "")
    if (
        os.getenv("ENVIRONMENT") != "test"
        or os.getenv("C2PRO_AI_MOCK") != "1"
        or url.hostname not in {"localhost", "127.0.0.1", "::1"}
        or url.path.rstrip("/") != "/c2pro_test"
    ):
        raise RuntimeError("VS1_VERIFY_REQUIRES_DISPOSABLE_TEST_DATABASE")
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    await init_db()
    try:
        async with get_raw_session() as db:
            common = {"run": fixture["runId"], "tenant": fixture["tenantId"]}
            stats = (await db.execute(text("""
                SELECT
                  (SELECT count(*) FROM public.n4_usage_reservations
                   WHERE run_id = CAST(:run AS uuid) AND tenant_id = CAST(:tenant AS uuid)) AS receipts,
                  (SELECT count(*) FROM public.n4_candidate_findings
                   WHERE run_id = CAST(:run AS uuid) AND tenant_id = CAST(:tenant AS uuid)
                   AND candidate_state = 'PROPOSED') AS proposed,
                  (SELECT count(*) FROM public.n4_extraction_windows
                   WHERE run_id = CAST(:run AS uuid) AND tenant_id = CAST(:tenant AS uuid)
                   AND status = 'BLOCKED') AS blocked
            """), common)).mappings().one()
            assert stats["receipts"] == fixture["preexistingReceipts"], "RECEIPTS_CHANGED"
            assert stats["proposed"] == fixture["findingsCount"], "FINDINGS_PROMOTED_OR_DROPPED"
            assert stats["blocked"] == 1, "WINDOW_STATE_CHANGED"
            print(json.dumps({
                "gate": "FG-1a",
                "scope": "DISPOSABLE_LOCAL_PG_ONLY",
                "receipts": stats["receipts"],
                "proposed": stats["proposed"],
                "blocked": stats["blocked"],
                "billable_model_calls": 0,
                "browser": "SEE_SEPARATE_PLAYWRIGHT_RESULT",
                "result": "LEDGER_UNCHANGED",
            }, sort_keys=True))
    finally:
        await close_db()


if __name__ == "__main__":
    asyncio.run(verify())
