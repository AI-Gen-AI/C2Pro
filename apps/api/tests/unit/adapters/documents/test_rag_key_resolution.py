"""
Unit tests for RAG provider key resolution.

Test Suite ID: TS-UD-RAG-CONFIG-001
"""
from __future__ import annotations


def test_openai_key_resolution_falls_back_to_settings(monkeypatch) -> None:
    """Test Suite ID: TS-UD-RAG-CONFIG-001."""
    from src.documents.adapters.rag import rag_service

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(rag_service.settings, "openai_api_key", "settings-openai-key")

    assert rag_service._resolve_openai_api_key() == "settings-openai-key"


def test_openai_key_resolution_prefers_environment(monkeypatch) -> None:
    """Test Suite ID: TS-UD-RAG-CONFIG-001."""
    from src.documents.adapters.rag import rag_service

    monkeypatch.setenv("OPENAI_API_KEY", "environment-openai-key")
    monkeypatch.setattr(rag_service.settings, "openai_api_key", "settings-openai-key")

    assert rag_service._resolve_openai_api_key() == "environment-openai-key"
