"""N12 financial checkpoint identity, not semantic clause/gold classification."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.analysis.adapters.ai.n12_checkpoint_escrow_port import (
    N12CheckpointIdentityError,
    bind_n12_checkpoint_escrow,
    build_n12_checkpoint_call_key,
)


def _state():
    return {
        "tenant_id": str(uuid4()),
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_revision_id": str(uuid4()),
        "thread_id": f"run-{uuid4()}",
        "retry_count": 0,
        "doc_type": "contract",
        "extracted_risks": [{"title": "Late delivery", "status": "PROPOSED"}],
        "extracted_wbs": [],
        # Resume provenance intentionally absent on first N12 node.
    }


SOURCE = "Section 9.6: Contractor shall give notice within seven days."


def _key(state, source=SOURCE, *, confirmed=True):
    return build_n12_checkpoint_call_key(
        state, model_safe_source=source, checkpoint_persisted=confirmed,
    )


def test_initial_n12_checkpoint_key_is_replay_stable_without_resume_metadata():
    state = _state()
    a = _key(state)
    b = _key(deepcopy(state))
    assert a == b and a.startswith("n12c-") and len(a) == 69
    assert SOURCE not in a


@pytest.mark.parametrize("change", [
    ("tenant_id", lambda: str(uuid4())),
    ("project_id", lambda: str(uuid4())),
    ("document_id", lambda: str(uuid4())),
    ("document_revision_id", lambda: str(uuid4())),
    ("thread_id", lambda: f"run-{uuid4()}"),
    ("retry_count", lambda: 1),
    ("extracted_risks", lambda: [{"title": "Different finding"}]),
    ("doc_type", lambda: "technical_spec"),
])
def test_material_checkpoint_identity_change_gets_distinct_call_key(change):
    field, make = change
    state = _state()
    before = _key(state)
    state[field] = make()
    assert _key(state) != before


def test_source_change_binds_another_digest_not_a_paid_replay():
    state = _state()
    assert _key(state, SOURCE) != _key(state, SOURCE + " Annex B")


def test_resumed_attempt_binds_distinct_authoritative_lineage():
    state = _state()
    initial = _key(state)
    operation = str(uuid4())
    attempt = str(uuid4())
    state["resume_provenance"] = {
        "operation_id": operation, "attempt_id": attempt,
        "owner_token": str(uuid4()),
    }
    resumed = _key(state)
    assert resumed != initial
    assert _key(deepcopy(state)) == resumed
    state["resume_provenance"]["attempt_id"] = str(uuid4())
    assert _key(state) != resumed


@pytest.mark.parametrize("field", [
    "tenant_id", "project_id", "document_id",
    "document_revision_id", "thread_id",
])
def test_missing_critical_pinned_id_is_fail_closed(field):
    state = _state()
    state.pop(field)
    with pytest.raises(N12CheckpointIdentityError):
        _key(state)


def test_missing_checkpoint_attestation_refused():
    with pytest.raises(N12CheckpointIdentityError, match="persisted"):
        _key(_state(), confirmed=False)


@pytest.mark.parametrize("bad_provenance", [
    {"operation_id": "resume-only"},
    {"attempt_id": "no-op-id"},
    ["wrong-shape"],
])
def test_partial_or_unstructured_resume_metadata_is_fail_closed(bad_provenance):
    state = _state()
    state["resume_provenance"] = bad_provenance
    with pytest.raises(N12CheckpointIdentityError):
        _key(state)


@pytest.mark.parametrize("invalid_retry", [
    "0", 1.0, None, -1, 1000, True,
])
def test_retry_sequence_must_be_bounded_integer(invalid_retry):
    state = _state()
    state["retry_count"] = invalid_retry
    with pytest.raises(N12CheckpointIdentityError):
        _key(state)


@pytest.mark.asyncio
async def test_n12_adapter_passes_exact_stable_id_through_real_port_contract():
    state = _state()
    invocations = []

    class RecordingService:
        async def run_full_source_review(
            self, system_prompt, user_content, *, governed_request_id=None,
        ):
            invocations.append((system_prompt, user_content, governed_request_id))
            return {"status": "UNASSESSED", "notes": ""}

    adapter = bind_n12_checkpoint_escrow(
        state=state, model_safe_source=SOURCE,
        service=RecordingService(), checkpoint_persisted=True,
    )
    first = await adapter.run_full_source_review("n12-system", "source and findings")
    second = await adapter.run_extraction("n12-system", "source and findings")
    assert first == second
    assert len(invocations) == 2
    assert invocations[0][2] == invocations[1][2] == _key(state)
    assert invocations[0][:2] == ("n12-system", "source and findings")



def test_mismatched_provider_tenant_is_refused_before_any_llm_call():
    state = _state()
    service = SimpleNamespace(tenant_id=uuid4())
    with pytest.raises(N12CheckpointIdentityError, match="does not match"):
        bind_n12_checkpoint_escrow(
            state=state, model_safe_source=SOURCE,
            service=service, checkpoint_persisted=True,
        )
