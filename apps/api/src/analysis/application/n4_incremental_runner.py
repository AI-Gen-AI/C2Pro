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
    N4LedgerError,
    account_call,
    block_window,
    commit_window,
    create_run,
    progress,
    reserve_call,
    retryable_windows,
    window_statuses,
)
from src.analysis.domain.n4_compact_window_response import (
    N4WindowContractError,
    parse_n4_window_output,
)
from src.analysis.domain.n4_failure_kinds import (
    N4CoverageStatus,
    derive_n4_coverage_status,
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
    # prompt_version is checked fail-closed at runtime; the legacy direct
    # adapter remains a separate owner until its v1 attribute is published.

    async def generate(
        self, *, window: N4SourceWindow, tenant_id: UUID, request_id: str,
        attempt: int = 1,
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
    # JV1-A1 contract: derived in application code (never a DB status), see
    # derive_n4_coverage_status. None until the runner computes it (A3).
    coverage_status: N4CoverageStatus | None = None
    gap_windows: tuple[int, ...] = ()


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
        inherit_approved_scopes: bool = False,
        max_context_chars: int = 12_000,
        overlap_chars: int = 400,
        max_attempts: int = 3,
    ) -> None:
        self.sessions = session_factory
        self.provider = provider
        self.run_cap = Decimal(str(run_cap_usd))
        self.call_reservation = Decimal(str(per_window_reservation_usd))
        configured_fallback_hold = getattr(provider, "fallback_reservation_usd", None)
        if configured_fallback_hold is not None and (
            configured_fallback_hold != self.call_reservation
        ):
            raise ValueError("N4 fallback escrow must equal the actual per-window reservation")
        self.period_key = period_key
        self.enabled = enabled
        self.inherit_approved_scopes = inherit_approved_scopes
        self.context_limit = max_context_chars
        self.overlap = overlap_chars
        if type(max_attempts) is not int or not 1 <= max_attempts <= 10:
            raise ValueError("N4 max_attempts must be an integer in [1,10]")
        self.max_attempts = max_attempts
        version = getattr(provider, "prompt_version", None)
        if (
            not isinstance(version, str)
            or not version.strip()
            or version != version.strip()
            or len(version) > 128
        ):
            raise ValueError("provider.prompt_version must be pinned before reservation")
        self.prompt_version = version
        self.model_id = provider.model_name
        config = {
            "prompt": version,
            "model": self.model_id,
            "window_chars": self.context_limit,
            "overlap": self.overlap,
        }
        self.attempt_escrow_enabled = getattr(provider, "attempt_escrow_enabled", False) is True
        self._attempt_escrow_policy = None
        if self.attempt_escrow_enabled:
            self._attempt_escrow_policy = json.dumps(
                provider.escrow_policy(), sort_keys=True, separators=(",", ":"),
            )
            config["attempt_escrow"] = json.loads(self._attempt_escrow_policy)
        self.config_sha256 = sha256(json.dumps(
            config, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        if (
            not self.run_cap.is_finite() or self.run_cap <= 0
            or not self.call_reservation.is_finite()
            or self.call_reservation <= 0
            or self.call_reservation > self.run_cap
            or not self.model_id.strip()
        ):
            raise ValueError("explicit positive run/call caps and pinned model required")

    def _reservation_for_attempt(self, window: N4SourceWindow, attempt: int) -> Decimal:
        """A5 quotes are per attempt; legacy providers retain their frozen amount."""
        if not self.attempt_escrow_enabled:
            return self.call_reservation
        try:
            policy = json.dumps(self.provider.escrow_policy(), sort_keys=True, separators=(",", ":"))
            if policy != self._attempt_escrow_policy:
                raise ValueError("N4 pinned escrow policy changed")
            amount = self.provider.reservation_for_attempt(
                window, attempt=attempt, ceiling=self.call_reservation,
            )
            if (not isinstance(amount, Decimal) or not amount.is_finite()
                    or amount <= 0 or amount > self.call_reservation):
                raise ValueError("N4 attempt exceeds committed call ceiling")
            return amount
        except (ValueError, ArithmeticError) as exc:
            raise N4BudgetError("N4 attempt escrow unavailable") from exc

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
            gap_rows = (await session.execute(text("""
                SELECT ordinal FROM public.n4_extraction_windows
                 WHERE tenant_id = CAST(:tenant AS uuid)
                   AND run_id = CAST(:run AS uuid) AND status = 'BLOCKED'
                 ORDER BY ordinal
            """), {
                "tenant": str(authority.tenant_id), "run": str(run_id),
            })).scalars().all()
            gaps = tuple(int(ordinal) for ordinal in gap_rows)
            return N4RunOutcome(
                run_id=run_id, status=str(current["status"]),
                examined_windows=int(current["examined_windows"]),
                total_windows=int(current["total_windows"]),
                stopped_reason=stopped_reason,
                settled_receipt_windows=int(evidence["settled_windows"]),
                persisted_result_windows=int(evidence["persisted_windows"]),
                blocked_result_windows=int(evidence["blocked_results"]),
                coverage_status=derive_n4_coverage_status(
                    total_windows=int(current["total_windows"]),
                    examined_windows=int(current["examined_windows"]),
                    gap_windows=gaps,
                ),
                gap_windows=gaps,
            )

    async def _account_and_block(
        self, *, authority: ProcessingAuthority, run_id: UUID,
        ordinal: int, reservation_id: UUID, cost: Decimal | None,
        reason: str, actual_model_name: str | None = None,
        actual_provider: str | None = None,
        input_tokens: int | None = None, output_tokens: int | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        async with self.sessions() as session, session.begin():
            await self._tenant_context(session, authority.tenant_id)
            await account_call(
                session, authority=authority,
                reservation_id=reservation_id, billed_usd=cost,
                actual_model_name=actual_model_name,
                actual_provider=actual_provider,
                input_tokens=input_tokens, output_tokens=output_tokens,
                provider_request_id=provider_request_id,
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
        # A mutable provider cannot switch prompt/model after a runner was
        # initialized; a new runner/config digest is mandatory for v2.
        if (
            getattr(self.provider, "prompt_version", None) != self.prompt_version
            or self.provider.model_name != self.model_id
        ):
            raise ValueError("N4 provider identity changed; rebuild pinned runner")

        windows = plan_n4_source_windows(
            model_safe_text, revision_id=str(authority.revision_id),
            max_context_chars=self.context_limit,
            overlap_chars=self.overlap,
        )
        config_digest = self.config_sha256
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
                    status = statuses.get(window.ordinal)
                    if set(statuses) != {w.ordinal for w in windows}:
                        raise N4LedgerError("source window ordinals missing on resume")
                    if status == "EXAMINED":
                        continue
                    if status not in ("PENDING", "BLOCKED"):
                        raise N4LedgerError("invalid N4 window state on resume")
                    # Count every durable attempt, including canceled entries,
                    # so each paid retry has a distinct, stable idempotency key.
                    prior = (await session.execute(text("""
                        SELECT status FROM public.n4_usage_reservations
                         WHERE tenant_id = CAST(:tenant AS uuid)
                           AND run_id = CAST(:run AS uuid)
                           AND window_ordinal = :ordinal
                         ORDER BY created_at, reservation_id
                    """), {
                        "tenant": str(authority.tenant_id),
                        "run": str(run_id), "ordinal": window.ordinal,
                    })).scalars().all()
                    if status == "BLOCKED":
                        retryable = await retryable_windows(
                            session, tenant_id=authority.tenant_id,
                            run_id=run_id, max_attempts=self.max_attempts,
                        )
                        if window.ordinal not in retryable:
                            if any(str(s) in ("UNKNOWN", "RESERVED") for s in prior):
                                return await self._outcome(
                                    authority, run_id,
                                    "OPEN_LIABILITY_REQUIRES_RECONCILIATION",
                                )
                            # Terminal gap, or bounded retries exhausted.
                            # Preserve BLOCKED rather than claiming coverage.
                            continue
                    elif prior:
                        # PENDING + any old attempt (even SETTLED) means a
                        # crash/interleaving may have occurred before findings.
                        # Never charge or send again without a deliberate
                        # BLOCKED transition and a settled ledger entry.
                        return await self._outcome(
                            authority, run_id,
                            "EXISTING_RESERVATION_REQUIRES_RECONCILIATION",
                        )
                    attempt_no = len(prior) + 1
                    # Preserve the original A2 first-attempt key exactly.
                    # Different paid attempts need distinct keys; if the
                    # current one is already RESERVED, we stop above.
                    attempt_suffix = "" if attempt_no == 1 else f":{attempt_no}"
                    call_key = sha256(
                        f"n4:{run_id}:{window.ordinal}:{window.context_sha256}:"
                        f"{self.model_id}{attempt_suffix}".encode()
                    ).hexdigest()
                    attempt_reservation = self._reservation_for_attempt(window, attempt_no)
                    reserved = await reserve_call(
                        session, authority=authority,
                        run_id=run_id, window_ordinal=window.ordinal,
                        idempotency_key=call_key,
                        provider_model=self.provider.model_name,
                        estimated_max_usd=attempt_reservation,
                        period_key=self.period_key,
                        inherit_approved_scopes=self.inherit_approved_scopes,
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
                if self.attempt_escrow_enabled:
                    response = await self.provider.generate(
                        window=window, tenant_id=authority.tenant_id,
                        request_id=str(reserved.reservation_id), attempt=attempt_no,
                        reservation_usd=attempt_reservation,
                    )
                elif attempt_no == 1:
                    # The frozen interface defaults attempt to 1. Keep the
                    # first-call compatibility of older providers; explicit
                    # paid retries require the v2-capable attempt argument.
                    response = await self.provider.generate(
                        window=window, tenant_id=authority.tenant_id,
                        request_id=str(reserved.reservation_id),
                    )
                else:
                    response = await self.provider.generate(
                        window=window, tenant_id=authority.tenant_id,
                        request_id=str(reserved.reservation_id), attempt=attempt_no,
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
                billable_model = getattr(exc, "model", None)
                billable_provider = (
                    getattr(self.provider, "provider_name", "anthropic")
                    if billable_model == self.provider.model_name
                    else next(
                        (
                            route.provider
                            for route in getattr(self.provider, "fallback_routes", ())
                            if route.model == billable_model
                        ),
                        None,
                    )
                )
                # An ambiguous billable amount with unknown model identity
                # remains in UNKNOWN, not falsely attributed to Anthropic.
                if billable_provider is None:
                    cost = None
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="PROVIDER_RESULT_UNCERTAIN",
                    actual_model_name=billable_model if billable_provider else None,
                    actual_provider=billable_provider,
                    input_tokens=getattr(exc, "input_tokens", None),
                    output_tokens=getattr(exc, "output_tokens", None),
                    provider_request_id=getattr(exc, "provider_request_id", None),
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

            allowed_fallback_models: frozenset[str] = getattr(self.provider, "approved_fallback_models", frozenset())
            if response.model_used != self.provider.model_name and (
                response.model_used not in allowed_fallback_models
            ):
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="PROVIDER_MODEL_MISMATCH",
                )
                return await self._outcome(
                    authority, run_id, "PROVIDER_MODEL_MISMATCH",
                )
            actual_provider = (
                getattr(self.provider, "provider_name", "anthropic")
                if response.model_used == self.provider.model_name
                else next(
                    (
                        route.provider
                        for route in getattr(self.provider, "fallback_routes", ())
                        if route.model == response.model_used
                    ),
                    None,
                )
            )
            if actual_provider not in ("anthropic", "openai", "gemini"):
                await self._account_and_block(
                    authority=authority, run_id=run_id,
                    ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id,
                    cost=cost, reason="UNVERIFIED_PROVIDER_IDENTITY",
                )
                return await self._outcome(authority, run_id, "UNVERIFIED_PROVIDER_IDENTITY")
            if self.attempt_escrow_enabled and cost > attempt_reservation:
                # A known overrun is a liability, not UNKNOWN or a valid result.
                await self._account_and_block(
                    authority=authority, run_id=run_id, ordinal=window.ordinal,
                    reservation_id=reserved.reservation_id, cost=cost,
                    reason="PROVIDER_RESULT_UNCERTAIN",
                    actual_model_name=response.model_used, actual_provider=actual_provider,
                    input_tokens=response.input_tokens, output_tokens=response.output_tokens,
                    provider_request_id=response.provider_request_id,
                )
                return await self._outcome(authority, run_id, "ATTEMPT_ESCROW_EXCEEDED")
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
                    actual_model_name=response.model_used,
                    actual_provider=actual_provider,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
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
                    actual_model_name=response.model_used,
                    actual_provider=actual_provider,
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
