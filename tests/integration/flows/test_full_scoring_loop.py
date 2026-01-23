from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.config import settings
from src.core import database as db_module
from src.core.database import Base
from src.modules.auth.models import Tenant, User
from src.modules.coherence import service as coherence_service
from src.modules.documents.models import DocumentStatus


FIXTURE_PDF = Path("tests/fixtures/files/contract_sample.pdf")


@asynccontextmanager
async def _no_rls_session(_tenant_id: UUID):
    if db_module._session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with db_module._session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _seed_auth(session_factory: async_sessionmaker[AsyncSession]) -> tuple[UUID, UUID]:
    tenant_id = uuid4()
    user_id = uuid4()

    async with session_factory() as session:
        tenant = Tenant(id=tenant_id, name="Test Tenant")
        user = User(
            id=user_id,
            tenant_id=tenant_id,
            email="tester@example.com",
            hashed_password="hashedpassword",
        )
        session.add_all([tenant, user])
        await session.commit()

    return tenant_id, user_id


def _make_auth_header(user_id: UUID, tenant_id: UUID) -> dict[str, str]:
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "email": "tester@example.com",
        "role": "admin",
        "exp": datetime.utcnow() + timedelta(minutes=30),
        "iat": datetime.utcnow(),
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_upload_and_calculate_score(monkeypatch) -> None:
    from src.main import create_application
    from src.ai.ai_service import AIService
    from src.core.celery_app import celery_app
    from src.modules.documents import models as document_models
    from src.modules.projects import models as project_models
    import src.modules.documents.router as documents_router
    import src.modules.documents.service as documents_service

    app = create_application()

    # Avoid RLS SET LOCAL for SQLite during tests.
    monkeypatch.setattr(db_module, "get_session_with_tenant", _no_rls_session)
    monkeypatch.setattr(documents_service, "get_session_with_tenant", _no_rls_session)
    monkeypatch.setattr(documents_router, "get_session_with_tenant", _no_rls_session)

    async def _fake_run_extraction(self, system_prompt: str, user_content: str):
        prompt = system_prompt.lower()
        if "wbs" in prompt or "cronograma" in prompt:
            return [{"code": "1.1", "name": "Foundation", "confidence": 0.9}]
        if "stakeholder" in prompt or "roles" in prompt:
            return [{"name": "Owner", "role": "Responsible", "confidence": 0.85}]
        return []

    monkeypatch.setattr(AIService, "run_extraction", _fake_run_extraction)
    celery_app.conf.task_always_eager = True

    async with LifespanManager(app):
        if db_module._engine is None:
            raise RuntimeError("Database engine not initialized.")

        async with db_module._engine.begin() as conn:
            _ = document_models.Document
            _ = project_models.Project
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(
            bind=db_module._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

        tenant_id, user_id = await _seed_auth(session_factory)
        headers = _make_auth_header(user_id, tenant_id)

        coherence_service.MOCK_PROJECT_DB[str(tenant_id)] = {"name": "Test Project"}

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=30.0,
            headers=headers,
        ) as client:
            project_payload = {"name": "Integration Project", "project_type": "construction"}
            project_response = await client.post("/api/v1/projects", json=project_payload)
            assert project_response.status_code == 201
            project_id = project_response.json()["id"]

            # Ensure coherence service has data for this project_id
            coherence_service.MOCK_PROJECT_DB[project_id] = {"name": "Integration Project"}
            coherence_service.MOCK_SCORE_DB[project_id] = coherence_service.CoherenceScore(
                project_id=UUID(project_id),
                score=82,
                breakdown={"critical": 0, "high": 1, "medium": 1, "low": 0},
                top_drivers=["Budget variance detected"],
            )

            with FIXTURE_PDF.open("rb") as pdf_file:
                files = {"file": ("contract_sample.pdf", pdf_file, "application/pdf")}
                data = {"document_type": "contract"}
                upload_response = await client.post(
                    f"/api/v1/projects/{project_id}/documents",
                    files=files,
                    data=data,
                )

            assert upload_response.status_code == 202
            upload_body = upload_response.json()
            assert upload_body.get("task_id")
            document_id = upload_body["id"]

            # Trigger parsing explicitly (Celery task uses mock DB in this environment).
            parse_response = await client.post(f"/api/v1/documents/{document_id}/parse")
            assert parse_response.status_code == 202

            parsed = False
            deadline = asyncio.get_event_loop().time() + 10
            while asyncio.get_event_loop().time() < deadline:
                poll_response = await client.get(f"/api/v1/projects/{project_id}/documents")
                assert poll_response.status_code == 200
                entries = poll_response.json()
                target = next((doc for doc in entries if doc["id"] == document_id), None)
                if target and target["status"] == DocumentStatus.PARSED.value.upper():
                    parsed = True
                    break
                await asyncio.sleep(0.5)

            assert parsed is True

            score_response = await client.get(f"/api/v1/projects/{project_id}/coherence-score")
            assert score_response.status_code == 200
            score_body = score_response.json()
            assert 0 <= score_body["score"] <= 100
            assert score_body["breakdown"]
