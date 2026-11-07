"""Real PostgreSQL SQL-shape verification for sanitized UAT S3 evidence.

Runs against an empty, random project/tenant: SELECT-only, no user/HITL data.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from scripts.verify_integral_s1_s8_pg import collect_s3_lineage_diagnostic


@pytest.mark.asyncio
async def test_s3_lineage_diagnostics_queries_real_postgres_without_raw_data(
    db: AsyncSession,
) -> None:
    report = await collect_s3_lineage_diagnostic(db, uuid4(), uuid4())
    assert report["schema"] == "c2pro-s3-lineage-diagnostic/v1"
    assert report["analyses_total"] == 0
    assert report["graph_completed_total"] == 0
    assert report["snapshots_total"] == 0
    assert report["latest_snapshot_assessment_count"] is None
    assert not any(k.endswith("_id") for k in report)
