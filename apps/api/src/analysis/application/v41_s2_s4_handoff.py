"""S2 -> S4 *proposal-only* evidence handoff for recovered REAL N4 source.

A-side ownership. No network, DB, credentials, AI calls, trust promotion, or
finance. This object is explicitly NOT a CoherenceVerifiedProjectManifest,
ProjectGraph input, approved baseline, scoring input, or HITL review.

S4/B must separately verify the CURRENT complete project inventory and the
canonical original blob SHA for each source in tenant-scoped PostgreSQL.
In particular, the N2 PII-safe projection SHA is NEVER a source blob SHA.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from collections.abc import Mapping
from typing import Any
from uuid import UUID

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_VERIFIED_PDF = frozenset({
    "PDF_EXACT_UNIQUE",
    "PDF_EXACT_REPEATED_ON_PAGE",
    "PDF_WHITESPACE_NORMALIZED_UNIQUE",
    "PDF_WHITESPACE_NORMALIZED_REPEATED_ON_PAGE",
})


class S2S4HandoffError(ValueError):
    """The proposed review data are not authentic enough even to hand off."""


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf8")).hexdigest()


def _uuid(value: object) -> bool:
    try:
        return isinstance(value, str) and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def create_pending_s2_s4_manifest(packet: Mapping[str, Any]) -> dict[str, Any]:
    """Return a *non-promotable* per-risk provenance index, without source text.

    The supplied packet has already been authenticated against BOTH fixed SHA
    values by the N4 recovery CLI and optionally the original SEC PDF. This
    second guard catches tampering and disallows laundering invented actions.
    It intentionally cannot manufacture the project's tenant/run/blob identity.
    """
    if not isinstance(packet, Mapping):
        raise S2S4HandoffError("OFFLINE_REVIEW_PACKET_MISSING")
    if (packet.get("packet_kind") != "OFFLINE_N4_REVIEW_PREPARATION_NOT_HITL"
        or packet.get("n4_status") != "PARTIAL"
        or packet.get("n12_status") != "NOT_STARTED"
        or packet.get("review_recording_enabled") is not False
        or packet.get("review_row_id") is not None
        or packet.get("trusted_artifact_id") is not None
        or packet.get("n12_checkpoint_id") is not None
        or packet.get("projectgraph_projection_enabled") is not False
        or packet.get("coherence_score_change") is not None
        or packet.get("user_94_page_pdf_attested") is not False):
        raise S2S4HandoffError("OFFLINE_PROPOSALS_CANNOT_BECOME_HITL_OR_S4")
    projection = packet.get("source_sha256")
    filing = packet.get("sec_original_filing_sha256_verified")
    run_id = packet.get("run_id")
    if (not isinstance(projection, str) or not _SHA.fullmatch(projection)
        or not isinstance(filing, str) or not _SHA.fullmatch(filing)
        or not _uuid(run_id)
        or packet.get("sec_filing_page_count") != 224
        or packet.get("sec_exhibit_page_count") != 73):
        raise S2S4HandoffError("N2_OR_ORIGINAL_SEC_SOURCE_NOT_ATTESTED")
    risks = packet.get("findings")
    if (not isinstance(risks, list)
        or not risks or len(risks) > 10_000
        or type(packet.get("candidate_count")) is not int
        or packet["candidate_count"] != len(risks)):
        raise S2S4HandoffError("PROPOSAL_INVENTORY_NOT_COMPLETE")
    seen: set[str] = set()
    revisions: set[str] = set()
    reviewed: Counter[str] = Counter()
    pdf_verdicts: Counter[str] = Counter()
    pointers: list[dict[str, object]] = []
    for i, candidate in enumerate(risks):
        if not isinstance(candidate, Mapping):
            raise S2S4HandoffError("MALFORMED_CANDIDATE")
        risk_key = candidate.get("n4_finding_key")
        ref = candidate.get("source_provenance")
        rev = candidate.get("source_revision_id")
        ordinal = candidate.get("offline_ordinal")
        window = candidate.get("n4_window_ordinal")
        if (not isinstance(risk_key, str) or not _SHA.fullmatch(risk_key)
            or risk_key in seen
            or ordinal != i or type(ordinal) is not int
            or type(window) is not int or not 0 <= window < 24
            or not isinstance(rev, str) or not _uuid(rev)
            or candidate.get("n4_run_id") != run_id
            or candidate.get("review_decision") is not None
            or candidate.get("reviewer_identity") is not None
            or not isinstance(ref, Mapping)
            or ref.get("type") != "N2_MODEL_SAFE_PROJECTION"
            or ref.get("sha256") != projection
            or ref.get("original_pdf_page_verified") is not False):
            raise S2S4HandoffError("PROPOSAL_IDENTITY_OR_REVIEW_FALSIFIED")
        seen.add(risk_key)
        revisions.add(rev)
        label = ref.get("quote_status")
        pdf = ref.get("sec_pdf_quote_match")
        excerpt = ref.get("quote_text")
        span = ref.get("analysis_span_n2")
        sec_page = ref.get("sec_filing_page")
        exhibit_page = ref.get("sec_exhibit_page")
        if label == "VERIFIED_IN_N2":
            if (pdf not in _VERIFIED_PDF
                or not isinstance(excerpt, str) or not excerpt.strip()
                or not isinstance(span, list) or len(span) != 2
                or any(type(v) is not int for v in span)
                or not 0 <= span[0] < span[1]
                or type(sec_page) is not int or type(exhibit_page) is not int
                or not 4 <= sec_page <= 76
                or exhibit_page != sec_page - 3):
                raise S2S4HandoffError("PDF_VERIFIED_QUOTE_PROVENANCE_INVALID")
            reviewed["literal_n2_and_sec_pdf"] += 1
        elif label == "NOT_VERIFIED_IN_N2":
            if (pdf != "NO_VERIFIABLE_N2_QUOTE" or excerpt is not None
                or span is not None or sec_page is not None
                or exhibit_page is not None):
                raise S2S4HandoffError("UNVERIFIED_QUOTE_CANNOT_GAIN_PAGE")
            reviewed["model_claim_without_verifiable_quote"] += 1
        else:
            raise S2S4HandoffError("UNKNOWN_N4_EVIDENCE_CLASS")
        pdf_verdicts[str(pdf)] += 1
        pointers.append({
            "finding_key": risk_key,
            "source_revision_id_from_disposed_qa_run": rev,
            "n4_window_ordinal": window,
            "source_evidence": label,
            "sec_pdf_match": pdf,
            "sec_filing_page": sec_page,
            "sec_exhibit_page": exhibit_page,
            "review": "PENDING_HUMAN",
            "s4_scoring_authority": False,
        })
    if len(revisions) != 1 or len({x["n4_window_ordinal"] for x in pointers}) != 24:
        raise S2S4HandoffError("N4_SOURCE_REVISION_OR_WINDOW_GAP")
    verdict = {
        "contract": "c2pro-v41-s2-s4-source-handoff/v1",
        "scope": "A_SIDE_PROPOSAL_EVIDENCE_ONLY",
        "s2_n4_run_from_disposed_qa_database": run_id,
        "n2_safe_projection_sha256": projection,
        "sec_original_filing_sha256": filing,
        "original_blob_sha256_from_current_project_db": None,
        "current_trusted_project_run_id": None,
        "tenant_id_current": None,
        "project_id_current": None,
        "coherence_verified_manifest_sha256": None,
        "coherence_complete_project_inventory_verified": False,
        "canonical_hitl_review_id": None,
        "n12_completed_checkpoint_id": None,
        "n4_full_source_coverage": False,
        "n4_provider_windows_with_proposed_findings": 24,
        "proposed_count": len(pointers),
        "n2_and_sec_pdf_literal_evidence_count": reviewed["literal_n2_and_sec_pdf"],
        "unverified_literal_count": reviewed["model_claim_without_verifiable_quote"],
        "pdf_verdicts": dict(sorted(pdf_verdicts.items())),
        "validated_count": 0,
        "pending_human_review_count": len(pointers),
        "accepted_risks": [],
        "score_validated": None,
        "score_pending": None,
        "coherence_result": "UNASSESSED_NOT_CALLED",
        "s4_provider_call_authorized": False,
        "projectgraph_promotion_authorized": False,
        "must_not_use_n2_digest_as_original_blob": True,
        "blockers": [
            "N4_ANALYSIS_PARTIAL_AND_REFERENCE_GAPS",
            "N12_REAL_NOT_EXECUTED",
            "AUTHENTICATED_HITL_DECISIONS_NOT_PRESENT",
            "CURRENT_TENANT_PROJECT_AND_BLOB_SHA_NOT_VERIFIED",
            "B_COMPLETE_PROJECT_REVISION_MANIFEST_NOT_VERIFIED",
            "DISPOSED_QA_RUN_ID_NOT_CURRENT_PROJECT_STATE",
            "USER_94_PAGE_PDF_NOT_ATTESTED",
        ],
        "item_pointers_without_quotes_or_model_text": pointers,
    }
    verdict["handoff_sha256"] = _sha(verdict)
    return verdict
