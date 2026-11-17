#!/usr/bin/env python3
"""Recover a bounded, source-checked N4 review inventory from a REAL pilot artifact.

Read-only. No network, provider, DB writes, or new model inference.
A settled call != accepted source coverage; a proposed finding != validated risk.
Source and artifact SHA must be operator-pinned. This tool cannot reconstruct
the disposed PostgreSQL window status rows or unavailable raw model outputs.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from src.analysis.domain.n4_source_windows import plan_n4_source_windows


class N4ArtifactRecoveryError(ValueError):
    """Evidence was incomplete or unsafe; do not promote the recovered review."""


def _digest(data: bytes) -> str:
    return sha256(data).hexdigest()


def inspect_real_n4(
    evidence: dict, protected_text: str, *,
    expected_run_sha: str, expected_source_sha256: str,
) -> dict:
    if evidence.get("run_sha") != expected_run_sha:
        raise N4ArtifactRecoveryError("WRONG_PROVENANCE_RUN_SHA")
    source = evidence.get("source") or {}
    safe_digest = _digest(protected_text.encode("utf-8"))
    if (safe_digest != expected_source_sha256
        or source.get("n2_text_sha256") != safe_digest):
        raise N4ArtifactRecoveryError("N2_SOURCE_SHA256_MISMATCH")
    n4 = evidence.get("n4") or {}
    try:
        run_id = str(UUID(n4["run_id"]))
        candidates = n4["candidates"]
        receipts = n4["receipts"]
        total_windows = int(n4["total_windows"])
    except (TypeError, KeyError, ValueError) as exc:
        raise N4ArtifactRecoveryError("N4_RUN_INVENTORY_UNAVAILABLE") from exc
    if (not isinstance(candidates, list) or not isinstance(receipts, list)
        or total_windows < 1 or total_windows > 10_000):
        raise N4ArtifactRecoveryError("N4_RUN_INVENTORY_MALFORMED")
    if n4.get("status") not in ("PARTIAL", "COMPLETE"):
        raise N4ArtifactRecoveryError("N4_RUN_NOT_REVIEWABLE")

    receipt_ordinals: set[int] = set()
    receipt_ids: set[str] = set()
    for receipt in receipts:
        ordinal = receipt.get("window_ordinal")
        req_id = receipt.get("provider_request_id")
        if (type(ordinal) is not int or not 0 <= ordinal < total_windows
            or ordinal in receipt_ordinals
            or receipt.get("status") != "SETTLED"
            or not isinstance(req_id, str) or not req_id
            or req_id in receipt_ids
            or type(receipt.get("input_tokens")) is not int
            or type(receipt.get("output_tokens")) is not int
            or receipt["input_tokens"] <= 0 or receipt["output_tokens"] <= 0):
            raise N4ArtifactRecoveryError("N4_RECEIPT_UNVERIFIED_OR_DUPLICATE")
        receipt_ordinals.add(ordinal)
        receipt_ids.add(req_id)
    if receipt_ordinals != set(range(total_windows)):
        raise N4ArtifactRecoveryError("N4_RECEIPTS_DO_NOT_COVER_ALL_WINDOWS")

    revision_ids = {
        ref.get("document_revision_id")
        for item in candidates for ref in item.get("source_refs", [])
    }
    if len(revision_ids) != 1:
        raise N4ArtifactRecoveryError("N4_MULTIPLE_OR_MISSING_SOURCE_REVISIONS")
    revision_id = next(iter(revision_ids))
    try:
        UUID(str(revision_id))
    except (ValueError, TypeError) as exc:
        raise N4ArtifactRecoveryError("N4_REVISION_ID_INVALID") from exc

    windows = plan_n4_source_windows(
        protected_text, revision_id=str(revision_id),
        max_context_chars=12_000, overlap_chars=400,
    )
    if (len(windows) != total_windows
        or "".join(w.core_text for w in windows) != protected_text):
        raise N4ArtifactRecoveryError("N4_SOURCE_WINDOW_PLAN_NOT_REPRODUCIBLE")

    seen: set[str] = set()
    counts: Counter[str] = Counter()
    candidate_ordinals: set[int] = set()
    per_window: Counter[int] = Counter()
    evidence_unverified: Counter[str] = Counter()
    for item in candidates:
        key = item.get("finding_key")
        ordinal = item.get("window_ordinal")
        claim = item.get("claim")
        refs = item.get("source_refs")
        if (not isinstance(key, str) or len(key) != 64
            or key in seen or type(ordinal) is not int
            or ordinal not in receipt_ordinals
            or not isinstance(claim, dict)
            or not isinstance(refs, list) or len(refs) != 1
            or claim.get("review_status") != "PROPOSED"
            or not isinstance(claim.get("risk_reason"), str)
            or not claim["risk_reason"].strip()):
            raise N4ArtifactRecoveryError("N4_CANDIDATE_MISSING_OR_DUPLICATE")
        seen.add(key)
        candidate_ordinals.add(ordinal)
        per_window[ordinal] += 1
        ref = refs[0]
        status = ref.get("evidence_status")
        if (ref.get("source_sha256") != safe_digest
            or ref.get("document_revision_id") != revision_id
            or ref.get("source_kind") != "MODEL_SAFE_PROJECTION"
            or claim.get("source_evidence_status") != status):
            raise N4ArtifactRecoveryError("N4_CANDIDATE_SOURCE_IDENTITY_MISMATCH")
        quote = claim.get("source_quote")
        span = ref.get("analysis_span")
        window = windows[ordinal]
        if status == "EXACT_MODEL_SAFE_MATCH":
            if (not isinstance(quote, str) or not quote
                or not isinstance(span, list) or len(span) != 2
                or any(type(i) is not int for i in span)
                or not window.context_start <= span[0] < span[1] <= window.context_end
                or protected_text[span[0]:span[1]] != quote
                or window.context_text.count(quote) != 1):
                raise N4ArtifactRecoveryError("N4_LITERAL_QUOTE_AND_WINDOW_MISMATCH")
            counts["EXACT_N2_SOURCE"] += 1
        else:
            if span is not None or quote is not None or not isinstance(status, str):
                raise N4ArtifactRecoveryError("N4_UNVERIFIED_QUOTE_FALSIFIED")
            counts["UNVERIFIED_SOURCE"] += 1
            evidence_unverified[status] += 1
    if not candidate_ordinals.issubset(receipt_ordinals):
        raise N4ArtifactRecoveryError("N4_CANDIDATE_WITHOUT_SETTLED_RECEIPT")
    return {
        "status": "RECOVERED_PROPOSALS_NOT_SEMANTICALLY_VALIDATED",
        "run_id": run_id,
        "source_n2_sha256": safe_digest,
        "source_pdf_pages_reported": source.get("source_exhibit_pages"),
        "total_windows": total_windows,
        "source_core_window_coverage": len(windows),
        "provider_settled_receipt_windows": len(receipt_ordinals),
        "distinct_provider_receipt_ids": len(receipt_ids),
        "persisted_candidate_windows": len(candidate_ordinals),
        "candidate_count": len(candidates),
        "distinct_candidate_keys": len(seen),
        "candidates_per_window": dict(sorted(per_window.items())),
        "verified_literal_candidates": counts["EXACT_N2_SOURCE"],
        "unverified_literal_candidates": counts["UNVERIFIED_SOURCE"],
        "unverified_reasons": dict(evidence_unverified),
        "pending_human_decisions": len(candidates),
        "approved_human_decisions": 0,
        "rejected_human_decisions": 0,
        "legacy_n4_status": n4["status"],
        "legacy_clean_examined_windows": n4.get("examined_windows"),
        "historical_window_states_reconstructible": False,
        "n12_status": evidence.get("n12", {}).get("status"),
        "projectgraph_status": "NOT_PROMOTED",
        "invoice_verified": False,
        "note": (
            "Distinct settled receipts and saved candidate rows recover a review "
            "inventory without repeating AI. Raw model window outputs and the "
            "disposed original PostgreSQL window rows are not in this artifact; "
            "do not reclassify BLOCKED as EXAMINED."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--n2-source", required=True, type=Path)
    parser.add_argument("--expected-evidence-sha256", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-run-sha", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = args.evidence.read_bytes()
        if len(raw) > 25_000_000 or _digest(raw) != args.expected_evidence_sha256:
            raise N4ArtifactRecoveryError("REAL_ARTIFACT_DIGEST_MISMATCH")
        report = inspect_real_n4(
            json.loads(raw),
            args.n2_source.read_text(encoding="utf8"),
            expected_run_sha=args.expected_run_sha,
            expected_source_sha256=args.expected_source_sha256,
        )
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:120]}))
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
