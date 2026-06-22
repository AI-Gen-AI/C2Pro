"""End-to-end fixture-based tests for the LEGAL pilot adapter.

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Exercises ``LegalExtractionAdapter`` against the synthetic EPC #001
extraction batch (Phase 2A.2).  The unit tests in ``test_adapter.py``
cover each rule in isolation; these tests verify the **realistic
mixed-batch behavior** an extractor would produce in a shadow run.

Assertions here are deterministic against
``EPC_001_EXPECTATIONS`` — if the fixture grows, update both in
lockstep.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import pytest

from src.evidence.domain.models import (
    Dimension,
    LocatorQuality,
    VerificationStatus,
)
from src.evidence.legal.adapter import LegalExtractionAdapter
from tests.modules.evidence.legal.fixtures.epc_contract_001 import (
    EPC_001_DOCUMENT_ID,
    EPC_001_EXPECTATIONS,
    build_epc_001_payloads,
)

# ---------------------------------------------------------------------------
# Recording sink (mirrors the one in test_adapter.py)
# ---------------------------------------------------------------------------


@dataclass
class _RecordingMetrics:
    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def incr(self, name: str, *, tags: dict[str, str] | None = None) -> None:
        self.calls.append((name, dict(tags or {})))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def count(self, name: str) -> int:
        return sum(1 for n, _ in self.calls if n == name)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def metrics() -> _RecordingMetrics:
    return _RecordingMetrics()


@pytest.fixture
def adapter(metrics: _RecordingMetrics) -> LegalExtractionAdapter:
    return LegalExtractionAdapter(
        document_id=EPC_001_DOCUMENT_ID, metrics=metrics
    )


@pytest.fixture
def epc_result(adapter: LegalExtractionAdapter):
    return adapter.adapt(build_epc_001_payloads())


# ---------------------------------------------------------------------------
# Channel distribution
# ---------------------------------------------------------------------------


class TestChannelDistribution:
    """The three output channels must match the fixture's documented
    expectations exactly — drift here means either the fixture changed
    or the adapter's routing did."""

    def test_payload_count_matches_fixture(self) -> None:
        assert len(build_epc_001_payloads()) == EPC_001_EXPECTATIONS["total_payloads"]

    def test_claim_channel_cardinality(self, epc_result) -> None:
        assert len(epc_result.claims) == EPC_001_EXPECTATIONS["claim_count"]

    def test_out_of_scope_channel_cardinality(self, epc_result) -> None:
        assert (
            len(epc_result.out_of_scope)
            == EPC_001_EXPECTATIONS["out_of_scope_count"]
        )

    def test_processing_error_channel_cardinality(self, epc_result) -> None:
        assert (
            len(epc_result.processing_errors)
            == EPC_001_EXPECTATIONS["processing_error_count"]
        )

    def test_channels_partition_the_input(self, epc_result) -> None:
        """Every payload must end in exactly one channel — no drops, no double-counting."""
        emitted = (
            len(epc_result.claims)
            + len(epc_result.out_of_scope)
            + len(epc_result.processing_errors)
        )
        assert emitted == EPC_001_EXPECTATIONS["total_payloads"]


# ---------------------------------------------------------------------------
# Claim-type distribution (claims channel)
# ---------------------------------------------------------------------------


class TestClaimTypeDistribution:
    def test_claim_type_histogram(self, epc_result) -> None:
        observed = Counter(c.claim_type for c in epc_result.claims)
        assert dict(observed) == EPC_001_EXPECTATIONS["claim_type_distribution"]

    def test_all_claims_are_legal_dimension(self, epc_result) -> None:
        assert all(c.dimension is Dimension.LEGAL for c in epc_result.claims)

    def test_all_claims_anchor_to_fixture_document(self, epc_result) -> None:
        assert all(
            c.text_anchor.document_id == EPC_001_DOCUMENT_ID
            for c in epc_result.claims
        )


# ---------------------------------------------------------------------------
# Out-of-scope channel detail
# ---------------------------------------------------------------------------


class TestOutOfScopeBreakdown:
    def test_out_of_scope_reason_histogram(self, epc_result) -> None:
        observed = Counter(ev.reason for ev in epc_result.out_of_scope)
        assert dict(observed) == EPC_001_EXPECTATIONS["out_of_scope_reasons"]

    def test_wrong_dimension_event_carries_real_dimension(self, epc_result) -> None:
        wrong_dim = [
            ev for ev in epc_result.out_of_scope if ev.reason == "wrong_dimension"
        ]
        assert len(wrong_dim) == 1
        assert wrong_dim[0].dimension == "TIME"
        assert wrong_dim[0].claim_type == "milestone_definition"

    def test_unknown_claim_type_event_carries_real_claim_type(
        self, epc_result
    ) -> None:
        unknown = [
            ev
            for ev in epc_result.out_of_scope
            if ev.reason == "unknown_claim_type"
        ]
        assert len(unknown) == 1
        assert unknown[0].claim_type == "force_majeure"
        assert unknown[0].dimension == "LEGAL"


# ---------------------------------------------------------------------------
# Processing-error channel detail
# ---------------------------------------------------------------------------


