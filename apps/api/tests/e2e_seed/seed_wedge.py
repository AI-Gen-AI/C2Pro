"""
Deterministic E2E seed for the FRT-192 full-stack wedge (QA-338 CI harness).

Creates a fixed, idempotent dataset that exercises the full stack:
  tenant -> user -> project -> documents -> coherence -> alert -> HITL review

Reuses seeded_auth_context logic (conftest.py) for tenant/user creation.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.adapters.persistence.models import Alert as AlertORM
from src.analysis.domain.enums import AlertSeverity, AlertStatus, AlertType
from src.coherence.adapters.persistence.models import CoherenceResultORM
from src.core.approval import ApprovalStatus
from src.core.auth.models import SubscriptionPlan, Tenant, User, UserRole
from src.core.auth.service import hash_password
from src.documents.adapters.persistence.models import DocumentORM
from src.documents.domain.models import DocumentStatus, DocumentType
from src.modules.hitl.adapters.persistence.models import ReviewItemORM
from src.modules.hitl.domain.entities import ImpactLevel, ReviewStatus
from src.projects.adapters.persistence.models import ProjectORM

# ── Fixed IDs ──────────────────────────────────────────────────────
TENANT_ID = UUID("00000000-0000-0000-0000-00000000a113")
USER_ID = UUID("00000000-0000-0000-0000-00000000b113")
PROJECT_ID = UUID("00000000-0000-0000-0000-00000000c303")

DOC_CONTRACT_ID = UUID("00000000-0000-0000-0000-00000000d401")
DOC_BUDGET_ID = UUID("00000000-0000-0000-0000-00000000d402")
DOC_SCHEDULE_ID = UUID("00000000-0000-0000-0000-00000000d403")

COHERENCE_ID = UUID("00000000-0000-0000-0000-00000000e503")
ALERT_ID = UUID("00000000-0000-0000-0000-00000000f601")
REVIEW_ID = UUID("00000000-0000-0000-0000-00000000f701")

TEST_PASSWORD_HASH = hash_password("TestPassword123!")

# Clerk identifiers — supplied by Codex's CI harness via env vars.
# Stable defaults allow local dev without Clerk configured.
CLERK_E2E_ORG_ID = os.environ.get("CLERK_E2E_ORG_ID", "org_e2e_wedge_default")
CLERK_E2E_USER_ID = os.environ.get("CLERK_E2E_USER_ID", "user_e2e_wedge_default")


def _utcnow_naive() -> datetime:
    """Return naive UTC for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(UTC).replace(tzinfo=None)


# ── Upsert helpers ─────────────────────────────────────────────────


async def _upsert_tenant(db: AsyncSession) -> None:
    """Idempotent tenant upsert — mirrors seeded_auth_context logic."""
    existing = await db.get(Tenant, TENANT_ID)
    if existing is not None:
        existing.is_active = True
        existing.subscription_status = "active"
        existing.clerk_org_id = CLERK_E2E_ORG_ID
        return
    db.add(
        Tenant(
            id=TENANT_ID,
            name="Wedge Gate E2E Tenant",
            slug="i13-real-e2e-tenant",
            subscription_plan=SubscriptionPlan.PROFESSIONAL,
            subscription_status="active",
            ai_budget_monthly=100.0,
            ai_spend_current=0.0,
            max_projects=100,
            max_users=25,
            max_storage_gb=100,
            is_active=True,
            clerk_org_id=CLERK_E2E_ORG_ID,
        )
    )


async def _upsert_user(db: AsyncSession) -> None:
    """Idempotent user upsert — mirrors seeded_auth_context logic."""
    existing = await db.get(User, USER_ID)
    if existing is not None:
        existing.tenant_id = TENANT_ID
        existing.email = "testuser@c2pro.com"
        existing.role = UserRole.ADMIN
        existing.is_active = True
        existing.is_verified = True
        existing.clerk_user_id = CLERK_E2E_USER_ID
        return
    db.add(
        User(
            id=USER_ID,
            tenant_id=TENANT_ID,
            email="testuser@c2pro.com",
            hashed_password=TEST_PASSWORD_HASH,
            first_name="Test",
            last_name="User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            last_login=_utcnow_naive(),
            clerk_user_id=CLERK_E2E_USER_ID,
        )
    )


async def _upsert_project(db: AsyncSession) -> None:
    """Idempotent project upsert — reuses create_project pattern (factories.py)."""
    existing = await db.get(ProjectORM, PROJECT_ID)
    if existing is not None:
        existing.name = "Wedge Gate Pilot"
        existing.code = "WEDGE-3"
        existing.status = "active"
        existing.project_type = "construction"
        return
    db.add(
        ProjectORM(
            id=PROJECT_ID,
            tenant_id=TENANT_ID,
            name="Wedge Gate Pilot",
            code="WEDGE-3",
            status="active",
            project_type="construction",
            description="FRT-192 full-stack E2E wedge gate pilot project",
            currency="EUR",
        )
    )


