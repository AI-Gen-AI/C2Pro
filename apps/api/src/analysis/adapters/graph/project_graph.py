"""Serial ProjectGraph skeleton for ADR-017 Tier-2.

TS-UT-ADR017-PG-001
"""

from __future__ import annotations

from time import perf_counter
from uuid import UUID

import structlog
from langgraph.graph import END, StateGraph

from src.analysis.adapters.graph.project_coherence_result import ProjectCoherenceResult
from src.analysis.adapters.graph.project_graph_state import ProjectGraphState
from src.analysis.adapters.graph.risk_signal_bridge import build_risk_signals
from src.analysis.domain.contracts import DocumentArtifact
from src.analysis.domain.node_result import NodeResult, NodeStatus
from src.coherence.graph.graph import evaluate_coherence_async
from src.coherence.graph.state import EvaluationConfig
from src.coherence.models import EnrichedCoherenceResult, FindingSignal
from src.health.application.coherence_subscore import coherence_subscore_from_result
from src.health.application.contract_scorer import score_contract_dimension
from src.health.application.documentation_scorer import score_documentation_dimension
from src.health.application.governance_scorer import score_governance_dimension
from src.health.application.health_engine import assemble_health_vector
from src.health.application.risk_scorer import score_risk_dimension
from src.project_state.domain.entities import ProjectRisk

logger = structlog.get_logger(__name__)

PROJECT_GRAPH_NODE_ORDER = [
    "load_current_artifacts",
    "align_entities",
    "cross_doc_coherence",
    "change_impact",
    "health",
    "snapshot_delta",
    "write_snapshot",
    "alert_correlation",
    "hitl_routing",
]


def _ok(node: str, data: object = None) -> list[NodeResult]:
    return [NodeResult(node=node, status=NodeStatus.OK, data=data)]


def _skipped(node: str, reason: str) -> list[NodeResult]:
    return [NodeResult(node=node, status=NodeStatus.SKIPPED, degradation_reason=reason)]


def _degraded(node: str, reason: str) -> list[NodeResult]:
    return [NodeResult(node=node, status=NodeStatus.DEGRADED, degradation_reason=reason)]


def _artifact_key(artifact: DocumentArtifact) -> str:
    return artifact.document_revision_id or artifact.document_id


def load_current_artifacts(state: ProjectGraphState) -> dict[str, object]:
    artifacts = state.get("artifacts", [])
    return {
        "artifacts": artifacts,
        "node_results": _ok("load_current_artifacts", {"artifact_count": len(artifacts)}),
    }


def align_entities(state: ProjectGraphState) -> dict[str, object]:
    anchors_by_doc_type: dict[str, list[str]] = {}
    for artifact in state.get("artifacts", []):
        anchors_by_doc_type.setdefault(artifact.doc_type, []).append(_artifact_key(artifact))
    return {
        "node_results": _ok(
            "align_entities",
            {"doc_type_groups": anchors_by_doc_type},
        )
    }


def _coherence_category(value: str | None) -> str | None:
    normalized = (value or "").upper().strip()
    aliases = {
        "SCHEDULE": "TIME",
        "TIME": "TIME",
        "TECH": "TECHNICAL",
        "TECHNICAL": "TECHNICAL",
        "FINANCIAL": "BUDGET",
        "BUDGET": "BUDGET",
        "LEGAL": "LEGAL",
        "SCOPE": "SCOPE",
        "QUALITY": "QUALITY",
    }
    return aliases.get(normalized)


def _severity_to_impact(value: object) -> float:
    normalized = getattr(value, "value", value)
    return {
        "HIGH": 0.7,
        "MEDIUM": 0.5,
        "LOW": 0.3,
    }.get(str(normalized).upper(), 0.3)


def _finding_signal_for_artifact(
    artifact: DocumentArtifact,
    finding_index: int,
    finding: object,
) -> FindingSignal | None:
    category = _coherence_category(getattr(finding, "category", None))
    if category is None:
        return None
    impact = (
        1.0 - (float(finding.score) / 100.0)
        if getattr(finding, "score", None) is not None
        else _severity_to_impact(getattr(finding, "severity", None))
    )
    return FindingSignal(
        rule_id=finding.rule_id or "ARTIFACT-COHERENCE-FINDING",
        clause_id=f"{_artifact_key(artifact)}:finding:{finding_index}",
        source="deterministic",
        impact_score=max(0.0, min(1.0, impact)),
        confidence=finding.confidence or 0.7,
        severity=str(getattr(getattr(finding, "severity", None), "value", "MEDIUM")).lower(),
        category=category,
        evidence_summary=finding.message,
        quote=finding.evidence_ref or finding.message,
        raw_data={
            "artifact_id": artifact.document_id,
            "artifact_revision_id": artifact.document_revision_id,
            "doc_type": artifact.doc_type,
            "source": "document_artifact.coherence_findings",
        },
    )


