"""N4 diagnostic graph: original G2 planner/parser + configurable local inference.

Independent laboratory only: it does not execute N4IncrementalRunner's cost
ledger, C2Pro N1/N2/N3, N12 critique or HITL. Never claim that it does.
Original domain modules are byte-identical copies from G2 SHA 916808c5.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from hashlib import sha256
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_SYSTEM_PROMPT,
    n4_window_source_message,
    parse_n4_window_output,
)

OLLAMA = "http://127.0.0.1:11434"

class N4DiagnosticContext(TypedDict, total=False):
    model_name: str
    system_prompt: str
    temperature: float
    max_output_tokens: int
    max_context_chars: int
    overlap_chars: int
    use_local_model: bool

class N4DiagnosticState(TypedDict, total=False):
    model_safe_text: str
    revision_id: str
    window_index: int
    response_text: str
    run_label: str
    window_count: int
    full_source_sha256: str
    window_info: dict[str, Any]
    effective_config: dict[str, Any]
    request_system_prompt: str
    request_user_prompt: str
    raw_model_response: str
    model_receipt: dict[str, Any]
    findings: list[dict[str, Any]]
    outstanding_references: list[str]
    response_status: str
    coverage_status: str
    error: str


def _window(state: N4DiagnosticState):
    cfg = state["effective_config"]
    windows = plan_n4_source_windows(
        state["model_safe_text"],
        revision_id=state.get("revision_id"),
        max_context_chars=cfg["max_context_chars"],
        overlap_chars=cfg["overlap_chars"],
    )
    index=state.get("window_index",0)
    if not isinstance(index,int) or not (0 <= index < len(windows)):
        raise ValueError("window_index out of range; inspect window_count")
    return windows[index]


def inventory(state: N4DiagnosticState, runtime: Runtime[N4DiagnosticContext]):
    cfg = runtime.context or {}
    text=state.get("model_safe_text")
    if not isinstance(text,str) or not text.strip():
        raise ValueError("model_safe_text is required (exact N2-safe text, not original PDF)")
    if len(text)>5_000_000:raise ValueError("5M chars per lab run maximum")
    max_chars=int(cfg.get("max_context_chars",12000))
    overlap=int(cfg.get("overlap_chars",400))
    if max_chars>200000:raise ValueError("max_context_chars above lab safety max")
    windows=plan_n4_source_windows(text,revision_id=state.get("revision_id"),
                                   max_context_chars=max_chars,overlap_chars=overlap)
    index=state.get("window_index",0)
    if not isinstance(index,int) or not 0<=index<len(windows):
        raise ValueError(f"window_index {index!r} not within 0..{len(windows)-1}")
    output_cap=int(cfg.get("max_output_tokens",2048))
    if not 128<=output_cap<=8192:raise ValueError("max_output_tokens outside lab allowed range")
    temperature=float(cfg.get("temperature",0.0))
    if not 0<=temperature<=2:raise ValueError("temperature must be between 0 and 2")
    effective={
        "max_context_chars":max_chars,"overlap_chars":overlap,
        "max_output_tokens":output_cap,"temperature":temperature,
        "model_name":str(cfg.get("model_name","qwen3:4b-instruct")),
        "use_local_model":bool(cfg.get("use_local_model",False)),
        "system_prompt_overridden":bool(cfg.get("system_prompt")),
    }
    window=windows[index]
    return {
        "window_count":len(windows),
        "full_source_sha256":window.source_sha256,
        "effective_config":effective,
        "window_info":{
            "ordinal":window.ordinal,"core_start":window.core_start,
            "core_end":window.core_end,"context_start":window.context_start,
            "context_end":window.context_end,"context_sha256":window.context_sha256,
            "text_length":len(window.context_text),
            "source_kind":"N2_MODEL_SAFE_PROJECTION_NOT_PDF_AUTHENTICATED",
            "core_inventory_gap_free":True,
            "inspected_windows":1
        },
        "request_system_prompt":str(cfg.get("system_prompt") or N4_WINDOW_SYSTEM_PROMPT),
        "request_user_prompt":n4_window_source_message(window),
        "response_status":"PLANNED",
        "coverage_status":"MODEL_NOT_YET_RUN",
    }


def _infer_local(*,model:str,prompt:str,source:str,max_output_tokens:int,temperature:float):
    with urllib.request.urlopen(OLLAMA+"/api/tags",timeout=7) as res:
        model_names={m["name"] for m in json.load(res).get("models",[])}
    if model not in model_names:
        raise ValueError("model not available in local Ollama; no model auto-pull")
    payload={
        "model":model,"stream":False,"format":"json",
        "options":{"temperature":temperature,"num_predict":max_output_tokens},
        "messages":[{"role":"system","content":prompt},{"role":"user","content":source}]
    }
    request=urllib.request.Request(OLLAMA+"/api/chat",
             data=json.dumps(payload,ensure_ascii=False).encode(),
             headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(request,timeout=180) as res:
        response=json.load(res)
    msg=response.get("message") or {}
    return {
        "content":str(msg.get("content") or ""),
        "model":str(response.get("model") or model),
        "done_reason":response.get("done_reason"),
        "prompt_eval_count":response.get("prompt_eval_count"),
        "eval_count":response.get("eval_count"),
        "provider":"OLLAMA_LOCAL_NO_EXTERNAL_API",
    }


async def inference(state: N4DiagnosticState, runtime: Runtime[N4DiagnosticContext]):
    cfg=state["effective_config"]
    if not cfg["use_local_model"]:
        raw=state.get("response_text","")
        return {"raw_model_response":raw,
                "model_receipt":{"provider":"REPLAY_SUPPLIED_RESPONSE","cost_usd":0},
                "response_status":"RESPONSE_RECEIVED" if raw else "NO_RESPONSE",
                "coverage_status":"REPLAY_ONLY_NOT_MODEL_INFERENCE"}
    try:
        receipt=await asyncio.to_thread(
            _infer_local,
            model=cfg["model_name"],
            prompt=state["request_system_prompt"],
            source=state["request_user_prompt"],
            max_output_tokens=cfg["max_output_tokens"],
            temperature=cfg["temperature"],
        )
        return {"raw_model_response":receipt["content"],"model_receipt":{
            k:v for k,v in receipt.items() if k!="content"},
            "response_status":"RESPONSE_RECEIVED",
            "coverage_status":"LOCAL_MODEL_EXECUTED_NOT_SEMANTICALLY_ATTESTED"}
    except Exception as exc:
        return {"raw_model_response":"",
                "model_receipt":{"provider":"OLLAMA_LOCAL","error_type":type(exc).__name__},
                "response_status":"MODEL_FAILURE","error":str(exc)[:240],
                "coverage_status":"MODEL_CALL_FAILED"}


def exact_parser(state: N4DiagnosticState):
    raw=state.get("raw_model_response")
    if not raw:
        return {"response_status":"BLOCKED_NO_RESPONSE","findings":[],
                "outstanding_references":[],
                "coverage_status":"NOT_EXAMINED"}
    try:
        result=parse_n4_window_output(raw,window=_window(state))
        if result.can_commit_as_examined:
            status="EXAMINED_WINDOW_ONLY"
        else:
            status="PARTIAL_OR_REFERENCES_OPEN"
        return {
            "response_status":status,
            "coverage_status":str(result.source_coverage_state),
            "findings":list(result.proposed_findings),
            "outstanding_references":list(result.outstanding_references),
            "model_receipt":{**state.get("model_receipt",{}),
              "reported_window_examined":result.reported_examined,
              "may_mark_window_examined":result.can_commit_as_examined,
              "original_pdf_verified":False,
              "full_c2pro_journey_executed":False,
            },
        }
    except Exception as exc:
        return {"response_status":"BLOCKED_INVALID_PROVIDER_OUTPUT","findings":[],
          "outstanding_references":[],"coverage_status":"NOT_EXAMINED",
          "error":f"{type(exc).__name__}: {str(exc)[:220]}"}


def build_n4_diagnostic(config=None):
    workflow=StateGraph(N4DiagnosticState,context_schema=N4DiagnosticContext)
    workflow.add_node("n4_real_g2_source_windows",inventory)
    workflow.add_node("n4_local_llm_or_exact_replay",inference)
    workflow.add_node("n4_real_g2_output_parser",exact_parser)
    workflow.add_edge(START,"n4_real_g2_source_windows")
    workflow.add_edge("n4_real_g2_source_windows","n4_local_llm_or_exact_replay")
    workflow.add_edge("n4_local_llm_or_exact_replay","n4_real_g2_output_parser")
    workflow.add_edge("n4_real_g2_output_parser",END)
    return workflow.compile()
