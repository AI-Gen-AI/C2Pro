"""
C2Pro - Extraction Application Ports

Defines abstract interfaces (ports) for external dependencies.
Following Hexagonal Architecture, these interfaces are implemented by adapters.

Increment I3: Clause Extraction + Normalization
- LLMAdapter: Abstract interface for LLM-based structured data extraction
- ClauseExtractionService: Application service for clause extraction orchestration
"""

import structlog
from abc import ABC, abstractmethod
from typing import Optional, Protocol, Any
from uuid import UUID, uuid5, NAMESPACE_DNS
from datetime import date

# Re-using IngestionChunk from I1
from src.modules.ingestion.domain.entities import IngestionChunk
from src.modules.extraction.domain.entities import ExtractedClause

logger = structlog.get_logger(__name__)


class LangSmithClientProtocol(Protocol):
    """Protocol for LangSmith client interface."""

    def start_span(
        self, name: str, input: Any = None, run_type: str = "tool", **kwargs
    ) -> Any:
        """Start a new span for tracing."""
        ...

    def end_span(self, span: dict[str, Any], outputs: Any = None) -> None:
        """End a span with outputs."""
        ...


class LLMAdapter(ABC):
    """
    Abstract Base Class for LLM interaction, specifically for structured data extraction.

    Refers to I3.2: Integration test - extraction preserves clause IDs and obligation actors.

    This port defines the contract for LLM-based structured extraction,
    enabling the system to use different LLM providers (OpenAI, Anthropic, etc.)
    transparently.

    The adapter pattern allows for:
    - Provider-agnostic business logic
    - Easy testing with mock implementations
    - Future provider additions without changing core logic
    - Consistent structured output across providers
    """

    @abstractmethod
    async def extract_structured_data(
        self, prompt: str, schema: dict[str, Any], context: str
    ) -> dict[str, Any]:
        """
        Interacts with an LLM to extract structured data based on a given prompt and schema.

        Args:
            prompt: The specific instruction for the LLM
            schema: JSON schema for the expected output structure
            context: The text content from which to extract data

        Returns:
            A dictionary matching the provided schema, containing the extracted data

        Example:
            ```python
            adapter = OpenAIAdapter()
            result = await adapter.extract_structured_data(
                prompt="Extract all obligations from the text",
                schema={"type": "object", "properties": {...}},
                context="The Contractor shall complete work by Dec 31."
            )
            ```
        """
        raise NotImplementedError("LLM adapters must implement extract_structured_data()")


