"""FROZEN domain contracts for the analysis graph (ADR-013 / TASK-V3-013-01).

Test Suite ID: TS-UD-V3-013-001.

These Pydantic v2 value objects are the canonical validation boundary between
the JSON-compatible Tier-1 LangGraph state and persisted/consumed Tier-2
``DocumentArtifact`` values (ADR-017). The live ``ProjectState`` deliberately
remains JSON-shaped because LangGraph checkpoints serialise it directly; nodes
normalise their emitted payloads before the artifact boundary.

FROZEN CONTRACT — do not add/rename/remove fields without re-freezing and
notifying every implementer. Multi-agent execution (Codex/Gemini/DeepSeek) relies
on this stability; a contract change mid-flight means STOP + re-broadcast.

Field sets are informed by the current extractor output
(``analysis/domain/ai_extraction.py``, ``analysis/domain/prompts.py``) and the six
canonical Coherence categories, so migration churn in TASK-V3-013-04 is minimal.

Conventions:
- ``extra="forbid"`` — unknown keys are a hard error, so extractor drift is caught
  at the boundary (ADR-013 "no silent drift").
- ``frozen=True`` on value objects — immutable, per the project immutability rule.
- Optional fields default to ``None`` so partial extraction still validates; missing
  data is ``None``, never fabricated (INV-1 / ADR-009 honest nulls).
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.analysis.domain.documentation_health import DocumentationHealthSignal

# Schema-visible versioning prevents persisted/API payload consumers from
# accepting contract drift silently.
PAYLOAD_CONTRACT_VERSION: Final[str] = "v1"
_VALUE_OBJECT = ConfigDict(
    extra="forbid",
    frozen=True,
    json_schema_extra={"x-contract-version": PAYLOAD_CONTRACT_VERSION},
)


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CoherenceCategory(str, Enum):
    """The six canonical product categories (+ ``general`` fallback)."""

    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    TIME = "TIME"
    QUALITY = "QUALITY"
    TECHNICAL = "TECHNICAL"
    LEGAL = "LEGAL"
    GENERAL = "general"


class RiskItem(BaseModel):
    """A contract risk (N4). ``severity`` is canonical; ``impact`` is the legacy
    extractor field, normalized into ``severity`` on construction until
    TASK-V3-013-04 updates the extractors to emit ``severity`` directly."""

    model_config = _VALUE_OBJECT

    title: str
    description: str
    category: str = "general"
    severity: Severity | None = None
    impact: Severity | None = None
    likelihood: Severity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    clause_ref: str | None = None
    source: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _severity_from_impact(cls, data: object) -> object:
        if isinstance(data, dict) and data.get("severity") is None and data.get("impact") is not None:
            return {**data, "severity": data["impact"]}
        return data


class WbsActivity(BaseModel):
    """A WBS / schedule activity (N5). Schedule fields stay optional until
    schedule ingestion (ADR-018 v1) makes dates/duration first-class."""

    model_config = _VALUE_OBJECT

    code: str
    name: str
    description: str | None = None
    level: int | None = Field(default=None, ge=0)
    parent_code: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_days: float | None = Field(default=None, ge=0.0)
    percent_complete: float | None = Field(default=None, ge=0.0, le=100.0)


class BudgetItem(BaseModel):
    """A budget / BOM line item (N9)."""

    model_config = _VALUE_OBJECT

    name: str
    amount: float = 0.0
    currency: str = "EUR"
    category: str | None = None
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = None
    cost_code: str | None = None


class Citation(BaseModel):
    """A validated source citation (N15)."""

    model_config = _VALUE_OBJECT

    type: str
    item: str
    quote: str
    found_in_source: bool


class CoherenceFinding(BaseModel):
    """A single coherence signal/finding (N8). ``score`` is on the 0–100 product
    scale; ``None`` means insufficient evidence (never 0 — INV-1)."""

    model_config = _VALUE_OBJECT

    category: str
    message: str
    rule_id: str | None = None
    severity: Severity | None = None
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_ref: str | None = None


class DocumentArtifact(BaseModel):
    """Typed Tier-1 → Tier-2 contract (ADR-017): the analysis output for ONE
    document, consumed by the ProjectGraph and immutable once emitted."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        json_schema_extra={"x-contract-version": PAYLOAD_CONTRACT_VERSION},
    )

    document_id: str
    document_revision_id: str | None = None  # ADR-015 temporal lineage
    doc_type: str
    document_category: str | None = None
    extracted_risks: list[RiskItem] = Field(default_factory=list)
    extracted_wbs: list[WbsActivity] = Field(default_factory=list)
    bom_items: list[BudgetItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    coherence_findings: list[CoherenceFinding] = Field(default_factory=list)
    documentation_health_signal: DocumentationHealthSignal | None = None
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    pii_redaction_count: int = Field(default=0, ge=0)


__all__ = [
    "PAYLOAD_CONTRACT_VERSION",
    "Severity",
    "CoherenceCategory",
    "RiskItem",
    "WbsActivity",
    "BudgetItem",
    "Citation",
    "CoherenceFinding",
    "DocumentArtifact",
]
