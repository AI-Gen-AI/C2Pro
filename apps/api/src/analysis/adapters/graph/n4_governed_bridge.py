"""Opt-in N4 graph bridge: durable multi-window candidates into existing HITL graph.

No provider calls occur unless every gate passes: N2-safe source, active fenced
ANALYSIS authority, tenant/project/document/revision identity, explicit cost
limits and pre-existing tenant/project/document budget buckets. The runner
holds the money transactionally before each model call. A model-safe quote
match is NOT proof of original-PDF source or semantic/legal correctness.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.application.n4_incremental_runner import N4IncrementalRunner, N4WindowProvider
from src.analysis.domain.ai_source_text import llm_document_text
from src.analysis.domain.n4_consolidation import consolidate_candidates
from src.analysis.domain.n4_failure_kinds import (
    N4_COVERAGE_SCHEMA_VERSION,
    N4CoverageGap,
    N4CoverageStatus,
    N4FailureKind,
    N4GapResolution,
    derive_n4_coverage_status,
)
from src.analysis.domain.n4_reference_register import build_reference_register
from src.analysis.domain.risk_provenance import classify_quote
from src.core.ai.anthropic_wrapper import AnthropicWrapper
from src.core.ai.model_router import ModelTier
from src.core.database import get_session_factory
from src.core.processing_authority import ProcessingStage, current_authority
from src.documents.application.n4_source_identity import is_n4_source_identity_valid
from src.documents.domain import quote_page_locator as _page_locator


class N4GraphBridgeBlocked(RuntimeError):
    """Fail closed without claiming the source was analyzed or reviewable."""

class N4RunIncomplete(N4GraphBridgeBlocked):
    """A durable N4 run has observable progress but is not HITL-reviewable."""

    def __init__(
        self, *, run_id: UUID, status: str, examined_windows: int,
        total_windows: int, persisted_result_windows: int,
        blocked_result_windows: int, stopped_reason: str | None,
        source_sha256: str,
    ) -> None:
        self.run_id = run_id
        self.status = status
        self.examined_windows = examined_windows
        self.total_windows = total_windows
        self.persisted_result_windows = persisted_result_windows
        self.blocked_result_windows = blocked_result_windows
        self.stopped_reason = stopped_reason
        self.source_sha256 = source_sha256
        super().__init__(
            "N4 durable source window run incomplete; "
            f"reason={stopped_reason or status}"
        )



def _identity(state: Mapping[str, Any]) -> tuple[Any, UUID, str]:
    authority = current_authority()
    if authority is None or authority.stage is not ProcessingStage.ANALYSIS:
        raise N4GraphBridgeBlocked("N4 requires an active analysis processing authority")
    try:
        tenant = UUID(str(state["tenant_id"]))
        doc = UUID(str(state["document_id"]))
        revision = UUID(str(state["document_revision_id"]))
        project = UUID(str(state["project_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise N4GraphBridgeBlocked("N4 exact tenant/project/document/revision identity missing") from exc
    if (
        authority.tenant_id != tenant or authority.document_id != doc
        or authority.revision_id != revision
    ):
        raise N4GraphBridgeBlocked("N4 authority is not for the source revision")
    if state.get("pii_anonymization_complete") is not True:
        raise N4GraphBridgeBlocked("N2 anonymization has not completed")
    original = state.get("document_text")
    projection = state.get("anonymized_text")
    if not isinstance(original, str) or not isinstance(projection, str) or not projection.strip():
        raise N4GraphBridgeBlocked("N4 N2-safe source projection is missing")
    if not is_n4_source_identity_valid(state, parsed_text=original):
        raise N4GraphBridgeBlocked("N4 pinned revision parser-text provenance unavailable")
    if llm_document_text(state) != projection:
        raise N4GraphBridgeBlocked("N4 LLM-facing source is not the pinned N2 projection")
    # Only the exact input projection's coverage may be established; N2 may have
    # redacted original sections. The N12/original document attestation remains
    # independent and must not be manufactured here.
    return authority, project, projection


def _limits() -> tuple[Decimal, Decimal, int, int]:
    try:
        run = Decimal(os.environ["C2PRO_N4_GRAPH_RUN_USD"])
        call = Decimal(os.environ["C2PRO_N4_GRAPH_WINDOW_USD"])
        max_chars = int(os.environ["C2PRO_N4_GRAPH_WINDOW_CHARS"])
        overlap = int(os.getenv("C2PRO_N4_GRAPH_OVERLAP_CHARS", "400"))
    except (KeyError, ValueError, TypeError, ArithmeticError) as exc:
        raise N4GraphBridgeBlocked("N4 explicit cost and source window policy absent") from exc
    if (
        not run.is_finite() or not call.is_finite()
        or run <= 0 or call <= 0 or call > run or run > Decimal("10")
        or call > Decimal("1") or max_chars < 1000 or max_chars > 20_000
        or overlap < 0 or overlap >= max_chars // 3
    ):
        raise N4GraphBridgeBlocked("N4 cost or source window policy outside allowed bounds")
    return run, call, max_chars, overlap


def _uat_inherited_scopes(tenant_id: UUID) -> bool:
    """Require exact UAT environment + approved tenant; never opt in by key alone."""
    if os.getenv("C2PRO_N4_UAT_INHERIT_SCOPES") != "1":
        return False
    approved = os.getenv("C2PRO_N4_UAT_APPROVED_TENANT_ID", "").strip()
    if approved != str(tenant_id):
        raise N4GraphBridgeBlocked(
            "N4 child-budget inheritance requires approved tenant"
        )
    railway_id = os.getenv("RAILWAY_ENVIRONMENT_ID", "").strip()
    railway_name = os.getenv("RAILWAY_ENVIRONMENT_NAME", "").strip().lower()
    if railway_id or railway_name:
        # On Railway, deployment identity is stronger than an application
        # ENVIRONMENT variable (which may legitimately be 'production' in UAT).
        pinned_id = os.getenv(
            "C2PRO_N4_UAT_APPROVED_RAILWAY_ENVIRONMENT_ID", ""
        ).strip()
        if railway_name != "pilot" or not pinned_id or railway_id != pinned_id:
            raise N4GraphBridgeBlocked(
                "N4 child-budget inheritance requires pinned UAT environment"
            )
    elif os.getenv("ENVIRONMENT", "").strip().lower() not in {"uat", "pilot"}:
        raise N4GraphBridgeBlocked(
            "N4 child-budget inheritance requires named UAT environment"
        )
    return True


_INFLIGHT_RESERVATIONS = frozenset({"RESERVED", "UNKNOWN"})
_KNOWN_FAILURE_KINDS = frozenset(k.value for k in N4FailureKind)
_UNCLASSIFIED_REASON = "Window not examined; failure kind unclassified"


def _page_spans(raw: Sequence[Any] | None) -> list[_page_locator.PageSpan]:
    """Normalize a page map (PageSpan or dict rows); malformed rows are dropped."""
    spans: list[_page_locator.PageSpan] = []
    for row in raw or ():
        if isinstance(row, _page_locator.PageSpan):
            spans.append(row)
        elif isinstance(row, Mapping):
            try:
                spans.append(_page_locator.PageSpan(
                    int(row["page"]), int(row["start_offset"]), int(row["end_offset"]),
                ))
            except (KeyError, TypeError, ValueError):
                continue
    return spans


# A11 excludes OCR_REPLACED_SUSPECT from its A9 map, retaining raw audit blocks.
# A7 must reject unsafe OCR without invalidating unaffected physical pages.
_A11_A9_OBSERVED_STATES = frozenset({
    "NATIVE_TEXT", "OCR_ONLY", "OCR_AUGMENTED",
    "OCR_DUPLICATE_IGNORED",
})
_A7_CITABLE_PAGE_STATES = _A11_A9_OBSERVED_STATES - {"OCR_REPLACED_SUSPECT"}
_A11_PAGE_DIAGNOSTICS = _A11_A9_OBSERVED_STATES | {
    "OCR_REPLACED_SUSPECT",
    "OCR_UNAVAILABLE", "OCR_FAILED", "OCR_EMPTY_RESULT", "OCR_UNCLASSIFIED",
    "SPARSE_TEXT_UNVERIFIED", "SPARSE_OCR_FAILED", "SPARSE_OCR_EMPTY",
    "NO_TEXT_UNASSESSED", "SUSPECT_NATIVE_TEXT_UNVERIFIED",
    "TEXT_OBSERVED_UNASSESSED", "NO_DIAGNOSTIC",
}


def _a11_a9_page_map(state: Mapping[str, Any]) -> tuple[list[_page_locator.PageSpan], bool]:
    """Consume only A11's revision-bound PDF projection, never arbitrary spans.

    The second value records that a physical map was supplied, including if it
    was malformed: a rejected map must yield PAGE_UNRESOLVED, not VERIFIED.
    A11's full block lineage is checked independently to prevent selective
    deletion of unsafe OCR rows or offsets in the compact A9 view.
    """
    identity = state.get("n4_source_identity")
    if not isinstance(identity, Mapping) or "a9_physical_page_map" not in identity:
        return [], False
    raw_map = identity["a9_physical_page_map"]
    lineage = identity.get("physical_page_lineage")
    parsed = state.get("document_text")
    if (
        not isinstance(raw_map, Mapping) or not isinstance(lineage, Mapping)
        or not isinstance(parsed, str) or not parsed
        or state.get("anonymized_text") != parsed
        or identity.get("parser_origin") != "pdf_file_parser"
        or not is_n4_source_identity_valid(state, parsed_text=parsed)
    ):
        return [], True

    digest = sha256(parsed.encode("utf-8")).hexdigest()
    revision = state.get("document_revision_id")
    blob_hash = identity.get("blob_hash")
    count = raw_map.get("source_pages")
    if (
        not isinstance(blob_hash, str) or len(blob_hash) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in blob_hash)
        or type(count) is not int or not 1 <= count <= 10_000
        or raw_map.get("schema_version") != "a11-a9-physical-page-map-v1"
        or raw_map.get("source_kind") != "PDF_PHYSICAL_PAGE_OBSERVATION"
        or raw_map.get("original_document_completeness_certified") is not False
        or raw_map.get("revision_id") != revision
        or raw_map.get("blob_hash") != blob_hash
        or raw_map.get("parsed_text_sha256") != digest
        or lineage.get("revision_id") != revision
        or lineage.get("blob_hash") != blob_hash
        or lineage.get("parsed_text_sha256") != digest
        or lineage.get("status") != "OBSERVED_ONLY"
        or lineage.get("origin") != "pdf_file_parser"
        or lineage.get("source_pages") != count
    ):
        return [], True

    pages = lineage.get("pages")
    blocks = lineage.get("spans")
    encoded = raw_map.get("spans")
    excluded = raw_map.get("excluded_pages")
    if (
        not isinstance(pages, list) or len(pages) != count
        or not isinstance(blocks, list)
        or not isinstance(encoded, list) or not isinstance(excluded, list)
    ):
        return [], True

    diagnoses: dict[int, str] = {}
    for expected_page, item in enumerate(pages, start=1):
        if not isinstance(item, Mapping):
            return [], True
        number, status = item.get("page"), item.get("status")
        if (
            type(number) is not int or number != expected_page
            or not isinstance(status, str)
            or status not in _A11_PAGE_DIAGNOSTICS
        ):
            return [], True
        diagnoses[number] = status
    if len(diagnoses) != count:
        return [], True

    # Reconstruct exactly A11's grouped-by-page spans from source-aligned
    # blocks. Every non-whitespace character must belong to some raw block;
    # unsafe pages are deliberately retained here for coverage verification.
    cursor = 0
    prior_page = 0
    grouped: list[dict[str, int]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            return [], True
        page = block.get("page")
        start, end = block.get("start_offset"), block.get("end_offset")
        method = block.get("method")
        if (
            type(page) is not int or not 1 <= page <= count
            or block.get("page_verified") is not True
            or type(start) is not int or type(end) is not int
            or not 0 <= cursor <= start < end <= len(parsed)
            or page < prior_page or not isinstance(method, str)
            or method not in {"NATIVE", "OCR"}
            or parsed[cursor:start].strip() or not parsed[start:end].strip()
            or (diagnoses[page] in {"OCR_ONLY", "OCR_REPLACED_SUSPECT"}
                and method != "OCR")
            or (diagnoses[page] in {"NATIVE_TEXT", "OCR_DUPLICATE_IGNORED"}
                and method != "NATIVE")
        ):
            return [], True
        if grouped and grouped[-1]["page"] == page:
            grouped[-1]["end_offset"] = end
        else:
            grouped.append({"page": page, "start_offset": start, "end_offset": end})
        cursor, prior_page = end, page
    if parsed[cursor:].strip():
        return [], True

    expected = [row for row in grouped if diagnoses[row["page"]] in _A11_A9_OBSERVED_STATES]
    expected_excluded = [
        {"page": number, "reason": diagnoses[number]}
        for number in range(1, count + 1)
        if diagnoses[number] not in _A11_A9_OBSERVED_STATES
    ]
    expected_status = (
        "NO_LOCATABLE_PAGES" if not expected
        else "PARTIAL" if expected_excluded else "OBSERVED_ONLY"
    )
    if (
        encoded != expected or excluded != expected_excluded
        or raw_map.get("status") != expected_status
    ):
        return [], True

    # Only non-suspect, nonfailed OCR/native pages can reach the A9 locator.
    return [
        _page_locator.PageSpan(row["page"], row["start_offset"], row["end_offset"])
        for row in expected if diagnoses[row["page"]] in _A7_CITABLE_PAGE_STATES
    ], True


def _grounded_page_spans(state: Mapping[str, Any]) -> list[_page_locator.PageSpan]:
    """A7 never falls back to unpinned legacy parsed_text_page_spans."""
    return _a11_a9_page_map(state)[0]

def _approx_pages(
    spans: Sequence[_page_locator.PageSpan], start: int, end: int,
) -> tuple[int | None, int | None]:
    hit = [p.page for p in spans if p.start_offset < end and p.end_offset > start]
    return (min(hit), max(hit)) if hit else (None, None)


def assess_n4_run(
    *,
    outcome: Any,
    windows: Sequence[Mapping[str, Any]],
    reservations: Sequence[Mapping[str, Any]],
    source_sha256: str,
    page_spans: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Return N4Coverage for a reviewable run or raise ``N4RunIncomplete``.

    Reviewable = every window terminal (EXAMINED, or BLOCKED as a recorded gap),
    at least one persisted result, and no in-flight/UNKNOWN reservation (a
    possibly billed or still running call is never a closed gap).
    """
    spans = _page_spans(page_spans)
    examined = [w for w in windows if w["status"] == "EXAMINED"]
    blocked = [w for w in windows if w["status"] == "BLOCKED"]
    inflight = any(r["status"] in _INFLIGHT_RESERVATIONS for r in reservations)
    # The returned rows must represent the *entire* planned source. Counting
    # only rows fetched from the ledger can silently hide a missing window.
    expected_total = outcome.total_windows
    ordinal_values = [w.get("ordinal") for w in windows]
    valid_ordinals = [
        ordinal for ordinal in ordinal_values
        if isinstance(ordinal, int) and not isinstance(ordinal, bool)
    ]
    ledger_consistent = (
        isinstance(expected_total, int) and not isinstance(expected_total, bool)
        and expected_total > 0 and len(windows) == expected_total
        and len(valid_ordinals) == expected_total
        and sorted(valid_ordinals) == list(range(expected_total))
        and outcome.examined_windows == len(examined)
    )
    terminal = bool(windows) and len(examined) + len(blocked) == len(windows)
    if (
        not ledger_consistent or not terminal or inflight or not examined
        or int(outcome.persisted_result_windows) < 1
    ):
        raise N4RunIncomplete(
            run_id=outcome.run_id, status=outcome.status,
            examined_windows=outcome.examined_windows,
            total_windows=outcome.total_windows,
            persisted_result_windows=outcome.persisted_result_windows,
            blocked_result_windows=outcome.blocked_result_windows,
            stopped_reason=outcome.stopped_reason, source_sha256=source_sha256,
        )
    attempts: dict[int, int] = {}
    for r in reservations:
        ordinal = int(r["window_ordinal"])
        attempts[ordinal] = attempts.get(ordinal, 0) + 1
    gaps: list[N4CoverageGap] = []
    for w in sorted(blocked, key=lambda row: int(row["ordinal"])):
        raw = str(w.get("blocked_reason") or "")
        known = raw in _KNOWN_FAILURE_KINDS
        start, end = _approx_pages(spans, int(w["core_start"]), int(w["core_end"]))
        gaps.append({
            "ordinal": int(w["ordinal"]),
            "failure_kind": raw if known else "UNCLASSIFIED",
            # Raw ledger text is never echoed: only a closed vocabulary.
            "reason": raw if known else _UNCLASSIFIED_REASON,
            "attempts": attempts.get(int(w["ordinal"]), 0),
            "page_start": start,
            "page_end": end,
            "resolution": N4GapResolution.OPEN.value,
        })
    gap_windows = [g["ordinal"] for g in gaps]
    status = derive_n4_coverage_status(
        total_windows=expected_total, examined_windows=len(examined),
        gap_windows=gap_windows,
    )
    if status is N4CoverageStatus.INCOMPLETE:  # defensive: unreachable if terminal
        raise N4RunIncomplete(
            run_id=outcome.run_id, status=outcome.status,
            examined_windows=outcome.examined_windows,
            total_windows=outcome.total_windows,
            persisted_result_windows=outcome.persisted_result_windows,
            blocked_result_windows=outcome.blocked_result_windows,
            stopped_reason=outcome.stopped_reason, source_sha256=source_sha256,
        )
    return {
        "schema_version": N4_COVERAGE_SCHEMA_VERSION,
        "status": status.value,
        "run_id": str(outcome.run_id),
        "source_sha256": source_sha256,
        "total_windows": expected_total,
        "examined_windows": len(examined),
        "gap_windows": gap_windows,
        "gaps": gaps,
    }


