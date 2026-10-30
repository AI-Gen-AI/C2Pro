#!/usr/bin/env python3
"""S3: direct PostgreSQL acceptance of technical source -> HITL -> Health.

No writes, no trust inference from browser screenshots. After the REAL Clerk
browser approved a synthetic technical SOURCE, independently assert exactly
which revision became trusted, exact technical quotes and explicit nullable
Health, without inventing project technical-compliance success.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from verify_s2_triplet_pg import (
    annotation,
    invalid,
    local_test_dsn,
    source_trace,
    specs,
)


def browser_facts(report: dict[str, Any], manifest: dict[str, Any], fixtures: Path):
    project_id, sources = source_trace(report, manifest, fixtures)
    tests = [
        test for spec in specs(report.get("suites", []))
        if str(spec.get("file", "")).endswith("triplet-user-journey.spec.ts")
        for test in spec.get("tests", [])
        if test.get("projectName") == "triplet-journey"
    ]
    if len(tests) != 1:
        invalid("S3 browser evidence must be unique")
    health = annotation(tests[0], "s3-technical-health")
    approval = annotation(tests[0], "s3-technical-source-approval")
    spec = next((row for row in sources if row[1] == "technical_spec"), None)
    if spec is None:
        invalid("S3 document family was not uploaded")
    _, _, document_id, revision_id, _ = spec
    if (
        str(health.get("projectId")) != str(project_id)
        or str(approval.get("projectId")) != str(project_id)
        or health.get("documentId") != str(document_id)
        or approval.get("documentId") != str(document_id)
        or approval.get("status") != 200
        or approval.get("sourceOnly") is not True
        or health.get("technicalState") != "unassessed"
        or health.get("technicalScore") is not None
        or health.get("overallScore") is not None
        or "TECHNICAL" not in (health.get("missingDimensions") or [])
    ):
        invalid("S3 browser did not demonstrate source-only approval and NULL Health")
    return project_id, document_id, revision_id


async def verify(dsn: str, project_id: UUID, document_id: UUID, revision_id: UUID):
    engine = create_async_engine(local_test_dsn(dsn))
    try:
        async with engine.connect() as db:
            await db.execute(text("SET TRANSACTION READ ONLY"))
            doc = (await db.execute(text(
                "SELECT d.tenant_id, d.project_id, d.document_type::text AS type, "
                "d.upload_status::text AS status, d.document_metadata AS metadata, "
                "d.parsing_error FROM documents d WHERE d.id=:d"
            ), {"d": document_id})).one_or_none()
            if doc is None or doc.type != "technical_spec" or doc.project_id != project_id:
                invalid("S3 technical document/project identity mismatch")
            if doc.status != "analyzed" or doc.parsing_error is not None:
                invalid("S3 document did not complete analysis after HITL")
            tenant_id = doc.tenant_id
            rows = (await db.execute(text(
                "SELECT c.clause_code, c.full_text, c.revision_id, "
                "c.extracted_entities AS entities, c.extraction_confidence, "
                "c.manually_verified FROM clauses c "
                "WHERE c.project_id=:p AND c.document_id=:d AND c.tenant_id=:t "
                "ORDER BY c.clause_code"
            ), {"p": project_id, "d": document_id, "t": tenant_id})).all()
            if len(rows) != 2 or [row.clause_code for row in rows] != ["4.1.2", "4.2"]:
                invalid("S3 real DOCX has not persisted both numbered technical requirements")
            for row in rows:
                ent = row.entities or {}
                requirement = ent.get("technical_requirement") or {}
                location = ent.get("evidence_location") or {}
                if (
                    row.revision_id != revision_id
                    or location.get("revision_id") != str(revision_id)
                    or requirement.get("source_section") != row.clause_code
                    or requirement.get("verification_status") != "unverified"
                    or row.extraction_confidence is not None
                    or row.manually_verified
                    or not row.full_text.startswith("Section " + row.clause_code)
                ):
                    invalid("S3 technical obligation is unbound, invented or falsely verified")
            if (doc.metadata or {}).get("technical_requirement_count") != 2:
                invalid("S3 technical requirements missing from durable metadata")
            artifacts = (await db.execute(text(
                "SELECT artifact_id, artifact_hash, document_revision_id, "
                "trust_state, lifecycle_status FROM document_artifacts "
                "WHERE tenant_id=:t AND project_id=:p AND document_id=:d "
                "AND document_revision_id=:r"
            ), {"t": tenant_id, "p": project_id, "d": document_id, "r": revision_id})).all()
            trusted = [
                a for a in artifacts
                if a.trust_state == "trusted" and a.lifecycle_status == "active"
            ]
            if len(trusted) != 1:
                invalid("S3 technical source is not EXACTLY one active trusted revision")
            artifact = trusted[0]
            reviews = (await db.execute(text(
                "SELECT id, upper(current_status::text) AS status, approved_by, approved_at, "
                "review_metadata->'candidate_binding'->>'artifact_id' AS bound_id, "
                "review_metadata->'candidate_binding'->>'artifact_hash' AS bound_hash "
                "FROM review_items "
                "WHERE tenant_id=:t AND project_id=:p AND document_id=:d"
            ), {"t": tenant_id, "p": project_id, "d": document_id})).all()
            if not any(
                r.status == "APPROVED" and r.approved_by and r.approved_at
                and r.bound_id == str(artifact.artifact_id)
                and r.bound_hash == artifact.artifact_hash
                for r in reviews
            ):
                invalid("S3 source trust lacks matching human approval, candidate id and hash")
            numeric = (await db.execute(text(
                "SELECT count(*) FROM coherence_results WHERE project_id=:p "
                "AND tenant_id=:t"
            ), {"p": project_id, "t": tenant_id})).scalar_one()
            if numeric:
                invalid("S3 source-only evaluation persisted a fabricated numeric Health")
            return {
                "gate": "S3-TECHNICAL-SOURCE-HEALTH",
                "result": "PASS",
                "project_id": str(project_id),
                "technical_document_id": str(document_id),
                "technical_revision_id": str(revision_id),
                "technical_requirement_sections": ["4.1.2", "4.2"],
                "trusted_source": True,
                "human_source_approval_bound": True,
                "analysis_status": doc.status,
                "technical_assessment": "UNVERIFIED",
                "technical_score": None,
                "overall_score": None,
                "numeric_coherence_rows": 0,
            }
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--playwright-json", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fixture-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.playwright_json.read_text())
    manifest = json.loads(args.manifest.read_text())
    project_id, document_id, revision_id = browser_facts(
        report, manifest, args.fixture_dir
    )
    result = await verify(
        os.environ.get("TEST_DATABASE_URL", ""),
        project_id, document_id, revision_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print("PASS S3: technical sections, exact HITL, analysis, and NULL Health verified in PostgreSQL")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (ValueError, KeyError, OSError, TypeError) as exc:
        raise SystemExit(str(exc)) from exc
