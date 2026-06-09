"""
Test suite for the Evidence domain contracts (Phase 1 — frozen).

Verifies immutability, serialization, and the certainty_effective
derived property matrix as specified in ADR-010 and ADR-011.

Refers to Suite ID: TS-UD-EVI-CTS-001.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from src.documents.domain.models import DocumentType
from src.evidence.domain.models import (
    Dimension,
    DocumentPresence,
    EvidenceClaim,
    EvidenceMaturityLevel,
    EvidenceMaturityReport,
    LocatorQuality,
    SourceRef,
    VerificationStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_document_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_claim_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_project_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_source_ref(sample_document_id: UUID) -> SourceRef:
    return SourceRef(
        document_id=sample_document_id,
        page=42,
        char_start=120,
        char_end=350,
        quote="The Contractor shall complete the Works within 540 calendar days...",
        locator_quality=LocatorQuality.EXACT,
    )


@pytest.fixture
def sample_evidence_claim(
    sample_claim_id: UUID, sample_source_ref: SourceRef
) -> EvidenceClaim:
    return EvidenceClaim(
        claim_id=sample_claim_id,
        dimension=Dimension.TIME,
        claim_type="milestone_definition",
        value={"milestone": "Project Completion", "deadline_days": 540},
        algorithmic_certainty=0.92,
        text_anchor=sample_source_ref,
        freshness=0.98,
        verification_status=VerificationStatus.VERIFIED,
    )


@pytest.fixture
def sample_document_presence() -> DocumentPresence:
    return DocumentPresence(
        document_type=DocumentType.CONTRACT,
        count=3,
        latest_uploaded_at=datetime(2026, 5, 20, tzinfo=UTC),
    )


@pytest.fixture
def sample_eml_report(
    sample_project_id: UUID, sample_document_presence: DocumentPresence
) -> EvidenceMaturityReport:
    return EvidenceMaturityReport(
        project_id=sample_project_id,
        evidence_maturity_level=EvidenceMaturityLevel.EML_3,
        level_name="Schedule-aware",
        ladder_version="epc_v1.0",
        cross_validation_capability=0.42,
        present_types=[sample_document_presence],
        missing_for_next_level=[DocumentType.BUDGET],
        next_level_unlocks=["Cost coherence analysis"],
        computed_at=datetime(2026, 5, 29, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Immutability tests
# ---------------------------------------------------------------------------


class TestImmutability:
    """All four frozen dataclasses must reject mutation with FrozenInstanceError."""

    def test_evidence_claim_is_frozen(self, sample_evidence_claim: EvidenceClaim) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_evidence_claim.algorithmic_certainty = 0.5  # type: ignore[misc]

    def test_evidence_maturity_report_is_frozen(
        self, sample_eml_report: EvidenceMaturityReport
    ) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_eml_report.evidence_maturity_level = (  # type: ignore[misc]
                EvidenceMaturityLevel.EML_5
            )

    def test_source_ref_is_frozen(self, sample_source_ref: SourceRef) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_source_ref.page = 99  # type: ignore[misc]

    def test_document_presence_is_frozen(
        self, sample_document_presence: DocumentPresence
    ) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            sample_document_presence.count = 10  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Serialization tests
# ---------------------------------------------------------------------------


class TestSerialization:
    """All domain contracts must be trivially serializable via dataclasses.asdict()."""

    def test_evidence_claim_asdict(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        d = dataclasses.asdict(sample_evidence_claim)
        assert isinstance(d, dict)
        assert d["claim_id"] == sample_evidence_claim.claim_id
        assert d["dimension"] == "TIME"
        assert d["verification_status"] == "verified"
        assert d["text_anchor"]["locator_quality"] == "exact"

    def test_evidence_maturity_report_asdict(
        self, sample_eml_report: EvidenceMaturityReport
    ) -> None:
        d = dataclasses.asdict(sample_eml_report)
        assert isinstance(d, dict)
        assert d["evidence_maturity_level"] == 3
        assert d["cross_validation_capability"] == 0.42
        assert len(d["present_types"]) == 1

    def test_source_ref_asdict(self, sample_source_ref: SourceRef) -> None:
        d = dataclasses.asdict(sample_source_ref)
        assert d["document_id"] == sample_source_ref.document_id
        assert d["page"] == 42
        assert d["locator_quality"] == "exact"

    def test_asdict_json_roundtrip(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        d = dataclasses.asdict(sample_evidence_claim)
        json_str = json.dumps(d, default=str)
        assert isinstance(json_str, str)
        reloaded = json.loads(json_str)
        assert reloaded["algorithmic_certainty"] == 0.92
        assert reloaded["human_verified"] is False
        assert reloaded["human_certainty"] is None


# ---------------------------------------------------------------------------
# certainty_effective matrix (ADR-011 §5.4)
# ---------------------------------------------------------------------------


class TestCertaintyEffective:
    """Verify the single-modifier certainty_effective derived property.

    ADR-011 §5.4 (design correction): locator_quality is NOT a second
    multiplier — it is already reflected in verification_status.
    """

    def test_verified_full_certainty(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=0.80,
            verification_status=VerificationStatus.VERIFIED,
        )
        assert claim.certainty_effective == 0.80

    def test_uncertain_reduced_certainty(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=0.80,
            verification_status=VerificationStatus.UNCERTAIN,
        )
        assert claim.certainty_effective == 0.48

    def test_unsupported_low_certainty(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=0.80,
            verification_status=VerificationStatus.UNSUPPORTED,
        )
        assert claim.certainty_effective == pytest.approx(0.16)

    def test_fabrication_suspected_zero(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=0.80,
            verification_status=VerificationStatus.FABRICATION_SUSPECTED,
        )
        assert claim.certainty_effective == 0.0

    def test_verification_deferred_uses_uncertain(
        self, sample_evidence_claim: EvidenceClaim
    ) -> None:
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=0.75,
            verification_status=VerificationStatus.UNCERTAIN,
            verification_trace={"reason": "verification_deferred"},
        )
        assert claim.certainty_effective == pytest.approx(0.45)
        assert claim.verification_trace["reason"] == "verification_deferred"

    def test_certainty_effective_ignores_locator_quality(
        self, sample_claim_id: UUID, sample_document_id: UUID
    ) -> None:
        ref_exact = SourceRef(
            document_id=sample_document_id,
            page=1,
            char_start=0,
            char_end=10,
            quote="text",
            locator_quality=LocatorQuality.EXACT,
        )
        ref_missing = SourceRef(
            document_id=sample_document_id,
            page=None,
            char_start=None,
            char_end=None,
            quote=None,
            locator_quality=LocatorQuality.MISSING,
        )

        claim_exact = EvidenceClaim(
            claim_id=sample_claim_id,
            dimension=Dimension.SCOPE,
            claim_type="test",
            value={},
            algorithmic_certainty=0.70,
            text_anchor=ref_exact,
            freshness=1.0,
            verification_status=VerificationStatus.UNCERTAIN,
        )
        claim_missing = EvidenceClaim(
            claim_id=uuid4(),
            dimension=Dimension.SCOPE,
            claim_type="test",
            value={},
            algorithmic_certainty=0.70,
            text_anchor=ref_missing,
            freshness=1.0,
            verification_status=VerificationStatus.UNCERTAIN,
        )

        assert claim_exact.certainty_effective == claim_missing.certainty_effective == 0.42

    @pytest.mark.parametrize(
        ("status", "modifier"),
        [
            (VerificationStatus.VERIFIED, 1.0),
            (VerificationStatus.UNCERTAIN, 0.6),
            (VerificationStatus.UNSUPPORTED, 0.2),
            (VerificationStatus.FABRICATION_SUSPECTED, 0.0),
        ],
    )
    def test_certainty_modifier_matrix(
        self,
        sample_evidence_claim: EvidenceClaim,
        status: VerificationStatus,
        modifier: float,
    ) -> None:
        algo = 0.55
        claim = dataclasses.replace(
            sample_evidence_claim,
            algorithmic_certainty=algo,
            verification_status=status,
        )
        expected = algo * modifier
        assert claim.certainty_effective == pytest.approx(expected)

    def test_fabrication_zero_regardless_of_algo(self) -> None:
        ref = SourceRef(
            document_id=uuid4(),
            page=1,
            char_start=0,
            char_end=5,
            quote="x",
            locator_quality=LocatorQuality.EXACT,
        )
        claim = EvidenceClaim(
            claim_id=uuid4(),
            dimension=Dimension.LEGAL,
            claim_type="test",
            value={},
            algorithmic_certainty=1.0,
            text_anchor=ref,
            freshness=1.0,
            verification_status=VerificationStatus.FABRICATION_SUSPECTED,
        )
        assert claim.certainty_effective == 0.0

    def test_default_status_is_uncertain(self) -> None:
        ref = SourceRef(
            document_id=uuid4(),
            page=1,
            char_start=0,
            char_end=5,
            quote="x",
            locator_quality=LocatorQuality.EXACT,
        )
        claim = EvidenceClaim(
            claim_id=uuid4(),
            dimension=Dimension.QUALITY,
            claim_type="test",
            value={},
            algorithmic_certainty=0.50,
            text_anchor=ref,
            freshness=1.0,
        )
        assert claim.verification_status == VerificationStatus.UNCERTAIN
        assert claim.certainty_effective == 0.30


# ---------------------------------------------------------------------------
# Enum exhaustiveness
# ---------------------------------------------------------------------------


class TestEnumExhaustiveness:
    """All enums must have the exact cardinality specified in the ADRs."""

    def test_dimension_has_six_values(self) -> None:
        assert len(Dimension) == 6

    def test_locator_quality_has_three_values(self) -> None:
        assert len(LocatorQuality) == 3

    def test_verification_status_has_four_values(self) -> None:
        assert len(VerificationStatus) == 4

    def test_eml_has_six_levels(self) -> None:
        assert len(EvidenceMaturityLevel) == 6
        assert EvidenceMaturityLevel.EML_0.value == 0
        assert EvidenceMaturityLevel.EML_5.value == 5


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestDefaults:
    """ADR-012 extension hooks must default to inert values."""

    def test_evidence_claim_human_fields_default(
        self, sample_claim_id: UUID, sample_document_id: UUID
    ) -> None:
        ref = SourceRef(
            document_id=sample_document_id,
            page=1,
            char_start=0,
            char_end=5,
            quote="x",
            locator_quality=LocatorQuality.EXACT,
        )
        claim = EvidenceClaim(
            claim_id=sample_claim_id,
            dimension=Dimension.LEGAL,
            claim_type="test",
            value={},
            algorithmic_certainty=0.90,
            text_anchor=ref,
            freshness=1.0,
        )
        assert claim.human_verified is False
        assert claim.human_certainty is None
        assert claim.review_status is None
        assert claim.reviewer_id is None
        assert claim.verification_trace == {}
