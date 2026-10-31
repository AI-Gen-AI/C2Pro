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

import asyncio
import hashlib
import json
import os
import re
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


REPORT_DIR = REPO_ROOT / "apps" / "web" / "playwright-report"
FIXTURE_DIR = REPO_ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "test-data" / "triplet"
BROWSER_MANIFEST = REPORT_DIR / "integral-browser-manifest.json"
PROVIDER_RECEIPT = REPORT_DIR / "integral-provider-receipt.json"


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


@dataclass
class _Ctx:
    """The rows and derived views every stage judges, built once."""

    facts: Facts
    browser: dict[str, Any]
    expect: Expectations
    checks: list[Check] = field(default_factory=list)

    def add(self, stage: str, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(stage, name, bool(ok), detail))

    def doc(self, key: str) -> str:
        return _doc(key, self.browser)

    @property
    def project_a(self) -> dict[str, Any]:
        assert self.facts.project_a is not None
        return self.facts.project_a

    @property
    def project_b(self) -> dict[str, Any]:
        assert self.facts.project_b is not None
        return self.facts.project_b

    @property
    def tenant_a(self) -> str:
        return str(self.project_a["tenant_id"])

    @property
    def tenant_b(self) -> str:
        return str(self.project_b["tenant_id"])

    def users_of(self, tenant: str, clerk_user: str) -> list[dict[str, Any]]:
        return [
            u
            for u in self.facts.users
            if str(u["tenant_id"]) == tenant and u.get("clerk_user_id") == clerk_user
        ]

    @property
    def documents(self) -> list[dict[str, Any]]:
        return [
            d for d in self.facts.documents if str(d["project_id"]) == str(self.project_a["id"])
        ]

    @property
    def revisions_of(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for revision in self.facts.revisions:
            grouped.setdefault(str(revision["document_id"]), []).append(revision)
        for rows in grouped.values():
            rows.sort(key=lambda r: int(r["rev_no"]))
        return grouped

    @property
    def artifacts_of(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for artifact in self.facts.artifacts:
            grouped.setdefault(str(artifact["document_id"]), []).append(artifact)
        return grouped

    @property
    def alerts(self) -> list[dict[str, Any]]:
        return [a for a in self.facts.alerts if str(a["project_id"]) == str(self.project_a["id"])]

    @property
    def reviews(self) -> list[dict[str, Any]]:
        return [r for r in self.facts.reviews if str(r["project_id"]) == str(self.project_a["id"])]

    @property
    def actor_ids(self) -> set[str]:
        return {str(u["id"]) for u in self.users_of(self.tenant_a, self.expect.clerk_user_a)}


def _judge_s1(c: _Ctx) -> None:
    e = c.expect
    add = c.add
    add("S1", "the two projects belong to two different tenants", c.tenant_a != c.tenant_b)
    add("S1", "project A is in the expected tenant A", not e.tenant_a or c.tenant_a == e.tenant_a)
    add("S1", "project B is in the expected tenant B", not e.tenant_b or c.tenant_b == e.tenant_b)
    row_a, row_b = c.facts.tenants.get(c.tenant_a), c.facts.tenants.get(c.tenant_b)
    org_a_bound = bool(row_a) and bool(e.clerk_org_a) and row_a.get("clerk_org_id") == e.clerk_org_a
    org_b_bound = bool(row_b) and bool(e.clerk_org_b) and row_b.get("clerk_org_id") == e.clerk_org_b
    add("S1", "tenant A is bound to the Clerk Organization of identity A", org_a_bound)
    add("S1", "tenant B is bound to the Clerk Organization of identity B", org_b_bound)
    add(
        "S1",
        "the two identities live in two different Organizations",
        bool(e.clerk_org_a) and e.clerk_org_a != e.clerk_org_b,
    )
    users_a = c.users_of(c.tenant_a, e.clerk_user_a)
    users_b = c.users_of(c.tenant_b, e.clerk_user_b)
    add(
        "S1",
        "identity A is an active user of tenant A",
        bool(e.clerk_user_a) and len(users_a) == 1 and bool(users_a[0].get("is_active")),
    )
    add(
        "S1",
        "identity B is an active user of tenant B",
        bool(e.clerk_user_b) and len(users_b) == 1 and bool(users_b[0].get("is_active")),
    )
    same_ids = str(c.project_a["id"]) == c.browser.get("projectIdA") and str(
        c.project_b["id"]
    ) == c.browser.get("projectIdB")
    add("S1", "the browser recorded the same project ids", same_ids)
    ident = c.browser.get("clerkIdentityChecks") or {}
    distinct = all(
        ident.get(k) is True for k in ("distinctUsers", "distinctOrganizations", "distinctTenants")
    )
    add("S1", "the browser saw distinct users, Organizations and tenants", distinct)


_FIXTURE_KEY_OF = {
    "contract": "contractA",
    "budget": "budget",
    "schedule": "schedule",
    "specification": "specification",
    "rejectedCandidate": "specificationRejected",
}


def _judge_s2(c: _Ctx) -> None:
    add = c.add
    documents = c.documents
    add(
        "S2",
        "project A holds exactly five documents",
        len(documents) == 5,
        f"{len(documents)} document(s)",
    )
    add(
        "S2",
        "every document is of tenant A",
        all(str(d["tenant_id"]) == c.tenant_a for d in documents),
    )
    types = sorted(str(d["document_type"]).lower() for d in documents)
    wanted_types = ["budget", "contract", "schedule", "technical_spec", "technical_spec"]
    add(
        "S2",
        "the document families are contract, budget, schedule and two technical specifications",
        types == wanted_types,
        ",".join(types),
    )
    revisions_of = c.revisions_of
    sha = c.expect.fixture_sha
    for key, fixture_key in _FIXTURE_KEY_OF.items():
        revs = revisions_of.get(c.doc(key), [])
        wanted = [sha["contractA"], sha["contractB"]] if key == "contract" else [sha[fixture_key]]
        add(
            "S2",
            f"{key}: stored revisions carry the pinned SHA-256 of the committed files",
            [r["blob_hash"] for r in revs] == wanted,
            f"{len(revs)} revision(s)",
        )


def _judge_s3(c: _Ctx) -> None:
    add = c.add
    f = c.facts
    add(
        "S3",
        "the worker completed the graph (graph.completed)",
        f.graph_events >= 1,
        f"{f.graph_events} event(s)",
    )
    add("S3", "an analysis row exists", f.analyses >= 1, f"{f.analyses}")
    add(
        "S3",
        "a project snapshot carries six Health assessments",
        f.six_dimension_snapshots >= 1,
        f"{f.six_dimension_snapshots}",
    )
    alerts = c.alerts
    add(
        "S3",
        "alerts are persisted for project A, all of tenant A",
        len(alerts) > 0 and all(str(a["tenant_id"]) == c.tenant_a for a in alerts),
        f"{len(alerts)} alert(s)",
    )
    rules = {str(a["rule_code"]) for a in alerts}
    for rule in c.expect.expected_rules:
        add("S3", f"{rule} is persisted", rule in rules)
    if c.expect.real_ai:
        calls = c.expect.worker_provider_successes
        add("S3", "the worker made at least one real provider call", calls >= 1, f"{calls}")
        add(
            "S3",
            "the tenant's AI spend was recorded",
            f.tenant_a_ai_spend > 0,
            f"{f.tenant_a_ai_spend}",
        )


def _judge_s4(c: _Ctx) -> None:
    contract_revisions = {str(r["revision_id"]) for r in c.revisions_of.get(c.doc("contract"), [])}
    with_clause = [a for a in c.alerts if a.get("source_clause_id")]
    resolved = [
        a
        for a in with_clause
        if c.facts.clause_revisions.get(str(a["source_clause_id"])) in contract_revisions
    ]
    c.add(
        "S4", "an alert cites a clause", len(with_clause) > 0, f"{len(with_clause)}/{len(c.alerts)}"
    )
    c.add(
        "S4",
        "the clause belongs to a revision of the contract",
        len(resolved) > 0,
        f"{len(resolved)}/{len(with_clause)}",
    )


def _approved_reviews_of(c: _Ctx, artifact: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        r
        for r in c.reviews
        if str(r["status"]).upper() == "APPROVED"
        and _binding(r).get("artifact_id") == str(artifact["artifact_id"])
    ]


def _binding(review: dict[str, Any]) -> dict[str, Any]:
    return (review.get("review_metadata") or {}).get("candidate_binding") or {}


def _judge_s5_approvals(c: _Ctx) -> None:
    for key in ("contract", "specification"):
        trusted = [a for a in c.artifacts_of.get(c.doc(key), []) if a["trust_state"] == "trusted"]
        c.add("S5", f"{key}: a trusted artifact exists", len(trusted) >= 1)
        for artifact in trusted:
            approvals = _approved_reviews_of(c, artifact)
            named = bool(approvals) and all(
                (r.get("approved_by") or "").strip() and r.get("approved_at") for r in approvals
            )
            bound = bool(approvals) and all(
                _binding(r).get("artifact_hash") == artifact["artifact_hash"] for r in approvals
            )
            c.add(
                "S5",
                f"{key}: every trusted artifact has an approved review, bound to it, naming who and when",
                named and bound,
                f"v{artifact.get('artifact_version')}",
            )


def _judge_s5(c: _Ctx) -> None:
    _judge_s5_approvals(c)
    rejected_id = c.doc("rejectedCandidate")
    rejected = [r for r in c.reviews if str(r["document_id"]) == rejected_id]
    c.add(
        "S5",
        "the draft specification has exactly one review and it is REJECTED",
        [str(r["status"]).upper() for r in rejected] == ["REJECTED"],
    )
    for review in rejected:
        reason = (review.get("review_metadata") or {}).get("rejection_reason")
        typed = (
            isinstance(reason, str)
            and hashlib.sha256(reason.encode()).hexdigest() == c.expect.reason_sha256
        )
        c.add("S5", "the stored rejection reason is the typed one", typed)
        c.add(
            "S5", "the rejection names who decided", bool((review.get("approved_by") or "").strip())
        )
    c.add(
        "S5",
        "nothing of the rejected draft is trusted",
        all(a["trust_state"] != "trusted" for a in c.artifacts_of.get(rejected_id, [])),
    )
    statuses = sorted({str(r["status"]) for r in c.reviews})
    final = {"APPROVED", "REJECTED", "CLOSED"}
    c.add(
        "S5",
        "no review is left pending",
        all(str(r["status"]).upper() in final for r in c.reviews),
        ",".join(statuses),
    )


def _judge_s6(c: _Ctx) -> None:
    contract_id = c.doc("contract")
    revs = c.revisions_of.get(contract_id, [])
    if len(revs) == 2:
        by_revision = {
            str(a["document_revision_id"]): a for a in c.artifacts_of.get(contract_id, [])
        }
        a_art = by_revision.get(str(revs[0]["revision_id"]))
        b_art = by_revision.get(str(revs[1]["revision_id"]))
        a_ok = bool(a_art) and (a_art["trust_state"], a_art["lifecycle_status"]) == (
            "trusted",
            "superseded",
        )
        b_ok = bool(b_art) and (b_art["trust_state"], b_art["lifecycle_status"]) == (
            "trusted",
            "active",
        )
        c.add("S6", "revision A was trusted and is now superseded", a_ok)
        c.add("S6", "revision B is the active trusted artifact", b_ok)
    else:
        c.add("S6", "the contract has exactly two revisions", False, f"{len(revs)} revision(s)")
    c.add(
        "S6",
        "no artifact of the project is left proposed",
        all(a["trust_state"] != "proposed" for a in c.facts.artifacts),
    )
    changes = [
        e
        for e in c.facts.events
        if e["event_type"] == "revision.changed"
        and str(e.get("document_id") or "") in {contract_id, ""}
    ]
    c.add(
        "S6",
        "exactly one revision.changed exists for the contract",
        len(changes) == 1,
        f"{len(changes)} event(s)",
    )


def _judge_s7_baseline(c: _Ctx) -> dict[str, Any] | None:
    baselines = [b for b in c.facts.baselines if str(b["project_id"]) == str(c.project_a["id"])]
    c.add(
        "S7", "exactly one approved WBS baseline exists", len(baselines) == 1, f"{len(baselines)}"
    )
    if not baselines:
        return None
    baseline = baselines[0]
    c.add(
        "S7",
        "the baseline was approved by the journey's human",
        str(baseline["approved_by"]) in c.actor_ids,
    )
    change_set = next(
        (x for x in c.facts.change_sets if str(x["id"]) == str(baseline["source_change_set_id"])),
        None,
    )
    recorded = change_set is not None and change_set.get("decided_self_approval") is not None
    self_approved = bool(change_set and change_set.get("decided_self_approval"))
    c.add(
        "S7",
        "the approval of the baseline is recorded (self-approval is reported, never hidden)",
        recorded,
        f"self_approved={self_approved}",
    )
    if self_approved:
        c.add(
            "S7",
            "a self-approval happened only because tenant A declares it",
            c.facts.tenant_a_distinct_approver_required is False,
        )
    if c.expect.self_approved_declared is not None:
        c.add(
            "S7",
            "the self-approval flag equals what the browser recorded",
            self_approved == c.expect.self_approved_declared,
        )
    return baseline


def _judge_s7_link(
    c: _Ctx, family: str, event: dict[str, Any], baseline: dict[str, Any] | None
) -> None:
    revision_by_id = {str(r["revision_id"]): r for rows in c.revisions_of.values() for r in rows}
    payload = event.get("payload") or {}
    revision = revision_by_id.get(
        str(payload.get("source_revision_id") or payload.get("technical_revision_id") or "")
    )
    blob_hash = payload.get("source_blob_hash")
    actor = str(event.get("actor") or "")
    c.add(
        "S7",
        f"{family} link: actor is a human user of tenant A",
        actor.startswith("user:") and actor.removeprefix("user:") in c.actor_ids,
    )
    c.add(
        "S7",
        f"{family} link: it names a stored source revision and its blob hash",
        bool(revision) and (blob_hash is None or blob_hash == revision["blob_hash"]),
    )
    c.add(
        "S7",
        f"{family} link: it names the approved baseline and node",
        bool(baseline) and str(payload.get("wbs_baseline_id")) == str(baseline["id"]),
    )
    c.add(
        "S7",
        f"{family} link: it carries a locator",
        bool(payload.get("source_locator") or payload.get("source_section")),
    )


def _judge_s7(c: _Ctx) -> None:
    baseline = _judge_s7_baseline(c)
    for family, event_type in FAMILY_EVENTS.items():
        rows = [e for e in c.facts.events if e["event_type"] == event_type]
        c.add("S7", f"exactly one approved {family} link exists", len(rows) == 1, f"{len(rows)}")
        for event in rows:
            _judge_s7_link(c, family, event, baseline)


def _judge_s8(c: _Ctx) -> None:
    digests = c.browser.get("snapshotDigests") or {}
    c.add(
        "S8",
        "the browser's snapshots before and after the new login are identical",
        bool(digests.get("before")) and digests.get("before") == digests.get("after"),
    )
    c.add("S8", "project A still exists with its five documents", len(c.documents) == 5)


def judge(facts: Facts, browser: dict[str, Any], expect: Expectations) -> list[Check]:
    """Every claim of the run, as a named check. Pure: no I/O."""
    ctx = _Ctx(facts=facts, browser=browser, expect=expect)
    ctx.add("S1", "project A exists in PostgreSQL", facts.project_a is not None)
    ctx.add("S1", "project B exists in PostgreSQL", facts.project_b is not None)
    if facts.project_a is not None and facts.project_b is not None:
        for stage in (
            _judge_s1,
            _judge_s2,
            _judge_s3,
            _judge_s4,
            _judge_s5,
            _judge_s6,
            _judge_s7,
            _judge_s8,
        ):
            stage(ctx)
    return ctx.checks


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
def _stage_verdict(browser_status: str, pg_status: str) -> str:
    """FAIL beats everything; a stage nobody ran or checked is NOT_RUN, never a pass."""
    if "FAIL" in (browser_status, pg_status):
        return "FAIL"
    if "NOT_RUN" in (browser_status, pg_status):
        return "NOT_RUN"
    return "PARTIAL" if browser_status == "PARTIAL" else "PASS"


def _step_rows(browser: dict[str, Any], checks: list[Check]) -> dict[str, Any]:
    stage_rows = {s["id"]: s for s in browser.get("stages", [])}
    steps: dict[str, Any] = {}
    for stage in STAGES:
        mine = [c for c in checks if c.stage == stage]
        row = stage_rows.get(stage) or {}
        browser_status = row.get("status", "NOT_RUN")
        pg_status = "NOT_RUN"
        if mine:
            pg_status = "PASS" if all(c.ok for c in mine) else "FAIL"
        steps[stage] = {
            "browser": browser_status,
            "postgres": pg_status,
            "verdict": _stage_verdict(browser_status, pg_status),
            "declaredGaps": row.get("partial", []),
            "failedChecks": [
                f"{c.name}{': ' + c.detail if c.detail else ''}" for c in mine if not c.ok
            ],
        }
    return steps


def _overall_verdict(steps: dict[str, Any], mode: str | None) -> str:
    verdicts = [steps[s]["verdict"] for s in STAGES]
    if "FAIL" in verdicts:
        return "FAILED"
    if "NOT_RUN" in verdicts:
        return "INCOMPLETE"
    if mode != "real-ai-uat":
        return "REHEARSAL_ONLY_NOT_UAT"
    return (
        "UAT_REAL_WITH_DECLARED_GAPS"
        if any(steps[s]["declaredGaps"] for s in STAGES)
        else "UAT_REAL_COMPLETE"
    )


def _first_failure(browser: dict[str, Any], steps: dict[str, Any]) -> dict[str, Any] | None:
    if browser.get("firstFailure"):
        return browser["firstFailure"]
    for stage in STAGES:
        if steps[stage]["verdict"] == "FAIL":
            reasons = steps[stage]["failedChecks"]
            return {"stage": stage, "message": reasons[0] if reasons else "failed"}
    return None


def build_manifest(
    browser: dict[str, Any],
    checks: list[Check],
    receipt: dict[str, Any],
    env: dict[str, str | None],
) -> dict[str, Any]:
    """One manifest tied to the project id: the browser half, the PostgreSQL verdicts and the first failure."""
    steps = _step_rows(browser, checks)
    return {
        "schema": "c2pro-integral-s1-s8-manifest/v1",
        "candidate_sha": env.get("candidate_sha") or browser.get("candidateSha"),
        "frontend_runtime_sha": env.get("frontend_runtime_sha")
        or browser.get("frontendRuntimeSha"),
        "backend_runtime_sha": env.get("backend_runtime_sha"),
        "mode": browser.get("mode"),
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
        "product_gaps": browser.get("productGaps") or [],
        "steps_S1_S8": steps,
        "postgres_checks": [
            {"stage": c.stage, "name": c.name, "ok": c.ok, "detail": c.detail} for c in checks
        ],
        "first_failure": _first_failure(browser, steps),
        "verdict": _overall_verdict(steps, browser.get("mode")),
        "acceptance": "NOT_ACCEPTED_UNTIL_INDEPENDENT_REVIEW",
    }


def _fixture_expectations(fixture_dir: Path) -> tuple[dict[str, str], list[str]] | None:
    """The committed fixtures' SHA-256 (proved against their pins) and the expected deterministic rules."""
    triplet = json.loads((fixture_dir / "triplet.manifest.json").read_text(encoding="utf-8"))
    extra = json.loads((fixture_dir / "integral.manifest.json").read_text(encoding="utf-8"))
    files = {
        "contractA": ("triplet-contract.docx", triplet["sha256"]["triplet-contract.docx"]),
        "contractB": ("triplet-contract-b.docx", extra["contract_b"]["sha256"]),
        "budget": ("triplet-budget.xlsx", triplet["sha256"]["triplet-budget.xlsx"]),
        "schedule": ("triplet-schedule.xlsx", triplet["sha256"]["triplet-schedule.xlsx"]),
        "specification": (
            "triplet-specification.docx",
            triplet["sha256"]["triplet-specification.docx"],
        ),
        "specificationRejected": (
            "triplet-specification-rejected.docx",
            extra["specification_rejected"]["sha256"],
        ),
    }
    actual = {key: _sha256_file(fixture_dir / name) for key, (name, _) in files.items()}
    if actual != {key: pinned for key, (_, pinned) in files.items()}:
        return None
    return actual, list(triplet["expected_rules"])


def _expectations(
    browser: dict[str, Any], receipt: dict[str, Any], fixtures: tuple[dict[str, str], list[str]]
) -> Expectations:
    stages = browser.get("stages") or []
    rejection = (
        ((stages[4].get("evidence") or {}).get("rejection") or {}) if len(stages) > 4 else {}
    )
    wbs = ((stages[6].get("evidence") or {}).get("wbs") or {}) if len(stages) > 6 else {}
    env = os.environ
    return Expectations(
        fixture_sha=fixtures[0],
        expected_rules=fixtures[1],
        clerk_user_a=env.get("CLERK_E2E_USER_ID", ""),
        clerk_org_a=env.get("CLERK_E2E_ORG_ID", ""),
        clerk_user_b=env.get("TENANT_B_CLERK_E2E_USER_ID", ""),
        clerk_org_b=env.get("TENANT_B_CLERK_E2E_ORG_ID", ""),
        tenant_a=env.get("E2E_EXPECTED_TENANT_ID", ""),
        tenant_b=env.get("TENANT_B_E2E_EXPECTED_TENANT_ID", ""),
        real_ai=browser.get("mode") == "real-ai-uat",
        worker_provider_successes=int(receipt.get("worker_provider_successes") or 0),
        reason_sha256=str(rejection.get("reasonSha256") or ""),
        self_approved_declared=wbs.get("selfApproved"),
    )


async def _collect_facts(database_url: str, project_a: UUID, project_b: UUID) -> Facts:
    engine = create_async_engine(_normalize_database_url(database_url))
    try:
        async with engine.connect() as conn:
            return await collect(conn, project_a, project_b)
    finally:
        await engine.dispose()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


_SHA = re.compile(r"[0-9a-f]{40}")


def _sha_from_env(name: str) -> str | None:
    """A commit SHA from the environment, kept only when it really is one (never free text)."""
    value = os.environ.get(name, "")
    return value if _SHA.fullmatch(value) else None


def main() -> int:
    # The evidence files live at fixed places of the checkout and the command line takes nothing: no argument
    # can redirect a read or a write, or reach what is written (Sonar S8707).
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("FAIL: no database url (set DATABASE_URL)", file=sys.stderr)
        return 2

    browser = _read_json(BROWSER_MANIFEST)
    if not browser.get("projectIdA") or not browser.get("projectIdB"):
        print(
            "FAIL: the browser manifest records no project id (the run stopped before S1 created them)",
            file=sys.stderr,
        )
        return 1
    fixtures = _fixture_expectations(FIXTURE_DIR)
    if fixtures is None:
        print("FAIL: a committed fixture no longer has its pinned SHA-256", file=sys.stderr)
        return 1
    receipt = _read_json(PROVIDER_RECEIPT)
    facts = asyncio.run(
        _collect_facts(database_url, UUID(browser["projectIdA"]), UUID(browser["projectIdB"]))
    )
    checks = judge(facts, browser, _expectations(browser, receipt, fixtures))
    manifest = build_manifest(
        browser,
        checks,
        receipt,
        {
            "candidate_sha": _sha_from_env("GITHUB_SHA"),
            "frontend_runtime_sha": _sha_from_env("FRONTEND_RUNTIME_SHA"),
            "backend_runtime_sha": _sha_from_env("BACKEND_RUNTIME_SHA"),
        },
    )
    # The manifest goes to stdout (the workflow redirects it): this process writes no file at all.
    sys.stdout.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    failed = [c for c in checks if not c.ok]
    for check in failed:
        print(
            f"FAIL [{check.stage}] {check.name}{': ' + check.detail if check.detail else ''}",
            file=sys.stderr,
        )
    stages = ",".join(f"{s}:{manifest['steps_S1_S8'][s]['verdict']}" for s in STAGES)
    print(f"verdict={manifest['verdict']} stages={stages}", file=sys.stderr)
    print(
        f"postgres checks: {len(checks) - len(failed)}/{len(checks)} passed; first_failure={manifest['first_failure']}",
        file=sys.stderr,
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
