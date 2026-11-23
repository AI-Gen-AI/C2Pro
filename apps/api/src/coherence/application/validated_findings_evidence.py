"""Pure, calibration-gated A26 validated and projected project exposure scoring."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import exp, isfinite

DIMENSIONS = ("SCOPE", "BUDGET", "LEGAL", "TIME", "QUALITY", "TECHNICAL")
STATES = ("CONFIRMED", "PENDING", "REJECTED")


@dataclass(frozen=True)
class ExposureFact:
    canonical_key: str
    dimension: str
    severity: str
    state: str
    evidence_id: str | None
    materiality: float | None = None
    accepted_risk: bool = False
    mitigation_fraction: float = 0.0
    mitigation_evidence_id: str | None = None
    mitigation_verified: bool = False


@dataclass(frozen=True)
class ScorePair:
    validated: float | None
    projected: float | None


@dataclass(frozen=True)
class ExposureScore:
    global_score: ScorePair
    dimensions: Mapping[str, ScorePair]
    validated_fact_count: int
    pending_fact_count: int


@dataclass(frozen=True)
class ExposureBands:
    severity: Mapping[str, float]
    dimension_weights: Mapping[str, float]
    materiality_scale: float
    calibrated: bool
    revision: str

    def validate(self) -> None:
        if not self.calibrated or not self.revision.strip():
            raise ValueError("exposure bands not calibrated/versioned")
        if set(self.severity) != {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("incomplete severity bands")
        if set(self.dimension_weights) != set(DIMENSIONS):
            raise ValueError("incomplete dimension weights")
        weights = list(self.dimension_weights.values())
        if not all(isfinite(x) and x > 0 for x in weights) or abs(sum(weights) - 1) > 1e-9:
            raise ValueError("dimension weights must sum to 1")
        vals = [self.severity[x] for x in ("LOW", "MEDIUM", "HIGH", "CRITICAL")]
        if not all(isfinite(v) and v >= 0 for v in vals) or vals != sorted(vals):
            raise ValueError("severity bands must be positive and ordered")
        if not isfinite(self.materiality_scale) or self.materiality_scale <= 0:
            raise ValueError("invalid materiality scale")


def _exposure(fact: ExposureFact, cfg: ExposureBands) -> float:
    if fact.dimension not in DIMENSIONS or fact.state not in STATES:
        raise ValueError("unsupported dimension/review state")
    if not fact.canonical_key.strip() or fact.severity not in cfg.severity:
        raise ValueError("missing typed fact key or severity")
    if fact.materiality is not None and (not isfinite(fact.materiality) or fact.materiality < 0):
        raise ValueError("invalid materiality")
    if not isfinite(fact.mitigation_fraction) or not 0 <= fact.mitigation_fraction <= 1:
        raise ValueError("invalid mitigation")
    value = cfg.severity[fact.severity]
    if fact.materiality is not None:
        value *= 1 + fact.materiality / cfg.materiality_scale
    if fact.mitigation_verified:
        if not fact.mitigation_evidence_id:
            raise ValueError("verified mitigation requires evidence")
        value *= 1 - fact.mitigation_fraction
    # accepted_risk has intentionally no effect: human acceptance is not mitigation.
    return value


def _category(exposures: Mapping[tuple[str, str], float], dim: str) -> float | None:
    values = [x for (_, d), x in exposures.items() if d == dim]
    return round(100 * exp(-sum(values)), 2) if values else None


def _global(scores: Mapping[str, float | None], weights: Mapping[str, float]) -> float | None:
    valid = {d: score for d, score in scores.items() if score is not None}
    if not valid:
        return None
    total = sum(weights[d] for d in valid)
    return round(sum(weights[d] * s for d, s in valid.items()) / total, 2)


def calculate_exposure_score(facts: Sequence[ExposureFact], cfg: ExposureBands) -> ExposureScore:
    """Deduplicate by (canonical typed fact/clause, dimension).

    Confirmed facts affect validated and projected; pending only projected.
    Rejected and ungrounded facts do neither. Multiple sources never double-count.
    """
    cfg.validate()
    validated: dict[tuple[str, str], float] = {}
    pending: dict[tuple[str, str], float] = {}
    for fact in facts:
        value = _exposure(fact, cfg)
        if fact.state == "REJECTED" or not fact.evidence_id:
            continue
        key = (fact.canonical_key, fact.dimension)
        target = validated if fact.state == "CONFIRMED" else pending
        target[key] = max(target.get(key, 0), value)
    projected = dict(validated)
    for key, val in pending.items():
        projected[key] = max(projected.get(key, 0), val)
    v = {dim: _category(validated, dim) for dim in DIMENSIONS}
    p = {dim: _category(projected, dim) for dim in DIMENSIONS}
    return ExposureScore(
        global_score=ScorePair(
            _global(v, cfg.dimension_weights), _global(p, cfg.dimension_weights)
        ),
        dimensions={d: ScorePair(v[d], p[d]) for d in DIMENSIONS},
        validated_fact_count=len(validated),
        pending_fact_count=len(set(pending) - set(validated)),
    )
