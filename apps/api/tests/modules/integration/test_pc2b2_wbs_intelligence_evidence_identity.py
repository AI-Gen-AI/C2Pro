"""PC-2b.2 (#921) Orchestrator finding -- the evidence-set identity of a deterministic run.

A run's ``evidence_set_digest`` must be the identity of the exact NORMALIZED WBS evidence-reference
set it was given (``normalize_evidence_refs``: opaque strings, whitespace trimmed, order and
duplicates irrelevant): the candidate's ``evidence_refs``, or the baseline's source change set's.
It is input identity, not evidence verification: EVIDENCE_COVERAGE stays NOT_EVALUATED.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.wbs.adapters.persistence.governance_models import WBSChangeSetORM
from src.wbs.application.governed_change_service import WBSGovernedChangeService
from src.wbs.intelligence.application.service import EVENT_RUN_COMPLETED, WBSIntelligenceService
from src.wbs.intelligence.contracts.run import TargetKind
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import Scope, _scope
from tests.modules.integration.test_pc2a2_wbs_governed_apply import (
    _approve,
    _events,
    _submit,
    _tree,
)

pytestmark = pytest.mark.asyncio


async def _draft(db: AsyncSession, s: Scope, refs: list[str]) -> UUID:
    change_set = await WBSGovernedChangeService(db).create_change_set(
        project_id=s.project, tenant_id=s.tenant, actor=s.author, title="WBS", evidence_refs=refs)
    change_set_id = change_set.id
    await db.commit()
    await _tree(db, s, change_set_id)
    return change_set_id


async def _run(db: AsyncSession, s: Scope, *, change_set_id: UUID | None = None, baseline_id: UUID | None = None
               ) -> Any:
    result = await WBSIntelligenceService(db).request_deterministic_run(
        project_id=s.project, tenant_id=s.tenant, actor=s.author,
        target_kind=TargetKind.CANDIDATE if change_set_id else TargetKind.BASELINE,
        change_set_id=change_set_id, baseline_id=baseline_id)
    await db.commit()
    return result


async def test_no_evidence_and_one_evidence_ref_have_different_identities(db: AsyncSession) -> None:
    # one scope, one target: only the attached evidence differs
    s = await _scope(db)
    change_set_id = await _draft(db, s, [])
    without = (await _run(db, s, change_set_id=change_set_id)).run
    await db.execute(update(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id)
                     .values(evidence_refs=["doc:contract-1"]))
    await db.commit()
    with_ref = (await _run(db, s, change_set_id=change_set_id)).run
    assert without.target_digest == with_ref.target_digest
    assert without.evidence_set_digest != with_ref.evidence_set_digest
    assert without.id != with_ref.id


async def test_the_identity_ignores_order_whitespace_and_duplicates(db: AsyncSession) -> None:
    from src.wbs.intelligence.application.service import wbs_evidence_set_digest

    assert wbs_evidence_set_digest([" doc:1 ", "doc:2", "doc:1"]) == wbs_evidence_set_digest(["doc:2", "doc:1"])
    assert wbs_evidence_set_digest([]) != wbs_evidence_set_digest(["doc:1"])
    assert wbs_evidence_set_digest(["doc:1"]) != wbs_evidence_set_digest(["doc:1", "doc:2"])
    a, b = await _scope(db), await _scope(db)
    first = (await _run(db, a, change_set_id=await _draft(db, a, [" doc:1 ", "doc:2", "doc:1"]))).run
    second = (await _run(db, b, change_set_id=await _draft(db, b, ["doc:2", "doc:1"]))).run
    assert first.evidence_set_digest == second.evidence_set_digest == wbs_evidence_set_digest(["doc:1", "doc:2"])


async def test_same_target_same_evidence_reuses_and_changed_evidence_is_a_new_run(db: AsyncSession) -> None:
    s = await _scope(db)
    change_set_id = await _draft(db, s, ["doc:1"])
    first = await _run(db, s, change_set_id=change_set_id)
    again = await _run(db, s, change_set_id=change_set_id)
    assert again.reused and again.run.id == first.run.id
    # the DRAFT's evidence changes without any structural edit: same target identity, other evidence
    await db.execute(update(WBSChangeSetORM).where(WBSChangeSetORM.id == change_set_id)
                     .values(evidence_refs=["doc:1", "doc:2"]))
    await db.commit()
    changed = await _run(db, s, change_set_id=change_set_id)
    assert (changed.run.target_digest, changed.run.target_change_set_revision) == (
        first.run.target_digest, first.run.target_change_set_revision)
    assert changed.run.evidence_set_digest != first.run.evidence_set_digest
    assert changed.run.idempotency_key != first.run.idempotency_key
    assert not changed.reused and changed.run.id != first.run.id


async def test_a_baseline_run_digests_its_source_change_sets_evidence(db: AsyncSession) -> None:
    from src.wbs.intelligence.application.service import wbs_evidence_set_digest

    s = await _scope(db)
    change_set_id = await _draft(db, s, ["doc:contract-1", "doc:spec-2"])
    await _submit(db, s, change_set_id)
    applied = await _approve(db, s, change_set_id)
    run = (await _run(db, s, baseline_id=applied.baseline_id)).run
    assert run.evidence_set_digest == wbs_evidence_set_digest(["doc:spec-2", "doc:contract-1"])
    assert run.evidence_set_digest != wbs_evidence_set_digest([])
    # candidate and baseline share one semantics: the same refs give the same identity
    other = await _scope(db)
    candidate = (await _run(db, other, change_set_id=await _draft(db, other, ["doc:spec-2", "doc:contract-1"]))).run
    assert candidate.evidence_set_digest == run.evidence_set_digest


async def test_the_stored_and_emitted_identity_match_and_qualification_is_unchanged(db: AsyncSession) -> None:
    from src.wbs.intelligence.application.service import wbs_evidence_set_digest

    s = await _scope(db)
    run = (await _run(db, s, change_set_id=await _draft(db, s, ["doc:1", "doc:2"]))).run
    assert run.evidence_set_digest == wbs_evidence_set_digest(["doc:1", "doc:2"])
    [event] = await _events(db, s.project, EVENT_RUN_COMPLETED)
    assert event.payload["evidence_set_digest"] == run.evidence_set_digest
    assert "doc:1" not in str(event.payload)  # digest only, never the references themselves
    coverage = next(r for r in run.qualification["results"] if r["dimension"] == "EVIDENCE_COVERAGE")  # type: ignore[index]
    assert coverage["status"] == "NOT_EVALUATED" and coverage["reason_code"] == "AI_QUALIFICATION_NOT_RUN"
    assert coverage["summary"].startswith("2 evidence reference(s)")  # refs present != evidence validated
