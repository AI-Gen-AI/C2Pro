"""TS-UA-HEALTH-024-L4-3 — the real N8 and N17 production seams.

These exercise the actual pipeline functions, not the helper in isolation:

- **N8 seam**: `coherence_scorer_node` must hand the canonical `Clause[]` and the
  coherence subgraph's `FindingSignal[]` to the assessment builder exactly once, and
  return the versioned artifact in its graph-state update.
- **N17 seam**: `PersistAnalysisUseCase.execute()` must carry that artifact into
  `AnalysisWrite.result_json` additively — `risks`/`wbs` preserved — and must OMIT the
  key entirely when no assessment ran (absent = NOT EVALUATED, never an empty result).

No DB is involved: the coherence subgraph and the repositories are stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from src.analysis.ports.types import AlertWrite, AnalysisWrite
from src.coherence.models import Clause, EnrichedCoherenceResult, FindingSignal
from src.health.domain.analysis_assessment import (
    SINGLE_DOCUMENT_ASSESSMENT_KEY,
    SINGLE_DOCUMENT_ASSESSMENT_VERSION,
    decode_single_document_assessment,
)

# =====================================================================================
# N8 seam — the real coherence_scorer_node
# =====================================================================================


@pytest.mark.asyncio
async def test_n8_node_feeds_canonical_clauses_and_findings_to_the_builder_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    subgraph_findings = [
        FindingSignal(rule_id="R-SCOPE-CLARITY-01", clause_id="c1", impact_score=0.4, category="SCOPE"),
        FindingSignal(rule_id="CROSS-BUDGET-SCOPE", clause_id="c1|c2", impact_score=0.6, category="CROSS"),
    ]

    async def fake_evaluate_coherence_async(
        clauses: list[Clause],
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
            finding_signals=subgraph_findings,
        )

    monkeypatch.setattr(
        "src.coherence.graph.graph.evaluate_coherence_async", fake_evaluate_coherence_async
    )

    # Wrap (not replace) the real builder so we observe the exact production arguments.
    import src.health.application.document_assessment as doc_assessment

    seen: list[tuple[list[Clause], list[FindingSignal]]] = []
    real_builder = doc_assessment.build_document_assessment_artifact

    def recording_builder(clauses, finding_signals):  # noqa: ANN001, ANN202
        seen.append((list(clauses), list(finding_signals)))
        return real_builder(clauses, finding_signals)

    monkeypatch.setattr(doc_assessment, "build_document_assessment_artifact", recording_builder)

    state: dict[str, Any] = {
        "project_id": str(uuid4()),
        "document_id": str(uuid4()),
        "document_text": "Payment terms and price: the budget and bill of quantities (BoQ) apply.",
        "doc_type": "contract",
        "messages": [],
        "extracted_risks": [],
        "extracted_wbs": [],
        "confidence_score": 0.95,
        "tenant_id": str(uuid4()),
        "analysis_id": str(uuid4()),
        "bom_items": [],
    }

    update = await coherence_scorer_node(state)

    # invoked exactly once, with the canonical contracts
    assert len(seen) == 1
    clauses, findings = seen[0]
    assert clauses and all(isinstance(c, Clause) for c in clauses)
    assert all(isinstance(f, FindingSignal) for f in findings)
    assert [f.rule_id for f in findings] == ["R-SCOPE-CLARITY-01", "CROSS-BUDGET-SCOPE"]

    # the graph update carries the versioned artifact
    artifact = update["single_document_assessment"]
    assert artifact is not None
    assert artifact[SINGLE_DOCUMENT_ASSESSMENT_KEY]["version"] == SINGLE_DOCUMENT_ASSESSMENT_VERSION

    decoded = decode_single_document_assessment(artifact)
    assert decoded is not None
    assert len(decoded.coverage.assessments) == 6
    # CROSS reached the artifact and stayed out of the canonical categories
    assert [f.rule_id for f in decoded.coverage.cross_findings] == ["CROSS-BUDGET-SCOPE"]
    assert all(
        all(f.category != "CROSS" for f in a.findings) for a in decoded.coverage.assessments
    )


@pytest.mark.asyncio
async def test_n8_node_emits_no_artifact_when_the_subgraph_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed N8 is NOT EVALUATED — the artifact must be absent, never empty-but-known."""
    from src.analysis.adapters.graph.nodes_extended import coherence_scorer_node

    async def exploding(*_args: object, **_kwargs: object) -> EnrichedCoherenceResult:
        raise RuntimeError("coherence subgraph unavailable")

    monkeypatch.setattr("src.coherence.graph.graph.evaluate_coherence_async", exploding)

    update = await coherence_scorer_node(
        {
            "project_id": str(uuid4()),
            "document_id": str(uuid4()),
            "document_text": "text",
            "doc_type": "contract",
            "messages": [],
            "extracted_risks": [],
            "extracted_wbs": [],
            "confidence_score": 0.5,
            "tenant_id": str(uuid4()),
            "analysis_id": str(uuid4()),
            "bom_items": [],
        }
    )
    assert update["single_document_assessment"] is None


