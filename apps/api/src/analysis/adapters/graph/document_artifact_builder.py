"""Build the Tier-1 DocumentArtifact hand-off for ADR-017.

TS-UT-ADR017-DA-001
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.analysis.domain.report_assembly import decision_snapshot_for_persistence


def _list_value(state: Mapping[str, Any], key: str) -> list[Any]:
    value = state.get(key)
    return value if isinstance(value, list) else []


def _confidence_score(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _pii_redaction_count(state: Mapping[str, Any]) -> int:
    explicit_count = state.get("pii_redaction_count")
    if isinstance(explicit_count, int):
        return max(explicit_count, 0)
    redactions = state.get("pii_redactions")
    return len(redactions) if isinstance(redactions, list) else 0


def _contract_risks(state: Mapping[str, Any]) -> list[Any]:
    """Convert live N4 candidate dictionaries to frozen ProjectGraph RiskItem.

    N4's extractor includes metadata (summary, probability, mitigation_suggestion,
    risk_score, immediate_alert...) that is intentionally NOT in the ADR-017
    RiskItem contract. Passing these through unchanged makes the immutable
    DocumentArtifact fail Pydantic validation and prevents durable projection.

    Keep the risk's canonical fields; the noncanonical mitigation survives
    separately in the N11 decision_snapshot. Do not pretend an unverified quote
    is an exact citation in the trusted artifact.
    """
    allowed = RiskItem.model_fields.keys()
    results: list[Any] = []
    for risk in _list_value(state, "extracted_risks"):
        if not isinstance(risk, Mapping):
            results.append(risk)  # Still fail contract validation explicitly.
            continue
        candidate = {
            name: risk[name]
            for name in allowed
            if name in risk and risk[name] is not None
        }
        if candidate.get("source_quote") and candidate.get("source_quote_status") != "VERIFIED":
            candidate["source_quote"] = None
            candidate["source_quote_status"] = (
                str(risk.get("source_quote_status") or "REQUIRES_SOURCE_VALIDATION")
            )
        results.append(candidate)
    return results


def build_document_artifact(final_state: Mapping[str, Any]) -> DocumentArtifact:
    """Map a Tier-1 final state into the typed Tier-2 artifact contract."""

    return DocumentArtifact.model_validate(
        {
            "document_id": str(final_state.get("document_id") or ""),
            "document_revision_id": final_state.get("document_revision_id"),
            "decision_snapshot": decision_snapshot_for_persistence(
                final_state.get("decision_package"),
                document_id=str(final_state.get("document_id") or "") or None,
                revision_id=str(final_state.get("document_revision_id") or "") or None,
            ),
            "doc_type": str(final_state.get("doc_type") or "unknown"),
            "document_category": final_state.get("document_category"),
            "extracted_risks": _contract_risks(final_state),
            "extracted_wbs": _list_value(final_state, "extracted_wbs"),
            "bom_items": _list_value(final_state, "bom_items"),
            "citations": _list_value(final_state, "citations"),
            "coherence_findings": _list_value(final_state, "coherence_findings"),
            "documentation_health_signal": final_state.get("documentation_health_signal"),
            "confidence_score": _confidence_score(final_state.get("confidence_score")),
            "pii_redaction_count": _pii_redaction_count(final_state),
        }
    )


__all__ = ["build_document_artifact"]
