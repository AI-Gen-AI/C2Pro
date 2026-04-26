"""Pydantic schema for the top-level 15-bundle golden corpus.

Mirrors the vocabulary of ``apps/api/src/golden/schemas.py`` (dimensions,
severities, rule-id pattern) but is deliberately self-contained so
``evals/run_evals.py`` can execute in CI without installing the backend.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_SHORT_STRING = 200
MAX_MEDIUM_STRING = 1_000
MAX_LONG_STRING = 20_000

BUNDLE_ID_PATTERN = r"^BUNDLE-\d{3}$"
RULE_ID_PATTERN = r"^[A-Z]{2,10}-\d{1,4}$"
ALERT_RULE_ID_PATTERN = r"^(?:[A-Z]{2,10}-\d{1,4}|[A-Z_]{3,40})$"


class Dimension(str, Enum):
    """The 6 coherence dimensions for EPC contract analysis."""

    Legal = "Legal"
    Quality = "Quality"
    Scope = "Scope"
    Schedule = "Schedule"
    Cost = "Cost"
    Technical = "Technical"


class Difficulty(str, Enum):
    """Difficulty levels for golden bundles."""

    Easy = "Easy"
    Medium = "Medium"
    Hard = "Hard"
    Expert = "Expert"


DocumentKind = Literal[
    "contract",
    "schedule",
    "budget",
    "specifications",
    "drawings",
]

REQUIRED_DOCUMENT_KINDS: frozenset[DocumentKind] = frozenset(
    {"contract", "schedule", "budget"}
)


class BundleDocument(BaseModel):
    """One synthetic document inside a bundle."""

    model_config = ConfigDict(frozen=True)

    kind: DocumentKind = Field(..., description="Document type within the bundle")
    title: str = Field(..., min_length=3, max_length=MAX_SHORT_STRING)
    synthetic_text: str = Field(
        ...,
        min_length=20,
        max_length=MAX_LONG_STRING,
        description="Inline synthetic payload — no external file references",
    )
    language: Literal["es", "en"] = Field(default="es")


class ExpectedIssue(BaseModel):
    """An incoherence the corpus expects the pipeline to detect."""

    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(..., pattern=RULE_ID_PATTERN, max_length=MAX_SHORT_STRING)
    dimension: Dimension
    severity: Literal["high", "medium", "low"]
    description_contains: str = Field(..., min_length=3, max_length=MAX_MEDIUM_STRING)


class ExpectedScoreRange(BaseModel):
    """Expected score assertion for one golden bundle.

    Test Suite ID: TS-UD-COH-CORP-007.
    """

    model_config = ConfigDict(frozen=True)

    min: float | None = Field(default=None, ge=0.0, le=100.0)
    max: float | None = Field(default=None, ge=0.0, le=100.0)
    reasoning: str = Field(..., min_length=3, max_length=MAX_MEDIUM_STRING)

    @model_validator(mode="after")
    def _range_is_ordered_or_null_score(self) -> "ExpectedScoreRange":
        if (self.min is None) != (self.max is None):
            raise ValueError("expected_score_range min and max must both be null or both numeric")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("expected_score_range min must be <= max")
        return self


class ExpectedAlert(BaseModel):
    """Expected alert assertion for one golden bundle.

    Test Suite ID: TS-UD-COH-CORP-007.
    """

    model_config = ConfigDict(frozen=True)

    rule_id: str = Field(..., pattern=ALERT_RULE_ID_PATTERN, max_length=MAX_SHORT_STRING)
    min_count: int = Field(..., ge=1, le=50)
    severity: Literal["critical", "high", "medium", "low"]


class ScoreCheck(str, Enum):
    """Whether a bundle must enforce score assertions."""

    Required = "required"
    Skip = "skip"


class Bundle(BaseModel):
    """A tridimensional audit bundle (Contract + Schedule + Budget)."""

    model_config = ConfigDict(frozen=True)

    bundle_id: str = Field(..., pattern=BUNDLE_ID_PATTERN)
    name: str = Field(..., min_length=5, max_length=MAX_SHORT_STRING)
    dimensions: list[Dimension] = Field(..., min_length=1, max_length=6)
    difficulty: Difficulty
    synthetic: Literal[True] = Field(
        default=True,
        description="Must be true — the corpus never carries real project data",
    )
    documents: list[BundleDocument] = Field(..., min_length=1, max_length=10)
    expected_issues: list[ExpectedIssue] = Field(..., min_length=1, max_length=50)
    expected_score_range: ExpectedScoreRange
    expected_alerts: list[ExpectedAlert] = Field(..., min_length=1, max_length=50)
    score_check: ScoreCheck = ScoreCheck.Required
    metadata: dict[str, Any] | None = Field(default=None)

    @field_validator("dimensions")
    @classmethod
    def _dedup_dimensions(cls, value: list[Dimension]) -> list[Dimension]:
        if len(set(value)) != len(value):
            raise ValueError("dimensions must be unique")
        return value

    @model_validator(mode="after")
    def _require_core_documents(self) -> "Bundle":
        kinds = {doc.kind for doc in self.documents}
        if kinds == {"contract"}:
            return self
        missing = REQUIRED_DOCUMENT_KINDS - kinds
        if missing:
            raise ValueError(
                f"bundle is missing required document kinds: {sorted(missing)}"
            )
        return self

    @model_validator(mode="after")
    def _score_check_has_valid_expectation(self) -> "Bundle":
        if self.score_check == ScoreCheck.Required:
            if self.expected_score_range.min is None or self.expected_score_range.max is None:
                raise ValueError("score_check=required needs numeric expected_score_range")
        if self.score_check == ScoreCheck.Skip and not self.expected_score_range.reasoning:
            raise ValueError("score_check=skip requires reasoning")
        return self

    @model_validator(mode="after")
    def _contract_only_bundles_expect_audit_incomplete(self) -> "Bundle":
        kinds = {doc.kind for doc in self.documents}
        if kinds != {"contract"}:
            return self
        if self.expected_score_range.min is not None or self.expected_score_range.max is not None:
            raise ValueError("contract-only bundles must expect a null score")
        if not any(alert.rule_id == "AUDIT_INCOMPLETE" for alert in self.expected_alerts):
            raise ValueError("contract-only bundles must expect AUDIT_INCOMPLETE")
        return self

    @model_validator(mode="after")
    def _issue_dimensions_subset_of_declared(self) -> "Bundle":
        declared = set(self.dimensions)
        used = {issue.dimension for issue in self.expected_issues}
        stray = used - declared
        if stray:
            raise ValueError(
                "expected_issues reference undeclared dimensions: "
                f"{sorted(d.value for d in stray)}"
            )
        return self


class ManifestEntry(BaseModel):
    """A single row in ``manifest.yaml``."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(..., pattern=BUNDLE_ID_PATTERN)
    dimensions: list[Dimension] = Field(..., min_length=1, max_length=6)
    difficulty: Difficulty
    expected_issue_count: int = Field(..., ge=1, le=50)


class Manifest(BaseModel):
    """Top-level ``manifest.yaml`` schema."""

    model_config = ConfigDict(frozen=True)

    version: int = Field(..., ge=1)
    total_bundles: int = Field(..., ge=1, le=1_000)
    bundles: list[ManifestEntry]

    @model_validator(mode="after")
    def _count_matches(self) -> "Manifest":
        if self.total_bundles != len(self.bundles):
            raise ValueError(
                f"total_bundles ({self.total_bundles}) does not match "
                f"len(bundles) ({len(self.bundles)})"
            )
        ids = [entry.id for entry in self.bundles]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate bundle ids in manifest")
        return self
