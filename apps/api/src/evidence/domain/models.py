"""
Evidence domain models — Phase 1 frozen contracts.

Implements ADR-010 (Evidence Maturity Layer) and ADR-011 (Evidence Intelligence Layer).
These types are upstream of the Coherence Engine and are consumed by ingestion,
extraction, and coherence modules.

Refers to Suite ID: TS-UD-EVI-CLM-001.
Refers to Suite ID: TS-UD-EVI-EML-001.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from src.documents.domain.models import DocumentType

# ---------------------------------------------------------------------------
# ADR-011: Core enums (Evidence Intelligence Layer)
# ---------------------------------------------------------------------------


class Dimension(str, Enum):
    """Canonical six-dimension taxonomy for EPC contract analysis.

    Matches CoherenceCategory semantically but is decoupled to preserve
    domain purity — mapping happens at the adapter/boundary layer.
    """

    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    TIME = "TIME"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    QUALITY = "QUALITY"


class LocatorQuality(str, Enum):
    """Quality of the text anchor localization within the source document.

    ADR-011 §4.2: Not all extractors return exact spans. EXACT requires
    page + offsets + quote; APPROXIMATE means page/paragraph level without
    precise coordinates; MISSING means no recoverable physical location.
    """

    EXACT = "exact"
    APPROXIMATE = "approximate"
    MISSING = "missing"


class VerificationStatus(str, Enum):
    """Post-CVC verification state for an evidence claim.

    ADR-011 §5.4: Only four states. UNCERTAIN covers both intermediate
    similarity and infrastructure timeouts (verification_deferred).
    FABRICATION_SUSPECTED is the only state that forces certainty to 0.0.
    """

    VERIFIED = "verified"
    UNCERTAIN = "uncertain"
    UNSUPPORTED = "unsupported"
    FABRICATION_SUSPECTED = "fabrication_suspected"


# ---------------------------------------------------------------------------
# ADR-010: Evidence Maturity Layer (EML)
# ---------------------------------------------------------------------------


class EvidenceMaturityLevel(int, Enum):
    """Normalized invariant scale (0–5) of document ecosystem maturity.

    The number is comparable across all industries. The COMPOSITION of each
    level (which document types satisfy it) lives in the IndustryProfile's
    eml_ladder, not in this enum. Industries with more natural stages are
    normalized to this 0–5 axis.

    ADR-010 §3.2: scale is invariant; composition is per-profile.
    """

    EML_0 = 0
    EML_1 = 1
    EML_2 = 2
    EML_3 = 3
    EML_4 = 4
    EML_5 = 5


@dataclass(frozen=True)
class DocumentPresence:
    """Which document types exist in the project and how many.

    ADR-010 §4: Observes type presence, not content quality.
    Document quality degradation is handled by ADR-011 evidence extraction.
    """

    document_type: DocumentType
    count: int
    latest_uploaded_at: datetime | None


@dataclass(frozen=True)
class EvidenceMaturityReport:
    """Snapshot of a project's document ecosystem maturity.

    EML high ≠ project good. Maturity measures documentation completeness,
    not coherence or health. ADR-010 §3.2.

    cross_validation_capability is the proportion of possible document
    crosses enabled by the present types — distinct from evidence_coverage
    (ADR-011) which measures claims within a dimension.
    """

    project_id: UUID
    evidence_maturity_level: EvidenceMaturityLevel
    level_name: str
    ladder_version: str
    cross_validation_capability: float
    present_types: list[DocumentPresence]
    missing_for_next_level: list[DocumentType]
    next_level_unlocks: list[str]
    computed_at: datetime


# ---------------------------------------------------------------------------
# ADR-011: Evidence Intelligence Layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceRef:
    """Strict traceability anchor adapted to real OCR constraints.

    ADR-011 §4.2: locator_quality is INPUT to verification state
    transitions (§5.4), NOT a parallel penalty multiplier on
    certainty_effective. A claim with locator=MISSING but valid
    structured value degrades to UNCERTAIN, not UNSUPPORTED.
    """

    document_id: UUID
    page: int | None
    char_start: int | None
    char_end: int | None
    quote: str | None
    locator_quality: LocatorQuality


@dataclass(frozen=True)
class EvidenceClaim:
    """Immutable, verified, traceable evidence claim — upstream of FindingSignal.

    Pipeline (ADR-011 §2):
        Document → Extractor → EvidenceClaim → RuleEvaluator → FindingSignal

    EvidenceClaim = "what does the document say, with what certainty, and where?"
    (the fact). FindingSignal = "what problem does a rule detect?" (the judgment).
    """

    claim_id: UUID
    dimension: Dimension
    claim_type: str
    value: dict[str, Any]

    # Technical axis (inputs to TRI and Coverage)
    algorithmic_certainty: float
    text_anchor: SourceRef
    freshness: float

    # CVC result (ADR-011 §5)
    verification_status: VerificationStatus = VerificationStatus.UNCERTAIN
    verification_trace: dict[str, Any] = field(default_factory=dict)

    # ADR-012 extension hooks (inert in Phase 1)
    human_verified: bool = False
    human_certainty: float | None = None
    review_status: str | None = None
    reviewer_id: UUID | None = None

    @property
    def certainty_effective(self) -> float:
        """Derived effective certainty — single modifier, not persisted.

        ADR-011 §5.4 (design correction): locator_quality is already reflected
        in verification_status, so NO second multiplier is applied here.
        Multiplying status_modifier × locator_modifier would double-count
        the same defect.

        Modifiers:
            VERIFIED            → ×1.0
            UNCERTAIN           → ×0.6
            UNSUPPORTED         → ×0.2
            FABRICATION_SUSPECTED → 0.0 (always, regardless of input)
        """
        _STATUS_MODIFIER: dict[VerificationStatus, float] = {
            VerificationStatus.VERIFIED: 1.0,
            VerificationStatus.UNCERTAIN: 0.6,
            VerificationStatus.UNSUPPORTED: 0.2,
            VerificationStatus.FABRICATION_SUSPECTED: 0.0,
        }
        return self.algorithmic_certainty * _STATUS_MODIFIER[self.verification_status]
