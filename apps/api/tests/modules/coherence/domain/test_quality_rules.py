"""
Coherence quality rules tests (TDD - RED phase).

Refers to Suite ID: TS-UD-COH-RUL-006.
"""

from __future__ import annotations

from uuid import uuid4

from src.coherence.domain.quality_rules import (
    CoherenceSeverity,
    CoherenceStatus,
    MaterialItem,
    QualityProjectData,
    QualityRulesEngine,
    QualitySpecification,
)


class TestQualityRulesSuite:
    """Refers to Suite ID: TS-UD-COH-RUL-006"""

    def test_001_r17_specification_without_standard_alert(self) -> None:
        spec = QualitySpecification.model_validate(
            {"id": uuid4(), "title": "Concrete strength", "standard_code": None}
        )
        data = QualityProjectData.model_validate({"specifications": [spec], "materials": []})

        results = QualityRulesEngine().evaluate(data)

        r17 = next(result for result in results if result.rule_id == "R17")
        assert r17.status == CoherenceStatus.FAIL
        assert r17.severity == CoherenceSeverity.HIGH
        assert spec.id in r17.affected_entities

    def test_002_r17_specification_with_standard_pass(self) -> None:
        spec = QualitySpecification.model_validate(
            {"id": uuid4(), "title": "Concrete strength", "standard_code": "ASTM-C150"}
        )
        data = QualityProjectData.model_validate({"specifications": [spec], "materials": []})

        results = QualityRulesEngine().evaluate(data)

        assert all(result.rule_id != "R17" for result in results)

    def test_003_r17_blank_standard_is_alert(self) -> None:
        spec = QualitySpecification.model_validate(
            {"id": uuid4(), "title": "Fireproof coating", "standard_code": "   "}
        )
        data = QualityProjectData.model_validate({"specifications": [spec], "materials": []})

        results = QualityRulesEngine().evaluate(data)

        r17 = next(result for result in results if result.rule_id == "R17")
        assert r17.affected_entities == [spec.id]

    def test_004_r17_metadata_reports_missing_standard_count(self) -> None:
        spec_a = QualitySpecification.model_validate(
            {"id": uuid4(), "title": "Spec A", "standard_code": ""}
        )
        spec_b = QualitySpecification.model_validate(
            {"id": uuid4(), "title": "Spec B", "standard_code": None}
        )
        data = QualityProjectData.model_validate({"specifications": [spec_a, spec_b]})

        results = QualityRulesEngine().evaluate(data)

        r17 = next(result for result in results if result.rule_id == "R17")
        assert r17.metadata["missing_standard_count"] == 2

    def test_005_r18_required_material_without_certification_alert(self) -> None:
        material = MaterialItem.model_validate(
            {"id": uuid4(), "name": "Rebar", "requires_certification": True, "certification_code": None}
        )
        data = QualityProjectData.model_validate({"materials": [material], "specifications": []})

        results = QualityRulesEngine().evaluate(data)

        r18 = next(result for result in results if result.rule_id == "R18")
        assert r18.status == CoherenceStatus.FAIL
        assert r18.severity == CoherenceSeverity.HIGH
        assert material.id in r18.affected_entities

    def test_006_r18_required_material_with_certification_pass(self) -> None:
        material = MaterialItem.model_validate(
            {
                "id": uuid4(),
                "name": "Rebar",
                "requires_certification": True,
                "certification_code": "ISO-9001-STEEL",
            }
        )
        data = QualityProjectData.model_validate({"materials": [material], "specifications": []})

        results = QualityRulesEngine().evaluate(data)

        assert all(result.rule_id != "R18" for result in results)

    def test_007_r18_material_without_requirement_is_ignored(self) -> None:
        material = MaterialItem.model_validate(
            {"id": uuid4(), "name": "Sand", "requires_certification": False, "certification_code": None}
        )
        data = QualityProjectData.model_validate({"materials": [material], "specifications": []})

        results = QualityRulesEngine().evaluate(data)

        assert all(result.rule_id != "R18" for result in results)

    def test_008_r18_metadata_reports_missing_certification_count(self) -> None:
        material_a = MaterialItem.model_validate(
            {"id": uuid4(), "name": "Material A", "requires_certification": True, "certification_code": ""}
        )
        material_b = MaterialItem.model_validate(
            {"id": uuid4(), "name": "Material B", "requires_certification": True, "certification_code": None}
        )
        data = QualityProjectData.model_validate({"materials": [material_a, material_b]})

        results = QualityRulesEngine().evaluate(data)

        r18 = next(result for result in results if result.rule_id == "R18")
        assert r18.metadata["missing_certification_count"] == 2
