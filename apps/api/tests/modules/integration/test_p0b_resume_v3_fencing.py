"""
C2PRO P0b crash-safe HITL resume V3 -- fencing, ownership and atomic N17.

The V3 RED campaign (section 1), driven against REAL PostgreSQL through
GENUINELY SEPARATE connections, because the properties under test are
cross-connection properties: a single shared AsyncSession would let every
assertion pass without proving anything about concurrent workers.

Cases:

A  two real connections; worker A owns fence N; B cannot acquire while the
   lease is live.
B  the lease expires, B acquires N+1, then A reaches N17 -- A must write
   ZERO durable business effects.
C  fault injection after each core N17 persistence step -- the whole
   transaction rolls back; no partial core effects survive.
E  N17 commits atomically, then the process dies before finalization -- a
   retry does not duplicate the business effects.

(D/F/G -- superseded-descendant exclusion, document-failure truthfulness and
lost-HTTP-response idempotency -- are covered by the crash-recovery suite
and the decision-revision tests alongside this file.)
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.analysis.adapters.persistence.models import Analysis
from src.analysis.application.persist_resume_analysis import (
    ANALYSIS_PERSISTED_EVENT,
    ResumeProvenance,
    persist_resume_analysis_atomically,
)
from src.core.auth.models import Tenant, User
from src.documents.adapters.persistence.models import DocumentORM
from src.modules.hitl.adapters.persistence import resume_ownership
from src.modules.hitl.adapters.persistence.resume_ownership import (
    OwnershipError,
    Phase,
)
from src.projects.adapters.persistence.models import ProjectORM
from src.temporal.adapters.persistence.models import ProjectEventORM
from src.wbs.adapters.persistence.models import WBSNodeORM

pytestmark = pytest.mark.asyncio


def _dsn(db) -> str:
    """The async DSN of the database the harness actually bootstrapped.

    Taken from the bound engine rather than the environment: the harness
    resolves and normalises the test URL itself, so re-reading env vars can
    (and did) yield a *sync* `postgresql://` DSN pointing at a database the
    fixtures never prepared.
    """
    url = db.get_bind().url
    if url.get_driver_name() != "asyncpg":
        url = url.set(drivername="postgresql+asyncpg")
    return url.render_as_string(hide_password=False)


@pytest.fixture
async def connections(db):
    """A session factory backed by its OWN engine.

    Each call yields a fresh session on its own connection, so CAS conflicts
    are arbitrated by PostgreSQL between real transactions rather than by
    SQLAlchemy inside one.

    Depends on `db` deliberately: the test_engine fixture is function-scoped
    and destructively resets the public schema per test, so an engine built
    BEFORE that bootstrap would hold connections whose schema no longer
    exists.
    """
    _ = db
    engine = create_async_engine(_dsn(db), pool_size=10, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def factory(tenant_id: UUID):
        async with maker() as session:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)"),
                {"t": str(tenant_id)},
            )
            yield session
            await session.commit()

    try:
        yield factory
    finally:
        await engine.dispose()


async def _seed(db: AsyncSession, tenant: Tenant) -> tuple[UUID, UUID, UUID]:
    """A project, a document and a review row id to hang an operation on."""
    project_id, document_id = uuid4(), uuid4()
    db.add(
        ProjectORM(
            id=project_id,
            tenant_id=tenant.id,
            name="V3 Fencing Project",
            code="P0B-V3",
            start_date=datetime.now(),
        )
    )
    await db.commit()
    db.add(
        DocumentORM(
            id=document_id,
            tenant_id=tenant.id,
            project_id=project_id,
            document_type="contract",
            filename="v3.pdf",
            upload_status="parsed_pending_analysis",
        )
    )
    await db.commit()
    return project_id, document_id, uuid4()


async def _acquire(connections, tenant, project_id, document_id, review_row_id, **kw):
    return await resume_ownership.acquire(
        review_row_id=review_row_id,
        tenant_id=tenant.id,
        project_id=project_id,
        document_id=document_id,
        thread_id=f"document:{document_id}:analysis",
        source_checkpoint_id=kw.pop("source_checkpoint_id", "cp-source-1"),
        decision=kw.pop("decision", "approve"),
        feedback=kw.pop("feedback", ""),
        reviewer=kw.pop("reviewer", "Reviewer"),
        lease_seconds=kw.pop("lease_seconds", 120),
        session_factory=connections,
    )


def _state(project_id: UUID, document_id: UUID, tenant: Tenant, *, risks=None, wbs=None):
    return {
        "project_id": str(project_id),
        "document_id": str(document_id),
        "tenant_id": str(tenant.id),
        "extracted_risks": risks if risks is not None else [],
        "extracted_wbs": wbs if wbs is not None else [],
        "coherence_score": 88,
        "coherence_breakdown": {"overall": 88},
        "single_document_assessment": {
            "single_document_assessment": {"proof_marker": "v3"}
        },
    }


def _provenance(ownership) -> ResumeProvenance:
    return ResumeProvenance(
        operation_id=ownership.operation_id,
        attempt_id=ownership.attempt_id,
        owner_token=ownership.owner_token,
        fencing_token=ownership.fencing_token,
        decision_revision=ownership.decision_revision,
        tenant_id=ownership.tenant_id,
    )


async def _core_effect_counts(db: AsyncSession, project_id: UUID, operation_id: UUID):
    analyses = (
        await db.execute(
            select(Analysis).where(Analysis.resume_operation_id == operation_id)
        )
    ).scalars().all()
    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.resume_operation_id == operation_id
            )
        )
    ).scalars().all()
    wbs = (
        await db.execute(select(WBSNodeORM).where(WBSNodeORM.project_id == project_id))
    ).scalars().all()
    return len(analyses), len(events), len(wbs)


# ── A: live lease excludes a second worker ───────────────────────────────────


async def test_case_a_live_lease_excludes_second_worker(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    owner_a, phase, reason = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner_a is not None and reason is None
    assert owner_a.fencing_token >= 1

    owner_b, phase_b, reason_b = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner_b is None, "a live lease must exclude a second acquirer"
    assert reason_b == "lease_held_by_other_owner"

    # A can still renew; the fence is unchanged.
    assert await resume_ownership.renew(
        ownership=owner_a, lease_seconds=120, session_factory=connections
    )


# ── B: expired lease -> takeover N+1; the stale owner cannot write ───────────


async def test_case_b_stale_owner_writes_nothing_after_takeover(
    connections, db: AsyncSession, test_user: User
) -> None:
    """The decisive fencing property.

    Worker A's lease expires and B takes over at fence N+1. A then wakes up
    and reaches N17. A must persist NOTHING -- not an analysis, not an
    event, not a WBS replacement.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    owner_a, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id, lease_seconds=1
    )
    assert owner_a is not None
    fence_a = owner_a.fencing_token

    # Age the lease past expiry using the DATABASE clock.
    async with connections(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations "
                "SET lease_expires_at = clock_timestamp() - interval '1 hour' "
                "WHERE id = cast(:op as uuid)"
            ),
            {"op": str(owner_a.operation_id)},
        )

    owner_b, _, reason_b = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner_b is not None, f"takeover must succeed on an expired lease: {reason_b}"
    assert owner_b.fencing_token == fence_a + 1, "the fence must advance on takeover"
    assert owner_b.attempt_id != owner_a.attempt_id, "takeover creates a NEW attempt"

    # A now reaches N17 with its stale authority.
    with pytest.raises(OwnershipError):
        await persist_resume_analysis_atomically(
            state=_state(project_id, document_id, tenant, risks=[], wbs=[{"code": "1", "name": "x"}]),
            provenance=_provenance(owner_a),
            session_factory=connections,
        )

    analyses, events, wbs = await _core_effect_counts(db, project_id, owner_a.operation_id)
    assert (analyses, events, wbs) == (0, 0, 0), (
        "a fenced-out worker must write ZERO durable business effects"
    )

    # The rightful owner still can.
    result = await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner_b),
        session_factory=connections,
    )
    assert result.created is True
    analyses, events, _ = await _core_effect_counts(db, project_id, owner_b.operation_id)
    assert (analyses, events) == (1, 1)