async def _load_run_ledger(
    tenant_id: UUID, run_id: UUID,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": str(tenant_id)},
        )
        params = {"tenant": str(tenant_id), "run": str(run_id)}
        windows = (await session.execute(text("""
            SELECT ordinal, status, blocked_reason, core_start, core_end
              FROM public.n4_extraction_windows
             WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
             ORDER BY ordinal
        """), params)).mappings().all()
        reservations = (await session.execute(text("""
            SELECT window_ordinal, status FROM public.n4_usage_reservations
             WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
        """), params)).mappings().all()
    return [dict(w) for w in windows], [dict(r) for r in reservations]


def _page_evidence(
    quote: str, source: str, refs: list[dict[str, Any]],
    spans: Sequence[_page_locator.PageSpan], *, revision_id: str,
    map_claimed: bool = False,
) -> tuple[int | None, str | None, str]:
    """(page_number, source_locator, page_verification_status) for a verified quote."""
    # Validate the persisted identity before any locator or no-map fallback.
    # Only an absent span on an identity-bound reference is an unanchored
    # literal; an explicitly malformed or mismatched span is not.
    digest = sha256(source.encode("utf-8")).hexdigest()
    normalized_quote = " ".join(quote.split())
    anchors: set[tuple[int, int]] = set()
    for ref in refs:
        if (
            not isinstance(ref, dict)
            or ref.get("source_kind") != "MODEL_SAFE_PROJECTION"
            or ref.get("evidence_status") != "EXACT_MODEL_SAFE_MATCH"
            or ref.get("source_sha256") != digest
            or ref.get("document_revision_id") != revision_id
            or not revision_id
        ):
            return None, None, "PAGE_UNRESOLVED"
        if "analysis_span" not in ref:
            continue
        span = ref["analysis_span"]
        if (
            not isinstance(span, list) or len(span) != 2
            or type(span[0]) is not int or type(span[1]) is not int
            or not 0 <= span[0] < span[1] <= len(source)
        ):
            return None, None, "PAGE_UNRESOLVED"
        excerpt = source[span[0]:span[1]]
        if " ".join(excerpt.split()) != normalized_quote:
            return None, None, "PAGE_UNRESOLVED"
        start = span[0] + len(excerpt) - len(excerpt.lstrip())
        end = span[1] - (len(excerpt) - len(excerpt.rstrip()))
        anchors.add((start, end))
    if len(anchors) > 1:
        return None, None, "PAGE_UNRESOLVED"
    if not spans:
        return None, None, (
            "PAGE_UNRESOLVED" if map_claimed else "PAGE_UNVERIFIED_NO_PAGE_MAP"
        )
    anchor = next(iter(anchors), None)
    near = anchor[0] if anchor is not None else None
    try:
        location = _page_locator.locate_quote_page(
            quote, source_text=source, page_spans=spans, near_offset=near,
        )
    except NotImplementedError:  # A9 locator not merged: no page claim
        return None, None, "PAGE_UNRESOLVED"
    if location is None:
        return None, None, "PAGE_UNRESOLVED"
    # A9 filters excluded pages before resolving matches. Do not let a
    # duplicate on a safe page silently replace the anchored occurrence
    # on an excluded page, or become unique merely by excluding its twin.
    if anchor is not None:
        if (location.start_offset, location.end_offset) != anchor:
            return None, None, "PAGE_UNRESOLVED"
    else:
        normalized_source = " ".join(source.split())
        normalized_quote = " ".join(quote.split())
        first = normalized_source.find(normalized_quote)
        if first < 0 or normalized_source.find(normalized_quote, first + 1) >= 0:
            return None, None, "PAGE_UNRESOLVED"
    locator = (
        f"p. {location.page_start}" if location.page_start == location.page_end
        else f"pp. {location.page_start}\u2013{location.page_end}"
    )
    return location.page_start, locator, "PAGE_LOCATED"


