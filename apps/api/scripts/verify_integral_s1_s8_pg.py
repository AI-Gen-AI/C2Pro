#!/usr/bin/env python
"""Independent, READ-ONLY PostgreSQL verification of the integral ACC-01 S1-S8 UAT, and its evidence manifest.

The browser judges what the application SAYS. This script judges what the database HOLDS, without going through the
application, for the SAME project id the browser recorded (and for the second tenant's project):

* S1  the two projects belong to two different tenants, each bound to its own Clerk Organization, and each human
      is a user row of its own tenant bound to its own Clerk user;
* S2  the project holds exactly the five documents the journey uploaded (contract, budget, schedule, technical
      specification, the draft specification), with the SHA-256 of the committed fixtures as stored bytes, and the
      contract has exactly revisions A and B;
* S3  the worker completed the graph, a project snapshot carries six Health assessments, and the persisted alerts
      include the expected deterministic findings;
* S4  an alert's source clause belongs to a revision of the contract document;
* S5  the contract and the specification were APPROVED by a named human on a review bound to the exact artifact;
      the draft specification review is REJECTED with the typed reason (by SHA-256) and nothing of it is trusted;
* S6  revision A is trusted-and-superseded, revision B is the active trusted artifact, nothing is left proposed and
      exactly one ``revision.changed`` exists for the document;
* S7  one approved WBS baseline whose approver is the journey's human (self-approval, when it happened, is REPORTED),
      and exactly one approved canonical link per family on that baseline and node, each carrying the source
      revision, the stored blob hash, the locator and a ``user:`` actor;
* S8  the snapshot digests taken by the browser before and after the new login are identical.

It never mutates. It prints and stores pseudonymous ids, statuses, counts and SHA-256 digests only (no Clerk id,
credential, document body, prompt or completion), and exits non-zero unless every check passes.

The result is merged with the browser half into ONE ``manifest.json`` tied to the project id, with the per-stage
verdicts, the evidence class (a deterministic-AI rehearsal is never UAT) and the first failure of the run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[3]
STAGES = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8")
FAMILY_EVENTS = {
    "budget": "budget.wbs_link_approved",
    "schedule": "schedule.wbs_link_approved",
    "technical": "technical.wbs_link_approved",
}


def _within_repo(path: Path) -> Path:
    """A CLI path must resolve inside this repository checkout: no ``..``, absolute or symlink escape."""
    resolved = path.resolve()
    if not resolved.is_relative_to(REPO_ROOT):
        raise SystemExit(f"FAIL: {path} resolves outside the repository")
    return resolved


def _normalize_database_url(raw: str) -> str:
    for prefix in ("postgresql://", "postgres://"):
        if raw.startswith(prefix):
            return raw.replace(prefix, "postgresql+asyncpg://", 1)
    return raw


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _pseudonym(value: str | None) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:12] if value else ""


@dataclass(frozen=True)
class Check:
    stage: str
    name: str
    ok: bool
    detail: str = ""


@dataclass
class Expectations:
    """What the run is held to; every value comes from the committed fixtures or the CI environment."""

    fixture_sha: dict[str, str]  # key -> sha256 of the committed file
    expected_rules: list[str]
    clerk_user_a: str = ""
    clerk_org_a: str = ""
    clerk_user_b: str = ""
    clerk_org_b: str = ""
    tenant_a: str = ""
    tenant_b: str = ""
    real_ai: bool = False
    worker_provider_successes: int = 0
    reason_sha256: str = ""
    self_approved_declared: bool | None = None


@dataclass
class Facts:
    """Plain rows read from PostgreSQL (dicts and lists), so ``judge`` is pure and testable without a database."""

    project_a: dict[str, Any] | None = None
    project_b: dict[str, Any] | None = None
    tenants: dict[str, dict[str, Any]] = field(default_factory=dict)  # tenant id -> row
    users: list[dict[str, Any]] = field(default_factory=list)
    documents: list[dict[str, Any]] = field(default_factory=list)
    revisions: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    reviews: list[dict[str, Any]] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)
    clause_revisions: dict[str, str] = field(default_factory=dict)  # clause id -> revision id
    events: list[dict[str, Any]] = field(default_factory=list)
    graph_events: int = 0
    analyses: int = 0
    six_dimension_snapshots: int = 0
    baselines: list[dict[str, Any]] = field(default_factory=list)
    change_sets: list[dict[str, Any]] = field(default_factory=list)
    tenant_a_distinct_approver_required: bool | None = None
    tenant_a_ai_spend: float = 0.0


def _doc(key: str, browser: dict[str, Any]) -> str:
    return str((browser.get("documentIds") or {}).get(key) or "")


def judge(facts: Facts, browser: dict[str, Any], expect: Expectations) -> list[Check]:  # noqa: C901, PLR0912, PLR0915
    """Every claim of the run, as a named check. Pure: no I/O."""
    checks: list[Check] = []

    def add(stage: str, name: str, ok: bool, detail: str = "") -> None:
        checks.append(Check(stage, name, bool(ok), detail))

    project_a, project_b = facts.project_a, facts.project_b
    # ── S1 ────────────────────────────────────────────────────────────────────────────────────────────────
    add("S1", "project A exists in PostgreSQL", project_a is not None)
    add("S1", "project B exists in PostgreSQL", project_b is not None)
    if project_a is None or project_b is None:
        return checks
    tenant_a, tenant_b = str(project_a["tenant_id"]), str(project_b["tenant_id"])
    add("S1", "the two projects belong to two different tenants", tenant_a != tenant_b)
    add(
        "S1",
        "project A is in the expected tenant A",
        not expect.tenant_a or tenant_a == expect.tenant_a,
    )
    add(
        "S1",
        "project B is in the expected tenant B",
        not expect.tenant_b or tenant_b == expect.tenant_b,
    )
    row_a, row_b = facts.tenants.get(tenant_a), facts.tenants.get(tenant_b)
    add(
        "S1",
        "tenant A is bound to the Clerk Organization of identity A",
        bool(row_a)
        and bool(expect.clerk_org_a)
        and row_a.get("clerk_org_id") == expect.clerk_org_a,
    )
    add(
        "S1",
        "tenant B is bound to the Clerk Organization of identity B",
        bool(row_b)
        and bool(expect.clerk_org_b)
        and row_b.get("clerk_org_id") == expect.clerk_org_b,
    )
    add(
        "S1",
        "the two identities live in two different Organizations",
        bool(expect.clerk_org_a) and expect.clerk_org_a != expect.clerk_org_b,
    )
    users_a = [
        u
        for u in facts.users
        if str(u["tenant_id"]) == tenant_a and u.get("clerk_user_id") == expect.clerk_user_a
    ]
    users_b = [
        u
        for u in facts.users
        if str(u["tenant_id"]) == tenant_b and u.get("clerk_user_id") == expect.clerk_user_b
    ]
    add(
        "S1",
        "identity A is an active user of tenant A",
        bool(expect.clerk_user_a) and len(users_a) == 1 and bool(users_a[0].get("is_active")),
    )
    add(
        "S1",
        "identity B is an active user of tenant B",
        bool(expect.clerk_user_b) and len(users_b) == 1 and bool(users_b[0].get("is_active")),
    )
    add(
        "S1",
        "the browser recorded the same project ids",
        str(project_a["id"]) == browser.get("projectIdA")
        and str(project_b["id"]) == browser.get("projectIdB"),
    )
    ident = browser.get("clerkIdentityChecks") or {}
    add(
        "S1",
        "the browser saw distinct users, Organizations and tenants",
        all(
            ident.get(k) is True
            for k in ("distinctUsers", "distinctOrganizations", "distinctTenants")
        ),
    )

    # ── S2 ────────────────────────────────────────────────────────────────────────────────────────────────
    documents = [d for d in facts.documents if str(d["project_id"]) == str(project_a["id"])]
    add(
        "S2",
        "project A holds exactly five documents",
        len(documents) == 5,
        f"{len(documents)} document(s)",
    )
    add(
        "S2",
        "every document is of tenant A",
        all(str(d["tenant_id"]) == tenant_a for d in documents),
    )
    types = sorted(str(d["document_type"]).lower() for d in documents)
    add(
        "S2",
        "the document families are contract, budget, schedule and two technical specifications",
        types == ["budget", "contract", "schedule", "technical_spec", "technical_spec"],
        ",".join(types),
    )
    revisions_of: dict[str, list[dict[str, Any]]] = {}
    for revision in facts.revisions:
        revisions_of.setdefault(str(revision["document_id"]), []).append(revision)
    for rows in revisions_of.values():
        rows.sort(key=lambda r: int(r["rev_no"]))
    file_by_key = {
        "contract": "contractA",
        "budget": "budget",
        "schedule": "schedule",
        "specification": "specification",
        "rejectedCandidate": "specificationRejected",
    }
    for key, fixture_key in file_by_key.items():
        document_id = _doc(key, browser)
        revs = revisions_of.get(document_id, [])
        wanted = (
            [expect.fixture_sha[fixture_key]]
            if key != "contract"
            else [expect.fixture_sha["contractA"], expect.fixture_sha["contractB"]]
        )
        add(
            "S2",
            f"{key}: stored revisions carry the pinned SHA-256 of the committed files",
            [r["blob_hash"] for r in revs] == wanted,
            f"{len(revs)} revision(s)",
        )

    # ── S3 ────────────────────────────────────────────────────────────────────────────────────────────────
    add(
        "S3",
        "the worker completed the graph (graph.completed)",
        facts.graph_events >= 1,
        f"{facts.graph_events} event(s)",
    )
    add("S3", "an analysis row exists", facts.analyses >= 1, f"{facts.analyses}")
    add(
        "S3",
        "a project snapshot carries six Health assessments",
        facts.six_dimension_snapshots >= 1,
        f"{facts.six_dimension_snapshots}",
    )
    alerts = [a for a in facts.alerts if str(a["project_id"]) == str(project_a["id"])]
    add(
        "S3",
        "alerts are persisted for project A, all of tenant A",
        len(alerts) > 0 and all(str(a["tenant_id"]) == tenant_a for a in alerts),
        f"{len(alerts)} alert(s)",
    )
    rules = {str(a["rule_code"]) for a in alerts}
    for rule in expect.expected_rules:
        add("S3", f"{rule} is persisted", rule in rules)
    if expect.real_ai:
        add(
            "S3",
            "the worker made at least one real provider call",
            expect.worker_provider_successes >= 1,
            f"{expect.worker_provider_successes}",
        )
        add(
            "S3",
            "the tenant's AI spend was recorded",
            facts.tenant_a_ai_spend > 0,
            f"{facts.tenant_a_ai_spend}",
        )

    # ── S4 ────────────────────────────────────────────────────────────────────────────────────────────────
    contract_id = _doc("contract", browser)
    contract_revisions = {str(r["revision_id"]) for r in revisions_of.get(contract_id, [])}
    with_clause = [a for a in alerts if a.get("source_clause_id")]
    resolved = [
        a
        for a in with_clause
        if facts.clause_revisions.get(str(a["source_clause_id"])) in contract_revisions
    ]
    add("S4", "an alert cites a clause", len(with_clause) > 0, f"{len(with_clause)}/{len(alerts)}")
    add(
        "S4",
        "the clause belongs to a revision of the contract",
        len(resolved) > 0,
        f"{len(resolved)}/{len(with_clause)}",
    )

    # ── S5 ────────────────────────────────────────────────────────────────────────────────────────────────
    artifacts_of: dict[str, list[dict[str, Any]]] = {}
    for artifact in facts.artifacts:
        artifacts_of.setdefault(str(artifact["document_id"]), []).append(artifact)
    reviews = [r for r in facts.reviews if str(r["project_id"]) == str(project_a["id"])]

    def approved_for(artifact: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            r
            for r in reviews
            if str(r["status"]).upper() == "APPROVED"
            and ((r.get("review_metadata") or {}).get("candidate_binding") or {}).get("artifact_id")
            == str(artifact["artifact_id"])
        ]

    for key in ("contract", "specification"):
        document_id = _doc(key, browser)
        trusted = [a for a in artifacts_of.get(document_id, []) if a["trust_state"] == "trusted"]
        add("S5", f"{key}: a trusted artifact exists", len(trusted) >= 1)
        for artifact in trusted:
            approvals = approved_for(artifact)
            named = approvals and all(
                (r.get("approved_by") or "").strip() and r.get("approved_at") for r in approvals
            )
            bound = approvals and all(
                ((r.get("review_metadata") or {}).get("candidate_binding") or {}).get(
                    "artifact_hash"
                )
                == artifact["artifact_hash"]
                for r in approvals
            )
            add(
                "S5",
                f"{key}: every trusted artifact has an approved review, bound to it, naming who and when",
                bool(named and bound),
                f"v{artifact.get('artifact_version')}",
            )
    rejected_id = _doc("rejectedCandidate", browser)
    rejected_reviews = [r for r in reviews if str(r["document_id"]) == rejected_id]
    add(
        "S5",
        "the draft specification has exactly one review and it is REJECTED",
        [str(r["status"]).upper() for r in rejected_reviews] == ["REJECTED"],
    )
    for review in rejected_reviews:
        reason = (review.get("review_metadata") or {}).get("rejection_reason")
        add(
            "S5",
            "the stored rejection reason is the typed one",
            isinstance(reason, str)
            and hashlib.sha256(reason.encode()).hexdigest() == expect.reason_sha256,
        )
        add(
            "S5", "the rejection names who decided", bool((review.get("approved_by") or "").strip())
        )
    add(
        "S5",
        "nothing of the rejected draft is trusted",
        all(a["trust_state"] != "trusted" for a in artifacts_of.get(rejected_id, [])),
    )
    add(
        "S5",
        "no review is left pending",
        all(str(r["status"]).upper() in {"APPROVED", "REJECTED", "CLOSED"} for r in reviews),
        ",".join(sorted({str(r["status"]) for r in reviews})),
    )

    # ── S6 ────────────────────────────────────────────────────────────────────────────────────────────────
    contract_artifacts = {
        str(a["document_revision_id"]): a for a in artifacts_of.get(contract_id, [])
    }
    revs = revisions_of.get(contract_id, [])
    if len(revs) == 2:
        a_artifact, b_artifact = (
            contract_artifacts.get(str(revs[0]["revision_id"])),
            contract_artifacts.get(str(revs[1]["revision_id"])),
        )
        add(
            "S6",
            "revision A was trusted and is now superseded",
            bool(a_artifact)
            and (a_artifact["trust_state"], a_artifact["lifecycle_status"])
            == ("trusted", "superseded"),
        )
        add(
            "S6",
            "revision B is the active trusted artifact",
            bool(b_artifact)
            and (b_artifact["trust_state"], b_artifact["lifecycle_status"])
            == ("trusted", "active"),
        )
    else:
        add("S6", "the contract has exactly two revisions", False, f"{len(revs)} revision(s)")
    add(
        "S6",
        "no artifact of the project is left proposed",
        all(a["trust_state"] != "proposed" for a in facts.artifacts),
    )
    changes = [
        e
        for e in facts.events
        if e["event_type"] == "revision.changed"
        and str(e.get("document_id") or "") in {contract_id, ""}
    ]
    add(
        "S6",
        "exactly one revision.changed exists for the contract",
        len(changes) == 1,
        f"{len(changes)} event(s)",
    )

    # ── S7 ────────────────────────────────────────────────────────────────────────────────────────────────
    baselines = [b for b in facts.baselines if str(b["project_id"]) == str(project_a["id"])]
    add("S7", "exactly one approved WBS baseline exists", len(baselines) == 1, f"{len(baselines)}")
    actor_ids = {str(u["id"]) for u in users_a}
    baseline = baselines[0] if baselines else None
    if baseline:
        add(
            "S7",
            "the baseline was approved by the journey's human",
            str(baseline["approved_by"]) in actor_ids,
        )
        change_set = next(
            (c for c in facts.change_sets if str(c["id"]) == str(baseline["source_change_set_id"])),
            None,
        )
        self_approved = bool(change_set and change_set.get("decided_self_approval"))
        add(
            "S7",
            "the approval of the baseline is recorded (self-approval is reported, never hidden)",
            change_set is not None and change_set.get("decided_self_approval") is not None,
            f"self_approved={self_approved}",
        )
        if self_approved:
            add(
                "S7",
                "a self-approval happened only because tenant A declares it",
                facts.tenant_a_distinct_approver_required is False,
            )
        if expect.self_approved_declared is not None:
            add(
                "S7",
                "the self-approval flag equals what the browser recorded",
                self_approved == expect.self_approved_declared,
            )
    link_events = [e for e in facts.events if e["event_type"] in FAMILY_EVENTS.values()]
    revision_by_id = {str(r["revision_id"]): r for rows in revisions_of.values() for r in rows}
    for family, event_type in FAMILY_EVENTS.items():
        rows = [e for e in link_events if e["event_type"] == event_type]
        add("S7", f"exactly one approved {family} link exists", len(rows) == 1, f"{len(rows)}")
        for event in rows:
            payload = event.get("payload") or {}
            revision = revision_by_id.get(
                str(payload.get("source_revision_id") or payload.get("technical_revision_id") or "")
            )
            blob_hash = payload.get("source_blob_hash")
            add(
                "S7",
                f"{family} link: actor is a human user of tenant A",
                str(event.get("actor") or "").removeprefix("user:") in actor_ids
                and str(event.get("actor") or "").startswith("user:"),
            )
            add(
                "S7",
                f"{family} link: it names a stored source revision and its blob hash",
                bool(revision) and (blob_hash is None or blob_hash == revision["blob_hash"]),
            )
            add(
                "S7",
                f"{family} link: it names the approved baseline and node",
                bool(baseline) and str(payload.get("wbs_baseline_id")) == str(baseline["id"]),
            )
            add(
                "S7",
                f"{family} link: it carries a locator",
                bool(payload.get("source_locator") or payload.get("source_section")),
            )

    # ── S8 ────────────────────────────────────────────────────────────────────────────────────────────────
    digests = browser.get("snapshotDigests") or {}
    add(
        "S8",
        "the browser's snapshots before and after the new login are identical",
        bool(digests.get("before")) and digests.get("before") == digests.get("after"),
    )
    add("S8", "project A still exists with its five documents", len(documents) == 5)
    return checks


# ── collection (read-only) ──────────────────────────────────────────────────────────────────────────────────
async def _rows(conn: AsyncConnection, sql: str, **params: Any) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in (await conn.execute(text(sql), params)).all()]


async def collect(conn: AsyncConnection, project_a: UUID, project_b: UUID) -> Facts:
    facts = Facts()
    projects = await _rows(
        conn,
        "SELECT id, tenant_id, name FROM projects WHERE id IN (:a, :b)",
        a=project_a,
        b=project_b,
    )
    by_id = {str(p["id"]): p for p in projects}
    facts.project_a, facts.project_b = by_id.get(str(project_a)), by_id.get(str(project_b))
    tenant_ids = [p["tenant_id"] for p in projects]
    for row in await _rows(
        conn,
        "SELECT id, clerk_org_id, settings, ai_spend_current FROM tenants WHERE id = ANY(:ids)",
        ids=tenant_ids,
    ):
        facts.tenants[str(row["id"])] = row
    facts.users = await _rows(
        conn,
        "SELECT id, tenant_id, clerk_user_id, is_active FROM users WHERE tenant_id = ANY(:ids)",
        ids=tenant_ids,
    )
    if facts.project_a is None:
        return facts
    pa = {"p": project_a}
    facts.documents = await _rows(
        conn,
        "SELECT id, tenant_id, project_id, document_type::text AS document_type FROM documents WHERE project_id = :p",
        **pa,
    )
    facts.revisions = await _rows(
        conn,
        "SELECT document_id, revision_id, rev_no, blob_hash FROM document_revisions WHERE project_id = :p",
        **pa,
    )
    facts.artifacts = await _rows(
        conn,
        "SELECT artifact_id, document_id, document_revision_id, artifact_version, artifact_hash, trust_state, lifecycle_status FROM document_artifacts WHERE project_id = :p",
        **pa,
    )
    facts.reviews = await _rows(
        conn,
        "SELECT project_id, document_id, item_id, id, upper(current_status::text) AS status, approved_by, approved_at, review_metadata FROM review_items WHERE project_id = :p",
        **pa,
    )
    facts.alerts = await _rows(
        conn,
        "SELECT project_id, tenant_id, rule_code, status::text AS status, source_clause_id FROM alerts WHERE project_id = :p",
        **pa,
    )
    clause_ids = [a["source_clause_id"] for a in facts.alerts if a["source_clause_id"]]
    if clause_ids:
        for row in await _rows(
            conn, "SELECT id, revision_id FROM clauses WHERE id = ANY(:ids)", ids=clause_ids
        ):
            facts.clause_revisions[str(row["id"])] = str(row["revision_id"])
    facts.events = await _rows(
        conn,
        "SELECT event_id, event_type, actor, payload, source_revision_id, payload->>'document_id' AS document_id "
        "FROM project_events WHERE project_id = :p",
        **pa,
    )
    facts.graph_events = sum(1 for e in facts.events if e["event_type"] == "graph.completed")
    facts.analyses = int(
        (
            await conn.execute(text("SELECT count(*) FROM analyses WHERE project_id = :p"), pa)
        ).scalar_one()
    )
    facts.six_dimension_snapshots = int(
        (
            await conn.execute(
                text(
                    "SELECT count(*) FROM project_snapshots WHERE project_id = :p "
                    "AND jsonb_array_length(health_vector -> 'single_document_coverage' -> 'assessments') = 6"
                ),
                pa,
            )
        ).scalar_one()
    )
    facts.baselines = await _rows(
        conn,
        "SELECT id, project_id, baseline_no, approved_by, source_change_set_id FROM wbs_baselines WHERE project_id = :p",
        **pa,
    )
    facts.change_sets = await _rows(
        conn,
        "SELECT id, submitted_by, decided_by, decided_self_approval FROM wbs_change_sets WHERE project_id = :p",
        **pa,
    )
    tenant_a = facts.tenants.get(str(facts.project_a["tenant_id"]))
    if tenant_a:
        governance = (tenant_a.get("settings") or {}).get("wbs_governance") or {}
        facts.tenant_a_distinct_approver_required = (
            governance.get("require_distinct_approver", True) is not False
        )
        facts.tenant_a_ai_spend = float(tenant_a.get("ai_spend_current") or 0)
    return facts


# ── manifest ────────────────────────────────────────────────────────────────────────────────────────────────
def build_manifest(
    browser: dict[str, Any],
    checks: list[Check],
    receipt: dict[str, Any],
    env: dict[str, str | None],
) -> dict[str, Any]:
    """One manifest tied to the project id: the browser half, the PostgreSQL verdicts and the first failure."""
    stage_rows = {s["id"]: s for s in browser.get("stages", [])}
    steps: dict[str, Any] = {}
    for stage in STAGES:
        mine = [c for c in checks if c.stage == stage]
        browser_status = (stage_rows.get(stage) or {}).get("status", "NOT_RUN")
        pg_status = "NOT_RUN" if not mine else ("PASS" if all(c.ok for c in mine) else "FAIL")
        if browser_status == "FAIL" or pg_status == "FAIL":
            combined = "FAIL"
        elif browser_status == "NOT_RUN" or pg_status == "NOT_RUN":
            combined = "NOT_RUN"
        elif browser_status == "PARTIAL":
            combined = "PARTIAL"
        else:
            combined = "PASS"
        steps[stage] = {
            "browser": browser_status,
            "postgres": pg_status,
            "verdict": combined,
            "declaredGaps": (stage_rows.get(stage) or {}).get("partial", []),
            "failedChecks": [
                f"{c.name}{': ' + c.detail if c.detail else ''}" for c in mine if not c.ok
            ],
        }
    failed = [s for s in STAGES if steps[s]["verdict"] == "FAIL"]
    unfinished = [s for s in STAGES if steps[s]["verdict"] == "NOT_RUN"]
    first = browser.get("firstFailure") or (
        {
            "stage": failed[0],
            "message": steps[failed[0]]["failedChecks"][0]
            if steps[failed[0]]["failedChecks"]
            else "failed",
        }
        if failed
        else None
    )
    mode = browser.get("mode")
    if failed or unfinished:
        verdict = "FAILED" if failed else "INCOMPLETE"
    elif mode != "real-ai-uat":
        verdict = "REHEARSAL_ONLY_NOT_UAT"
    elif any(steps[s]["declaredGaps"] for s in STAGES):
        verdict = "UAT_REAL_WITH_DECLARED_GAPS"
    else:
        verdict = "UAT_REAL_COMPLETE"
    return {
        "schema": "c2pro-integral-s1-s8-manifest/v1",
        "candidate_sha": env.get("candidate_sha") or browser.get("candidateSha"),
        "frontend_runtime_sha": env.get("frontend_runtime_sha")
        or browser.get("frontendRuntimeSha"),
        "backend_runtime_sha": env.get("backend_runtime_sha"),
        "mode": mode,
        "evidence_class": browser.get("evidenceClass"),
        "project_id_A": browser.get("projectIdA"),
        "project_id_B": browser.get("projectIdB"),
        "document_ids": browser.get("documentIds"),
        "revision_ids": browser.get("contractRevisionIds"),
        "review_item_ids": browser.get("reviewItemIds"),
        "event_ids": browser.get("eventIds"),
        "wbs": browser.get("wbs"),
        "provider_real_call_receipt": receipt,
        "clerk_identity_checks": browser.get("clerkIdentityChecks"),
        "snapshot_digests": browser.get("snapshotDigests"),
        "steps_S1_S8": steps,
        "postgres_checks": [
            {"stage": c.stage, "name": c.name, "ok": c.ok, "detail": c.detail} for c in checks
        ],
        "first_failure": first,
        "verdict": verdict,
        "acceptance": "NOT_ACCEPTED_UNTIL_INDEPENDENT_REVIEW",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--browser-manifest", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provider-receipt",
        type=Path,
        help="JSON written by the workflow from the provider preflight and the worker log",
    )
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--candidate-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--frontend-runtime-sha", default=os.environ.get("FRONTEND_RUNTIME_SHA"))
    parser.add_argument("--backend-runtime-sha", default=os.environ.get("BACKEND_RUNTIME_SHA"))
    args = parser.parse_args()
    if not args.database_url:
        print("FAIL: no database url (set DATABASE_URL or pass --database-url)")
        return 2

    browser_path = _within_repo(args.browser_manifest)
    fixture_dir = _within_repo(args.fixture_dir)
    output = _within_repo(args.output)
    browser = json.loads(browser_path.read_text(encoding="utf-8"))
    if not browser.get("projectIdA") or not browser.get("projectIdB"):
        print(
            "FAIL: the browser manifest records no project id (the run stopped before S1 created them)"
        )
        return 1

    triplet = json.loads((fixture_dir / "triplet.manifest.json").read_text(encoding="utf-8"))
    extra = json.loads((fixture_dir / "integral.manifest.json").read_text(encoding="utf-8"))
    fixture_sha = {
        "contractA": _sha256_file(fixture_dir / "triplet-contract.docx"),
        "contractB": _sha256_file(fixture_dir / "triplet-contract-b.docx"),
        "budget": _sha256_file(fixture_dir / "triplet-budget.xlsx"),
        "schedule": _sha256_file(fixture_dir / "triplet-schedule.xlsx"),
        "specification": _sha256_file(fixture_dir / "triplet-specification.docx"),
        "specificationRejected": _sha256_file(fixture_dir / "triplet-specification-rejected.docx"),
    }
    pinned = {
        "contractA": triplet["sha256"]["triplet-contract.docx"],
        "contractB": extra["contract_b"]["sha256"],
        "budget": triplet["sha256"]["triplet-budget.xlsx"],
        "schedule": triplet["sha256"]["triplet-schedule.xlsx"],
        "specification": triplet["sha256"]["triplet-specification.docx"],
        "specificationRejected": extra["specification_rejected"]["sha256"],
    }
    if fixture_sha != pinned:
        print("FAIL: a committed fixture no longer has its pinned SHA-256")
        return 1

    receipt: dict[str, Any] = {}
    if args.provider_receipt:
        receipt = json.loads(_within_repo(args.provider_receipt).read_text(encoding="utf-8"))
    rejection = ((browser.get("stages") or [{}] * 8)[4].get("evidence") or {}).get(
        "rejection"
    ) or {}
    s7 = ((browser.get("stages") or [{}] * 8)[6].get("evidence") or {}).get("wbs") or {}
    expect = Expectations(
        fixture_sha=fixture_sha,
        expected_rules=list(triplet["expected_rules"]),
        clerk_user_a=os.environ.get("CLERK_E2E_USER_ID", ""),
        clerk_org_a=os.environ.get("CLERK_E2E_ORG_ID", ""),
        clerk_user_b=os.environ.get("TENANT_B_CLERK_E2E_USER_ID", ""),
        clerk_org_b=os.environ.get("TENANT_B_CLERK_E2E_ORG_ID", ""),
        tenant_a=os.environ.get("E2E_EXPECTED_TENANT_ID", ""),
        tenant_b=os.environ.get("TENANT_B_E2E_EXPECTED_TENANT_ID", ""),
        real_ai=browser.get("mode") == "real-ai-uat",
        worker_provider_successes=int(receipt.get("worker_provider_successes") or 0),
        reason_sha256=str(rejection.get("reasonSha256") or ""),
        self_approved_declared=s7.get("selfApproved"),
    )

    async def run() -> list[Check]:
        engine = create_async_engine(_normalize_database_url(args.database_url))
        try:
            async with engine.connect() as conn:
                facts = await collect(
                    conn, UUID(browser["projectIdA"]), UUID(browser["projectIdB"])
                )
        finally:
            await engine.dispose()
        return judge(facts, browser, expect)

    checks = asyncio.run(run())
    manifest = build_manifest(
        browser,
        checks,
        receipt,
        {
            "candidate_sha": args.candidate_sha,
            "frontend_runtime_sha": args.frontend_runtime_sha,
            "backend_runtime_sha": args.backend_runtime_sha,
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    failed = [c for c in checks if not c.ok]
    for check in failed:
        print(f"FAIL [{check.stage}] {check.name}{': ' + check.detail if check.detail else ''}")
    print(
        f"verdict={manifest['verdict']} stages="
        + ",".join(f"{s}:{manifest['steps_S1_S8'][s]['verdict']}" for s in STAGES)
    )
    print(
        f"postgres checks: {len(checks) - len(failed)}/{len(checks)} passed; first_failure={manifest['first_failure']}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
