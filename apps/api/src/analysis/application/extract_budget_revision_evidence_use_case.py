"""Extract source-backed budget evidence from one immutable spreadsheet revision."""

from __future__ import annotations

import asyncio

from collections.abc import Collection
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.analysis.domain.budget_row_evidence import (
    ApprovedWBSScope,
    BudgetRowEvidence,
    InvalidBudgetRowEvidenceError,
    bind_verified_budget_row,
)
from src.coherence.domain.budget_line_availability import structured_budget_assessment_from_rows
from src.documents.adapters.parsers.excel_file_parser import ExcelFileParser
from src.documents.application.document_source import verify_revision_file_hash
from src.documents.domain.models import Document, DocumentType
from src.temporal.domain.document_revision import DocumentRevision
from src.wbs.adapters.persistence.link_authority import require_linkable_wbs_nodes


class ApprovedScopeService(Protocol):
    async def require(self, *, tenant_id: UUID, project_id: UUID, node_ids: set[UUID]) -> UUID: ...


@dataclass(frozen=True)
class AuthoritativeApprovedScopeService:
    """Adapter over the transaction-scoped current-approved-WBS authority gate."""

    session: AsyncSession

    async def require(self, *, tenant_id: UUID, project_id: UUID, node_ids: set[UUID]) -> UUID:
        authority = await require_linkable_wbs_nodes(
            self.session, tenant_id=tenant_id, project_id=project_id, node_ids=node_ids
        )
        assert authority.baseline_id is not None
        return authority.baseline_id


@dataclass(frozen=True)
class BudgetRevisionEvidenceResult:
    rows: tuple[BudgetRowEvidence, ...]
    assessment_reason: str


@dataclass(frozen=True)
class ExtractBudgetRevisionEvidenceUseCase:
    parser: ExcelFileParser
    approved_scope_service: ApprovedScopeService

    async def execute(
        self,
        *,
        document: Document,
        revision: DocumentRevision,
        source_path: Path,
        existing_row_identities: Collection[tuple[UUID, str]],
    ) -> BudgetRevisionEvidenceResult:
        _require_matching_budget_revision(document, revision)
        await asyncio.to_thread(verify_revision_file_hash, source_path, revision.blob_hash)
        parsed_rows = await self.parser.parse_budget(source_path, include_evidence=True)
        # Idempotent redelivery must not re-authorize links that were safely
        # persisted against an older WBS baseline. Only NEW rows need approval.
        known = set(existing_row_identities)
        new_rows = [
            row
            for row in parsed_rows
            if (revision.revision_id, str(row["source_locator"])) not in known
        ]
        verified_locators = {str(row["source_locator"]) for row in new_rows}
        wbs_by_locator = {
            str(row["source_locator"]): UUID(str(row["wbs_node_id"]))
            for row in new_rows
            if row.get("wbs_node_id") not in (None, "")
        }
        scope = None
        if wbs_by_locator:
            baseline_id = await self.approved_scope_service.require(
                tenant_id=revision.tenant_id,
                project_id=revision.project_id,
                node_ids=set(wbs_by_locator.values()),
            )
            scope = ApprovedWBSScope(
                tenant_id=revision.tenant_id,
                project_id=revision.project_id,
                baseline_id=baseline_id,
                node_ids=frozenset(wbs_by_locator.values()),
            )

        rows: list[BudgetRowEvidence] = []
        for parsed in new_rows:
            locator = str(parsed["source_locator"])
            identity = (revision.revision_id, locator)
            if identity in known:
                continue
            rows.append(
                bind_verified_budget_row(
                    document_revision=revision,
                    actor_tenant_id=document.tenant_id,
                    source_revision_id=revision.revision_id,
                    source_locator=locator,
                    verified_locators=verified_locators,
                    description=_required_text(parsed, "item"),
                    quantity=_required_decimal(parsed, "quantity"),
                    unit=_required_text(parsed, "unit"),
                    unit_price=_required_decimal(parsed, "unit_price"),
                    amount=_required_decimal(parsed, "total"),
                    currency=_required_text(parsed, "currency"),
                    tax_basis=_required_text(parsed, "tax_basis"),
                    approved_wbs_scope=scope,
                    wbs_node_id=wbs_by_locator.get(locator),
                    existing_row_identities=known,
                    numeric_provenance=tuple(
                        (key, str(value))
                        for key, value in parsed["numeric_provenance"].items()
                    ),
                )
            )
            known.add(identity)

        _assessment, reasons = structured_budget_assessment_from_rows(rows)
        return BudgetRevisionEvidenceResult(rows=tuple(rows), assessment_reason=reasons["BUDGET"])


def _require_matching_budget_revision(document: Document, revision: DocumentRevision) -> None:
    if document.document_type is not DocumentType.BUDGET:
        raise InvalidBudgetRowEvidenceError("document is not a budget")
    # Select supported format from the immutable revision, never from mutable
    # current document metadata after a format-changing reupload.
    if Path(revision.blob_key).suffix.lower() != ".xlsx":
        raise InvalidBudgetRowEvidenceError(
            "selected source revision is not a supported XLSX budget"
        )
    if (
        document.id != revision.document_id
        or document.tenant_id != revision.tenant_id
        or document.project_id != revision.project_id
    ):
        raise InvalidBudgetRowEvidenceError("document does not match immutable revision")


def _required_text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if value is None or not str(value).strip():
        raise InvalidBudgetRowEvidenceError(f"parsed budget row is missing {key}")
    return str(value).strip()


def _required_decimal(row: dict[str, object], key: str) -> Decimal:
    value = row.get(key)
    if value is None:
        raise InvalidBudgetRowEvidenceError(f"parsed budget row is missing {key}")
    decimal = Decimal(str(value))
    if not decimal.is_finite():
        raise InvalidBudgetRowEvidenceError(f"parsed budget row has non-finite {key}")
    return decimal


__all__ = [
    "ApprovedScopeService",
    "AuthoritativeApprovedScopeService",
    "BudgetRevisionEvidenceResult",
    "ExtractBudgetRevisionEvidenceUseCase",
]
