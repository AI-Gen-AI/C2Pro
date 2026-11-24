"""A26 pure Score synthetic checks: no database, LLM or document payloads."""

from dataclasses import replace
from math import exp, nan

import pytest

from src.coherence.application.validated_findings_evidence import (
    ExposureBands,
    ExposureFact,
    calculate_exposure_score,
)


@pytest.fixture
def cfg():
    return ExposureBands(
        severity={"LOW": 0.05, "MEDIUM": 0.15, "HIGH": 0.3, "CRITICAL": 0.6},
        dimension_weights={
            "SCOPE": 0.20,
            "BUDGET": 0.20,
            "LEGAL": 0.15,
            "TIME": 0.15,
            "QUALITY": 0.15,
            "TECHNICAL": 0.15,
        },
        materiality_scale=100000,
        calibrated=True,
        revision="SYNTHETIC-ONLY",
    )


def fact(**kwargs):
    return ExposureFact(
        **(
            {
                "canonical_key": "typed-clause-1",
                "dimension": "BUDGET",
                "severity": "HIGH",
                "state": "PENDING",
                "evidence_id": "synthetic-quote",
            }
            | kwargs
        )
    )


def test_pending_moves_projected_only(cfg):
    r = calculate_exposure_score([fact()], cfg)
    assert r.global_score.validated is None
    assert 0 < r.global_score.projected < 100
    assert r.dimensions["TIME"].projected is None


def test_confirmation_moves_both_rejection_removes(cfg):
    proposed = calculate_exposure_score([fact()], cfg)
    confirmed = calculate_exposure_score([fact(state="CONFIRMED")], cfg)
    rejected = calculate_exposure_score([fact(state="REJECTED")], cfg)
    assert confirmed.global_score.validated == proposed.global_score.projected
    assert confirmed.global_score.projected == confirmed.global_score.validated
    assert rejected.global_score.projected is None


def test_accepted_risk_does_not_raise_score(cfg):
    original = fact(state="CONFIRMED")
    assert calculate_exposure_score([original], cfg) == calculate_exposure_score(
        [replace(original, accepted_risk=True)], cfg
    )


def test_duplicate_fact_across_sources_counts_once(cfg):
    first = fact(state="CONFIRMED")
    second = replace(first, evidence_id="synthetic-budget-row")
    one = calculate_exposure_score([first], cfg)
    two = calculate_exposure_score([first, second], cfg)
    assert one == two
    assert two.validated_fact_count == 1


def test_mitigation_only_with_verified_evidence(cfg):
    initial = fact(state="CONFIRMED")
    original = calculate_exposure_score([initial], cfg)
    unsupported = calculate_exposure_score([replace(initial, mitigation_fraction=0.7)], cfg)
    corrected = calculate_exposure_score(
        [
            replace(
                initial,
                mitigation_fraction=0.7,
                mitigation_verified=True,
                mitigation_evidence_id="synthetic-mitigation-evidence",
            )
        ],
        cfg,
    )
    assert original == unsupported
    assert corrected.global_score.validated > original.global_score.validated


def test_unknown_dimensions_are_null(cfg):
    r = calculate_exposure_score([fact(state="CONFIRMED")], cfg)
    assert r.dimensions["LEGAL"].validated is None
    assert r.dimensions["TECHNICAL"].projected is None


def test_ungrounded_facts_not_promoted(cfg):
    assert calculate_exposure_score([fact(evidence_id=None)], cfg).global_score.projected is None


def test_materiality_uses_configuration(cfg):
    small = calculate_exposure_score([fact(materiality=0)], cfg)
    large = calculate_exposure_score([fact(materiality=300000)], cfg)
    assert large.global_score.projected < small.global_score.projected


def test_pending_exposure_never_increases_confirmed_score(cfg):
    r = calculate_exposure_score(
        [fact(state="CONFIRMED"), fact(canonical_key="other", severity="LOW")], cfg
    )
    assert r.global_score.projected <= r.global_score.validated


@pytest.mark.parametrize("bad", [{"calibrated": False}, {"revision": ""}, {"materiality_scale": 0}])
def test_uncalibrated_bands_refused(cfg, bad):
    with pytest.raises(ValueError):
        calculate_exposure_score([fact()], replace(cfg, **bad))


