"""PQ-HITL-09 S7: one approved WBS, with a Budget and a Schedule in the same project.

#852 and #860 each prove their document type alone never writes canonical WBS or
BOM. S7 needs them together: a project with one human-approved WBS receives BOTH
a schedule and a budget, both go through the REAL upload use case and the REAL
ingestion worker (_process) against the test database, and the canonical
hierarchy must come out exactly as it went in.

Invariants exercised:
* ONE_CANONICAL_WBS_HIERARCHY: still exactly one root and the same rows.
* BUDGET_AND_SCHEDULE_REFERENCE_WBS_NOT_REPLACE_IT: no WBS node, RACI or BOM row
  is added, renumbered, relinked or sourced from either document.

NOT_ASSESSED_ON_DIFFERENT_CURRENCY_OR_TAX is covered within one budget revision
by tests/unit/analysis/test_budget_row_evidence.py. Across documents it is NOT
implemented: the contract/budget comparators in
src/coherence/cross_document/comparators.py compare bare totals and
ProjectCrossDocInputs.currency is "reserved for a future FX-mismatch guard".
That gap is reported, not asserted here. Matrix live_uat_status stays NOT_VERIFIED.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.tasks import ingestion_tasks
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (  # noqa: F401 - fixture
    SCHEDULE_V1,
    _canonical,
    _document_state,
    _human_wbs,
    _project,
    _upload_schedule,
    worker,
)
from tests.integration.document_flow.test_860_budget_bom_governance_guard import (
    BUDGET_V1,
    _upload_budget,
)

pytestmark = pytest.mark.asyncio


async def test_budget_and_schedule_reference_one_approved_wbs_without_replacing_it(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    tenant_id = test_user.tenant_id
    project_id = await _project(db, tenant_id)
    approved = await _human_wbs(db, tenant_id, project_id)
    before = await _canonical(db, project_id)
    assert len(before["wbs"]) == 2

    schedule, schedule_revision = await _upload_schedule(
        db, worker, test_user, project_id, SCHEDULE_V1
    )
    budget, budget_revision = await _upload_budget(db, worker, test_user, project_id, BUDGET_V1)

    schedule_result = await ingestion_tasks._process(schedule.id, schedule_revision.revision_id)
    budget_result = await ingestion_tasks._process(budget.id, budget_revision.revision_id)
    assert schedule_result["status"] == "success", schedule_result
    assert budget_result["status"] == "success", budget_result
    assert budget_result["details"]["extraction_summary"]["budget_lines"] == 2
    for document in (schedule, budget):
        assert (await _document_state(db, document.id))["status"] == "parsed_pending_analysis"

    # Same canonical rows, RACI and BOM links, byte for byte.
    assert await _canonical(db, project_id) == before

    roots = await db.execute(
        text("SELECT id FROM wbs_nodes WHERE project_id = :p AND parent_id IS NULL"),
        {"p": project_id},
    )
    assert [row[0] for row in roots] == [approved["root"]]

    sourced = await db.scalar(
        text("SELECT count(*) FROM wbs_nodes WHERE project_id = :p "
             "AND source_document_id IN (:s, :b)"),
        {"p": project_id, "s": schedule.id, "b": budget.id},
    )
    assert sourced == 0
    # Schedule codes ("2", "2.1") never became WBS identities next to the human "1".
    codes = await db.execute(
        text("SELECT code FROM wbs_nodes WHERE project_id = :p ORDER BY code"), {"p": project_id}
    )
    assert [row[0] for row in codes] == ["1", "1.1"]
