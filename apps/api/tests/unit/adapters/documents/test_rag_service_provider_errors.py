"""
Unit tests for RAG provider failure handling.
Refers to Suite ID: TS-UD-RAG-ERR-001.
"""
from __future__ import annotations

import httpx
import pytest

from src.documents.application.dtos import RetrievedChunk
from src.core.ai.anthropic_wrapper import AIResponse
from src.documents.adapters.rag import rag_service
from src.documents.adapters.rag.rag_service import RagProviderUnavailableError, RagService


@pytest.mark.asyncio
async def test_i12_rag_answer_translates_openai_429_to_provider_unavailable(monkeypatch) -> None:
    """TS-UD-RAG-ERR-001: OpenAI embedding throttling must not leak raw HTTPStatusError tracebacks."""

    async def _raise_429(_texts):
        request = httpx.Request("POST", "https://api.openai.com/v1/embeddings")
        response = httpx.Response(429, request=request, text="rate limited")
        raise httpx.HTTPStatusError(
            "Client error '429 Too Many Requests'",
            request=request,
            response=response,
        )

    monkeypatch.setattr(rag_service, "_embed_texts", _raise_429)
    async def _project_exists(*_, **__):
        return True

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_exists)

    with pytest.raises(RagProviderUnavailableError) as exc:
        await RagService(db_session=None).answer_question(
            tenant_id=rag_service.uuid4(),
            project_id=rag_service.uuid4(),
            question="what is the end date of the project",
            top_k=5,
        )

    assert exc.value.status_code == 429
    assert "embedding provider is temporarily unavailable" in str(exc.value)


@pytest.mark.asyncio
async def test_i12_rag_answer_rejects_unknown_project_before_embedding(monkeypatch) -> None:
    """TS-UD-RAG-ERR-001: a document_id in the project_id slot should return not found before embeddings."""
    embedding_called = False

    async def _embed(_texts):
        nonlocal embedding_called
        embedding_called = True
        return [[0.1]]

    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    async def _project_missing(*_, **__):
        return False

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_missing)

    with pytest.raises(rag_service.RagProjectNotFoundError):
        await RagService(db_session=None).answer_question(
            tenant_id=rag_service.uuid4(),
            project_id=rag_service.uuid4(),
            question="what is the end date of the project",
            top_k=5,
        )

    assert embedding_called is False


@pytest.mark.asyncio
async def test_i12_rag_retrieval_uses_tenant_scoped_direct_chunk_query() -> None:
    """TS-UD-RAG-ERR-001: retrieval must not depend on stale match_documents function signatures."""

    class _Result:
        def fetchall(self):
            return []

    class _Session:
        def __init__(self) -> None:
            self.sql = ""
            self.params = {}

        async def execute(self, stmt, params):
            self.sql = str(stmt)
            self.params = params
            return _Result()

    session = _Session()

    await rag_service._retrieve_chunks(
        session,
        tenant_id=rag_service.uuid4(),
        project_id=rag_service.uuid4(),
        embedding=[0.1],
        top_k=5,
    )

    assert "FROM document_chunks" in session.sql
    assert "tenant_id = CAST(:tenant_id AS uuid)" in session.sql
    assert "project_id = CAST(:project_id AS uuid)" in session.sql
    assert "LIMIT CAST(:match_count AS integer)" in session.sql
    assert "match_documents(" not in session.sql
    assert session.params["match_count"] == 5


