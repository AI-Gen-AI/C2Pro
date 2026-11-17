"""Paid, bounded V4.1 real SEC EPC pilot. OPERATOR QA ONLY.

N1/N2 PDF -> real N3 classification -> lossless N4 incremental real model/
transactional PG ledger -> real N12 with durable checkpoint and shared escrow.
All outputs PROPOSED; never auto-approve or claim ProjectGraph/UI UAT.
A separate exact-SHA GitHub workflow must bind a dedicated provider key,
SDK call governor and a disposable PostgreSQL database.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import asyncpg
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from v41_contract_source_preflight import preflight

from src.analysis.adapters.ai.anthropic_client import AIService
from src.analysis.adapters.ai.n4_anthropic_window_provider import AnthropicN4WindowProvider
from src.analysis.adapters.graph import nodes, workflow
from src.analysis.adapters.graph.schema import ProjectState
from src.analysis.application.n4_incremental_runner import N4IncrementalRunner
from src.analysis.domain.prompts import ROUTER_SYSTEM_PROMPT
from src.core.ai import legacy_ai_governed_call
from src.core.ai.anthropic_wrapper import AnthropicWrapper
from src.core.ai.model_router import ModelTier
from tests.integration.analysis.test_n4_incremental_store_pg import (
    _new_authority,
    _seed_caps,
    _seed_identity,
)

MAX_CALLS = 30
MAX_USD = Decimal("5.00")


def _gate():
    sha = os.environ.get("GITHUB_SHA", "")
    ref = os.environ.get("GITHUB_REF_NAME", "")
    exact = os.environ.get("C2PRO_V41_REAL_AI_CONFIRM_SHA", "")
    if not (len(sha) == 40 and sha == exact and
            ref == "qa/c2pro-v4-ab-n12-latch-integration-20261117"):
        raise RuntimeError("V41_REAL_AI_EXACT_SHA_REF_MISMATCH")
    if os.environ.get("C2PRO_AI_MOCK") != "0":
        raise RuntimeError("V41_REAL_AI_MOCK_MUST_BE_DISABLED")
    if os.environ.get("C2PRO_N12_CHECKPOINT_ESCROW") != "1":
        raise RuntimeError("V41_N12_DURABLE_ESCROW_NOT_ENABLED")
    if os.environ.get("C2PRO_N12_REQUIRE_ESCROW") != "1":
        raise RuntimeError("V41_N12_LATCH_NOT_ENABLED")
    provider = os.environ.get("C2PRO_V41_PROVIDER", "anthropic")
    if provider == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("V41_DEDICATED_ANTHROPIC_KEY_MISSING")
        from real_ai_governor import _limits
        _path, calls, cap = _limits()
        if calls != MAX_CALLS or Decimal(str(cap)) != MAX_USD:
            raise RuntimeError("V41_SDK_GOVERNOR_LIMITS_MISMATCH")
        from anthropic.resources.messages import AsyncMessages, Messages
        if not getattr(AsyncMessages.create, "_c2pro_governed", False):
            raise RuntimeError("V41_ASYNC_PROVIDER_NOT_GOVERNED")
        if not getattr(Messages.create, "_c2pro_governed", False):
            raise RuntimeError("V41_SYNC_PROVIDER_NOT_GOVERNED")
    elif provider == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("V41_DEDICATED_OPENAI_KEY_MISSING")
        if os.getenv("C2PRO_V41_OPENAI_MAX_CALLS") != "30" or os.getenv("C2PRO_V41_OPENAI_MAX_USD") != "5.0":
            raise RuntimeError("V41_OPENAI_GOVERNOR_MISCONFIGURED")
    else:
        raise RuntimeError("V41_PROVIDER_NOT_ALLOWED")
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn.startswith("postgresql://") or not dsn.endswith("/c2pro_test"):
        raise RuntimeError("V41_DB_MUST_BE_DISPOSABLE_TEST_DATABASE")
    return dsn


def _save(report: dict, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "real_analysis_evidence.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf8",
    )


async def _ledger_snapshot(engine, tenant_id):
    async with AsyncSession(engine) as db, db.begin():
        await db.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        n4 = (await db.execute(text("""
            SELECT r.window_ordinal, r.status, r.spent_usd, r.reserved_usd,
                   r.model_name, r.input_tokens, r.output_tokens,
                   r.provider_request_id
              FROM public.n4_usage_reservations AS r
             WHERE r.tenant_id=CAST(:tenant AS uuid)
             ORDER BY r.window_ordinal
        """), {"tenant": str(tenant_id)})).mappings().all()
        n12 = (await db.execute(text("""
            SELECT call_source, status, billed_usd, reserved_usd,
                   input_tokens, output_tokens, provider_model, idempotency_key
              FROM public.legacy_ai_usage_reservations
             WHERE tenant_id=CAST(:tenant AS uuid)
             ORDER BY created_at
        """), {"tenant": str(tenant_id)})).mappings().all()
        balance = (await db.execute(text("""
            SELECT ai_budget_monthly, ai_spend_current, ai_spend_reserved_usd
              FROM public.tenants
             WHERE id=CAST(:tenant AS uuid)
        """), {"tenant": str(tenant_id)})).mappings().one()
        return list(map(dict,n4)),list(map(dict,n12)),dict(balance)


async def _get_findings(engine, tenant_id, run_id):
    async with AsyncSession(engine) as db, db.begin():
        await db.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": str(tenant_id)},
        )
        rows = (await db.execute(text("""
            SELECT finding_key, window_ordinal, source_refs, claim
              FROM public.n4_candidate_findings
             WHERE tenant_id=CAST(:tenant AS uuid)
               AND run_id=CAST(:run AS uuid)
             ORDER BY window_ordinal, finding_key
        """), {"tenant": str(tenant_id),"run": str(run_id)})).mappings().all()
        return [dict(row) for row in rows]


async def pilot(sec_pdf: Path, out: Path):
    dsn = _gate()  # No expense is possible before all gates.
    source_report = await preflight(sec_pdf, out)
    safe = (out / "source_n2_protected.txt").read_text(encoding="utf8")
    if source_report["n4_windows_planned"] != 24:
        raise RuntimeError("V41_SOURCE_WINDOW_COUNT_CHANGED")
    print("V41_LIVE_PREPARED: PDF=73 pages; N2 chars=", len(safe),
          "N4 windows=24; source_sha256=", source_report["n2_text_sha256"],
          flush=True)
    report = {
        "run_sha": os.environ["GITHUB_SHA"],
        "provider": os.environ.get("C2PRO_V41_PROVIDER", "anthropic"),
        "billing_note": "Estimated pricing from metered tokens; NOT verified against provider invoice",
        "data_source": "SEC EX-99.1 authentic public EPC via 73-page filing PDF rendition",
        "source": source_report,
        "governor_max_usd": str(MAX_USD),
        "governor_max_calls": MAX_CALLS,
        "n3": {"status": "NOT_STARTED"},
        "n4": {"status": "NOT_STARTED"},
        "n12": {"status": "NOT_STARTED"},
        "hitl": {"status": "PENDING_REVIEW", "approved_risk_count": 0},
        "n8_projectgraph": {"status": "UNASSESSED_NOT_PROMOTED"},
        "validation": "PENDING",
    }
    _save(report, out)

    authority = _new_authority(uuid4(), uuid4(), uuid4())
    project = uuid4()
    conn = await asyncpg.connect(dsn)
    try:
        await _seed_identity(conn, authority=authority, project=project)
        await _seed_caps(
            conn, authority.tenant_id, project, authority.document_id, "4.000000",
        )
        await conn.execute("""
            UPDATE public.tenants SET ai_budget_monthly=5.0,
               ai_spend_current=0.0, ai_spend_reserved_usd=0.0,
               ai_spend_last_reset=clock_timestamp() AT TIME ZONE 'UTC'
            WHERE id=$1
        """, authority.tenant_id)
    finally:
        await conn.close()
    engine = create_async_engine(
        dsn.replace("postgresql://", "postgresql+asyncpg://", 1),
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    @asynccontextmanager
    async def budget_session(tenant_id):
        async with AsyncSession(engine) as db:
            try:
                await db.execute(text(
                    "SELECT set_config('app.current_tenant', :tenant, true)"
                ), {"tenant": str(tenant_id)})
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise
    # Isolated runner DI only; actual shared ledger tables/transactions stay real.
    legacy_ai_governed_call.get_session_with_tenant = budget_session

    try:
        configured_provider = os.environ.get("C2PRO_V41_PROVIDER", "anthropic")
        transport = None
        if configured_provider == "openai":
            from v41_openai_budgeted_adapter import (
                OpenAIBudgetedTransport,
                OpenAICompatWrapper,
            )
            transport = OpenAIBudgetedTransport(os.environ["OPENAI_API_KEY"])
            n3_wrapper = OpenAICompatWrapper(transport)
        else:
            n3_wrapper = AnthropicWrapper(
                enable_cache=False, enable_retry=False,
                max_tokens_limit=512, timeout_seconds=90,
            )
        n3 = AIService(wrapper=n3_wrapper, tenant_id=authority.tenant_id)
        # Classification is a header-level task only, not a filter on N4.
        n3_text = safe[:6000]
        n3_key = "n3-" + hashlib.sha256(
            (str(authority.revision_id) + source_report["n2_text_sha256"]).encode()
        ).hexdigest()
        print("N3_REAL_CALL: governed and zero automatic retries", flush=True)
        classification = await n3.run_extraction(
            ROUTER_SYSTEM_PROMPT, n3_text,
            governed_request_id=n3_key,
        )
        doc_type = str(classification.get("doc_type", "")).lower().strip()
        report["n3"] = {
            "status": "CLASSIFIED" if doc_type in ("contract","other") else "UNASSESSED",
            "document_type": doc_type,
            "classification_context_chars": len(n3_text),
            "economic_call_key_digest": hashlib.sha256(n3_key.encode()).hexdigest(),
        }
        _save(report, out)
        if doc_type not in ("contract", "other"):
            raise RuntimeError("N3_NOT_ROUTABLE_TO_N4")

        if configured_provider == "openai":
            from v41_openai_budgeted_adapter import OpenAIWindowProvider
            assert transport is not None
            provider = OpenAIWindowProvider(transport)
        else:
            provider = AnthropicN4WindowProvider.from_configured_account(
                tier=ModelTier.STANDARD, max_output_tokens=4096,
            )
        report["model"] = provider.model_name
        runner = N4IncrementalRunner(
            session_factory=factory,
            provider=provider,
            enabled=True,
            run_cap_usd="4.000000",
            per_window_reservation_usd="0.150000",
            period_key=datetime.now(UTC).strftime("%Y-%m"),
            max_context_chars=12000, overlap_chars=400,
        )
        print("N4_INCREMENTAL_REAL_START 24 windows budgeted before every provider call",
              flush=True)
        outcome = await runner.run(
            authority=authority, project_id=project,
            model_safe_text=safe, n2_projection_attested=True,
        )
        findings = await _get_findings(
            engine, authority.tenant_id, outcome.run_id,
        )
        n4_finance,n3_finance,balances = await _ledger_snapshot(
            engine,authority.tenant_id,
        )
        report["n4"] = {
            "status": outcome.status,
            "stopped_reason": outcome.stopped_reason,
            "run_id": str(outcome.run_id),
            "examined_windows": outcome.examined_windows,
            "total_windows": outcome.total_windows,
            "settled_receipt_windows": outcome.settled_receipt_windows,
            "persisted_result_windows": outcome.persisted_result_windows,
            "blocked_result_windows": outcome.blocked_result_windows,
            "finding_count": len(findings),
            "candidates": findings,  # all, never top-N.
            "receipts": n4_finance,
        }
        report["shared_ledger"] = n3_finance
        report["tenant_balance"] = balances
        _save(report,out)
        print(
            "N4_REAL_STATUS", outcome.status,
            "clean", outcome.examined_windows, "/", outcome.total_windows,
            "settled", outcome.settled_receipt_windows,
            "durably_parsed", outcome.persisted_result_windows,
            "blocked_with_results", outcome.blocked_result_windows,
            "candidates", len(findings), flush=True,
        )
        if outcome.status != "COMPLETE" or outcome.examined_windows != outcome.total_windows:
            raise RuntimeError("N4_REAL_PARTIAL_REQUIRES_RECONCILIATION")

        # Map all provisional findings, retaining exact source offsets and
        # original candidate keys. Nothing becomes approved.
        candidates = []
        for finding in findings:
            claim = finding["claim"]
            refs = finding["source_refs"]
            verified = any(
                r.get("evidence_status") == "EXACT_MODEL_SAFE_MATCH"
                for r in refs
            )
            candidates.append({
                "title": claim.get("title",""),
                "description": claim.get("risk_reason",""),
                "source_quote": claim.get("source_quote") if verified else None,
                "source_quote_status": "VERIFIED" if verified else "NOT_FOUND",
                "source_refs": refs,
                "finding_key": finding["finding_key"],
                "clause_ref": claim.get("clause_ref"),
                "risk_status": "PROPOSED",
            })

        if configured_provider == "openai":
            from v41_openai_budgeted_adapter import OpenAICompatWrapper
            assert transport is not None
            n12_wrapper = OpenAICompatWrapper(transport)
        else:
            n12_wrapper = AnthropicWrapper(
                enable_cache=False, enable_retry=False,
                max_tokens_limit=4096, timeout_seconds=90,
            )
        n12_service = AIService(
            wrapper=n12_wrapper, tenant_id=authority.tenant_id,
        )
        nodes.get_ai_service = lambda _tenant: n12_service
        graph_builder=StateGraph(ProjectState)
        async def extractor(state):
            return {"doc_type": state["doc_type"]}
        graph_builder.add_node("extractor",extractor)
        graph_builder.add_node("critique",nodes.critique_node)
        graph_builder.set_entry_point("extractor")
        graph_builder.add_edge("extractor","critique")
        graph_builder.add_edge("critique",END)

        pool=AsyncConnectionPool(
            conninfo=dsn, min_size=0, max_size=3,
            kwargs={"autocommit":True},
        )
        async with pool:
            saver=AsyncPostgresSaver(conn=pool)
            await saver.setup()
            graph=graph_builder.compile(checkpointer=saver)
            workflow.get_graph_app=lambda: graph
            thread = "v41-sec-real-" + str(uuid4())
            state={
                "tenant_id":str(authority.tenant_id),
                "project_id":str(project),
                "document_id":str(authority.document_id),
                "document_revision_id":str(authority.revision_id),
                "thread_id":thread,
                "doc_type":doc_type,
                "document_text":safe,
                "anonymized_text":safe,
                "messages":[],
                "node_results":[],
                "confidence_score":None,
                "human_approval_required":True,
                "critique_notes":"",
                "retry_count":0,
                "extracted_risks":candidates,
                "extracted_wbs":[],
                "n12_source_attestation":None,
            }
            result=await graph.ainvoke(
                state,{"configurable":{"thread_id":thread}},
                durability="sync",
            )
            # No automatic reentry if previous call charged or uncertain.
        n4_finance,n3n12_finance,balances=await _ledger_snapshot(
            engine,authority.tenant_id,
        )
        report["n12"]={
            "status":"COMPLETE_OR_UNASSESSED",
            "critic_notes":str(result.get("critique_notes") or ""),
            "confidence":result.get("confidence_score"),
            "human_approval_required":bool(result.get("human_approval_required")),
            "n12_source_attestation_valid":False,
            "node_results":[
                {"node":n.node,"status":str(n.status)}
                for n in result.get("node_results",[])
            ],
        }
        report["n4"]["receipts"]=n4_finance
        report["shared_ledger"]=n3n12_finance
        report["tenant_balance"]=balances
        report["hitl"]={
            "status":"PENDING_INDIVIDUAL_DECISIONS",
            "total_proposed":len(candidates),
            "approved_risk_count":0,
            "rejected_risk_count":0,
            "review_rows":[{
                "finding_key":f["finding_key"],
                "title":f["title"],
                "source_quote":f["source_quote"],
                "source_refs":f["source_refs"],
                "description":f["description"],
                "decision":"PENDING",
            } for f in candidates],
        }
        report["validation"]="N3_N4_N12_LIVE_FINANCIAL_NOT_UAT"
        _save(report,out)
        print("N12_REAL_COMPLETED",
              "HITL_REQUIRED=",bool(result.get("human_approval_required")),
              "N4_CANDIDATES=",len(candidates),flush=True)
    except Exception as exc:
        report["validation"]="NO_GO_PARTIAL_REAL_AI"
        report["failure_code"]=type(exc).__name__
        report["failure_reason"]=str(exc)[:160]
        try:
            receipts, legacy,balance=await _ledger_snapshot(
                engine,authority.tenant_id,
            )
            report["last_n4_receipts"]=receipts
            report["last_legacy_receipts"]=legacy
            report["tenant_balance"]=balance
        except Exception:
            report["ledger_read_failure"]=True
        _save(report,out)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--sec-pdf",required=True,type=Path)
    parser.add_argument("--out-dir",required=True,type=Path)
    args=parser.parse_args()
    asyncio.run(pilot(args.sec_pdf,args.out_dir))
