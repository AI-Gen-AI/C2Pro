"""
ECOA v2 orchestrator — composes evidence, conflicts, per-category aggregation
and global aggregation into a single `CoherenceV2Payload`.

Implements the pseudocode of ADR-009 §6 verbatim.

Refers to Suite ID: TS-UA-COH-V2-ORCH-001.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.coherence.application.dtos.coherence_v2_dtos import (
    CategoryV2,
    CoherenceV2Payload,
)
from src.coherence.domain.v2_constants import MIN_EVIDENCE_BY_CATEGORY
from src.coherence.services.v2.aggregator_v2 import GlobalAggregatorV2
from src.coherence.services.v2.category_aggregator import (
    CategoryAggregator,
    worst_open_severity,
)
from src.coherence.services.v2.conflict_service import (
    ConflictCandidate,
    ConflictReport,
    ConflictService,
)
from src.coherence.services.v2.evidence_service import EvidenceService


@dataclass(frozen=True)
class ProjectEvidenceInputs:
    project_docs: list[Any]
    project_context: dict[str, Any]
    rule_signals_by_category: dict[str, list[tuple[str, float]]] = field(default_factory=dict)
    conflict_candidates_by_category: dict[str, list[ConflictCandidate]] = field(
        default_factory=dict
    )
    applicability: dict[str, tuple[bool, str | None]] = field(default_factory=dict)
    assessment_by_category: dict[str, bool] = field(default_factory=dict)


class CoherenceV2Orchestrator:
    def __init__(
        self,
        evidence: EvidenceService,
        conflict: ConflictService,
        cat_agg: CategoryAggregator,
        global_agg: GlobalAggregatorV2,
    ) -> None:
        self._evidence = evidence
        self._conflict = conflict
        self._cat_agg = cat_agg
        self._global_agg = global_agg

    async def run(
        self,
        project_id: UUID,
        evidence_inputs: ProjectEvidenceInputs,
    ) -> CoherenceV2Payload:
        await asyncio.sleep(0)
        categories: list[CategoryV2] = []
        conflicts: list[ConflictReport] = []
        for cat in MIN_EVIDENCE_BY_CATEGORY:
            applicable, reason = evidence_inputs.applicability.get(cat, (True, None))
            evidence = self._evidence.collect(cat, evidence_inputs.project_docs)
            signals = evidence_inputs.rule_signals_by_category.get(cat, [])
            candidates = evidence_inputs.conflict_candidates_by_category.get(cat, [])
            conflict = self._conflict.detect(cat, evidence, candidates)
            conflicts.append(conflict)
            categories.append(
                self._cat_agg.aggregate(
                    category=cat,
                    evidence=evidence,
                    conflict=conflict,
                    rule_signals=signals,
                    applicable=applicable,
                    applicability_reason=reason,
                    assessed=evidence_inputs.assessment_by_category.get(cat, True),
                )
            )

        global_block = self._global_agg.aggregate(
            categories, worst_open_severity=worst_open_severity(conflicts)
        )
        # model_validate: "global" is a Python keyword, only expressible via alias.
        return CoherenceV2Payload.model_validate(
            {
                "project_id": project_id,
                "generated_at": datetime.now(UTC),
                "global": global_block,
                "categories": categories,
            }
        )


__all__ = ["CoherenceV2Orchestrator", "ProjectEvidenceInputs"]
