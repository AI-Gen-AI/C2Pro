"""Independent PostgreSQL verification of the real-AI functional pilot (TS-E2E-REAL-AI-HITL-001), on the SAME project.

Reads three things and trusts none of them alone:
  1. the browser manifest the spec wrote (what the browser saw and did);
  2. PostgreSQL (what the system persisted), read by a separate process through its own connection;
  3. the AI call governor's ledger (what actually left for the provider: calls, models, message ids, tokens, cost).

Verdicts (exit code 1 only for FAIL):
  PASS     every check held and the product offered every capability the scenario needs;
  PARTIAL  every check held but a capability is missing (named, with its concrete blocker) -- never a silent pass;
  FAIL     a persistence, authority, provider-reality or budget guarantee did not hold.

What a PASS or PARTIAL still does NOT prove: S1-S8, the quality of the findings (reported as measurements; the wording of
titles needs a human reviewer), or anything about a second document. Paths are constants: nothing here takes a path from
the command line.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent / "real_ai_governor"))

REPORT_DIR = API_ROOT.parent / "web" / "playwright-report"
MANIFEST_PATH = REPORT_DIR / "real-ai-hitl-vertical.json"
LEDGER_PATH = REPORT_DIR / "real-ai-governor-ledger.jsonl"
VERDICT_PATH = REPORT_DIR / "real-ai-hitl-verdict.json"
FIXTURE_DIR = API_ROOT.parent / "web" / "src" / "tests" / "e2e" / "test-data" / "pj01"
PENDING = {"PENDING_REVIEW_REQUIRED", "PENDING_REVIEW_CONDITIONAL", "ESCALATED"}
CAPABILITIES = {"READ_REVIEW", "REVIEW_FINDING", "APPROVE_CANDIDATE"}


class Checks:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> bool:
        self.items.append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [c for c in self.items if not c["ok"]]


def _norm(action: str | None) -> str | None:
    return action.upper() if action else None


def quality_measurements(risks: list[dict[str, Any]], contract_text: str, expected_categories: set[str]) -> dict[str, Any]:
    """Measurements, not a verdict: what the findings rest on. Title wording is left to a human reviewer."""
    from src.analysis.domain.risk_categories import normalize_category

    quotes = [(r.get("source_quote") or r.get("source_text_snippet") or "").strip() for r in risks]
    contiguous = sum(1 for q in quotes if q and q in contract_text)
    categories = {str(getattr(normalize_category(str(r.get("category"))), "value", r.get("category"))) for r in risks if r.get("category")}
    return {
        "risk_count": len(risks),
        "with_clause_ref": sum(1 for r in risks if r.get("clause_ref")),
        "with_source_quote": sum(1 for q in quotes if q),
        "quotes_contiguous_in_contract": contiguous,
        "quotes_not_contiguous": sum(1 for q in quotes if q) - contiguous,
        "categories": sorted(categories),
        "expected_categories": sorted(expected_categories),
        "missing_categories": sorted(expected_categories - categories),
        "category_coverage_is_not_risk_coverage": True,
        "title_wording": "REQUIRES_HUMAN_REVIEW",
    }


def judge(manifest: dict[str, Any], db: dict[str, Any], ledger: dict[str, Any], limits: dict[str, Any]) -> dict[str, Any]:
    """Pure: the same inputs always give the same verdict."""
    c = Checks()
    gaps = [dict(g) for g in manifest.get("gaps", [])]
    blocker = manifest.get("blocker")

    # -- the browser half -------------------------------------------------------------------------------------------
    c.add("browser: the scenario ran in REAL_AI mode with C2PRO_AI_MOCK=0", manifest.get("mode") == "REAL_AI" and manifest.get("aiMockEnv") == "0")
    c.add("browser: no step failed", manifest.get("failedStep") is None, f"{manifest.get('failedStep')}: {manifest.get('failure')}")

    # -- the provider was real, bounded and recorded -----------------------------------------------------------------
    c.add("provider: at least one real call was admitted and completed", ledger["calls"] >= 1 and ledger["completed"] >= 1, str(ledger["calls"]))
    c.add("provider: no call is still in flight", ledger["in_flight"] == 0)
    c.add("provider: no call was refused by the governor (no cap was hit)", not ledger["refused"], "; ".join(ledger["refused"]))
    c.add("provider: calls within the cap", ledger["calls"] <= limits["max_calls"], f"{ledger['calls']} <= {limits['max_calls']}")
    c.add("provider: spend within the budget", ledger["spent_usd"] <= limits["max_usd"], f"{ledger['spent_usd']} <= {limits['max_usd']} USD")
    c.add("provider: only Claude models answered", bool(ledger["models"]) and all(m.startswith("claude") for m in ledger["models"]), ",".join(ledger["models"]))
    c.add("provider: every completed call has a distinct provider message id", len(ledger["message_ids"]) == ledger["completed"] == len(set(ledger["message_ids"])) and all(ledger["message_ids"]))
    c.add("provider: tokens were billed (input and output > 0)", ledger["input_tokens"] > 0 and ledger["output_tokens"] > 0)

    # -- PostgreSQL: the project, the document, the candidate, the review -------------------------------------------------
    project = db.get("project")
    c.add("pg: the project the browser created exists", bool(project) and str(project["id"]) == manifest.get("projectId"))
    documents = db.get("documents", [])
    c.add("pg: exactly one contract document, the uploaded one", len(documents) == 1 and str(documents[0]["id"]) == manifest.get("documentId") and documents[0]["document_type"] == "contract")
    c.add("pg: the document has a persisted revision", len(db.get("revisions", [])) >= 1)

    if blocker:
        # The scenario could not reach the human decisions: PARTIAL with the concrete blocker, after the checks above held.
        verdict = "FAIL" if c.failed else "PARTIAL"
        return _result(verdict, c, gaps, blocker, {})

    reviews = db.get("reviews", [])
    review = reviews[0] if len(reviews) == 1 else None
    c.add("pg: exactly one review item for the document", review is not None, str(len(reviews)))
    candidate = db.get("candidate")
    c.add("pg: the candidate artifact is PROPOSED (nothing was trusted by a finding decision)", bool(candidate) and candidate["trust_state"] == "proposed", str(candidate and candidate["trust_state"]))
    risks = (candidate or {}).get("risks", [])
    c.add("pg: the real analysis produced at least two findings in the candidate", len(risks) >= 2, str(len(risks)))
    if review is not None:
        c.add("pg: the review is still pending (a finding decision never decides the review)", _norm(review["status"]) in PENDING, str(review["status"]))
        metadata = review.get("review_metadata") or {}
        c.add("pg: the review is bound to the candidate artifact", str(metadata.get("trust_candidate_required")).lower() == "true" and (metadata.get("candidate_binding") or {}).get("artifact_id") == str((candidate or {}).get("artifact_id")))
        c.add("pg: the review row is the one the browser decided on", str(review["id"]) == manifest.get("reviewRowId"))

    # -- authority: enforce + explicit grants -----------------------------------------------------------------------------
    c.add("pg: tenant is in ENFORCE", str(db.get("authorization_mode", "")).lower() == "enforce", str(db.get("authorization_mode")))
    c.add("pg: the three review capabilities are actively granted on THIS project", set(db.get("active_grants", [])) >= CAPABILITIES, ",".join(sorted(db.get("active_grants", []))))

    # -- the decisions ---------------------------------------------------------------------------------------------------
    decisions = db.get("decisions", [])
    by_ordinal = {int(d["source_ordinal"]): d for d in decisions}
    c.add("pg: exactly two decisions are recorded, on ordinals 0 and 1", sorted(by_ordinal) == [0, 1] and len(decisions) == 2, str(sorted(by_ordinal)))
    first, second = by_ordinal.get(0), by_ordinal.get(1)
    c.add("pg: ordinal 0 is CONFIRMED", bool(first) and _norm(first["action"]) == "CONFIRMED")
    c.add("pg: ordinal 1 is DISMISSED with a non-empty typed reason", bool(second) and _norm(second["action"]) == "DISMISSED" and bool((second.get("reason") or "").strip()))
    c.add("pg: both were taken by a named human of this tenant (created_by = reviewer_id, member of the tenant)", bool(decisions) and all(d["created_by"] == d["reviewer_id"] and d["reviewer_is_member"] for d in decisions))
    c.add("pg: the ledger is gap-free and bound to the same candidate and tenant", [int(d["ledger_revision"]) for d in sorted(decisions, key=lambda d: int(d["ledger_revision"]))] == [1, 2] and all(str(d["artifact_id"]) == str((candidate or {}).get("artifact_id")) and str(d["tenant_id"]) == str((project or {}).get("tenant_id")) for d in decisions))

    # -- persistence seen by the browser must equal PostgreSQL --------------------------------------------------------------
    stored = [None, None]
    for ordinal, entry in by_ordinal.items():
        if 0 <= ordinal < 2:
            stored[ordinal] = _norm(entry["action"])
    shown_before = [_norm(a) if a else None for a in manifest.get("persistedActionsBeforeRelogin", [])][:2]
    shown_after = [_norm(a) if a else None for a in manifest.get("persistedActionsAfterRelogin", [])][:2]
    c.add("persistence: the decisions survive a page reload", bool(manifest.get("persistedAfterReload")))
    c.add("persistence: the review was not decided by the finding decisions (browser view)", bool(manifest.get("reviewStillPending")))
    c.add("persistence: the decisions the API showed before and after a NEW login equal PostgreSQL", shown_before == stored == shown_after, f"{shown_before} / {stored} / {shown_after}")
    c.add("persistence: the same Clerk user signed in again and saw them", bool((manifest.get("relogin") or {}).get("sameUser")) and bool((manifest.get("relogin") or {}).get("decisionsVisible")))

    quality = quality_measurements(
        risks, db.get("contract_text", ""), set(db.get("expected_categories", []))
    )
    if risks and quality["with_source_quote"] == 0:
        gaps.append({
            "code": "SOURCE_QUOTE_NOT_PERSISTED_IN_CANDIDATE",
            "detail": f"none of the {len(risks)} persisted findings carries the contract text it rests on (the extractor can return it: first pilot, 6/8 contiguous)",
        })
    verdict = "FAIL" if c.failed else ("PARTIAL" if gaps else "PASS")
    return _result(verdict, c, gaps, blocker, quality)


def _result(verdict: str, c: Checks, gaps: list[dict[str, Any]], blocker: str | None, quality: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_class": "LIVE_PARTIAL_FUNCTIONAL_REAL_AI_HITL",
        "verdict": verdict,
        "claims": "one project: real-AI extraction -> findings in the review UI -> one CONFIRMED + one DISMISSED with reason -> PostgreSQL -> reload/relogin. NOT S1-S8, NOT a quality acceptance of the findings, NOT a final approval.",
        "blocker": blocker,
        "gaps": gaps,
        "checks": c.items,
        "failed_checks": [x["check"] for x in c.failed],
        "quality_measurements": quality,
    }


# ── collection ------------------------------------------------------------------------------------------------------
async def _rows(conn: Any, sql: str, **params: Any) -> list[dict[str, Any]]:
    from sqlalchemy import text

    return [dict(r._mapping) for r in (await conn.execute(text(sql), params)).all()]


async def collect(conn: Any, project_id: UUID) -> dict[str, Any]:
    p = {"p": str(project_id)}
    projects = await _rows(conn, "SELECT id, tenant_id FROM projects WHERE id = cast(:p as uuid)", **p)
    db: dict[str, Any] = {"project": projects[0] if projects else None}
    if not projects:
        return db
    tenant = str(projects[0]["tenant_id"])
    db["documents"] = await _rows(conn, "SELECT id, document_type::text AS document_type FROM documents WHERE project_id = cast(:p as uuid)", **p)
    db["revisions"] = await _rows(conn, "SELECT revision_id FROM document_revisions WHERE project_id = cast(:p as uuid)", **p)
    db["reviews"] = await _rows(
        conn, "SELECT id, upper(current_status::text) AS status, review_metadata FROM review_items WHERE project_id = cast(:p as uuid)", **p
    )
    artifacts = await _rows(
        conn,
        "SELECT artifact_id, trust_state, payload -> 'extracted_risks' AS risks FROM document_artifacts "
        "WHERE project_id = cast(:p as uuid) AND payload ? 'extracted_risks' ORDER BY artifact_version DESC",
        **p,
    )
    if artifacts:
        raw = artifacts[0]["risks"]
        db["candidate"] = {
            "artifact_id": artifacts[0]["artifact_id"],
            "trust_state": str(artifacts[0]["trust_state"]).lower(),
            "risks": [dict(r) for r in (json.loads(raw) if isinstance(raw, str) else raw or []) if isinstance(r, dict)],
        }
    db["authorization_mode"] = (
        await _rows(conn, "SELECT coalesce(settings #>> '{hitl_project_authorization,mode}', 'enforce') AS mode FROM tenants WHERE id = cast(:t as uuid)", t=tenant)
    )[0]["mode"]
    db["active_grants"] = [
        r["permission"]
        for r in await _rows(
            conn,
            "SELECT permission::text AS permission FROM public.project_review_grants WHERE project_id = cast(:p as uuid) AND revoked_at IS NULL",
            **p,
        )
    ]
    db["decisions"] = await _rows(
        conn,
        "SELECT d.review_row_id, d.artifact_id, d.tenant_id, d.source_ordinal, d.action, d.reason, d.reviewer_id, d.created_by, d.ledger_revision, "
        "EXISTS (SELECT 1 FROM users u WHERE u.tenant_id = d.tenant_id AND (u.id::text = d.reviewer_id OR u.clerk_user_id = d.reviewer_id)) AS reviewer_is_member "
        "FROM public.hitl_finding_decisions d WHERE d.project_id = cast(:p as uuid) ORDER BY d.ledger_revision",
        **p,
    )
    contract = FIXTURE_DIR / "contract-a.source.txt"
    db["contract_text"] = contract.read_text(encoding="utf-8")
    expected = json.loads((FIXTURE_DIR / "contract-a.manifest.json").read_text(encoding="utf-8"))["expected_health"]["categories"]
    from src.analysis.domain.risk_categories import normalize_category

    db["expected_categories"] = sorted({str(getattr(normalize_category(name), "value", name)) for name in expected})
    return db


def _ledger_summary() -> dict[str, Any]:
    from real_ai_governor import read_events, summarize

    return summarize(read_events(LEDGER_PATH))


async def _run() -> dict[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    limits = {"max_calls": int(os.environ["C2PRO_AI_GOVERNOR_MAX_CALLS"]), "max_usd": float(os.environ["C2PRO_AI_GOVERNOR_MAX_USD"])}
    raw = os.environ["DATABASE_URL"]
    url = raw.replace("postgresql://", "postgresql+asyncpg://", 1) if raw.startswith("postgresql://") else raw
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            db = await collect(conn, UUID(manifest["projectId"])) if manifest.get("projectId") else {"project": None}
    finally:
        await engine.dispose()
    return judge(manifest, db, _ledger_summary(), limits)


def main() -> int:
    result = asyncio.run(_run())
    VERDICT_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("verdict", "blocker", "failed_checks", "gaps")}, indent=2, default=str))
    print(json.dumps({"ledger": _ledger_summary(), "quality": result["quality_measurements"]}, indent=2, default=str))
    return 1 if result["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
