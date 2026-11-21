"""N4 V4 incremental ledger and budget accounting (WBS 2.2, 2.5, 2.6).

Callers own the PostgreSQL transaction; never call this adapter from a
side-effecting provider retry without a persisted reservation. The ledger
records PROPOSED findings, not trusted or human-approved decisions.

Lock ordering: processing-authority row -> run row -> sorted budget buckets ->
usage reservation / window. This is intentionally separate from HITL V3.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.n4_source_windows import N4SourceWindow
from src.core.processing_authority import (
    ProcessingAuthority,
    ProcessingStage,
    verify_in_transaction,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_KINDS = frozenset({"TENANT", "PROJECT", "DOCUMENT", "RUN"})
_SCALE = Decimal("0.000001")


class N4LedgerError(RuntimeError):
    """A ledger invariant failed. Do not treat this as zero findings."""


class N4BudgetError(N4LedgerError):
    """Budget was missing, exhausted or usage needs reconciliation."""


class N4BudgetNotConfigured(N4BudgetError):
    """A required scope has no explicit cap; never assume infinite credit."""


class N4BudgetExceeded(N4BudgetError):
    """A reservation would exceed at least one spending limit."""


class N4PriorRunReconciliationRequired(N4BudgetError):
    """Prior N4 usage requires reconciliation; a new paid run is forbidden."""


@dataclass(frozen=True)
class N4Reservation:
    reservation_id: UUID
    status: str
    replay: bool


def _amount(value: Decimal | str | int) -> Decimal:
    try:
        number = Decimal(str(value))
        if not number.is_finite() or number < 0:
            raise ValueError("money must be a finite nonnegative amount")
        return number.quantize(_SCALE)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("invalid financial amount") from exc


def _uuid(value: UUID | str | None) -> str:
    return str(UUID(str(value)))


async def _verify(session: AsyncSession, authority: ProcessingAuthority) -> None:
    if authority.stage is not ProcessingStage.ANALYSIS or not authority.revision_id:
        raise N4LedgerError("N4 requires a pinned ANALYSIS processing authority")
    # Explicit verify, never fence_current() (which is a no-op when unbound).
    await verify_in_transaction(session, authority)


async def _locked_tenant_budget(
    session: AsyncSession, *, tenant_id: UUID, for_settlement: bool = False,
) -> Decimal:
    """Tenant-row escrow shared with the legacy spend counter.

    N4 reservations increment tenants.ai_spend_reserved_usd and settlement
    transfers the charge to tenants.ai_spend_current. Both are protected by
    this row lock and by the SAME transaction as the N4 usage receipt. Legacy
    check_budget_availability sees N4 pending use, but legacy preflight itself
    is not an atomic reservation and remains a separately scoped gap.
    """
    row = (await session.execute(text("""
        SELECT ai_budget_monthly, ai_spend_current, ai_spend_reserved_usd,
               ai_spend_last_reset, is_active
          FROM public.tenants WHERE id = CAST(:tenant AS uuid)
         FOR UPDATE
    """), {"tenant": _uuid(tenant_id)})).mappings().one_or_none()
    if row is None:
        raise N4BudgetNotConfigured("tenant budget record not found")
    cap = Decimal(str(row["ai_budget_monthly"]))
    spent = Decimal(str(row["ai_spend_current"]))
    reserved = Decimal(str(row["ai_spend_reserved_usd"]))
    if any(not x.is_finite() for x in (cap, spent, reserved)) or spent < 0 or reserved < 0:
        raise N4BudgetNotConfigured("tenant budget is missing or invalid")
    if not for_settlement and (row["is_active"] is not True or cap <= 0):
        raise N4BudgetError("inactive tenant or unavailable global budget")
    if not for_settlement:
        db_time = await session.scalar(text(
            "SELECT clock_timestamp() AT TIME ZONE 'UTC'"
        ))
        last_reset = row["ai_spend_last_reset"]
        if last_reset is None or (
            last_reset.year, last_reset.month
        ) != (db_time.year, db_time.month):
            # The legacy month reset is performed BEFORE committing a new
            # N4 reservation. Pending liabilities remain reserved across
            # a month change; neither an UNKNOWN charge nor an old hold is
            # silently forgiven. Future legacy checks see current reset.
            await session.execute(text("""
                UPDATE public.tenants
                   SET ai_spend_current = 0,
                       ai_spend_last_reset = :reset_at
                 WHERE id = CAST(:tenant AS uuid)
            """), {
                "tenant": _uuid(tenant_id), "reset_at": db_time,
            })
            spent = Decimal("0")
    return cap - spent - reserved


async def _locked_run(
    session: AsyncSession, *, tenant_id: UUID, run_id: UUID,
    authority: ProcessingAuthority,
) -> dict[str, Any]:
    row = (await session.execute(text("""
        SELECT run_id, tenant_id, project_id, document_id, document_revision_id,
               generation, fencing_token, status, total_windows, budget_cap_usd,
               source_sha256
          FROM public.n4_extraction_runs
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid)
         FOR UPDATE
    """), {"tenant": _uuid(tenant_id), "run": _uuid(run_id)})).mappings().one_or_none()
    if row is None:
        raise N4LedgerError("N4 run absent or not visible to this tenant")
    record = dict(row)
    if (
        str(record["document_id"]) != str(authority.document_id)
        or str(record["document_revision_id"]) != str(authority.revision_id)
        or int(record["generation"]) != authority.generation
    ):
        raise N4LedgerError("N4 run and processing authority do not match")
    if int(record["fencing_token"]) > authority.fencing_token:
        raise N4LedgerError("newer N4 fence owns this run")
    if int(record["fencing_token"]) < authority.fencing_token:
        await session.execute(text("""
            UPDATE public.n4_extraction_runs SET fencing_token = :fence,
                updated_at = clock_timestamp()
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND run_id = CAST(:run AS uuid)
        """), {
            "fence": authority.fencing_token,
            "tenant": _uuid(tenant_id), "run": _uuid(run_id),
        })
    return record


async def create_run(
    session: AsyncSession, *, authority: ProcessingAuthority,
    project_id: UUID, config_sha256: str, windows: tuple[N4SourceWindow, ...],
    budget_cap_usd: Decimal | str | int,
) -> UUID:
    """Idempotently create a revision-pinned run and all pending windows.

    No provider call, automatic approval, budget charging or COMMIT here.
    The caller MUST commit the enclosing transaction before using the run.
    """
    if not windows or not _SHA.fullmatch(config_sha256):
        raise ValueError("valid config hash and at least one window required")
    source_sha256 = windows[0].source_sha256
    if not _SHA.fullmatch(source_sha256):
        raise ValueError("invalid model-safe source hash")
    if any(
        w.ordinal != idx or w.source_sha256 != source_sha256
        or w.revision_id != str(authority.revision_id)
        for idx, w in enumerate(windows)
    ):
        raise ValueError("N4 windows must have sequential ordinals and pinned source")
    budget = _amount(budget_cap_usd)
    if budget <= 0:
        raise ValueError("N4 run budget must be greater than zero")
    await _verify(session, authority)
    run_id = uuid4()
    inserted = (await session.execute(text("""
        INSERT INTO public.n4_extraction_runs
            (run_id, tenant_id, project_id, document_id, document_revision_id,
             source_sha256, config_sha256, generation, fencing_token,
             total_windows, budget_cap_usd)
        VALUES (CAST(:run AS uuid), CAST(:tenant AS uuid),
                CAST(:project AS uuid), CAST(:document AS uuid),
                CAST(:revision AS uuid), :source, :config, :generation,
                :fence, :total, :budget)
        ON CONFLICT
            (tenant_id, document_revision_id, source_sha256,
             config_sha256, generation)
        DO NOTHING
        RETURNING run_id
    """), {
        "run": str(run_id), "tenant": _uuid(authority.tenant_id),
        "project": _uuid(project_id), "document": _uuid(authority.document_id),
        "revision": _uuid(authority.revision_id), "source": source_sha256,
        "config": config_sha256, "generation": authority.generation,
        "fence": authority.fencing_token, "total": len(windows), "budget": budget,
    })).scalar_one_or_none()
    if inserted is not None:
        # An explicit run budget is part of the trusted create_run request.
        # Other caps (tenant/project/document) MUST be configured by an
        # authorized administrator; we never invent them.
        await session.execute(text("""
            INSERT INTO public.n4_budget_buckets
              (tenant_id, scope_kind, scope_id, period_key, cap_usd)
            VALUES (CAST(:tenant AS uuid), 'RUN', CAST(:run AS uuid),
                    'RUN', :cap)
            ON CONFLICT DO NOTHING
        """), {
            "tenant": _uuid(authority.tenant_id),
            "run": str(run_id), "cap": budget,
        })
        for w in windows:
            await session.execute(text("""
                INSERT INTO public.n4_extraction_windows
                  (tenant_id, run_id, ordinal, core_start, core_end,
                   context_start, context_end, context_sha256)
                VALUES (CAST(:tenant AS uuid), CAST(:run AS uuid),
                  :ordinal, :core_start, :core_end, :context_start,
                  :context_end, :context_sha256)
            """), {
                "tenant": _uuid(authority.tenant_id), "run": str(run_id),
                "ordinal": w.ordinal, "core_start": w.core_start,
                "core_end": w.core_end, "context_start": w.context_start,
                "context_end": w.context_end,
                "context_sha256": w.context_sha256,
            })
        return run_id
    existing = (await session.execute(text("""
        SELECT run_id, total_windows, budget_cap_usd
          FROM public.n4_extraction_runs
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND document_revision_id = CAST(:revision AS uuid)
           AND source_sha256 = :source AND config_sha256 = :config
           AND generation = :generation
         FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id),
        "revision": _uuid(authority.revision_id),
        "source": source_sha256, "config": config_sha256,
        "generation": authority.generation,
    })).mappings().one()
    if int(existing["total_windows"]) != len(windows) or (
        Decimal(existing["budget_cap_usd"]) != budget
    ):
        raise N4LedgerError("same run identity cannot change windows or budget")
    run_id = UUID(str(existing["run_id"]))
    await _locked_run(
        session, tenant_id=authority.tenant_id, run_id=run_id, authority=authority,
    )
    for w in windows:
        old = (await session.execute(text("""
            SELECT core_start, core_end, context_start, context_end, context_sha256
              FROM public.n4_extraction_windows
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal
        """), {
            "tenant": _uuid(authority.tenant_id),
            "run": str(run_id), "ordinal": w.ordinal,
        })).mappings().one_or_none()
        if old is None or (
            int(old["core_start"]) != w.core_start
            or int(old["core_end"]) != w.core_end
            or int(old["context_start"]) != w.context_start
            or int(old["context_end"]) != w.context_end
            or old["context_sha256"] != w.context_sha256
        ):
            raise N4LedgerError("source window mapping drift on resume")
    return run_id


