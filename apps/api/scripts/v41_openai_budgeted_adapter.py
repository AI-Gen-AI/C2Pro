"""Bounded OpenAI Responses adapter, isolated V4.1 real-provider QA only.

One network POST per attempt. No SDK retries, continuation or cache.
PG escrow is the financial source of truth; this cross-process governor adds
a GLOBAL 30-call / $5 ceiling. Prices are estimates from metered token counts,
NOT externally reconciled invoicing.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx

from src.analysis.application.n4_incremental_runner import N4ProviderReceipt
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
)

MODEL = "gpt-4.1"
INPUT_USD_M = Decimal("2.00")
OUTPUT_USD_M = Decimal("10.00")  # conservative output rate for this QA
MAX_USD = Decimal("5.00")
MAX_CALLS = 30


class OpenAIProviderFailure(RuntimeError):
    """Uncertain paid request; caller must not retry the same operation."""


def _dollars(input_tokens: int, output_tokens: int) -> Decimal:
    return (Decimal(input_tokens)*INPUT_USD_M + Decimal(output_tokens)*OUTPUT_USD_M) / Decimal(1_000_000)


class OpenAIBudgetedTransport:
    def __init__(self, api_key: str):
        if not api_key:
            raise PermissionError("S2 dedicated OpenAI key not supplied")
        root = Path(os.environ.get("GITHUB_WORKSPACE","")).resolve()
        if not root.is_dir() or not os.environ.get("GITHUB_SHA"):
            raise PermissionError("OpenAI QA only allowed inside GitHub Actions")
        self.ledger = root / "apps/api/c2pro-v41-openai-governor.jsonl"
        self.api_key=api_key
        self.model_name=MODEL

    def _event(self, event: dict):
        ledger=self.ledger
        ledger.parent.mkdir(parents=True,exist_ok=True)
        lock=ledger.with_suffix(".jsonl.lock")
        with open(lock,"a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                records=[]
                if ledger.exists():
                    records=[json.loads(x) for x in ledger.read_text().splitlines() if x.strip()]
                if event["ev"] == "reserve":
                    reserved={r["id"]:r for r in records if r["ev"]=="reserve"}
                    complete={r["id"]:r for r in records if r["ev"]=="done"}
                    if len(reserved) >= MAX_CALLS:
                        raise PermissionError("OPENAI_GLOBAL_CALL_CAP")
                    known=sum((Decimal(str(r["cost_estimated_usd"])) for r in complete.values()),Decimal(0))
                    open_held=sum((
                        Decimal(str(v["estimated_max_usd"]))
                        for k,v in reserved.items() if k not in complete
                    ),Decimal(0))
                    # Even failed calls retain their worst-case liability.
                    if known+open_held+Decimal(str(event["estimated_max_usd"])) > MAX_USD:
                        raise PermissionError("OPENAI_GLOBAL_BUDGET_CAP")
                with open(ledger,"a",encoding="utf-8") as out:
                    out.write(json.dumps(event,sort_keys=True)+"\n")
            finally:
                fcntl.flock(handle,fcntl.LOCK_UN)

    async def request(
        self, *, system: str, prompt: str, max_tokens: int,
        schema: dict | None, request_id: str,
    ) -> SimpleNamespace:
        if not (256 <= max_tokens <= 4096):
            raise ValueError("OPENAI_OUTPUT_TOKENS_NOT_BOUNDED")
        if not request_id or len(request_id)>128:
            raise ValueError("OPENAI_STABLE_REQUEST_ID_REQUIRED")
        # Worst-case text tokenization estimate 2 chars/token, not a bill.
        est_tokens=(len(system)+len(prompt)+1)//2+1
        worst=_dollars(est_tokens,max_tokens)
        call_id=str(uuid4())
        self._event({"ev":"reserve","id":call_id,"request_id_sha256":__import__("hashlib").sha256(request_id.encode()).hexdigest(),
                     "model":MODEL,"estimated_max_usd":str(worst),"time":time.time()})
        body={
            "model":MODEL,"store":False,"instructions":system,
            "input":[{"role":"user","content":prompt}],
            "max_output_tokens":max_tokens,
            "text":{"format":schema if schema else {"type":"json_object"}},
        }
        try:
            async with httpx.AsyncClient(timeout=120,follow_redirects=False) as client:
                resp=await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization":f"Bearer {self.api_key}"},
                    json=body,
                )
            if resp.status_code >= 400:
                try:
                    error=(resp.json() or {}).get("error") or {}
                except (ValueError, TypeError):
                    error={}
                # Status/type/code/param only; never log provider echo of input.
                raise OpenAIProviderFailure(
                    f"OPENAI_HTTP_{resp.status_code}:"
                    f"{str(error.get('type') or 'unknown')[:50]}:"
                    f"{str(error.get('code') or 'unknown')[:50]}:"
                    f"{str(error.get('param') or 'none')[:50]}"
                )
            payload=resp.json()
            usage=payload.get("usage") or {}
            it=usage.get("input_tokens")
            ot=usage.get("output_tokens")
            if type(it) is not int or type(ot) is not int or it<=0 or ot<=0:
                raise OpenAIProviderFailure("OPENAI_METERED_USAGE_UNAVAILABLE")
            cost=_dollars(it,ot)
            returned_model=str(payload.get("model") or "")
            if not (returned_model==MODEL or returned_model.startswith(MODEL+"-")):
                failure=OpenAIProviderFailure("OPENAI_MODEL_DRIFT")
                failure.cost_usd=cost
                failure.input_tokens=it
                failure.output_tokens=ot
                raise failure
            text="".join(
                c.get("text","")
                for out in (payload.get("output") or [])
                if out.get("type")=="message"
                for c in out.get("content",[])
                if c.get("type")=="output_text"
            )
            self._event({
                "ev":"done","id":call_id,"model":payload.get("model",MODEL),
                "request_id":str(payload.get("id") or "")[:100],
                "input_tokens":it,"output_tokens":ot,
                "cost_estimated_usd":str(cost),
                "status":payload.get("status"),"time":time.time(),
            })
            if cost > worst:
                failure=OpenAIProviderFailure("OPENAI_ACTUAL_USAGE_EXCEEDS_WORST_CASE")
                failure.cost_usd=cost
                failure.input_tokens=it
                failure.output_tokens=ot
                raise failure
            if payload.get("status")!="completed" or not text:
                e=OpenAIProviderFailure("OPENAI_INCOMPLETE_OR_EMPTY_RESPONSE")
                e.cost_usd=cost
                e.input_tokens=it
                e.output_tokens=ot
                raise e
            return SimpleNamespace(
                content=text,model_used=MODEL,input_tokens=it,
                output_tokens=ot,cost_usd=cost,request_id=payload.get("id"),
                cached=False,continuations=0,latency_ms=0.0,
            )
        except Exception as exc:
            self._event({"ev":"fail","id":call_id,"error":type(exc).__name__,"time":time.time()})
            raise


class OpenAICompatWrapper:
    enable_cache=False
    cache_service=None
    llm_client=SimpleNamespace(max_retries=0)

    def __init__(self, transport: OpenAIBudgetedTransport):
        self.transport=transport

    async def generate(self, request):
        return await self.transport.request(
            system=str(request.system_prompt or "")+"\nReply using valid JSON.",
            # Responses JSON mode validates the USER input, not only instructions.
            prompt="Return a valid JSON object.\n\n"+str(request.prompt),
            max_tokens=int(getattr(request,"max_tokens",None) or 1024),
            schema=None,request_id=str(request.request_id),
        )


_N4_SCHEMA={
    "type":"json_schema","name":"c2pro_v41_n4_window","strict":True,
    "schema":{
        "type":"object","additionalProperties":False,
        "properties":{
            "window_examined":{"type":"boolean"},
            "findings":{
                "type":"array","items":{
                    "type":"object","additionalProperties":False,
                    "properties":{
                        "title":{"type":"string"},
                        "category":{"type":"string"},
                        "risk_reason":{"type":"string"},
                        "source_quote":{"type":"string"},
                        "clause_ref":{"type":["string","null"]},
                        "impact":{"type":["string","null"]},
                    },
                    "required":["title","category","risk_reason","source_quote","clause_ref","impact"],
                },
            },
            "outstanding_references":{"type":"array","items":{"type":"string"}},
        },
        "required":["window_examined","findings","outstanding_references"],
    },
}


class OpenAIWindowProvider:
    def __init__(self, transport: OpenAIBudgetedTransport):
        self.transport=transport
        self.model_name=MODEL

    async def generate(self, *, window, tenant_id: UUID, request_id: str):
        if tenant_id is None or not window.revision_id:
            raise ValueError("N4_TENANT_REVISION_REQUIRED")
        response=await self.transport.request(
            system=N4_WINDOW_SYSTEM_PROMPT,
            prompt=n4_window_source_message(window),
            max_tokens=4096,schema=_N4_SCHEMA,request_id=request_id,
        )
        return N4ProviderReceipt(
            content=response.content,model_used=self.model_name,
            reported_cost_usd=str(response.cost_usd),
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            provider_request_id=response.request_id or request_id,
        )
