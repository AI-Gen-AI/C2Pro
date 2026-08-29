"""TS-UA-HEALTH-024-R1 — persisted-clause evidence granularity at N8 (P0b-R1).

R1 replaces the single synthetic whole-document ``coherence.models.Clause`` that N8 used
to build with the **already-persisted** ``documents.clauses`` rows for the analysed
document. No new parser is introduced: ingestion already segments and persists contract
clauses idempotently, and R1 only reads them back through the Documents bounded-context
read abstraction.

What these tests pin:

* **Identity** — canonical evidence identity is the persisted ``clauses.id`` UUID.
  ``clause_code`` (``AUTO-001``) is metadata, never identity.
* **Ownership** — the analysis graph reaches persisted clauses through the Documents read
  port only; ``ClauseORM`` never enters the analysis bounded context.
* **Determinism** — a stable total order over clauses (source offsets when present, else
  ``clause_code`` with a persisted-UUID tie-break), so replay produces identical evidence.
* **Honesty** — a contract with zero persisted clauses degrades to explicit
  ``DOCUMENT`` granularity; it must never present a synthetic document-level id as if it
  were a persisted clause id. Missing source spans stay ``None``; they are never
  reinterpreted as ``0``.
* **Compatibility** — non-contract documents keep the legacy whole-document clause, and
  the L4-3 contract ("the assessment runs exactly once") is preserved.

No DB is involved: the Documents read port is stubbed with in-memory domain clauses.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.coherence.models import Clause as CoherenceClause
from src.coherence.models import EnrichedCoherenceResult, FindingSignal
from src.documents.domain.models import Clause as PersistedClause
from src.documents.domain.models import ClauseType
from src.health.domain.analysis_assessment import (
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    decode_single_document_assessment,
)

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = UUID("33333333-3333-3333-3333-333333333333")


def _persisted(
    *,
    clause_id: UUID | None = None,
    code: str = "AUTO-001",
    text: str | None = "The Contractor shall perform the Works.",
    clause_type: ClauseType | None = ClauseType.SCOPE,
    title: str | None = None,
    start: int | None = None,
    end: int | None = None,
    entities: dict[str, Any] | None = None,
) -> PersistedClause:
    return PersistedClause(
        id=clause_id or uuid4(),
        project_id=PROJECT_ID,
        tenant_id=TENANT_ID,
        document_id=DOCUMENT_ID,
        clause_code=code,
        clause_type=clause_type,
        title=title,
        full_text=text,
        text_start_offset=start,
        text_end_offset=end,
        extracted_entities=entities if entities is not None else {},
        extraction_confidence=0.65,
        extraction_model="deterministic-contract-ingestion",
    )


# Six texts drawn from real EPC contract language, one per canonical category. Each is a
# separate persisted clause, so a single contract must produce multi-category evidence.
SIX_CATEGORY_CLAUSE_TEXTS: dict[str, str] = {
    "SCOPE": (
        "The scope of work comprises the design, supply and installation of the plant, "
        "including all deliverables listed in the statement of work and the work "
        "breakdown structure. Any change of scope requires a change order."
    ),
    "BUDGET": (
        "The contract price is EUR 12,500,000. Payment terms: the Employer shall pay each "
        "invoice within 30 days. The budget and the bill of quantities (BoQ) govern all "
        "cost and price adjustments to the contract amount."
    ),
    "SCHEDULE": (
        "The completion date is 2027-06-30. The baseline schedule, its milestones and the "
        "critical path shall be updated monthly. Delay to any milestone deadline entitles "
        "the Employer to liquidated damages per day of delay."
    ),
    "QUALITY": (
        "All works shall be subject to inspection, testing and acceptance in accordance "
        "with the quality assurance plan. Non-conformities shall be recorded and the "
        "quality control records submitted for approval before handover."
    ),
    "TECHNICAL": (
        "The technical specification requires that all equipment comply with the "
        "applicable design standards and the technical requirements of the specification "
        "documents, including materials, drawings and performance tolerances."
    ),
    "LEGAL": (
        "In the event of breach, the party in default shall indemnify the other party. "
        "Termination for convenience, warranty obligations, liability caps and the "
        "governing law and dispute resolution clause apply to this agreement."
    ),
}


async def _fake_coherence_result(
    clauses: list[CoherenceClause],
    project_id: str = "default",
    config: object | None = None,
    seed_signals: list[object] | None = None,
    seed_coverage: dict[str, bool] | None = None,
) -> EnrichedCoherenceResult:
    return EnrichedCoherenceResult(
        overall_score=None,
        score_version="coherence-v1",
        score_reason="insufficient_evidence",
        score_missing_dimensions=["schedule", "budget"],
        calculated_at=datetime.now(UTC),
        finding_signals=[],
    )


def _state(**overrides: Any) -> dict[str, Any]:
    state: dict[str, Any] = {
        "project_id": str(PROJECT_ID),
        "document_id": str(DOCUMENT_ID),
        "tenant_id": str(TENANT_ID),
        "analysis_id": str(uuid4()),
        "document_text": "whole document text",
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "bom_items": [],
        "confidence_score": 0.9,
    }
    state.update(overrides)
    return state


def _stub_loader(
    monkeypatch: pytest.MonkeyPatch,
    clauses: list[PersistedClause] | None = None,
    *,
    raises: Exception | None = None,
) -> list[tuple[UUID, UUID]]:
    """Stub the persisted-clause loader at the N8 seam and record its arguments."""
    import src.analysis.adapters.graph.nodes_extended as node_module

    calls: list[tuple[UUID, UUID]] = []

    async def loader(tenant_id: UUID, document_id: UUID) -> tuple[PersistedClause, ...]:
        calls.append((tenant_id, document_id))
        if raises is not None:
            raise raises
        return tuple(clauses or ())

    monkeypatch.setattr(node_module, "load_persisted_clause_evidence", loader)
    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async", _fake_coherence_result
    )
    return calls


# =====================================================================================
# Deterministic ordering (Documents domain)
# =====================================================================================


class TestDeterministicOrdering:
    def test_source_offsets_win_when_available(self) -> None:
        from src.documents.domain.clause_ordering import order_clause_evidence

        third = _persisted(code="AUTO-003", start=900)
        first = _persisted(code="AUTO-001", start=10)
        second = _persisted(code="AUTO-002", start=120)

        ordered = order_clause_evidence([third, first, second])

        assert [c.clause_code for c in ordered] == ["AUTO-001", "AUTO-002", "AUTO-003"]

    def test_falls_back_to_clause_code_when_offsets_are_absent(self) -> None:
        from src.documents.domain.clause_ordering import order_clause_evidence

        ordered = order_clause_evidence(
            [_persisted(code="AUTO-010"), _persisted(code="AUTO-002"), _persisted(code="AUTO-001")]
        )

        assert [c.clause_code for c in ordered] == ["AUTO-001", "AUTO-002", "AUTO-010"]

    def test_persisted_uuid_breaks_ties_and_never_reorders_on_replay(self) -> None:
        from src.documents.domain.clause_ordering import order_clause_evidence

        low = _persisted(clause_id=UUID(int=1), code="AUTO-001")
        high = _persisted(clause_id=UUID(int=9), code="AUTO-001")

        assert [c.id for c in order_clause_evidence([high, low])] == [low.id, high.id]
        assert [c.id for c in order_clause_evidence([low, high])] == [low.id, high.id]

    def test_clauses_with_offsets_are_ordered_before_clauses_without(self) -> None:
        """A mixed population still yields one total, reproducible order."""
        from src.documents.domain.clause_ordering import order_clause_evidence

        spanned = _persisted(code="AUTO-050", start=5)
        unspanned = _persisted(code="AUTO-001")

        assert [c.clause_code for c in order_clause_evidence([unspanned, spanned])] == [
            "AUTO-050",
            "AUTO-001",
        ]


# =====================================================================================
# Clause adapter — persisted domain Clause -> coherence.models.Clause
# =====================================================================================


class TestClauseAdapter:
    def test_canonical_identity_is_the_persisted_uuid(self) -> None:
        from src.analysis.application.clause_evidence import to_coherence_clauses

        persisted = _persisted(clause_id=UUID(int=7), code="AUTO-001")

        (mapped,) = to_coherence_clauses([persisted], doc_type="contract")

        assert mapped.id == str(UUID(int=7))
        assert isinstance(mapped, CoherenceClause)

    def test_clause_code_is_metadata_never_identity(self) -> None:
        from src.analysis.application.clause_evidence import to_coherence_clauses

        (mapped,) = to_coherence_clauses(
            [_persisted(clause_id=UUID(int=7), code="AUTO-042")], doc_type="contract"
        )

        assert mapped.id != "AUTO-042"
        assert mapped.data["clause_code"] == "AUTO-042"

    def test_carries_type_title_entities_and_lineage(self) -> None:
        from src.analysis.application.clause_evidence import to_coherence_clauses

        (mapped,) = to_coherence_clauses(
            [
                _persisted(
                    code="AUTO-004",
                    text="Payment within 30 days.",
                    clause_type=ClauseType.PAYMENT,
                    title="Payment",
                    entities={"category": "BUDGET", "payment_term_days": 30},
                )
            ],
            doc_type="contract",
        )

        assert mapped.text == "Payment within 30 days."
        assert mapped.data["clause_type"] == "payment"
        assert mapped.data["title"] == "Payment"
        assert mapped.data["extracted_entities"] == {
            "category": "BUDGET",
            "payment_term_days": 30,
        }
        assert mapped.data["document_type"] == "contract"
        assert mapped.data["source_document_id"] == str(DOCUMENT_ID)
        assert mapped.data["evidence_granularity"] == "clause"

    def test_missing_source_spans_stay_null_and_are_never_zeroed(self) -> None:
        from src.analysis.application.clause_evidence import to_coherence_clauses

        (mapped,) = to_coherence_clauses([_persisted(start=None, end=None)], doc_type="contract")

        assert mapped.data["text_start_offset"] is None
        assert mapped.data["text_end_offset"] is None

    def test_absent_full_text_maps_to_empty_text_without_fabrication(self) -> None:
        from src.analysis.application.clause_evidence import to_coherence_clauses

        (mapped,) = to_coherence_clauses([_persisted(text=None)], doc_type="contract")

        assert mapped.text == ""

    def test_every_persisted_clause_survives_the_mapping(self) -> None:
        """No silent truncation: the adapter never caps or drops evidence."""
        from src.analysis.application.clause_evidence import to_coherence_clauses

        persisted = [_persisted(code=f"AUTO-{i:03d}") for i in range(1, 61)]

        mapped = to_coherence_clauses(persisted, doc_type="contract")

        assert len(mapped) == 60
        assert len({c.id for c in mapped}) == 60


# =====================================================================================
# Documents read port
# =====================================================================================


class TestDocumentsReadPort:
    @pytest.mark.asyncio
    async def test_read_port_is_tenant_scoped_and_returns_deterministic_order(self) -> None:
        from src.documents.application.read_clause_evidence import read_clause_evidence

        seen: list[tuple[UUID, UUID]] = []

        class _Reader:
            async def list_clauses_for_document(
                self, tenant_id: UUID, document_id: UUID
            ) -> list[PersistedClause]:
                seen.append((tenant_id, document_id))
                return [_persisted(code="AUTO-002"), _persisted(code="AUTO-001")]

        result = await read_clause_evidence(_Reader(), TENANT_ID, DOCUMENT_ID)

        assert seen == [(TENANT_ID, DOCUMENT_ID)]
        assert [c.clause_code for c in result] == ["AUTO-001", "AUTO-002"]

    def test_the_real_repository_satisfies_the_clause_evidence_read_port(self) -> None:
        """Pins the adapter to the port so a repository rename cannot silently break N8."""
        import inspect

        from src.documents.adapters.persistence.sqlalchemy_document_repository import (
            SqlAlchemyDocumentRepository,
        )
        from src.documents.ports.clause_evidence_reader import ClauseEvidenceReader

        assert isinstance(SqlAlchemyDocumentRepository(session=None), ClauseEvidenceReader)
        signature = inspect.signature(SqlAlchemyDocumentRepository.list_clauses_for_document)
        assert list(signature.parameters) == ["self", "tenant_id", "document_id"]

    @pytest.mark.asyncio
    async def test_loader_reads_through_the_port_inside_a_tenant_scoped_session(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The composition root opens an RLS-scoped session and delegates to the port."""
        from contextlib import asynccontextmanager

        import src.core.database as database_module
        import src.documents.application.read_clause_evidence as read_module
        from src.analysis.adapters.graph.clause_evidence_loader import (
            load_persisted_clause_evidence,
        )

        opened_for: list[UUID] = []

        @asynccontextmanager
        async def fake_session(tenant_id: UUID):  # noqa: ANN202
            opened_for.append(tenant_id)
            yield object()

        read_calls: list[tuple[UUID, UUID]] = []

        async def fake_read(reader, tenant_id, document_id):  # noqa: ANN001, ANN202
            read_calls.append((tenant_id, document_id))
            return (_persisted(code="AUTO-001"),)

        monkeypatch.setattr(database_module, "get_session_with_tenant", fake_session)
        monkeypatch.setattr(read_module, "read_clause_evidence", fake_read)

        result = await load_persisted_clause_evidence(TENANT_ID, DOCUMENT_ID)

        assert opened_for == [TENANT_ID]
        assert read_calls == [(TENANT_ID, DOCUMENT_ID)]
        assert [c.clause_code for c in result] == ["AUTO-001"]

    def test_analysis_graph_never_imports_the_clause_orm(self) -> None:
        """Bounded-context ownership: N8 reads clauses only through the Documents port."""
        from pathlib import Path

        import src.analysis.adapters.graph.nodes_extended as node_module

        source = Path(node_module.__file__).read_text(encoding="utf-8")

        assert "ClauseORM" not in source
        assert "documents.adapters.persistence" not in source


