"""
I7 Coherence Scoring Application Service
Test Suite ID: TS-I7-SCORE-SVC-001
"""

from uuid import UUID

from src.modules.coherence.domain.entities import CoherenceAlert
from src.modules.scoring.domain.entities import OverallScore, ScoreConfig
from src.modules.scoring.domain.services import ScoreAggregator


class CoherenceScoringService:
    """Aggregates coherence alerts into a deterministic overall score."""

    def __init__(self) -> None:
        self._default_profile = ScoreConfig(
            severity_weights={"Critical": 1.0, "High": 0.7, "Medium": 0.4, "Low": 0.1},
            alert_type_multipliers={
                "Schedule Mismatch": 1.5,
                "Budget Mismatch": 1.2,
                "Scope-Procurement Mismatch": 1.0,
            },
            severity_thresholds={"Critical": 2.0, "High": 1.0, "Medium": 0.5},
        )
        self._tenant_profiles: dict[UUID, ScoreConfig] = {
            UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"): ScoreConfig(
                severity_weights={"Critical": 2.0, "High": 1.0, "Medium": 0.5, "Low": 0.2},
                alert_type_multipliers={"Schedule Mismatch": 2.0, "Budget Mismatch": 1.5},
                severity_thresholds={"Critical": 3.0, "High": 1.5, "Medium": 0.7},
            ),
            UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"): ScoreConfig(
                severity_weights={"Critical": 0.8, "High": 0.5, "Medium": 0.3, "Low": 0.1},
                alert_type_multipliers={"Schedule Mismatch": 1.0, "Budget Mismatch": 1.0},
                severity_thresholds={"Critical": 1.5, "High": 0.8, "Medium": 0.4},
            ),
        }
        self._project_profiles: dict[tuple[UUID, UUID], ScoreConfig] = {}

    async def aggregate_coherence_score(
        self,
        alerts: list[CoherenceAlert],
        tenant_id: UUID,
        project_id: UUID,
    ) -> OverallScore:
        profile = self._resolve_profile(tenant_id=tenant_id, project_id=project_id)
        aggregator = ScoreAggregator(config=profile)
        return aggregator.aggregate_score(alerts)

    def _resolve_profile(self, tenant_id: UUID, project_id: UUID) -> ScoreConfig:
        # Project-specific configuration always takes precedence.
        if (tenant_id, project_id) in self._project_profiles:
            return self._project_profiles[(tenant_id, project_id)].model_copy(deep=True)
        if tenant_id in self._tenant_profiles:
            return self._tenant_profiles[tenant_id].model_copy(deep=True)
        return self._default_profile.model_copy(deep=True)
