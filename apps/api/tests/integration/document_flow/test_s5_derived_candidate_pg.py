"""S5 Vn+1 on PostgreSQL: DISMISSED / CORRECTION_PROPOSED decisions produce a DERIVED, versioned, traceable candidate.

Scope, stated so nothing is over-read:

* PRODUCED: from the S5-03 reconciliation, a new candidate Vn+1 (PROPOSED) through the product's own governed
  ``propose_correction`` -- Vn is SUPERSEDED (never TRUSTED), the review rebinds to Vn+1, and the provenance (source
  candidate id/version/hash/revision, reconciliation digest, ledger head, every decision, the deriving human) is kept with
  the review. Nothing is approved, rejected or trusted by deriving.
* NOT a promotion: Vn+1 starts with every finding UNDECIDED. A human must decide its findings again and approve it
  explicitly; S5-04 (current reconciliation) and S5-05 (grant + digest inside the first-TRUSTED transaction) then apply
  to Vn+1 exactly as to any candidate.
* GATED: exclusions are unambiguous and implemented; the field a CORRECTION_PROPOSED text replaces is an interpretation
  (``description``) awaiting owner ratification, so correction materialization is refused (409) until
  ``CORRECTIONS_RATIFIED`` is switched on. The correction tests switch it on to prove the path works, not to claim it is
  ratified.
* NOT claimed: P1 SQL administrative authority (NOT_VERIFIED), typed critique (UNEVALUATED), an independent security
  review (PENDING), real-AI extraction (the findings here are authored by the controlled seed).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth.models import SubscriptionPlan, Tenant
from src.modules.hitl.adapters.http import finding_decision_router as routes
from src.modules.hitl.domain import derived_candidate as domain
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
    _status,
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


# ── helpers ────────────────────────────────────────────────────────────────────────────────────────────────────
async def _decider(actors: Actors) -> Any:  # noqa: F811
    person = await actors.user(label="decider")
    await actors.grant(person, READ, FIND, APPROVE)
    return person


async def _decide_all(w: Any, person: Any, actions: list[A], **texts: str) -> int:
    expected = 0
    for ordinal, action in enumerate(actions):
        extra = {"proposed_text": texts[str(ordinal)]} if str(ordinal) in texts else {}
        await _decide(w, person, ordinal, expected, action, **extra)
        expected += 1
    return expected


def _body(w: Any, expected: int, *, source_hash: str | None = None) -> Any:
    return routes.DerivedCandidateRequest(source_artifact_hash=source_hash or w.artifact_hash, expected_ledger_revision=expected)


async def _derive(w: Any, user: Any, expected: int, *, source_hash: str | None = None, tenant_id: Any = None) -> Any:
    async with w.sessions(tenant_id or w.tenant_id) as session:
        try:
            out = await routes.derive_candidate(w.review_row_id, _body(w, expected, source_hash=source_hash), current_user=user, session=session)
        except BaseException:
            await session.rollback()
            raise
        await session.commit()
        return out


def _code(exc: HTTPException) -> str:
    return exc.detail["code"] if isinstance(exc.detail, dict) else str(exc.detail)


async def _refused(w: Any, user: Any, expected: int, **kw: Any) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        await _derive(w, user, expected, **kw)
    return caught.value


async def _artifacts(db: AsyncSession, w: Any) -> list[Any]:
    await db.commit()
    return list(
        (
            await db.execute(
                text(
                    "SELECT artifact_id, artifact_version, trust_state, lifecycle_status, artifact_hash, payload "
                    "FROM document_artifacts WHERE document_id = :d ORDER BY artifact_version"
                ),
                {"d": w.document_id},
            )
        ).all()
    )


def _payload(row: Any) -> dict[str, Any]:
    return row.payload if isinstance(row.payload, dict) else json.loads(row.payload)


def _rebind(w: Any, derived: Any, risks: list[dict[str, Any]]) -> None:
    """What a screen does after deriving: it reads the NEW candidate's pins and findings."""
    w.artifact_id, w.artifact_version, w.artifact_hash = derived.derived_artifact_id, derived.derived_artifact_version, derived.derived_artifact_hash
    w.risks = risks


