"""G3: N4 ProjectGraph signals link to the physical clause only when source-grounded."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from src.analysis.adapters.graph.project_graph import (
    _aggregate_cross_doc_inputs,
    _artifact_risk_signals,
)
from src.analysis.adapters.graph.review_source_references import risk_quote_source_key
from src.analysis.adapters.persistence.risk_source_clause_binding import (
    load_trusted_risk_source_clause_ids,
)
from src.analysis.domain.contracts import DocumentArtifact, RiskItem

TENANT, PROJECT, DOC, REV = uuid4(), uuid4(), uuid4(), uuid4()


def _risk(ref: str | None, status: str | None = "VERIFIED", **kw: object) -> RiskItem:
    if status == "VERIFIED":
        kw.setdefault("source_quote", f"quote {ref}")
    return RiskItem(
        title=f"risk {ref}", description="d", category="LEGAL", impact="HIGH",
        clause_ref=ref, source_quote_status=status, **kw,
    )


def _artifact(*risks: RiskItem, doc: UUID = DOC, rev: UUID | None = REV) -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(doc), document_revision_id=str(rev) if rev else None,
        doc_type="contract", extracted_risks=list(risks),
    )


def _clause(code: str, *, text: str | None = None, tenant: UUID = TENANT, rev: UUID = REV,
            doc: UUID = DOC) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(), tenant_id=tenant, project_id=PROJECT, document_id=doc, revision_id=rev,
        clause_code=code, full_text=text if text is not None else f"{code} Heading text quote {code}",
    )


class _Repo:
    def __init__(self, clauses: list[SimpleNamespace] | Exception) -> None:
        self.clauses, self.calls = clauses, []

    async def list_clauses_bound_to_revision(self, tenant_id, document_id, revision_id):
        self.calls.append((tenant_id, document_id, revision_id))
        if isinstance(self.clauses, Exception):
            raise self.clauses
        return self.clauses


def _k(ref: str, quote: str | None = None) -> str:
    return risk_quote_source_key(DOC, REV, ref, quote or f"quote {ref}")  # type: ignore[return-value]


async def _load(artifact: DocumentArtifact, repo: _Repo) -> dict[str, str]:
    return await load_trusted_risk_source_clause_ids(
        None, tenant_id=TENANT, project_id=PROJECT, artifacts=[artifact], repository=repo
    )


@pytest.mark.asyncio
async def test_verified_exact_reference_resolves_physical_clause() -> None:
    clause = _clause("6.1")
    mapping = await _load(_artifact(_risk("6.1")), _Repo([clause]))
    assert list(mapping.values()) == [str(clause.id)]
    signals, _, _ = _aggregate_cross_doc_inputs([_artifact(_risk("6.1"))], mapping)
    assert [s.clause_id for s in signals] == [str(clause.id)]


@pytest.mark.asyncio
async def test_unverified_quote_never_resolves_and_skips_lookup() -> None:
    repo = _Repo([_clause("6.1")])
    for status in (None, "NOT_FOUND", "UNVERIFIED"):
        assert await _load(_artifact(_risk("6.1", status)), repo) == {}
    assert repo.calls == []


@pytest.mark.asyncio
async def test_non_numeric_clause_ref_not_resolved() -> None:
    assert await _load(_artifact(_risk("Clause 6.1 payment")), _Repo([_clause("6.1")])) == {}


@pytest.mark.asyncio
async def test_duplicate_and_heading_conflict_fail_closed() -> None:
    assert await _load(_artifact(_risk("6.1")), _Repo([_clause("6.1"), _clause("6.1")])) == {}
    # explicit code says 6.1 but physical heading says 6.2 -> ambiguous
    assert await _load(
        _artifact(_risk("6.1")), _Repo([_clause("6.1", text="6.2 Other quote 6.1")])
    ) == {}


@pytest.mark.asyncio
async def test_cross_tenant_and_stale_revision_clauses_ignored() -> None:
    clauses = [_clause("6.1", tenant=uuid4()), _clause("6.1", rev=uuid4())]
    assert await _load(_artifact(_risk("6.1")), _Repo(clauses)) == {}


@pytest.mark.asyncio
async def test_no_revision_and_repo_exception_fall_back() -> None:
    repo = _Repo([_clause("6.1")])
    assert await _load(_artifact(_risk("6.1"), rev=None), repo) == {}
    assert repo.calls == []
    assert await _load(_artifact(_risk("6.1")), _Repo(RuntimeError("db down"))) == {}


def test_multiple_independent_risks_bind_per_risk_and_keep_order() -> None:
    a, b = _clause("6.1"), _clause("6.3")
    art = _artifact(_risk("6.1"), _risk("6.2"), _risk("6.3"), _risk("6.3", None))
    mapping = {
        _k("6.1"): str(a.id),
        _k("6.3"): str(b.id),
    }
    signals, _, finding_count = _aggregate_cross_doc_inputs([art], mapping)
    # Unverified proposals remain in the artifact, but do not feed N8 scoring.
    assert len(art.extracted_risks) == 4
    assert finding_count == 0  # unrelated, counts coherence findings only
    assert _artifact_risk_signals(art, mapping).dropped_reasons == {
        "quote_not_independently_verified": 2
    }
    assert [s.clause_id for s in signals] == [str(a.id), str(b.id)]
    assert [s.raw_data["title"] for s in signals] == [
        art.extracted_risks[0].title, art.extracted_risks[2].title
    ]


def test_only_revision_bound_risks_are_scored_without_changing_the_proposals() -> None:
    art = _artifact(_risk("6.1", likelihood="LOW"), _risk("6.2", confidence=0.4))
    clause = uuid4()
    base, base_cov, base_n = _aggregate_cross_doc_inputs([art])
    bound, bound_cov, bound_n = _aggregate_cross_doc_inputs(
        [art], {_k("6.1"): str(clause)}
    )
    assert len(art.extracted_risks) == 2  # never erase proposals
    assert base == [] and base_cov == {}
    assert base_n == bound_n == 0
    assert bound_cov == {"LEGAL": True}
    assert len(bound) == 1
    assert bound[0].clause_id == str(clause)
    assert bound[0].raw_data["source_binding_kind"] == "verified_clause"
    assert bound[0].raw_data["artifact_revision_id"] == str(REV)
    assert bound[0].raw_data["source"] == "document_artifact.extracted_risks"
    assert _artifact_risk_signals(art, {_k("6.1"): str(clause)}).dropped_count == 1


def test_unverified_status_ignores_mapping_even_if_key_present() -> None:
    art = _artifact(_risk("6.1", "NOT_FOUND"))
    signals, _, finding_count = _aggregate_cross_doc_inputs(
        [art], {_k("6.1"): str(uuid4())}
    )
    assert signals == []
    assert finding_count == 0
    assert _artifact_risk_signals(art, {_k("6.1"): str(uuid4())}).dropped_reasons == {
        "quote_not_independently_verified": 1
    }
    assert len(art.extracted_risks) == 1  # proposal is not erased


@pytest.mark.asyncio
async def test_verified_empty_or_missing_quote_never_gets_physical_clause() -> None:
    repo = _Repo([_clause("6.1")])
    for quote in (None, "", "   "):
        art = _artifact(_risk("6.1", source_quote=quote))
        assert await _load(art, repo) == {}
    assert repo.calls == []


@pytest.mark.asyncio
async def test_quote_in_other_physical_clause_fails_closed() -> None:
    clauses = [_clause("6.1", text="6.1 Payment"), _clause("6.2", text="6.2 Quoted elsewhere")]
    art = _artifact(_risk("6.1", source_quote="Quoted elsewhere"))
    assert await _load(art, _Repo(clauses)) == {}


@pytest.mark.asyncio
async def test_missing_full_text_and_non_exact_quote_fail_closed() -> None:
    no_text = _clause("6.1")
    no_text.full_text = None
    assert await _load(_artifact(_risk("6.1")), _Repo([no_text])) == {}
    # exact substring only: no case/whitespace normalisation
    clause = _clause("6.1", text="6.1 Pay within 30 days")
    for quote in ("pay within 30 days", "Pay  within 30 days"):
        assert await _load(_artifact(_risk("6.1", source_quote=quote)), _Repo([clause])) == {}


@pytest.mark.asyncio
async def test_two_risks_same_code_only_valid_quote_binds() -> None:
    clause = _clause("6.1", text="6.1 Pay within 30 days")
    good = _risk("6.1", source_quote="Pay within 30 days")
    bad = _risk("6.1", source_quote="Absent from clause")
    art = _artifact(bad, good)
    mapping = await _load(art, _Repo([clause]))
    assert list(mapping.values()) == [str(clause.id)]
    signals, _, _ = _aggregate_cross_doc_inputs([art], mapping)
    assert [s.clause_id for s in signals] == [str(clause.id)]
    assert [s.raw_data["title"] for s in signals] == [good.title]
    assert len(art.extracted_risks) == 2
    assert _artifact_risk_signals(art, mapping).dropped_reasons == {
        "quote_not_independently_verified": 1
    }


@pytest.mark.asyncio
async def test_exact_trusted_bound_keeps_original_quote() -> None:
    clause = _clause("6.1", text="6.1 Pay within 30 days")
    risk = _risk("6.1", source_quote="Pay within 30 days")
    mapping = await _load(_artifact(risk), _Repo([clause]))
    assert mapping == {_k("6.1", "Pay within 30 days"): str(clause.id)}
    assert risk.source_quote == "Pay within 30 days"


@pytest.mark.parametrize("bad", ["not-a-uuid", "", "6.1", "12345678-1234-1234-1234"])
def test_invalid_mapped_uuid_falls_back_to_surrogate(bad: str) -> None:
    art = _artifact(_risk("6.1"))
    signals, _, _ = _aggregate_cross_doc_inputs([art], {_k("6.1"): bad})
    assert signals == []


def test_mapped_uuid_is_canonicalised_and_code_only_key_ignored() -> None:
    clause = uuid4()
    art = _artifact(_risk("6.1"))
    signals, _, _ = _aggregate_cross_doc_inputs([art], {_k("6.1"): str(clause).upper()})
    assert signals[0].clause_id == str(clause)
    legacy = f"{DOC}|{REV}|6.1"
    signals, _, _ = _aggregate_cross_doc_inputs([art], {legacy: str(clause)})
    assert signals == []


def test_unbound_verified_flag_must_not_seed_projectgraph_score() -> None:
    """The persisted artifact may claim VERIFIED without any original-source proof."""
    risk = _risk("6.1", source_quote="INVENTED SOURCE PASSAGE")
    art = _artifact(risk)
    signals, coverage, _ = _aggregate_cross_doc_inputs([art], None)
    assert signals == [] and coverage == {}
    result = _artifact_risk_signals(art, None)
    assert result.dropped_reasons == {"quote_not_independently_verified": 1}
    assert art.extracted_risks == [risk]


def test_empty_mapping_is_not_a_source_binding() -> None:
    art = _artifact(_risk("6.1"))
    signals, coverage, _ = _aggregate_cross_doc_inputs([art], {})
    assert signals == [] and coverage == {}


@pytest.mark.asyncio
async def test_cross_document_unbound_risk_reports_unassessed(monkeypatch):
    """Failure to bind cannot yield a global score even if another signal scores."""
    from src.analysis.adapters.graph import project_graph as mod
    from src.coherence.models import EnrichedCoherenceResult

    async def fake_evaluate(*args, **kwargs):
        return EnrichedCoherenceResult(overall_score=91.0)

    monkeypatch.setattr(mod, "evaluate_coherence_async", fake_evaluate)
    art = _artifact(_risk("6.1"))
    outcome = await mod.evaluate_artifact_set(
        [art], project_id=PROJECT, tenant_id=TENANT, llm_on=False,
        risk_source_clause_ids={},
    )
    assert outcome.summary.overall_score is None
    assert outcome.summary.score_reason == "unassessed_unbound_risk_provenance"
    assert outcome.summary.excluded_risk_count == 1
    assert outcome.summary.excluded_risk_reasons == {
        "quote_not_independently_verified": 1
    }
    assert "risk_provenance" in outcome.summary.insufficient_data_reasons
    assert art.extracted_risks[0].title == "risk 6.1"

@pytest.mark.asyncio
async def test_unavailable_source_loader_has_distinct_reason(monkeypatch):
    from src.analysis.adapters.graph import project_graph as mod
    from src.coherence.models import EnrichedCoherenceResult

    async def fake_evaluate(*args, **kwargs):
        return EnrichedCoherenceResult(overall_score=94.0)

    monkeypatch.setattr(mod, "evaluate_coherence_async", fake_evaluate)
    result = await mod.evaluate_artifact_set(
        [_artifact(_risk("6.1"))],
        project_id=PROJECT, tenant_id=TENANT, llm_on=False,
        risk_source_clause_ids={}, risk_source_binding_status="UNAVAILABLE",
    )
    assert result.summary.overall_score is None
    assert result.summary.score_reason == "unassessed_risk_source_lookup_unavailable"
    assert result.summary.excluded_risk_count == 1