def test_verification_without_evidence_is_rejected(cfg):
    with pytest.raises(ValueError, match="requires evidence"):
        calculate_exposure_score([fact(mitigation_verified=True, mitigation_fraction=0.5)], cfg)


def test_new_pending_dimension_cannot_improve_global_score(cfg):
    confirmed = fact(state="CONFIRMED", severity="CRITICAL")
    pending = fact(
        canonical_key="typed-time-2",
        dimension="TIME",
        severity="LOW",
        state="PENDING",
    )
    baseline = calculate_exposure_score([confirmed], cfg)
    combined = calculate_exposure_score([confirmed, pending], cfg)
    assert combined.global_score.validated == baseline.global_score.validated
    assert combined.global_score.projected <= combined.global_score.validated
    assert combined.dimensions["TIME"].validated is None
    assert combined.dimensions["TIME"].projected is not None
    assert combined.pending_fact_count == 1


def test_confirmed_same_key_supersedes_stale_pending_replica(cfg):
    stale_pending = fact(state="PENDING", severity="CRITICAL")
    current = fact(state="CONFIRMED", severity="LOW")
    expected = calculate_exposure_score([current], cfg)
    both_orders = [
        calculate_exposure_score([stale_pending, current], cfg),
        calculate_exposure_score([current, stale_pending], cfg),
    ]
    assert all(result == expected for result in both_orders)
    assert expected.pending_fact_count == 0


def test_duplicate_key_uses_largest_exposure_within_same_state(cfg):
    low = fact(state="CONFIRMED", severity="LOW")
    high = replace(low, severity="HIGH", evidence_id="synthetic-second-source")
    observed = calculate_exposure_score([low, high, low], cfg)
    expected = calculate_exposure_score([high], cfg)
    assert observed == expected
    assert observed.validated_fact_count == 1


def test_assessable_only_weight_normalization_and_all_null(cfg):
    observed = calculate_exposure_score([fact(state="CONFIRMED")], cfg)
    expected = round(100 * exp(-cfg.severity["HIGH"]), 2)
    assert observed.global_score.validated == expected
    assert observed.global_score.projected == expected
    assert observed.dimensions["BUDGET"].validated == expected
    assert all(
        pair.validated is None and pair.projected is None
        for dimension, pair in observed.dimensions.items()
        if dimension != "BUDGET"
    )
    empty = calculate_exposure_score([], cfg)
    assert empty.global_score.validated is None
    assert empty.global_score.projected is None
    assert empty.validated_fact_count == 0
    assert empty.pending_fact_count == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"dimension": "SCHEDULE"},
        {"state": "APPROVED"},
        {"severity": "UNKNOWN"},
        {"canonical_key": "   "},
        {"evidence_id": "   "},
        {"materiality": -1},
        {"materiality": nan},
        {"mitigation_fraction": -0.1},
        {"mitigation_fraction": 1.1},
        {"mitigation_fraction": nan},
        {"mitigation_verified": True, "mitigation_evidence_id": "  "},
    ],
)
def test_invalid_or_unlocated_fact_fails_closed(cfg, bad):
    with pytest.raises(ValueError):
        calculate_exposure_score([fact(**bad)], cfg)


@pytest.mark.parametrize(
    "bad",
    [
        {
            "dimension_weights": dict.fromkeys(
                ("SCOPE", "BUDGET", "LEGAL", "TIME", "QUALITY", "TECHNICAL"), 1
            )
        },
        {"severity": {"LOW": 0.1, "MEDIUM": 0.4, "HIGH": 0.2, "CRITICAL": 0.6}},
        {"severity": {"LOW": 0.1, "MEDIUM": 0.2, "HIGH": 0.3}},
        {"materiality_scale": nan},
    ],
)
def test_bad_configuration_fails_closed(cfg, bad):
    with pytest.raises(ValueError):
        calculate_exposure_score([fact()], replace(cfg, **bad))