async def _vn1_risks(db: AsyncSession, w: Any, derived: Any) -> list[dict[str, Any]]:
    rows = await _artifacts(db, w)
    return _payload(next(r for r in rows if r.artifact_id == derived.derived_artifact_id))["extracted_risks"]


EVENT = "hitl.candidate_derived"


async def _events(db: AsyncSession, w: Any) -> list[Any]:
    await db.commit()
    return list(
        (
            await db.execute(
                text(
                    "SELECT event_id, tenant_id, project_id, actor, source_revision_id, payload FROM project_events "
                    "WHERE project_id = :p AND event_type = :t ORDER BY occurred_at, event_id"
                ),
                {"p": w.project_id, "t": EVENT},
            )
        ).all()
    )


async def _scoring(db: AsyncSession, artifact_id: Any) -> Any:
    await db.commit()
    return (await db.execute(text("SELECT scoring FROM document_artifacts WHERE artifact_id = :a"), {"a": artifact_id})).scalar_one()


async def _give_vn_a_score(db: AsyncSession, w: Any) -> dict[str, Any]:
    """The source candidate carries an N8 score, as a real analysis would leave it."""
    score = {"coherence_score": 82.0, "score_version": "coherence-v1"}
    await db.execute(text("UPDATE document_artifacts SET scoring = cast(:s as jsonb) WHERE artifact_id = :a"), {"s": json.dumps(score), "a": w.artifact_id})
    await db.commit()
    return score


@pytest.fixture
def corrections_ratified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(domain, "CORRECTIONS_RATIFIED", True)


# ═══ the derived candidate ════════════════════════════════════════════════════════════════════════════════════
async def test_a_dismissal_produces_a_versioned_proposed_candidate_and_leaves_the_original_unchanged(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    before = await _artifacts(db, w)
    vn = next(r for r in before if r.artifact_id == w.artifact_id)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])

    derived = await _derive(w, person, expected)

    assert derived.replayed is False and derived.derived_state == "PROPOSED" and derived.final_approval == "SEPARATE_ACT"
    assert (derived.excluded, derived.corrected, derived.retained) == (1, 0, 4)
    after = await _artifacts(db, w)
    new = next(r for r in after if r.artifact_id == derived.derived_artifact_id)
    old = next(r for r in after if r.artifact_id == w.artifact_id)
    assert new.trust_state == "proposed" and new.artifact_version == vn.artifact_version + 1 and new.artifact_hash != vn.artifact_hash
    assert [r["title"] for r in _payload(new)["extracted_risks"]] == [r["title"] for r in w.risks[:4]], "the dismissed finding is left out"
    assert _payload(new)["extracted_risks"] == w.risks[:4], "the retained findings are the source's, untouched"
    assert (old.trust_state, old.lifecycle_status, old.artifact_hash) == ("superseded", "superseded", vn.artifact_hash), "Vn: only superseded"
    assert _payload(old) == _payload(vn), "the original candidate's content is not altered"
    assert all(r.trust_state != "trusted" for r in after), "deriving trusts nothing"
    assert (derived.source_artifact_id, derived.source_artifact_version, derived.source_artifact_hash) == (w.artifact_id, vn.artifact_version, vn.artifact_hash)