class ClauseExtractionService:
    """
    Application service responsible for orchestrating clause extraction from ingestion chunks.

    Refers to I3.2: Integration test - extraction preserves clause IDs and obligation actors.
    Refers to I3.5: Observability hooks (LangSmith) - Capture prompt version and extracted entities.
    Refers to I3.6: Human-in-the-loop checkpoints - Mandatory validation for ambiguous/high-impact clauses.

    This service:
    - Orchestrates LLM-based clause extraction
    - Normalizes extracted data into ExtractedClause entities
    - Flags high-impact + ambiguous clauses for manual review
    - Integrates with LangSmith for observability

    Args:
        llm_adapter: The LLM adapter to use for extraction
        langsmith_client: Optional LangSmith client for observability
        low_confidence_threshold: Threshold below which clauses are flagged (default: 0.5)
    """

    def __init__(
        self,
        llm_adapter: LLMAdapter,
        langsmith_client: Optional[LangSmithClientProtocol] = None,
        low_confidence_threshold: float = 0.5,
    ):
        """
        Initialize the clause extraction service.

        Args:
            llm_adapter: The LLM adapter to use for extraction
            langsmith_client: Optional LangSmith client for observability
            low_confidence_threshold: Confidence threshold for flagging review
        """
        self.llm_adapter = llm_adapter
        self.langsmith_client = langsmith_client
        self.low_confidence_threshold = low_confidence_threshold

        logger.info(
            "clause_extraction_service_initialized",
            low_confidence_threshold=low_confidence_threshold,
        )

    async def extract_clauses(
        self, chunks: list[IngestionChunk]
    ) -> list[ExtractedClause]:
        """
        Extracts and normalizes clauses from a list of ingestion chunks.

        Refers to I3.2: Integration test - extraction preserves clause IDs and obligation actors.
        Refers to I3.4: Expected failure - Missing confidence flags for ambiguous clauses.
        Refers to I3.5: Observability hooks (LangSmith) - Log prompt version and entities.
        Refers to I3.6: Human-in-the-loop - Flag high-impact + ambiguous clauses.

        Workflow:
        1. Start LangSmith span for observability
        2. Process each chunk with LLM adapter
        3. Normalize LLM output to ExtractedClause entities
        4. Generate chunk_id if not present
        5. Flag high-impact + ambiguous clauses for manual review
        6. End LangSmith span with outputs

        Args:
            chunks: List of ingestion chunks to extract clauses from

        Returns:
            List of ExtractedClause entities with complete provenance metadata

        Example:
            ```python
            service = ClauseExtractionService(llm_adapter=OpenAIAdapter())
            clauses = await service.extract_clauses(ingestion_chunks)
            for clause in clauses:
                if clause.metadata.get("requires_manual_validation"):
                    route_to_review_queue(clause)
            ```
        """
        logger.info(
            "clause_extraction_started",
            chunk_count=len(chunks),
        )

        # Step 1: Start LangSmith span for observability
        # Refers to I3.5: Observability hooks
        span = None
        if self.langsmith_client:
            span = self.langsmith_client.start_span(
                name="extract_clauses_run",
                input={
                    "chunk_count": len(chunks),
                    "chunk_content": [c.content for c in chunks],
                    "prompt_version": "v1.0",
                },
                run_type="chain",
            )

        # Step 2: Process each chunk with LLM adapter
        extracted_clauses = []
        for chunk in chunks:
            logger.debug(
                "extracting_clauses_from_chunk",
                doc_id=str(chunk.doc_id),
                version_id=str(chunk.version_id),
                page=chunk.page,
            )

            # Call LLM adapter for structured extraction
            llm_output = await self.llm_adapter.extract_structured_data(
                prompt="Extract all clauses and their attributes from the following text:",
                schema={
                    "type": "object",
                    "properties": {
                        "clauses": {"type": "array"},
                        "prompt_version": {"type": "string"},
                    },
                },
                context=chunk.content,
            )

            # Step 3: Normalize LLM output to ExtractedClause entities
            for item in llm_output.get("clauses", []):
                # Step 4: Generate chunk_id if not present
                # Use deterministic UUID based on doc_id, version_id, and page
                chunk_id = self._generate_chunk_id(
                    chunk.doc_id, chunk.version_id, chunk.page
                )

                # Convert string UUIDs to UUID objects
                if isinstance(item.get("clause_id"), str):
                    item["clause_id"] = UUID(item["clause_id"])

                # Add provenance metadata
                item["document_id"] = chunk.doc_id
                item["version_id"] = chunk.version_id
                item["chunk_id"] = chunk_id

                # Convert ISO format date string to date object if present
                if isinstance(item.get("due_date"), str):
                    try:
                        item["due_date"] = date.fromisoformat(item["due_date"])
                    except ValueError:
                        logger.warning(
                            "invalid_date_format",
                            date_string=item.get("due_date"),
                        )
                        item["due_date"] = None

                # Create ExtractedClause entity with validation
                clause = ExtractedClause(**item)

                # Step 5: Flag high-impact + ambiguous clauses for manual review
                # Refers to I3.6: Human-in-the-loop checkpoints
                if self._requires_manual_validation(clause):
                    clause.metadata["requires_manual_validation"] = True
                    logger.info(
                        "clause_flagged_for_manual_review",
                        clause_id=str(clause.clause_id),
                        confidence=clause.confidence,
                        ambiguity_flag=clause.ambiguity_flag,
                        impact=clause.metadata.get("impact"),
                    )

                extracted_clauses.append(clause)

        logger.info(
            "clause_extraction_complete",
            extracted_count=len(extracted_clauses),
        )

        # Step 6: End LangSmith span with outputs
        if self.langsmith_client and span:
            self.langsmith_client.end_span(
                span,
                outputs={
                    "extracted_clauses": [c.model_dump() for c in extracted_clauses]
                },
            )

        return extracted_clauses

    def _generate_chunk_id(
        self, doc_id: UUID, version_id: UUID, page: int
    ) -> UUID:
        """
        Generate a deterministic chunk_id based on document provenance.

        Uses UUID5 (name-based UUID) to ensure the same chunk always gets
        the same ID, which is important for idempotency and deduplication.

        Args:
            doc_id: Document UUID
            version_id: Version UUID
            page: Page number

        Returns:
            Deterministic chunk UUID
        """
        # Create deterministic namespace from doc_id + version_id + page
        namespace_string = f"{doc_id}:{version_id}:{page}"
        chunk_id = uuid5(NAMESPACE_DNS, namespace_string)

        logger.debug(
            "chunk_id_generated",
            doc_id=str(doc_id),
            version_id=str(version_id),
            page=page,
            chunk_id=str(chunk_id),
        )

        return chunk_id

    def _requires_manual_validation(self, clause: ExtractedClause) -> bool:
        """
        Determine if a clause requires mandatory manual validation.

        Refers to I3.6: Human-in-the-loop checkpoints - Mandatory validation
        for ambiguous/high-impact clauses.

        A clause requires manual validation if:
        - It has high impact AND is ambiguous
        - Impact is determined by metadata["impact"] == "high"
        - Ambiguity is determined by ambiguity_flag == True

        Args:
            clause: The extracted clause to evaluate

        Returns:
            True if the clause requires manual validation
        """
        is_high_impact = clause.metadata.get("impact") == "high"
        is_ambiguous = clause.ambiguity_flag

        # High-impact + ambiguous = requires manual validation
        if is_high_impact and is_ambiguous:
            return True

        # Also flag very low confidence clauses
        if clause.confidence < self.low_confidence_threshold:
            return True

        return False
