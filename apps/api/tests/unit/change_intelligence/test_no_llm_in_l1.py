"""No-LLM guard for ADR-016 L1 structural diff.

TS-UT-CI-NOLLM-001
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.documents.domain.models import Clause, ClauseType


def _clause(code: str, text: str) -> Clause:
    return Clause(
        id=uuid4(),
        project_id=uuid4(),
        tenant_id=uuid4(),
        document_id=uuid4(),
        clause_code=code,
        clause_type=ClauseType.OTHER,
        title=None,
        full_text=text,
    )


def test_l1_modules_do_not_import_llm_clients_and_diff_runs_without_llm() -> None:
    from src.change_intelligence.application.structural_diff import diff_contract_revisions

    module_paths = [
        Path("src/change_intelligence/domain/contracts.py"),
        Path("src/change_intelligence/application/anchor_resolver.py"),
        Path("src/change_intelligence/application/structural_diff.py"),
    ]
    forbidden = ("core.ai", "llm_client", "anthropic")
    for module_path in module_paths:
        source = module_path.read_text(encoding="utf-8")
        assert all(symbol not in source for symbol in forbidden)

    project_id = uuid4()
    tenant_id = uuid4()
    changeset = diff_contract_revisions(
        project_id=project_id,
        tenant_id=tenant_id,
        from_revision_id=uuid4(),
        to_revision_id=uuid4(),
        old_clauses=[_clause("5.2", "Penalty cap is 10 percent.")],
        new_clauses=[_clause("5.2", "Penalty cap is 15 percent.")],
    )

    assert len(changeset.changes) == 1