async def test_the_provenance_and_the_new_binding_are_persisted_with_the_review(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED])
    source_revision = w.revision_id
    derived = await _derive(w, person, expected)

    state = await _status(db, w)
    binding = state["metadata"]["candidate_binding"]
    assert (binding["artifact_id"], binding["artifact_version"], binding["artifact_hash"]) == (
        str(derived.derived_artifact_id), derived.derived_artifact_version, derived.derived_artifact_hash,
    ), "approval of this review now binds Vn+1"
    entries = state["metadata"]["candidate_derivations"]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["policy"] == domain.DERIVATION_POLICY_VERSION and entry["derived_state"] == "PROPOSED"
    assert entry["source_artifact_id"] == str(derived.source_artifact_id) and entry["source_artifact_hash"] == derived.source_artifact_hash
    assert entry["source_document_revision_id"] == str(source_revision), "the identity of the source revision is kept"
    assert entry["source_ledger_revision"] == expected and entry["reconciliation_digest"] == derived.reconciliation_digest
    assert entry["derived_by"] == str(person.id), "the authenticated human, never client data"
    assert [e["ordinal"] for e in entry["excluded"]] == [1] and entry["retained"] == [0, 2, 3, 4]
    ledger = (await db.execute(text("SELECT event_id FROM hitl_finding_decisions WHERE review_row_id = :r AND action = 'DISMISSED'"), {"r": w.review_row_id})).scalar_one()
    assert entry["excluded"][0]["decision_event_id"] == str(ledger), "traceable to the decision it rests on"
    count = (await db.execute(text("SELECT count(*) FROM hitl_finding_decisions WHERE review_row_id = :r"), {"r": w.review_row_id})).scalar_one()
    assert count == expected, "the ledger is untouched by deriving"


async def test_deriving_creates_no_operation_or_analysis_only_its_own_event_and_a_pre_existing_trusted_artifact_is_untouched(
    db: AsyncSession, actors: Actors  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    # an older TRUSTED artifact of the same document, as left by an earlier approved revision
    older = (await _artifacts(db, w))[0]
    await db.execute(
        text(
            "INSERT INTO document_artifacts (artifact_id, document_id, document_revision_id, project_id, tenant_id, payload, "
            "lifecycle_status, artifact_version, artifact_hash, trust_state, scoring) "
            "SELECT :new, document_id, document_revision_id, project_id, tenant_id, payload, 'active', 50, :hash, 'trusted', scoring "
            "FROM document_artifacts WHERE artifact_id = :old"
        ),
        {"new": uuid4(), "old": older.artifact_id, "hash": "c" * 64},
    )
    await db.commit()
    trusted_before = [(r.artifact_id, r.artifact_hash, r.lifecycle_status, _payload(r)) for r in await _artifacts(db, w) if r.trust_state == "trusted"]
    footprint = await _footprint(db, w)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])

    await _derive(w, person, expected)

    trusted_after = [(r.artifact_id, r.artifact_hash, r.lifecycle_status, _payload(r)) for r in await _artifacts(db, w) if r.trust_state == "trusted"]
    assert trusted_after == trusted_before and len(trusted_after) == 1, "trusted content is never altered by a derivation"
    after = await _footprint(db, w)
    for key in ("analyses", "resume_operations"):
        assert after[key] == footprint[key], key
    assert after["project_events"] == footprint["project_events"] + 1, "exactly ONE new event: the derivation's own evidence"
    assert len(await _events(db, w)) == 1
    assert after["review"] == "PENDING_REVIEW_REQUIRED"


async def test_a_correction_is_refused_until_the_owner_ratifies_which_field_it_replaces(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CORRECTION_PROPOSED], **{"4": "Access is guaranteed from 01/01/2027."})
    before = await _artifacts(db, w)
    refusal = await _refused(w, person, expected)
    assert (refusal.status_code, _code(refusal)) == (409, "correction_semantics_not_ratified")
    assert [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in await _artifacts(db, w)] == [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in before], "nothing created"


async def test_a_ratified_correction_replaces_only_the_description_with_the_reviewers_text(
    db: AsyncSession, actors: Actors, corrections_ratified: None  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    text_ = "Access to the site is guaranteed from 01/01/2027."
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CORRECTION_PROPOSED], **{"4": text_})
    original = w.risks[4]
    derived = await _derive(w, person, expected)
    assert (derived.excluded, derived.corrected, derived.retained) == (0, 1, 4)
    risks = await _vn1_risks(db, w, derived)
    assert len(risks) == 5 and risks[4]["description"] == text_
    assert {k: v for k, v in risks[4].items() if k != "description"} == {k: v for k, v in original.items() if k != "description"}
    assert risks[:4] == w.risks[:4]
    entry = (await _status(db, w))["metadata"]["candidate_derivations"][0]
    assert entry["corrected"][0]["field"] == "description" and text_ not in json.dumps(entry), "digests, not a second copy"


