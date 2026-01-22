from __future__ import annotations

from pathlib import Path
import sys

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_graph_runs_with_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("C2PRO_AI_MOCK", "1")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test-anon-key")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret")

    repo_root = Path(__file__).resolve().parents[2]
    api_root = repo_root / "apps" / "api"
    if str(api_root) not in sys.path:
        sys.path.insert(0, str(api_root))

    from src.ai.graph.workflow import get_graph_app

    app = get_graph_app()
    state = {
        "document_text": "Contrato de obra con clausula de penalizacion",
        "project_id": "test-project",
        "tenant_id": "",
        "risks": [],
        "wbs": [],
        "messages": [],
        "next_step": "",
        "human_approval_required": False,
        "analysis_id": None,
    }

    result = await app.ainvoke(state, config={"configurable": {"thread_id": "test-project"}})

    assert result["next_step"] in {"risk_extractor", "wbs_extractor"}
    assert isinstance(result["messages"], list)
    assert result["human_approval_required"] is False
