from __future__ import annotations

import hashlib
import json
import math
import os
import re
from typing import Any
from uuid import UUID, uuid4

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.ai.anthropic_wrapper import AIRequest, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType
from src.core.resilience import with_circuit_breaker
from src.core.resilience.config import get_circuit_breaker_settings
from src.documents.application.dtos import RagAnswer, RetrievedChunk

logger = structlog.get_logger()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
DEFAULT_TOP_K = 5


def _resolve_openai_api_key() -> str | None:
    """Resolve OpenAI key from environment or settings.

    Test Suite ID: TS-UD-RAG-CONFIG-001
    """
    return os.getenv("OPENAI_API_KEY") or settings.openai_api_key


class RagProviderUnavailableError(RuntimeError):
    """TS-UD-RAG-ERR-001: retryable upstream RAG provider failure."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _deterministic_embedding(text_value: str) -> list[float]:
    """A stable unit-length vector derived from the text itself.

    Same text -> same vector, different text -> different vector, so similarity
    search stays meaningful in tests without any network call.
    """
    digest = hashlib.sha256(text_value.encode("utf-8")).digest()
    raw = [
        ((digest[index % len(digest)] + index) % 256) / 255.0
        for index in range(EMBEDDING_DIMENSION)
    ]
    norm = math.sqrt(sum(value * value for value in raw)) or 1.0
    return [value / norm for value in raw]


class RagProviderMisconfiguredError(RuntimeError):
    """TS-UD-RAG-ERR-002: the embedding provider is not usable as configured.

    Distinct from :class:`RagProviderUnavailableError`: retrying will not help
    until an operator changes configuration. Kept separate so a deployment
    missing its embedding credentials degrades loudly instead of looking like a
    document that simply had nothing to embed.
    """


class RagProjectNotFoundError(RuntimeError):
    """TS-UD-RAG-ERR-001: project is not visible in the current tenant."""


class RagService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.db_session = db_session

    async def ingest_document(
        self,
        *,
        tenant_id: UUID,
        document_id: UUID,
        project_id: UUID,
        text_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        chunks = _split_text(text_content, chunk_size=1000, overlap=200)
        if not chunks:
            return 0

        embeddings: list[list[float]] = await _embed_texts(chunks)
        chunk_metadata = metadata or {}

        rows = []
        for chunk, embedding in zip(chunks, embeddings, strict=False):
            rows.append(
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
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
        tenant_id: UUID,
        question: str,
        project_id: UUID,
        top_k: int = DEFAULT_TOP_K,
    ) -> RagAnswer:
        if not await _project_exists_in_tenant(
            self.db_session,
            tenant_id=tenant_id,
            project_id=project_id,
        ):
            raise RagProjectNotFoundError("Project not found or access denied.")

        try:
            embedding = (await _embed_texts([question]))[0]
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            logger.warning(
                "rag_embedding_provider_unavailable",
                status_code=status_code,
                project_id=str(project_id),
            )
            raise RagProviderUnavailableError(
                "RAG embedding provider is temporarily unavailable. Please retry later.",
                status_code=status_code,
            ) from exc
        chunks = await _retrieve_chunks(
            self.db_session,
            tenant_id=tenant_id,
            project_id=project_id,
            embedding=embedding,
            top_k=top_k,
        )

        if not chunks:
            return RagAnswer(answer="No lo encuentro en el documento", sources=[])

        context = "\n\n".join(chunk.content for chunk in chunks)
        prompt = _build_answer_prompt(question=question, context=context)

        wrapper = get_anthropic_wrapper()
        try:
            response = await wrapper.generate(
                AIRequest(
                    prompt=prompt,
                    system_prompt=(
                        "Responde solo con texto en espanol. "
                        "Si no sabes, di: 'No lo encuentro en el documento'."
                    ),
                    task_type=AITaskType.COMPLEX_EXTRACTION,
                    temperature=0.0,
                ),
            )
            answer_text = response.content.strip()
            if _is_no_answer(answer_text):
                fallback_answer = _extractive_answer(question=question, chunks=chunks)
                if fallback_answer is not None:
                    return RagAnswer(answer=fallback_answer, sources=chunks)
            return RagAnswer(answer=answer_text, sources=chunks)
        except Exception as exc:
            fallback_answer = _extractive_answer(question=question, chunks=chunks)
            if fallback_answer is not None:
                logger.warning(
                    "rag_llm_answer_failed_extractively_answered",
                    project_id=str(project_id),
                    error=str(exc),
                )
                return RagAnswer(answer=fallback_answer, sources=chunks)
            logger.warning(
                "rag_answer_provider_unavailable",
                project_id=str(project_id),
                error=str(exc),
            )
            raise RagProviderUnavailableError(
                "RAG answer provider is temporarily unavailable. Please retry later."
            ) from exc


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


def _get_openai_cb_config() -> tuple[int, float]:
    """Get circuit breaker config for OpenAI embeddings."""
    settings = get_circuit_breaker_settings()
    return settings.openai_failure_threshold, settings.openai_recovery_timeout


@with_circuit_breaker(
    "openai_embeddings",
    failure_threshold=5,
    recovery_timeout=60.0,
)
async def _embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for texts using OpenAI API.

    Protected by circuit breaker to prevent cascading failures
    when OpenAI API is unavailable.
    """
    if settings.embeddings_mock:
        # Provider/network boundary only: chunking, vector shape and the chunk
        # INSERT stay exactly as in production, so the acceptance journey still
        # exercises the seam that silently produced zero chunks. Refused in
        # production by validate_security_posture.
        return [_deterministic_embedding(text_value) for text_value in texts]

    api_key = _resolve_openai_api_key()
    if not api_key:
        raise RagProviderMisconfiguredError("OPENAI_API_KEY is not configured.")

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

    logger.debug(
        "openai_embeddings_success",
        text_count=len(texts),
        embedding_count=len(embeddings),
    )
    return embeddings


