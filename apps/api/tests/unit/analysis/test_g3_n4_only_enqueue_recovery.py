"""G3 stranded CAS/enqueue recovery regressions: synthetic, zero provider calls."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException

from src.analysis.application.n4_only_pilot_policy import N4OnlyPilotScope, pilot_marker
from src.core.processing_authority import ProcessingAuthority, ProcessingStage
from src.documents.adapters.http.router import recover_n4_only_enqueue_endpoint
from src.documents.domain.models import DocumentStatus, DocumentType

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
PROJECT = UUID("9182c02b-0d3c-4568-835c-c4e76105a579")
DOC = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REV = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")
OWNER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
ENV = "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e"


@pytest.fixture
def scope(monkeypatch):
    data = {
        "tenant_id": str(TENANT),
        "project_id": str(PROJECT),
        "document_id": str(DOC),
        "revision_id": str(REV),
        "source_sha256": "a" * 64,
        "approved_user_id": str(OWNER),
        "predecessor_generation": 2,
        "predecessor_fence": 8,
        "expected_windows": 23,
        "expires_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat(),
    }
    for k, v in {
        "C2PRO_N4_ONLY_APPROVED_SCOPE": json.dumps(data),
        "C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED": "1",
        "RAILWAY_ENVIRONMENT_NAME": "pilot",
        "RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID": ENV,
        "C2PRO_N4_UAT_APPROVED_TENANT_ID": str(TENANT),
    }.items():
        monkeypatch.setenv(k, v)
    return N4OnlyPilotScope.from_environment()


class State:
    def __init__(self, scope):
        self.lock = asyncio.Lock()
        self.marker = pilot_marker(scope)
        self.status = DocumentStatus.UPLOADED
        self.doc_type = DocumentType.CONTRACT
        self.revision = REV
        self.stage = "INGESTION"
        self.phase = "PENDING"
        self.gen = 3
        self.fence = 9
        self.attempt_id = uuid4()
        self.owner_token = uuid4()
        self.attempts = 0
        self.lease = False
        self.active_revision = True
        self.run = False
        self.receipts = False
        self.claims = 0
        self.audit = []


class Result:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value

    def mappings(self):
        return self

    def one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value


class Session:
    def __init__(self, state):
        self.s = state
        self.locked = False
        self.reads = []

    async def execute(self, query, params):
        sql = str(query)
        assert sql.lstrip().upper().startswith("SELECT")
        self.reads.append(sql)
        if "FROM public.documents" in sql and "FOR UPDATE" in sql:
            await self.s.lock.acquire()
            self.locked = True
            return Result((DOC,))
        if "FROM public.document_revisions" in sql:
            return Result(self.s.active_revision)
        if "FROM public.document_processing_operations" in sql:
            return Result(
                {
                    "revision_id": self.s.revision,
                    "generation": self.s.gen,
                    "stage": self.s.stage,
                    "phase": self.s.phase,
                    "fencing_token": self.s.fence,
                    "attempt_count": self.s.attempts,
                    "attempt_id": self.s.attempt_id,
                    "owner_token": self.s.owner_token,
                    "lease_valid": self.s.lease,
                }
            )
        if "FROM public.n4_extraction_runs r" in sql:
            return Result(self.s.run)
        if "FROM public.n4_usage_reservations receipt" in sql:
            return Result(self.s.receipts)
        raise AssertionError("unexpected SQL")

    def release(self):
        if self.locked:
            self.locked = False
            self.s.lock.release()

    async def rollback(self):
        self.release()


class Repo:
    def __init__(self, s):
        self.s = s
        self.session = Session(s)
        self.commits = 0

    async def get_by_id(self, tenant, document):
        return SimpleNamespace(
            project_id=PROJECT,
            document_type=self.s.doc_type,
            upload_status=self.s.status,
            document_metadata={"n4_only_pilot": self.s.marker, "parsed_text_revision_id": str(REV)},
        )

    async def update_metadata(self, tenant, doc, metadata):
        self.s.marker = metadata["n4_only_pilot"]
        self.s.audit = self.s.marker.get("enqueue_recovery_events", [])

    async def commit(self):
        self.commits += 1
        self.session.release()


@pytest.fixture
def claim(monkeypatch):
    async def claimed(session, *, tenant_id, document_id, stage, revision_id):
        s = session.s
        assert session.locked
        assert stage is ProcessingStage.INGESTION and revision_id == REV
        if s.lease:
            return None
        s.phase = "CLAIMED"
        s.lease = True
        s.claims += 1
        s.attempts += 1
        s.fence += 1
        return ProcessingAuthority(
            tenant_id=tenant_id,
            document_id=document_id,
            revision_id=revision_id,
            generation=s.gen,
            stage=ProcessingStage.INGESTION,
            attempt_id=uuid4(),
            owner_token=uuid4(),
            fencing_token=s.fence,
        )

    monkeypatch.setattr(
        "src.documents.application.n4_only_enqueue_recovery.processing_authority.claim_for_recovery",
        claimed,
    )


@pytest.fixture
def broker(monkeypatch):
    calls = []

    class Task:
        fail = False

        def apply_async(self, *, kwargs, task_id):
            calls.append((kwargs, task_id))
            if self.fail:
                raise OSError("synthetic broker outage")
            return SimpleNamespace(id=task_id)

    task = Task()
    monkeypatch.setattr("src.core.tasks.ingestion_tasks.process_document_async", task)
    return task, calls


async def send(state, *, user=OWNER, tenant=TENANT, project=PROJECT):
    return await recover_n4_only_enqueue_endpoint(
        project_id=project, document_id=DOC, user_id=user, tenant_id=tenant, repo=Repo(state)
    )


@pytest.mark.asyncio
async def test_failure_manual_recovery_and_lease_expiry(scope, claim, broker):
    task, calls = broker
    s = State(scope)
    task.fail = True
    a = await send(s)
    assert a["status"] == "BROKER_ACK_UNKNOWN_STOP"
    assert a["generation"] == 3 and a["fencing_token"] == 10
    assert a["n4_billable_in_this_request"] is False
    assert s.audit[0]["claimed_fence"] == 10
    with pytest.raises(HTTPException):
        await send(s)  # no immediate duplicate
    assert len(calls) == 1 and s.claims == 1
    s.lease = False
    task.fail = False
    b = await send(s)
    assert b["status"] == "ENQUEUED" and b["generation"] == 3 and b["fencing_token"] == 11
    assert len(s.audit) == 2 and len(calls) == 2
    assert calls[-1][0]["authority"]["fencing_token"] == 11
    s.lease = False
    with pytest.raises(HTTPException):
        await send(s)
    assert len(calls) == 2  # bounded, never indefinite


@pytest.mark.asyncio
async def test_concurrent_requests_single_claim(scope, claim, broker):
    _, calls = broker
    s = State(scope)
    outcomes = await asyncio.gather(send(s), send(s), return_exceptions=True)
    assert sum(isinstance(x, dict) for x in outcomes) == 1
    assert sum(isinstance(x, HTTPException) and x.status_code == 409 for x in outcomes) == 1
    assert len(calls) == 1 and s.claims == 1 and s.gen == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        "receipt",
        "run",
        "active_lease",
        "wrong_generation",
        "wrong_revision",
        "wrong_stage",
        "already_running",
        "too_many_claims",
        "wrong_status",
        "wrong_type",
        "revision_superseded",
        "marker_changed",
    ],
)
async def test_denied_preflight_never_enqueues(scope, claim, broker, bad):
    _, calls = broker
    s = State(scope)
    if bad == "receipt":
        s.receipts = True
    if bad == "run":
        s.run = True
    if bad == "active_lease":
        s.phase = "CLAIMED"
        s.lease = True
    if bad == "wrong_generation":
        s.gen = 4
    if bad == "wrong_revision":
        s.revision = OTHER
    if bad == "wrong_stage":
        s.stage = "ANALYSIS"
    if bad == "already_running":
        s.phase = "RUNNING"
    if bad == "too_many_claims":
        s.attempts = 2
    if bad == "wrong_status":
        s.status = DocumentStatus.PARSING
    if bad == "wrong_type":
        s.doc_type = DocumentType.SCHEDULE
    if bad == "revision_superseded":
        s.active_revision = False
    if bad == "marker_changed":
        s.marker["source_sha256"] = "f" * 64
    with pytest.raises(HTTPException) as exc:
        await send(s)
    assert exc.value.status_code == 409
    assert not calls and not s.audit and s.claims == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "denial", ["owner", "tenant", "project", "expiry", "disabled", "production"]
)
async def test_denied_operator_or_identity(scope, claim, broker, monkeypatch, denial):
    _, calls = broker
    s = State(scope)
    if denial == "disabled":
        monkeypatch.setenv("C2PRO_N4_ONLY_MANUAL_RECOVERY_ENABLED", "0")
    if denial == "production":
        monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    if denial == "expiry":
        data = json.loads(__import__("os").environ["C2PRO_N4_ONLY_APPROVED_SCOPE"])
        data["expires_at"] = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        monkeypatch.setenv("C2PRO_N4_ONLY_APPROVED_SCOPE", json.dumps(data))
    with pytest.raises(HTTPException):
        await send(
            s,
            user=OTHER if denial == "owner" else OWNER,
            tenant=OTHER if denial == "tenant" else TENANT,
            project=OTHER if denial == "project" else PROJECT,
        )
    assert not calls and s.claims == 0


def _g4_running_after_adopt(state, *, guard_state="ADOPTED_BEFORE_EFFECTS"):
    """A synthetic SIGKILL immediately AFTER adopting fence 10."""
    state.phase = "RUNNING"
    state.status = DocumentStatus.PARSING
    state.attempts = 1
    state.fence = 10
    state.lease = False
    if guard_state is not None:
        state.marker["ingestion_effects_guard"] = {
            "state": guard_state,
            "generation": 3,
            "document_revision_id": str(REV),
            "attempt_id": str(state.attempt_id),
            "fencing_token": 10,
        }
    return state


@pytest.mark.asyncio
async def test_g4_sigkill_post_adopt_before_effects_recovers_once(scope, claim, broker):
    _task, messages = broker
    state = _g4_running_after_adopt(State(scope))
    response = await send(state)
    assert response["status"] == "ENQUEUED"
    assert response["generation"] == 3 and response["fencing_token"] == 11
    assert state.claims == 1 and len(messages) == 1
    assert state.audit[-1]["recovered_from_phase"] == "RUNNING"
    assert state.audit[-1]["pre_effects_guard_verified"] is True
    assert messages[0][0]["authority"]["fencing_token"] == 11
    with pytest.raises(HTTPException):
        await send(state)  # lease active; no new enqueue
    assert len(messages) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "guard_status",
    [
        None,
        "EFFECTS_MAY_HAVE_OCCURRED",
        "UNVERIFIED",
    ],
)
async def test_g4_sigkill_with_uncertain_ingestion_must_stop(scope, claim, broker, guard_status):
    _task, messages = broker
    state = _g4_running_after_adopt(State(scope), guard_state=guard_status)
    with pytest.raises(HTTPException) as exc:
        await send(state)
    assert exc.value.status_code == 409
    assert not messages and state.claims == 0 and state.audit == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage",
    [
        "stale_attempt",
        "wrong_fence",
        "wrong_revision",
        "active_lease",
        "old_n4_run",
        "any_receipt",
        "attempts_exhausted",
        "expired_policy",
    ],
)
async def test_g4_running_fails_closed_on_stale_lineage_or_possible_cost(
    scope, claim, broker, monkeypatch, damage
):
    _task, messages = broker
    state = _g4_running_after_adopt(State(scope))
    proof = state.marker["ingestion_effects_guard"]
    if damage == "stale_attempt":
        proof["attempt_id"] = str(uuid4())
    if damage == "wrong_fence":
        proof["fencing_token"] = 9
    if damage == "wrong_revision":
        proof["document_revision_id"] = str(OTHER)
    if damage == "active_lease":
        state.lease = True
    if damage == "old_n4_run":
        state.run = True
    if damage == "any_receipt":
        state.receipts = True
    if damage == "attempts_exhausted":
        state.attempts = 2
    if damage == "expired_policy":
        import os

        payload = json.loads(os.environ["C2PRO_N4_ONLY_APPROVED_SCOPE"])
        payload["expires_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        monkeypatch.setenv("C2PRO_N4_ONLY_APPROVED_SCOPE", json.dumps(payload))
    with pytest.raises(HTTPException) as exc:
        await send(state)
    assert exc.value.status_code == 409
    assert not messages and state.claims == 0


@pytest.mark.asyncio
async def test_g4_running_concurrent_recovery_only_one_claim(scope, claim, broker):
    _, messages = broker
    state = _g4_running_after_adopt(State(scope))
    outcomes = await asyncio.gather(send(state), send(state), return_exceptions=True)
    assert sum(isinstance(x, dict) for x in outcomes) == 1
    assert sum(isinstance(x, HTTPException) for x in outcomes) == 1
    assert len(messages) == 1 and state.claims == 1


@pytest.mark.asyncio
async def test_g4_two_phase_barrier_is_committed_before_ingestion(
    scope, claim, broker, monkeypatch
):
    from src.documents.application.n4_only_ingestion_effects_guard import (
        BEFORE_EFFECTS,
        MAY_HAVE_OCCURRED,
        record_before_ingestion_effects,
        record_ingestion_effects_possible,
    )

    state = State(scope)
    repo = Repo(state)
    doc = await repo.get_by_id(TENANT, DOC)
    grant = ProcessingAuthority(
        tenant_id=TENANT,
        document_id=DOC,
        revision_id=REV,
        generation=3,
        stage=ProcessingStage.INGESTION,
        attempt_id=state.attempt_id,
        owner_token=state.owner_token,
        fencing_token=10,
    )
    await record_before_ingestion_effects(repo=repo, document=doc, grant=grant)
    assert repo.commits == 0  # same txn as ADOPT, worker commits both
    assert state.marker["ingestion_effects_guard"]["state"] == BEFORE_EFFECTS
    await repo.commit()

    checks = []

    async def verify(session, authority):
        checks.append(authority.fencing_token)

    monkeypatch.setattr(
        "src.documents.application.n4_only_ingestion_effects_guard."
        "processing_authority.verify_in_transaction",
        verify,
    )
    await record_ingestion_effects_possible(repo=repo, document=doc, grant=grant)
    assert checks == [10] and repo.commits == 2
    assert state.marker["ingestion_effects_guard"]["state"] == MAY_HAVE_OCCURRED

    state = _g4_running_after_adopt(state, guard_state=MAY_HAVE_OCCURRED)
    _task, messages = broker
    with pytest.raises(HTTPException):
        await send(state)
    assert not messages and state.claims == 0


@pytest.mark.asyncio
async def test_g4_unsafe_marker_cannot_be_reset_by_new_adoption(scope):
    from src.documents.application.n4_only_ingestion_effects_guard import (
        N4OnlyIngestionEffectsUnsafe,
        record_before_ingestion_effects,
    )

    state = _g4_running_after_adopt(State(scope), guard_state="EFFECTS_MAY_HAVE_OCCURRED")
    repo = Repo(state)
    doc = await repo.get_by_id(TENANT, DOC)
    future = ProcessingAuthority(
        tenant_id=TENANT,
        document_id=DOC,
        revision_id=REV,
        generation=3,
        stage=ProcessingStage.INGESTION,
        attempt_id=uuid4(),
        owner_token=uuid4(),
        fencing_token=11,
    )
    with pytest.raises(N4OnlyIngestionEffectsUnsafe):
        await record_before_ingestion_effects(repo=repo, document=doc, grant=future)
    assert repo.commits == 0


@pytest.mark.asyncio
async def test_g4_effects_seal_commit_failure_prevents_ingestion(scope, monkeypatch):
    from src.documents.application.n4_only_ingestion_effects_guard import (
        record_before_ingestion_effects,
        record_ingestion_effects_possible,
    )

    state = State(scope)
    repo = Repo(state)
    doc = await repo.get_by_id(TENANT, DOC)
    grant = ProcessingAuthority(
        tenant_id=TENANT,
        document_id=DOC,
        revision_id=REV,
        generation=3,
        stage=ProcessingStage.INGESTION,
        attempt_id=state.attempt_id,
        owner_token=state.owner_token,
        fencing_token=10,
    )
    await record_before_ingestion_effects(repo=repo, document=doc, grant=grant)
    await repo.commit()

    async def verified(session, authority):
        assert authority.fencing_token == 10

    async def fail_commit():
        raise RuntimeError("synthetic database commit unavailable")

    monkeypatch.setattr(
        "src.documents.application.n4_only_ingestion_effects_guard."
        "processing_authority.verify_in_transaction",
        verified,
    )
    monkeypatch.setattr(repo, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="commit unavailable"):
        await record_ingestion_effects_possible(repo=repo, document=doc, grant=grant)
    # Caller must not proceed into _ingest_owned when the guard commit fails.
    assert state.marker["ingestion_effects_guard"]["state"] == "EFFECTS_MAY_HAVE_OCCURRED"


@pytest.mark.parametrize(
    ("status", "has_guard", "authority_present", "manual"),
    [
        (DocumentStatus.UPLOADED, False, False, False),
        (DocumentStatus.UPLOADED, True, False, True),
        (DocumentStatus.PARSING, False, False, True),
        (DocumentStatus.PARSING, True, False, True),
        (DocumentStatus.PARSED_PENDING_ANALYSIS, False, False, True),
        (DocumentStatus.PARSING, True, True, False),
    ],
)
def test_g4_legacy_redelivery_never_auto_acquires_expired_running(
    status,
    has_guard,
    authority_present,
    manual,
):
    from src.documents.application.n4_only_ingestion_effects_guard import manual_claim_required

    marker = {"state": "QUEUED"}
    if has_guard:
        marker["ingestion_effects_guard"] = {"state": "ADOPTED_BEFORE_EFFECTS"}
    doc = SimpleNamespace(upload_status=status, document_metadata={"n4_only_pilot": marker})
    authority = {"claimed": True} if authority_present else None
    assert manual_claim_required(doc, authority) is manual


@pytest.mark.asyncio
@pytest.mark.parametrize("malformed", ["string", "unknown-state"])
async def test_g4_malformed_guard_never_requeues_even_if_phase_pending(
    scope,
    claim,
    broker,
    malformed,
):
    _task, messages = broker
    state = State(scope)
    state.marker["ingestion_effects_guard"] = (
        "corrupt" if malformed == "string" else {"state": "UNKNOWN"}
    )
    with pytest.raises(HTTPException) as exc:
        await send(state)
    assert exc.value.status_code == 409
    assert not messages and state.claims == 0