async def test_prior_attempt_is_superseded_in_the_ledger(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    owner_a, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    async with connections(tenant.id) as s:
        await s.execute(
            text(
                "UPDATE resume_operations SET lease_expires_at = clock_timestamp() "
                "- interval '1 hour' WHERE id = cast(:op as uuid)"
            ),
            {"op": str(owner_a.operation_id)},
        )
    owner_b, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner_b is not None

    async with connections(tenant.id) as s:
        rows = (
            await s.execute(
                text(
                    "SELECT id, fencing_token, outcome FROM resume_operation_attempts "
                    "WHERE operation_id = cast(:op as uuid) ORDER BY fencing_token"
                ),
                {"op": str(owner_a.operation_id)},
            )
        ).all()
    assert len(rows) == 2, "the ledger is append-only: one row per attempt"
    assert rows[0].outcome == "SUPERSEDED", "the prior attempt is explicitly superseded"
    assert rows[1].outcome == "ACTIVE"
    assert rows[1].fencing_token == rows[0].fencing_token + 1


# ── C: atomic N17 -- a fault after ANY core step rolls back everything ───────


@pytest.mark.parametrize(
    "fault_point", ["after_analysis", "after_alerts", "after_wbs", "after_event", "after_phase"]
)
async def test_case_c_n17_fault_leaves_zero_partial_core_effects(
    connections, db: AsyncSession, test_user: User, fault_point: str
) -> None:
    """Injected failure after each core persistence step.

    Each must leave ZERO committed core effects -- this is what the previous
    split-commit design could not offer, since the analysis was committed
    before the event was even attempted.
    """
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner is not None

    risks = [
        {
            "title": "Late delivery",
            "description": "Schedule risk",
            "category": "schedule",
            "severity": "HIGH",
        }
    ]
    wbs = [{"code": "1.1", "name": "Mobilisation"}]

    class _Boom(RuntimeError):
        pass

    async def fault(point: str) -> None:
        if point == fault_point:
            raise _Boom(f"injected at {point}")

    with pytest.raises(_Boom):
        await persist_resume_analysis_atomically(
            state=_state(project_id, document_id, tenant, risks=risks, wbs=wbs),
            provenance=_provenance(owner),
            session_factory=connections,
            fault=fault,
        )

    analyses, events, wbs_rows = await _core_effect_counts(
        db, project_id, owner.operation_id
    )
    assert (analyses, events, wbs_rows) == (0, 0, 0), (
        f"fault at {fault_point} must roll back EVERY core effect"
    )

    async with connections(tenant.id) as s:
        phase = (
            await s.execute(
                text("SELECT phase FROM resume_operations WHERE id = cast(:op as uuid)"),
                {"op": str(owner.operation_id)},
            )
        ).scalar_one()
    assert phase != Phase.N17_DURABLE.value, "no durable phase without durable effects"


# ── E: N17 durable, then crash -- a retry must not duplicate ────────────────


async def test_case_e_retry_after_durable_n17_does_not_duplicate(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )

    first = await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner),
        session_factory=connections,
    )
    assert first.created is True

    # The process dies here; the same operation is replayed.
    second = await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner),
        session_factory=connections,
    )
    assert second.created is False, "a replay must adopt the existing analysis"
    assert second.analysis_id == first.analysis_id

    analyses, events, _ = await _core_effect_counts(db, project_id, owner.operation_id)
    assert analyses == 1, "exactly one operation-keyed analysis"
    assert events == 1, "exactly one analysis.persisted event"


