from __future__ import annotations

import json
import os
from typing import Any
from uuid import UUID, uuid4

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.ai.anthropic_wrapper import AIRequest, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType
from src.documents.application.dtos import RagAnswer, RetrievedChunk

logger = structlog.get_logger()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
DEFAULT_TOP_K = 5


class RagService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def ingest_document(
        self,
        *,
        document_id: UUID,
        project_id: UUID,
        text_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        chunks = _split_text(text_content, chunk_size=1000, overlap=200)
        if not chunks:
            return 0

        embeddings = await _embed_texts(chunks)
        chunk_metadata = metadata or {}

        rows = []
        for chunk, embedding in zip(chunks, embeddings):
            rows.append(
                {
                    "id": uuid4(),
                    "document_id": document_id,
                    "project_id": project_id,
                    "content": chunk,
                    "embedding": _format_vector(embedding),
                    "metadata": json.dumps(chunk_metadata),
                }
            )

        await _insert_chunks(self.db_session, rows)
        return len(rows)

    async def answer_question(
        self,
        *,
        question: str,
        project_id: UUID,
        top_k: int = DEFAULT_TOP_K,
    ) -> RagAnswer:
        embedding = (await _embed_texts([question]))[0]
        chunks = await _retrieve_chunks(
            self.db_session,
            project_id=project_id,
            embedding=embedding,
            top_k=top_k,
        )

        if not chunks:
            return RagAnswer(answer="No lo encuentro en el documento", sources=[])

        context = "\n\n".join(chunk.content for chunk in chunks)
        prompt = _build_answer_prompt(question=question, context=context)

        wrapper = get_anthropic_wrapper()
        response = await wrapper.generate(
            AIRequest(
                prompt=prompt,
                system_prompt=(
                    "Responde solo con texto en espanol. "
                    "Si no sabes, di: 'No lo encuentro en el documento'."
                ),
                task_type=AITaskType.COMPLEX_EXTRACTION,
                temperature=0.0,
            )
        )
        return RagAnswer(answer=response.content.strip(), sources=chunks)


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if not text:
        return []
    normalized = " ".join(text.split())
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(normalized), step):
        chunk = normalized[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
    return chunks


async def _embed_texts(texts: list[str]) -> list[list[float]]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": EMBEDDING_MODEL, "input": texts},
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = [item["embedding"] for item in payload.get("data", [])]

    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding response size mismatch.")
    return embeddings


async def _insert_chunks(db_session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    stmt = text(
        """
        INSERT INTO document_chunks (id, document_id, project_id, content, embedding, metadata)
        VALUES (:id, :document_id, :project_id, :content, :embedding::vector, :metadata::jsonb)
        """
    )
    await db_session.execute(stmt, rows)
    await db_session.commit()
    logger.info("rag_chunks_inserted", count=len(rows))


async def _retrieve_chunks(
    db_session: AsyncSession,
    *,
    project_id: UUID,
    embedding: list[float],
    top_k: int,
) -> list[RetrievedChunk]:
    stmt = text(
        """
        SELECT content, metadata, (embedding <=> :embedding::vector) AS distance
        FROM match_documents(:project_id, :embedding::vector, :match_count)
        """
    )
    result = await db_session.execute(
        stmt,
        {
            "project_id": str(project_id),
            "embedding": _format_vector(embedding),
            "match_count": top_k,
        },
    )
    rows = result.fetchall()
    return [
        RetrievedChunk(
            content=row[0],
            metadata=row[1] or {},
            similarity=float(row[2]),
        )
        for row in rows
    ]


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding[:EMBEDDING_DIMENSION]) + "]"


def _build_answer_prompt(*, question: str, context: str) -> str:
    return (
        "Usa el siguiente CONTEXTO para responder la PREGUNTA. "
        "Si no sabes, di exactamente: 'No lo encuentro en el documento'.\n\n"
        f"CONTEXTO:\n{context}\n\n"
        f"PREGUNTA:\n{question}\n"
    )