def _candidate_payload(
    claim: Mapping[str, Any], refs: list[dict[str, Any]], source: str,
    *, revision_id: str, page_spans: Sequence[Any] | None = None,
    map_claimed: bool = False,
) -> dict[str, Any]:
    if not isinstance(claim, dict) or not isinstance(refs, list) or not refs:
        raise N4GraphBridgeBlocked("N4 candidate lacks persisted claim and source reference")
    title = claim.get("title")
    reason = claim.get("risk_reason")
    if not isinstance(title, str) or not title.strip():
        raise N4GraphBridgeBlocked("N4 candidate title absent")
    if not isinstance(reason, str) or not reason.strip():
        raise N4GraphBridgeBlocked("N4 interpretation absent")
    reported_quote = claim.get("source_quote")
    verified_quote, verified_status = classify_quote(reported_quote, source)
    is_projection_match = bool(
        verified_quote and verified_status == "VERIFIED"
        and claim.get("source_evidence_status") == "EXACT_MODEL_SAFE_MATCH"
        and any(
            isinstance(ref, dict)
            and ref.get("source_kind") == "MODEL_SAFE_PROJECTION"
            and ref.get("evidence_status") == "EXACT_MODEL_SAFE_MATCH"
            for ref in refs
        )
    )
    quote = verified_quote if is_projection_match else None
    # "VERIFIED" here means an exact match in the N2 model-safe projection. It is
    # not a page-verified citation of the original document: that is reported
    # separately in ``page_verification_status``. When a page map exists but the
    # quote cannot be placed on a page, the quote is withheld, never VERIFIED.
    page_number: int | None = None
    locator: str | None = None
    page_status: str | None = None
    unresolved = False
    if quote:
        page_number, locator, page_status = _page_evidence(
            quote, source, refs, _page_spans(page_spans), revision_id=revision_id,
            map_claimed=map_claimed,
        )
        unresolved = page_status == "PAGE_UNRESOLVED"
        if unresolved:
            quote = None
    return {
        "title": title.strip(),
        "description": reason.strip(),
        "category": str(claim.get("category") or "general"),
        "severity": None,  # model has not established a verified legal severity
        "likelihood": None,
        "confidence": None,
        "clause_ref": str(claim.get("clause_ref") or "") or None,
        "source_quote": quote,
        "source_quote_status": (
            "VERIFIED" if quote
            else "PAGE_UNRESOLVED" if unresolved else "NOT_FOUND_IN_DOCUMENT"
        ),
        "source": quote,
        "page_number": page_number,
        "source_locator": locator,
        "page_verification_status": page_status,
    }


