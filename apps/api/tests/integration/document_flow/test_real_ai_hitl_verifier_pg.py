"""verify_real_ai_hitl_pg.py against REAL PostgreSQL: its SQL reads the real schema, and its verdict follows what is persisted.

The world is the controlled S5 review (a candidate with five RISK findings, bound to its review, enforce + grants). One
CONFIRMED and one DISMISSED decision are taken through the real route, then the verifier's ``collect`` + ``judge`` read them.
No provider, no browser: the manifest and the governor ledger are synthetic here and say so. What is pinned is that the
verifier's queries match the schema, that a missing guarantee turns the verdict into FAIL, and that a capability the product
lacks turns it into PARTIAL rather than PASS.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.hitl.domain.finding_decision import FindingDecisionAction as A
from tests.integration.document_flow.test_758_checkpoint_lineage_authority_fence import (  # noqa: F401
    _clean_recovery_discovery_rows,
    real_saver,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    worker,  # noqa: F401
)
from tests.integration.document_flow.test_s5_controlled_findings_pg import (  # noqa: F401
    controlled,
    no_risks,
)
from tests.integration.document_flow.test_s5_finding_reconciliation_pg import _decide
from tests.integration.document_flow.test_s5_hitl_reject_and_differentiated_approval import (
    world,  # noqa: F401
)
from tests.integration.document_flow.test_s5_project_review_authorization_pg import (  # noqa: F401
    APPROVE,
    FIND,
    READ,
    Actors,
    actors,
)
from tests.modules.integration.test_issue649_hitl_audit_idempotency import (
    request_sessions,  # noqa: F401
)
from tests.modules.integration.test_p0b_crash_safe_resume_recovery import (
    independent_sessions,  # noqa: F401
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import verify_real_ai_hitl_pg as verifier  # noqa: E402

pytestmark = pytest.mark.asyncio

LEDGER_OK = {
    "calls": 3, "completed": 3, "failed": 0, "in_flight": 0, "spent_usd": 0.04, "reserved_open_usd": 0.0, "refused": [],
    "models": ["claude-haiku-4-5-20251001"], "input_tokens": 5000, "output_tokens": 4000, "message_ids": ["msg_a", "msg_b", "msg_c"],
}
LIMITS = {"max_calls": 12, "max_usd": 1.0}


def manifest_for(w: Any, **over: Any) -> dict[str, Any]:
    base = {
        "mode": "REAL_AI", "aiMockEnv": "0", "failedStep": None, "failure": None, "gaps": [], "blocker": None,
        "projectId": str(w.project_id), "documentId": str(w.document_id), "reviewRowId": str(w.review_row_id),
        "persistedActionsBeforeRelogin": ["CONFIRMED", "DISMISSED", None, None, None],
        "persistedActionsAfterRelogin": ["CONFIRMED", "DISMISSED", None, None, None],
        "persistedAfterReload": True, "reviewStillPending": True,
        "relogin": {"sameUser": True, "decisionsVisible": True},
    }
    base.update(over)
    return base


async def _two_decisions(actors: Actors) -> Any:  # noqa: F811
    person = await actors.user(label="vertical-reviewer")
    await actors.grant(person, READ, FIND, APPROVE)
    await _decide(actors.w, person, 0, 0, A.CONFIRMED)
    await _decide(actors.w, person, 1, 1, A.DISMISSED, reason="not supported by the quoted clause")
    return person


async def _collect(db: AsyncSession, w: Any) -> dict[str, Any]:
    conn = await db.connection()
    return await verifier.collect(conn, w.project_id)


async def test_collect_reads_the_real_schema_and_a_complete_world_is_a_pass(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    await _two_decisions(actors)
    w = actors.w
    facts = await _collect(db, w)
    assert facts["project"] is not None and len(facts["reviews"]) == 1 and facts["candidate"]["trust_state"] == "proposed"
    assert len(facts["candidate"]["risks"]) == 5 and facts["authorization_mode"] == "enforce"
    assert {d["action"] for d in facts["decisions"]} == {"CONFIRMED", "DISMISSED"} and set(facts["active_grants"]) >= CAPS
    verdict = verifier.judge(manifest_for(w), {**facts, "documents": facts["documents"]}, LEDGER_OK, LIMITS)
    assert verdict["failed_checks"] == [] and verdict["verdict"] == "PASS", verdict["failed_checks"]
    names = {c["check"]: c["ok"] for c in verdict["checks"]}
    assert names["pg: ordinal 0 is CONFIRMED"] and names["pg: ordinal 1 is DISMISSED with a non-empty typed reason"]
    assert names["pg: the review is still pending (a finding decision never decides the review)"]
    assert names["pg: the candidate artifact is PROPOSED (nothing was trusted by a finding decision)"]
    assert names["pg: the three review capabilities are actively granted on THIS project"] and names["pg: tenant is in ENFORCE"]


CAPS = {"READ_REVIEW", "REVIEW_FINDING", "APPROVE_CANDIDATE"}


async def test_a_missing_decision_in_postgres_is_a_fail_even_if_the_browser_claims_it(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    person = await actors.user(label="only-one")
    await actors.grant(person, READ, FIND, APPROVE)
    await _decide(actors.w, person, 0, 0, A.CONFIRMED)  # the dismissal the browser reports was never persisted
    facts = await _collect(db, actors.w)
    verdict = verifier.judge(manifest_for(actors.w), facts, LEDGER_OK, LIMITS)
    assert verdict["verdict"] == "FAIL"
    assert "pg: exactly two decisions are recorded, on ordinals 0 and 1" in verdict["failed_checks"]
    assert any("equal PostgreSQL" in f for f in verdict["failed_checks"])


async def test_a_refused_call_or_an_exceeded_cap_is_a_fail(db: AsyncSession, actors: Actors) -> None:  # noqa: F811
    await _two_decisions(actors)
    facts = await _collect(db, actors.w)
    refused = {**LEDGER_OK, "refused": ["GOVERNOR_BUDGET_CAP: ..."]}
    assert "provider: no call was refused by the governor (no cap was hit)" in verifier.judge(manifest_for(actors.w), facts, refused, LIMITS)["failed_checks"]
    overspent = {**LEDGER_OK, "spent_usd": 2.5}
    assert "provider: spend within the budget" in verifier.judge(manifest_for(actors.w), facts, overspent, LIMITS)["failed_checks"]
    mocked = verifier.judge(manifest_for(actors.w, aiMockEnv="1"), facts, {**LEDGER_OK, "calls": 0, "completed": 0, "message_ids": []}, LIMITS)
    assert mocked["verdict"] == "FAIL" and "browser: the scenario ran in REAL_AI mode with C2PRO_AI_MOCK=0" in mocked["failed_checks"]


def test_a_missing_capability_is_partial_with_its_blocker_never_a_pass() -> None:
    db = {"project": {"id": "p", "tenant_id": "t"}, "documents": [{"id": "d", "document_type": "contract"}], "revisions": [{"revision_id": "r"}]}
    manifest = {
        "mode": "REAL_AI", "aiMockEnv": "0", "failedStep": None, "projectId": "p", "documentId": "d",
        "blocker": "FEWER_THAN_TWO_FINDINGS: the panel shows 1 finding(s)", "gaps": [{"code": "FEWER_THAN_TWO_FINDINGS", "detail": "x"}],
    }
    result = verifier.judge(manifest, db, LEDGER_OK, LIMITS)
    assert result["verdict"] == "PARTIAL" and result["blocker"].startswith("FEWER_THAN_TWO_FINDINGS")


def test_the_quality_measurements_separate_contiguous_quotes_from_stitched_ones_and_do_not_confuse_categories_with_risks() -> None:
    contract = "A. The price is fixed.\nB. Completion by 31/12/2025.\nC. Liability is capped."
    risks = [
        {"category": "BUDGET", "clause_ref": "A", "source_quote": "The price is fixed."},
        {"category": "TIME", "clause_ref": "B", "source_quote": "The price is fixed. Completion by 31/12/2025."},  # two sentences joined
        {"category": "LEGAL", "clause_ref": None, "source_quote": ""},
    ]
    q = verifier.quality_measurements(risks, contract, {"BUDGET", "SCHEDULE", "LEGAL", "SCOPE"})
    assert q["quotes_contiguous_in_contract"] == 1 and q["quotes_not_contiguous"] == 1 and q["with_clause_ref"] == 2
    assert q["missing_categories"] == ["SCOPE"] and q["category_coverage_is_not_risk_coverage"] is True
    assert q["title_wording"] == "REQUIRES_HUMAN_REVIEW"
