"""Adapter-level tests for LegalExtractionAdapter (Phase 2A.1).

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Covers the three output channels (claims / processing_errors /
out_of_scope), the absence of FABRICATION_SUSPECTED for structural
errors, locator-quality derivation, and the metrics contract.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest

from src.evidence.domain.models import (
    Dimension,
    LocatorQuality,
    VerificationStatus,
)
from src.evidence.legal.adapter import (
    LegalExtractionAdapter,
    MetricsSink,
    OutOfScopeEvent,
    ProcessingError,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _RecordingMetrics:
    """In-memory MetricsSink for assertions."""

    calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def incr(self, name: str, *, tags: dict[str, str] | None = None) -> None:
        self.calls.append((name, dict(tags or {})))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


@pytest.fixture
def document_id() -> UUID:
    return uuid4()


@pytest.fixture
def metrics() -> _RecordingMetrics:
    return _RecordingMetrics()


@pytest.fixture
def adapter(
    document_id: UUID, metrics: _RecordingMetrics
) -> LegalExtractionAdapter:
    return LegalExtractionAdapter(document_id=document_id, metrics=metrics)


def _valid_payment_terms_payload(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "dimension": "LEGAL",
        "claim_type": "payment_terms",
        "value": {
            "currency": "EUR",
            "net_days": 45,
            "advance_payment_pct": 10.0,
            "retention_pct": 5.0,
        },
        "confidence": 0.84,
        "freshness": 0.95,
        "page": 12,
        "char_start": 100,
        "char_end": 280,
        "quote": "Payment shall be made within forty-five (45) days of invoice...",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    def test_single_payment_terms_claim_built(
        self,
        adapter: LegalExtractionAdapter,
        document_id: UUID,
    ) -> None:
        result = adapter.adapt([_valid_payment_terms_payload()])

        assert len(result.claims) == 1
        assert result.processing_errors == ()
        assert result.out_of_scope == ()

        claim = result.claims[0]
        assert claim.dimension is Dimension.LEGAL
        assert claim.claim_type == "payment_terms"
        assert claim.algorithmic_certainty == pytest.approx(0.84)
        assert claim.freshness == pytest.approx(0.95)
        assert claim.text_anchor.document_id == document_id
        assert claim.text_anchor.locator_quality is LocatorQuality.EXACT
        assert claim.value["currency"] == "EUR"
        assert claim.value["net_days"] == 45

    def test_three_pilot_claim_types_all_pass(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payloads = [
            _valid_payment_terms_payload(),
            {
                "dimension": "LEGAL",
                "claim_type": "late_fees_penalties",
                "value": {
                    "currency": "USD",
                    "rate_pct_per_day": 0.1,
                    "cap_pct_of_contract": 10.0,
                    "basis": "monthly_invoice",
                },
                "confidence": 0.71,
            },
            {
                "dimension": "LEGAL",
                "claim_type": "liability_cap",
                "value": {
                    "currency": "USD",
                    "cap_pct_of_contract": 100.0,
                    "excludes_gross_negligence": True,
                    "basis": "contract_value",
                },
                "confidence": 0.88,
            },
        ]
        result = adapter.adapt(payloads)
        assert len(result.claims) == 3
        assert {c.claim_type for c in result.claims} == {
            "payment_terms",
            "late_fees_penalties",
            "liability_cap",
        }


class TestShadowModeStatus:
    """Phase 2A.1 runs CVC OFF — every built claim is UNCERTAIN."""

    def test_built_claim_is_uncertain_in_shadow(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        result = adapter.adapt([_valid_payment_terms_payload()])
        claim = result.claims[0]
        assert claim.verification_status is VerificationStatus.UNCERTAIN
        assert claim.verification_trace["phase"] == "2A_shadow"
        assert claim.verification_trace["cvc_disabled"] is True

    def test_certainty_effective_applies_uncertain_modifier(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        result = adapter.adapt([_valid_payment_terms_payload(confidence=0.80)])
        # UNCERTAIN modifier is 0.6 → 0.80 * 0.6 = 0.48
        assert result.claims[0].certainty_effective == pytest.approx(0.48)


# ---------------------------------------------------------------------------
# Schema-invalid value → processing_error, NOT a claim, NOT fabrication
# ---------------------------------------------------------------------------


class TestSchemaInvalid:
    """A Pydantic value-validation failure must surface as a
    ``schema_validation_error`` ProcessingError. It must NOT become an
    EvidenceClaim and must NEVER be tagged FABRICATION_SUSPECTED."""

    def test_negative_rate_per_day_emits_processing_error(
        self,
        adapter: LegalExtractionAdapter,
        metrics: _RecordingMetrics,
    ) -> None:
        payload = {
            "dimension": "LEGAL",
            "claim_type": "late_fees_penalties",
            "value": {"rate_per_day": -5.0},
            "confidence": 0.9,
        }
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert len(result.processing_errors) == 1
        err = result.processing_errors[0]
        assert err.reason == "schema_validation_error"
        assert err.claim_type == "late_fees_penalties"
        assert err.dimension == "LEGAL"
        assert "rate_per_day" in err.detail
        assert "evidence.claims.schema_invalid" in metrics.names()

    def test_percentage_out_of_range_emits_processing_error(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["value"] = {"advance_payment_pct": 250.0}
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert len(result.processing_errors) == 1
        assert result.processing_errors[0].reason == "schema_validation_error"

    def test_extra_field_in_value_rejected(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["value"] = {"currency": "USD", "hallucinated_field": "x"}
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert len(result.processing_errors) == 1
        assert result.processing_errors[0].reason == "schema_validation_error"

    def test_no_claim_ever_carries_fabrication_suspected(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        """Structural errors must not promote claims to fabrication_suspected.

        This guards the ADR-011 §5.4 semantic boundary:
        FABRICATION_SUSPECTED is reserved for CVC veracity judgments.
        """
        payloads = [
            _valid_payment_terms_payload(),
            {  # invalid envelope
                "dimension": "LEGAL",
                "claim_type": "payment_terms",
                "value": {},
                "confidence": 2.0,
            },
            {  # invalid value
                "dimension": "LEGAL",
                "claim_type": "liability_cap",
                "value": {"cap_value": -1.0},
                "confidence": 0.7,
            },
        ]
        result = adapter.adapt(payloads)
        for claim in result.claims:
            assert claim.verification_status is not VerificationStatus.FABRICATION_SUSPECTED


# ---------------------------------------------------------------------------
# No fabricated defaults
# ---------------------------------------------------------------------------


class TestNoFabricatedDefaults:
    """An empty or partial value must propagate ``None`` — never invent
    currency, net_days, caps or rates."""

    def test_empty_value_produces_claim_with_all_none(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["value"] = {}
        result = adapter.adapt([payload])
        assert len(result.claims) == 1
        v = result.claims[0].value
        assert v["currency"] is None
        assert v["net_days"] is None
        assert v["advance_payment_pct"] is None
        assert v["retention_pct"] is None
        assert v["milestone_count"] is None

    def test_partial_value_keeps_missing_as_none(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["value"] = {"net_days": 60}
        result = adapter.adapt([payload])
        v = result.claims[0].value
        assert v["net_days"] == 60
        assert v["currency"] is None
        assert v["advance_payment_pct"] is None


# ---------------------------------------------------------------------------
# Out-of-scope filtering — visible, never silent
# ---------------------------------------------------------------------------


class TestOutOfScope:
    def test_wrong_dimension_emits_event_and_metric(
        self,
        adapter: LegalExtractionAdapter,
        metrics: _RecordingMetrics,
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["dimension"] = "BUDGET"
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert result.processing_errors == ()
        assert len(result.out_of_scope) == 1
        event = result.out_of_scope[0]
        assert event.reason == "wrong_dimension"
        assert event.dimension == "BUDGET"
        out_of_scope_calls = [
            (n, t) for n, t in metrics.calls if n == "evidence.claims.out_of_scope"
        ]
        assert len(out_of_scope_calls) == 1
        assert out_of_scope_calls[0][1]["reason"] == "wrong_dimension"

    def test_unknown_claim_type_emits_event_and_metric(
        self,
        adapter: LegalExtractionAdapter,
        metrics: _RecordingMetrics,
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["claim_type"] = "force_majeure"
        payload["value"] = {}
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert len(result.out_of_scope) == 1
        event = result.out_of_scope[0]
        assert event.reason == "unknown_claim_type"
        assert event.claim_type == "force_majeure"
        assert any(
            n == "evidence.claims.out_of_scope"
            and t.get("reason") == "unknown_claim_type"
            for n, t in metrics.calls
        )


# ---------------------------------------------------------------------------
# Invalid envelope
# ---------------------------------------------------------------------------


class TestInvalidEnvelope:
    def test_missing_required_field_emits_invalid_envelope(
        self,
        adapter: LegalExtractionAdapter,
        metrics: _RecordingMetrics,
    ) -> None:
        payload = {
            "dimension": "LEGAL",
            "claim_type": "payment_terms",
            # missing "value" and "confidence"
        }
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert len(result.processing_errors) == 1
        err = result.processing_errors[0]
        assert err.reason == "invalid_envelope"
        assert err.claim_type == "payment_terms"
        assert "evidence.claims.invalid_envelope" in metrics.names()

    def test_confidence_out_of_range_is_invalid_envelope(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload()
        payload["confidence"] = 1.5
        result = adapter.adapt([payload])
        assert result.claims == ()
        assert result.processing_errors[0].reason == "invalid_envelope"

    def test_non_dict_payload_emits_invalid_envelope(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        result = adapter.adapt(["not-a-dict"])  # type: ignore[list-item]
        assert result.claims == ()
        assert len(result.processing_errors) == 1
        assert result.processing_errors[0].reason == "invalid_envelope"
        assert result.processing_errors[0].claim_type == "<unknown>"


# ---------------------------------------------------------------------------
# Locator quality derivation
# ---------------------------------------------------------------------------


class TestLocatorQualityDerivation:
    def test_full_offsets_and_quote_give_exact(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        result = adapter.adapt([_valid_payment_terms_payload()])
        assert result.claims[0].text_anchor.locator_quality is LocatorQuality.EXACT

    def test_only_page_gives_approximate(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload(
            char_start=None, char_end=None, quote=None
        )
        result = adapter.adapt([payload])
        assert (
            result.claims[0].text_anchor.locator_quality is LocatorQuality.APPROXIMATE
        )

    def test_only_quote_gives_approximate(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload(
            page=None, char_start=None, char_end=None
        )
        result = adapter.adapt([payload])
        assert (
            result.claims[0].text_anchor.locator_quality is LocatorQuality.APPROXIMATE
        )

    def test_no_locator_info_gives_missing(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payload = _valid_payment_terms_payload(
            page=None, char_start=None, char_end=None, quote=None
        )
        result = adapter.adapt([payload])
        assert result.claims[0].text_anchor.locator_quality is LocatorQuality.MISSING


# ---------------------------------------------------------------------------
# Mixed batch
# ---------------------------------------------------------------------------


class TestMixedBatch:
    def test_three_channels_populated_independently(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        payloads = [
            _valid_payment_terms_payload(),  # → claim
            {  # → invalid_envelope (confidence missing)
                "dimension": "LEGAL",
                "claim_type": "payment_terms",
                "value": {},
            },
            {  # → schema_validation_error
                "dimension": "LEGAL",
                "claim_type": "liability_cap",
                "value": {"cap_pct_of_contract": -10.0},
                "confidence": 0.6,
            },
            {  # → out_of_scope (dimension)
                "dimension": "TIME",
                "claim_type": "payment_terms",
                "value": {},
                "confidence": 0.5,
            },
            {  # → out_of_scope (claim_type)
                "dimension": "LEGAL",
                "claim_type": "force_majeure",
                "value": {},
                "confidence": 0.5,
            },
        ]
        result = adapter.adapt(payloads)
        assert len(result.claims) == 1
        assert len(result.processing_errors) == 2
        assert len(result.out_of_scope) == 2
        reasons = {e.reason for e in result.processing_errors}
        assert reasons == {"invalid_envelope", "schema_validation_error"}


# ---------------------------------------------------------------------------
# Sink port + null sink
# ---------------------------------------------------------------------------


class TestMetricsSinkPort:
    def test_null_sink_is_default(self, document_id: UUID) -> None:
        # Construct without sink → NullMetrics is used; should not raise.
        adapter = LegalExtractionAdapter(document_id=document_id)
        result = adapter.adapt([_valid_payment_terms_payload()])
        assert len(result.claims) == 1

    def test_metrics_sink_protocol_accepts_minimal_impl(
        self, document_id: UUID
    ) -> None:
        class Counter:
            def __init__(self) -> None:
                self.total = 0

            def incr(
                self, name: str, *, tags: dict[str, str] | None = None
            ) -> None:
                self.total += 1

        counter: MetricsSink = Counter()  # structural check
        adapter = LegalExtractionAdapter(document_id=document_id, metrics=counter)
        adapter.adapt([_valid_payment_terms_payload()])
        assert isinstance(counter, Counter) and counter.total >= 1


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class TestResultTypes:
    def test_processing_error_is_frozen(self) -> None:
        err = ProcessingError(
            reason="schema_validation_error",
            claim_type="payment_terms",
            dimension="LEGAL",
            detail="x",
            raw_payload_preview="y",
            document_id=uuid4(),
        )
        with pytest.raises(Exception):
            err.reason = "other"  # type: ignore[misc]

    def test_out_of_scope_event_is_frozen(self) -> None:
        ev = OutOfScopeEvent(
            reason="wrong_dimension", claim_type="x", dimension="BUDGET", document_id=uuid4()
        )
        with pytest.raises(Exception):
            ev.reason = "other"  # type: ignore[misc]

    def test_adapter_result_channels_are_tuples(
        self, adapter: LegalExtractionAdapter
    ) -> None:
        result = adapter.adapt([])
        assert isinstance(result.claims, tuple)
        assert isinstance(result.processing_errors, tuple)
        assert isinstance(result.out_of_scope, tuple)
