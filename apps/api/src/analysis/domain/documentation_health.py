"""TS-ADR-013-GRAPH-001 - Documentation-health signal for ADR-018."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.analysis.domain.node_result import NodeResult, NodeStatus


class DocumentationHealthSignal(BaseModel):
    """Typed aggregate of material-node runtime trust outcomes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    degraded_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_nodes: list[str] = Field(default_factory=list)
    degraded_nodes: list[str] = Field(default_factory=list)
    skipped_nodes: list[str] = Field(default_factory=list)


def build_documentation_health_signal(
    node_results: list[NodeResult],
) -> DocumentationHealthSignal:
    failed = [result.node for result in node_results if result.status is NodeStatus.FAILED]
    degraded = [
        result.node for result in node_results if result.status is NodeStatus.DEGRADED
    ]
    skipped = [result.node for result in node_results if result.status is NodeStatus.SKIPPED]
    return DocumentationHealthSignal(
        total_count=len(node_results),
        failed_count=len(failed),
        degraded_count=len(degraded),
        skipped_count=len(skipped),
        failed_nodes=failed,
        degraded_nodes=degraded,
        skipped_nodes=skipped,
    )


__all__ = ["DocumentationHealthSignal", "build_documentation_health_signal"]