def test_verified_mitigation_at_zero_and_full_boundary(cfg):
    confirmed = fact(state="CONFIRMED")
    base = calculate_exposure_score([confirmed], cfg)
    no_discount = calculate_exposure_score(
        [
            replace(
                confirmed,
                mitigation_fraction=0.0,
                mitigation_verified=True,
                mitigation_evidence_id="synthetic-verification",
            )
        ],
        cfg,
    )
    full_discount = calculate_exposure_score(
        [
            replace(
                confirmed,
                mitigation_fraction=1.0,
                mitigation_verified=True,
                mitigation_evidence_id="synthetic-verification",
            )
        ],
        cfg,
    )
    assert no_discount == base
    assert full_discount.global_score.validated == 100
    assert full_discount.global_score.projected == 100


def test_rejected_and_pending_to_confirmed_transition(cfg):
    pending = fact()
    confirmed = replace(pending, state="CONFIRMED")
    rejected = replace(pending, state="REJECTED")
    initial = calculate_exposure_score([pending], cfg)
    accepted = calculate_exposure_score([confirmed], cfg)
    dismissed = calculate_exposure_score([rejected], cfg)
    assert initial.validated_fact_count == 0
    assert initial.pending_fact_count == 1
    assert accepted.validated_fact_count == 1
    assert accepted.pending_fact_count == 0
    assert accepted.global_score.validated == initial.global_score.projected
    assert dismissed.global_score.validated is None
    assert dismissed.global_score.projected is None
    assert dismissed.pending_fact_count == 0


@pytest.mark.parametrize("dimension", ("SCOPE", "BUDGET", "LEGAL", "TIME", "QUALITY", "TECHNICAL"))
def test_matrix_six_dimensions_individually_evaluable(cfg, dimension):
    item = fact(dimension=dimension, state="CONFIRMED")
    observed = calculate_exposure_score([item], cfg)
    assert observed.dimensions[dimension].validated == observed.dimensions[dimension].projected
    assert observed.dimensions[dimension].validated is not None
    assert observed.validated_fact_count == 1
    assert observed.pending_fact_count == 0
    for other in {"SCOPE", "BUDGET", "LEGAL", "TIME", "QUALITY", "TECHNICAL"} - {dimension}:
        assert observed.dimensions[other].validated is None
        assert observed.dimensions[other].projected is None


def test_matrix_typed_key_is_dimension_scoped(cfg):
    budget = fact(state="CONFIRMED", dimension="BUDGET")
    legal = replace(budget, dimension="LEGAL", evidence_id="synthetic-legal-evidence")
    scored = calculate_exposure_score([budget, legal], cfg)
    assert scored.validated_fact_count == 2
    assert scored.pending_fact_count == 0
    assert scored.dimensions["BUDGET"].validated is not None
    assert scored.dimensions["LEGAL"].validated is not None


def test_matrix_pending_acceptance_is_not_confirmation(cfg):
    pending = fact(state="PENDING")
    accepted = replace(pending, accepted_risk=True)
    assert calculate_exposure_score([pending], cfg) == calculate_exposure_score([accepted], cfg)
    assert calculate_exposure_score([accepted], cfg).global_score.validated is None


def test_matrix_all_rejected_stays_null(cfg):
    dismissed = [
        fact(canonical_key=f"dismissed-{dim}", dimension=dim, state="REJECTED")
        for dim in ("SCOPE", "BUDGET", "LEGAL", "TIME", "QUALITY", "TECHNICAL")
    ]
    observed = calculate_exposure_score(dismissed, cfg)
    assert observed.validated_fact_count == 0
    assert observed.pending_fact_count == 0
    assert observed.global_score.validated is None
    assert observed.global_score.projected is None
    assert all(item.validated is None for item in observed.dimensions.values())
    assert all(item.projected is None for item in observed.dimensions.values())


@pytest.mark.parametrize("state", ("PENDING", "CONFIRMED"))
def test_matrix_duplicate_rejected_permutation_is_deterministic(cfg, state):
    current = fact(state=state, severity="MEDIUM")
    duplicate = replace(current, evidence_id="synthetic-second-source")
    dismissed = replace(current, state="REJECTED", evidence_id="synthetic-dismissal")
    expected = calculate_exposure_score([current], cfg)
    assert calculate_exposure_score([dismissed, duplicate, current], cfg) == expected
    assert calculate_exposure_score([current, duplicate, dismissed], cfg) == expected
