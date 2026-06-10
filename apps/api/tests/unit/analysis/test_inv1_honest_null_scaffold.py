"""TS-ADR-013-GRAPH-001 - INV-1 evidence and honest-null scaffold."""

from __future__ import annotations


def test_evidence_ref_tier_enum_allows_inv1_classification() -> None:
    """TS-ADR-013-GRAPH-001 - Evidence references carry verified/weak/inferred/unverified tiers."""
    from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier

    ref = EvidenceRef(
        ref_id="clause-1",
        source="document",
        tier=EvidenceTier.VERIFIED,
        locator="p.1",
    )

    assert ref.tier is EvidenceTier.VERIFIED
    assert {tier.value for tier in EvidenceTier} == {
        "verified",
        "weak",
        "inferred",
        "unverified",
    }


def test_honest_null_helper_returns_none_with_reason_and_evidence_refs() -> None:
    """TS-ADR-013-GRAPH-001 - Missing evidence returns null plus reason, never fabricated 0/100."""
    from src.analysis.domain.honest_null import honest_null
    from src.evidence.domain.runtime_trust import EvidenceRef, EvidenceTier

    ref = EvidenceRef(ref_id="claim-1", source="coherence", tier=EvidenceTier.UNVERIFIED)

    value = honest_null(reason="missing_verified_evidence", evidence_refs=[ref])

    assert value.value is None
    assert value.reason == "missing_verified_evidence"
    assert value.evidence_refs == [ref]
