"""Nonproduction ONLY: seed one ACC-01 S7 Clerk browser UAT project and WBS.

This seed builds trusted synthetic SOURCE FIXTURES, but writes NO canonical
Budget/Schedule/Technical approvals. Those decisions are executed by browser
requests carrying the genuine Clerk session token in the Playwright test.
This is S7 approval/relogin UAT, not S1-S8 AI/ingestion qualification.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import docx
from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import DocumentArtifactORM
from src.core.auth.models import UserRole
from src.core.database import close_db, get_raw_session, init_db
from src.documents.adapters.persistence.models import ClauseORM, DocumentORM
from src.documents.adapters.storage.factory import build_storage_service
from src.documents.domain.models import DocumentType
from src.temporal.adapters.persistence.models import DocumentRevisionORM
from src.wbs.adapters.persistence.governance_repository import Actor
from src.wbs.domain.governance import ActorKind
from tests.e2e_seed.seed_wedge import seed_wedge_e2e
from tests.integration.analysis.test_s7_review_service_settlement_pg import SOURCE
from tests.integration.analysis.test_s7_structured_wbs_three_source_pg import (
    _structured_document,
)
from tests.modules.integration.test_pc2a1_wbs_governance_foundation import (
    Scope,
    _user,
)
from tests.modules.integration.test_pc2a2_wbs_governed_apply import _baseline_one


async def _technical_source(
    db: AsyncSession, w: dict, storage: object,
) -> dict[str, str]:
    doc = docx.Document()
    doc.add_paragraph(SOURCE)
    stream = io.BytesIO()
    doc.save(stream)
    data = stream.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    document_id, revision_id, clause_id = uuid4(), uuid4(), uuid4()
    key = f"synthetic/s7-clerk/{w['project']}/{revision_id}.docx"
    await storage.upload_bytes(data, key)  # type: ignore[attr-defined]
    db.add(DocumentORM(
        id=document_id, tenant_id=w["tenant"], project_id=w["project"],
        document_type=DocumentType.TECHNICAL_SPEC, filename="s7-spec.docx",
        file_format=".docx", file_hash=digest, created_by=w["actor"],
    ))
    await db.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    db.add(DocumentRevisionORM(
        revision_id=revision_id, tenant_id=w["tenant"], project_id=w["project"],
        document_id=document_id, rev_no=1, blob_hash=digest, blob_key=key,
        valid_from=now, created_at=now,
    ))
    await db.flush()
    db.add(DocumentArtifactORM(
        artifact_id=uuid4(), tenant_id=w["tenant"], project_id=w["project"],
        document_id=document_id, document_revision_id=revision_id,
        artifact_version=1, artifact_hash="a" * 64,
        payload={"doc_type": "technical_spec"},
        trust_state="trusted", lifecycle_status="active",
    ))
    db.add(ClauseORM(
        id=clause_id, tenant_id=w["tenant"], project_id=w["project"],
        document_id=document_id, revision_id=revision_id,
        clause_code="4.1.2", title=SOURCE, full_text=SOURCE,
        text_start_offset=0, text_end_offset=len(SOURCE),
        extracted_entities={
            "technical_requirement": {
                "source_section": "4.1.2", "verification_status": "unverified",
            },
            "evidence_location": {"revision_id": str(revision_id)},
        },
        extraction_confidence=None, extraction_model="deterministic-technical-section-v1",
        manually_verified=False,
    ))
    await db.commit()
    return {
        "documentId": str(document_id), "revisionId": str(revision_id),
        "clauseId": str(clause_id), "blobHash": digest,
    }


async def seed() -> dict:
    if os.getenv("ENVIRONMENT", "").lower() != "test" or os.getenv("STORAGE_PROVIDER", "").lower() != "local":
        raise RuntimeError("S7_CLERK_SEED_REQUIRES_LOCAL_TEST_ONLY")
    if not os.getenv("CLERK_E2E_USER_ID") or not os.getenv("CLERK_E2E_ORG_ID"):
        raise RuntimeError("S7_CLERK_SEED_REQUIRES_AUTHENTIC_TEST_CLERK_FIXTURE")

    await init_db()
    try:
        async with get_raw_session() as db:
            ids = await seed_wedge_e2e(db)
            author = Actor(user_id=ids["user_id"], kind=ActorKind.HUMAN, role=UserRole.USER.value)
            admin = await _user(db, ids["tenant_id"], UserRole.ADMIN)
            admin2 = await _user(db, ids["tenant_id"], UserRole.ADMIN)
            scope = Scope(ids["tenant_id"], ids["project_id"], author, admin, admin2)
            _, nodes, applied = await _baseline_one(db, scope)
            w = {
                "tenant": ids["tenant_id"], "project": ids["project_id"],
                "actor": ids["user_id"], "baseline": applied.baseline_id,
                "node": nodes["1.1"],
            }
            storage = build_storage_service()
            technical = await _technical_source(db, w, storage)
            with tempfile.TemporaryDirectory(prefix="s7-clerk-") as directory:
                files: dict[str, Path] = {}
                budget = await _structured_document(db, w, Path(directory), "budget", files)
                schedule = await _structured_document(db, w, Path(directory), "schedule", files)
                for key, file in files.items():
                    await storage.upload_bytes(file.read_bytes(), key)
            result = {
                "projectId": str(w["project"]),
                "baselineId": str(w["baseline"]),
                "nodeId": str(w["node"]),
                "technical": technical,
                "budget": {
                    "documentId": str(budget["source_document_id"]),
                    "revisionId": str(budget["source_revision_id"]),
                    "blobHash": budget["expected_blob_hash"],
                    "sourceLocator": budget["source_locator"],
                },
                "schedule": {
                    "documentId": str(schedule["source_document_id"]),
                    "revisionId": str(schedule["source_revision_id"]),
                    "blobHash": schedule["expected_blob_hash"],
                    "sourceLocator": schedule["source_locator"],
                },
                "fixtureMode": "synthetic-source-only",
                "approvalEventsSeeded": False,
            }
            return result
    finally:
        await close_db()


if __name__ == "__main__":
    data = asyncio.run(seed())
    path = Path("../web/playwright-report/s7-clerk-source.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    print("S7 Clerk source fixture seeded with no approval events", data["projectId"])