def _reference_proposals(
    register: Sequence[Mapping[str, Any]], *, source: str,
    source_sha256: str, revision_id: str, page_spans: Sequence[Any] | None = None,
    map_claimed: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Turn verified literal missing-external references into PROPOSED risks.

    Missing is relative to this analyzed source, not proof that the project
    has failed to supply the referenced attachment elsewhere. Never auto-trust.
    """
    risks: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    for entry in register:
        if entry.get("status") != "MISSING_EXTERNAL":
            continue
        quote = entry.get("source_quote")
        label = entry.get("label")
        if not isinstance(quote, str) or not quote or not isinstance(label, str):
            continue
        start = source.find(quote)
        if start < 0:  # No literal evidence: no manufactured proposal.
            continue
        key = sha256(
            (source_sha256 + ":" + label + ":" + quote).encode("utf-8")
        ).hexdigest()
        refs: list[dict[str, Any]] = [{
            "document_revision_id": revision_id,
            "source_sha256": source_sha256,
            "source_kind": "MODEL_SAFE_PROJECTION",
            "evidence_status": "EXACT_MODEL_SAFE_MATCH",
        }]
        # The register only proves a literal occurrence; it does not retain
        # a unique occurrence's offset. Never invent a disambiguating anchor.
        normalized_source = " ".join(source.split())
        normalized_quote = " ".join(quote.split())
        first = normalized_source.find(normalized_quote)
        if first >= 0 and normalized_source.find(normalized_quote, first + 1) < 0:
            refs[0]["analysis_span"] = [start, start + len(quote)]
        risk = _candidate_payload({
            "title": "Referenced document not provided",
            "risk_reason": (
                f"Reference to {label} is not resolved in the analyzed source. "
                "Verify whether the attachment was supplied separately."
            ),
            "category": "SCOPE",
            "clause_ref": label,
            "source_quote": quote,
            "source_evidence_status": "EXACT_MODEL_SAFE_MATCH",
        }, refs, source, revision_id=revision_id, page_spans=page_spans,
            map_claimed=map_claimed)
        risks.append(risk)
        provenance.append({
            "finding_key": key,
            "window_ordinal": None,
            "source_refs": refs,
            "source_keys": [key],
            "consolidation_trace": [],
            "detector": "literal_reference_register",
        })
    return risks, provenance


async def run_governed_n4_in_graph(state: Mapping[str, Any]) -> dict[str, Any]:
    """Run N4 against exact N2 source and return an existing graph-shaped state update."""
    if os.getenv("C2PRO_N4_GRAPH_LEDGER_ENABLED") != "1":
        raise N4GraphBridgeBlocked("N4 graph ledger is disabled")
    if os.getenv("C2PRO_AI_MOCK") == "1":
        raise N4GraphBridgeBlocked("N4 governed graph refuses mock model mode")
    authority, project_id, source_text = _identity(state)
    run_cap, per_call, chars, overlap = _limits()
    primary = os.getenv("C2PRO_N4_GRAPH_PRIMARY_PROVIDER", "anthropic")
    provider: N4WindowProvider
    if primary == "openai":
        from src.analysis.adapters.ai.n4_direct_openai_window_provider import (
            DirectOpenAIN4WindowProvider,
        )
        provider = DirectOpenAIN4WindowProvider(
            max_output_tokens=2048, reservation_usd=per_call,
        )
    elif primary == "anthropic":
        direct = os.getenv("C2PRO_DIRECT_FALLBACK_ENABLED") == "1"
        provider = AnthropicN4WindowProvider(
            wrapper=AnthropicWrapper(
                enable_cache=False, enable_retry=False,
                max_tokens_limit=2048, timeout_seconds=75,
            ),
            tier=ModelTier.STANDARD,
            max_output_tokens=2048,
            fallback_reservation_usd=per_call if direct else None,
        )
    else:
        raise N4GraphBridgeBlocked("Unapproved N4 primary provider")
    runner = N4IncrementalRunner(
        session_factory=get_session_factory(),
        provider=provider,
        run_cap_usd=run_cap,
        per_window_reservation_usd=per_call,
        period_key=datetime.now(UTC).strftime("%Y-%m"),
        max_context_chars=chars,
        overlap_chars=overlap,
        enabled=True,
        inherit_approved_scopes=_uat_inherited_scopes(authority.tenant_id),
    )
    outcome = await runner.run(
        authority=authority, project_id=project_id,
        model_safe_text=source_text, n2_projection_attested=True,
    )
    source_sha256 = sha256(source_text.encode("utf-8")).hexdigest()
    spans, map_claimed = _a11_a9_page_map(state)
    # Always reconcile the persisted ledger, including on the fast COMPLETE
    # path. Runner counters alone cannot prove that every ordinal still exists.
    windows, reservations = await _load_run_ledger(
        authority.tenant_id, outcome.run_id,
    )
    coverage = assess_n4_run(
        outcome=outcome, windows=windows, reservations=reservations,
        source_sha256=source_sha256, page_spans=spans,
    )
    if outcome.status == "COMPLETE" and (
        coverage["status"] != N4CoverageStatus.COMPLETE.value
        or outcome.settled_receipt_windows != outcome.total_windows
        or outcome.persisted_result_windows != outcome.total_windows
    ):
        raise N4RunIncomplete(
            run_id=outcome.run_id, status=outcome.status,
            examined_windows=outcome.examined_windows,
            total_windows=outcome.total_windows,
            persisted_result_windows=outcome.persisted_result_windows,
            blocked_result_windows=outcome.blocked_result_windows,
            stopped_reason="INCONSISTENT_COMPLETE_LEDGER",
            source_sha256=source_sha256,
        )

    # Tenant RLS and an exact run_id: never import another document's candidates.
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": str(authority.tenant_id)},
        )
        params = {"tenant": str(authority.tenant_id), "run": str(outcome.run_id)}
        rows = (await session.execute(text("""
            SELECT f.finding_key, f.claim, f.source_refs, f.window_ordinal
              FROM public.n4_candidate_findings f
             WHERE f.tenant_id = CAST(:tenant AS uuid)
               AND f.run_id = CAST(:run AS uuid)
             ORDER BY f.window_ordinal, f.finding_key
        """), params)).mappings().all()
        unresolved_rows = (await session.execute(text("""
            SELECT unresolved_refs FROM public.n4_extraction_windows
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND run_id = CAST(:run AS uuid)
             ORDER BY ordinal
        """), params)).scalars().all()
        unresolved_refs = [
            ref for entry in unresolved_rows if isinstance(entry, list)
            for ref in entry if isinstance(ref, str)
        ]

    candidates: list[dict[str, Any]] = []
    for row in rows:
        payload = _candidate_payload(
            row["claim"], row["source_refs"], source_text,
            revision_id=str(authority.revision_id), page_spans=spans,
            map_claimed=map_claimed,
        )
        candidates.append({
            **payload,
            "finding_key": row["finding_key"],
            "window_ordinal": int(row["window_ordinal"]),
            "source_refs": row["source_refs"],
        })
    merged = consolidate_candidates(candidates)
    _trace_keys = {"finding_key", "window_ordinal", "source_refs", "source_keys",
                   "consolidation_trace"}
    risks = [{k: v for k, v in m.items() if k not in _trace_keys} for m in merged]
    provenance = [{
        "finding_key": m["finding_key"],
        "window_ordinal": m["window_ordinal"],
        "source_refs": m["source_refs"],
        "source_keys": m["source_keys"],
        "consolidation_trace": m["consolidation_trace"],
    } for m in merged]
    register = build_reference_register(source_text, [
        {"finding_key": m["finding_key"], "source_quote": m.get("source_quote")}
        for m in merged
    ], unresolved_refs=unresolved_refs)
    reference_risks, reference_provenance = _reference_proposals(
        register, source=source_text, source_sha256=source_sha256,
        revision_id=str(authority.revision_id), page_spans=spans,
        map_claimed=map_claimed,
    )
    risks.extend(reference_risks)
    provenance.extend(reference_provenance)
    return {
        "extracted_risks": risks,
        "risk_extraction_outcome": (
            "PROPOSED_NOT_VERIFIED" if risks else "NO_FINDINGS_UNASSESSED"
        ),
        "risk_extraction_error_type": None,
        "confidence_score": None,
        "human_approval_required": True,
        "n4_incremental_run_id": str(outcome.run_id),
        "n4_incremental_window_coverage": {
            "examined": coverage["examined_windows"],
            "total": outcome.total_windows,
            "source_kind": "MODEL_SAFE_PROJECTION",
            "original_document_completeness_certified": False,
            "semantic_recall_certified": False,
        },
        "n4_candidate_provenance": provenance,
        "n4_coverage": coverage,
        "n4_reference_register": register,
    }
