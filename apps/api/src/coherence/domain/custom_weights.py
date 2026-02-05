"""
Custom coherence weight profiles domain service.

Refers to Suite ID: TS-UD-COH-SCR-003.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .category_weights import (
    CoherenceCategory,
    get_default_category_weights,
    validate_category_weights,
)


class CustomWeightProfile(BaseModel):
    name: str
    weights: dict[CoherenceCategory, float]
    project_type: str | None = None


class CustomWeightRegistry:
    """Stores and resolves custom weight profiles with minimal history tracking."""

    def __init__(self) -> None:
        default_profile = CustomWeightProfile(
            name="default",
            weights=get_default_category_weights(),
            project_type=None,
        )
        self._profiles: dict[str, CustomWeightProfile] = {default_profile.name: default_profile}
        self._history: dict[str, list[CustomWeightProfile]] = {
            default_profile.name: [default_profile.model_copy(deep=True)]
        }

    def _normalize_weights(
        self,
        weights: dict[CoherenceCategory, float],
    ) -> dict[CoherenceCategory, float]:
        normalized = dict(weights)
        missing = [category for category in CoherenceCategory if category not in normalized]
        current_total = sum(normalized.values())

        if missing:
            if current_total > 1.0:
                raise ValueError("Category weights must sum to 1.0")
            remainder = 1.0 - current_total
            share = remainder / len(missing)
            for category in missing:
                normalized[category] = share
        else:
            if current_total <= 0:
                equal = 1.0 / len(CoherenceCategory)
                normalized = {category: equal for category in CoherenceCategory}
            elif abs(current_total - 1.0) > 1e-9:
                normalized = {category: value / current_total for category, value in normalized.items()}

        validate_category_weights(normalized)
        return normalized

    def create_profile(self, profile: CustomWeightProfile, normalize: bool = False) -> None:
        weights = self._normalize_weights(profile.weights) if normalize else dict(profile.weights)
        if not normalize:
            validate_category_weights(weights)

        stored = profile.model_copy(update={"weights": weights}, deep=True)
        self._profiles[stored.name] = stored
        self._history.setdefault(stored.name, []).append(stored.model_copy(deep=True))

    def update_profile(
        self,
        name: str,
        weights: dict[CoherenceCategory, float],
        normalize: bool = False,
    ) -> None:
        existing = self._profiles[name]
        updated = CustomWeightProfile(
            name=name,
            project_type=existing.project_type,
            weights=weights,
        )
        self.create_profile(profile=updated, normalize=normalize)

    def get_profile(self, name: str) -> CustomWeightProfile:
        return self._profiles[name].model_copy(deep=True)

    def get_by_project_type(self, project_type: str) -> CustomWeightProfile:
        for profile in self._profiles.values():
            if profile.project_type == project_type:
                return profile.model_copy(deep=True)
        return self.get_profile("default")

    def get_history(self, name: str) -> list[CustomWeightProfile]:
        history = self._history.get(name, [])
        return [entry.model_copy(deep=True) for entry in history]
