"""
SqlAlchemy implementation of the IEntityExtractionService port.
Uses use cases from other modules (Stakeholders, Procurement) to extract and persist entities.
Follows the modular monolith principles by going through public use cases.

#852: a SCHEDULE is observed, never written into the canonical WBS. A schedule
activity is not a WBS node and its visible ``wbs`` code is not a canonical WBS
identity; the governed WBS baseline authority is PC-1 / PC-2. The schedule stays
recoverable from its immutable revision (deterministically reparsable) and from
its RAG chunks, so nothing is lost by not materializing it here. This service
therefore has no WBS writer at all.

#860: a BUDGET is observed, never written into the canonical BOM. A budget line is
not a canonical BOM item, and the BOM table is a mixed legacy object (manual
procurement rows, historical budget-derived rows, procurement edits) that budget
ingestion must never create, delete, replace, reset or relink. The budget stays
recoverable from its immutable revision (deterministically reparsable). This
service therefore has no BOM writer at all.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

import structlog

from src.documents.domain.models import Document, DocumentType
from src.documents.ports.entity_extraction_service import IEntityExtractionService

# DTOs and Interfaces from other modules
from src.stakeholders.application.dtos import StakeholderCreateRequest

logger = structlog.get_logger()


class DocumentsEntityExtractionService(IEntityExtractionService):
    def __init__(
        self,
        stakeholder_use_case_factory: Callable[[], Any],
        user_id: UUID,
    ) -> None:
        """
        Initialize the service with factories to avoid circular dependencies
        and provide the user_id for auditing.

        There is deliberately no WBS or BOM use case: schedule ingestion never
        writes the canonical WBS (#852) and budget ingestion never writes the
        canonical BOM (#860).
        """
        self._stakeholder_use_case_factory = stakeholder_use_case_factory
        self._user_id = user_id

    async def extract_entities_from_document(
        self,
        document: Document,
        parsed_payload: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, int]:
        # ``wbs_items`` / ``bom_items`` count canonical writes and are always 0
        # (#852 / #860); ``schedule_activities`` / ``budget_lines`` count what the
        # schedule / budget carries.
        extraction_summary = {
            "stakeholders": 0,
            "wbs_items": 0,
            "bom_items": 0,
            "schedule_activities": 0,
            "budget_lines": 0,
        }

        if document.document_type == DocumentType.CONTRACT:
            summary = await self._extract_stakeholders(document, parsed_payload, tenant_id)
            extraction_summary["stakeholders"] = summary

        if document.document_type == DocumentType.SCHEDULE:
            extraction_summary["schedule_activities"] = _count_schedule_activities(
                parsed_payload
            )

        if document.document_type == DocumentType.BUDGET:
            extraction_summary["budget_lines"] = _count_budget_lines(parsed_payload)

        return extraction_summary

    async def _extract_stakeholders(
        self, document: Document, parsed_payload: dict[str, Any], _tenant_id: UUID
    ) -> int:
        text_blocks = parsed_payload.get("text_blocks", [])
        emails = _extract_emails(text_blocks)
        if not emails:
            return 0

        use_case = self._stakeholder_use_case_factory()
        count = 0

        for email in emails:
            # Note: The use case handles "existing" check if implemented there,
            # or we might get a uniqueness error from DB which is also fine for a background task.
            # For parity with legacy, we keep it simple.
            payload = StakeholderCreateRequest(
                name=_normalize_name_from_email(email),
                email=email,
                company=None,
                role=None,
                department=None,
                phone=None,
                type=None,
                power_score=None,
                interest_score=None,
                feedback_comment=None,
                stakeholder_metadata={"source_document_id": str(document.id)}
            )
            try:
                await use_case.execute(
                    project_id=document.project_id,
                    user_id=self._user_id,
                    payload=payload,
                    tenant_id=_tenant_id
                )
                count += 1
            except Exception as exc:
                # Likely duplicate email or other validation error
                logger.debug("stakeholder_extraction_skipped", email=email, error=str(exc))

        return count


def _extract_emails(text_blocks: list[dict[str, Any]]) -> set[str]:
    emails: set[str] = set()
    for block in text_blocks:
        text = block.get("text", "")
        if not isinstance(text, str):
            continue
        for email in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text):
            emails.add(email.lower())
    return emails


def _count_schedule_activities(parsed_payload: dict[str, Any]) -> int:
    """Named schedule activities observed (#852): counted, never written as WBS."""
    schedule_data = parsed_payload.get("schedule") or []
    return sum(1 for task in schedule_data if isinstance(task, dict) and task.get("task"))


def _count_budget_lines(parsed_payload: dict[str, Any]) -> int:
    """Budget lines observed (#860): counted, never written as canonical BOM.

    A line is a named row with a quantity (flat .xlsx rows, or BC3 chapter units).
    """
    budget_payload = parsed_payload.get("budget")
    rows: list[tuple[object, object]] = []
    if isinstance(budget_payload, list):
        rows = [(item.get("item"), item.get("quantity"))
                for item in budget_payload if isinstance(item, dict)]
    elif isinstance(budget_payload, dict):
        rows = [
            (unit.get("description"), unit.get("quantity"))
            for chapter in budget_payload.get("chapters", [])
            if isinstance(chapter, dict)
            for unit in chapter.get("units", [])
            if isinstance(unit, dict)
        ]
    return sum(1 for name, quantity in rows if name and _parse_decimal(quantity) is not None)


def _parse_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _normalize_name_from_email(email: str) -> str:
    local_part = email.split("@")[0]
    cleaned = re.sub(r"[._-]+", " ", local_part).strip()
    return cleaned.title() if cleaned else email
