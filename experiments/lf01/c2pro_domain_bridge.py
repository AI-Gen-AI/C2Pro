#!/usr/bin/env python3
"""LF-01 real, writable C2Pro N4/N12-domain lab bridge.

Executes imports from the unmodified, SHA-pinned C2Pro source snapshot.
All writes are to the LF01 private SQLite store. No upstream C2Pro mutations.
No LangGraph orchestration is simulated; statuses are explicit.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE_DIR = Path(os.environ.get("LF01_C2PRO_SRC", "/home/lf01lab/c2pro-source"))
sys.path.insert(0, str(SOURCE_DIR))
from src.analysis.domain.n4_source_windows import plan_n4_source_windows
from src.analysis.domain.n4_compact_window_response import (
    N4_WINDOW_SYSTEM_PROMPT, n4_window_source_message, parse_n4_window_output
)
from src.analysis.domain.n12_source_attestation import is_n12_source_attestation_valid

BASE = Path(os.environ.get("LF01_BRIDGE_DIR", "/home/lf01lab/bridge"))
DB = BASE / "c2pro-lf01-lab.sqlite"
TOKEN_FILE = Path(os.environ.get("LF01_BRIDGE_TOKEN_FILE", "/home/lf01lab/lf01-config/bridge_token"))
BIND = os.environ.get("LF01_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("LF01_BRIDGE_PORT", "17861"))
LOCK = threading.RLock()
MAX_BODY = 5_000_000
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, created_at REAL NOT NULL, document_kind TEXT NOT NULL,
 source_sha TEXT NOT NULL, original_text TEXT NOT NULL, revision_id TEXT,
 core_count INTEGER NOT NULL, max_context_chars INTEGER NOT NULL,
 overlap_chars INTEGER NOT NULL, source_module_sha TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS windows (
 run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, core_start INTEGER,
 core_end INTEGER, context_start INTEGER, context_end INTEGER,
 context_sha TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'PLANNED',
 response TEXT, parsed TEXT, updated_at REAL,
 PRIMARY KEY (run_id,ordinal),
 FOREIGN KEY (run_id) REFERENCES runs(id)
);
CREATE TABLE IF NOT EXISTS lab_reviews (
 run_id TEXT NOT NULL, candidate_key TEXT NOT NULL, verdict TEXT NOT NULL,
 comment TEXT, reviewed_at REAL NOT NULL,
 PRIMARY KEY (run_id,candidate_key)
);
CREATE TABLE IF NOT EXISTS n12_checks (
 id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
 evidence_valid INTEGER NOT NULL, checked_at REAL NOT NULL
);
"""

def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def src_sha() -> str:
    return hashlib.sha256((SOURCE_DIR/"src/analysis/domain/n4_source_windows.py").read_bytes()).hexdigest()

def windows_from_run(db, run):
    return plan_n4_source_windows(
        run["original_text"], revision_id=run["revision_id"],
        max_context_chars=run["max_context_chars"],
        overlap_chars=run["overlap_chars"])

def public_run(db, run_id, details=False):
    run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise LookupError("run not found")
    ws = db.execute("SELECT ordinal,core_start,core_end,context_start,context_end,context_sha,status,parsed FROM windows WHERE run_id=? ORDER BY ordinal", (run_id,)).fetchall()
    ret = {
        "run_id":run["id"],"created_at":run["created_at"],
        "document_kind":run["document_kind"],"revision_id":run["revision_id"],
        "model_safe_source_sha":run["source_sha"],"windows_total":run["core_count"],
        "states": {s:sum(1 for w in ws if w["status"]==s) for s in ["PLANNED","EXAMINED","BLOCKED"]},
        "real_c2pro_n4_source_module_sha256":run["source_module_sha"],
        "N1_N2":"EXTERNAL_MODEL_SAFE_TEXT_SUPPLIED_NOT_VALIDATED",
        "N3":"NOT_RUN","N4":"REAL_C2PRO_N4_DOMAIN_CODE",
        "N12":"ATTESTATION_CHECK_ONLY_NOT_FULL_N12",
        "HITL":"LAB_REVIEW_ONLY_NOT_C2PRO_HITL",
        "ProjectGraph":"NOT_CONNECTED","Coherence":"NOT_CONNECTED",
        "production_changes":False,"persistent_lab_changes":True
    }
    if details:
        ret["windows"]=[{
            "ordinal":w["ordinal"],"core_start":w["core_start"],"core_end":w["core_end"],
            "context_start":w["context_start"],"context_end":w["context_end"],
            "context_sha256":w["context_sha"],"status":w["status"],
            "parsed":json.loads(w["parsed"]) if w["parsed"] else None
        } for w in ws]
        ret["lab_reviews"]=[dict(row) for row in db.execute("SELECT candidate_key,verdict,comment,reviewed_at FROM lab_reviews WHERE run_id=?", (run_id,))]
        ret["n12_attestation_checks"]=[dict(row) for row in db.execute("SELECT evidence_valid,checked_at FROM n12_checks WHERE run_id=?", (run_id,))]
    return ret

