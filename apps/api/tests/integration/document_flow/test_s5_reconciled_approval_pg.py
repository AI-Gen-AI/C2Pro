"""S5-04 + S5-05 on PostgreSQL: the final approval is bound to a CURRENT reconciliation, and the grant is revalidated
inside the transaction that materializes the first TRUSTED.

Scope, stated so nothing is over-read:

* S5-04  under ``enforce`` an approval of a candidate-bound analysis review needs a reconciliation that is consistent,
  has no blocker (NEEDS_INFO, undecided finding, material verified open critique) and needs no derived candidate. It is
  refused BEFORE any resume operation exists. Provisional decisions, the approval and the TRUSTED promotion stay three
  separate acts. ``off`` / ``audit`` keep the legacy rule (transitional, NOT secure).
* S5-05  the approver's APPROVE_CANDIDATE grant, the decider's membership and the reconciliation digest are
  revalidated INSIDE the transaction that commits the first TRUSTED (FOR SHARE on grant and review rows): a revocation
  between the check and the promotion is rejected with no partial promotion; a revocation racing the promotion waits.
* NOT claimed: that a grant was issued by an authenticated human administrator (P1 SQL administrative authority:
  NOT_VERIFIED), derived-candidate (Vn+1) production (NOT_IMPLEMENTED), typed critique (UNEVALUATED).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import Tenant
from src.modules.hitl.application import resume_workflow_use_case as resume_module
from src.modules.hitl.domain.finding_decision import FindingDecisionAction as A
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
from tests.integration.document_flow.test_s5_finding_reconciliation_pg import _decide
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
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
    _sweep,
    independent_sessions,  # noqa: F401
)

pytestmark = pytest.mark.asyncio


def _spy_on_promotion_revalidation(monkeypatch: pytest.MonkeyPatch) -> list[BaseException | None]:
    """Records what ``revalidate_at_promotion`` did, so a refusal is attributed to S5-05 and not to some unrelated failure."""
    from src.modules.hitl.application import approval_authority

    outcomes: list[BaseException | None] = []
    real = approval_authority.revalidate_at_promotion

    async def spy(*args: Any, **kwargs: Any) -> None:
        try:
            await real(*args, **kwargs)
        except BaseException as exc:
            outcomes.append(exc)
            raise
        outcomes.append(None)

    monkeypatch.setattr(approval_authority, "revalidate_at_promotion", spy)
    return outcomes


def _trusted(footprint: dict[str, Any]) -> int:
    return [t for _, t, *_ in footprint["artifacts"]].count("trusted")


async def _signer(actors: Actors) -> Any:  # noqa: F811
    person = await actors.user(label="signer")
    await actors.grant(person, READ, FIND, APPROVE)
    return person


async def _confirm_all(w: Any, person: Any, *, skip: set[int] = frozenset()) -> int:  # type: ignore[assignment]
    expected = 0
    for ordinal in range(5):
        if ordinal in skip:
            continue
        await _decide(w, person, ordinal, expected)
        expected += 1
    return expected


async def _refused(w: Any, maker: Any, route: str, person: Any) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        await _final(w, maker, route, person)
    return caught.value


def _code(exc: HTTPException) -> str:
    return exc.detail["code"] if isinstance(exc.detail, dict) else str(exc.detail)


# ═══ S5-04 ═════════════════════════════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("route", ["approve", "resume"])
@pytest.mark.parametrize("case", ["needs_info", "undecided", "dismissed", "correction_proposed"])
async def test_s504_an_approval_is_refused_while_the_reconciliation_blocks_it_and_nothing_changes(
    db: AsyncSession, actors: Actors, request_sessions: Any, route: str, case: str  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    if case == "undecided":
        await _confirm_all(w, person, skip={4})
    else:
        expected = await _confirm_all(w, person, skip={4})
        action = {"needs_info": A.NEEDS_INFO, "dismissed": A.DISMISSED, "correction_proposed": A.CORRECTION_PROPOSED}[case]
        await _decide(w, person, 4, expected, action)
    before = await _footprint(db, w)

    refusal = await _refused(w, request_sessions, route, person)
    assert (refusal.status_code, _code(refusal)) == (409, "reconciliation_blocks_approval"), (case, refusal.detail)
    after = await _footprint(db, w)
    assert after == before, "refused BEFORE any resume operation, analysis, event or trust change"
    assert after["resume_operations"] == 0 and _trusted(after) == 0 and after["review"] == "PENDING_REVIEW_REQUIRED"


async def test_s504_a_clean_reconciliation_approves_and_only_the_approval_promotes_to_trusted(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _confirm_all(w, person)
    provisional = await _footprint(db, w)
    assert _trusted(provisional) == 0 and provisional["review"] == "PENDING_REVIEW_REQUIRED", "intent alone trusts nothing"
    await _final(w, request_sessions, "approve", person)
    final = await _footprint(db, w)
    assert final["review"] == "APPROVED" and _trusted(final) == 1


async def test_s504_a_later_decision_that_supersedes_needs_info_unblocks_the_approval(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    expected = await _confirm_all(w, person, skip={4})
    await _decide(w, person, 4, expected, A.NEEDS_INFO)
    assert (await _refused(w, request_sessions, "approve", person)).status_code == 409
    await _decide(w, person, 4, expected + 1, A.CONFIRMED)
    await _final(w, request_sessions, "approve", person)
    assert (await _footprint(db, w))["review"] == "APPROVED"


async def test_s504_rejection_never_needs_the_reconciliation(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _decide(w, person, 0, 0, A.NEEDS_INFO)
    await _final(w, request_sessions, "reject", person)
    final = await _footprint(db, w)
    assert final["review"] == "REJECTED" and _trusted(final) == 0


@pytest.mark.parametrize("mode", ["off", "audit"])
async def test_s504_off_and_audit_keep_the_legacy_rule_and_are_declared_transitional(
    db: AsyncSession, actors: Actors, request_sessions: Any, mode: str  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="legacy")
    await actors.mode(mode)
    await _decide(w, person, 0, 0, A.NEEDS_INFO)  # legacy rule: any active human of the tenant
    await _final(w, request_sessions, "approve", person)
    assert (await _footprint(db, w))["review"] == "APPROVED", f"{mode}: NOT secure, by design and documented"


# ═══ S5-05 ═════════════════════════════════════════════════════════════════════════════════════════════════════
async def test_s505_a_grant_revoked_between_the_check_and_the_promotion_rejects_the_promotion(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="revoked-midway")
    grants = await actors.grant(person, READ, FIND, APPROVE)
    await _confirm_all(w, person)
    real_acquire = resume_module.acquire

    async def acquire_then_revoke(**kwargs: Any) -> Any:
        outcome = await real_acquire(**kwargs)  # the pre-check passed and the operation is owned...
        await actors.revoke(grants[APPROVE])  # ...and only now is the grant revoked
        return outcome

    monkeypatch.setattr(resume_module, "acquire", acquire_then_revoke)
    outcomes = _spy_on_promotion_revalidation(monkeypatch)
    before = await _footprint(db, w)
    refusal = await _refused(w, request_sessions, "approve", person)
    # N17 runs inside the graph's save node, which reports ANY failure of its transaction as "did not reach durable
    # persistence" (502, review unchanged and retryable): the safety property is the state, asserted below.
    assert refusal.status_code in {403, 409, 502}, refusal.detail
    assert [type(o).__name__ for o in outcomes] == ["PromotionNotAuthorized"], "refused by S5-05, inside the promotion transaction"
    assert "no longer holds APPROVE_CANDIDATE" in str(outcomes[0])
    last_error = (await db.execute(text("SELECT last_error FROM resume_operations WHERE review_row_id = :r"), {"r": w.review_row_id})).scalar_one()
    assert last_error, "the failure is recorded on the operation, retryable once authorized"
    after = await _footprint(db, w)
    assert _trusted(after) == 0 == _trusted(before), "no TRUSTED state"
    assert after["review"] == "PENDING_REVIEW_REQUIRED" and after["analyses"] == before["analyses"], "no partial promotion"


async def test_s505_a_decider_who_stops_being_an_active_member_before_the_promotion_is_rejected(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    await _confirm_all(w, person)
    real_acquire = resume_module.acquire

    async def acquire_then_deactivate(**kwargs: Any) -> Any:
        outcome = await real_acquire(**kwargs)
        await db.execute(text("UPDATE users SET is_active = false WHERE id = :u"), {"u": person.id})
        await db.commit()
        return outcome

    monkeypatch.setattr(resume_module, "acquire", acquire_then_deactivate)
    outcomes = _spy_on_promotion_revalidation(monkeypatch)
    await _refused(w, request_sessions, "approve", person)
    assert [type(o).__name__ for o in outcomes] == ["PromotionNotAuthorized"] and "no longer an active human member" in str(outcomes[0])
    after = await _footprint(db, w)
    assert _trusted(after) == 0 and after["review"] == "PENDING_REVIEW_REQUIRED"


async def test_s505_the_reconciliation_going_stale_between_the_check_and_the_promotion_rejects_it(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    w, person = actors.w, await _signer(actors)
    expected = await _confirm_all(w, person)
    real_acquire = resume_module.acquire

    async def acquire_then_append(**kwargs: Any) -> Any:
        outcome = await real_acquire(**kwargs)
        await _decide(w, person, 0, expected, A.NEEDS_INFO)  # a material decision lands after the check
        return outcome

    monkeypatch.setattr(resume_module, "acquire", acquire_then_append)
    outcomes = _spy_on_promotion_revalidation(monkeypatch)
    await _refused(w, request_sessions, "approve", person)
    assert [type(o).__name__ for o in outcomes] == ["PromotionNotAuthorized"] and "reconciliation" in str(outcomes[0]) and "stale" in str(outcomes[0])
    after = await _footprint(db, w)
    assert _trusted(after) == 0 and after["review"] == "PENDING_REVIEW_REQUIRED"


async def test_s505_a_failure_after_the_promotion_statement_leaves_no_trusted_state_and_a_retry_succeeds(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )

    w, person = actors.w, await _signer(actors)
    await _confirm_all(w, person)
    real_commit = SqlAlchemyDocumentArtifactRepository.commit_candidate
    calls = {"n": 0}

    async def commit_then_fail(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = await real_commit(self, *args, **kwargs)
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected failure after the promotion statement")
        return result

    monkeypatch.setattr(SqlAlchemyDocumentArtifactRepository, "commit_candidate", commit_then_fail)
    with pytest.raises(Exception):  # noqa: B017 - any failure surface (502 / propagated) is acceptable here
        await _final(w, request_sessions, "approve", person)
    failed = await _footprint(db, w)
    assert _trusted(failed) == 0 and failed["review"] == "PENDING_REVIEW_REQUIRED", "the whole transaction rolled back"
    await _final(w, request_sessions, "approve", person)
    assert _trusted(await _footprint(db, w)) == 1, "the retry promotes exactly once"


async def test_s505_a_revocation_racing_the_promotion_waits_for_it_and_cannot_slip_in_between(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from src.analysis.adapters.persistence.document_artifact_repository import (
        SqlAlchemyDocumentArtifactRepository,
    )

    w = actors.w
    person = await actors.user(label="racing")
    grants = await actors.grant(person, READ, FIND, APPROVE)
    await _confirm_all(w, person)
    real_commit = SqlAlchemyDocumentArtifactRepository.commit_candidate
    inside, release = asyncio.Event(), asyncio.Event()

    async def hold_inside_the_transaction(self: Any, *args: Any, **kwargs: Any) -> Any:
        inside.set()  # the grant was revalidated FOR SHARE just before this statement
        await asyncio.wait_for(release.wait(), timeout=30)
        return await real_commit(self, *args, **kwargs)

    monkeypatch.setattr(SqlAlchemyDocumentArtifactRepository, "commit_candidate", hold_inside_the_transaction)
    approval = asyncio.create_task(_final(w, request_sessions, "approve", person))
    await asyncio.wait_for(inside.wait(), timeout=60)
    revocation = asyncio.create_task(actors.revoke(grants[APPROVE]))
    done, _ = await asyncio.wait({revocation}, timeout=2.0)
    assert not done, "the revocation (an UPDATE of the grant row) waits for the promotion transaction"
    release.set()
    await asyncio.wait_for(approval, timeout=60)
    await asyncio.wait_for(revocation, timeout=30)
    assert _trusted(await _footprint(db, w)) == 1, "the promotion committed under the grant that was valid inside its transaction"
    still = (await db.execute(text("SELECT count(*) FROM project_review_grants WHERE grant_id = :g AND revoked_at IS NOT NULL"), {"g": grants[APPROVE]})).scalar_one()
    assert still == 1, "and the revocation took effect right after"


async def test_s505_under_enforce_a_promotion_without_a_recorded_authority_fails_closed(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """The operation was claimed under the legacy rule (no authority recorded) and the tenant became enforce afterwards."""
    w = actors.w
    person = await actors.user(label="late-enforce")
    await actors.mode("off")
    await _decide(w, person, 0, 0)
    real_acquire = resume_module.acquire

    async def acquire_then_enforce(**kwargs: Any) -> Any:
        outcome = await real_acquire(**kwargs)
        await actors.mode("enforce")
        await actors.grant(person, READ, FIND, APPROVE)
        return outcome

    monkeypatch.setattr(resume_module, "acquire", acquire_then_enforce)
    outcomes = _spy_on_promotion_revalidation(monkeypatch)
    await _refused(w, request_sessions, "approve", person)
    assert [type(o).__name__ for o in outcomes] == ["PromotionNotAuthorized"] and "no approval authority was recorded" in str(outcomes[0])
    after = await _footprint(db, w)
    assert _trusted(after) == 0 and after["review"] == "PENDING_REVIEW_REQUIRED"


async def test_rel01_crash_after_acquire_recovers_the_original_enforce_authority(
    db: AsyncSession, actors: Actors, request_sessions: Any, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """A hard death after ``acquire`` must leave the original receipt durable for recovery.

    The fault is deliberately at the old ``acquire() -> record_authority()``
    boundary.  The reconciler is real and runs only after the database lease
    expires, so this proves the committed state rather than a mocked handoff.
    """
    from src.core.tasks import hitl_resume_reconciler as reconciler

    w = actors.w
    person = await actors.user(label="rel01-signer")
    grants = await actors.grant(person, READ, FIND, APPROVE)
    await _confirm_all(w, person)
    real_acquire = resume_module.acquire
    crashed = False

    async def acquire_then_crash(**kwargs: Any) -> Any:
        nonlocal crashed
        await real_acquire(**kwargs)
        crashed = True
        raise BaseException("REL-01 simulated power loss after acquire")  # noqa: TRY002

    monkeypatch.setattr(resume_module, "acquire", acquire_then_crash)
    with pytest.raises(BaseException, match="REL-01 simulated power loss"):
        await _final(w, request_sessions, "approve", person)
    assert crashed, "the operation was acquired before the simulated crash"

    async with w.sessions(w.tenant_id) as session:
        await session.execute(
            text(
                "UPDATE resume_operations "
                "SET lease_expires_at = clock_timestamp() - interval '1 hour', "
                "    heartbeat_at = clock_timestamp() - interval '1 hour' "
                "WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(w.review_row_id)},
        )

    tenant = await db.get(Tenant, w.tenant_id)
    assert tenant is not None
    swept = await _sweep(reconciler, w.sessions, tenant, w.saver, w.app)
    assert swept["scanned"] == 1 and swept["recovered"] == 1, swept

    after = await _footprint(db, w)
    assert after["review"] == "APPROVED" and _trusted(after) == 1
    authority = (
        await db.execute(
            text(
                "SELECT operation_metadata -> 'authority' "
                "FROM resume_operations WHERE review_row_id = cast(:r as uuid)"
            ),
            {"r": str(w.review_row_id)},
        )
    ).scalar_one()
    assert authority["user_id"] == str(person.id)
    assert authority["grant_id"] == str(grants[APPROVE])


# ═══ the receipt is persisted with the claimed operation ═══════════════════════════════════════════════════════
async def test_the_approval_persists_its_receipt_and_authority_on_the_claimed_operation(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    from tests.integration.document_flow.test_s5_finding_reconciliation_pg import _reconcile

    w, person = actors.w, await _signer(actors)
    await _confirm_all(w, person)
    expected = (await _reconcile(w, person, capability=APPROVE)).receipt()
    await _final(w, request_sessions, "approve", person)
    stored = (await db.execute(text("SELECT operation_metadata -> 'authority' FROM resume_operations WHERE review_row_id = :r"), {"r": w.review_row_id})).scalar_one()
    assert stored["user_id"] == str(person.id) and stored["tenant_id"] == str(w.tenant_id) and stored["project_id"] == str(w.project_id)
    assert stored["grant_id"], "the grant the approval was taken under is recorded"
    assert stored["receipt"]["digest"] == expected.digest, "the very reconciliation that was approved"
    assert (stored["receipt"]["ledger_revision"], stored["receipt"]["artifact_hash"]) == (5, w.artifact_hash)
    assert stored["receipt"]["signable_as_is"] is True and stored["receipt"]["policy_version"] == "s5-03/v1"


async def test_a_decision_taken_under_the_legacy_rule_records_an_explicit_null_not_an_inherited_authority(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w = actors.w
    person = await actors.user(label="legacy-null")
    await actors.mode("off")
    await _final(w, request_sessions, "approve", person)
    stored = (await db.execute(text("SELECT operation_metadata -> 'authority', operation_metadata ? 'authority' FROM resume_operations WHERE review_row_id = :r"), {"r": w.review_row_id})).one()
    assert stored[1] is True and stored[0] is None, "the key exists and is JSON null"