def _bucket_scopes(
    *, tenant_id: UUID, project_id: UUID, document_id: UUID,
    run_id: UUID, period_key: str,
) -> list[tuple[str, str, str]]:
    if not re.fullmatch(r"\d{4}-\d{2}", period_key):
        raise ValueError("period_key must be YYYY-MM")
    scopes = [
        ("TENANT", _uuid(tenant_id), period_key),
        ("PROJECT", _uuid(project_id), period_key),
        ("DOCUMENT", _uuid(document_id), period_key),
        ("RUN", _uuid(run_id), "RUN"),
    ]
    return sorted(scopes)


async def _inherit_missing_subscopes(
    session: AsyncSession, *, tenant_id: UUID, project_id: UUID,
    document_id: UUID, period_key: str,
) -> None:
    """Derive missing child caps from an already-approved TENANT cap.

    Only called with explicit UAT opt-in by reserve_call, after the global
    tenant row is locked and the ANALYSIS authority/run have been verified.
    Child buckets are NOT additional credit: every reservation also charges
    the tenant bucket and the shared tenants.ai_spend_reserved_usd counter.
    Existing explicit child caps are never overwritten or raised.
    """
    policy = (await session.execute(text("""
        SELECT t.ai_budget_monthly AS global_cap, b.cap_usd AS tenant_cap
          FROM public.tenants t
          JOIN public.n4_budget_buckets b
            ON b.tenant_id = t.id AND b.scope_kind = 'TENANT'
           AND b.scope_id = t.id AND b.period_key = :period
          JOIN public.documents d
            ON d.tenant_id = t.id
           AND d.id = CAST(:document AS uuid)
           AND d.project_id = CAST(:project AS uuid)
         WHERE t.id = CAST(:tenant AS uuid) AND t.is_active IS TRUE
    """), {
        "tenant": _uuid(tenant_id), "project": _uuid(project_id),
        "document": _uuid(document_id), "period": period_key,
    })).mappings().one_or_none()
    if policy is None:
        raise N4BudgetNotConfigured(
            "approved TENANT budget or verified project-document identity missing"
        )
    try:
        cap = min(_amount(policy["global_cap"]), _amount(policy["tenant_cap"]))
    except (ValueError, TypeError) as exc:
        raise N4BudgetNotConfigured("TENANT spending cap invalid") from exc
    if cap <= 0:
        raise N4BudgetNotConfigured("positive approved TENANT cap required")
    for kind, scope_id in (
        ("PROJECT", project_id), ("DOCUMENT", document_id),
    ):
        await session.execute(text("""
            INSERT INTO public.n4_budget_buckets
              (tenant_id, scope_kind, scope_id, period_key, cap_usd)
            VALUES (CAST(:tenant AS uuid), :kind, CAST(:scope AS uuid),
                    :period, :cap)
            ON CONFLICT DO NOTHING
        """), {
            "tenant": _uuid(tenant_id), "kind": kind,
            "scope": _uuid(scope_id), "period": period_key, "cap": cap,
        })


