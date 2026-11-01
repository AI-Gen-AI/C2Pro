"""S5-03 on PostgreSQL: the reconciler over the REAL ledger, behind the REAL per-project authority, under concurrency.

Read-only by construction: every test that reconciles also proves the review stays PENDING and nothing becomes TRUSTED.
The use of the result by the final approval (S5-04) and the revalidation of the grant at the first TRUSTED (S5-05) are
proven in ``test_s5_reconciled_approval_pg.py``; the last test here records that the former gap is closed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant
from src.modules.hitl.application.finding_reconciliation_service import (
    FindingReconciliationService,
    ReconciliationStale,
)
from src.modules.hitl.application.finding_review_authorization import FindingReviewerNotAuthorized
from src.modules.hitl.application.project_review_authorization import (
    ProjectAuthorizationDenied,
    ProjectCapability,
)
from src.modules.hitl.application.review_findings_view import ReviewFindingsUnavailable
from src.modules.hitl.domain.finding_decision import FindingDecisionAction as A
from src.modules.hitl.domain.finding_reconciliation import (
    AdvisoryCode,
    BlockerCode,
    DerivationCode,
    FindingResolution,
    ReconciliationStatus,
)
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_controlled_findings_pg import (  # noqa: F401
    controlled,
    no_risks,
)
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    _submission,
    world,  # noqa: F401
)
from tests.integration.document_flow.test_s5_project_authorization_evidence_pg import (
    _final,
    _footprint,
)
from tests.integration.document_flow.test_s5_project_review_authorization_pg import (  # noqa: F401
    APPROVE,
    FIND,
    READ,
    Actors,
    actors,
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


async def _decide(w: Any, user: Any, ordinal: int, expected: int, action: A = A.CONFIRMED, reason: str | None = None, **kw: Any) -> Any:
    from src.modules.hitl.adapters.http import finding_decision_router as findings

    reason = reason if reason is not None else (None if action is A.CONFIRMED else f"{action.value.lower()} reason")
    if action is A.CORRECTION_PROPOSED:
        kw.setdefault("proposed_text", "reworded finding")
    async with w.sessions(w.tenant_id) as session:
        receipt = await findings.record_finding_decision(
            w.review_row_id, _submission(w, ordinal=ordinal, expected=expected, action=action, reason=reason, **kw),
            current_user=user, session=session,
        )
        await session.commit()
        return receipt


async def _reconcile(w: Any, user: Any, *, capability: ProjectCapability = READ, lock: bool = False) -> Any:
    async with w.sessions(w.tenant_id) as session:
        result = await FindingReconciliationService(session).reconcile(
            tenant_id=w.tenant_id, user=user, review_row_id=w.review_row_id, capability=capability, lock=lock
        )
        await session.rollback()
        return result


async def _signer(actors: Actors) -> Any:  # noqa: F811
    person = await actors.user(label="reconciler")
    await actors.grant(person, READ, FIND, APPROVE)
    return person


# ── what each decision means ─────────────────────────────────────────────────────────────────────────────────
async def test_all_confirmed_is_signable_as_is_deterministic_across_sessions_and_changes_nothing(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    before = await _footprint(db, w)
    for ordinal in range(5):
        await _decide(w, person, ordinal, ordinal)
    results = [await _reconcile(w, person) for _ in range(3)]
    first = results[0]
    assert first.status is ReconciliationStatus.CONSISTENT and first.signable_as_is and first.ledger_revision == 5
    assert len(first.retained) == 5 and not first.excluded and not first.blockers and not first.derivations
    assert len({r.digest for r in results}) == 1, "the same ledger gives the same digest in every session"
    assert first.identity.artifact_hash == w.artifact_hash and first.identity.review_row_id == w.review_row_id
    after = await _footprint(db, w)
    assert after["review"] == "PENDING_REVIEW_REQUIRED" == before["review"]
    assert [t for _, t, *_ in after["artifacts"]] == [t for _, t, *_ in before["artifacts"]], "nothing became TRUSTED"
    assert after["project_events"] == before["project_events"] and after["resume_operations"] == before["resume_operations"]


async def test_the_four_actions_and_the_undecided_finding_map_to_exclusions_blockers_and_derivations(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0, A.CONFIRMED)
    await _decide(w, person, 1, 1, A.DISMISSED)
    await _decide(w, person, 2, 2, A.NEEDS_INFO)
    await _decide(w, person, 3, 3, A.CORRECTION_PROPOSED)
    r = await _reconcile(w, person)  # finding 4 has no decision
    by_ordinal = {o.ordinal: o for o in r.outcomes}
    assert [by_ordinal[i].resolution for i in range(5)] == [
        FindingResolution.RETAINED, FindingResolution.EXCLUDED, FindingResolution.BLOCKED_NEEDS_INFO,
        FindingResolution.CORRECTION_PENDING, FindingResolution.UNDECIDED,
    ]
    assert {b.code for b in r.blockers} == {BlockerCode.NEEDS_INFO, BlockerCode.UNDECIDED_FINDING}
    assert {d.code for d in r.derivations} == {DerivationCode.DISMISSED_EXCLUSION, DerivationCode.CORRECTION_PROPOSED}
    assert not r.signable_as_is and len(r.retained) == 1 and len(r.excluded) == 1
    assert by_ordinal[0].decisive and by_ordinal[0].decisive.reviewer_id == str(person.id), "the evidence names the human"

    # NEEDS_INFO is resolved only by a LATER decision; the history keeps both
    await _decide(w, person, 2, 4, A.CONFIRMED)
    await _decide(w, person, 4, 5, A.CONFIRMED)
    later = await _reconcile(w, person)
    assert {b.code for b in later.blockers} == set()
    assert [h.action for h in next(o for o in later.outcomes if o.ordinal == 2).history] == [A.NEEDS_INFO, A.CONFIRMED]
    assert later.digest != r.digest and later.ledger_revision == 6
    assert not later.signable_as_is, "the dismissal and the correction still require a derived candidate"


# ── project authority ────────────────────────────────────────────────────────────────────────────────────────
async def test_reconciliation_requires_the_project_capability_before_any_ledger_row_is_read(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0)

    stranger = await actors.user(label="stranger")
    with pytest.raises(ProjectAuthorizationDenied) as caught:
        await _reconcile(w, stranger)
    assert caught.value.visible is False, "no grant at all on the project: the review does not exist for them (404)"

    p2 = await actors.other_project()
    p2_person = await actors.user(label="p2")
    await actors.grant(p2_person, READ, FIND, APPROVE, project=p2)
    with pytest.raises(ProjectAuthorizationDenied) as caught:
        await _reconcile(w, p2_person)
    assert caught.value.visible is False, "fully granted on a DIFFERENT project of the same tenant: still a stranger"

    reviewer_only = await actors.user(label="reviewer-only")
    await actors.grant(reviewer_only, FIND)
    with pytest.raises(ProjectAuthorizationDenied) as caught:
        await _reconcile(w, reviewer_only)
    assert (caught.value.capability, caught.value.visible) == (READ, True), "REVIEW_FINDING does not imply READ_REVIEW (403)"

    reader = await actors.user(label="reader")
    await actors.grant(reader, READ)
    assert (await _reconcile(w, reader)).ledger_revision == 1
    with pytest.raises(ProjectAuthorizationDenied) as caught:
        await _reconcile(w, reader, capability=APPROVE)
    assert (caught.value.capability, caught.value.visible) == (APPROVE, True), "a signer needs APPROVE_CANDIDATE, not READ"

    viewer = await actors.user(label="viewer")
    viewer.role = type(person.role)("viewer")
    with pytest.raises(FindingReviewerNotAuthorized):
        await _reconcile(w, viewer)
    assert (await _footprint(db, w))["review"] == "PENDING_REVIEW_REQUIRED"


async def test_a_revocation_before_the_operation_is_effective_and_a_foreign_tenant_sees_nothing(
    db: AsyncSession, actors: Actors, independent_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="revoked")
    grants = await actors.grant(person, READ)
    assert (await _reconcile(w, person)).status is ReconciliationStatus.CONSISTENT
    await actors.revoke(grants[READ])
    with pytest.raises(ProjectAuthorizationDenied):
        await _reconcile(w, person)

    # another tenant's human, in ITS OWN tenant context, cannot reach this tenant's review (RLS + tenant-scoped SQL)
    other = Tenant(id=uuid4(), name="Other", slug=f"other-{uuid4().hex[:8]}", clerk_org_id=f"org_{uuid4().hex[:8]}", is_active=True, subscription_plan=SubscriptionPlan.STARTER)
    db.add(other)
    await db.commit()
    outsider = await actors.user(label="foreign", tenant_id=other.id)
    async with independent_sessions(other.id) as session:
        with pytest.raises(ReviewFindingsUnavailable):
            await FindingReconciliationService(session).reconcile(tenant_id=other.id, user=outsider, review_row_id=w.review_row_id)
        await session.rollback()


async def test_a_role_without_bypassrls_reads_only_its_own_tenant_through_rls(
    db: AsyncSession, actors: Actors, independent_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0)
    role = f"s503_reader_{uuid4().hex[:10]}"
    await db.execute(text(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS"))
    await db.execute(text(f"GRANT USAGE ON SCHEMA public TO {role}"))
    for table in ("review_items", "document_artifacts", "document_processing_operations", "hitl_finding_decisions", "project_review_grants", "tenants", "users"):
        await db.execute(text(f"GRANT SELECT ON public.{table} TO {role}"))
    await db.commit()
    try:
        assert (await db.execute(text("SELECT rolbypassrls FROM pg_roles WHERE rolname = :r"), {"r": role})).scalar_one() is False
        async with independent_sessions(w.tenant_id) as session:
            await session.execute(text(f"SET LOCAL ROLE {role}"))
            result = await FindingReconciliationService(session).reconcile(tenant_id=w.tenant_id, user=person, review_row_id=w.review_row_id)
            assert result.ledger_revision == 1 and result.status is ReconciliationStatus.CONSISTENT
            await session.rollback()
        # same role, ANOTHER tenant's context: the review row is invisible, whatever the SQL says
        async with independent_sessions(uuid4()) as session:
            await session.execute(text(f"SET LOCAL ROLE {role}"))
            raw = (await session.execute(text("SELECT count(*) FROM hitl_finding_decisions"))).scalar_one()
            assert raw == 0, "RLS partitions the ledger for a role that cannot bypass it"
            await session.rollback()
    finally:
        await db.rollback()
        await db.execute(text(f"DROP OWNED BY {role}"))
        await db.execute(text(f"DROP ROLE IF EXISTS {role}"))
        await db.commit()


# ── stale receipts and concurrency ───────────────────────────────────────────────────────────────────────────
async def test_a_receipt_goes_stale_when_a_decision_is_appended_and_not_otherwise(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    for ordinal in range(5):
        await _decide(w, person, ordinal, ordinal)
    receipt = (await _reconcile(w, person, capability=APPROVE)).receipt()
    assert receipt.signable_as_is and receipt.ledger_revision == 5

    async with w.sessions(w.tenant_id) as session:
        fresh = await FindingReconciliationService(session).verify_current(receipt, tenant_id=w.tenant_id, user=person, lock=False)
        assert fresh.digest == receipt.digest
        await session.rollback()

    await _decide(w, person, 0, 5, A.NEEDS_INFO)  # a later, material decision
    async with w.sessions(w.tenant_id) as session:
        with pytest.raises(ReconciliationStale):
            await FindingReconciliationService(session).verify_current(receipt, tenant_id=w.tenant_id, user=person, lock=False)
        await session.rollback()
    now = await _reconcile(w, person, capability=APPROVE)
    assert not now.signable_as_is and now.ledger_revision == 6 and now.digest != receipt.digest


async def test_a_receipt_goes_stale_when_the_candidates_processing_authority_moves(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    receipt = (await _reconcile(w, person, capability=APPROVE)).receipt()
    await db.execute(text("UPDATE review_items SET lineage_fencing_token = lineage_fencing_token + 1 WHERE id = :r"), {"r": w.review_row_id})
    await db.commit()
    async with w.sessions(w.tenant_id) as session:
        with pytest.raises(ReconciliationStale):
            await FindingReconciliationService(session).verify_current(receipt, tenant_id=w.tenant_id, user=person, lock=False)
        await session.rollback()


async def test_a_revocation_between_the_reconciliation_and_the_verification_is_a_denial_not_a_stale_receipt(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="signer")
    grants = await actors.grant(person, READ, APPROVE)
    receipt = (await _reconcile(w, person, capability=APPROVE)).receipt()
    await actors.revoke(grants[APPROVE])
    async with w.sessions(w.tenant_id) as session:
        with pytest.raises(ProjectAuthorizationDenied):
            await FindingReconciliationService(session).verify_current(receipt, tenant_id=w.tenant_id, user=person, lock=False)
        await session.rollback()


async def test_the_share_lock_holds_the_ledger_still_while_a_reconciliation_transaction_lives(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0)
    first_digest = (await _reconcile(w, person)).digest

    async with w.sessions(w.tenant_id) as locked:
        held = await FindingReconciliationService(locked).reconcile(
            tenant_id=w.tenant_id, user=person, review_row_id=w.review_row_id, lock=True
        )
        writer = asyncio.create_task(_decide(w, person, 1, 1))
        done, _ = await asyncio.wait({writer}, timeout=2.0)
        assert not done, "the ledger writer (FOR UPDATE on the review row) waits for the reconciliation transaction"
        assert held.ledger_revision == 1
        await locked.rollback()  # releases the lock
    receipt = await asyncio.wait_for(writer, timeout=15)
    assert receipt.ledger_revision == 2
    after = await _reconcile(w, person)
    assert after.ledger_revision == 2 and after.digest not in {first_digest, held.digest}


async def test_concurrent_reconciliations_agree_on_one_digest(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    for ordinal in range(3):
        await _decide(w, person, ordinal, ordinal)
    results = await asyncio.gather(*[_reconcile(w, person) for _ in range(6)])
    assert len({r.digest for r in results}) == 1 and {r.ledger_revision for r in results} == {3}


async def test_decisions_on_a_superseded_candidate_are_ignored_not_applied(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    """A ledger row recorded against another artifact hash of the same review is STALE: reported, never applied."""
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0)
    await db.execute(
        text("ALTER TABLE hitl_finding_decisions DISABLE TRIGGER USER"),
    )
    await db.execute(
        text("UPDATE hitl_finding_decisions SET artifact_hash = :h, action = 'DISMISSED', reason = 'obsolete' WHERE review_row_id = :r"),
        {"h": "b" * 64, "r": w.review_row_id},
    )
    await db.execute(text("ALTER TABLE hitl_finding_decisions ENABLE TRIGGER USER"))
    await db.commit()
    r = await _reconcile(w, person)
    assert r.status is ReconciliationStatus.CONSISTENT and len(r.stale_event_ids) == 1
    assert AdvisoryCode.STALE_DECISIONS_IGNORED in [a.code for a in r.advisories]
    assert not r.excluded, "the obsolete dismissal excludes nothing from the current candidate"
    assert {b.code for b in r.blockers} == {BlockerCode.UNDECIDED_FINDING}


async def test_a_tampered_ledger_is_inconsistent_and_concludes_nothing(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0)
    await _decide(w, person, 1, 1)
    await db.execute(text("ALTER TABLE hitl_finding_decisions DISABLE TRIGGER USER"))
    await db.execute(text("DELETE FROM hitl_finding_decisions WHERE review_row_id = :r AND ledger_revision = 1"), {"r": w.review_row_id})
    await db.execute(text("ALTER TABLE hitl_finding_decisions ENABLE TRIGGER USER"))
    await db.commit()
    r = await _reconcile(w, person)
    assert r.status is ReconciliationStatus.INCONSISTENT and not r.signable_as_is
    assert any(i.startswith("LEDGER_REVISIONS_NOT_CONTIGUOUS_FROM_1") for i in r.inconsistencies)
    assert r.outcomes == () and r.retained == ()


# ── S5-04 closed the gap S5-03 pinned ───────────────────────────────────────────────────────────────────────
async def test_the_gap_s503_pinned_is_closed_the_final_approval_now_depends_on_the_reconciliation(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    """S5-03 pinned (as a fact) that a NEEDS_INFO on the ledger did not stop today's approval. S5-04 flipped it: under
    enforce the approval is refused while the reconciliation blocks it (full matrix: test_s5_reconciled_approval_pg)."""
    from fastapi import HTTPException

    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0, A.NEEDS_INFO)
    assert not (await _reconcile(w, person, capability=APPROVE)).signable_as_is
    with pytest.raises(HTTPException) as refused:
        await _final(w, request_sessions, "approve", person)
    assert refused.value.status_code == 409 and refused.value.detail["code"] == "reconciliation_blocks_approval"
    assert (await _footprint(db, w))["review"] == "PENDING_REVIEW_REQUIRED"
