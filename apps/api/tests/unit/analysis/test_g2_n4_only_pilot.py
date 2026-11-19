"""G2 N4-only isolated regression: zero provider calls and no UAT DB usage."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied,
    N4OnlyPilotScope,
    pilot_marker,
    require_marked_pilot,
)

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
PROJECT = UUID("9182c02b-0d3c-4568-835c-c4e76105a579")
DOCUMENT = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REVISION = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")
USER = UUID("11111111-1111-4111-8111-111111111111")
ENV = "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e"
SOURCE = "Synthetic N2-protected source only. No contract content."
SHA = hashlib.sha256(SOURCE.encode()).hexdigest()


@pytest.fixture
def approved_scope(monkeypatch):
    details = {
        "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(DOCUMENT), "revision_id": str(REVISION),
        "source_sha256": SHA, "approved_user_id": str(USER),
        "predecessor_generation": 2, "predecessor_fence": 8,
        "expected_windows": 23,
        "expires_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
    }
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "pilot")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", ENV)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", ENV)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(TENANT))
    monkeypatch.setenv("C2PRO_N4_ONLY_APPROVED_SCOPE", json.dumps(details))
    return N4OnlyPilotScope.from_environment()


def test_absent_scope_fails_closed(monkeypatch):
    monkeypatch.delenv("C2PRO_N4_ONLY_APPROVED_SCOPE", raising=False)
    with pytest.raises(N4OnlyPilotDenied):
        N4OnlyPilotScope.from_environment()


@pytest.mark.parametrize("key,value", [
    ("RAILWAY_ENVIRONMENT_NAME", "production"),
    ("RAILWAY_ENVIRONMENT_ID", "wrong"),
    ("C2PRO_N4_UAT_APPROVED_TENANT_ID", "22222222-2222-4222-8222-222222222222"),
])
def test_environment_fail_closed(monkeypatch, approved_scope, key, value):
    monkeypatch.setenv(key, value)
    with pytest.raises(N4OnlyPilotDenied):
        N4OnlyPilotScope.from_environment()


def test_scope_enforces_owner_tenant_revision_generation_and_marker(approved_scope):
    marker = pilot_marker(approved_scope)
    kwargs = {"tenant_id": TENANT, "project_id": PROJECT, "document_id": DOCUMENT,
                  "revision_id": REVISION, "generation": 3}
    assert require_marked_pilot(marker, **kwargs) == approved_scope
    approved_scope.check_target(**kwargs, scope_digest=approved_scope.digest, user_id=USER)
    bad = [
        {"tenant_id": UUID("22222222-2222-4222-8222-222222222222")},
        {"project_id": UUID("22222222-2222-4222-8222-222222222222")},
        {"revision_id": UUID("22222222-2222-4222-8222-222222222222")},
        {"generation": 2},
    ]
    for changed in bad:
        with pytest.raises(N4OnlyPilotDenied):
            require_marked_pilot(marker, **(kwargs | changed))
    with pytest.raises(N4OnlyPilotDenied):
        approved_scope.check_target(**kwargs, scope_digest=approved_scope.digest,
                                    user_id=UUID("22222222-2222-4222-8222-222222222222"))
    with pytest.raises(N4OnlyPilotDenied):
        require_marked_pilot(marker | {"source_sha256": "0" * 64}, **kwargs)


def test_pilot_preflight_requires_fresh_fence_and_exact_n2_sha(monkeypatch, approved_scope):
    from src.analysis.application import n4_only_pilot as pilot
    from src.core.processing_authority import ProcessingStage

    authority = SimpleNamespace(
        tenant_id=TENANT, document_id=DOCUMENT, revision_id=REVISION,
        generation=3, stage=ProcessingStage.ANALYSIS, fencing_token=9,
    )
    monkeypatch.setattr(pilot, "current_authority", lambda: authority)
    monkeypatch.setattr(pilot, "_identity", lambda state: (authority, PROJECT, SOURCE))
    monkeypatch.setattr(pilot, "_limits", lambda: (5, 0.5, 12000, 400))
    boundaries = [SimpleNamespace(core_start=i, core_end=i + 1) for i in range(22)]
    boundaries.append(SimpleNamespace(core_start=22, core_end=len(SOURCE)))
    monkeypatch.setattr(pilot, "plan_n4_source_windows", lambda *a, **kw: tuple(boundaries))
    state = {"tenant_id": str(TENANT), "project_id": str(PROJECT),
                 "document_id": str(DOCUMENT), "document_revision_id": str(REVISION),
                 "doc_type": "contract", "n4_only_pilot": pilot_marker(approved_scope)}
    pilot.attest_n4_pilot_input(state)
    authority.fencing_token = 8
    with pytest.raises(N4OnlyPilotDenied):
        pilot.attest_n4_pilot_input(state)
    authority.fencing_token = 9
    monkeypatch.setattr(pilot, "_identity", lambda state: (authority, PROJECT, SOURCE + "CHANGED"))
    with pytest.raises(N4OnlyPilotDenied):
        pilot.attest_n4_pilot_input(state)


def test_changed_window_count_denies_before_provider(monkeypatch, approved_scope):
    from src.analysis.application import n4_only_pilot as pilot
    from src.core.processing_authority import ProcessingStage
    authority = SimpleNamespace(
        tenant_id=TENANT, document_id=DOCUMENT, revision_id=REVISION,
        generation=3, stage=ProcessingStage.ANALYSIS, fencing_token=9,
    )
    monkeypatch.setattr(pilot, "current_authority", lambda: authority)
    monkeypatch.setattr(pilot, "_identity", lambda state: (authority, PROJECT, SOURCE))
    monkeypatch.setattr(pilot, "_limits", lambda: (5, 0.5, 12000, 400))
    monkeypatch.setattr(pilot, "plan_n4_source_windows", lambda *a, **kw: tuple(
        SimpleNamespace(core_start=i, core_end=i + 1) for i in range(22)
    ))
    state = {"tenant_id": str(TENANT), "project_id": str(PROJECT),
             "document_id": str(DOCUMENT), "document_revision_id": str(REVISION),
             "doc_type": "contract", "n4_only_pilot": pilot_marker(approved_scope)}
    with pytest.raises(N4OnlyPilotDenied, match="inventory changed"):
        pilot.attest_n4_pilot_input(state)


@pytest.mark.asyncio
@pytest.mark.parametrize("finding_count", [0, 2])
async def test_topology_persists_proposed_and_never_invokes_n12(
    monkeypatch, finding_count,
):
    from src.analysis.adapters.graph.workflow import route_after_risk_extraction
    from src.analysis.application import n4_only_pilot as pilot

    seen = []
    async def n1(state):
        seen.append("N1")
        return {"document_text": SOURCE}
    async def n2(state):
        seen.append("N2")
        return {"anonymized_text": SOURCE}
    async def n4(state):
        seen.append("N4")
        return {
            "extracted_risks": [{"title": "Synthetic"} for _ in range(finding_count)],
            "n4_incremental_run_id": "44444444-4444-4444-8444-444444444444",
            "n4_incremental_window_coverage": {"examined": 23, "total": 23},
        }
    monkeypatch.setattr(pilot, "document_ingestion_node", n1)
    monkeypatch.setattr(pilot, "pii_anonymizer_node", n2)
    monkeypatch.setattr(pilot, "n4_only_risk_node", n4)
    assert set(pilot.build_n4_only_workflow().nodes) == {
        "document_ingestion", "pii_anonymizer", "risk_extractor"
    }
    state = {
        "project_id": str(PROJECT), "document_id": str(DOCUMENT),
        "document_text": SOURCE, "doc_type": "contract",
        "messages": [], "extracted_risks": [], "n4_only_pilot": {"synthetic": True},
    }
    result = await pilot.run_n4_only_pilot(state)
    assert seen == ["N1", "N2", "N4"]
    assert result["n4_only_pilot_status"] == (
        "PROPOSED_N12_UNASSESSED" if finding_count else "NO_FINDINGS_UNASSESSED"
    )
    assert result["n12_status"] == "UNASSESSED"
    assert result["coherence_score"] is None
    assert result["trust_state"] == "PROPOSED"
    assert result["hitl_generated"] is False
    # Normal documents still enter N12 after successful N4.
    assert route_after_risk_extraction({"workflow_terminated": False}) == "critique"


@pytest.mark.asyncio
async def test_partial_run_never_claims_23_examined(monkeypatch):
    from src.analysis.application import n4_only_pilot as pilot
    async def passthrough(state):
        return {}
    async def incomplete(state):
        return {
            "n4_incremental_run_id": "synthetic",
            "n4_incremental_window_coverage": {"examined": 22, "total": 23},
        }
    monkeypatch.setattr(pilot, "document_ingestion_node", passthrough)
    monkeypatch.setattr(pilot, "pii_anonymizer_node", passthrough)
    monkeypatch.setattr(pilot, "n4_only_risk_node", incomplete)
    with pytest.raises(pilot.N4OnlyPilotIncomplete):
        await pilot.run_n4_only_pilot({"n4_only_pilot": {"synthetic": True}})


@pytest.mark.asyncio
async def test_pilot_endpoint_denied_before_any_mutation(monkeypatch):
    from fastapi import HTTPException

    from src.documents.adapters.http.router import reprocess_n4_only_pilot_endpoint
    monkeypatch.delenv("C2PRO_N4_ONLY_APPROVED_SCOPE", raising=False)
    class NeverTouchedRepo:
        def __getattribute__(self, name):
            raise AssertionError("forbidden read or write before scope")
    with pytest.raises(HTTPException) as exc:
        await reprocess_n4_only_pilot_endpoint(
            project_id=PROJECT, document_id=DOCUMENT,
            user_id=USER, tenant_id=TENANT, repo=NeverTouchedRepo()
        )
    assert exc.value.status_code == 403
