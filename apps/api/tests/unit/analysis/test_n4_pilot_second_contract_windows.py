"""A second contract must use its own exact N2 window inventory.

Synthetic preflight only: no provider, Celery, ledger, upload, or UAT DB.
The original 23-window test is unchanged and remains in test_g2_n4_only_pilot.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest

from src.analysis.application import n4_only_pilot as pilot
from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied, N4OnlyPilotScope, pilot_marker,
)
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.core.processing_authority import ProcessingStage

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
PROJECT = UUID("9182c02b-0d3c-4568-835c-c4e76105a579")
DOCUMENT = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REVISION = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")
USER = UUID("11111111-1111-4111-8111-111111111111")
ENVIRONMENT_ID = "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e"
# 83k synthetic source characters => 8 source windows with max_context=12k,
# overlap=400. Do not embed ABB contractual text in repository fixtures.
SOURCE = "A" * 83_000
SOURCE_SHA = hashlib.sha256(SOURCE.encode()).hexdigest()
assert len(plan_n4_source_windows(SOURCE, max_context_chars=12_000, overlap_chars=400)) == 8


def scope_env(monkeypatch, *, count=8, sha=SOURCE_SHA):
    config = {
        "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(DOCUMENT), "revision_id": str(REVISION),
        "source_sha256": sha, "approved_user_id": str(USER),
        "predecessor_generation": 2, "predecessor_fence": 8,
        "expected_windows": count,
        "expires_at": (datetime.now(UTC) + timedelta(hours=12)).isoformat(),
    }
    monkeypatch.setenv("C2PRO_N4_ONLY_APPROVED_SCOPE", json.dumps(config))
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "pilot")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", ENVIRONMENT_ID)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", ENVIRONMENT_ID)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(TENANT))
    return config


def target_state(scope):
    return {
        "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(DOCUMENT),
        "document_revision_id": str(REVISION),
        "doc_type": "contract", "n4_only_pilot": pilot_marker(scope),
    }


def setup_preflight(monkeypatch):
    authority = SimpleNamespace(
        tenant_id=TENANT, document_id=DOCUMENT, revision_id=REVISION,
        generation=3, stage=ProcessingStage.ANALYSIS, fencing_token=9,
    )
    monkeypatch.setattr(pilot, "current_authority", lambda: authority)
    monkeypatch.setattr(pilot, "_identity", lambda state: (authority, PROJECT, SOURCE))
    monkeypatch.setattr(pilot, "_limits", lambda: (5, 0.5, 12000, 400))
    return authority


def test_eight_window_contract_matches_pinned_n2_projection(monkeypatch):
    scope_env(monkeypatch, count=8)
    scope = N4OnlyPilotScope.from_environment()
    setup_preflight(monkeypatch)
    pilot.attest_n4_pilot_input(target_state(scope))


@pytest.mark.parametrize("count", [0, -1, 65, 100000])
def test_invalid_window_inventory_never_enables_pilot(monkeypatch, count):
    scope_env(monkeypatch, count=count)
    with pytest.raises(N4OnlyPilotDenied, match="expired or not approved"):
        N4OnlyPilotScope.from_environment()


def test_eight_window_scope_rejects_nine_window_claim_before_provider(monkeypatch):
    scope_env(monkeypatch, count=9)
    scope = N4OnlyPilotScope.from_environment()
    setup_preflight(monkeypatch)
    with pytest.raises(N4OnlyPilotDenied, match="inventory changed"):
        pilot.attest_n4_pilot_input(target_state(scope))


def test_eight_window_scope_rejects_different_source_sha(monkeypatch):
    scope_env(monkeypatch, count=8, sha="f" * 64)
    scope = N4OnlyPilotScope.from_environment()
    setup_preflight(monkeypatch)
    with pytest.raises(N4OnlyPilotDenied, match="projection SHA"):
        pilot.attest_n4_pilot_input(target_state(scope))


def test_eight_window_scope_rejects_wrong_revision_and_marker(monkeypatch):
    scope_env(monkeypatch, count=8)
    scope = N4OnlyPilotScope.from_environment()
    setup_preflight(monkeypatch)
    state = target_state(scope)
    state["document_revision_id"] = str(UUID("22222222-2222-4222-8222-222222222222"))
    with pytest.raises(N4OnlyPilotDenied):
        pilot.attest_n4_pilot_input(state)
    state = target_state(scope)
    state["n4_only_pilot"]["scope_digest"] = "f" * 64
    with pytest.raises(N4OnlyPilotDenied):
        pilot.attest_n4_pilot_input(state)
