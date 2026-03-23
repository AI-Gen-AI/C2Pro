"""
SqlAlchemy implementation of the IEntityExtractionService port.
Uses use cases from other modules (Stakeholders, Procurement) to extract and persist entities.
Follows the modular monolith principles by going through public use cases.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Any
from uuid import UUID

import structlog
from src.documents.domain.models import Document, DocumentType
from src.documents.ports.entity_extraction_service import IEntityExtractionService

# DTOs and Interfaces from other modules
from src.stakeholders.application.dtos import StakeholderCreateRequest
from src.procurement.application.dtos import WBSItemCreate, BOMItemCreate
from src.procurement.domain.models import WBSItemType

logger = structlog.get_logger()


class DocumentsEntityExtractionService(IEntityExtractionService):
    def __init__(
        self,
        stakeholder_use_case_factory: Callable[[], Any],
        wbs_use_case_factory: Callable[[], Any],
        bom_use_case_factory: Callable[[], Any],
        user_id: UUID,
    ) -> None:
        """
        Initialize the service with factories to avoid circular dependencies
        and provide the user_id for auditing.
        """
        self._stakeholder_use_case_factory = stakeholder_use_case_factory
        self._wbs_use_case_factory = wbs_use_case_factory
        self._bom_use_case_factory = bom_use_case_factory
        self._user_id = user_id

    async def extract_entities_from_document(
        self,
        document: Document,
        parsed_payload: dict,
        tenant_id: UUID,
    ) -> dict[str, int]:
        extraction_summary = {"stakeholders": 0, "wbs_items": 0, "bom_items": 0}

        if document.document_type == DocumentType.CONTRACT:
            summary = await self._extract_stakeholders(document, parsed_payload, tenant_id)
            extraction_summary["stakeholders"] = summary

        if document.document_type == DocumentType.SCHEDULE:
            summary = await self._extract_wbs_items(document, parsed_payload, tenant_id)
            extraction_summary["wbs_items"] = summary

        if document.document_type == DocumentType.BUDGET:
            summary = await self._extract_bom_items(document, parsed_payload, tenant_id)
            extraction_summary["bom_items"] = summary

        return extraction_summary

    async def _extract_stakeholders(
        self, document: Document, parsed_payload: dict, tenant_id: UUID
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
                company=None, # To be enriched by AI if the use case supports it
                stakeholder_metadata={"source_document_id": str(document.id)}
            )
            try:
                await use_case.execute(
                    project_id=document.project_id,
                    user_id=self._user_id,
                    payload=payload
                )
                count += 1
            except Exception as exc:
                # Likely duplicate email or other validation error
                logger.debug("stakeholder_extraction_skipped", email=email, error=str(exc))
        
        return count

    async def _extract_wbs_items(
        self, document: Document, parsed_payload: dict, tenant_id: UUID
    ) -> int:
        schedule_data = parsed_payload.get("schedule", [])
        if not schedule_data:
            return 0

        use_case = self._wbs_use_case_factory()
        count = 0

        for index, task in enumerate(schedule_data, start=1):
            task_name = task.get("task")
            if not task_name:
                continue
            
            wbs_code = f"SCH-{index:03d}"
            payload = WBSItemCreate(
                project_id=document.project_id,
                wbs_code=wbs_code,
                name=str(task_name),
                item_type=WBSItemType.ACTIVITY,
                planned_start=_parse_datetime_value(task.get("start_date")),
                planned_end=_parse_datetime_value(task.get("end_date")),
                wbs_metadata={"source_document_id": str(document.id)}
            )
            try:
                await use_case.execute(payload, tenant_id)
                count += 1
            except Exception as exc:
                logger.debug("wbs_extraction_skipped", code=wbs_code, error=str(exc))

        return count

    async def _extract_bom_items(
        self, document: Document, parsed_payload: dict, tenant_id: UUID
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
                        "price": _parse_decimal(unit.get("price")),
                        "total": _parse_decimal(unit.get("total")),
                        "metadata": {
                            "source_document_id": str(document.id),
                            "chapter_code": chapter.get("code")
                        }
                    })

        for item in items_to_process:
            if not item["name"] or item["quantity"] is None:
                continue
            
            payload = BOMItemCreate(
                project_id=document.project_id,
                item_code=item["code"],
                item_name=item["name"],
                quantity=item["quantity"],
                unit=item["unit"],
                unit_price=item["price"],
                total_price=item["total"],
                currency="EUR",
                bom_metadata=item["metadata"]
            )
            try:
                await use_case.execute(payload, tenant_id)
                count += 1
            except Exception as exc:
                logger.debug("bom_extraction_skipped", name=item["name"], error=str(exc))

        return count


def _extract_emails(text_blocks: list[dict]) -> set[str]:
    emails: set[str] = set()
    for block in text_blocks:
        text = block.get("text", "")
        if not isinstance(text, str):
            continue
        for email in re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", text):
            emails.add(email.lower())
    return emails


def _parse_datetime_value(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


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
