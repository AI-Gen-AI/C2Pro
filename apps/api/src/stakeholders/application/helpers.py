"""
Shared helper functions for stakeholder scoring and quadrant derivation.
"""
from __future__ import annotations

from typing import Any

from src.stakeholders.domain.models import PowerLevel, InterestLevel, StakeholderQuadrant


def score_from_metadata(metadata: dict[str, Any], key: str, level: PowerLevel | InterestLevel) -> int:
    value = metadata.get(key)
    if isinstance(value, int):
        return max(1, min(value, 10))
    if level == PowerLevel.HIGH or level == InterestLevel.HIGH:
        return 9
    if level == PowerLevel.LOW or level == InterestLevel.LOW:
        return 2
    return 5


def derive_levels_and_quadrant(
    power_score: int | None,
    interest_score: int | None,
) -> tuple[PowerLevel, InterestLevel, StakeholderQuadrant | None]:
    power_level = score_to_power_level(power_score)
    interest_level = score_to_interest_level(interest_score)
    if power_score is None and interest_score is None:
        return power_level, interest_level, None
    quadrant = quadrant_from_scores(
        power_score or level_default(power_level),
        interest_score or level_default(interest_level),
    )
    return power_level, interest_level, quadrant


def level_default(level: PowerLevel | InterestLevel) -> int:
    if level == PowerLevel.HIGH or level == InterestLevel.HIGH:
        return 9
    if level == PowerLevel.LOW or level == InterestLevel.LOW:
        return 2
    return 5


def score_to_power_level(score: int | None) -> PowerLevel:
    if score is None:
        return PowerLevel.MEDIUM
    if score >= 8:
        return PowerLevel.HIGH
    if score <= 4:
        return PowerLevel.LOW
    return PowerLevel.MEDIUM


def score_to_interest_level(score: int | None) -> InterestLevel:
    if score is None:
        return InterestLevel.MEDIUM
    if score >= 8:
        return InterestLevel.HIGH
    if score <= 4:
        return InterestLevel.LOW
    return InterestLevel.MEDIUM


def quadrant_from_scores(power_score: int, interest_score: int) -> StakeholderQuadrant:
    high_power = power_score >= 8
    high_interest = interest_score >= 8
    low_power = power_score <= 4
    low_interest = interest_score <= 4

    if high_power and high_interest:
        return StakeholderQuadrant.KEY_PLAYER
    if high_power and low_interest:
        return StakeholderQuadrant.KEEP_SATISFIED
    if low_power and high_interest:
        return StakeholderQuadrant.KEEP_INFORMED
    return StakeholderQuadrant.MONITOR