async def _upsert_documents(db: AsyncSession) -> None:
    """Idempotent document triplet upsert — reuses create_document pattern."""
    specs = [
        (DOC_CONTRACT_ID, "baseline-contract.pdf", DocumentType.CONTRACT, "contract"),
        (DOC_BUDGET_ID, "validated-budget.xlsx", DocumentType.BUDGET, "budget"),
        (DOC_SCHEDULE_ID, "approved-schedule.xlsx", DocumentType.SCHEDULE, "schedule"),
    ]
    for doc_id, filename, doc_type, _label in specs:
        existing = await db.get(DocumentORM, doc_id)
        if existing is not None:
            existing.filename = filename
            existing.document_type = doc_type
            existing.upload_status = DocumentStatus.PARSED
            continue
        db.add(
            DocumentORM(
                id=doc_id,
                tenant_id=TENANT_ID,
                project_id=PROJECT_ID,
                document_type=doc_type,
                filename=filename,
                storage_url=f"projects/{PROJECT_ID}/documents/{filename}",
                file_size_bytes=10240,
                upload_status=DocumentStatus.PARSED,
                created_by=USER_ID,
            )
        )


async def _upsert_coherence(db: AsyncSession) -> None:
    """Idempotent coherence result upsert."""
    existing = await db.get(CoherenceResultORM, COHERENCE_ID)
    category_scores = {
        "SCOPE": 84,
        "BUDGET": 78,
        "QUALITY": 86,
        "TECHNICAL": 80,
        "LEGAL": 88,
        "TIME": 76,
    }
    if existing is not None:
        existing.global_score = 82
        existing.category_scores = category_scores
        existing.score_version = "coherence-v1"
        return
    db.add(
        CoherenceResultORM(
            id=COHERENCE_ID,
            project_id=PROJECT_ID,
            tenant_id=TENANT_ID,
            global_score=82,
            category_scores=category_scores,
            category_details=[],
            alerts=[],
            score_version="coherence-v1",
            calculated_at=_utcnow_naive(),
        )
    )


async def _upsert_alert(db: AsyncSession) -> None:
    """Idempotent alert upsert — references doc-contract as source."""
    existing = await db.get(AlertORM, ALERT_ID)
    if existing is not None:
        existing.title = "Budget deviation has supporting evidence"
        existing.severity = AlertSeverity.MEDIUM
        existing.status = AlertStatus.OPEN
        return
    db.add(
        AlertORM(
            id=ALERT_ID,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            severity=AlertSeverity.MEDIUM,
            alert_type=AlertType.COHERENCE,
            title="Budget deviation has supporting evidence",
            message="Contract baseline shows budget variance within tolerance",
            description="Budget deviation has supporting evidence",
            status=AlertStatus.OPEN,
            approval_status=ApprovalStatus.PENDING,
            affected_entities={"document_id": str(DOC_CONTRACT_ID)},
        )
    )


async def _upsert_review_item(db: AsyncSession) -> None:
    """Idempotent HITL review item upsert — references alert-wedge-1."""
    existing = await db.get(ReviewItemORM, REVIEW_ID)
    if existing is not None:
        existing.current_status = ReviewStatus.PENDING_REVIEW_REQUIRED
        existing.confidence = 0.88
        existing.impact_level = ImpactLevel.MEDIUM
        existing.item_data = {"summary": "Budget deviation has supporting evidence"}
        return
    db.add(
        ReviewItemORM(
            id=REVIEW_ID,
            item_id=ALERT_ID,
            item_type="alert",
            current_status=ReviewStatus.PENDING_REVIEW_REQUIRED,
            confidence=0.88,
            impact_level=ImpactLevel.MEDIUM,
            tenant_id=TENANT_ID,
            project_id=PROJECT_ID,
            document_id=DOC_CONTRACT_ID,
            sla_due_date=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=7),
            item_data={"summary": "Budget deviation has supporting evidence"},
        )
    )


# ── Public entry points ────────────────────────────────────────────


async def seed_e2e_auth_tenancy(db: AsyncSession) -> dict[str, UUID]:
    """Seed ONLY the authentication tenancy: tenant + user, nothing else.

    The canonical P0b journey must create its own clean project and upload its
    own document through the browser, so seeding a project or documents would
    invalidate exactly what that gate is meant to prove. This reuses the same
    upserts as seed_wedge_e2e rather than adding a parallel tenant bootstrap.

    Idempotent. Returns the fixed tenant/user ids for downstream assertions.
    """
    await _upsert_tenant(db)
    await db.flush()
    await _upsert_user(db)
    await db.commit()

    return {"tenant_id": TENANT_ID, "user_id": USER_ID}


async def seed_wedge_e2e(db: AsyncSession) -> dict[str, UUID]:
    """
    Create the FRT-192 wedge seed dataset.

    Idempotent: safe to call multiple times.  Each entity is upserted
    (select-or-create) so re-runs do not duplicate rows.

    Returns a dict of all created IDs for downstream assertions.
    """
    await _upsert_tenant(db)
    await db.flush()
    await _upsert_user(db)
    await db.flush()
    await _upsert_project(db)
    await db.flush()
    await _upsert_documents(db)
    await _upsert_coherence(db)
    await _upsert_alert(db)
    await _upsert_review_item(db)
    await db.commit()

    return {
        "tenant_id": TENANT_ID,
        "user_id": USER_ID,
        "project_id": PROJECT_ID,
        "doc_contract_id": DOC_CONTRACT_ID,
        "doc_budget_id": DOC_BUDGET_ID,
        "doc_schedule_id": DOC_SCHEDULE_ID,
        "coherence_id": COHERENCE_ID,
        "alert_id": ALERT_ID,
        "review_id": REVIEW_ID,
    }