def plan_run(data):
    text = data.get("model_safe_text", "")
    if not isinstance(text,str) or len(text)>MAX_BODY:
        raise ValueError("model_safe_text must be string up to 5 MB")
    max_chars = int(data.get("max_context_chars",12000))
    overlap = int(data.get("overlap_chars",400))
    revision_id = data.get("revision_id")
    source_kind = str(data.get("document_kind","contract"))
    if len(source_kind)>60: raise ValueError("document_kind too long")
    ws = plan_n4_source_windows(text, revision_id=revision_id,
                               max_context_chars=max_chars, overlap_chars=overlap)
    run_id = str(uuid.uuid4())
    with LOCK, connect() as db:
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)",
                   (run_id,time.time(),source_kind,ws[0].source_sha256,
                    text,revision_id,len(ws),max_chars,overlap,src_sha()))
        for w in ws:
            db.execute("INSERT INTO windows (run_id,ordinal,core_start,core_end,context_start,context_end,context_sha,status) VALUES (?,?,?,?,?,?,?,'PLANNED')",
                       (run_id,w.ordinal,w.core_start,w.core_end,w.context_start,w.context_end,w.context_sha256))
        return public_run(db,run_id,details=True)

def parse_window(data, infer=False):
    run_id = str(data.get("run_id",""))
    ordinal = int(data.get("ordinal",-1))
    with LOCK,connect() as db:
        run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:raise LookupError("run not found")
        ws = windows_from_run(db,run)
        if ordinal<0 or ordinal>=len(ws):raise ValueError("invalid ordinal")
        window = ws[ordinal]
        if window.source_sha256 != run["source_sha"]:
            raise RuntimeError("source has changed since run creation")
        if infer:
            model = str(data.get("model","qwen3:4b-instruct"))
            if model not in ("qwen3:4b-instruct","qwen3:8b-q4_K_M","ministral-3:3b"):
                raise ValueError("local model not allowlisted")
            request = {
                "model":model,"stream":False,"format":"json",
                "options":{"temperature":0,"num_predict":4096},
                "messages":[
                    {"role":"system","content":N4_WINDOW_SYSTEM_PROMPT},
                    {"role":"user","content":n4_window_source_message(window)}
                ]}
            url = "http://127.0.0.1:11434/api/chat"
            q = Request(url,json.dumps(request).encode(),headers={"Content-Type":"application/json"})
            with urlopen(q,timeout=180) as out:
                model_result=json.load(out)
            raw=model_result.get("message",{}).get("content","")
        else:
            raw=data.get("response")
        try:
            parsed=parse_n4_window_output(raw,window=window)
            payload={
                "window_ordinal":parsed.window_ordinal,
                "reported_examined":parsed.reported_examined,
                "source_coverage_state":parsed.source_coverage_state,
                "proposed_findings":list(parsed.proposed_findings),
                "outstanding_references":list(parsed.outstanding_references),
                "can_commit_as_examined":parsed.can_commit_as_examined,
            }
            status = "EXAMINED" if parsed.can_commit_as_examined else "BLOCKED"
        except Exception as exc:
            # Preserve failures, never convert malformed output to empty findings.
            payload={"error_type":type(exc).__name__,"error":str(exc)[:220]}
            status="BLOCKED"
        db.execute("UPDATE windows SET status=?,response=?,parsed=?,updated_at=? WHERE run_id=? AND ordinal=?",
                   (status,json.dumps(raw),json.dumps(payload),time.time(),run_id,ordinal))
        return {"run_id":run_id,"ordinal":ordinal,"window_status":status,"result":payload,
                "source":"REAL_C2PRO_N4_DOMAIN_CODE",
                "inference":"LOCAL_OLLAMA" if infer else "CALLER_SUPPLIED_RESPONSE",
                "persisted":True}

def n12_check(data):
    run_id=str(data.get("run_id",""))
    with LOCK,connect() as db:
        run=db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:raise LookupError("run not found")
        state=data.get("state")
        if not isinstance(state,dict):raise ValueError("state must be object")
        valid=is_n12_source_attestation_valid(state,source_text=run["original_text"])
        db.execute("INSERT INTO n12_checks (run_id,evidence_valid,checked_at) VALUES (?,?,?)",
                   (run_id,int(valid),time.time()))
        return {"run_id":run_id,"attestation_valid":valid,"persisted":True,
                "validation":"REAL_C2PRO_N12_SOURCE_ATTESTATION_FUNCTION",
                "full_N12_critique":"NOT_EXECUTED"}

