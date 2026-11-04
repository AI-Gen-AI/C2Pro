"""#1104 (budget stated_total, coherent dashboard) and #1106 (contract completion vs schedule) together.

TS-INT-COH-INTEGRATION-001. The two changes touch the same worker (`ingestion_tasks._process`) and the
same coherence router. One project, real worker, real PostgreSQL, real `POST /coherence/evaluate`: the
uploaded budget's declared total reaches the contract-vs-budget rules AND the schedule's observed finish
reaches the provisional time advisory, in the same evaluation. No AI model is involved.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

import openpyxl
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.domain.models import DocumentType
from tests.integration.document_flow.test_contract_schedule_completion_flow import (  # noqa: F401 - fixture
    COMPLETION_CLAUSE,
    LATE_SCHEDULE,
    PRICE_CLAUSE,
    PROVISIONAL_RULE,
    RULE,
    _docx,
    _evaluate,
    _metadata,
    _project,
    _upload_and_ingest,
    _xlsx,
    worker,
)

pytestmark = pytest.mark.asyncio


def _budget_xlsx(total: float) -> bytes:
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["Item", "Quantity", "Unit", "Unit Price", "Total"])
    sheet.append(["Obra civil", 1, "ud", total, total])
    sheet.append(["Total presupuesto", None, None, None, total])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def test_the_budget_total_and_the_schedule_finish_both_reach_one_evaluation(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id = await _project(db, test_user.tenant_id)
    await _upload_and_ingest(
        db, worker, test_user, project_id, filename="contract.docx",
        content=_docx([PRICE_CLAUSE, COMPLETION_CLAUSE]), document_type=DocumentType.CONTRACT,
    )
    budget_doc, budget_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="budget.xlsx",
        content=_budget_xlsx(1_500_000), document_type=DocumentType.BUDGET,
    )
    schedule_doc, schedule_rev = await _upload_and_ingest(
        db, worker, test_user, project_id, filename="schedule.xlsx",
        content=_xlsx(LATE_SCHEDULE), document_type=DocumentType.SCHEDULE,
    )

    # Both worker observations are recorded for their own document type.
    declared = (await _metadata(db, budget_doc.id))["stated_total_by_revision"]
    assert declared[str(budget_rev.revision_id)]["total"] == 1_500_000
    assert (await _metadata(db, schedule_doc.id))["schedule_planned_finish"]["date"] == "2027-09-30"

    # P0: these are original XLSX observations, NOT procurement BOM or WBS
    # and NOT a trusted schedule/budget baseline. Both belong to the same
    # immutable revision the worker was asked to process.
    budget_source = (await db.execute(
        text("""
            SELECT source_locator, payload, revision_id
            FROM document_source_units
            WHERE tenant_id = CAST(:tenant AS uuid)
              AND project_id = CAST(:project AS uuid)
              AND document_id = CAST(:document AS uuid)
              AND revision_id = CAST(:revision AS uuid)
              AND family = 'budget'
        """),
        {
            "tenant": str(test_user.tenant_id),
            "project": str(project_id),
            "document": str(budget_doc.id),
            "revision": str(budget_rev.revision_id),
        },
    )).mappings().all()
    assert budget_source
    assert any(row["payload"]["kind"] == "line_item" for row in budget_source)
    assert all(row["source_locator"] for row in budget_source)
    assert all(row["revision_id"] == budget_rev.revision_id for row in budget_source)

    schedule_source = (await db.execute(
        text("""
            SELECT source_locator, payload, revision_id
            FROM document_source_units
            WHERE tenant_id = CAST(:tenant AS uuid)
              AND project_id = CAST(:project AS uuid)
              AND document_id = CAST(:document AS uuid)
              AND revision_id = CAST(:revision AS uuid)
              AND family = 'schedule'
        """),
        {
            "tenant": str(test_user.tenant_id),
            "project": str(project_id),
            "document": str(schedule_doc.id),
            "revision": str(schedule_rev.revision_id),
        },
    )).mappings().all()
    assert schedule_source
    assert all(row["payload"]["kind"] == "activity" for row in schedule_source)
    assert all(row["revision_id"] == schedule_rev.revision_id for row in schedule_source)
    assert all(row["source_locator"] for row in schedule_source)

    result = await _evaluate(db, test_user, project_id)

    rules = {alert.rule_id for alert in result.alerts}
    assert {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"} <= rules  # budget side (#1104)
    assert PROVISIONAL_RULE in rules  # time side (#1106), provisional
    assert RULE not in rules  # never a confirmed breach from a submitted schedule
    assert RULE not in {s.rule_id for s in result.finding_signals}
