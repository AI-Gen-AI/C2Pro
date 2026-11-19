"""P1: read persisted N4 partial evidence after execution-scope expiry."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from src.analysis.application.n4_only_pilot_policy import (
    N4OnlyPilotDenied,
    N4OnlyPilotScope,
    pilot_marker,
    require_marked_pilot,
    require_readable_pilot,
)
from src.documents.adapters.http.router import read_n4_only_pilot_findings

TENANT = UUID("c30fe672-6654-4382-b7a4-e51cfc49c1b0")
PROJECT = UUID("9182c02b-0d3c-4568-835c-c4e76105a579")
DOCUMENT = UUID("645fb46d-f39b-4919-9584-7b7942f99256")
REVISION = UUID("327a4eec-ef29-43dd-a71c-f229325da0d0")
OWNER = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
RUN = UUID("44444444-4444-4444-8444-444444444444")
SHA = "5" * 64
ENV = "60aa9a4c-c231-4bd9-bc87-f76883ea7e0e"


@pytest.fixture
def expired_scope(monkeypatch):
    data = {
        "tenant_id": str(TENANT), "project_id": str(PROJECT),
        "document_id": str(DOCUMENT), "revision_id": str(REVISION),
        "source_sha256": SHA, "approved_user_id": str(OWNER),
        "predecessor_generation": 2, "predecessor_fence": 8,
        "expected_windows": 23,
        "expires_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    }
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "pilot")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_ID", ENV)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", ENV)
    monkeypatch.setenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", str(TENANT))
    monkeypatch.setenv("C2PRO_N4_ONLY_APPROVED_SCOPE", json.dumps(data))
    return N4OnlyPilotScope.from_environment_for_read()


def identity(**overrides):
    return {"tenant_id": TENANT, "project_id": PROJECT, "document_id": DOCUMENT,
                "revision_id": REVISION, "generation": 3, "user_id": OWNER} | overrides


def test_read_partial_after_expiry_but_post_stays_expired(expired_scope):
    marker = pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"}
    assert require_readable_pilot(marker, **identity()) == expired_scope
    with pytest.raises(N4OnlyPilotDenied):
        N4OnlyPilotScope.from_environment()
    with pytest.raises(N4OnlyPilotDenied):
        require_marked_pilot(marker, **{k: v for k,v in identity().items() if k != "user_id"})


@pytest.mark.parametrize("changed", [
    {"user_id": OTHER}, {"tenant_id": OTHER}, {"project_id": OTHER},
    {"document_id": OTHER}, {"revision_id": OTHER}, {"generation": 2},
])
def test_read_rejects_foreign_or_stale_identity(expired_scope, changed):
    marker = pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"}
    with pytest.raises(N4OnlyPilotDenied):
        require_readable_pilot(marker, **identity(**changed))


@pytest.mark.parametrize("changed", [
    {"scope_digest": "f"*64}, {"source_sha256": "f"*64},
    {"revision_id": str(OTHER)}, {"generation": 4},
    {"state": "APPROVED"}, {"state": "TRUSTED"}, {"state": "RETRY"},
])
def test_read_rejects_tampered_marker(expired_scope, changed):
    marker = pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"} | changed
    with pytest.raises(N4OnlyPilotDenied):
        require_readable_pilot(marker, **identity())


class Result:
    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def all(self):
        return self.value


class ReadSession:
    def __init__(self, *, missing=False):
        self.calls = []
        self.missing = missing

    async def execute(self, statement, params):
        sql = str(statement)
        assert sql.strip().upper().startswith("SELECT")  # no mutation, ever
        self.calls.append((sql, params))
        if "FROM public.n4_extraction_runs r" in sql:
            for required in (
                "JOIN public.document_processing_operations op",
                "op.fencing_token = r.fencing_token",
                "r.source_sha256 = :source_sha",
                "r.fencing_token > :predecessor_fence",
                "dr.valid_to IS NULL",
            ):
                assert required in sql
            assert params["source_sha"] == SHA
            assert params["generation"] == 3
            return Result(None if self.missing else {
                "run_id": RUN, "status": "PARTIAL",
                "fencing_token": 9, "total_windows": 23,
            })
        if "count(*) FROM public.n4_candidate_findings" in sql:
            return Result(2)
        if "SELECT f.finding_key, f.window_ordinal" in sql:
            assert params["offset"] == 1 and params["limit"] == 1
            return Result([{
                "finding_key": "risk-synthetic",
                "window_ordinal": 4,
                "claim": {"review_status": "PROPOSED", "source_quote": "N2 dummy quote"},
                "source_refs": [{
                    "source_kind": "MODEL_SAFE_PROJECTION",
                    "evidence_status": "EXACT_MODEL_SAFE_MATCH",
                    "analysis_span": [110, 124],
                    "document_revision_id": str(REVISION),
                    "source_sha256": SHA,
                }],
            }])
        raise AssertionError("unexpected SELECT")


class ReadRepo:
    def __init__(self, marker, *, revision=REVISION, project=PROJECT, missing=False):
        self.doc = SimpleNamespace(
            project_id=project,
            document_metadata={
                "n4_only_pilot": marker, "parsed_text_revision_id": str(revision),
            },
        )
        self.session = ReadSession(missing=missing)

    async def get_by_id(self, tenant_id, document_id):
        return self.doc


@pytest.mark.asyncio
async def test_partial_get_200_with_proposed_citations_and_pagination(expired_scope):
    marker = pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"}
    repo = ReadRepo(marker)
    result = await read_n4_only_pilot_findings(
        project_id=PROJECT, document_id=DOCUMENT,
        tenant_id=TENANT, user_id=OWNER,
        offset=1, limit=1, repo=repo,
    )
    assert result["status"] == "PARTIAL_UNASSESSED"
    assert result["ledger_status"] == "PARTIAL"
    assert result["total_findings"] == 2
    assert result["offset"] == 1 and result["limit"] == 1
    assert result["fencing_token"] == 9
    assert result["generation"] == 3
    assert result["document_revision_id"] == str(REVISION)
    assert result["n12_status"] == "UNASSESSED"
    assert result["original_pdf_coverage"] == "UNVERIFIED"
    assert result["findings"][0]["review_state"] == "PROPOSED"
    assert result["findings"][0]["n2_quote_status"] == "VERIFIED_IN_N2"
    assert result["findings"][0]["n2_source_refs"][0]["analysis_span"] == [110, 124]
    assert result["findings"][0]["pdf_quote_status"] == "UNVERIFIED"
    assert len(repo.session.calls) == 3  # all SELECT; no task or reservation


@pytest.mark.asyncio
@pytest.mark.parametrize("denial", [
    "foreign_owner", "foreign_tenant", "foreign_project",
    "stale_revision", "tampered_marker",
])
async def test_get_denies_without_any_ledger_lookup(expired_scope, denial):
    marker = pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"}
    repo = ReadRepo(marker, revision=OTHER if denial == "stale_revision" else REVISION,
                    project=OTHER if denial == "foreign_project" else PROJECT)
    if denial == "tampered_marker":
        repo.doc.document_metadata["n4_only_pilot"] = marker | {"scope_digest": "0" * 64}
    with pytest.raises(HTTPException) as exc:
        await read_n4_only_pilot_findings(
            project_id=PROJECT, document_id=DOCUMENT,
            tenant_id=OTHER if denial == "foreign_tenant" else TENANT,
            user_id=OTHER if denial == "foreign_owner" else OWNER,
            offset=1, limit=1, repo=repo,
        )
    assert exc.value.status_code == 404
    assert repo.session.calls == []


@pytest.mark.asyncio
async def test_get_does_not_expose_stale_run_fencing(expired_scope):
    repo = ReadRepo(pilot_marker(expired_scope) | {"state": "PARTIAL_UNASSESSED"},
                    missing=True)
    with pytest.raises(HTTPException) as exc:
        await read_n4_only_pilot_findings(
            project_id=PROJECT, document_id=DOCUMENT,
            tenant_id=TENANT, user_id=OWNER, offset=1, limit=1, repo=repo,
        )
    assert exc.value.status_code == 404
    assert len(repo.session.calls) == 1