class TestProcessingErrorBreakdown:
    def test_processing_error_reason_histogram(self, epc_result) -> None:
        observed = Counter(err.reason for err in epc_result.processing_errors)
        assert dict(observed) == EPC_001_EXPECTATIONS["processing_error_reasons"]

    def test_hallucinated_field_surfaces_as_schema_error(
        self, epc_result
    ) -> None:
        err = epc_result.processing_errors[0]
        assert err.reason == "schema_validation_error"
        assert err.claim_type == "late_fees_penalties"
        assert err.dimension == "LEGAL"
        assert "adjustment_factor" in err.detail


# ---------------------------------------------------------------------------
# Critical invariants — these must hold for EVERY fixture run
# ---------------------------------------------------------------------------


class TestSemanticInvariants:
    """The non-negotiable rules that protect the product thesis."""

    def test_no_claim_is_fabrication_suspected(self, epc_result) -> None:
        """ADR-011 §5.4: FABRICATION_SUSPECTED is reserved for CVC veracity
        judgments. A schema/structural error must NEVER promote a claim
        to that state — doing so would poison the Golden Corpus."""
        fabricated = [
            c
            for c in epc_result.claims
            if c.verification_status is VerificationStatus.FABRICATION_SUSPECTED
        ]
        assert (
            len(fabricated)
            == EPC_001_EXPECTATIONS["fabrication_suspected_count"]
            == 0
        )

    def test_all_built_claims_are_uncertain_in_shadow(self, epc_result) -> None:
        for c in epc_result.claims:
            assert c.verification_status is VerificationStatus.UNCERTAIN
            assert c.verification_trace.get("cvc_disabled") is True
            assert c.verification_trace.get("phase") == "2A_shadow"

    def test_partial_payment_terms_keeps_silent_fields_as_none(
        self, epc_result
    ) -> None:
        """Schedule 4 only restates milestone_count. The other contractual
        fields MUST remain None — inventing currency/net_days here would
        fabricate coherence with §7."""
        partials = [
            c
            for c in epc_result.claims
            if c.claim_type == "payment_terms" and c.text_anchor.page == 72
        ]
        assert len(partials) == 1
        v = partials[0].value
        assert v["milestone_count"] == 7
        assert v["currency"] is None
        assert v["net_days"] is None
        assert v["advance_payment_pct"] is None
        assert v["retention_pct"] is None

    def test_main_payment_terms_has_all_fields_populated(self, epc_result) -> None:
        """§7 main clause should produce a fully-populated claim — proves
        the partial above is genuine signal, not an extractor failure."""
        mains = [
            c
            for c in epc_result.claims
            if c.claim_type == "payment_terms" and c.text_anchor.page == 18
        ]
        assert len(mains) == 1
        v = mains[0].value
        assert v["currency"] == "EUR"
        assert v["net_days"] == 45
        assert v["advance_payment_pct"] == 15.0
        assert v["retention_pct"] == 5.0
        assert v["milestone_count"] == 7


# ---------------------------------------------------------------------------
# Locator quality propagation
# ---------------------------------------------------------------------------


class TestLocatorQualityPropagation:
    def test_main_clauses_have_exact_locators(self, epc_result) -> None:
        exact_pages = {18, 34, 48}
        exact_claims = [
            c
            for c in epc_result.claims
            if c.text_anchor.page in exact_pages
        ]
        assert len(exact_claims) == 3
        for c in exact_claims:
            assert c.text_anchor.locator_quality is LocatorQuality.EXACT

    def test_schedule_restatement_degrades_to_approximate(
        self, epc_result
    ) -> None:
        schedule = [
            c
            for c in epc_result.claims
            if c.claim_type == "payment_terms" and c.text_anchor.page == 72
        ][0]
        assert schedule.text_anchor.locator_quality is LocatorQuality.APPROXIMATE
        assert schedule.text_anchor.char_start is None
        assert schedule.text_anchor.char_end is None


# ---------------------------------------------------------------------------
# Metrics emission shape
# ---------------------------------------------------------------------------


class TestMetricsEmission:
    """The metrics sink must see the activity in each channel — silent
    drops would defeat the visibility goal of the out-of-scope event."""

    def test_built_claims_counter_matches_channel(
        self, epc_result, metrics: _RecordingMetrics
    ) -> None:
        assert metrics.count("evidence.claims.built") == len(epc_result.claims)

    def test_out_of_scope_counter_matches_channel(
        self, epc_result, metrics: _RecordingMetrics
    ) -> None:
        assert metrics.count("evidence.claims.out_of_scope") == len(
            epc_result.out_of_scope
        )

    def test_schema_invalid_counter_matches_processing_errors(
        self, epc_result, metrics: _RecordingMetrics
    ) -> None:
        assert metrics.count("evidence.claims.schema_invalid") == len(
            epc_result.processing_errors
        )

    def test_built_metric_tags_carry_claim_type(
        self, epc_result, metrics: _RecordingMetrics
    ) -> None:
        del epc_result  # only used to trigger the run via the fixture chain
        built = [
            tags
            for name, tags in metrics.calls
            if name == "evidence.claims.built"
        ]
        observed = Counter(t.get("claim_type") for t in built)
        assert dict(observed) == EPC_001_EXPECTATIONS["claim_type_distribution"]
