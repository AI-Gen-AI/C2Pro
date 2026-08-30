"""
RAG Ingestion Service Interface (Port).
Defines the contract for ingesting document chunks into a RAG system.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from src.core.json_types import JsonDict
from src.documents.domain.models import Document


class RagIngestionOutcome(StrEnum):
    """What actually happened, in terms the caller can act on.

    Ingestion used to return ``None`` whether it embedded a hundred chunks, hit
    an unconfigured provider, or found nothing to embed. Those are different
    facts with different consequences, so they are different values here.
    """

    INGESTED = "ingested"
    """Chunks were embedded and persisted."""

    NOT_REQUIRED = "not_required"
    """The document carried no embeddable free text (e.g. schedule/budget)."""

    PROVIDER_UNAVAILABLE = "provider_unavailable"
    """Transient upstream failure. Retrying may succeed."""

    MISCONFIGURED = "misconfigured"
    """The provider is unusable as configured. Retrying will not help."""


_ATTENTION_OUTCOMES = frozenset(
    {RagIngestionOutcome.PROVIDER_UNAVAILABLE, RagIngestionOutcome.MISCONFIGURED}
)


@dataclass(frozen=True)
class RagIngestionResult:
    """Typed ingestion outcome.

    Deliberately carries no provider error text: upstream messages can embed
    credentials or internal hostnames, and this value travels toward callers
    and, indirectly, users. The raw error stays in the structured log.
    """

    outcome: RagIngestionOutcome
    chunks: int = 0

    @property
    def requires_attention(self) -> bool:
        """True when RAG did not complete for a document that needed it.

        This is the predicate that decides whether a document may be called
        ANALYZED: only a genuine ingestion or a document that never needed one
        can support that claim.
        """
        return self.outcome in _ATTENTION_OUTCOMES


class IRagIngestionService(ABC):
    @abstractmethod
    async def ingest_document_chunks(
        self, document: Document, parsed_payload: JsonDict, tenant_id: UUID
    ) -> RagIngestionResult:
        """
        Ingests parsed document content into the RAG system.
        :param document: The domain Document entity.
        :param parsed_payload: The content parsed by the file parser.
        :param tenant_id: The ID of the current tenant.
        :returns: What happened, in a form the caller can branch on.
        """
        pass
