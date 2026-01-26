from __future__ import annotations

import asyncio
import json
from uuid import UUID, uuid4
from unittest.mock import patch

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.stakeholder_extractor import StakeholderExtractorAgent
from src.ai.ai_service import AIService
from src.core import database as db_module
from src.core.database import Base, get_session
from src.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TenantIsolationMiddleware,
)
from src.core.security import get_current_tenant_id, get_current_user_id
from src.modules.auth.models import Tenant
from src.modules.documents.models import Clause, Document
from src.modules.projects.models import Project, ProjectType
from src.modules.stakeholders.models import (
    Stakeholder,
    StakeholderQuadrant,
    StakeholderWBSRaci,
    WBSItem,
    WBSItemType,
)
from src.services.stakeholder_classifier import StakeholderClassifier, StakeholderInput


async def _override_get_session():
    if db_module._session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with db_module._session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _create_test_schema() -> None:
    if db_module._engine is None:
        raise RuntimeError("Database engine not initialized.")
    async with db_module._engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[
                Tenant.__table__,
                Project.__table__,
                Document.__table__,
                Clause.__table__,
                Stakeholder.__table__,
                WBSItem.__table__,
                StakeholderWBSRaci.__table__,
            ],
        )


async def _seed_auth(session: AsyncSession) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    user_id = uuid4()
    session.add(Tenant(id=tenant_id, name="Stakeholder Flow Tenant", slug=f"tenant-{tenant_id.hex[:8]}"))
    await session.commit()

    email = f"stakeholder-flow-{user_id.hex[:8]}@example.com"
    meta_payload = json.dumps(
        {
            "tenant_id": str(tenant_id),
            "first_name": "Stakeholder",
            "last_name": "Flow",
            "role": "user",
        },
        ensure_ascii=True,
    )
    await session.execute(
        text(
            "INSERT INTO auth.users (id, email, raw_user_meta_data, created_at, updated_at) "
            "VALUES (:id, :email, CAST(:meta AS jsonb), NOW(), NOW())"
        ),
        {
            "id": user_id,
            "email": email,
            "meta": meta_payload,
        },
    )
    await session.commit()
    return tenant_id, user_id


async def _persist_extracted_stakeholders(
    session: AsyncSession,
    project_id: UUID,
    extracted: list[dict[str, str | None]],
) -> list[Stakeholder]:
    created: list[Stakeholder] = []
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()

    for item in extracted:
        key = (
            (item.get("name") or "").strip().lower() or None,
            (item.get("role") or "").strip().lower() or None,
            (item.get("company") or "").strip().lower() or None,
            (item.get("contact_email") or "").strip().lower() or None,
        )
        if key in seen:
            continue
        seen.add(key)

        stakeholder = Stakeholder(
            project_id=project_id,
            name=item.get("name"),
            role=item.get("role"),
            organization=item.get("company"),
            email=item.get("contact_email"),
        )
        session.add(stakeholder)
        created.append(stakeholder)

    await session.commit()
    return created


async def _build_app(tenant_id: UUID, user_id: UUID):
    from src.main import create_application

    app = create_application()
    app.user_middleware = [
        middleware
        for middleware in app.user_middleware
        if middleware.cls
        not in (RateLimitMiddleware, RequestLoggingMiddleware, TenantIsolationMiddleware)
    ]
    app.middleware_stack = app.build_middleware_stack()

    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
    app.dependency_overrides[get_current_user_id] = lambda: user_id
    app.dependency_overrides[get_session] = _override_get_session
    return app