def _aggregate_cross_doc_inputs(
    artifacts: list[DocumentArtifact],
) -> tuple[list[FindingSignal], dict[str, bool], int]:
    signals: list[FindingSignal] = []
    coverage: dict[str, bool] = {}
    finding_count = 0

    for artifact in artifacts:
        risk_result = build_risk_signals(
            [risk.model_dump(mode="json") for risk in artifact.extracted_risks],
            clause_id=_artifact_key(artifact),
        )
        for signal in risk_result.signals:
            signals.append(
                signal.model_copy(
                    update={
                        "raw_data": {
                            **signal.raw_data,
                            "artifact_id": artifact.document_id,
                            "artifact_revision_id": artifact.document_revision_id,
                            "doc_type": artifact.doc_type,
                            "source": "document_artifact.extracted_risks",
                        }
                    }
                )
            )
        coverage.update(risk_result.coverage_seed)

        for index, finding in enumerate(artifact.coherence_findings):
            signal = _finding_signal_for_artifact(artifact, index, finding)
            if signal is not None:
                signals.append(signal)
                coverage[signal.category] = True
                finding_count += 1

    return signals, coverage, finding_count


def _coherence_summary(
    result: EnrichedCoherenceResult,
    *,
    signal_count: int,
    finding_count: int,
    artifact_count: int,
    llm_on: bool,
) -> ProjectCoherenceResult:
    return ProjectCoherenceResult(
        overall_score=result.overall_score,
        category_scores={
            str(item.category).upper(): item.score
            for item in result.category_breakdown
        },
        signal_count=signal_count,
        finding_count=finding_count,
        artifact_count=artifact_count,
        llm_on=llm_on,
        insufficient_data_reasons=list(result.score_missing_dimensions or []),
        score_reason=result.score_reason,
    )


async def cross_doc_coherence(state: ProjectGraphState) -> dict[str, object]:
    started = perf_counter()
    artifacts = state.get("artifacts", [])
    project_id = state["project_id"]
    tenant_id = state["tenant_id"]
    if not artifacts:
        return {
            "coherence_result": None,
            "node_results": _skipped("cross_doc_coherence", "no artifacts"),
        }

    signals, coverage, finding_count = _aggregate_cross_doc_inputs(artifacts)
    llm_on = await is_coherence_llm_enabled(tenant_id)
    degraded = False
    overall_score_present = False
    try:
        engine_result = await evaluate_coherence_async(
            [],
            str(project_id),
            config=EvaluationConfig(
                low_budget_mode=not llm_on,
                tenant_id=str(tenant_id),
                project_id=str(project_id),
                missing_dimensions=[
                    category
                    for category in ("SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY")
                    if not coverage.get(category, False)
                ],
            ),
            seed_signals=signals,
            seed_coverage=coverage,
        )
        overall_score_present = engine_result.overall_score is not None
        summary = _coherence_summary(
            engine_result,
            signal_count=len(signals),
            finding_count=finding_count,
            artifact_count=len(artifacts),
            llm_on=llm_on,
        )
        status = _ok("cross_doc_coherence", summary)
        return {"coherence_result": summary, "node_results": status}
    except Exception as exc:  # noqa: BLE001 - ProjectGraph node must degrade, not crash.
        degraded = True
        return {
            "coherence_result": None,
            "node_results": _degraded("cross_doc_coherence", str(exc)),
        }
    finally:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "project_graph_cross_doc_coherence",
            project_id=str(project_id),
            tenant_id=str(tenant_id),
            artifact_count=len(artifacts),
            llm_on=llm_on,
            duration_ms=duration_ms,
            overall_score_present=overall_score_present,
            degraded=degraded,
            signal_count=len(signals),
        )


def change_impact(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "impact_result": None,
        "node_results": _skipped("change_impact", "pending ADR-016-L3 change impact"),
    }


def health(state: ProjectGraphState) -> dict[str, object]:
    try:
        artifacts = state.get("artifacts", [])
        project_id = state["project_id"]
        tenant_id = state["tenant_id"]
        risks = [
            ProjectRisk(entity_id=UUID(risk.source or artifact.document_id), payload=risk)
            if _is_uuid(risk.source)
            else ProjectRisk(entity_id=UUID(int=0), payload=risk)
            for artifact in artifacts
            for risk in artifact.extracted_risks
        ]
        coherence = state.get("coherence_result")
        if isinstance(coherence, dict):
            coherence_result = ProjectCoherenceResult.model_validate(coherence)
        else:
            coherence_result = coherence
        vector = assemble_health_vector(
            project_id,
            tenant_id,
            signals=[
                score_risk_dimension(
                    risks,
                    assessment_ran=bool(artifacts),
                    extraction_quality=_artifact_confidence(artifacts),
                ),
                score_contract_dimension(
                    [],
                    [],
                    coherence_subscore=coherence_subscore_from_result(coherence_result),
                ),
                score_documentation_dimension(None),
                score_governance_dimension(None),
            ],
            prior_composite=None,
        )
        return {
            "health_result": vector.model_dump(mode="json"),
            "node_results": _ok("health", {"composite_score": vector.composite_score}),
        }
    except Exception as exc:  # noqa: BLE001 - ProjectGraph node must degrade, not crash.
        return {
            "health_result": None,
            "node_results": _degraded("health", str(exc)),
        }