def review(data):
    run_id=str(data.get("run_id",""))
    key=str(data.get("candidate_key",""))
    verdict=str(data.get("verdict","")).upper()
    if verdict not in ("APPROVE","REJECT","REOPEN"):raise ValueError("unknown lab verdict")
    if not key or len(key)>256:raise ValueError("candidate_key required")
    with LOCK,connect() as db:
        if not db.execute("SELECT id FROM runs WHERE id=?",(run_id,)).fetchone():
            raise LookupError("run not found")
        findings=db.execute("SELECT parsed FROM windows WHERE run_id=? AND parsed IS NOT NULL",(run_id,)).fetchall()
        keys=set()
        for row in findings:
            for f in json.loads(row[0]).get("proposed_findings",[]):
                if isinstance(f,dict):keys.add(str(f.get("finding_key") or f.get("key") or ""))
        if key not in keys:raise ValueError("candidate key not in run's real N4 results")
        if verdict=="REOPEN":
            db.execute("DELETE FROM lab_reviews WHERE run_id=? AND candidate_key=?",(run_id,key))
        else:
            db.execute("INSERT INTO lab_reviews VALUES (?,?,?,?,?) ON CONFLICT(run_id,candidate_key) DO UPDATE SET verdict=excluded.verdict,comment=excluded.comment,reviewed_at=excluded.reviewed_at",
                       (run_id,key,verdict,str(data.get("comment",""))[:800],time.time()))
        return {"run_id":run_id,"candidate_key":key,"verdict":verdict,"persisted":True,
                "boundary":"LF01_TEST_DATABASE_NOT_C2PRO_PRODUCTION_HITL"}

def dispatch(method,path,body):
    if method=="GET" and path=="/health":
        return {"ok":True,"service":"lf01-c2pro-bridge","version":"1.0",
                "n4_c2pro_domain_sha256":src_sha(),"write_target":"lf01_private_sqlite",
                "real_code_modules":["n4_source_windows","n4_compact_window_response","n12_source_attestation"],
                "production":"not_connected"}
    if method=="GET" and path=="/v1/runs":
        with connect() as db:
            ids=[r[0] for r in db.execute("SELECT id FROM runs ORDER BY created_at DESC LIMIT 30")]
            return {"runs":[public_run(db,x) for x in ids]}
    if method=="GET" and path.startswith("/v1/runs/"):
        with connect() as db:
            return public_run(db,path[len("/v1/runs/"):],details=True)
    if method=="POST" and path=="/v1/n4/plan":return plan_run(body)
    if method=="POST" and path=="/v1/n4/parse":return parse_window(body)
    if method=="POST" and path=="/v1/n4/infer":return parse_window(body,infer=True)
    if method=="POST" and path=="/v1/n12/verify":return n12_check(body)
    if method=="POST" and path=="/v1/lab/review":return review(body)
    raise LookupError("unknown endpoint")

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass # No contract snippets or credentials in HTTP server logs.
    def reply(self,code,obj):
        raw=json.dumps(obj,ensure_ascii=False,default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)
    def serve(self,method):
        if self.path=="/health" and method=="GET":
            return self.reply(200,dispatch("GET",self.path,{}))
        expected=TOKEN_FILE.read_text().strip()
        actual=self.headers.get("X-LF01-Token","")
        if not hmac.compare_digest(expected,actual):
            return self.reply(401,{"error":"unauthorized"})
        try:
            body={}
            if method=="POST":
                length=int(self.headers.get("Content-Length","0"))
                if not 0<length<=MAX_BODY:return self.reply(413,{"error":"body size"})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError("JSON object required")
            result=dispatch(method,self.path.split("?")[0],body)
            return self.reply(200,result)
        except (LookupError,ValueError) as exc:
            return self.reply(400,{"error":str(exc)[:200]})
        except Exception as exc:
            return self.reply(500,{"error_type":type(exc).__name__,"error":str(exc)[:160]})
    def do_GET(self):self.serve("GET")
    def do_POST(self):self.serve("POST")

if __name__=="__main__":
    BASE.mkdir(mode=0o700,parents=True,exist_ok=True)
    with connect() as db:
        db.executescript(SCHEMA)
        db.execute("PRAGMA journal_mode=WAL")
    print("LF01 C2Pro domain bridge starting, localhost-only; code-sha="+src_sha()[:12],flush=True)
    ThreadingHTTPServer((BIND,PORT),Handler).serve_forever()