def test_full_stakeholder_lifecycle() -> None:
    async def _run() -> None:
        async def _fake_run_extraction(self, system_prompt: str, user_content: str):
            prompt = system_prompt.lower()
            if "extractor de partes intervinientes" in prompt:
                return {
                    "stakeholders": [
                        {
                            "name": "Juan Perez",
                            "role": "Project Manager",
                            "company": "Acme Corp",
                            "type": "CLIENT",
                            "contact_email": "juan.perez@acme.example",
                        }
                    ]
                }
            if "clasificar stakeholders" in prompt:
                return {
                    "stakeholders": [
                        {
                            "index": 0,
                            "power_score": 9,
                            "interest_score": 9,
                            "quadrant": "MANAGE_CLOSELY",
                        }
                    ]
                }
            return {}

        with patch.object(AIService, "run_extraction", new=_fake_run_extraction):
            app = await _build_app(uuid4(), uuid4())
            async with LifespanManager(app):
                await _create_test_schema()

                if db_module._session_factory is None:
                    raise RuntimeError("Database session factory not initialized.")

                async with db_module._session_factory() as session:
                    tenant_id, user_id = await _seed_auth(session)
                    project_id = uuid4()
                    session.add(
                        Project(
                            id=project_id,
                            tenant_id=tenant_id,
                            name="Stakeholder Flow Project",
                            project_type=ProjectType.CONSTRUCTION,
                        )
                    )
                    wbs_item_id = uuid4()
                    session.add(
                        WBSItem(
                            id=wbs_item_id,
                            project_id=project_id,
                            wbs_code="1.1",
                            name="Foundation",
                            description=None,
                            level=1,
                            item_type=WBSItemType.ACTIVITY,
                        )
                    )
                    await session.commit()

                    extractor = StakeholderExtractorAgent(tenant_id=str(tenant_id))
                    extracted = await extractor.extract("Contract between Acme Corp and Juan Perez.")
                    extracted_payload = [
                        {
                            "name": item.name,
                            "role": item.role,
                            "company": item.company,
                            "contact_email": item.contact_email,
                        }
                        for item in extracted
                    ]
                    stakeholders = await _persist_extracted_stakeholders(
                        session, project_id, extracted_payload
                    )

                    app.dependency_overrides[get_current_tenant_id] = lambda: tenant_id
                    app.dependency_overrides[get_current_user_id] = lambda: user_id

                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        response = await client.get(
                            f"/api/v1/stakeholders/projects/{project_id}"
                        )
                        assert response.status_code == 200
                        payload = response.json()
                        assert len(payload) == 1
                        assert payload[0]["name"] == "Juan Perez"
                        assert payload[0]["power_level"] == "medium"
                        assert payload[0]["interest_level"] == "medium"

                        classifier = StakeholderClassifier(tenant_id=str(tenant_id))
                        enriched = await classifier.classify_batch(
                            [
                                StakeholderInput(
                                    name=stakeholders[0].name,
                                    role=stakeholders[0].role,
                                    company=stakeholders[0].organization,
                                )
                            ],
                            contract_type="contract",
                        )
                        stakeholders[0].power_level = enriched[0].power_level
                        stakeholders[0].interest_level = enriched[0].interest_level
                        stakeholders[0].quadrant = enriched[0].quadrant_db
                        metadata = dict(stakeholders[0].stakeholder_metadata or {})
                        metadata["classification"] = {
                            "power_score": enriched[0].power_score,
                            "interest_score": enriched[0].interest_score,
                            "quadrant": enriched[0].quadrant.value,
                        }
                        stakeholders[0].stakeholder_metadata = metadata
                        await session.commit()

                        assignment_payload = {
                            "task_id": str(wbs_item_id),
                            "stakeholder_id": str(stakeholders[0].id),
                            "role": "RESPONSIBLE",
                        }
                        response = await client.put("/api/v1/assignments", json=assignment_payload)
                        assert response.status_code == 200

                        response = await client.get(f"/api/v1/projects/{project_id}/raci")
                        assert response.status_code == 200
                        matrix = response.json()["matrix"]
                        target_row = next(
                            row for row in matrix if row["task_id"] == str(wbs_item_id)
                        )
                        assert any(
                            cell["stakeholder_id"] == str(stakeholders[0].id)
                            for cell in target_row["assignments"]
                        )

    asyncio.run(_run())


def test_duplicate_extraction_is_deduped() -> None:
    async def _run() -> None:
        async def _fake_run_extraction(self, system_prompt: str, user_content: str):
            return {
                "stakeholders": [
                    {
                        "name": "Juan Perez",
                        "role": "Project Manager",
                        "company": "Acme Corp",
                        "type": "CLIENT",
                        "contact_email": "juan.perez@acme.example",
                    },
                    {
                        "name": "Juan Perez",
                        "role": "Project Manager",
                        "company": "Acme Corp",
                        "type": "CLIENT",
                        "contact_email": "juan.perez@acme.example",
                    },
                ]
            }

        with patch.object(AIService, "run_extraction", new=_fake_run_extraction):
            app = await _build_app(uuid4(), uuid4())
            async with LifespanManager(app):
                await _create_test_schema()

                if db_module._session_factory is None:
                    raise RuntimeError("Database session factory not initialized.")

                async with db_module._session_factory() as session:
                    tenant_id, _user_id = await _seed_auth(session)
                    project_id = uuid4()
                    session.add(
                        Project(
                            id=project_id,
                            tenant_id=tenant_id,
                            name="Dedup Project",
                            project_type=ProjectType.CONSTRUCTION,
                        )
                    )
                    await session.commit()

                    extractor = StakeholderExtractorAgent(tenant_id=str(tenant_id))
                    extracted = await extractor.extract("Contract with Juan Perez.")
                    extracted_payload = [
                        {
                            "name": item.name,
                            "role": item.role,
                            "company": item.company,
                            "contact_email": item.contact_email,
                        }
                        for item in extracted
                    ]
                    stakeholders = await _persist_extracted_stakeholders(
                        session, project_id, extracted_payload
                    )

                    assert len(stakeholders) == 1

    asyncio.run(_run())


def test_unknown_role_defaults_to_monitor() -> None:
    async def _run() -> None:
        async def _fake_run_extraction(self, system_prompt: str, user_content: str):
            if "clasificar stakeholders" in system_prompt.lower():
                return {"stakeholders": []}
            return {}

        with patch.object(AIService, "run_extraction", new=_fake_run_extraction):
            classifier = StakeholderClassifier(tenant_id="test-tenant")
            enriched = await classifier.classify_batch(
                [StakeholderInput(name="Mystery Person", role="Unknown Role", company="Unknown Inc")],
                contract_type="contract",
            )
            assert enriched[0].quadrant_db == StakeholderQuadrant.MONITOR

    asyncio.run(_run())
