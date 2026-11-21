"""Opt-in N4 graph bridge: durable multi-window candidates into existing HITL graph.

No provider calls occur unless every gate passes: N2-safe source, active fenced
ANALYSIS authority, tenant/project/document/revision identity, explicit cost
limits and pre-existing tenant/project/document budget buckets. The runner
holds the money transactionally before each model call. A model-safe quote
match is NOT proof of original-PDF source or semantic/legal correctness.
"""
from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import text

from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.application.n4_incremental_runner import N4IncrementalRunner
from src.analysis.domain.ai_source_text import llm_document_text
from src.analysis.domain.risk_provenance import classify_quote
from src.core.ai.anthropic_wrapper import AnthropicWrapper
from src.core.ai.model_router import ModelTier
from src.core.database import get_session_factory
from src.core.processing_authority import ProcessingStage, current_authority
from src.documents.application.n4_source_identity import is_n4_source_identity_valid


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


def _candidate_payload(claim: Mapping[str, Any], refs: list, source: str) -> dict[str, Any]:
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
    return {
        "title": title.strip(),
        "description": reason.strip(),
        "category": str(claim.get("category") or "general"),
        "severity": None,  # model has not established a verified legal severity
        "likelihood": None,
        "confidence": None,
        "clause_ref": str(claim.get("clause_ref") or "") or None,
        "source_quote": quote,
        "source_quote_status": "VERIFIED" if quote else "NOT_FOUND_IN_DOCUMENT",
        "source": quote,
    }


async def run_governed_n4_in_graph(state: Mapping[str, Any]) -> dict[str, Any]:
    """Run N4 against exact N2 source and return an existing graph-shaped state update."""
    if os.getenv("C2PRO_N4_GRAPH_LEDGER_ENABLED") != "1":
        raise N4GraphBridgeBlocked("N4 graph ledger is disabled")
    if os.getenv("C2PRO_AI_MOCK") == "1":
        raise N4GraphBridgeBlocked("N4 governed graph refuses mock model mode")
    authority, project_id, source_text = _identity(state)
    run_cap, per_call, chars, overlap = _limits()
    primary = os.getenv("C2PRO_N4_GRAPH_PRIMARY_PROVIDER", "anthropic")
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
    if outcome.status != "COMPLETE" or (
        outcome.examined_windows != outcome.total_windows
        or outcome.settled_receipt_windows != outcome.total_windows
        or outcome.persisted_result_windows != outcome.total_windows
    ):
        raise N4RunIncomplete(
            run_id=outcome.run_id,
            status=outcome.status,
            examined_windows=outcome.examined_windows,
            total_windows=outcome.total_windows,
            persisted_result_windows=outcome.persisted_result_windows,
            blocked_result_windows=outcome.blocked_result_windows,
            stopped_reason=outcome.stopped_reason,
            source_sha256=sha256(source_text.encode("utf-8")).hexdigest(),
        )

    # Tenant RLS and an exact run_id: never import another document's candidates.
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": str(authority.tenant_id)},
        )
        rows = (await session.execute(text("""
            SELECT f.finding_key, f.claim, f.source_refs, f.window_ordinal
              FROM public.n4_candidate_findings f
             WHERE f.tenant_id = CAST(:tenant AS uuid)
               AND f.run_id = CAST(:run AS uuid)
             ORDER BY f.window_ordinal, f.finding_key
        """), {"tenant": str(authority.tenant_id), "run": str(outcome.run_id)})).mappings().all()

    risks = []
    provenance = []
    for row in rows:
        risks.append(_candidate_payload(row["claim"], row["source_refs"], source_text))
        provenance.append({
            "finding_key": row["finding_key"],
            "window_ordinal": int(row["window_ordinal"]),
            "source_refs": row["source_refs"],
        })
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
            "examined": outcome.examined_windows,
            "total": outcome.total_windows,
            "source_kind": "MODEL_SAFE_PROJECTION",
            "original_document_completeness_certified": False,
            "semantic_recall_certified": False,
        },
        "n4_candidate_provenance": provenance,
    }
