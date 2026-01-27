"""
Legacy entity extraction adapter.

Bridges the new Documents module port to existing legacy models/services.
This is a transitional adapter until stakeholders/procurement ports are ready.
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

import structlog
from sqlalchemy import select

from src.core.database import get_session_with_tenant
from src.services.stakeholder_classifier import StakeholderClassifier, StakeholderInput
from src.stakeholders.adapters.persistence.models import StakeholderORM as Stakeholder
from src.procurement.adapters.persistence.models import BOMItemORM as BOMItem, WBSItemORM as WBSItem, WBSItemType

from src.documents.domain.models import Document, DocumentType
from src.documents.ports.entity_extraction_service import IEntityExtractionService

logger = structlog.get_logger()


class LegacyEntityExtractionService(IEntityExtractionService):
    async def extract_entities_from_document(
        self,
        document: Document,
        parsed_payload: dict,
        tenant_id: UUID,
    ) -> dict[str, int]:
        extraction_summary = {"stakeholders": 0, "wbs_items": 0, "bom_items": 0}

        async with get_session_with_tenant(tenant_id) as tenant_db:
            if document.document_type == DocumentType.CONTRACT:
                text_blocks = parsed_payload.get("text_blocks", [])
                emails = _extract_emails(text_blocks)
                new_stakeholders: list[Stakeholder] = []
                stakeholder_inputs: list[StakeholderInput] = []

                for email in emails:
                    existing = await tenant_db.scalar(
                        select(Stakeholder).where(
                            Stakeholder.project_id == document.project_id,
                            Stakeholder.email == email,
                        )
                    )
                    if existing:
                        continue
                    stakeholder = Stakeholder(
                        project_id=document.project_id,
                        name=_normalize_name_from_email(email),
                        email=email,
                        extracted_from_document_id=document.id,
                        stakeholder_metadata={"source_document_id": str(document.id)},
                    )
                    tenant_db.add(stakeholder)
                    new_stakeholders.append(stakeholder)
                    stakeholder_inputs.append(
                        StakeholderInput(
                            name=stakeholder.name,
                            role=stakeholder.role,
                            company=stakeholder.organization,
                        )
                    )
                    extraction_summary["stakeholders"] += 1

                if new_stakeholders:
                    classifier = StakeholderClassifier(tenant_id=str(tenant_id))
                    try:
                        enriched = await classifier.classify_batch(
                            stakeholder_inputs,
                            contract_type=document.document_type.value,
                        )
                    except Exception as exc:
                        logger.warning("stakeholder_classification_failed", error=str(exc))
                    else:
                        for stakeholder, result in zip(new_stakeholders, enriched):
                            stakeholder.power_level = result.power_level
                            stakeholder.interest_level = result.interest_level
                            stakeholder.quadrant = result.quadrant_db
                            metadata = dict(stakeholder.stakeholder_metadata or {})
                            metadata["classification"] = {
                                "power_score": result.power_score,
                                "interest_score": result.interest_score,
                                "quadrant": result.quadrant.value,
                            }
                            stakeholder.stakeholder_metadata = metadata

            if document.document_type == DocumentType.SCHEDULE:
                for index, task in enumerate(parsed_payload.get("schedule", []), start=1):
                    task_name = task.get("task")
                    if not task_name:
                        continue
                    wbs_code = f"SCH-{index:03d}"
                    existing = await tenant_db.scalar(
                        select(WBSItem).where(
                            WBSItem.project_id == document.project_id,
                            WBSItem.wbs_code == wbs_code,
                        )
                    )
                    if existing:
                        continue
                    wbs_item = WBSItem(
                        project_id=document.project_id,
                        wbs_code=wbs_code,
                        name=str(task_name),
                        description=None,
                        level=1,
                        item_type=WBSItemType.ACTIVITY,
                        planned_start=_parse_datetime_value(task.get("start_date")),
                        planned_end=_parse_datetime_value(task.get("end_date")),
                        wbs_metadata={"source_document_id": str(document.id)},
                    )
                    tenant_db.add(wbs_item)
                    extraction_summary["wbs_items"] += 1

            if document.document_type == DocumentType.BUDGET:
                budget_payload = parsed_payload.get("budget")
                if isinstance(budget_payload, list):
                    for index, item in enumerate(budget_payload, start=1):
                        item_name = item.get("item")
                        quantity = _parse_decimal(item.get("quantity"))
                        if not item_name or quantity is None:
                            continue
                        item_code = f"BUD-{index:04d}"
                        existing = await tenant_db.scalar(
                            select(BOMItem).where(
                                BOMItem.project_id == document.project_id,
                                BOMItem.item_name == item_name,
                                BOMItem.unit == item.get("unit"),
                            )
                        )
                        if existing:
                            continue
                        bom_item = BOMItem(
                            project_id=document.project_id,
                            item_code=item_code,
                            item_name=str(item_name),
                            quantity=quantity,
                            unit=item.get("unit"),
                            unit_price=_parse_decimal(item.get("unit_price")),
                            total_price=_parse_decimal(item.get("total")),
                            currency="EUR",
                            bom_metadata={"source_document_id": str(document.id)},
                        )
                        tenant_db.add(bom_item)
                        extraction_summary["bom_items"] += 1
                elif isinstance(budget_payload, dict):
                    for chapter in budget_payload.get("chapters", []):
                        for unit in chapter.get("units", []):
                            item_name = unit.get("description")
                            quantity = _parse_decimal(unit.get("quantity"))
                            if not item_name or quantity is None:
                                continue
                            item_code = unit.get("code")
                            existing = await tenant_db.scalar(
                                select(BOMItem).where(
                                    BOMItem.project_id == document.project_id,
                                    BOMItem.item_name == item_name,
                                    BOMItem.unit == unit.get("unit"),
                                )
                            )
                            if existing:
                                continue
                            bom_item = BOMItem(
                                project_id=document.project_id,
                                item_code=item_code,
                                item_name=str(item_name),
                                quantity=quantity,
                                unit=unit.get("unit"),
                                unit_price=_parse_decimal(unit.get("price")),
                                total_price=_parse_decimal(unit.get("total")),
                                currency="EUR",
                                bom_metadata={
                                    "source_document_id": str(document.id),
                                    "chapter_code": chapter.get("code"),
                                },
                            )
                            tenant_db.add(bom_item)
                            extraction_summary["bom_items"] += 1

            if any(extraction_summary.values()):
                await tenant_db.commit()
            return extraction_summary


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