async def test_n17_emits_analysis_persisted_not_graph_completed(
    connections, db: AsyncSession, test_user: User
) -> None:
    """N17 must not claim the graph finished -- the graph continues after it."""
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner),
        session_factory=connections,
    )

    events = (
        await db.execute(
            select(ProjectEventORM).where(
                ProjectEventORM.resume_operation_id == owner.operation_id
            )
        )
    ).scalars().all()
    assert [e.event_type for e in events] == [ANALYSIS_PERSISTED_EVENT]


async def test_duplicate_operation_event_is_refused_by_the_database(
    connections, db: AsyncSession, test_user: User
) -> None:
    """The one-event-per-operation rule is a DB constraint, not a convention."""
    from sqlalchemy.exc import IntegrityError

    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner),
        session_factory=connections,
    )

    with pytest.raises(IntegrityError):
        async with connections(tenant.id) as s:
            await s.execute(
                text(
                    "INSERT INTO project_events (event_id, project_id, tenant_id, "
                    "event_type, payload, evidence_refs, occurred_at, created_at, "
                    "resume_operation_id) VALUES (gen_random_uuid(), cast(:p as uuid), "
                    "cast(:t as uuid), :etype, '{}'::jsonb, '[]'::jsonb, now(), now(), "
                    "cast(:op as uuid))"
                ),
                {
                    "p": str(project_id),
                    "t": str(tenant.id),
                    "etype": ANALYSIS_PERSISTED_EVENT,
                    "op": str(owner.operation_id),
                },
            )


