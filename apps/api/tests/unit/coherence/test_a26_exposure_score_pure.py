"""A26 pure Score synthetic checks: no database, LLM or document payloads."""

from dataclasses import replace

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
    assert one == two and two.validated_fact_count == 1


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