async def _lock_budget_scopes(
    session: AsyncSession, *, tenant_id: UUID,
    scopes: list[tuple[str, str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind, scope_id, period in scopes:
        row = (await session.execute(text("""
            SELECT scope_kind, scope_id, period_key, cap_usd,
                   reserved_usd, spent_usd
              FROM public.n4_budget_buckets
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND scope_kind = :kind AND scope_id = CAST(:scope AS uuid)
               AND period_key = :period
             FOR UPDATE
        """), {
            "tenant": _uuid(tenant_id), "kind": kind,
            "scope": scope_id, "period": period,
        })).mappings().one_or_none()
        if row is None:
            raise N4BudgetNotConfigured(
                f"N4 budget bucket absent for scope {kind}; no implicit unlimited budget"
            )
        rows.append(dict(row))
    return rows


# Reused in ephemeral-PG regression to verify the EXACT live reservation gate.
_CROSS_GENERATION_RECEIPT_SQL = text("""
    SELECT 1
      FROM public.n4_usage_reservations prior
      JOIN public.n4_extraction_runs previous
        ON previous.tenant_id = prior.tenant_id AND previous.run_id = prior.run_id
     WHERE previous.tenant_id = CAST(:tenant AS uuid)
       AND previous.document_id = CAST(:document AS uuid)
       AND previous.document_revision_id = CAST(:revision AS uuid)
       AND previous.source_sha256 = :source_sha
       AND previous.run_id <> CAST(:run AS uuid)
       AND prior.status IN ('SETTLED', 'RESERVED', 'UNKNOWN')
     LIMIT 1
""")

async def reserve_call(
    session: AsyncSession, *, authority: ProcessingAuthority,
    run_id: UUID, window_ordinal: int, idempotency_key: str,
    provider_model: str, estimated_max_usd: Decimal | str | int,
    period_key: str, inherit_approved_scopes: bool = False,
) -> N4Reservation:
    """One atomic reservation across tenant, project, document and run caps.

    Replay returns existing reservation; it does NOT authorize a second
    model call. Unknown/unfinished prior attempts block a different key.
    """
    if len(idempotency_key.strip()) < 8 or not provider_model.strip():
        raise ValueError("provider model and a stable idempotency key are required")
    amount = _amount(estimated_max_usd)
    if amount <= 0:
        raise ValueError("a reservation must be positive")
    await _verify(session, authority)
    # The caller cannot select a stale monthly bucket with unused credit.
    # The PostgreSQL clock is the financial authority, not the worker clock.
    db_month = await session.scalar(text(
        "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC', 'YYYY-MM')"
    ))
    if period_key != str(db_month):
        raise N4BudgetError("N4 reservation period must equal current DB UTC month")
    global_remaining = await _locked_tenant_budget(
        session, tenant_id=authority.tenant_id,
    )
    run = await _locked_run(
        session, tenant_id=authority.tenant_id,
        run_id=run_id, authority=authority,
    )
    if run["status"] in ("COMPLETE", "FAILED"):
        raise N4LedgerError("cannot reserve a completed or failed N4 run")
    window = (await session.execute(text("""
        SELECT status FROM public.n4_extraction_windows
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "ordinal": window_ordinal,
    })).scalar_one_or_none()
    if window is None or window == "EXAMINED":
        raise N4LedgerError("source window unavailable or already examined")
    old = (await session.execute(text("""
        SELECT reservation_id, status, reserved_usd, window_ordinal, model_name
          FROM public.n4_usage_reservations
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND idempotency_key = :key
         FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "key": idempotency_key,
    })).mappings().one_or_none()
    if old:
        if (
            Decimal(old["reserved_usd"]) != amount
            or int(old["window_ordinal"]) != window_ordinal
            or str(old["model_name"]) != provider_model
        ):
            raise N4LedgerError("same attempt key cannot change model, window or amount")
        return N4Reservation(UUID(str(old["reservation_id"])), str(old["status"]), True)
    open_attempt = (await session.execute(text("""
        SELECT 1 FROM public.n4_usage_reservations
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
           AND window_ordinal = :ordinal AND status IN ('RESERVED','UNKNOWN')
         LIMIT 1
    """), {
        "tenant": _uuid(authority.tenant_id),
        "run": str(run_id), "ordinal": window_ordinal,
    })).scalar_one_or_none()
    if open_attempt:
        raise N4BudgetError(
            "window has unsettled or unknown provider cost; reconcile before retry"
        )
    # A run-local idempotency key contains run_id and cannot prevent a later
    # generation from paying for the same source a second time. Before ANY
    # reservation/bucket mutation, refuse a new run whenever an earlier run
    # of this immutable document revision + N2 source has billable history.
    # This conservative stop requires explicit reconciliation / reuse design,
    # never silently drops a SETTLED, RESERVED, or UNKNOWN provider liability.
    cross_generation = (await session.execute(_CROSS_GENERATION_RECEIPT_SQL, {
        "tenant": _uuid(authority.tenant_id),
        "document": _uuid(authority.document_id),
        "revision": _uuid(authority.revision_id),
        "source_sha": str(run["source_sha256"]),
        "run": str(run_id),
    })).scalar_one_or_none()
    if cross_generation:
        raise N4PriorRunReconciliationRequired(
            "earlier generation has billable or unknown N4 usage; "
            "reconcile before any new provider call"
        )
    if inherit_approved_scopes:
        await _inherit_missing_subscopes(
            session, tenant_id=authority.tenant_id,
            project_id=UUID(str(run["project_id"])),
            document_id=authority.document_id, period_key=period_key,
        )
    scopes = _bucket_scopes(
        tenant_id=authority.tenant_id, project_id=UUID(str(run["project_id"])),
        document_id=authority.document_id, run_id=run_id, period_key=period_key,
    )
    buckets = await _lock_budget_scopes(
        session, tenant_id=authority.tenant_id, scopes=scopes,
    )
    if Decimal(run["budget_cap_usd"]) < amount:
        raise N4BudgetExceeded("single call exceeds N4 run cap")
    if global_remaining < amount:
        raise N4BudgetExceeded(
            "global tenant budget includes all confirmed and N4 reserved AI use"
        )
    for bucket in buckets:
        available = (
            Decimal(bucket["cap_usd"]) -
            Decimal(bucket["reserved_usd"]) -
            Decimal(bucket["spent_usd"])
        )
        if available < amount:
            raise N4BudgetExceeded(
                f"N4 spend cap exhausted for {bucket['scope_kind']}"
            )
    for kind, scope_id, period in scopes:
        await session.execute(text("""
            UPDATE public.n4_budget_buckets
               SET reserved_usd = reserved_usd + :amount,
                   updated_at = clock_timestamp()
             WHERE tenant_id = CAST(:tenant AS uuid) AND scope_kind = :kind
               AND scope_id = CAST(:scope AS uuid) AND period_key = :period
        """), {
            "amount": amount, "tenant": _uuid(authority.tenant_id),
            "kind": kind, "scope": scope_id, "period": period,
        })
    global_hold = (await session.execute(text("""
        UPDATE public.tenants SET
            ai_spend_reserved_usd = ai_spend_reserved_usd + :amount
         WHERE id = CAST(:tenant AS uuid)
         RETURNING id
    """), {
        "amount": amount, "tenant": _uuid(authority.tenant_id),
    })).scalar_one_or_none()
    if global_hold is None:
        raise N4LedgerError("unable to reserve global tenant balance")
    reservation_id = uuid4()
    await session.execute(text("""
        INSERT INTO public.n4_usage_reservations
            (reservation_id, tenant_id, run_id, window_ordinal,
             idempotency_key, bucket_scopes, reserved_usd, model_name)
        VALUES (CAST(:reservation AS uuid), CAST(:tenant AS uuid),
                CAST(:run AS uuid), :ordinal, :key, CAST(:scopes AS jsonb),
                :amount, :model)
    """), {
        "reservation": str(reservation_id),
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "ordinal": window_ordinal, "key": idempotency_key,
        "scopes": json.dumps([
            {"kind": kind, "id": scope_id, "period": period}
            for kind, scope_id, period in scopes
        ]), "amount": amount, "model": provider_model,
    })
    return N4Reservation(reservation_id, "RESERVED", False)


async def account_call(
    session: AsyncSession, *, authority: ProcessingAuthority,
    reservation_id: UUID, billed_usd: Decimal | str | int | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    provider_request_id: str | None = None,
    actual_model_name: str | None = None,
    actual_provider: str | None = None,
) -> str:
    """Reconcile provider receipt once, or retain reserve if price unknown.

    The observed charge may exceed the preflight reservation. It remains an
    actual liability; do not silently cap or replace actual billed use with 0.
    """
    for count in (input_tokens, output_tokens):
        if count is not None and (type(count) is not int or count < 0):
            raise N4LedgerError("provider token count must be nonnegative integer")
    if provider_request_id is not None and (
        not provider_request_id or len(provider_request_id) > 128
    ):
        raise N4LedgerError("invalid provider request reference")
    await _verify(session, authority)
    # Global tenant lock must be taken before the run lock, matching
    # reserve_call order: authority -> tenant -> run -> reservation -> buckets.
    await _locked_tenant_budget(
        session, tenant_id=authority.tenant_id, for_settlement=True,
    )
    # Read the run ID without a lock; then obey the global lock order:
    # processing authority -> tenant -> run -> reservation -> scopes. A changed
    # reservation is re-read once locked, never trusted from the first read.
    initial = (await session.execute(text("""
        SELECT run_id FROM public.n4_usage_reservations
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND reservation_id = CAST(:reservation AS uuid)
    """), {
        "tenant": _uuid(authority.tenant_id),
        "reservation": str(reservation_id),
    })).scalar_one_or_none()
    if initial is None:
        raise N4LedgerError("reservation absent or not visible to this tenant")
    await _locked_run(
        session, tenant_id=authority.tenant_id,
        run_id=UUID(str(initial)), authority=authority,
    )
    reservation = (await session.execute(text("""
        SELECT reservation_id, run_id, status, reserved_usd,
               spent_usd, bucket_scopes, input_tokens, output_tokens,
               provider_request_id, model_name, actual_model_name, actual_provider
          FROM public.n4_usage_reservations
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND reservation_id = CAST(:reservation AS uuid)
         FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id),
        "reservation": str(reservation_id),
    })).mappings().one()
    status = str(reservation["status"])
    # The primary reservation model must remain immutable. Explicitly retain
    # the actual provider/model when a different direct API settled the call.
    resolved_model = actual_model_name or str(reservation["model_name"])
    resolved_provider = actual_provider or (
        "anthropic" if resolved_model == reservation["model_name"] else None
    )
    if not (
        isinstance(resolved_model, str)
        and 2 <= len(resolved_model) <= 128
        and resolved_provider in ("anthropic", "openai", "gemini")
    ):
        raise N4LedgerError("actual provider/model identity is invalid")
    if billed_usd is None:
        if status == "SETTLED":
            return status
        if status == "CANCELED":
            raise N4LedgerError("cannot reopen canceled reservation")
        await session.execute(text("""
            UPDATE public.n4_usage_reservations
               SET status = 'UNKNOWN', input_tokens = COALESCE(:in_tokens, input_tokens),
                   output_tokens = COALESCE(:out_tokens, output_tokens),
                   provider_request_id = COALESCE(:provider_req, provider_request_id)
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND reservation_id = CAST(:reservation AS uuid)
        """), {
            "tenant": _uuid(authority.tenant_id), "reservation": str(reservation_id),
            "in_tokens": input_tokens, "out_tokens": output_tokens,
            "provider_req": provider_request_id,
        })
        return "UNKNOWN"
    actual = _amount(billed_usd)
    if status == "SETTLED":
        if (
            (reservation["actual_model_name"] or reservation["model_name"]) != resolved_model
            or (reservation["actual_provider"] or "anthropic") != resolved_provider
        ):
            raise N4LedgerError("replayed provider identity differs from committed receipt")
        if Decimal(reservation["spent_usd"]) != actual or any(
            provided is not None and provided != reservation[name]
            for name, provided in (
                ("input_tokens", input_tokens),
                ("output_tokens", output_tokens),
                ("provider_request_id", provider_request_id),
            )
        ):
            raise N4LedgerError("replayed usage receipt differs from committed cost or usage")
        return "SETTLED"
    if status == "CANCELED":
        raise N4LedgerError("cannot settle canceled reservation")
    scopes = reservation["bucket_scopes"]
    if isinstance(scopes, str):
        scopes = json.loads(scopes)
    expected = _bucket_scopes(
        tenant_id=authority.tenant_id,
        project_id=(await _project_for_run(
            session, authority.tenant_id, UUID(str(reservation["run_id"]))
        )),
        document_id=authority.document_id,
        run_id=UUID(str(reservation["run_id"])),
        period_key=next(
            (str(x["period"]) for x in scopes if x["kind"] == "TENANT"), "",
        ),
    )
    if [
        (x["kind"], x["id"], x["period"]) for x in scopes
    ] != expected:
        raise N4LedgerError("reservation scope identities were modified")
    # Lock scope rows in the SAME deterministic order as a reservation.
    await _lock_budget_scopes(
        session, tenant_id=authority.tenant_id, scopes=expected,
    )
    for kind, scope_id, period in expected:
        await session.execute(text("""
            UPDATE public.n4_budget_buckets
               SET reserved_usd = reserved_usd - :reserved,
                   spent_usd = spent_usd + :actual,
                   updated_at = clock_timestamp()
             WHERE tenant_id = CAST(:tenant AS uuid) AND scope_kind = :kind
               AND scope_id = CAST(:scope AS uuid) AND period_key = :period
        """), {
            "reserved": Decimal(reservation["reserved_usd"]), "actual": actual,
            "tenant": _uuid(authority.tenant_id), "kind": kind,
            "scope": scope_id, "period": period,
        })
    # Transfer the liability once: the ledger and the legacy global counter
    # cannot disagree after this transaction commits. Overages are actual
    # charges and must be recorded, not silently clipped to reservation.
    global_settlement = (await session.execute(text("""
        UPDATE public.tenants
           SET ai_spend_reserved_usd = ai_spend_reserved_usd - :reserved,
               ai_spend_current = ai_spend_current + CAST(:actual AS double precision)
         WHERE id = CAST(:tenant AS uuid)
           AND ai_spend_reserved_usd >= :reserved
         RETURNING id
    """), {
        "reserved": Decimal(reservation["reserved_usd"]),
        "actual": actual, "tenant": _uuid(authority.tenant_id),
    })).scalar_one_or_none()
    if global_settlement is None:
        raise N4LedgerError("tenant global reservation missing or already settled")
    await session.execute(text("""
        UPDATE public.n4_usage_reservations
           SET status = 'SETTLED', spent_usd = :actual,
               input_tokens = COALESCE(:in_tokens, input_tokens),
               output_tokens = COALESCE(:out_tokens, output_tokens),
               provider_request_id = COALESCE(:provider_req, provider_request_id),
               actual_model_name = :actual_model,
               actual_provider = :actual_provider,
               settled_at = clock_timestamp()
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND reservation_id = CAST(:reservation AS uuid)
    """), {
        "actual": actual, "tenant": _uuid(authority.tenant_id),
        "reservation": str(reservation_id),
        "in_tokens": input_tokens, "out_tokens": output_tokens,
        "provider_req": provider_request_id,
        "actual_model": resolved_model,
        "actual_provider": resolved_provider,
    })
    return "SETTLED"


async def _project_for_run(
    session: AsyncSession, tenant_id: UUID, run_id: UUID,
) -> UUID:
    project = (await session.execute(text("""
        SELECT project_id FROM public.n4_extraction_runs
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
    """), {"tenant": _uuid(tenant_id), "run": str(run_id)})).scalar_one()
    return UUID(str(project))


async def commit_window(
    session: AsyncSession, *, authority: ProcessingAuthority, run_id: UUID,
    window_ordinal: int, findings: list[dict[str, Any]],
    unresolved_refs: tuple[str, ...] = (),
    incomplete_reason: str | None = None,
) -> str:
    """Atomically commit one successfully billed window and proposed findings.

    A validated response may contain zero candidates, but completing ALL
    windows is only source coverage — never proof that no risks exist.
    """
    await _verify(session, authority)
    run = await _locked_run(
        session, tenant_id=authority.tenant_id,
        run_id=run_id, authority=authority,
    )
    if run["status"] in ("COMPLETE", "FAILED"):
        raise N4LedgerError("run has already reached a terminal status")
    win = (await session.execute(text("""
        SELECT status, findings_sha256 FROM public.n4_extraction_windows
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id),
        "run": str(run_id), "ordinal": window_ordinal,
    })).mappings().one_or_none()
    if win is None:
        raise N4LedgerError("window not found")
    digest = sha256(
        json.dumps(
            sorted(findings, key=lambda item: str(item.get("finding_key", ""))),
            sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if win["status"] in ("EXAMINED", "BLOCKED"):
        if win["findings_sha256"] != digest:
            raise N4LedgerError("replayed N4 window has a different findings payload")
        return "ALREADY_EXAMINED" if win["status"] == "EXAMINED" else "ALREADY_BLOCKED"
    receipt = (await session.execute(text("""
        SELECT 1 FROM public.n4_usage_reservations
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
           AND window_ordinal = :ordinal AND status = 'SETTLED'
         LIMIT 1
    """), {
        "tenant": _uuid(authority.tenant_id),
        "run": str(run_id), "ordinal": window_ordinal,
    })).scalar_one_or_none()
    if receipt is None:
        raise N4LedgerError("window cannot be examined before a settled provider receipt")
    for finding in findings:
        key = str(finding.get("finding_key", ""))
        refs, claim = finding.get("source_refs"), finding.get("claim")
        if not _SHA.fullmatch(key) or not isinstance(refs, list) or not refs:
            raise N4LedgerError("candidate must have a stable digest and source refs")
        if not isinstance(claim, dict):
            raise N4LedgerError("candidate claim must be a JSON object")
        old = (await session.execute(text("""
            SELECT source_refs, claim FROM public.n4_candidate_findings
             WHERE tenant_id = CAST(:tenant AS uuid)
               AND run_id = CAST(:run AS uuid) AND finding_key = :key
        """), {
            "tenant": _uuid(authority.tenant_id),
            "run": str(run_id), "key": key,
        })).mappings().one_or_none()
        if old:
            if old["source_refs"] != refs or old["claim"] != claim:
                raise N4LedgerError("candidate identity collision with changed evidence")
            continue
        await session.execute(text("""
            INSERT INTO public.n4_candidate_findings
                (finding_id, tenant_id, run_id, window_ordinal,
                 finding_key, source_refs, claim)
            VALUES (CAST(:id AS uuid), CAST(:tenant AS uuid),
                    CAST(:run AS uuid), :ordinal, :key,
                    CAST(:refs AS jsonb), CAST(:claim AS jsonb))
        """), {
            "id": str(uuid4()), "tenant": _uuid(authority.tenant_id),
            "run": str(run_id), "ordinal": window_ordinal,
            "key": key, "refs": json.dumps(refs), "claim": json.dumps(claim),
        })
    blocked = bool(unresolved_refs or incomplete_reason)
    next_window_status = "BLOCKED" if blocked else "EXAMINED"
    await session.execute(text("""
        UPDATE public.n4_extraction_windows
           SET status = :status, findings_sha256 = :digest,
               unresolved_refs = CAST(:refs AS jsonb), blocked_reason = :reason,
               committed_at = clock_timestamp()
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "ordinal": window_ordinal, "digest": digest,
        "status": next_window_status, "refs": json.dumps(unresolved_refs),
        "reason": incomplete_reason or ("REFERENCES_UNRESOLVED" if unresolved_refs else None),
    })
    status_totals = (await session.execute(text("""
        SELECT
          count(*) FILTER (WHERE status != 'EXAMINED') AS incomplete,
          count(*) FILTER (WHERE status = 'BLOCKED') AS blocked
          FROM public.n4_extraction_windows
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid)
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
    })).mappings().one()
    next_status = (
        "PARTIAL" if status_totals["blocked"] else
        "COMPLETE" if int(status_totals["incomplete"]) == 0 else "RUNNING"
    )
    await session.execute(text("""
        UPDATE public.n4_extraction_runs SET status = :status,
                updated_at = clock_timestamp()
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
    """), {
        "tenant": _uuid(authority.tenant_id),
        "run": str(run_id), "status": next_status,
    })
    return next_status


async def progress(
    session: AsyncSession, *, tenant_id: UUID, run_id: UUID,
) -> dict[str, int | str]:
    """Read only tenant-visible progress; coverage is not semantic recall."""
    row = (await session.execute(text("""
        SELECT r.status, r.total_windows,
               count(w.ordinal) FILTER (WHERE w.status = 'EXAMINED') AS examined
          FROM public.n4_extraction_runs r
          JOIN public.n4_extraction_windows w
            ON w.tenant_id = r.tenant_id AND w.run_id = r.run_id
         WHERE r.tenant_id = CAST(:tenant AS uuid)
           AND r.run_id = CAST(:run AS uuid)
         GROUP BY r.status, r.total_windows
    """), {"tenant": _uuid(tenant_id), "run": str(run_id)})).mappings().one_or_none()
    if row is None:
        raise N4LedgerError("run not found for tenant")
    return {
        "status": str(row["status"]),
        "total_windows": int(row["total_windows"]),
        "examined_windows": int(row["examined"]),
    }


async def window_statuses(
    session: AsyncSession, *, tenant_id: UUID, run_id: UUID,
) -> dict[int, str]:
    """Read tenant-visible window progress. No unexamined call is replayed."""
    rows = (await session.execute(text("""
        SELECT ordinal, status FROM public.n4_extraction_windows
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
         ORDER BY ordinal
    """), {"tenant": _uuid(tenant_id), "run": str(run_id)})).all()
    return {int(ordinal): str(status) for ordinal, status in rows}


async def block_window(
    session: AsyncSession, *, authority: ProcessingAuthority,
    run_id: UUID, window_ordinal: int, reason: str,
) -> None:
    """Persist UNKNOWN or invalid output as blocked without claiming analysis."""
    if not reason or len(reason) > 80:
        raise ValueError("bounded non-sensitive failure kind required")
    await _verify(session, authority)
    run = await _locked_run(
        session, tenant_id=authority.tenant_id, run_id=run_id, authority=authority,
    )
    if run["status"] in ("COMPLETE", "FAILED"):
        raise N4LedgerError("terminal run cannot be blocked")
    status = (await session.execute(text("""
        SELECT status FROM public.n4_extraction_windows
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal FOR UPDATE
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "ordinal": window_ordinal,
    })).scalar_one_or_none()
    if status is None or status == "EXAMINED":
        raise N4LedgerError("missing or previously examined source window")
    await session.execute(text("""
        UPDATE public.n4_extraction_windows
           SET status = 'BLOCKED', blocked_reason = :reason
         WHERE tenant_id = CAST(:tenant AS uuid)
           AND run_id = CAST(:run AS uuid) AND ordinal = :ordinal
    """), {
        "tenant": _uuid(authority.tenant_id), "run": str(run_id),
        "ordinal": window_ordinal, "reason": reason,
    })
    await session.execute(text("""
        UPDATE public.n4_extraction_runs
           SET status = 'PARTIAL', updated_at = clock_timestamp()
         WHERE tenant_id = CAST(:tenant AS uuid) AND run_id = CAST(:run AS uuid)
    """), {"tenant": _uuid(authority.tenant_id), "run": str(run_id)})
