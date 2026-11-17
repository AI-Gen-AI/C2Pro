"""S7: four pinned DOCX/XLSX fixtures, canonical WBS and real PostgreSQL.

Exercises the existing worker, Coherence evaluate and persisted alerts, without
real LLM, self-approving anything or fabricating source→WBS links.
A project-level WBS is not evidence that any budget/schedule/spec row has
an approved WBS-node relationship. Assert that distinction explicitly.
"""

from __future__ import annotations

import hashlib
import json
import os
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.scoring import ScoringService
from src.coherence.structured_source_binding import resolve_alert_original_rows
from src.documents.domain.models import DocumentType
from src.wbs.adapters.persistence.link_authority import (
    WBSNotApprovedError,
    require_linkable_wbs_nodes,
)
from tests.integration.document_flow.test_852_schedule_wbs_governance_guard import (
    _canonical,
    _human_wbs,
)
from tests.integration.document_flow.test_contract_schedule_completion_flow import (
    PROVISIONAL_RULE,
    RULE,
    TRIPLET_DIR,
    _evaluate,
    _metadata,
    _project,
    _upload_and_ingest,
    worker,  # noqa: F401 - fixture re-exported into test module
)

pytestmark = pytest.mark.asyncio

FAMILIES = (
    ("triplet-contract.docx", DocumentType.CONTRACT),
    ("triplet-budget.xlsx", DocumentType.BUDGET),
    ("triplet-schedule.xlsx", DocumentType.SCHEDULE),
    ("triplet-specification.docx", DocumentType.TECHNICAL_SPEC),
)
RULES = {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN", PROVISIONAL_RULE}


async def test_four_official_sources_preserve_wbs_and_persist_discrepancies(
    db: AsyncSession,
    test_session_factory,
    worker,
    test_user,
) -> None:
    manifest = json.loads((TRIPLET_DIR / "triplet.manifest.json").read_text())
    project = await _project(db, test_user.tenant_id)
    wbs = await _human_wbs(db, test_user.tenant_id, project)
    before = await _canonical(db, project)
    assert len(before["wbs"]) == 2 and wbs["root"] != wbs["child"]

    sources = {}
    for filename, document_type in FAMILIES:
        raw = (TRIPLET_DIR / filename).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        assert sha == manifest["sha256"][filename]
        document, revision = await _upload_and_ingest(
            db,
            worker,
            test_user,
            project,
            filename=filename,
            content=raw,
            document_type=document_type,
        )
        assert revision.blob_hash == sha
        assert (revision.tenant_id, revision.project_id, revision.document_id) == (
            test_user.tenant_id,
            project,
            document.id,
        )
        sources[filename] = (document, revision)
    assert len({d.id for d, _ in sources.values()}) == 4
    assert len({r.revision_id for _, r in sources.values()}) == 4

    # Uploading sources must NEVER rewrite the canonical WBS or silently
    # declare its package budget/schedule as approved source facts.
    assert await _canonical(db, project) == before
    budget_doc, budget_rev = sources["triplet-budget.xlsx"]
    schedule_doc, schedule_rev = sources["triplet-schedule.xlsx"]
    spec_doc, spec_rev = sources["triplet-specification.docx"]
    assert (await _metadata(db, budget_doc.id))["stated_total_by_revision"][
        str(budget_rev.revision_id)
    ]["total"] == manifest["budget"]["stated_total_eur"]
    finish = (await _metadata(db, schedule_doc.id))["schedule_planned_finish"]
    assert finish["date"] == manifest["schedule"]["planned_finish"]
    assert finish["revision_id"] == str(schedule_rev.revision_id)
    assert finish["source_locator"] == "Plan!4"

    result = await _evaluate(db, test_user, project)
    alerts = {a.rule_id: a for a in result.alerts}
    assert alerts.keys() >= RULES
    assert RULE not in alerts, "submitted schedule is NOT an approved baseline"
    assert "DET-CRS-WBSBUD" not in alerts, "WBS has no sourced approved cost baseline"
    # Both economic alert codes are preserved, but their one common delta
    # contributes just once to scoring once sufficient coverage is obtained.
    economic = [
        s
        for s in result.finding_signals
        if s.rule_id
        in {
            "DET-CRS-CONBUD",
            "DET-CRS-NEGMARGIN",
        }
    ]
    assert {s.rule_id for s in economic} == {"DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"}
    calculator = ScoringService()
    observed = calculator.calculate_detailed(
        economic,
        num_clauses=5,
        coverage_map=dict.fromkeys(calculator._ALL_CATEGORIES, True),
    )
    strongest = max(economic, key=calculator._compute_signal_contribution)
    reference = calculator.calculate_detailed(
        [strongest],
        num_clauses=5,
        coverage_map=dict.fromkeys(calculator._ALL_CATEGORIES, True),
    )
    assert observed.total_findings == 1
    assert observed.raw_penalty_sum == reference.raw_penalty_sum
    assert observed.category_contributions == reference.category_contributions
    assert result.overall_score is None, "partial cross-family evidence cannot be green"
    assert "Plan!4" in alerts[PROVISIONAL_RULE].evidence.claim
    assert str(schedule_rev.revision_id) in alerts[PROVISIONAL_RULE].evidence.claim
    assert "2027-06-30" in alerts[PROVISIONAL_RULE].message
    assert "2027-09-30" in alerts[PROVISIONAL_RULE].message

    await db.commit()
    async with test_session_factory() as observer:
        revisions = (
            (
                await observer.execute(
                    text("""
            SELECT d.filename, d.document_type::text AS document_type,
                   d.id AS document_id, r.revision_id, r.blob_hash
              FROM documents d JOIN document_revisions r ON d.id=r.document_id
             WHERE d.project_id=:p AND d.tenant_id=:t AND r.valid_to IS NULL
        """),
                    {"p": project, "t": test_user.tenant_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(revisions) == 4
        for row in revisions:
            assert row["blob_hash"] == manifest["sha256"][row["filename"]]
            assert row["document_id"] == sources[row["filename"]][0].id
            assert row["revision_id"] == sources[row["filename"]][1].revision_id

        located: dict[str, list[str]] = {}
        for family, original in (
            ("budget", "triplet-budget.xlsx"),
            ("schedule", "triplet-schedule.xlsx"),
        ):
            doc, rev = sources[original]
            rows = (
                (
                    await observer.execute(
                        text("""
                SELECT source_locator, revision_id, payload
                  FROM document_source_units
                 WHERE project_id=:p AND tenant_id=:t AND document_id=:d
                   AND revision_id=:r AND family=:f
            """),
                        {
                            "p": project,
                            "t": test_user.tenant_id,
                            "d": doc.id,
                            "r": rev.revision_id,
                            "f": family,
                        },
                    )
                )
                .mappings()
                .all()
            )
            assert rows and all(row["source_locator"] for row in rows)
            assert all(row["revision_id"] == rev.revision_id for row in rows)
            expected = "Presupuesto!2" if family == "budget" else "Plan!4"
            assert expected in {row["source_locator"] for row in rows}
            located[family] = sorted({row["source_locator"] for row in rows})

        contract_doc, contract_rev = sources["triplet-contract.docx"]
        clauses = (
            await observer.execute(
                text("""
            SELECT full_text, document_id FROM clauses
             WHERE document_id=:doc
        """),
                {"doc": contract_doc.id},
            )
        ).all()
        assert any("30 de junio de 2027" in x.full_text for x in clauses)
        assert any("1.000.000 euros" in x.full_text for x in clauses)

        persisted = (
            (
                await observer.execute(
                    text("""
            SELECT rule_id, category::text AS category,
                   severity::text AS severity, source_clause_id, alert_metadata
              FROM alerts WHERE project_id=:p AND tenant_id=:t
        """),
                    {"p": project, "t": test_user.tenant_id},
                )
            )
            .mappings()
            .all()
        )
        assert {row["rule_id"] for row in persisted} >= RULES
        assert any(
            row["rule_id"] == PROVISIONAL_RULE and row["severity"].lower() == "medium"
            for row in persisted
        )
        assert all(row["rule_id"] != RULE for row in persisted)
        schedule_alert = next(row for row in persisted if row["rule_id"] == PROVISIONAL_RULE)
        assert schedule_alert["source_clause_id"] is None  # no invented trusted contract clause
        schedule_refs = schedule_alert["alert_metadata"]["detection_evidence"]["structured_sources"]
        assert len(schedule_refs) == 1
        assert schedule_refs[0]["document_id"] == str(schedule_doc.id)
        assert schedule_refs[0]["revision_id"] == str(schedule_rev.revision_id)
        assert schedule_refs[0]["source_locator"] == "Plan!4"
        assert schedule_refs[0]["blob_sha256"] == manifest["sha256"]["triplet-schedule.xlsx"]
        assert schedule_alert["alert_metadata"]["original_row_binding"] == (
            "CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED"
        )
        financial = [
            r
            for r in persisted
            if r["rule_id"]
            in {
                "DET-CRS-CONBUD",
                "DET-CRS-NEGMARGIN",
            }
        ]
        assert len(financial) == 2
        group_keys = {row["alert_metadata"].get("economic_discrepancy_key") for row in financial}
        assert len(group_keys) == 1 and next(iter(group_keys)).startswith("CONTRACT_BUDGET:")
        assert all(
            row["alert_metadata"]["economic_impact_accounting"] == "ONE_DELTA_TWO_RELATED_ALERTS"
            for row in financial
        )
        assert all(
            row["alert_metadata"]["related_rule_codes"] == ["DET-CRS-CONBUD", "DET-CRS-NEGMARGIN"]
            for row in financial
        )
        assert all(
            row["alert_metadata"]["severity_qualification"]
            == "NUMERIC_MATERIALITY_NOT_VERIFIED_CONTRACTUAL_LOSS"
            for row in financial
        )
        for finding in financial:
            refs = (
                finding["alert_metadata"]
                .get("detection_evidence", {})
                .get("structured_sources", [])
            )
            assert any(
                ref.get("family") == "budget"
                and ref.get("document_id") == str(budget_doc.id)
                and ref.get("revision_id") == str(budget_rev.revision_id)
                and ref.get("source_locator", "").startswith("Presupuesto!")
                for ref in refs
            ), "financial discrepancy must retain its exact budget source revision"
        assert (
            await observer.scalar(
                text("SELECT count(*) FROM coherence_results WHERE project_id=:p"),
                {"p": project},
            )
            == 0
        )
        # The technical requirements are actually extracted and revision-bound,
        # but stay UNVERIFIED until a separate human source review.
        technical = (
            (
                await observer.execute(
                    text("""
            SELECT clause_code, full_text, revision_id, manually_verified,
                   extraction_confidence, extracted_entities
              FROM clauses WHERE tenant_id=:t AND document_id=:d
             ORDER BY clause_code
        """),
                    {"t": test_user.tenant_id, "d": spec_doc.id},
                )
            )
            .mappings()
            .all()
        )
        assert [row["clause_code"] for row in technical] == ["4.1.2", "4.2"]
        assert all(row["revision_id"] == spec_rev.revision_id for row in technical)
        assert all(
            not row["manually_verified"] and row["extraction_confidence"] is None
            for row in technical
        )
        assert all(
            row["extracted_entities"]["technical_requirement"]["verification_status"]
            == "unverified"
            for row in technical
        )
        assert "35 MPa" in technical[0]["full_text"]
        assert "B500S" in technical[1]["full_text"]
        assert "TECHNICAL" in (result.score_missing_dimensions or [])
        assert spec_doc.id != contract_doc.id
        assert spec_rev.blob_hash == manifest["sha256"]["triplet-specification.docx"]

    from src.temporal.adapters.persistence.document_revision_repository import (
        SqlAlchemyDocumentRevisionRepository,
    )

    assert (
        await SqlAlchemyDocumentRevisionRepository(db).list_lineage(
            budget_doc.id, UUID("00000000-0000-0000-0000-000000000001")
        )
        == []
    )

    # Reading/evaluating the four files cannot promote untrusted document
    # observations into WBS edits or into canonical positive Coherence.
    assert await _canonical(db, project) == before

    # This legacy project tree is NOT an approved WBS baseline. No source
    # mapping may be fabricated or promoted from the four uploaded files.
    with pytest.raises(WBSNotApprovedError):
        await require_linkable_wbs_nodes(
            db,
            tenant_id=test_user.tenant_id,
            project_id=project,
            node_ids=[wbs["child"]],
        )

    # A valid source can acquire a navigable SHA (still NOT HITL-approved).
    # Stale/fabricated revisions, foreign tenants, wrong row and tampered
    # expected hashes all fail closed without a manufactured source binding.
    reference = {
        "family": "schedule",
        "document_id": str(schedule_doc.id),
        "revision_id": str(schedule_rev.revision_id),
        "source_locator": "Plan!4",
    }
    for changes, tenant, expected in (
        ({}, test_user.tenant_id, True),
        ({"revision_id": str(uuid4())}, test_user.tenant_id, False),
        ({"source_locator": "Plan!777"}, test_user.tenant_id, False),
        ({"blob_sha256": "f" * 64}, test_user.tenant_id, False),
        ({}, uuid4(), False),
    ):
        row = {**reference, **changes}
        payload = SimpleNamespace(
            alert_metadata={
                "detection_evidence": {"structured_sources": [row]},
            }
        )
        await resolve_alert_original_rows(
            db,
            tenant_id=tenant,
            project_id=project,
            payloads=[payload],
        )
        resolved_ref = payload.alert_metadata["detection_evidence"]["structured_sources"][0]
        assert (resolved_ref.get("blob_sha256") == schedule_rev.blob_hash) is expected
        assert payload.alert_metadata["original_row_binding"] == (
            "CURRENT_SOURCE_ROW_RESOLVED_NOT_HITL_APPROVED" if expected else "NOT_VERIFIED"
        )

    # Optional evidence-only JSON, directly from read-back PostgreSQL rows.
    # All UUIDs are from a disposable synthetic DB, never from a real tenant.
    if os.environ.get("C2PRO_S7_EMIT_EVIDENCE") == "1":
        print(
            "S7_EVIDENCE_JSON="
            + json.dumps(
                {
                    "scope": "disposable-postgresql-real-parser-stub-provider",
                    "project_id": str(project),
                    "tenant_id": str(test_user.tenant_id),
                    "documents": [
                        {
                            "filename": row["filename"],
                            "document_id": str(row["document_id"]),
                            "revision_id": str(row["revision_id"]),
                            "sha256": row["blob_hash"],
                        }
                        for row in sorted(revisions, key=lambda item: item["filename"])
                    ],
                    "alert_rules": sorted(row["rule_id"] for row in persisted),
                    "economic_alert_count": len(financial),
                    "economic_unique_discrepancy_count": len(group_keys),
                    "economic_single_impact_raw_penalty": observed.raw_penalty_sum,
                    "source_row_locators": located,
                    "alert_evidence_bindings": [
                        {
                            "rule_id": row["rule_id"],
                            "severity": row["severity"],
                            "economic_discrepancy_key": row["alert_metadata"].get(
                                "economic_discrepancy_key"
                            ),
                            "economic_impact_accounting": row["alert_metadata"].get(
                                "economic_impact_accounting"
                            ),
                            "severity_qualification": row["alert_metadata"].get(
                                "severity_qualification"
                            ),
                            "original_row_binding": row["alert_metadata"].get(
                                "original_row_binding"
                            ),
                            "related_rule_codes": row["alert_metadata"].get(
                                "related_rule_codes", []
                            ),
                            "source_clause_id": str(row["source_clause_id"])
                            if row["source_clause_id"]
                            else None,
                            "structured_sources": row["alert_metadata"]
                            .get("detection_evidence", {})
                            .get("structured_sources", []),
                        }
                        for row in sorted(persisted, key=lambda r: r["rule_id"])
                    ],
                    "risk_advisory_provisional": PROVISIONAL_RULE in alerts,
                    "technical_sources": [
                        {
                            "clause_code": row["clause_code"],
                            "revision_id": str(row["revision_id"]),
                            "verification_status": row["extracted_entities"][
                                "technical_requirement"
                            ]["verification_status"],
                        }
                        for row in technical
                    ],
                    "wbs_canonical_nodes": len(before["wbs"]),
                    "wbs_unchanged": True,
                    "wbs_links_approved": "NOT_ATTESTED",
                    "coherence_score": result.overall_score,
                    "technical_coverage": "NOT_ASSESSED",
                },
                sort_keys=True,
            )
        )