# ── decision revision (section 6) ────────────────────────────────────────────


async def test_decision_change_before_n17_supersedes_prior_attempt(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    approve_owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id, decision="approve"
    )
    assert approve_owner is not None

    # The reviewer changes their mind BEFORE anything is durable.
    reject_owner, _, reason = await _acquire(
        connections,
        tenant,
        project_id,
        document_id,
        review_row_id,
        decision="reject",
        feedback="actually no",
    )
    assert reject_owner is not None, f"a changed decision must be allowed pre-N17: {reason}"
    assert reject_owner.decision_revision == approve_owner.decision_revision + 1
    assert reject_owner.fencing_token > approve_owner.fencing_token

    # The superseded approve attempt can no longer write.
    with pytest.raises(OwnershipError):
        await persist_resume_analysis_atomically(
            state=_state(project_id, document_id, tenant),
            provenance=_provenance(approve_owner),
            session_factory=connections,
        )
    analyses, events, _ = await _core_effect_counts(db, project_id, approve_owner.operation_id)
    assert (analyses, events) == (0, 0)


async def test_decision_is_immutable_once_n17_is_durable(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id, decision="approve"
    )
    await persist_resume_analysis_atomically(
        state=_state(project_id, document_id, tenant),
        provenance=_provenance(owner),
        session_factory=connections,
    )

    changed, phase, reason = await _acquire(
        connections,
        tenant,
        project_id,
        document_id,
        review_row_id,
        decision="reject",
        feedback="too late",
    )
    assert changed is None, "the decision must be immutable once the effect is durable"
    assert reason == "decision_immutable_after_n17"
    assert phase is Phase.N17_DURABLE


# ── concurrency across real connections ──────────────────────────────────────


async def test_concurrent_acquire_across_connections_yields_one_owner(
    connections, db: AsyncSession, test_user: User
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    results = await asyncio.gather(
        *[
            _acquire(connections, tenant, project_id, document_id, review_row_id)
            for _ in range(4)
        ],
        return_exceptions=True,
    )
    owners = [r[0] for r in results if not isinstance(r, BaseException) and r[0] is not None]
    assert len(owners) == 1, f"exactly one owner across real connections, got {len(owners)}"


async def test_operator_required_is_reached_and_never_retried(
    connections, db: AsyncSession, test_user: User
) -> None:
    """Bounded failure escalates instead of retrying forever or faking success."""
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)

    last_phase = None
    for _ in range(resume_ownership.MAX_FAILURES_BEFORE_OPERATOR):
        owner, _, reason = await _acquire(
            connections, tenant, project_id, document_id, review_row_id
        )
        if owner is None:
            break
        last_phase = await resume_ownership.record_failure(
            ownership=owner, error="boom", session_factory=connections
        )

    assert last_phase is Phase.OPERATOR_REQUIRED

    blocked, phase, reason = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert blocked is None, "OPERATOR_REQUIRED must never be auto-retried"
    assert reason == "operator_required"


async def test_cross_tenant_cannot_acquire(
    connections, db: AsyncSession, test_user: User, test_tenant_2: Tenant
) -> None:
    tenant = await db.get(Tenant, test_user.tenant_id)
    project_id, document_id, review_row_id = await _seed(db, tenant)
    owner, _, _ = await _acquire(
        connections, tenant, project_id, document_id, review_row_id
    )
    assert owner is not None

    intruder, _, reason = await resume_ownership.acquire(
        review_row_id=review_row_id,
        tenant_id=test_tenant_2.id,
        project_id=project_id,
        document_id=document_id,
        thread_id="t",
        source_checkpoint_id="cp",
        decision="approve",
        feedback="",
        reviewer="Intruder",
        session_factory=connections,
    )
    # The other tenant gets its OWN operation row and can never address this
    # one -- it must not be handed ownership of another tenant's operation.
    assert intruder is None or intruder.operation_id != owner.operation_id
