"""B4 isolated, read-only preview over the existing source comparison engine.

No API route, worker, DB, model, ProjectGraph scoring, trust promotion or automatic
approval. Source observations and trusted document artifacts MUST be independently
loaded from immutable revisions by the caller. This harness checks identities and
hashes again; it cannot certify authenticity of a PDF or the completeness of BOQ.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import UUID

from src.analysis.adapters.graph.structured_source_comparison import (
    _source_row,
    compare_original_source_rows,
)
from src.analysis.application.b3_project_graph_preview import _validated_b3_refs
from src.analysis.application.b3_source_inventory_bridge import B3SourceBridgeError
from src.analysis.domain.contracts import DocumentArtifact


def preview_b4_provisional_comparison(
    *,
    packet: Mapping[str, Any],
    tenant_id: UUID,
    project_id: UUID,
    trusted_document_artifacts: Sequence[DocumentArtifact],
    source_units: Sequence[Mapping[str, Any]],
    source_quotes: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Compare revision-pinned evidence without touching Coherence or persistence.

    `trusted_document_artifacts` and `source_quotes` MUST originate in the
    existing trusted-artifact and N2 source-quote resolvers. This is a pure
    diagnostic boundary and does NOT establish that those inputs are trusted.
    Its results are provisional even when the comparator reports a discrepancy.
    """
    refs = _validated_b3_refs(packet, project_id=project_id, tenant_id=tenant_id)
    by_family = {ref["family"]: ref for ref in refs}
    if len(by_family) != len(refs):
        raise B3SourceBridgeError("multiple revisions of a source family require explicit selection")

    contract = by_family["contract"]
    artifacts = list(trusted_document_artifacts)
    if len(artifacts) > 1 or any(
        not isinstance(a, DocumentArtifact)
        or a.doc_type.lower() != "contract"
        or a.document_id != contract["document_id"]
        or a.document_revision_id != contract["revision_id"]
        for a in artifacts
    ):
        raise B3SourceBridgeError("B4 contract artifact is not bound to selected revision")

    validated_units: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for unit in source_units:
        if not isinstance(unit, Mapping):
            raise B3SourceBridgeError("invalid structured source unit")
        family = unit.get("family")
        ref = by_family.get(family)
        if family not in {"schedule", "budget"} or ref is None:
            raise B3SourceBridgeError("B4 unit family not selected in B3 inventory")
        if (unit.get("tenant_id") != str(tenant_id)
            or unit.get("project_id") != str(project_id)
            or unit.get("document_id") != ref["document_id"]
            or unit.get("revision_id") != ref["revision_id"]
            or unit.get("blob_hash") != ref["blob_sha256"]):
            raise B3SourceBridgeError("B4 unit revision, project or blob mismatch")
        checked = _source_row(unit)
        if checked is None:
            raise B3SourceBridgeError("B4 original source row checksum/locator invalid")
        kind = checked["payload"].get("kind")
        if (family == "schedule" and kind != "activity") or (
            family == "budget" and kind not in {"budget_line", "declared_total"}
        ):
            raise B3SourceBridgeError("B4 unsupported structured source kind")
        if kind == "declared_total" and (
            checked["payload"].get("source_total_kind") != "EXPLICIT_DECLARED_TOTAL"
            or checked["payload"].get("source_total_review") != "REQUIRES_REVIEW"
        ):
            raise B3SourceBridgeError("B4 budget total requires explicit source-row semantics")
        identity = (str(family), checked["source_locator"])
        if identity in identities:
            raise B3SourceBridgeError("B4 duplicate source unit locator")
        identities.add(identity)
        validated_units.append(dict(unit))

    checked_quotes: list[dict[str, Any]] = []
    for quote in source_quotes:
        if not isinstance(quote, Mapping):
            raise B3SourceBridgeError("invalid B4 quote")
        if (
            quote.get("tenant_id") != str(tenant_id)
            or quote.get("project_id") != str(project_id)
            or quote.get("document_id") != contract["document_id"]
            or quote.get("revision_id") != contract["revision_id"]
            or quote.get("doc_type") != "contract"
        ):
            raise B3SourceBridgeError("B4 quote not bound to selected contract revision")
        text = quote.get("source_quote")
        digest = quote.get("source_quote_sha256")
        locator = quote.get("source_locator")
        if (
            not isinstance(text, str) or not text.strip()
            or not isinstance(digest, str)
            or hashlib.sha256(text.encode("utf-8")).hexdigest() != digest
            or not isinstance(locator, str) or not locator.startswith("chunk:")
        ):
            raise B3SourceBridgeError("B4 N2 quote requires content hash and chunk locator")
        checked_quotes.append(dict(quote))

    if not artifacts:
        return {
            "status": "NOT_ASSESSED",
            "findings": [],
            "not_assessed_reasons": ["TRUSTED_CONTRACT_ARTIFACT_UNAVAILABLE"],
            "source_unit_count": len(validated_units),
            "source_quote_count": len(checked_quotes),
            "coherence_score": None,
            "n12_assessment": "NOT_RUN_BY_B4",
            "trusted_promotions": 0,
            "snapshots_written": 0,
            "alerts_written": 0,
        }

    evaluation = compare_original_source_rows(
        artifacts, validated_units, checked_quotes
    )
    # Deliberately no call into evaluate_artifact_set(), ProjectGraph scoring,
    # write_snapshot(), alerts, HITL writes or any model.
    return {
        "status": "PROVISIONAL_SOURCE_OBSERVATIONS" if evaluation["findings"] else "NOT_ASSESSED",
        "findings": evaluation["findings"],
        "not_assessed_reasons": evaluation["not_assessed_reasons"],
        "source_unit_count": len(validated_units),
        "source_rows_verified": evaluation["source_rows_verified"],
        "source_quote_count": len(checked_quotes),
        "review_required": bool(evaluation["findings"]),
        "coherence_score": None,
        "n12_assessment": "NOT_RUN_BY_B4",
        "trusted_promotions": 0,
        "snapshots_written": 0,
        "alerts_written": 0,
    }


__all__ = ["preview_b4_provisional_comparison"]