# ═══ nothing is derived from an incomplete or unnecessary reconciliation ═════════════════════════════════════
@pytest.mark.parametrize(
    "actions",
    [
        [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.NEEDS_INFO],
        [A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED],  # the fifth finding is undecided
        [],
    ],
)
async def test_needs_info_and_incomplete_decisions_block_the_derivation_and_create_nothing(
    db: AsyncSession, actors: Actors, actions: list[A]  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, actions)
    before = await _artifacts(db, w)
    refusal = await _refused(w, person, expected)
    assert (refusal.status_code, _code(refusal)) == (409, "derivation_blocked"), refusal.detail
    assert refusal.detail["blockers"], "the blockers are named"
    after = await _artifacts(db, w)
    assert [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in after] == [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in before]
    assert "candidate_derivations" not in (await _status(db, w))["metadata"]


async def test_a_candidate_that_needs_no_derivation_is_refused(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED] * 5)
    refusal = await _refused(w, person, expected)
    assert (refusal.status_code, _code(refusal)) == (409, "no_derivation_required")
    assert len(await _artifacts(db, w)) == 2, "Vn-1 (superseded by the seed) and Vn only"


# ═══ explicit human validation and approval of Vn+1 ═══════════════════════════════════════════════════════
async def test_the_derived_candidate_needs_new_decisions_and_an_explicit_approval_and_only_then_is_trusted(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    derived = await _derive(w, person, expected)
    risks = await _vn1_risks(db, w, derived)
    old_hash = derived.source_artifact_hash
    _rebind(w, derived, risks)

    # 1. the dismissal of Vn does NOT carry over as an approval of Vn+1: its findings are undecided
    with pytest.raises(HTTPException) as caught:
        await _final(w, request_sessions, "approve", person)
    assert (caught.value.status_code, _code(caught.value)) == (409, "reconciliation_blocks_approval")
    assert caught.value.detail["blockers"] == ["UNDECIDED_FINDING"] * 4
    assert (await _footprint(db, w))["resume_operations"] == 0 and all(r.trust_state != "trusted" for r in await _artifacts(db, w))

    # 2. a decision still aimed at the superseded Vn is refused
    stale = w.artifact_id, w.artifact_version, w.artifact_hash, w.risks
    w.artifact_hash = old_hash
    with pytest.raises(HTTPException) as stale_caught:
        await _decide(w, person, 0, expected)
    assert stale_caught.value.status_code == 409
    w.artifact_id, w.artifact_version, w.artifact_hash, w.risks = stale

    # 3. the human validates Vn+1 finding by finding, then approves it: only now it is TRUSTED, exactly that candidate
    for ordinal in range(4):
        await _decide(w, person, ordinal, expected + ordinal)
    await _final(w, request_sessions, "approve", person)
    final = await _artifacts(db, w)
    trusted = [r for r in final if r.trust_state == "trusted"]
    assert [r.artifact_id for r in trusted] == [derived.derived_artifact_id] and trusted[0].artifact_hash == derived.derived_artifact_hash
    assert next(r for r in final if r.artifact_hash == old_hash).trust_state != "trusted", "the original candidate is never trusted"
    authority = (await db.execute(text("SELECT operation_metadata -> 'authority' FROM resume_operations WHERE review_row_id = :r"), {"r": w.review_row_id})).scalar_one()
    assert authority["receipt"]["artifact_id"] == str(derived.derived_artifact_id) and authority["receipt"]["signable_as_is"] is True, (
        "the signature is bound to the reconciliation of Vn+1, not of Vn"
    )


async def test_a_derived_candidate_cannot_be_promoted_by_someone_without_a_valid_approval_grant(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    derived = await _derive(w, person, expected)
    _rebind(w, derived, await _vn1_risks(db, w, derived))
    for ordinal in range(4):
        await _decide(w, person, ordinal, expected + ordinal)
    reviewer_only = await actors.user(label="reviewer-only")
    await actors.grant(reviewer_only, READ, FIND)
    with pytest.raises(HTTPException) as caught:
        await _final(w, request_sessions, "approve", reviewer_only)
    assert caught.value.status_code in {403, 404}, caught.value.detail
    assert all(r.trust_state != "trusted" for r in await _artifacts(db, w)) and (await _footprint(db, w))["resume_operations"] == 0


# ═══ authority, tenant isolation ═══════════════════════════════════════════════════════════════════════════════
async def test_deriving_needs_the_review_finding_capability_on_this_project(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    reader = await actors.user(label="reader")
    await actors.grant(reader, READ)
    refusal = await _refused(w, reader, expected)
    assert (refusal.status_code, _code(refusal)) == (403, "project_capability_required")
    stranger = await actors.user(label="no-grants")
    assert (await _refused(w, stranger, expected)).status_code == 404, "no visibility of the project at all"
    assert len(await _artifacts(db, w)) == 2


async def test_a_revoked_review_finding_grant_cannot_derive(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w = actors.w
    person = await actors.user(label="revoked")
    grants = await actors.grant(person, READ, FIND)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    await actors.revoke(grants[FIND])
    refusal = await _refused(w, person, expected)
    assert refusal.status_code in {403, 404}
    assert len(await _artifacts(db, w)) == 2


async def test_another_tenant_cannot_derive_or_see_the_review(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    other = Tenant(id=uuid4(), name="Other", slug=f"other-{uuid4().hex[:8]}", clerk_org_id=f"org_{uuid4().hex[:8]}", is_active=True, subscription_plan=SubscriptionPlan.STARTER)
    db.add(other)
    await db.commit()
    other_tenant = other.id
    outsider = await actors.user(label="outsider", tenant_id=other_tenant)
    refusal = await _refused(w, outsider, expected, tenant_id=other_tenant)
    assert refusal.status_code in {403, 404}
    assert len(await _artifacts(db, w)) == 2 and "candidate_derivations" not in (await _status(db, w))["metadata"]


# ═══ staleness, concurrency, idempotency, recovery ════════════════════════════════════════════════════════
async def test_a_derivation_built_on_a_stale_ledger_or_candidate_is_refused(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    stale_ledger = await _refused(w, person, expected - 1)
    assert (stale_ledger.status_code, _code(stale_ledger)) == (409, "stale_ledger_revision")
    stale_candidate = await _refused(w, person, expected, source_hash="d" * 64)
    assert (stale_candidate.status_code, _code(stale_candidate)) == (409, "stale_or_unbound_candidate")
    await _decide(w, person, 4, expected, A.CONFIRMED)  # the reviewer changed their mind meanwhile
    after_change = await _refused(w, person, expected)
    assert _code(after_change) == "stale_ledger_revision", "a digest older than the ledger is never applied"
    assert len(await _artifacts(db, w)) == 2


async def test_a_retry_is_idempotent_and_returns_the_same_derived_candidate(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    first = await _derive(w, person, expected)
    again = await _derive(w, person, expected)
    assert again.replayed is True and not first.replayed
    assert (again.derived_artifact_id, again.derived_artifact_hash, again.reconciliation_digest) == (first.derived_artifact_id, first.derived_artifact_hash, first.reconciliation_digest)
    rows = await _artifacts(db, w)
    assert len([r for r in rows if r.trust_state == "proposed" and r.lifecycle_status == "active"]) == 1, "exactly one live proposal"
    assert len((await _status(db, w))["metadata"]["candidate_derivations"]) == 1, "one provenance entry, not two"


async def test_two_concurrent_derivations_produce_one_candidate(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    outcomes = await asyncio.gather(_derive(w, person, expected), _derive(w, person, expected), return_exceptions=True)
    results = [o for o in outcomes if not isinstance(o, BaseException)]
    assert len(results) == 2, outcomes
    assert len({r.derived_artifact_id for r in results}) == 1 and sorted(r.replayed for r in results) == [False, True]
    rows = await _artifacts(db, w)
    assert len([r for r in rows if r.trust_state == "proposed" and r.lifecycle_status == "active"]) == 1
    assert len((await _status(db, w))["metadata"]["candidate_derivations"]) == 1


async def test_a_failure_while_deriving_rolls_everything_back_and_the_retry_succeeds(
    db: AsyncSession, actors: Actors, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    from src.modules.hitl.application import derived_candidate_service as service

    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    before = await _artifacts(db, w)
    real = service.DerivedCandidateService._record_provenance

    async def fail(self: Any, *args: Any, **kwargs: Any) -> None:
        raise RuntimeError("crash after the new candidate was written, before the provenance")

    monkeypatch.setattr(service.DerivedCandidateService, "_record_provenance", fail)
    with pytest.raises(RuntimeError):
        await _derive(w, person, expected)
    monkeypatch.setattr(service.DerivedCandidateService, "_record_provenance", real)
    after_failure = await _artifacts(db, w)
    assert [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in after_failure] == [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in before], "no half-made candidate"
    assert (await _status(db, w))["metadata"]["candidate_binding"]["artifact_id"] == str(w.artifact_id), "the review still binds Vn"

    derived = await _derive(w, person, expected)
    assert derived.replayed is False and len((await _status(db, w))["metadata"]["candidate_derivations"]) == 1


async def test_a_finished_review_cannot_be_derived(db: AsyncSession, actors: Actors, request_sessions: Any) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED] * 5)
    await _final(w, request_sessions, "approve", person)
    refusal = await _refused(w, person, expected)
    assert refusal.status_code in {404, 409}
    assert [r.trust_state for r in await _artifacts(db, w)].count("trusted") == 1


# ═══ A3 — the evidence is an append-only project event written with the candidate ═════════════════════════
async def test_the_derivation_is_recorded_as_an_append_only_project_event_in_the_same_transaction(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.DISMISSED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED])
    source_revision = w.revision_id
    derived = await _derive(w, person, expected)

    events = await _events(db, w)
    assert len(events) == 1
    event = events[0]
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    assert (event.tenant_id, event.project_id, event.actor) == (w.tenant_id, w.project_id, str(person.id)), "the authenticated human"
    assert event.source_revision_id == source_revision, "the identity of the source revision"
    assert payload["policy"] == domain.DERIVATION_POLICY_VERSION and payload["reconciliation_policy"]
    assert payload["review_row_id"] == str(w.review_row_id) and payload["reconciliation_digest"] == derived.reconciliation_digest
    assert (payload["source_artifact_id"], payload["source_artifact_hash"], payload["source_ledger_revision"]) == (
        str(derived.source_artifact_id), derived.source_artifact_hash, expected,
    )
    assert (payload["derived_artifact_id"], payload["derived_artifact_hash"]) == (str(derived.derived_artifact_id), derived.derived_artifact_hash)
    assert [e["ordinal"] for e in payload["excluded"]] == [1] and payload["excluded"][0]["decision_event_id"]
    assert derived.event_id == event.event_id
    # append-only by the table itself (trigger), not by convention
    for sql in ("UPDATE project_events SET payload = '{}'::jsonb WHERE event_id = :e", "DELETE FROM project_events WHERE event_id = :e"):
        with pytest.raises(Exception, match="append-only"):
            await db.execute(text(sql), {"e": event.event_id})
        await db.rollback()


async def test_the_replay_comes_from_the_event_ledger_not_from_the_mutable_review_metadata(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    first = await _derive(w, person, expected)
    await db.execute(text("UPDATE review_items SET review_metadata = review_metadata - 'candidate_derivations' WHERE id = :r"), {"r": w.review_row_id})
    await db.commit()
    again = await _derive(w, person, expected)
    assert again.replayed is True and again.derived_artifact_id == first.derived_artifact_id and again.event_id == first.event_id
    assert len(await _events(db, w)) == 1 and len([r for r in await _artifacts(db, w) if r.trust_state == "proposed" and r.lifecycle_status == "active"]) == 1


async def test_a_failure_after_the_candidate_but_before_the_event_leaves_neither(db: AsyncSession, actors: Actors, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    from src.temporal.adapters.persistence.project_event_repository import (
        SqlAlchemyProjectEventRepository,
    )

    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    before = await _artifacts(db, w)
    real = SqlAlchemyProjectEventRepository.append

    async def boom(self: Any, event: Any) -> Any:
        raise RuntimeError("crash while appending the evidence")

    monkeypatch.setattr(SqlAlchemyProjectEventRepository, "append", boom)
    with pytest.raises(RuntimeError):
        await _derive(w, person, expected)
    monkeypatch.setattr(SqlAlchemyProjectEventRepository, "append", real)
    assert [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in await _artifacts(db, w)] == [(r.artifact_id, r.trust_state, r.lifecycle_status) for r in before]
    assert await _events(db, w) == [] and (await _status(db, w))["metadata"]["candidate_binding"]["artifact_id"] == str(w.artifact_id)
    derived = await _derive(w, person, expected)
    assert derived.replayed is False and len(await _events(db, w)) == 1


async def test_a_refused_derivation_writes_no_event(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.NEEDS_INFO])
    await _refused(w, person, expected)
    await _refused(w, person, expected - 1)
    assert await _events(db, w) == []


# ═══ A4 — a score inherited from Vn is never presented as the evaluation of Vn+1 ═════════════════════════════
async def test_the_derived_candidate_carries_no_score_and_the_original_score_stays_as_history(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    from src.analysis.application.trusted_materialization import MaterializationContent

    w, person = actors.w, await _decider(actors)
    original = await _give_vn_a_score(db, w)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    derived = await _derive(w, person, expected)
    assert derived.scoring_state == "PENDING_REEVALUATION"

    vn = await _scoring(db, w.artifact_id)
    assert (vn if isinstance(vn, dict) else json.loads(vn)) == original, "the original evaluation is kept, untouched, as history"
    raw = await _scoring(db, derived.derived_artifact_id)
    vn1 = raw if isinstance(raw, dict) else json.loads(raw)
    assert vn1["coherence_score"] is None and vn1["score_version"] is None, "no Score is fabricated or carried"
    assert vn1["evaluation"] == "PENDING_REEVALUATION" and vn1["derived_from_artifact_id"] == str(w.artifact_id)
    event = (await _events(db, w))[0]
    payload = event.payload if isinstance(event.payload, dict) else json.loads(event.payload)
    assert payload["source_scoring"] == original and payload["derived_scoring"]["evaluation"] == "PENDING_REEVALUATION"
    # what the TRUSTED materializer would write for Vn+1 is "no score", not the old 82
    content = MaterializationContent.from_artifact({"document_id": str(w.document_id), "extracted_risks": []})
    assert content.coherence_score is None


# ═══ A1 — proposing and approving are different capabilities ═══════════════════════════════════════════════
async def test_approving_alone_does_not_allow_deriving_and_deriving_alone_does_not_allow_approving(
    db: AsyncSession, actors: Actors, request_sessions: Any  # noqa: F811
) -> None:
    w, person = actors.w, await _decider(actors)
    expected = await _decide_all(w, person, [A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.CONFIRMED, A.DISMISSED])
    approver_only = await actors.user(label="approver-only")
    await actors.grant(approver_only, READ, APPROVE)
    assert _code(await _refused(w, approver_only, expected)) == "project_capability_required", "APPROVE_CANDIDATE does not imply REVIEW_FINDING"
    proposer = await actors.user(label="proposer")
    await actors.grant(proposer, READ, FIND)
    derived = await _derive(w, proposer, expected)
    _rebind(w, derived, await _vn1_risks(db, w, derived))
    for ordinal in range(4):
        await _decide(w, proposer, ordinal, expected + ordinal)
    with pytest.raises(HTTPException) as caught:
        await _final(w, request_sessions, "approve", proposer)
    assert caught.value.status_code in {403, 404} and all(r.trust_state != "trusted" for r in await _artifacts(db, w)), "the proposer cannot promote"
    await actors.grant(approver_only, FIND)  # now holds both: still an explicit, separate act
    await _final(w, request_sessions, "approve", approver_only)
    assert [r.artifact_id for r in await _artifacts(db, w) if r.trust_state == "trusted"] == [derived.derived_artifact_id]


# ═══ A2 — the correction gate stays shut until the owner ratifies the semantics ═══════════════════════════════
def test_the_correction_gate_is_shut_by_default() -> None:
    assert domain.CORRECTIONS_RATIFIED is False
