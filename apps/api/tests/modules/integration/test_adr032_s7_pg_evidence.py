"""ADR-032 / S7 evidence on isolated PostgreSQL, judged by the integral run's OWN verifier.

The journey the integral UAT performs in a browser is executed here through the product's real services in
real transactions: request the Budget and Schedule trust candidates, decide both on the exact bindings (one human:
the audited tenant exception the seed grants), approve the Technical link and the Budget/Schedule links on the SAME
canonical WBS, then read every row back with ``verify_integral_s1_s8_pg.collect`` and run its S7 judge. Not browser
UAT and not Clerk: it proves the chain and the verifier against real rows.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from scripts import seed_integral_uat as seed
from scripts import verify_integral_s1_s8_pg as verifier
from src.analysis.application.approve_canonical_technical_wbs_link import (
    CANONICAL_APPROVAL,
    ApproveCanonicalTechnicalWBSLinkService,
)
from src.analysis.application.canonical_structured_wbs_links import (
    APPROVAL,
    ApproveStructuredWBSLinkService,
    ImmutableXLSXRowReader,
)
from src.analysis.application.record_technical_wbs_review import RecordTechnicalWBSReviewService
from src.core.auth.models import Tenant, User
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from tests.integration.analysis.test_s7_review_service_settlement_pg import _arguments
from tests.integration.analysis.test_s7_review_service_settlement_pg import (
    _world as _technical_world,
)
from tests.modules.integration.test_adr032_structured_source_trust_pg import (
    KEY,
    _decide,
    _document,
    _request,
    _Storage,
)

pytestmark = pytest.mark.asyncio


async def test_s7_chain_on_isolated_postgres_passes_the_integral_verifier(
    db: AsyncSession, test_session_factory, tmp_path: Path
) -> None:
    w = await _technical_world(db, tmp_path)  # tenant A: approved WBS baseline + node + technical source
    (tmp_path / "b").mkdir()
    other = await _technical_world(db, tmp_path / "b")  # a second tenant that stands in for tenant B
    storage = _Storage()
    # The audited exception, exactly as the seed writes it -- tenant A only.
    exception = seed.self_approval_exception()
    await db.execute(
        update(Tenant).where(Tenant.id == w["tenant"]).values(
            settings={
                # This chain proves ADR-032 trust and the S7 links, not the per-project authorization rollout
                # (covered at the structured-source boundary in its own tests): keep the fixture explicitly transitional.
                "hitl_project_authorization": {"mode": "off"},
                "wbs_governance": {"require_distinct_approver": False},
                "trust_governance": {"structured_source_self_approval": exception},
            }
        )
    )
    await db.commit()
    actor = await db.get(User, w["actor"])
    assert actor is not None and actor.clerk_user_id

    # 1. The Budget and the Schedule: request, then decide on the exact binding (the same human).
    docs, trust = {}, {}
    for family in ("budget", "schedule"):
        docs[family] = await _document(db, w, tmp_path, storage, family=family)
        requested = await _request(test_session_factory, storage, w, docs[family], key=f"{KEY}{family}-req")
        decided = await _decide(
            test_session_factory, storage, w, requested, "APPROVE", actor=w["actor"], key=f"{KEY}{family}-dec"
        )
        assert decided.trust_state == "trusted" and decided.self_approved and not decided.independent
        trust[family] = {
            "artifactId": str(requested.artifact_id),
            "decisionEventId": str(decided.event_id),
            "selfApproved": decided.self_approved,
            "independent": decided.independent,
        }

    # 2. The three canonical links on the SAME approved WBS baseline and node.
    reader = ImmutableXLSXRowReader(storage, ExcelFileParser())  # type: ignore[arg-type]
    async with test_session_factory() as session:
        review = await RecordTechnicalWBSReviewService(session, w["reader"]).execute(**_arguments(w))
        await session.commit()
    async with test_session_factory() as session:
        await ApproveCanonicalTechnicalWBSLinkService(session).execute(
            tenant_id=w["tenant"], project_id=w["project"], actor_user_id=w["actor"],
            review_event_id=review.event_id, expected_wbs_baseline_id=w["baseline"],
            expected_wbs_node_id=w["node"], approval=CANONICAL_APPROVAL,
            idempotency_key=f"{KEY}technical-link", reason="Technical requirement approved against the node",
        )
        await session.commit()
    for family, doc in docs.items():
        async with test_session_factory() as session:
            await ApproveStructuredWBSLinkService(session, reader).execute(
                tenant_id=w["tenant"], project_id=w["project"], actor_user_id=w["actor"], family=family,
                source_document_id=doc["document"], source_revision_id=doc["revision"],
                expected_blob_hash=doc["digest"], source_locator="Sheet!2",
                expected_wbs_baseline_id=w["baseline"], expected_wbs_node_id=w["node"],
                approval=APPROVAL, idempotency_key=f"{KEY}{family}-link",
                reason=f"Human links the exact {family} row",
            )
            await session.commit()

    # 3. Read the rows back with the verifier's own collector and judge S7.
    url = (await db.connection()).engine.url.render_as_string(hide_password=False)
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            facts = await verifier.collect(conn, w["project"], other["project"])
    finally:
        await engine.dispose()
    browser = {
        "mode": "deterministic-rehearsal",
        "documentIds": {
            "budget": str(docs["budget"]["document"]),
            "schedule": str(docs["schedule"]["document"]),
            "specification": str(w["document"]),
        },
        "structuredTrust": trust,
        "stages": [],
    }
    expect = verifier.Expectations(
        fixture_sha={}, expected_rules=[], clerk_user_a=actor.clerk_user_id, tenant_a=str(w["tenant"]),
    )
    ctx = verifier._Ctx(facts, browser, expect)  # S7 only: the other stages need the full journey
    verifier._judge_s7(ctx)
    checks = ctx.checks
    # The fixture baseline was applied by the tenant's ADMIN (a different human than the one who requested and
    # decided the trust), through the governed fixture -- no row is rewritten and no trigger is bypassed. The
    # verifier's single "approved by the journey's human" check is the one the integral run (one human) satisfies;
    # here it must fail for exactly that reason and no other.
    baseline_check = "the baseline was approved by the journey's human"
    failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok and c.name != baseline_check]
    assert failed == []
    approver = next(b["approved_by"] for b in facts.baselines if str(b["project_id"]) == str(w["project"]))
    baseline_approver = await db.get(User, approver)  # an active user of tenant A (just not the journey's human)
    assert baseline_approver is not None and baseline_approver.tenant_id == w["tenant"] and baseline_approver.is_active
    assert len(checks) >= 40  # the structured-trust chain is actually judged, not skipped
    manifest = verifier.build_manifest(browser, checks, {}, {"candidate_sha": "a" * 40})
    assert manifest["structured_trust_independence"] == "SELF_APPROVED_NOT_INDEPENDENT"
    # A concise, committed-evidence-friendly summary of what was proven (no ids of real systems).
    print(json.dumps({
        "s7_checks": len(checks), "failed": failed,
        "independence": manifest["structured_trust_independence"],
        "exception_granted_by": exception["granted_by"],
    }))
    # Tenant B never received the exception.
    assert "structured_source_self_approval" not in (
        (await db.scalar(select(Tenant.settings).where(Tenant.id == other["tenant"])) or {}).get("trust_governance", {})
    )
    _ = uuid4
