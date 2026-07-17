"""
Application use case: classify a document into a `DOC_TYPES` code.

Orchestrates `DocumentTypeClassificationService` with a short-circuit when
the caller already knows the document type (idempotent re-runs).

Refers to EPIC-CORE-DECOUPLE / TASK-IMPL-010 Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.analysis.domain.ai_extraction import (
    AIExtractionPort,
    DocumentTypeClassificationService,
)
from src.analysis.domain.prompts import DOC_TYPES


@dataclass(frozen=True)
class ClassifyDocumentCommand:
    text: str
    current_doc_type: str | None = None


@dataclass(frozen=True)
class ClassifyDocumentUseCase:
    ai: AIExtractionPort
    service: DocumentTypeClassificationService = field(
        default_factory=DocumentTypeClassificationService
    )

    async def execute(self, cmd: ClassifyDocumentCommand) -> str:
        if cmd.current_doc_type in DOC_TYPES:
            return cmd.current_doc_type
        return await self.service.classify(text=cmd.text, ai=self.ai)
