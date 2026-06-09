"""LEGAL dimension extraction pilot (Phase 2A.1).

Refers to Suite ID: TS-UD-EVI-LEGAL-001.

Synthetic-payload adapter and Pydantic schemas for three pilot LEGAL
claim types: payment_terms, late_fees_penalties, liability_cap.

Not wired to Celery or PDF ingestion in 2A.1 — synthetic inputs only.
See ADR-011 Phase 2A roadmap.
"""
from src.evidence.legal.adapter import (
    AdapterResult,
    LegalExtractionAdapter,
    MetricsSink,
    NullMetrics,
    OutOfScopeEvent,
    ProcessingError,
)
from src.evidence.legal.schemas import (
    LEGAL_CLAIM_SCHEMAS,
    LateFeesPenaltiesValue,
    LiabilityCapValue,
    PaymentTermsValue,
    RawExtractedClaim,
)

__all__ = [
    "LEGAL_CLAIM_SCHEMAS",
    "AdapterResult",
    "LateFeesPenaltiesValue",
    "LegalExtractionAdapter",
    "LiabilityCapValue",
    "MetricsSink",
    "NullMetrics",
    "OutOfScopeEvent",
    "PaymentTermsValue",
    "ProcessingError",
    "RawExtractedClaim",
]