@pytest.mark.asyncio
async def test_i12_rag_answer_falls_back_to_schedule_end_date_when_llm_unavailable(monkeypatch) -> None:
    """TS-UD-RAG-ERR-001: schedule date questions should not 500 when answer LLM is unavailable."""

    async def _project_exists(*_, **__):
        return True

    async def _embed(_texts):
        return [[0.1]]

    async def _retrieve(*_, **__):
        return [
            RetrievedChunk(
                content=(
                    "WBS: SCH-033; Task: Emisión del Operational Acceptance Certificate; "
                    "Start: 2014-10-05; End: 2015-01-02; Duration: 90"
                ),
                metadata={"document_type": "schedule"},
                similarity=0.1,
            )
        ]

    class _UnavailableWrapper:
        async def generate(self, _request):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_exists)
    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    monkeypatch.setattr(rag_service, "_retrieve_chunks", _retrieve)
    monkeypatch.setattr(rag_service, "get_anthropic_wrapper", lambda: _UnavailableWrapper())

    answer = await RagService(db_session=None).answer_question(
        tenant_id=rag_service.uuid4(),
        project_id=rag_service.uuid4(),
        question="what is the end date of the project",
        top_k=5,
    )

    assert "2015-01-02" in answer.answer
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_i12_rag_answer_falls_back_to_schedule_equipment_when_llm_unavailable(monkeypatch) -> None:
    """TS-UD-RAG-ERR-001: equipment questions should be answered from schedule chunks when LLM is down."""

    async def _project_exists(*_, **__):
        return True

    async def _embed(_texts):
        return [[0.1]]

    async def _retrieve(*_, **__):
        return [
            RetrievedChunk(
                content=(
                    "WBS: 3.0; Task: Suministro desde el extranjero (Schedule 1) "
                    "Task: Fabricación de transformador 100 MVA; Start: 2013-11-15; End: 2014-05-13 "
                    "Task: Fabricación de transformador 25/31.5 MVA; Start: 2013-11-15; End: 2014-04-13 "
                    "Task: Embalaje y preparación para envío; Start: 2014-05-29; End: 2014-06-07"
                ),
                metadata={"document_type": "schedule"},
                similarity=0.1,
            )
        ]

    class _UnavailableWrapper:
        async def generate(self, _request):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_exists)
    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    monkeypatch.setattr(rag_service, "_retrieve_chunks", _retrieve)
    monkeypatch.setattr(rag_service, "get_anthropic_wrapper", lambda: _UnavailableWrapper())

    answer = await RagService(db_session=None).answer_question(
        tenant_id=rag_service.uuid4(),
        project_id=rag_service.uuid4(),
        question="what are the main equipment to purchase, just say two of them",
        top_k=5,
    )

    assert answer.answer == "Transformador 100 MVA; Transformador 25/31.5 MVA."
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_i12_rag_answer_falls_back_to_contract_damages_when_llm_abstains(monkeypatch) -> None:
    """TS-UD-RAG-ERR-003: penalty questions should summarize retrieved contract damages evidence."""

    async def _project_exists(*_, **__):
        return True

    async def _embed(_texts):
        return [[0.1]]

    async def _retrieve(*_, **__):
        return [
            RetrievedChunk(
                content=(
                    "Any default or breach under the Second Contract shall give the Employer "
                    "an absolute right to terminate this Contract at the Contractor's risk, "
                    "cost and responsibility, either in full or in part and/or recover damages "
                    "under this First Contract as well."
                ),
                metadata={"document_type": "contract"},
                similarity=0.1,
            ),
            RetrievedChunk(
                content=(
                    "No price adjustment shall be allowed for periods of delay for which "
                    "Contractor is entirely responsible. The Employer will, however, be entitled "
                    "to any decrease in the Contract Price."
                ),
                metadata={"document_type": "contract"},
                similarity=0.2,
            ),
        ]

    class _AbstainingWrapper:
        async def generate(self, _request):
            return AIResponse(
                content="No lo encuentro en el documento.",
                model_used="test",
                input_tokens=0,
                output_tokens=0,
                cost_usd=0.0,
                latency_ms=0.0,
            )

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_exists)
    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    monkeypatch.setattr(rag_service, "_retrieve_chunks", _retrieve)
    monkeypatch.setattr(rag_service, "get_anthropic_wrapper", lambda: _AbstainingWrapper())

    answer = await RagService(db_session=None).answer_question(
        tenant_id=rag_service.uuid4(),
        project_id=rag_service.uuid4(),
        question="what are the liquidated damages or delay penalties for the contractor?",
        top_k=10,
    )

    assert "recover damages" in answer.answer
    assert "decrease in the Contract Price" in answer.answer
    assert "No lo encuentro" not in answer.answer


@pytest.mark.asyncio
async def test_i12_rag_answer_translates_generation_failure_to_provider_unavailable(monkeypatch) -> None:
    """TS-UD-RAG-ERR-001: LLM generation failures without extractive answers must not leak tracebacks."""

    async def _project_exists(*_, **__):
        return True

    async def _embed(_texts):
        return [[0.1]]

    async def _retrieve(*_, **__):
        return [
            RetrievedChunk(
                content="General contract context without a deterministic answer.",
                metadata={"document_type": "contract"},
                similarity=0.1,
            )
        ]

    class _UnavailableWrapper:
        async def generate(self, _request):
            raise RuntimeError("model unavailable")

    monkeypatch.setattr(rag_service, "_project_exists_in_tenant", _project_exists)
    monkeypatch.setattr(rag_service, "_embed_texts", _embed)
    monkeypatch.setattr(rag_service, "_retrieve_chunks", _retrieve)
    monkeypatch.setattr(rag_service, "get_anthropic_wrapper", lambda: _UnavailableWrapper())

    with pytest.raises(RagProviderUnavailableError) as exc:
        await RagService(db_session=None).answer_question(
            tenant_id=rag_service.uuid4(),
            project_id=rag_service.uuid4(),
            question="what is the warranty period?",
            top_k=5,
        )

    assert "answer provider is temporarily unavailable" in str(exc.value)
