"""
Custom weights domain tests (TDD - RED phase).

Refers to Suite ID: TS-UD-COH-SCR-003.
"""

from __future__ import annotations

import pytest

from src.coherence.domain.category_weights import CoherenceCategory
from src.coherence.domain.custom_weights import (
    CustomWeightProfile,
    CustomWeightRegistry,
)


class TestCustomWeights:
    """Refers to Suite ID: TS-UD-COH-SCR-003"""

    def test_001_create_custom_profile_with_valid_weights(self) -> None:
        profile = CustomWeightProfile.model_validate(
            {
                "name": "balanced_plus",
                "weights": {
                    CoherenceCategory.SCOPE: 0.20,
                    CoherenceCategory.BUDGET: 0.20,
                    CoherenceCategory.QUALITY: 0.15,
                    CoherenceCategory.TECHNICAL: 0.15,
                    CoherenceCategory.LEGAL: 0.15,
                    CoherenceCategory.TIME: 0.15,
                },
            }
        )
        registry = CustomWeightRegistry()

        registry.create_profile(profile=profile)

        assert registry.get_profile("balanced_plus").name == "balanced_plus"

    def test_002_reject_weights_sum_not_one(self) -> None:
        profile = CustomWeightProfile.model_validate(
            {
                "name": "invalid_sum",
                "weights": {
                    CoherenceCategory.SCOPE: 0.40,
                    CoherenceCategory.BUDGET: 0.40,
                    CoherenceCategory.QUALITY: 0.15,
                    CoherenceCategory.TECHNICAL: 0.15,
                    CoherenceCategory.LEGAL: 0.15,
                    CoherenceCategory.TIME: 0.15,
                },
            }
        )

        with pytest.raises(ValueError, match="sum to 1.0"):
            CustomWeightRegistry().create_profile(profile=profile)

    def test_003_reject_missing_category_without_normalization(self) -> None:
        profile = CustomWeightProfile.model_validate(
            {
                "name": "missing_quality",
                "weights": {
                    CoherenceCategory.SCOPE: 0.30,
                    CoherenceCategory.BUDGET: 0.30,
                    CoherenceCategory.TECHNICAL: 0.10,
                    CoherenceCategory.LEGAL: 0.15,
                    CoherenceCategory.TIME: 0.15,
                },
            }
        )

        with pytest.raises(ValueError, match="Missing category weights"):
            CustomWeightRegistry().create_profile(profile=profile, normalize=False)

    def test_004_normalize_partial_weights_auto(self) -> None:
        profile = CustomWeightProfile.model_validate(
            {
                "name": "partial",
                "weights": {
                    CoherenceCategory.BUDGET: 0.30,
                    CoherenceCategory.TIME: 0.25,
                },
            }
        )
        registry = CustomWeightRegistry()

        registry.create_profile(profile=profile, normalize=True)

        stored = registry.get_profile("partial")
        assert stored.weights[CoherenceCategory.BUDGET] == pytest.approx(0.30)
        assert stored.weights[CoherenceCategory.TIME] == pytest.approx(0.25)
        assert sum(stored.weights.values()) == pytest.approx(1.0)

    def test_005_custom_budget_30_distribution(self) -> None:
        registry = CustomWeightRegistry()
        profile = CustomWeightProfile.model_validate(
            {
                "name": "budget_30",
                "weights": {
                    CoherenceCategory.BUDGET: 0.30,
                },
            }
        )

        registry.create_profile(profile=profile, normalize=True)

        stored = registry.get_profile("budget_30")
        other = (1.0 - 0.30) / 5
        assert stored.weights[CoherenceCategory.BUDGET] == pytest.approx(0.30)
        assert stored.weights[CoherenceCategory.SCOPE] == pytest.approx(other)

    def test_006_custom_time_25_distribution(self) -> None:
        registry = CustomWeightRegistry()
        profile = CustomWeightProfile.model_validate(
            {
                "name": "time_25",
                "weights": {
                    CoherenceCategory.TIME: 0.25,
                },
            }
        )

        registry.create_profile(profile=profile, normalize=True)

        stored = registry.get_profile("time_25")
        other = (1.0 - 0.25) / 5
        assert stored.weights[CoherenceCategory.TIME] == pytest.approx(0.25)
        assert stored.weights[CoherenceCategory.BUDGET] == pytest.approx(other)

    def test_007_resolve_weights_by_project_type(self) -> None:
        registry = CustomWeightRegistry()
        residential = CustomWeightProfile.model_validate(
            {
                "name": "residential",
                "project_type": "residential",
                "weights": {
                    CoherenceCategory.BUDGET: 0.50,
                    CoherenceCategory.TIME: 0.20,
                    CoherenceCategory.SCOPE: 0.30,
                },
            }
        )
        commercial = CustomWeightProfile.model_validate(
            {
                "name": "commercial",
                "project_type": "commercial",
                "weights": {
                    CoherenceCategory.BUDGET: 0.20,
                    CoherenceCategory.TIME: 0.50,
                    CoherenceCategory.SCOPE: 0.30,
                },
            }
        )
        registry.create_profile(profile=residential, normalize=True)
        registry.create_profile(profile=commercial, normalize=True)

        resolved = registry.get_by_project_type("commercial")

        assert resolved.name == "commercial"
        assert resolved.weights[CoherenceCategory.TIME] == pytest.approx(0.50)

    def test_008_weight_history_tracking(self) -> None:
        registry = CustomWeightRegistry()
        profile = CustomWeightProfile.model_validate(
            {
                "name": "mutable",
                "weights": {
                    CoherenceCategory.BUDGET: 0.30,
                },
            }
        )
        registry.create_profile(profile=profile, normalize=True)
        registry.update_profile(
            name="mutable",
            weights={CoherenceCategory.BUDGET: 0.25, CoherenceCategory.TIME: 0.75},
            normalize=True,
        )

        history = registry.get_history("mutable")

        assert len(history) == 2
        assert history[0].weights[CoherenceCategory.BUDGET] == pytest.approx(0.30)
        assert history[1].weights[CoherenceCategory.TIME] == pytest.approx(0.75)

    def test_009_profile_read_returns_copy(self) -> None:
        registry = CustomWeightRegistry()
        profile = CustomWeightProfile.model_validate(
            {
                "name": "copy_check",
                "weights": {
                    CoherenceCategory.BUDGET: 0.30,
                },
            }
        )
        registry.create_profile(profile=profile, normalize=True)

        fetched = registry.get_profile("copy_check")
        fetched.weights[CoherenceCategory.BUDGET] = 1.0

        assert registry.get_profile("copy_check").weights[CoherenceCategory.BUDGET] == pytest.approx(0.30)

    def test_010_default_fallback_when_project_type_not_found(self) -> None:
        registry = CustomWeightRegistry()

        resolved = registry.get_by_project_type("unknown")

        assert resolved.name == "default"
        assert resolved.weights[CoherenceCategory.SCOPE] == pytest.approx(0.20)