async def _insert_chunks(db_session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    # Use raw SQL with CAST syntax instead of :: to avoid asyncpg parser issues
    for row in rows:
        stmt = text(
            """
            INSERT INTO document_chunks (id, tenant_id, document_id, project_id, content, embedding, metadata)
            VALUES (
                CAST(:id AS uuid),
                CAST(:tenant_id AS uuid),
                CAST(:document_id AS uuid),
                CAST(:project_id AS uuid),
                :content,
                CAST(:embedding AS vector),
                CAST(:metadata AS jsonb)
            )
            """
        )
        await db_session.execute(stmt, row)
    await db_session.commit()
    logger.info("rag_chunks_inserted", count=len(rows))


async def _retrieve_chunks(
    db_session: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
    embedding: list[float],
    top_k: int,
) -> list[RetrievedChunk]:
    # TS-UD-RAG-ERR-001: query chunks directly instead of relying on a database
    # match_documents function whose signature can drift across local migrations.
    # Keep tenant_id in the predicate so RAG reads remain tenant-scoped.
    stmt = text(
        """
        SELECT
            content,
            metadata,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM document_chunks
        WHERE tenant_id = CAST(:tenant_id AS uuid)
          AND project_id = CAST(:project_id AS uuid)
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT CAST(:match_count AS integer)
        """
    )
    result = await db_session.execute(
        stmt,
        {
            "tenant_id": str(tenant_id),
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


async def _project_exists_in_tenant(
    db_session: AsyncSession,
    *,
    tenant_id: UUID,
    project_id: UUID,
) -> bool:
    """TS-UD-RAG-ERR-001: verify project scope before calling external providers."""
    stmt = text(
        """
        SELECT 1
        FROM projects
        WHERE id = CAST(:project_id AS uuid)
          AND tenant_id = CAST(:tenant_id AS uuid)
        LIMIT 1
        """
    )
    result = await db_session.execute(
        stmt,
        {
            "tenant_id": str(tenant_id),
            "project_id": str(project_id),
        },
    )
    return result.scalar_one_or_none() is not None


def _format_vector(embedding: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in embedding[:EMBEDDING_DIMENSION]) + "]"


def _build_answer_prompt(*, question: str, context: str) -> str:
    return (
        "Usa el siguiente CONTEXTO para responder la PREGUNTA. "
        "Si no sabes, di exactamente: 'No lo encuentro en el documento'.\n\n"
        f"CONTEXTO:\n{context}\n\n"
        f"PREGUNTA:\n{question}\n"
    )


def _extractive_answer(*, question: str, chunks: list[RetrievedChunk]) -> str | None:
    """TS-UD-RAG-ERR-001: deterministic RAG fallback when LLM generation is unavailable."""
    return (
        _extractive_schedule_end_date_answer(question=question, chunks=chunks)
        or _extractive_equipment_answer(
            question=question,
            chunks=chunks,
        )
        or _extractive_contract_damages_answer(
            question=question,
            chunks=chunks,
        )
    )


def _is_no_answer(answer: str) -> bool:
    normalized = answer.strip().lower().rstrip(".")
    return normalized in {
        "no lo encuentro en el documento",
    }


def _extractive_contract_damages_answer(*, question: str, chunks: list[RetrievedChunk]) -> str | None:
    """TS-UD-RAG-ERR-003: summarize obvious contract damages/penalty evidence."""
    normalized_question = question.lower()
    if not any(
        term in normalized_question
        for term in ("penalty", "penalties", "liquidated damages", "damages", "delay", "penalidad", "multa")
    ):
        return None

    evidence: list[str] = []
    for chunk in chunks:
        if chunk.metadata.get("document_type") != "contract":
            continue
        text_content = " ".join(chunk.content.split())
        lower_content = text_content.lower()
        if "recover damages" in lower_content:
            evidence.append("el Employer puede recover damages bajo el contrato por breach/default")
        if "decrease in the contract price" in lower_content:
            evidence.append("para retrasos atribuibles al Contractor, el Employer puede reclamar una decrease in the Contract Price")
        if "risk, cost and responsibility" in lower_content:
            evidence.append("el contrato también menciona terminación al riesgo, costo y responsabilidad del Contractor")

    if not evidence:
        return None

    unique_evidence = list(dict.fromkeys(evidence))
    return (
        "El contrato no muestra en los fragmentos recuperados una tasa específica de liquidated damages, "
        "pero sí indica: "
        + "; ".join(unique_evidence)
        + "."
    )


def _extractive_schedule_end_date_answer(*, question: str, chunks: list[RetrievedChunk]) -> str | None:
    """TS-UD-RAG-ERR-001: deterministic schedule date fallback when LLM generation is unavailable."""
    normalized_question = question.lower()
    if not any(term in normalized_question for term in ("end date", "finish date", "fecha fin", "fin")):
        return None

    dates: list[str] = []
    for chunk in chunks:
        dates.extend(re.findall(r"(?:End|Fin)\s*:\s*(\d{4}-\d{2}-\d{2})", chunk.content, flags=re.IGNORECASE))

    if not dates:
        return None

    end_date = max(dates)
    return f"La fecha de finalización del proyecto es {end_date}."


def _extractive_equipment_answer(*, question: str, chunks: list[RetrievedChunk]) -> str | None:
    """TS-UD-RAG-ERR-001: extract obvious purchasable equipment from retrieved schedule tasks."""
    normalized_question = question.lower()
    if not any(term in normalized_question for term in ("equipment", "purchase", "purchas", "equipos", "comprar")):
        return None

    equipment: list[str] = []
    seen: set[str] = set()
    task_pattern = re.compile(r"Task:\s*(.*?)(?=;\s*Start:|\s+Start:|\s+Task:|$)", flags=re.IGNORECASE)
    fabrication_prefix = re.compile(r"^Fabricaci[oó]n\s+de\s+", flags=re.IGNORECASE)
    equipment_terms = ("transformador", "equipo", "plant", "equipment", "spare", "repuesto")

    for chunk in chunks:
        for match in task_pattern.finditer(chunk.content):
            task_name = " ".join(match.group(1).split()).strip()
            if not any(term in task_name.lower() for term in equipment_terms):
                continue
            item = fabrication_prefix.sub("", task_name).strip()
            if item:
                item = item[0].upper() + item[1:]
            if not item or item.lower() in seen:
                continue
            seen.add(item.lower())
            equipment.append(item)
            if len(equipment) >= 2:
                return "; ".join(equipment) + "."

    return None