# =====================================================================================
# N8 behaviour
# =====================================================================================


class TestN8ClauseEvidence:
    @pytest.mark.asyncio
    async def test_contract_with_persisted_clauses_uses_granular_evidence(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        ids = [UUID(int=100 + i) for i in range(3)]
        persisted = [
            _persisted(clause_id=cid, code=f"AUTO-{i + 1:03d}", text=text)
            for i, (cid, text) in enumerate(
                zip(ids, list(SIX_CATEGORY_CLAUSE_TEXTS.values())[:3], strict=True)
            )
        ]
        calls = _stub_loader(monkeypatch, persisted)

        seen: list[list[CoherenceClause]] = []
        import src.health.application.document_assessment as doc_assessment

        real = doc_assessment.build_document_assessment_artifact

        def recording(clauses, finding_signals, *args, **kwargs):  # noqa: ANN001, ANN202
            seen.append(list(clauses))
            return real(clauses, finding_signals, *args, **kwargs)

        monkeypatch.setattr(doc_assessment, "build_document_assessment_artifact", recording)

        update = await coherence_scorer_node(_state())

        assert calls == [(TENANT_ID, DOCUMENT_ID)]
        # The assessment still runs exactly once (L4-3 contract preserved).
        assert len(seen) == 1
        assert [c.id for c in seen[0]] == [str(cid) for cid in ids]
        assert update["single_document_assessment"] is not None

    @pytest.mark.asyncio
    async def test_evidence_clause_ids_are_the_persisted_uuids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        budget_id = UUID(int=501)
        _stub_loader(
            monkeypatch,
            [
                _persisted(
                    clause_id=budget_id,
                    code="AUTO-001",
                    text=SIX_CATEGORY_CLAUSE_TEXTS["BUDGET"],
                )
            ],
        )

        update = await coherence_scorer_node(_state())
        decoded = decode_single_document_assessment(update["single_document_assessment"])

        assert decoded is not None
        assert decoded.evidence_granularity == "clause"
        all_ids = {
            clause_id
            for assessment in decoded.coverage.assessments
            for clause_id in assessment.evidence_clause_ids
        }
        assert all_ids == {str(budget_id)}
        # The synthetic legacy identifier must not appear anywhere.
        assert f"contract-{DOCUMENT_ID}" not in all_ids

    @pytest.mark.asyncio
    async def test_contract_with_zero_persisted_clauses_degrades_to_document_granularity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        _stub_loader(monkeypatch, [])

        update = await coherence_scorer_node(
            _state(document_text=SIX_CATEGORY_CLAUSE_TEXTS["BUDGET"])
        )
        decoded = decode_single_document_assessment(update["single_document_assessment"])

        assert decoded is not None
        # Explicitly labelled document-level — never presented as persisted clause evidence.
        assert decoded.evidence_granularity == "document"
        all_ids = {
            clause_id
            for assessment in decoded.coverage.assessments
            for clause_id in assessment.evidence_clause_ids
        }
        assert all_ids <= {f"contract-{DOCUMENT_ID}"}

    @pytest.mark.asyncio
    async def test_non_contract_retains_the_legacy_whole_document_clause(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        calls = _stub_loader(monkeypatch, [_persisted()])

        seen: list[list[CoherenceClause]] = []
        import src.health.application.document_assessment as doc_assessment

        real = doc_assessment.build_document_assessment_artifact

        def recording(clauses, finding_signals, *args, **kwargs):  # noqa: ANN001, ANN202
            seen.append(list(clauses))
            return real(clauses, finding_signals, *args, **kwargs)

        monkeypatch.setattr(doc_assessment, "build_document_assessment_artifact", recording)

        update = await coherence_scorer_node(
            _state(doc_type="budget", document_text=SIX_CATEGORY_CLAUSE_TEXTS["BUDGET"])
        )

        # Non-contract documents have no persisted clause segmentation — do not even ask.
        assert calls == []
        assert len(seen) == 1
        assert [c.id for c in seen[0]] == [f"budget-{DOCUMENT_ID}"]
        decoded = decode_single_document_assessment(update["single_document_assessment"])
        assert decoded is not None
        assert decoded.evidence_granularity == "document"

    @pytest.mark.asyncio
    async def test_clause_load_failure_degrades_honestly_without_failing_the_node(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        _stub_loader(monkeypatch, raises=RuntimeError("clause store unavailable"))

        update = await coherence_scorer_node(
            _state(document_text=SIX_CATEGORY_CLAUSE_TEXTS["LEGAL"])
        )
        decoded = decode_single_document_assessment(update["single_document_assessment"])

        assert decoded is not None
        assert decoded.evidence_granularity == "document"
        assert update["coherence_reason"] != "node_failed"

    @pytest.mark.asyncio
    async def test_contract_without_tenant_identity_never_queries_the_clause_store(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No tenant id means no RLS scope — degrade rather than read unscoped."""
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        calls = _stub_loader(monkeypatch, [_persisted()])

        update = await coherence_scorer_node(
            _state(tenant_id=None, document_text=SIX_CATEGORY_CLAUSE_TEXTS["SCOPE"])
        )
        decoded = decode_single_document_assessment(update["single_document_assessment"])

        assert calls == []
        assert decoded is not None
        assert decoded.evidence_granularity == "document"

    @pytest.mark.asyncio
    async def test_risk_bridge_signals_keep_a_document_level_clause_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A document-level risk must not be attributed to an arbitrary persisted clause."""
        import src.analysis.adapters.graph.nodes_extended as node_module
        from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

        _stub_loader(
            monkeypatch,
            [_persisted(clause_id=UUID(int=901), code="AUTO-001", text=SIX_CATEGORY_CLAUSE_TEXTS["LEGAL"])],
        )

        seen_ids: list[str] = []
        real_bridge = node_module.build_risk_signals

        def recording_bridge(risks, *, clause_id):  # noqa: ANN001, ANN202
            seen_ids.append(clause_id)
            return real_bridge(risks, clause_id=clause_id)

        monkeypatch.setattr(node_module, "build_risk_signals", recording_bridge)

        await coherence_scorer_node(
            _state(extracted_risks=[{"category": "LEGAL", "description": "Uncapped liability"}])
        )

        assert seen_ids == [f"contract-{DOCUMENT_ID}"]
        assert str(UUID(int=901)) not in seen_ids


# =====================================================================================
# Real router + CROSS structure over granular evidence
# =====================================================================================


class TestGranularEvidenceWithRealRouter:
    def test_one_contract_yields_multi_category_evidence(self) -> None:
        """The real CategoryRouter over persisted clauses — no thresholds tuned."""
        from src.analysis.application.clause_evidence import to_coherence_clauses
        from src.health.application.single_document_coverage import (
            assess_single_document_coverage,
        )

        persisted = [
            _persisted(code=f"AUTO-{i + 1:03d}", text=text)
            for i, text in enumerate(SIX_CATEGORY_CLAUSE_TEXTS.values())
        ]
        clauses = to_coherence_clauses(persisted, doc_type="contract")

        coverage = assess_single_document_coverage(clauses, [])
        present = {a.category.value for a in coverage.assessments if a.evidence_count > 0}

        assert len(present) >= 4, f"granular evidence collapsed to {present}"
        # Distinct persisted clauses carry the evidence, not one document-level blob.
        evidence_ids = {
            cid for a in coverage.assessments for cid in a.evidence_clause_ids
        }
        assert len(evidence_ids) >= 4

    def test_cross_pairs_form_over_distinct_persisted_uuids(self) -> None:
        """R1 unblocks CROSS structurally; the data-key semantics stay R2's job."""
        from src.analysis.application.clause_evidence import to_coherence_clauses
        from src.coherence.graph.nodes import (
            _build_category_cross_pairs,
            _build_enriched_clauses,
        )
        from src.coherence.graph.state import EvaluationConfig

        persisted = [
            _persisted(clause_id=UUID(int=1000 + i), code=f"AUTO-{i + 1:03d}", text=text)
            for i, text in enumerate(SIX_CATEGORY_CLAUSE_TEXTS.values())
        ]
        clauses = list(to_coherence_clauses(persisted, doc_type="contract"))

        enriched = _build_enriched_clauses(clauses, {})
        pairs = _build_category_cross_pairs(enriched, EvaluationConfig())

        assert pairs, "granular clauses must make cross-clause pairing structurally possible"
        for pair in pairs:
            assert pair.clause_a.clause.id != pair.clause_b.clause.id
            UUID(pair.clause_a.clause.id)  # persisted UUIDs survive into the pair
            UUID(pair.clause_b.clause.id)

    def test_whole_document_evidence_cannot_form_cross_pairs(self) -> None:
        """The pre-R1 baseline: one clause, so pairing was structurally impossible."""
        from src.analysis.application.clause_evidence import whole_document_evidence
        from src.coherence.graph.nodes import (
            _build_category_cross_pairs,
            _build_enriched_clauses,
        )
        from src.coherence.graph.state import EvaluationConfig

        evidence = whole_document_evidence(
            doc_type="contract",
            document_id=str(DOCUMENT_ID),
            text=" ".join(SIX_CATEGORY_CLAUSE_TEXTS.values()),
            risks=[],
            wbs=[],
            bom_items=[],
        )

        enriched = _build_enriched_clauses(list(evidence.clauses), {})

        assert len(enriched) == 1
        assert _build_category_cross_pairs(enriched, EvaluationConfig()) == []


# =====================================================================================
# Artifact granularity lineage
# =====================================================================================


class TestArtifactGranularityLineage:
    def test_granularity_is_recorded_in_the_persisted_artifact(self) -> None:
        from src.analysis.application.clause_evidence import (
            EvidenceGranularity,
            to_coherence_clauses,
        )
        from src.health.application.document_assessment import (
            build_document_assessment_artifact,
        )

        clauses = to_coherence_clauses(
            [_persisted(text=SIX_CATEGORY_CLAUSE_TEXTS["BUDGET"])], doc_type="contract"
        )
        artifact = build_document_assessment_artifact(
            clauses, [], granularity=EvidenceGranularity.CLAUSE
        )

        assert artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY]["evidence_granularity"] == "clause"
        decoded = decode_single_document_assessment(artifact)
        assert decoded is not None
        assert decoded.evidence_granularity == "clause"

    def test_legacy_artifacts_without_granularity_decode_as_document_level(self) -> None:
        """Already-persisted v1 artifacts stay readable — absent granularity IS document."""
        from src.health.application.document_assessment import (
            build_document_assessment_artifact,
        )

        artifact = build_document_assessment_artifact(
            [CoherenceClause(id="contract-doc", text=SIX_CATEGORY_CLAUSE_TEXTS["LEGAL"])],
            [FindingSignal(rule_id="R-1", clause_id="contract-doc", impact_score=0.3, category="LEGAL")],
        )
        payload = dict(artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY])
        payload.pop("evidence_granularity", None)

        decoded = decode_single_document_assessment(
            {SINGLE_DOCUMENT_ASSESSMENT_KEY: payload}
        )

        assert decoded is not None
        assert decoded.evidence_granularity == "document"
