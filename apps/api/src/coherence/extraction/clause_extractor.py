"""
TS-SEC-CLAUSE-PII-001 / TASK-BCK-055: Coherence structured extraction layer.

Extracts the specific fields that deterministic rules need from raw clause text
using a targeted Claude Haiku prompt. Results are cached in
clauses.extracted_entities so subsequent evaluations pay zero LLM cost.

Key design decisions:
- Contract documents contain clauses that span ALL categories (penalty = LEGAL,
  payment schedule = BUDGET+TIME, scope of work = SCOPE, etc.). We therefore
  run a COMBINED extraction prompt covering all six category schemas in one call.
- Non-UUID clause IDs (RAG chunks like "chunk_0_abc12345") skip the DB cache
  gracefully — they still get LLM extraction for the current evaluation.
- Fails open at every step: extraction errors leave clause.data unchanged.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, cast
from uuid import UUID

from src.coherence.models import Clause
from src.core.ai.anthropic_wrapper import AIRequest, get_anthropic_wrapper
from src.core.ai.model_router import AITaskType, ModelTier

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Complete field schema — all six categories merged into one extraction call.
# Contract documents span all categories so a single combined prompt is more
# accurate and cheaper than six separate calls.
# ---------------------------------------------------------------------------

_COMBINED_SCHEMA: dict[str, str] = {
    # ── LEGAL ──
    "last_review_date": "ISO date (YYYY-MM-DD) of last contract review, null if absent",
    "penalty_cap_pct": "penalty cap as float percentage (e.g. 10.0), null if absent",
    "daily_penalty_pct": "daily delay penalty as float percentage, null if absent",
    "has_penalty_cap": "true if a penalty cap is explicitly stated, false if penalty is unlimited, null if unmentioned",
    "notice_period_days": "integer days required for termination/claims notice, null if absent",
    "warranty_months": "warranty/defects-liability period in months as integer, null if absent",
    "payment_term_days": "payment terms in days (e.g. net-30 → 30) as integer, null if absent",
    "insurance_expiry": "ISO date of insurance/bond expiry, null if absent",
    "project_end_date": "ISO date of contract/project end, null if absent",
    # ── TIME ──
    "status": "schedule status: one of delayed/behind/at_risk/critical/suspended/cancelled/on_track/completed — infer from context, null if not determinable",
    "start_date": "ISO date of work start, null if absent",
    "end_date": "ISO date of completion deadline, null if absent",
    "buffer_days": "float buffer/float days explicitly stated, null if absent",
    "milestones": "list of {name: str, date: YYYY-MM-DD} objects, empty list if none",
    "schedule_items": "list of {id: str, start_date: YYYY-MM-DD, end_date: YYYY-MM-DD, predecessor_id: str|null}, empty list if none",
    # ── BUDGET ──
    "current": "current/actual spend as float, null if absent",
    "planned": "planned/budgeted amount as float, null if absent",
    "currency": "currency code (USD/EUR/INR/etc.), null if absent",
    "contingency": "contingency reserve amount as float, null if absent",
    "total_budget": "total budget as float, null if absent",
    "unit_price": "unit price as float for line-item clauses, null if absent",
    "quantity": "quantity as float for line-item clauses, null if absent",
    "line_total": "line total as float, null if absent",
    "budget_items": "list of {description: str, amount: float} line items, empty list if none",
    "contract_total": "overall contract total amount as float, null if absent",
    "retention_pct": "retention percentage as float (e.g. 5.0 for 5%), null if absent",
    "advance_pct": "advance payment percentage as float, null if absent",
    "bank_guarantee": "true if a bank guarantee/performance bond is required, false otherwise",
    # ── TECHNICAL ──
    "lead_time_days": "integer procurement lead-time days, null if absent",
    "required_on_site_date": "ISO date when items must be on site, null if absent",
    "item_name": "name of the technical item or equipment described, null if absent",
    "spec_reference": "specific standard/specification reference (e.g. 'ISO 9001'), null if absent",
    "iso": "ISO standard number referenced, null if absent",
    "astm": "ASTM standard referenced, null if absent",
    "en_standard": "EN standard referenced, null if absent",
    "bom_items": "list of {item_name: str, budget_item_id: str|null}, empty list if none",
    # ── QUALITY ──
    "quality_standards": "list of quality standard strings (ISO/EN/ASTM) referenced, empty list if none",
    "inspection": "true if an inspection clause is present, false otherwise",
    "testing": "true if a testing/commissioning clause is present, false otherwise",
    "inspection_frequency": "inspection frequency description, null if absent",
    "inspection_method": "inspection method description, null if absent",
    # ── SCOPE ──
    "deliverables": "list of concrete deliverable strings extracted from clause text, empty list if none",
}

_SYSTEM_PROMPT = (
    "You are a contract clause data extractor for a construction project management platform. "
    "Extract ALL structured data fields present in the clause text. "
    "Return ONLY a valid JSON object — no markdown fences, no explanation. "
    "Use null for fields not present. Use empty lists [] for absent list fields. "
    "Do not invent data that is not supported by the text."
)


def _build_prompt(clause_text: str) -> str:
    fields_desc = "\n".join(f'  "{k}": {v}' for k, v in _COMBINED_SCHEMA.items())
    return (
        "Extract every applicable field from the following contract clause.\n\n"
        f"CLAUSE TEXT:\n\"\"\"\n{clause_text[:4000]}\n\"\"\"\n\n"
        f"Return a JSON object with these fields (null/[] for absent):\n{{\n{fields_desc}\n}}"
    )


_ALL_REQUIRED_KEYS: frozenset[str] = frozenset(_COMBINED_SCHEMA.keys())


def _already_enriched(clause: Clause) -> bool:
    """True if clause.data already has at least two rule-required fields populated."""
    present = sum(
        1 for k, v in clause.data.items()
        if k in _ALL_REQUIRED_KEYS and v is not None and v != [] and v != ""
    )
    return present >= 2


def _is_valid_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


async def _call_llm(clause_text: str) -> dict[str, Any]:
    """Call Claude Haiku through the PII-safe Anthropic wrapper."""
    if os.getenv("C2PRO_AI_MOCK") == "1":
        # Same mock convention as src.analysis.adapters.ai.anthropic_client.AIService:
        # deterministic, zero-latency, no real Anthropic call.
        return {}
    try:
        response = await get_anthropic_wrapper().generate(
            AIRequest(
                prompt=_build_prompt(clause_text),
                system_prompt=_SYSTEM_PROMPT,
                task_type=AITaskType.CONTRACT_EXTRACTION,
                force_model_tier=ModelTier.FLASH,
                max_tokens=2048,
                use_cache=False,
            )
        )
        raw = response.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        return cast(dict[str, Any], json.loads(raw))
    except Exception as exc:
        logger.warning("clause_extractor: LLM call failed: %s", exc)
        return {}


async def _load_cache(clause_id: str) -> dict[str, Any] | None:
    """Load extracted_entities from clauses table; skip for non-UUID IDs."""
    if not _is_valid_uuid(clause_id):
        return None
    try:
        from sqlalchemy import select

        from src.core.database import _session_factory
        from src.documents.adapters.persistence.models import ClauseORM

        if _session_factory is None:
            return None
        async with _session_factory() as session:
            row = await session.execute(
                select(ClauseORM.extracted_entities).where(
                    ClauseORM.id == UUID(clause_id)
                )
            )
            result = row.scalar_one_or_none()
            if isinstance(result, dict) and any(
                k in _ALL_REQUIRED_KEYS and result[k] is not None and result[k] != [] and result[k] != ""
                for k in result
            ):
                return result
        return None
    except Exception as exc:
        logger.debug("clause_extractor: cache load failed for %s: %s", clause_id, exc)
        return None


async def _write_cache(clause_id: str, data: dict[str, Any]) -> None:
    """Persist extracted fields to clauses.extracted_entities; skip for non-UUID IDs."""
    if not data or not _is_valid_uuid(clause_id):
        return
    try:
        from sqlalchemy import update

        from src.core.database import _session_factory
        from src.documents.adapters.persistence.models import ClauseORM

        if _session_factory is None:
            return
        async with _session_factory() as session:
            await session.execute(
                update(ClauseORM)
                .where(ClauseORM.id == UUID(clause_id))
                .values(extracted_entities=data)
            )
            await session.commit()
    except Exception as exc:
        logger.debug("clause_extractor: cache write failed for %s: %s", clause_id, exc)


async def enrich_clauses(clauses: list[Clause]) -> list[Clause]:
    """
    Enrich each clause's `data` dict with structured fields extracted from text.

    Per-clause strategy:
      1. Already has ≥2 rule-required fields → skip.
      2. UUID clause ID → check DB cache.
      3. Cache miss or non-UUID ID → call Claude Haiku (combined schema).
      4. Write to DB cache (UUID IDs only).
      5. Merge into clause.data without overwriting existing values.

    Fails open: errors leave the clause unchanged.
    """
    result: list[Clause] = []
    for clause in clauses:
        if _already_enriched(clause):
            result.append(clause)
            continue

        cached = await _load_cache(clause.id)
        if cached:
            _merge(clause.data, cached)
            result.append(clause)
            logger.warning("clause_extractor: cache hit %s", clause.id)
            continue

        extracted = await _call_llm(clause.text)
        if extracted:
            _merge(clause.data, extracted)
            await _write_cache(clause.id, extracted)
            populated = [k for k, v in extracted.items() if v is not None and v != [] and v != ""]
            logger.warning(
                "clause_extractor: extracted %d fields for %s: %s",
                len(populated),
                clause.id,
                populated[:8],
            )

        result.append(clause)

    return result


def _merge(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge source into target; never overwrite existing non-null/non-empty values."""
    for key, value in source.items():
        if value is not None and value != [] and value != "" and target.get(key) is None:
            target[key] = value
