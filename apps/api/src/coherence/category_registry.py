"""
Category Registry Loader and Validation for Coherence Score Engine v1.0.

Location: apps/api/src/coherence/category_registry.py
"""

from __future__ import annotations

import datetime
import os
import re
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


class CanonicalCategory(StrEnum):
    """The six canonical risk / coherence categories."""

    LEGAL = "LEGAL"
    SCOPE = "SCOPE"
    BUDGET = "BUDGET"
    SCHEDULE = "SCHEDULE"
    TECHNICAL = "TECHNICAL"
    QUALITY = "QUALITY"


class VersionInfo(BaseModel):
    """Registry and score engine version details."""

    registry_version: str = Field(..., min_length=1)
    score_version: int = Field(gt=0)
    embedding_model: str = Field(..., min_length=1)
    cutoff_date: datetime.date
    languages: list[str] = Field(..., min_length=1)


class DefaultsWeights(BaseModel):
    """Default weights for different signal channels."""

    embedding: float = Field(..., ge=0.0, le=1.0)
    structural: float = Field(..., ge=0.0, le=1.0)
    lexicon: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_weights_sum(self) -> DefaultsWeights:
        total = self.embedding + self.structural + self.lexicon
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return self


class DefaultsThresholds(BaseModel):
    """Default decision thresholds for routing/escalation."""

    escalate_low: float = Field(..., ge=0.0, le=1.0)
    escalate_high: float = Field(..., ge=0.0, le=1.0)
    insufficient_evidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> DefaultsThresholds:
        if self.escalate_low >= self.escalate_high:
            raise ValueError("escalate_low must be less than escalate_high")
        if self.insufficient_evidence > self.escalate_low:
            raise ValueError("insufficient_evidence must be less than or equal to escalate_low")
        return self


class Defaults(BaseModel):
    """Global configuration defaults."""

    weights: DefaultsWeights
    thresholds: DefaultsThresholds


class StructuralSignals(BaseModel):
    """Section titles and regex patterns used for structural signal extraction."""

    section_titles: dict[str, list[str]]
    patterns: list[str]

    @field_validator("patterns")
    @classmethod
    def validate_regex_patterns(cls, v: list[str]) -> list[str]:
        for pattern in v:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern '{pattern}': {e}")
        return v


class CategoryDefinition(BaseModel):
    """Detailed category specifications including prototypes, keywords, and structural signals."""

    enum: CanonicalCategory
    prototypes: dict[str, list[str]]
    structural_signals: StructuralSignals
    lexicon: dict[str, list[str]]


class SegmentationConfig(BaseModel):
    """Rules governing segmentation strategy during ingestion."""

    monolith_strategy: str = Field(..., min_length=1)
    fallback: str = Field(..., min_length=1)
    markers: dict[str, list[str]]


class IngestionConfig(BaseModel):
    """Global document ingestion and segment mapping configuration."""

    segmentation: SegmentationConfig


class AggregationConfig(BaseModel):
    """Mathematical algorithms/heuristics for scoring aggregation."""

    chunk_combiner: str = Field(..., min_length=1)
    doc_method: str = Field(..., min_length=1)
    top_k: int = Field(..., gt=0)
    doc_relevance: str = Field(..., min_length=1)
    keep_evidence_pointers: bool


class CategoryRegistry(BaseModel):
    """Root representation of the Category Registry configuration."""

    version: VersionInfo
    defaults: Defaults
    categories: dict[CanonicalCategory, CategoryDefinition]
    doc_type_priors: dict[str, dict[CanonicalCategory, float]]
    ingestion: IngestionConfig
    aggregation: AggregationConfig

    @field_validator("categories")
    @classmethod
    def validate_canonical_categories(
        cls, v: dict[CanonicalCategory, CategoryDefinition]
    ) -> dict[CanonicalCategory, CategoryDefinition]:
        required = {CanonicalCategory(category) for category in CanonicalCategory}
        provided = {CanonicalCategory(category) for category in v}
        if required != provided:
            missing = required - provided
            extra = provided - required
            msg = []
            if missing:
                msg.append(f"missing categories: {', '.join(m.value for m in missing)}")
            if extra:
                msg.append(f"unexpected categories: {', '.join(e.value for e in extra)}")
            raise ValueError(
                f"The registry must contain exactly the six canonical categories: {'; '.join(msg)}"
            )
        return v

    @field_validator("doc_type_priors")
    @classmethod
    def validate_priors_range(
        cls, v: dict[str, dict[CanonicalCategory, float]]
    ) -> dict[str, dict[CanonicalCategory, float]]:
        for doc_type, priors in v.items():
            for cat, prior in priors.items():
                if not (0.0 <= prior <= 1.0):
                    raise ValueError(
                        f"Prior value for {doc_type} / {cat.value} must be between 0.0 and 1.0, got {prior}"
                    )
        return v


def load_category_registry(path: str | Path | None = None) -> CategoryRegistry:
    """Loads and validates the Category Registry YAML configuration file.

    Performs robust path fallback checks to guarantee error-free operations across environments.
    """
    if path is not None:
        path = Path(path)
    else:
        # Check environment override
        env_path = os.environ.get("C2PRO_CATEGORY_REGISTRY_PATH")
        if env_path:
            path = Path(env_path)
        else:
            # Fallback path checking sequence
            source_path = Path(__file__)
            candidates = [
                source_path.with_name("category_registry.yaml"),
                Path("docs/coherence_engine/category_registry.yaml"),
            ]
            for parent in source_path.parents:
                candidates.append(parent / "docs" / "coherence_engine" / "category_registry.yaml")
            for candidate in candidates:
                if candidate.exists():
                    path = candidate
                    break

            if path is None:
                raise FileNotFoundError(
                    "Could not locate category_registry.yaml automatically. "
                    "Please configure C2PRO_CATEGORY_REGISTRY_PATH or pass the path explicitly."
                )

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return CategoryRegistry.model_validate(data)
