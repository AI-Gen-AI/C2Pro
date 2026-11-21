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
import os
import re
from bisect import bisect_right
from collections import Counter
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from scripts.v41_private_cli_paths import (
    authorize_private_input,
    authorize_private_output,
)
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
        # Rebuild the N4 application's ORIGINAL immutable identity scheme.
        # A syntactically unique SHA is insufficient: an altered category,
        # locator or window must not be laundered by an authentic receipt.
        anchor = (
            ref["analysis_span"][0]
            if isinstance(ref.get("analysis_span"), list)
            and ref["analysis_span"]
            else None
        )
        key_material = {
            "source_sha256": ref.get("source_sha256"),
            "revision": ref.get("document_revision_id"),
            "category": claim.get("category"),
            "title": claim.get("title"),
            "quote_anchor": anchor,
            "clause": claim.get("clause_ref") if anchor is None else None,
            "window": ordinal if anchor is None else None,
        }
        calculated_key = _digest(json.dumps(
            key_material, sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf8"))
        if calculated_key != key:
            raise N4ArtifactRecoveryError("N4_FINDING_IDENTITY_MISMATCH")
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
                or window.context_text.count(quote) != 1
                or ("quote_sha256" in ref
                    and ref["quote_sha256"] != _digest(quote.encode("utf8")))):
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


def prepare_offline_hitl_packet(
    evidence: dict, protected_text: str, *,
    expected_run_sha: str, expected_source_sha256: str,
) -> dict:
    """Prepare exactly the recovered candidates for later authenticated review.

    This is NOT a persisted HITL review, immutable artifact, N12 checkpoint or
    ProjectGraph input. A real API must issue and re-verify those authorities.
    The source quote is displayed ONLY when verified verbatim against N2.
    """
    report = inspect_real_n4(
        evidence, protected_text,
        expected_run_sha=expected_run_sha,
        expected_source_sha256=expected_source_sha256,
    )
    ordered = sorted(
        evidence["n4"]["candidates"],
        key=lambda item: (item["window_ordinal"], item["finding_key"]),
    )
    findings = []
    for index, item in enumerate(ordered):
        claim = item["claim"]
        ref = item["source_refs"][0]
        verified = ref["evidence_status"] == "EXACT_MODEL_SAFE_MATCH"
        findings.append({
            "offline_ordinal": index,
            "n4_finding_key": item["finding_key"],
            "n4_run_id": report["run_id"],
            "source_revision_id": ref["document_revision_id"],
            "n4_window_ordinal": item["window_ordinal"],
            "title": claim["title"],
            "category_model_proposed": claim["category"],
            "model_interpretation": claim["risk_reason"],
            "model_impact": claim.get("impact"),
            "model_reported_clause_ref_unverified": claim.get("clause_ref"),
            "source_provenance": {
                "type": "N2_MODEL_SAFE_PROJECTION",
                "sha256": ref["source_sha256"],
                "quote_status": (
                    "VERIFIED_IN_N2" if verified else "NOT_VERIFIED_IN_N2"
                ),
                "quote_text": claim.get("source_quote") if verified else None,
                "analysis_span_n2": ref["analysis_span"] if verified else None,
                "original_pdf_page_verified": False,
                "unverified_reason": (
                    None if verified else ref["evidence_status"]
                ),
            },
            "review_decision": None,
            "reviewer_identity": None,
        })
    return {
        "packet_kind": "OFFLINE_N4_REVIEW_PREPARATION_NOT_HITL",
        "producer_run_sha": expected_run_sha,
        "source_sha256": expected_source_sha256,
        "run_id": report["run_id"],
        "candidate_count": len(findings),
        "n4_status": report["legacy_n4_status"],
        "n12_status": report["n12_status"],
        "candidate_review_actions_available_only_via_authenticated_api": [
            "CONFIRMED", "DISMISSED", "NEEDS_INFO", "CORRECTION_PROPOSED",
        ],
        "review_recording_enabled": False,
        "review_row_id": None,
        "trusted_artifact_id": None,
        "n12_checkpoint_id": None,
        "projectgraph_projection_enabled": False,
        "coherence_score_change": None,
        "blockers": [
            "N4_PARTIAL_SOURCE_COVERAGE",
            "N12_REAL_PROVIDER_NOT_EXECUTED",
            "NO_IMMUTABLE_CANDIDATE_ARTIFACT_OR_AUTHENTICATED_REVIEW",
            "NO_HUMAN_DECISIONS",
            "USER_94_PAGE_PDF_NOT_ATTESTED",
        ],
        "findings": findings,
    }


def attest_original_sec_filing_pages(
    packet: dict, protected_text: str, *, sec_pdf_bytes: bytes,
    expected_filing_sha256: str,
) -> dict:
    """Verify source quotes against ORIGINAL SEC filing page text, offline.

    This is *not* attestation against the user's separate 94-page PDF.
    Whitespace-normalized matches preserve source words but not PDF layout;
    repeated quotes are explicitly marked ambiguous within the cited page.
    """
    import fitz

    if (len(sec_pdf_bytes) > 25_000_000
        or _digest(sec_pdf_bytes) != expected_filing_sha256
        or _digest(protected_text.encode("utf8")) != packet["source_sha256"]):
        raise N4ArtifactRecoveryError("SEC_PDF_OR_N2_SOURCE_SHA256_MISMATCH")
    markers = list(re.finditer(
        r"\[\[PDF_PAGE_(\d{3}) SEC_8K_PAGE_(\d{3})\]\]", protected_text,
    ))
    if (len(markers) != 73
        or any(
            int(m.group(1)) != i + 1 or int(m.group(2)) != i + 4
            for i, m in enumerate(markers)
        )):
        raise N4ArtifactRecoveryError("SEC_N2_PAGE_MARKER_CHAIN_NOT_VERIFIABLE")
    starts = [m.start() for m in markers]
    classifications: Counter[str] = Counter()
    with fitz.open(stream=sec_pdf_bytes, filetype="pdf") as pdf:
        if pdf.page_count != 224:
            raise N4ArtifactRecoveryError("ORIGINAL_SEC_PDF_PAGE_COUNT_CHANGED")
        texts = {
            page_number: pdf[page_number - 1].get_text("text")
            for page_number in range(4, 77)
        }
        for candidate in packet["findings"]:
            trace = candidate["source_provenance"]
            trace["sec_exhibit_page"] = None
            trace["sec_filing_page"] = None
            trace["sec_pdf_quote_match"] = "NO_VERIFIABLE_N2_QUOTE"
            trace["sec_pdf_quote_occurrences_on_page"] = None
            if trace["quote_status"] != "VERIFIED_IN_N2":
                continue
            span = trace["analysis_span_n2"]
            i = bisect_right(starts, span[0]) - 1
            if (i < 0 or span[0] < markers[i].end()
                or (i + 1 < len(markers)
                    and span[1] > markers[i + 1].start())):
                raise N4ArtifactRecoveryError("N2_QUOTE_CROSSES_PDF_PAGE_MARKER")
            sec_page = int(markers[i].group(2))
            page_text = texts[sec_page]
            quote = trace["quote_text"]
            exact_count = page_text.count(quote)
            if exact_count:
                how = ("PDF_EXACT_UNIQUE" if exact_count == 1
                       else "PDF_EXACT_REPEATED_ON_PAGE")
                matches = exact_count
            else:
                # Changes line-breaks and whitespace only; never approximates
                # wording, punctuation, numbers or contractual meaning.
                compact_page = " ".join(page_text.split())
                compact_quote = " ".join(quote.split())
                matches = compact_page.count(compact_quote)
                how = (
                    "PDF_WHITESPACE_NORMALIZED_UNIQUE"
                    if matches == 1 else
                    "PDF_WHITESPACE_NORMALIZED_REPEATED_ON_PAGE"
                    if matches > 1 else "PDF_TEXT_NOT_FOUND_ON_REFERENCED_PAGE"
                )
            if not matches:
                raise N4ArtifactRecoveryError("N2_QUOTE_NOT_AT_SEC_SOURCE_PAGE")
            trace["sec_exhibit_page"] = int(markers[i].group(1))
            trace["sec_filing_page"] = sec_page
            trace["sec_pdf_quote_match"] = how
            trace["sec_pdf_quote_occurrences_on_page"] = matches
            classifications[how] += 1
    packet["sec_original_filing_sha256_verified"] = expected_filing_sha256
    packet["sec_filing_page_count"] = 224
    packet["sec_exhibit_page_count"] = 73
    packet["sec_original_filing_evidence_summary"] = dict(sorted(classifications.items()))
    packet["user_94_page_pdf_attested"] = False
    return packet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--n2-source", required=True, type=Path)
    parser.add_argument("--expected-evidence-sha256", required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-run-sha", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--review-packet-out", type=Path)
    parser.add_argument("--original-sec-pdf", type=Path)
    args = parser.parse_args()
    try:
        args.evidence = authorize_private_input(
            args.evidence, filename="real_analysis_evidence.json",
        )
        args.n2_source = authorize_private_input(
            args.n2_source, filename="source_n2_protected.txt",
        )
        if args.original_sec_pdf is not None:
            args.original_sec_pdf = authorize_private_input(
                args.original_sec_pdf, filename="sec_8k.pdf",
            )
        args.out = authorize_private_output(args.out)
        if args.review_packet_out is not None:
            args.review_packet_out = authorize_private_output(args.review_packet_out)
        raw = args.evidence.read_bytes()
        if len(raw) > 25_000_000 or _digest(raw) != args.expected_evidence_sha256:
            raise N4ArtifactRecoveryError("REAL_ARTIFACT_DIGEST_MISMATCH")
        source_text = args.n2_source.read_text(encoding="utf8")
        original_evidence = json.loads(raw)
        report = inspect_real_n4(
            original_evidence, source_text,
            expected_run_sha=args.expected_run_sha,
            expected_source_sha256=args.expected_source_sha256,
        )
        if args.original_sec_pdf and not args.review_packet_out:
            raise N4ArtifactRecoveryError("SEC_PDF_REQUIRES_OFFLINE_REVIEW_PACKET")
        review_packet = (
            prepare_offline_hitl_packet(
                original_evidence, source_text,
                expected_run_sha=args.expected_run_sha,
                expected_source_sha256=args.expected_source_sha256,
            ) if args.review_packet_out else None
        )
        if review_packet is not None and args.original_sec_pdf:
            filing_sha = (original_evidence.get("source") or {}).get(
                "source_filing_sha256",
            )
            if not isinstance(filing_sha, str) or len(filing_sha) != 64:
                raise N4ArtifactRecoveryError("SEC_ORIGINAL_FILING_SHA_UNPINNED")
            if args.original_sec_pdf.stat().st_size > 25_000_000:
                raise N4ArtifactRecoveryError("SEC_ORIGINAL_FILING_UNBOUNDED")
            attest_original_sec_filing_pages(
                review_packet, source_text,
                sec_pdf_bytes=args.original_sec_pdf.read_bytes(),
                expected_filing_sha256=filing_sha,
            )
    except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc)[:120]}))
        return 2
    try:
        if review_packet is not None:
            assert args.review_packet_out is not None
            path = args.review_packet_out
            # Output root must exist and is independently authorized.
            # Full model suggestions are sensitive analysis material. Never
            # overwrite an existing packet or follow a symlink.
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            fd = os.open(path, flags, 0o600)
            with os.fdopen(fd, "w", encoding="utf8") as output:
                json.dump(review_packet, output, indent=2, ensure_ascii=False)
                output.write("\n")
        # Reject existing symlinks and avoid following newly swapped links.
        out_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
        out_fd = os.open(args.out, out_flags, 0o600)
        with os.fdopen(out_fd, "w", encoding="utf8") as output:
            output.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": type(exc).__name__}))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