def _is_uuid(value: str | None) -> bool:
    if value is None:
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _artifact_confidence(artifacts: list[DocumentArtifact]) -> float | None:
    scores = [
        artifact.confidence_score
        for artifact in artifacts
        if artifact.confidence_score is not None
    ]
    if not scores:
        return None
    return sum(scores) / len(scores)


def snapshot_delta(state: ProjectGraphState) -> dict[str, object]:
    changed_artifact_ids = [_artifact_key(artifact) for artifact in state.get("artifacts", [])]
    return {
        "changed_artifact_ids": changed_artifact_ids,
        "node_results": _ok(
            "snapshot_delta",
            {
                "changed_artifact_count": len(changed_artifact_ids),
                "previous_snapshot_id": str(state.get("previous_snapshot_id"))
                if state.get("previous_snapshot_id") is not None
                else None,
            },
        ),
    }


def write_snapshot(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "snapshot_id": None,
        "node_results": _skipped("write_snapshot", "pending ADR-015 snapshot write"),
    }


def alert_correlation(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "node_results": _skipped("alert_correlation", "pending ADR-019 alert correlation"),
    }


def hitl_routing(_state: ProjectGraphState) -> dict[str, object]:
    return {
        "node_results": _skipped("hitl_routing", "pending ADR-020 HITL routing"),
    }


async def is_project_graph_enabled(tenant_id: UUID) -> bool:
    """Resolve the per-tenant ProjectGraph gate, failing closed."""

    try:
        from src.alerts.adapters.persistence.tenant_repository import (
            SqlAlchemyTenantRepository,
        )
        from src.config import settings
        from src.core.database import get_raw_session
        from src.core.feature_flags import TenantFlagsService

        async with get_raw_session() as session:
            return await TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=settings,
            ).is_enabled(tenant_id, "feature_v3_project_graph")
    except Exception as exc:  # noqa: BLE001 - live ProjectGraph invocation must fail closed.
        logger.warning(
            "feature_v3_project_graph_resolution_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


async def is_coherence_llm_enabled(tenant_id: UUID) -> bool:
    """Resolve the per-tenant coherence LLM gate, failing closed."""

    try:
        from src.alerts.adapters.persistence.tenant_repository import (
            SqlAlchemyTenantRepository,
        )
        from src.config import settings
        from src.core.database import get_raw_session
        from src.core.feature_flags import TenantFlagsService

        async with get_raw_session() as session:
            return await TenantFlagsService(
                tenant_repository=SqlAlchemyTenantRepository(session),
                settings=settings,
            ).is_enabled(tenant_id, "feature_v3_coherence_llm")
    except Exception as exc:  # noqa: BLE001 - coherence LLM gate must fail closed.
        logger.warning(
            "feature_v3_coherence_llm_resolution_failed",
            tenant_id=str(tenant_id),
            error=str(exc),
        )
        return False


def build_project_graph():
    """Build the serial Tier-2 graph skeleton."""

    workflow = StateGraph(ProjectGraphState)
    workflow.add_node("load_current_artifacts", load_current_artifacts)
    workflow.add_node("align_entities", align_entities)
    workflow.add_node("cross_doc_coherence", cross_doc_coherence)
    workflow.add_node("change_impact", change_impact)
    workflow.add_node("health", health)
    workflow.add_node("snapshot_delta", snapshot_delta)
    workflow.add_node("write_snapshot", write_snapshot)
    workflow.add_node("alert_correlation", alert_correlation)
    workflow.add_node("hitl_routing", hitl_routing)

    workflow.set_entry_point("load_current_artifacts")
    workflow.add_edge("load_current_artifacts", "align_entities")
    workflow.add_edge("align_entities", "cross_doc_coherence")
    workflow.add_edge("cross_doc_coherence", "change_impact")
    workflow.add_edge("change_impact", "health")
    workflow.add_edge("health", "snapshot_delta")
    workflow.add_edge("snapshot_delta", "write_snapshot")
    workflow.add_edge("write_snapshot", "alert_correlation")
    workflow.add_edge("alert_correlation", "hitl_routing")
    workflow.add_edge("hitl_routing", END)
    return workflow.compile()


__all__ = [
    "PROJECT_GRAPH_NODE_ORDER",
    "build_project_graph",
    "cross_doc_coherence",
    "is_coherence_llm_enabled",
    "is_project_graph_enabled",
]
