"""
Coherence quality rules engine domain models and evaluators.

Refers to Suite ID: TS-UD-COH-RUL-006.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CoherenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARN = "WARN"


class CoherenceSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CoherenceResult(BaseModel):
    rule_id: str
    status: CoherenceStatus
    severity: CoherenceSeverity
    message: str
    affected_entities: list[UUID] = Field(default_factory=list)
    metadata: dict[str, int] = Field(default_factory=dict)


class QualitySpecification(BaseModel):
    id: UUID
    title: str
    standard_code: str | None = None

    @field_validator("standard_code")
    @classmethod
    def normalize_standard_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized if normalized else None


class MaterialItem(BaseModel):
    id: UUID
    name: str
    requires_certification: bool = False
    certification_code: str | None = None

    @field_validator("certification_code")
    @classmethod
    def normalize_certification_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized if normalized else None


class QualityProjectData(BaseModel):
    specifications: list[QualitySpecification] = Field(default_factory=list)
    materials: list[MaterialItem] = Field(default_factory=list)


class RuleR17SpecificationWithoutStandard:
    rule_id = "R17"

    def evaluate(self, data: QualityProjectData) -> CoherenceResult | None:
        missing_standard_spec_ids = [spec.id for spec in data.specifications if spec.standard_code is None]

        if not missing_standard_spec_ids:
            return None

        return CoherenceResult(
            rule_id=self.rule_id,
            status=CoherenceStatus.FAIL,
            severity=CoherenceSeverity.HIGH,
            message="Specification without required quality standard.",
            affected_entities=missing_standard_spec_ids,
            metadata={"missing_standard_count": len(missing_standard_spec_ids)},
        )


class RuleR18MaterialWithoutCertification:
    rule_id = "R18"

    def evaluate(self, data: QualityProjectData) -> CoherenceResult | None:
        missing_cert_material_ids = [
            material.id
            for material in data.materials
            if material.requires_certification and material.certification_code is None
        ]

        if not missing_cert_material_ids:
            return None

        return CoherenceResult(
            rule_id=self.rule_id,
            status=CoherenceStatus.FAIL,
            severity=CoherenceSeverity.HIGH,
            message="Material requires certification but none was provided.",
            affected_entities=missing_cert_material_ids,
            metadata={"missing_certification_count": len(missing_cert_material_ids)},
        )


class QualityRulesEngine:
    """Minimal deterministic quality rules engine for TS-UD-COH-RUL-006."""

    def __init__(self) -> None:
        self._rules = (RuleR17SpecificationWithoutStandard(), RuleR18MaterialWithoutCertification())

    def evaluate(self, data: QualityProjectData) -> list[CoherenceResult]:
        results: list[CoherenceResult] = []
        for rule in self._rules:
            result = rule.evaluate(data)
            if result is not None:
                results.append(result)
        return results
