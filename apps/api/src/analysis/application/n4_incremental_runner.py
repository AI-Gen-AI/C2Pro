"""Governed N4 window execution, no changes to legacy N1–N17 (V4 WBS 2.x).

Execution is intentionally opt-in. The caller must attest that source text is
the immutable N2-safe projection, own a valid ANALYSIS processing authority,
and provision tenant/project/document budget caps outside this service.

Transactions: reserve + commit BEFORE provider; provider call WITHOUT DB
locks; settle + findings COMMIT together. A replay of a reserved request
never triggers a second network call. Partial or unknown results remain
reviewable but never masquerade as source coverage or approved risks.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.analysis.adapters.persistence.n4_incremental_store import (
    N4BudgetError,
    account_call,
    block_window,
    commit_window,
    create_run,
    progress,
    reserve_call,
    window_statuses,
)
from src.analysis.domain.n4_compact_window_response import (
    N4WindowContractError,
    parse_n4_window_output,
)
from src.analysis.domain.n4_source_windows import (
    N4SourceWindow,
    plan_n4_source_windows,
)
from src.core.processing_authority import ProcessingAuthority


@dataclass(frozen=True)
class N4ProviderReceipt:
    content: str
    model_used: str
    reported_cost_usd: str | Decimal | None
    input_tokens: int
    output_tokens: int
    provider_request_id: str | None = None


class N4WindowProvider(Protocol):
    model_name: str

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
    ) -> N4ProviderReceipt: ...


@dataclass(frozen=True)
class N4RunOutcome:
    run_id: UUID
    status: str
    examined_windows: int
    total_windows: int
    stopped_reason: str | None = None
    # Financially settled is not the same as fully examined or HITL approved.
    settled_receipt_windows: int = 0
    persisted_result_windows: int = 0
    blocked_result_windows: int = 0


class N4IncrementalRunner:
    """Minimum runnable S2 seam: safe resume and a transactional spend ledger.

    This class is not plugged into the production graph, and should not
    override legacy N4 until FRONT-A contracts and full-project UAT pass.
    """

    def __init__(
        self, *, session_factory: async_sessionmaker[AsyncSession],
        provider: N4WindowProvider,
        run_cap_usd: Decimal | str,
        per_window_reservation_usd: Decimal | str,
        period_key: str,
        enabled: bool = False,
        max_context_chars: int = 12_000,
        overlap_chars: int = 400,
    ) -> None:
        self.sessions = session_factory
        self.provider = provider
        self.run_cap = Decimal(str(run_cap_usd))
        self.call_reservation = Decimal(str(per_window_reservation_usd))
        self.period_key = period_key
        self.enabled = enabled
        self.context_limit = max_context_chars
        self.overlap = overlap_chars
        if (
            not self.run_cap.is_finite() or self.run_cap <= 0
            or not self.call_reservation.is_finite()
            or self.call_reservation <= 0
            or self.call_reservation > self.run_cap
            or not provider.model_name.strip()
        ):
            raise ValueError("explicit positive run/call caps and pinned model required")

    @staticmethod
    async def _tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
        await session.execute(
            text("SELECT set_config('app.current_tenant', :tenant, true)"),
            {"tenant": str(tenant_id)},
        )

    async def _outcome(
        self, authority: ProcessingAuthority, run_id: UUID,
        stopped_reason: str | None = None,
    ) -> N4RunOutcome:
        async with self.sessions() as session, session.begin():
            await self._tenant_context(session, authority.tenant_id)
            current = await progress(
                session, tenant_id=authority.tenant_id, run_id=run_id,
            )
            # BLOCKED can represent a parsed, settled result awaiting
            # external references. It can also represent failed parsing
            # without a persisted result. Neither implies clean coverage.
            evidence = (await session.execute(text("""
                SELECT
                  count(*) FILTER (WHERE settled) AS settled_windows,
                  count(*) FILTER (
                    WHERE settled AND committed_at IS NOT NULL
                      AND findings_sha256 IS NOT NULL
                  ) AS persisted_windows,
                  count(*) FILTER (
                    WHERE status='BLOCKED' AND settled
                      AND committed_at IS NOT NULL
                      AND findings_sha256 IS NOT NULL
                  ) AS blocked_results
                FROM (
                  SELECT w.status, w.committed_at, w.findings_sha256,
                         EXISTS (
                           SELECT 1 FROM public.n4_usage_reservations r
                           WHERE r.tenant_id = w.tenant_id
                             AND r.run_id = w.run_id
                             AND r.window_ordinal = w.ordinal
                             AND r.status = 'SETTLED'
                         ) AS settled
                  FROM public.n4_extraction_windows w
                  WHERE w.tenant_id = CAST(:tenant AS uuid)
                    AND w.run_id = CAST(:run AS uuid)
                ) AS window_receipts
            """), {
                "tenant": str(authority.tenant_id),
                "run": str(run_id),
            })).mappings().one()
            return N4RunOutcome(
                run_id=run_id, status=str(current["status"]),
                examined_windows=int(current["examined_windows"]),
                total_windows=int(current["total_windows"]),
                stopped_reason=stopped_reason,
                settled_receipt_windows=int(evidence["settled_windows"]),
                persisted_result_windows=int(evidence["persisted_windows"]),
                blocked_result_windows=int(evidence["blocked_results"]),
            )

    async def _account_and_block(
        self, *, authority: ProcessingAuthority, run_id: UUID,
        ordinal: int, reservation_id: UUID, cost: Decimal | None,
        reason: str,
    ) -> None:
        async with self.sessions() as session, session.begin():
            await self._tenant_context(session, authority.tenant_id)
            await account_call(
                session, authority=authority,
                reservation_id=reservation_id, billed_usd=cost,
            )
            await block_window(
                session, authority=authority, run_id=run_id,
                window_ordinal=ordinal, reason=reason,
            )

    async def run(
        self, *, authority: ProcessingAuthority, project_id: UUID,
        model_safe_text: str, n2_projection_attested: bool,
    ) -> N4RunOutcome:
        """Execute all source windows sequentially with durable per-call costs.

        Any provider crash after reserving blocks replay without a duplicate
        call; separate reconciliation can reclassify a recorded liability.
        A returned `COMPLETE` means the N2 projection's windows were visited,
        not independent completeness/recall, original-PDF attestation or HITL.
        """
        if not self.enabled:
            raise PermissionError("N4 V4 provider calls are disabled by default")
        if not n2_projection_attested:
            raise PermissionError("N2-safe source provenance is mandatory")
        if authority.revision_id is None:
            raise ValueError("document revision must be pinned before N4")

        windows = plan_n4_source_windows(
            model_safe_text, revision_id=str(authority.revision_id),
            max_context_chars=self.context_limit,
            overlap_chars=self.overlap,
        )
        config = {
            "prompt": "n4-compact-window-v1",
            "model": self.provider.model_name,
            "window_chars": self.context_limit,
            "overlap": self.overlap,
        }
        config_digest = sha256(json.dumps(
            config, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        async with self.sessions() as session, session.begin():
            await self._tenant_context(session, authority.tenant_id)
            run_id = await create_run(
                session, authority=authority, project_id=project_id,
                config_sha256=config_digest, windows=windows,
                budget_cap_usd=self.run_cap,
            )

        for window in windows:
            # All budget failures are decided before any network call.
            try:
                async with self.sessions() as session, session.begin():
                    await self._tenant_context(session, authority.tenant_id)
                    statuses = await window_statuses(
                        session, tenant_id=authority.tenant_id, run_id=run_id,
                    )
                    if statuses.get(window.ordinal) in ("EXAMINED", "BLOCKED"):
                        continue
                    # Stable across retries/restarts. Replay MUST NOT hit provider.
                    call_key = sha256(
                        f"n4:{run_id}:{window.ordinal}:{window.context_sha256}:"
                        f"{self.provider.model_name}".encode()
                    ).hexdigest()
                    reserved = await reserve_call(
                        session, authority=authority,
                        run_id=run_id, window_ordinal=window.ordinal,
                        idempotency_key=call_key,
                        provider_model=self.provider.model_name,
                        estimated_max_usd=self.call_reservation,
                        period_key=self.period_key,
                    )
            except N4BudgetError as exc:
                # The denied transaction rolls back before the BLOCKED state
                # is written. This preserves all already examined windows.
                async with self.sessions() as session, session.begin():
                    await self._tenant_context(session, authority.tenant_id)
                    await block_window(
                        session, authority=authority, run_id=run_id,
                        window_ordinal=window.ordinal,
                        reason="BUDGET_OR_RESERVATION_UNAVAILABLE",
                    )
                return await self._outcome(
                    authority, run_id, type(exc).__name__,
                )
            if reserved.replay:
                # This reservation might be IN FLIGHT in a different worker.
                # No second provider call AND do not mark the shared window
                # BLOCKED: the first worker must retain the right to finish.
                # A crashed run will remain reserved pending reconciliation.
                return await self._outcome(
                    authority, run_id, "EXISTING_RESERVATION_REQUIRES_RECONCILIATION",
                )
            try:
                response = await self.provider.generate(
                    window=window, tenant_id=authority.tenant_id,
                    request_id=str(reserved.reservation_id),
                )
            except Exception as exc:
                # Partial provider exceptions may carry a billable usage
                # estimate. Missing usage is UNKNOWN, not zero.
                reported = getattr(exc, "cost_usd", None)
                try:
                    cost = Decimal(str(reported)) if reported is not None else None
                    if cost is not None and (
                        not cost.is_finite() or cost < 0
                    ):
                        cost = None
                except (InvalidOperation, ValueError, TypeError):
                    cost = None
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="PROVIDER_RESULT_UNCERTAIN",
                )
                return await self._outcome(
                    authority, run_id, "PROVIDER_RESULT_UNCERTAIN",
                )

            try:
                cost = (
                    Decimal(str(response.reported_cost_usd))
                    if response.reported_cost_usd is not None else None
                )
                if cost is None or not cost.is_finite() or cost < 0:
                    raise ValueError("missing or invalid provider usage")
            except (InvalidOperation, TypeError, ValueError):
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=None, reason="USAGE_UNAVAILABLE",
                )
                return await self._outcome(authority, run_id, "USAGE_UNAVAILABLE")

            if response.model_used != self.provider.model_name:
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="PROVIDER_MODEL_MISMATCH",
                )
                return await self._outcome(
                    authority, run_id, "PROVIDER_MODEL_MISMATCH",
                )
            try:
                parsed = parse_n4_window_output(
                    response.content, window=window,
                )
            except N4WindowContractError:
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="INVALID_PROVIDER_ENVELOPE",
                )
                return await self._outcome(
                    authority, run_id, "INVALID_PROVIDER_ENVELOPE",
                )

            async with self.sessions() as session, session.begin():
                await self._tenant_context(session, authority.tenant_id)
                # One DB transaction reconciles the billable response and
                # persists every proposed finding. No N12/HITL authority.
                await account_call(
                    session, authority=authority,
                    reservation_id=reserved.reservation_id, billed_usd=cost,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    provider_request_id=response.provider_request_id,
                )
                await commit_window(
                    session, authority=authority, run_id=run_id,
                    window_ordinal=window.ordinal,
                    findings=list(parsed.proposed_findings),
                    unresolved_refs=parsed.outstanding_references,
                    incomplete_reason=(
                        None if parsed.reported_examined
                        else "MODEL_DID_NOT_EXAMINE_WINDOW"
                    ),
                )

        return await self._outcome(authority, run_id)
