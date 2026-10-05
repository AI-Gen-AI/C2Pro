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
from src.procurement.application.dtos import BOMItemCreate
from src.procurement.domain.models import BOMCategory, ProcurementStatus

# DTOs and Interfaces from other modules
from src.stakeholders.application.dtos import StakeholderCreateRequest

logger = structlog.get_logger()


class DocumentsEntityExtractionService(IEntityExtractionService):
    def __init__(
        self,
        stakeholder_use_case_factory: Callable[[], Any],
        bom_use_case_factory: Callable[[], Any],
        user_id: UUID,
    ) -> None:
        """
        Initialize the service with factories to avoid circular dependencies
        and provide the user_id for auditing.

        There is deliberately no WBS use case: schedule ingestion never writes the
        canonical WBS (#852).
        """
        self._stakeholder_use_case_factory = stakeholder_use_case_factory
        self._bom_use_case_factory = bom_use_case_factory
        self._user_id = user_id

    async def extract_entities_from_document(
        self,
        document: Document,
        parsed_payload: dict[str, Any],
        tenant_id: UUID,
    ) -> dict[str, int]:
        # ``wbs_items`` counts canonical WBS writes and is always 0 (#852);
        # ``schedule_activities`` counts the named activities the schedule carries.
        extraction_summary = {
            "stakeholders": 0,
            "wbs_items": 0,
            "bom_items": 0,
            "schedule_activities": 0,
        }

        if document.document_type == DocumentType.CONTRACT:
            summary = await self._extract_stakeholders(document, parsed_payload, tenant_id)
            extraction_summary["stakeholders"] = summary

        if document.document_type == DocumentType.SCHEDULE:
            extraction_summary["schedule_activities"] = _count_schedule_activities(
                parsed_payload
            )

        if document.document_type == DocumentType.BUDGET:
            summary = await self._extract_bom_items(document, parsed_payload, tenant_id)
            extraction_summary["bom_items"] = summary

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

    async def _extract_bom_items(
        self, document: Document, parsed_payload: dict[str, Any], _tenant_id: UUID
    ) -> int:
        budget_payload = parsed_payload.get("budget")
        if not budget_payload:
            return 0

        use_case = self._bom_use_case_factory()
        count = 0

        # Normalize budget payload into a flat list of items
        items_to_process = []
        if isinstance(budget_payload, list):
            for index, item in enumerate(budget_payload, start=1):
                items_to_process.append({
                    "name": item.get("item"),
                    "code": f"BUD-{index:04d}",
                    "quantity": _parse_decimal(item.get("quantity")),
                    "unit": item.get("unit"),
                    "category": item.get("category"),
                    "price": _parse_decimal(item.get("unit_price")),
                    "total": _parse_decimal(item.get("total")),
                    "metadata": {"source_document_id": str(document.id)}
                })
        elif isinstance(budget_payload, dict):
            for chapter in budget_payload.get("chapters", []):
                for unit in chapter.get("units", []):
                    items_to_process.append({
                        "name": unit.get("description"),
                        "code": unit.get("code"),
                        "quantity": _parse_decimal(unit.get("quantity")),
                        "unit": unit.get("unit"),
                        "category": unit.get("category"),
                        "price": _parse_decimal(unit.get("price")),
                        "total": _parse_decimal(unit.get("total")),
                        "metadata": {
                            "source_document_id": str(document.id),
                            "chapter_code": chapter.get("code")
                        }
                    })

        payloads: list[BOMItemCreate] = []
        for item in items_to_process:
            if not item["name"] or item["quantity"] is None:
                continue

            payloads.append(
                BOMItemCreate(
                    project_id=document.project_id,
                    item_code=item["code"],
                    item_name=item["name"],
                    quantity=item["quantity"],
                    unit=item["unit"],
                    unit_price=item["price"],
                    total_price=item["total"],
                    currency="EUR",
                    description=None,
                    category=_to_bom_category(item.get("category")),
                    supplier=None,
                    lead_time_days=None,
                    incoterm=None,
                    procurement_status=ProcurementStatus.PENDING,
                    wbs_item_id=None,
                    contract_clause_id=None,
                    source_document_id=document.id,
                    bom_metadata=item["metadata"],
                )
            )

        if not payloads:
            return 0

        try:
            created = await use_case.replace_for_source_document(
                project_id=document.project_id,
                source_document_id=document.id,
                bom_items=payloads,
                tenant_id=_tenant_id,
            )
            count = len(created)
        except Exception as exc:
            logger.debug("bom_extraction_skipped", document_id=str(document.id), error=str(exc))

        return count


def _to_bom_category(value: object) -> BOMCategory | None:
    """Map a parsed category string (e.g. "material"/"service") to BOMCategory."""
    if isinstance(value, BOMCategory):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return BOMCategory(value.strip().lower())
        except ValueError:
            return None
    return None


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