# =====================================================================================
# N17 seam — the real PersistAnalysisUseCase
# =====================================================================================


class _FakeAnalysisRepo:
    def __init__(self) -> None:
        self.written: list[AnalysisWrite] = []
        self.alerts: list[AlertWrite] = []
        self.committed = False

    async def add_analysis(self, analysis: AnalysisWrite, tenant_id: UUID | None = None) -> None:
        self.written.append(analysis)

    async def add_alerts(self, alerts: Any, tenant_id: UUID | None = None) -> None:
        self.alerts.extend(alerts)

    async def get_result_json(self, analysis_id: UUID, tenant_id: UUID) -> dict[str, Any] | None:
        return None

    async def list_recent(self, *, limit: int, offset: int, tenant_id: UUID | None = None) -> list[Any]:
        return []

    async def count_all(self, tenant_id: UUID | None = None) -> int:
        return 0

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True


class _FakeWbsRepo:
    def __init__(self) -> None:
        self.created: list[tuple[UUID, list[dict[str, Any]]]] = []

    async def bulk_create_from_dicts(self, project_id: UUID, items: list[dict[str, Any]]) -> None:
        self.created.append((project_id, items))


class _FakeSession:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> None:
        self.statements.append(statement)


async def _persist(assessment: dict[str, Any] | None) -> AnalysisWrite:
    from src.analysis.application.persist_analysis_use_case import (
        PersistAnalysisCommand,
        PersistAnalysisUseCase,
    )

    repo = _FakeAnalysisRepo()
    await PersistAnalysisUseCase(
        analysis_repo=repo, wbs_repo=_FakeWbsRepo(), session=_FakeSession()
    ).execute(
        PersistAnalysisCommand(
            project_id=uuid4(),
            tenant_id=uuid4(),
            extracted_risks=[{"title": "Late delivery", "category": "TIME", "risk_score": 7}],
            extracted_wbs=[{"code": "1.1", "name": "Mobilisation"}],
            coherence_score=None,
            coherence_breakdown={},
            single_document_assessment=assessment,
        )
    )
    assert repo.committed
    assert len(repo.written) == 1
    return repo.written[0]


@pytest.mark.asyncio
async def test_n17_persists_the_artifact_alongside_risks_and_wbs() -> None:
    from src.health.application.document_assessment import build_document_assessment_artifact

    artifact = build_document_assessment_artifact(
        [Clause(id="c1", text="Payment terms and price: the budget and BoQ set unit rates.")],
        [FindingSignal(rule_id="R1", clause_id="c1", impact_score=0.4, category="BUDGET")],
    )
    written = await _persist(artifact)

    # existing keys preserved
    assert written.result_json["risks"] == [
        {"title": "Late delivery", "category": "TIME", "risk_score": 7}
    ]
    assert written.result_json["wbs"] == [{"code": "1.1", "name": "Mobilisation"}]

    # versioned assessment actually entered result_json and reconstructs
    decoded = decode_single_document_assessment(written.result_json)
    assert decoded is not None
    assert decoded.version == SINGLE_DOCUMENT_ASSESSMENT_VERSION
    assert [f.rule_id for f in decoded.finding_signals] == ["R1"]
    assert len(decoded.coverage.assessments) == 6


@pytest.mark.asyncio
async def test_n17_omits_the_key_entirely_when_no_assessment_ran() -> None:
    written = await _persist(None)

    assert written.result_json["risks"]
    assert written.result_json["wbs"]
    # absent, NOT an empty artifact — absence is the NOT EVALUATED signal
    assert SINGLE_DOCUMENT_ASSESSMENT_KEY not in written.result_json
    assert decode_single_document_assessment(written.result_json) is None
