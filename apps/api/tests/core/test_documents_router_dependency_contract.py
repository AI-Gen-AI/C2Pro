"""
Router dependency injection contracts for the documents module.
Test Suite ID: TS-ARCH-DOC-DI-001
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.documents.adapters.http.router import (
    get_document_history_use_case,
    get_document_relationship_explanation_service,
    get_document_relationship_explanation_use_case,
    get_document_repository,
)
from src.documents.application.get_document_history_use_case import GetDocumentHistoryUseCase
from src.documents.application.get_document_relationship_explanation_use_case import (
    GetDocumentRelationshipExplanationUseCase,
)
from src.documents.application.services.relationship_explanation_service import (
    EvidenceRelationshipExplanationService,
)

API_ROOT = Path(__file__).resolve().parents[2]


def test_task_inf_049_documents_router_does_not_execute_sql_or_build_services_inline() -> None:
    """TASK-INF-049: documents HTTP handlers must delegate history/explanation work to injected collaborators."""
    source = (API_ROOT / "src" / "documents/adapters/http/router.py").read_text(encoding="utf-8")

    forbidden_snippets = [
        "document_result = await db.execute(",
        "alert_result = await db.execute(",
        "EvidenceRelationshipExplanationService().build(",
    ]

    for snippet in forbidden_snippets:
        assert snippet not in source, (
            f"Documents router still contains inline persistence/service logic for TASK-INF-049: {snippet}"
        )


def test_task_inf_049_documents_dependency_factories_build_expected_types() -> None:
    """TASK-INF-049: documents dependency providers must construct read use cases outside handlers."""
    session = SimpleNamespace()

    repository = get_document_repository(db=session)
    explanation_service = get_document_relationship_explanation_service()

    assert isinstance(explanation_service, EvidenceRelationshipExplanationService)
    assert isinstance(get_document_history_use_case(repo=repository), GetDocumentHistoryUseCase)
    assert isinstance(
        get_document_relationship_explanation_use_case(
            repo=repository,
            explanation_service=explanation_service,
        ),
        GetDocumentRelationshipExplanationUseCase,
    )
