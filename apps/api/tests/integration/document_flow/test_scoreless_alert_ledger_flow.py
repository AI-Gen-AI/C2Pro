"""A score-withheld ``POST /coherence/evaluate`` still keeps the alert ledger honest (ACC-01 #1110).

REAL PostgreSQL, REAL worker, REAL ``evaluate_project_coherence``. The positive case (the advisory is
persisted without a ``CoherenceResult``) lives in ``test_contract_schedule_completion_flow``; these
tests are the NEGATIVE side of the same contract:

* an earlier alert that an incomplete evaluation cannot reassess is NOT auto-resolved;
* a human decision on a persisted alert survives a scoreless re-evaluation;
* an equivalent re-evaluation never duplicates the alert;
* nothing is written for another project or tenant, and no trusted score artefact appears;
* the persisted alert keeps its approval state (still PENDING: a scoreless run approves nothing).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    COMPLETION_CLAUSE,
    LATE_SCHEDULE,
    PRICE_CLAUSE,
    PROVISIONAL_RULE,
    _evaluate,
    _project,
    _scenario,
    worker,  # noqa: F401  (pytest fixture)
)

pytestmark = pytest.mark.asyncio


async def _alerts(db: AsyncSession, project_id: Any, rule: str = PROVISIONAL_RULE) -> list[Any]:
    await db.commit()  # read what the endpoint made durable, not an open transaction
    return list(
        (
            await db.execute(
                text(
                    "SELECT id, tenant_id, project_id, status, approval_status, source_clause_id, "
                    "alert_metadata FROM alerts WHERE project_id = :p AND rule_id = :r"
                ),
                {"p": project_id, "r": rule},
            )
        ).all()
    )


async def _persist_advisory(
    db: AsyncSession, worker: Any, user: Any, *, approve_contract: bool = True
) -> tuple[Any, Any]:
    project_id, contract_doc, *_ = await _scenario(
        db, worker, user, contract=[PRICE_CLAUSE, COMPLETION_CLAUSE], schedule=LATE_SCHEDULE,
        approve_contract=approve_contract,
    )
    result = await _evaluate(db, user, project_id)
    assert result.overall_score is None, "the regression must exercise the score-withheld path"
    [row] = await _alerts(db, project_id)
    return project_id, row


async def test_a_scoreless_evaluation_keeps_the_advisory_pending_and_creates_no_score_artifact(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, row = await _persist_advisory(db, worker, test_user)

    assert row.tenant_id == test_user.tenant_id
    assert row.project_id == project_id
    assert str(row.status).lower() == "open"
    assert str(row.approval_status).lower() == "pending", "a scoreless run approves nothing"
    assert row.source_clause_id is not None, "provenance: the contract clause stays linked"
    assert row.alert_metadata["detection_evidence"]["claim"], "provenance: the evidence is persisted"
    for table in ("coherence_results", "analyses"):
        count = (
            await db.execute(text(f"SELECT count(*) FROM {table} WHERE project_id = :p"), {"p": project_id})
        ).scalar_one()
        assert count == 0, f"a withheld score must not fabricate a row in {table}"


async def test_an_equivalent_scoreless_reevaluation_does_not_duplicate_or_reopen(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, first = await _persist_advisory(db, worker, test_user)

    for _ in range(2):
        again = await _evaluate(db, test_user, project_id)
        assert again.overall_score is None

    [row] = await _alerts(db, project_id)  # still exactly one
    assert row.id == first.id, "the same durable finding is reused, not recreated"


async def test_a_human_decision_survives_a_scoreless_reevaluation(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, first = await _persist_advisory(db, worker, test_user)
    await db.execute(
        text("UPDATE alerts SET status = 'acknowledged' WHERE id = :i"), {"i": first.id}
    )
    await db.commit()

    again = await _evaluate(db, test_user, project_id)
    assert again.overall_score is None

    [row] = await _alerts(db, project_id)
    assert row.id == first.id
    assert str(row.status).lower() == "acknowledged", "an acknowledged finding is not reopened by identical evidence"


async def test_an_earlier_alert_is_not_resolved_by_an_evaluation_that_cannot_reassess_it(
    db: AsyncSession, worker: Any, test_user: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, first = await _persist_advisory(db, worker, test_user)

    # The next evaluation cannot assess the schedule at all (several schedule documents): the
    # advisory is no longer re-detected, but "not re-detected" is not "resolved".
    async def _unassessable(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"reason": "multiple_schedule_documents"}

    monkeypatch.setattr("src.coherence.router.load_schedule_planned_finish", _unassessable)
    again = await _evaluate(db, test_user, project_id)
    assert again.overall_score is None
    assert not [a for a in again.alerts if a.rule_id == PROVISIONAL_RULE], "premise: not re-detected"

    [row] = await _alerts(db, project_id)
    assert row.id == first.id
    assert str(row.status).lower() == "open", "an incomplete evaluation must not auto-resolve earlier findings"


async def test_scoreless_alerts_are_not_written_for_another_project_or_tenant(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    project_id, first = await _persist_advisory(db, worker, test_user)
    other_project = await _project(db, test_user.tenant_id)  # same tenant, no documents at all
    other_tenant_project = await _project(db, uuid4())  # different tenant

    with pytest.raises(HTTPException) as excinfo:  # no documents: nothing to evaluate, nothing to persist
        await _evaluate(db, test_user, other_project)
    assert excinfo.value.status_code == 404

    assert await _alerts(db, other_project) == []
    assert await _alerts(db, other_tenant_project) == []
    [row] = await _alerts(db, project_id)
    assert row.id == first.id
    assert row.tenant_id == test_user.tenant_id


async def test_an_unapproved_contract_keeps_the_alert_but_authorises_no_document_link(
    db: AsyncSession, worker: Any, test_user: Any
) -> None:
    """ACC-01 S4 (#1111) x #1110: the finding is durable, the deep link fails closed.

    Only a trusted-current (approved) clause may authorise the Alerts foreign key / document link; a
    contract still awaiting its review must not be linked as if it were approved evidence.
    """
    _project_id, row = await _persist_advisory(db, worker, test_user, approve_contract=False)

    assert str(row.status).lower() == "open"
    assert row.source_clause_id is None, "no source link from an unapproved contract"
    assert row.alert_metadata["detection_evidence"]["claim"], "the evidence text is still persisted"
