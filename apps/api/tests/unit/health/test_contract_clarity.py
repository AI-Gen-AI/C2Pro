"""TS-UT-HEALTH-022 - Contract clarity findings (ADR-022 / V3-P1-SCOPE-11).

Covers the hard constraint from ADR-022: contract_clarity_findings is a
findings-only projection — severity + evidence, no score/confidence/weight,
and it must never move HealthVector.composite_score.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.coherence.models import FindingSignal
from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier
from src.health.application.contract_clarity_findings import (
    extract_contract_clarity_findings,
)
from src.health.application.health_engine import assemble_health_vector
from src.health.domain.contract_clarity import (
    CONTRACT_CLARITY_RULE_IDS,
    ContractClarityFinding,
)
from src.health.domain.health_vector import (
    HealthBand,
    HealthDimension,
    HealthSignal,
)


def _finding_signal(
    *,
    rule_id: str,
    clause_id: str = "clause-1",
    severity: str = "high",
    evidence_summary: str = "Vague scope language detected",
    quote: str = "as necessary",
) -> FindingSignal:
    return FindingSignal(
        rule_id=rule_id,
        clause_id=clause_id,
        source="llm",
        impact_score=0.7,
        confidence=0.7,
        severity=severity,  # type: ignore[arg-type]
        category="SCOPE",
        evidence_summary=evidence_summary,
        quote=quote,
    )


def _evidence(ref_id: str) -> EvidenceRef:
    return EvidenceRef(
        ref_id=ref_id,
        source="health_test",
        tier=EvidenceTier.VERIFIED,
        locator=ref_id,
    )


def _scored_signal(dimension: HealthDimension, score: float, confidence: float, ref_id: str) -> HealthSignal:
    return HealthSignal(
        dimension=dimension,
        score=score,
        band=HealthBand.HEALTHY if score >= 80 else HealthBand.WATCH,
        confidence=confidence,
        evidence=[_evidence(ref_id)],
    )


class TestContractClarityRuleIds:
    def test_expected_five_rules_in_scope(self) -> None:
        assert {
            "R-SCOPE-CLARITY-01",
            "R-PAYMENT-CLARITY-01",
            "R-SCHEDULE-CLARITY-01",
            "R-TECHNICAL-SPEC-CLARITY-01",
            "R-RESPONSIBILITY-01",
        } == CONTRACT_CLARITY_RULE_IDS

    def test_quality_standards_rule_excluded(self) -> None:
        """R-QUALITY-STANDARDS-01 is not a clause-clarity rule (ADR-022)."""
        assert "R-QUALITY-STANDARDS-01" not in CONTRACT_CLARITY_RULE_IDS


class TestContractClarityFindingContract:
    def test_severity_only_no_score_field(self) -> None:
        finding = ContractClarityFinding(
            rule_id="R-SCOPE-CLARITY-01",
            clause_id="clause-1",
            severity="high",
            summary="Vague scope language",
        )
        field_names = set(ContractClarityFinding.model_fields)
        assert "score" not in field_names
        assert "confidence" not in field_names
        assert "weight" not in field_names
        assert "impact_score" not in field_names
        assert finding.severity == "high"

    def test_frozen_and_extra_forbidden(self) -> None:
        finding = ContractClarityFinding(
            rule_id="R-SCOPE-CLARITY-01",
            clause_id="clause-1",
            severity="high",
            summary="Vague scope language",
        )
        with pytest.raises(ValidationError):
            finding.severity = "low"  # type: ignore[misc]

        with pytest.raises(ValidationError):
            ContractClarityFinding(
                rule_id="R-SCOPE-CLARITY-01",
                clause_id="clause-1",
                severity="high",
                summary="Vague scope language",
                unexpected=True,
            )

    def test_quote_defaults_to_none(self) -> None:
        finding = ContractClarityFinding(
            rule_id="R-SCOPE-CLARITY-01",
            clause_id="clause-1",
            severity="high",
            summary="Vague scope language",
        )
        assert finding.quote is None


class TestExtractContractClarityFindings:
    def test_filters_to_clarity_rules_only(self) -> None:
        signals = [
            _finding_signal(rule_id="R-SCOPE-CLARITY-01"),
            _finding_signal(rule_id="R-RESPONSIBILITY-01"),
            _finding_signal(rule_id="R-QUALITY-STANDARDS-01"),  # not clause-clarity
            _finding_signal(rule_id="DET-BUD-OVERRUN"),  # unrelated deterministic rule
        ]

        findings = extract_contract_clarity_findings(signals)

        assert {f.rule_id for f in findings} == {
            "R-SCOPE-CLARITY-01",
            "R-RESPONSIBILITY-01",
        }

    def test_maps_fields_correctly(self) -> None:
        signal = _finding_signal(
            rule_id="R-PAYMENT-CLARITY-01",
            clause_id="clause-7.2",
            severity="critical",
            evidence_summary="Payment terms use undefined 'reasonable time'",
            quote="within a reasonable time",
        )

        [finding] = extract_contract_clarity_findings([signal])

        assert finding.rule_id == "R-PAYMENT-CLARITY-01"
        assert finding.clause_id == "clause-7.2"
        assert finding.severity == "critical"
        assert finding.summary == "Payment terms use undefined 'reasonable time'"
        assert finding.quote == "within a reasonable time"

    def test_empty_quote_becomes_none(self) -> None:
        signal = _finding_signal(rule_id="R-SCOPE-CLARITY-01", quote="")
        [finding] = extract_contract_clarity_findings([signal])
        assert finding.quote is None

    def test_empty_input_returns_empty_list(self) -> None:
        assert extract_contract_clarity_findings([]) == []

    def test_no_matching_rules_returns_empty_list(self) -> None:
        signals = [_finding_signal(rule_id="DET-BUD-OVERRUN")]
        assert extract_contract_clarity_findings(signals) == []


class TestFindingsOnlyHardConstraint:
    """ADR-022 hard constraint: findings never move the composite score."""

    def test_findings_do_not_change_composite_score(self) -> None:
        project_id, tenant_id = uuid4(), uuid4()
        signals = [_scored_signal(HealthDimension.CONTRACT, 80, 0.75, "contract")]
        findings = [
            ContractClarityFinding(
                rule_id="R-SCOPE-CLARITY-01",
                clause_id="clause-1",
                severity="critical",
                summary="Vague scope language",
            )
        ]

        without_findings = assemble_health_vector(
            project_id, tenant_id, signals=signals, prior_composite=None,
        )
        with_findings = assemble_health_vector(
            project_id,
            tenant_id,
            signals=signals,
            prior_composite=None,
            contract_clarity_findings=findings,
        )

        assert without_findings.composite_score == with_findings.composite_score
        assert without_findings.composite_band == with_findings.composite_band
        assert without_findings.dimensions == with_findings.dimensions
        assert without_findings.contract_clarity_findings == []
        assert with_findings.contract_clarity_findings == findings

    def test_default_is_empty_list(self) -> None:
        vector = assemble_health_vector(
            uuid4(), uuid4(), signals=[], prior_composite=None,
        )
        assert vector.contract_clarity_findings == []

    def test_no_health_dimension_named_contract_clarity(self) -> None:
        """There is no scored HealthDimension for clause clarity in v0."""
        assert not any(
            member.value == "contract_clarity" for member in HealthDimension
        )
