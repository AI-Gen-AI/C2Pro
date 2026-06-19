"""Schema-level tests for LEGAL pilot claim types (Phase 2A.1).

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

These tests assert the *shape contract* of the boundary types — defaults
to ``None``, range enforcement, ``extra="forbid"`` and frozen behavior —
in isolation from the adapter.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.evidence.legal.schemas import (
    LEGAL_CLAIM_SCHEMAS,
    LateFeesPenaltiesValue,
    LiabilityCapValue,
    PaymentTermsValue,
    RawExtractedClaim,
)

# ---------------------------------------------------------------------------
# Defaults to None — no fabricated coherence
# ---------------------------------------------------------------------------


class TestNoneDefaults:
    """No optional contractual field may default to a non-None value.

    Inventing currency, net_days, caps, or rates when the contract is
    silent would manufacture coherence between documents that the
    product is built to detect as missing.
    """

    def test_payment_terms_all_optional_default_none(self) -> None:
        v = PaymentTermsValue()
        assert v.currency is None
        assert v.net_days is None
        assert v.advance_payment_pct is None
        assert v.retention_pct is None
        assert v.milestone_count is None

    def test_late_fees_all_optional_default_none(self) -> None:
        v = LateFeesPenaltiesValue()
        assert v.currency is None
        assert v.rate_per_day is None
        assert v.rate_pct_per_day is None
        assert v.cap_value is None
        assert v.cap_pct_of_contract is None
        assert v.basis is None

    def test_liability_cap_all_optional_default_none(self) -> None:
        v = LiabilityCapValue()
        assert v.currency is None
        assert v.cap_value is None
        assert v.cap_pct_of_contract is None
        assert v.excludes_gross_negligence is None
        assert v.basis is None


# ---------------------------------------------------------------------------
# Range enforcement
# ---------------------------------------------------------------------------


class TestRangeEnforcement:
    @pytest.mark.parametrize("net_days", [-1, 366, 9999])
    def test_payment_terms_net_days_out_of_range_rejected(self, net_days: int) -> None:
        with pytest.raises(ValidationError):
            PaymentTermsValue(net_days=net_days)

    @pytest.mark.parametrize("pct", [-0.01, 100.01, 250.0])
    def test_payment_terms_percentage_out_of_range_rejected(self, pct: float) -> None:
        with pytest.raises(ValidationError):
            PaymentTermsValue(advance_payment_pct=pct)
        with pytest.raises(ValidationError):
            PaymentTermsValue(retention_pct=pct)

    def test_late_fees_rate_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LateFeesPenaltiesValue(rate_per_day=-0.01)

    def test_late_fees_cap_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LateFeesPenaltiesValue(cap_value=-1.0)

    def test_liability_cap_value_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LiabilityCapValue(cap_value=-1.0)

    @pytest.mark.parametrize("pct", [-0.01, 100.01])
    def test_liability_cap_pct_out_of_range_rejected(self, pct: float) -> None:
        with pytest.raises(ValidationError):
            LiabilityCapValue(cap_pct_of_contract=pct)


class TestCurrencyShape:
    @pytest.mark.parametrize("bad", ["US", "USDX", "", "USDOLLARS"])
    def test_currency_length_rejected(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            PaymentTermsValue(currency=bad)

    @pytest.mark.parametrize("good", ["USD", "EUR", "SAR", "BRL"])
    def test_currency_three_letters_accepted(self, good: str) -> None:
        assert PaymentTermsValue(currency=good).currency == good


# ---------------------------------------------------------------------------
# Closed schemas + immutability
# ---------------------------------------------------------------------------


class TestClosedAndFrozen:
    def test_extra_fields_rejected_payment_terms(self) -> None:
        with pytest.raises(ValidationError):
            PaymentTermsValue.model_validate({"hallucinated_field": 1})

    def test_extra_fields_rejected_envelope(self) -> None:
        with pytest.raises(ValidationError):
            RawExtractedClaim.model_validate(
                {
                    "dimension": "LEGAL",
                    "claim_type": "payment_terms",
                    "value": {},
                    "confidence": 0.9,
                    "rogue": "x",
                }
            )

    def test_payment_terms_is_frozen(self) -> None:
        v = PaymentTermsValue(currency="USD")
        with pytest.raises(ValidationError):
            v.currency = "EUR"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Envelope contract
# ---------------------------------------------------------------------------


class TestRawExtractedClaim:
    def test_minimal_valid_envelope(self) -> None:
        env = RawExtractedClaim(
            dimension="LEGAL",
            claim_type="payment_terms",
            value={},
            confidence=0.5,
        )
        assert env.freshness == 1.0
        assert env.page is None
        assert env.quote is None

    @pytest.mark.parametrize("conf", [-0.01, 1.01, 2.0])
    def test_confidence_out_of_range_rejected(self, conf: float) -> None:
        with pytest.raises(ValidationError):
            RawExtractedClaim(
                dimension="LEGAL",
                claim_type="payment_terms",
                value={},
                confidence=conf,
            )

    @pytest.mark.parametrize("fresh", [-0.01, 1.01])
    def test_freshness_out_of_range_rejected(self, fresh: float) -> None:
        with pytest.raises(ValidationError):
            RawExtractedClaim(
                dimension="LEGAL",
                claim_type="payment_terms",
                value={},
                confidence=0.5,
                freshness=fresh,
            )


# ---------------------------------------------------------------------------
# Registry coverage
# ---------------------------------------------------------------------------


def test_registry_has_three_pilot_claim_types() -> None:
    assert set(LEGAL_CLAIM_SCHEMAS) == {
        "payment_terms",
        "late_fees_penalties",
        "liability_cap",
    }
