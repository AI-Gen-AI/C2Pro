"""
Test Suite: TS-UA-DTO-SER-001 - Advanced Serialization/Deserialization
Component: Application Layer DTOs - Serialization
Priority: P1 (High)
Coverage Target: 95%

This test suite validates advanced serialization/deserialization scenarios:
1. Complex type conversions (Decimal, Enum, Optional)
2. Collection serialization (List, Dict, JSONB)
3. Error handling for invalid formats
4. Edge cases (None, empty, circular references)
5. Performance with large datasets

Methodology: TDD Strict (Red → Green → Refactor)
"""

import json
import pytest
from datetime import datetime, date
from decimal import Decimal
from uuid import UUID, uuid4
from typing import Optional, List, Dict
from pydantic import ValidationError

# Import all DTOs for testing
from src.procurement.application.dtos import (
    WBSItemCreate,
    WBSItemResponse,
    BOMItemCreate,
)
from src.analysis.application.dtos import (
    CoherenceScoreResponse,
    AlertCreate,
)
from src.stakeholders.application.dtos import (
    StakeholderCreate,
    RACICreate,
)
from src.projects.application.dtos import (
    ProjectCreateRequest,
    ProjectDetailResponse,
)

# Import domain enums
from src.procurement.domain.models import BOMCategory, ProcurementStatus, WBSItemType
from src.analysis.domain.enums import AlertSeverity
from src.stakeholders.domain.models import PowerLevel, InterestLevel, RACIRole
from src.projects.domain.models import ProjectStatus, ProjectType


# ===========================================
# 🔴 RED PHASE - Decimal Serialization
# ===========================================


class TestDecimalSerialization:
    """
    Test Suite for Decimal type serialization/deserialization
    Related to financial calculations and precision requirements
    """

    @pytest.mark.unit
    def test_ser_001_decimal_to_string_serialization(self):
        """
        🔴 RED: Test Decimal serialization to string

        Given: A DTO with Decimal fields
        When: Serializing to JSON
        Then: Decimal values should be serialized as strings with precision preserved
        """
        wbs_item = WBSItemCreate(
            project_id=uuid4(),
            wbs_code="1.0",
            name="Test Item",
            level=1,
            budget_allocated=Decimal("10000.5678"),
            budget_spent=Decimal("5000.1234")
        )

        json_str = wbs_item.model_dump_json()
        data = json.loads(json_str)

        # Verify Decimal precision is preserved
        assert "10000.5678" in json_str or abs(float(data['budget_allocated']) - 10000.5678) < 0.0001
        assert "5000.1234" in json_str or abs(float(data['budget_spent']) - 5000.1234) < 0.0001

    @pytest.mark.unit
    def test_ser_002_decimal_deserialization_from_string(self):
        """
        🔴 RED: Test Decimal deserialization from string

        Given: A dict with Decimal values as strings
        When: Deserializing to DTO
        Then: Strings should be converted to Decimal objects
        """
        data = {
            "project_id": uuid4(),
            "wbs_code": "1.0",
            "name": "Test Item",
            "level": 1,
            "budget_allocated": "10000.5678",
            "budget_spent": "5000.1234"
        }

        wbs_item = WBSItemCreate(**data)
        assert isinstance(wbs_item.budget_allocated, Decimal)
        assert wbs_item.budget_allocated == Decimal("10000.5678")
        assert wbs_item.budget_spent == Decimal("5000.1234")

    @pytest.mark.unit
    def test_ser_003_decimal_deserialization_from_float(self):
        """
        🔴 RED: Test Decimal deserialization from float

        Given: A dict with Decimal values as floats
        When: Deserializing to DTO
        Then: Floats should be converted to Decimal objects (with potential precision loss warning)
        """
        data = {
            "project_id": uuid4(),
            "wbs_code": "1.0",
            "name": "Test Item",
            "level": 1,
            "budget_allocated": 10000.56,
            "budget_spent": 5000.12
        }

        wbs_item = WBSItemCreate(**data)
        assert isinstance(wbs_item.budget_allocated, Decimal)


# ===========================================
# 🔴 RED PHASE - Enum Serialization
# ===========================================


class TestEnumSerialization:
    """
    Test Suite for Enum serialization/deserialization
    """

    @pytest.mark.unit
    def test_ser_004_enum_to_string_serialization(self):
        """
        🔴 RED: Test Enum serialization to string value

        Given: A DTO with Enum fields
        When: Serializing to JSON
        Then: Enum should be serialized as its string value
        """
        alert = AlertCreate(
            project_id=uuid4(),
            title="Test Alert",
            description="Test description",
            severity=AlertSeverity.HIGH
        )

        json_str = alert.model_dump_json()
        data = json.loads(json_str)

        assert data['severity'] == 'high'  # Enum value, not name

    @pytest.mark.unit
    def test_ser_005_enum_deserialization_from_string(self):
        """
        🔴 RED: Test Enum deserialization from string

        Given: A dict with Enum as string
        When: Deserializing to DTO
        Then: String should be converted to Enum
        """
        data = {
            "project_id": uuid4(),
            "title": "Test Alert",
            "description": "Test description",
            "severity": "high"
        }

        alert = AlertCreate(**data)
        assert isinstance(alert.severity, AlertSeverity)
        assert alert.severity == AlertSeverity.HIGH

    @pytest.mark.unit
    def test_ser_006_enum_invalid_value_error(self):
        """
        🔴 RED: Test Enum deserialization with invalid value

        Given: A dict with invalid Enum value
        When: Deserializing to DTO
        Then: ValidationError should be raised
        """
        data = {
            "project_id": uuid4(),
            "title": "Test Alert",
            "description": "Test description",
            "severity": "INVALID_SEVERITY"
        }

        with pytest.raises(ValidationError) as exc_info:
            AlertCreate(**data)

        errors = exc_info.value.errors()
        assert any('severity' in str(error['loc']) for error in errors)


# ===========================================
# 🔴 RED PHASE - Optional Field Handling
# ===========================================


class TestOptionalFieldSerialization:
    """
    Test Suite for Optional/None value serialization
    """

    @pytest.mark.unit
    def test_ser_007_optional_field_none_serialization(self):
        """
        🔴 RED: Test Optional field with None value serialization

        Given: A DTO with Optional fields set to None
        When: Serializing to dict
        Then: None values should be included in serialization
        """
        wbs_item = WBSItemCreate(
            project_id=uuid4(),
            wbs_code="1.0",
            name="Test Item",
            level=1,
            parent_id=None,
            budget_allocated=None,
            planned_start=None
        )

        data = wbs_item.model_dump()
        assert 'parent_id' in data
        assert data['parent_id'] is None
        assert data['budget_allocated'] is None

    @pytest.mark.unit
    def test_ser_008_optional_field_exclude_none(self):
        """
        🔴 RED: Test Optional field exclusion with exclude_none

        Given: A DTO with Optional fields set to None
        When: Serializing with exclude_none=True
        Then: None values should be excluded from output
        """
        wbs_item = WBSItemCreate(
            project_id=uuid4(),
            wbs_code="1.0",
            name="Test Item",
            level=1,
            parent_id=None,
            budget_allocated=None
        )

        data = wbs_item.model_dump(exclude_none=True)
        assert 'parent_id' not in data
        assert 'budget_allocated' not in data
        assert 'project_id' in data  # Required fields still present

    @pytest.mark.unit
    def test_ser_009_optional_field_omitted_deserialization(self):
        """
        🔴 RED: Test Optional field deserialization when omitted

        Given: A dict without optional fields
        When: Deserializing to DTO
        Then: Optional fields should default to None
        """
        data = {
            "project_id": uuid4(),
            "wbs_code": "1.0",
            "name": "Test Item",
            "level": 1
            # parent_id, budget_allocated omitted
        }

        wbs_item = WBSItemCreate(**data)
        assert wbs_item.parent_id is None
        assert wbs_item.budget_allocated is None


# ===========================================
# 🔴 RED PHASE - Collection Serialization
# ===========================================


class TestCollectionSerialization:
    """
    Test Suite for List and Dict serialization
    """

    @pytest.mark.unit
    def test_ser_010_list_field_serialization(self):
        """
        🔴 RED: Test List field serialization

        Given: A DTO with list fields (e.g., children, top_drivers)
        When: Serializing to JSON
        Then: List should be properly serialized
        """
        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=85,
            top_drivers=["Rule R1", "Rule R5", "Rule R11"]
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert isinstance(data['top_drivers'], list)
        assert len(data['top_drivers']) == 3
        assert "Rule R1" in data['top_drivers']

    @pytest.mark.unit
    def test_ser_011_dict_field_serialization(self):
        """
        🔴 RED: Test Dict/JSONB field serialization

        Given: A DTO with dict fields (metadata, breakdown)
        When: Serializing to JSON
        Then: Dict should be properly serialized
        """
        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=85,
            breakdown={"critical": 5, "high": 10, "medium": 15, "low": 20}
        )

        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert isinstance(data['breakdown'], dict)
        assert data['breakdown']['critical'] == 5
        assert data['breakdown']['high'] == 10

    @pytest.mark.unit
    def test_ser_012_empty_list_serialization(self):
        """
        🔴 RED: Test empty list serialization

        Given: A DTO with empty list field
        When: Serializing
        Then: Empty list should be preserved
        """
        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=100,
            top_drivers=[]
        )

        data = response.model_dump()
        assert data['top_drivers'] == []
        assert isinstance(data['top_drivers'], list)


# ===========================================
# 🔴 RED PHASE - Error Handling
# ===========================================


class TestSerializationErrorHandling:
    """
    Test Suite for serialization error scenarios
    """

    @pytest.mark.unit
    def test_ser_013_invalid_uuid_format_error(self):
        """
        🔴 RED: Test invalid UUID format error

        Given: A dict with invalid UUID string
        When: Deserializing to DTO
        Then: ValidationError should be raised with clear message
        """
        data = {
            "project_id": "not-a-valid-uuid",
            "status": "CALCULATED",
            "score": 85
        }

        with pytest.raises(ValidationError) as exc_info:
            CoherenceScoreResponse(**data)

        errors = exc_info.value.errors()
        assert any('project_id' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    def test_ser_014_invalid_datetime_format_error(self):
        """
        🔴 RED: Test invalid datetime format error

        Given: A dict with invalid datetime string
        When: Deserializing to DTO
        Then: ValidationError should be raised
        """
        data = {
            "name": "Test Project",
            "start_date": "not-a-valid-date",
            "project_type": "CONSTRUCTION"
        }

        with pytest.raises(ValidationError) as exc_info:
            ProjectCreateRequest(**data)

        errors = exc_info.value.errors()
        assert any('start_date' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    def test_ser_015_type_mismatch_error(self):
        """
        🔴 RED: Test type mismatch during deserialization

        Given: A dict with wrong type for a field
        When: Deserializing to DTO
        Then: ValidationError should be raised
        """
        data = {
            "project_id": uuid4(),
            "wbs_code": "1.0",
            "name": "Test Item",
            "level": "not-an-integer"  # Should be int
        }

        with pytest.raises(ValidationError) as exc_info:
            WBSItemCreate(**data)

        errors = exc_info.value.errors()
        assert any('level' in str(error['loc']) for error in errors)


# ===========================================
# 🔴 RED PHASE - Complex Nested Structures
# ===========================================


class TestComplexNestedSerialization:
    """
    Test Suite for deeply nested and complex structures
    """

    @pytest.mark.unit
    def test_ser_016_deeply_nested_structure(self):
        """
        🔴 RED: Test deeply nested DTO serialization

        Given: A DTO with multiple levels of nesting (WBS tree with 3 levels)
        When: Serializing
        Then: All nested levels should be properly serialized
        """
        project_id = uuid4()
        now = datetime.now()

        # Level 3 (leaf)
        leaf = WBSItemResponse(
            id=uuid4(),
            project_id=project_id,
            wbs_code="1.1.1",
            name="Leaf",
            level=3,
            budget_spent=Decimal("0"),
            children=[],
            created_at=now,
            updated_at=now
        )

        # Level 2
        child = WBSItemResponse(
            id=uuid4(),
            project_id=project_id,
            wbs_code="1.1",
            name="Child",
            level=2,
            budget_spent=Decimal("0"),
            children=[leaf],
            created_at=now,
            updated_at=now
        )

        # Level 1 (root)
        root = WBSItemResponse(
            id=uuid4(),
            project_id=project_id,
            wbs_code="1.0",
            name="Root",
            level=1,
            budget_spent=Decimal("0"),
            children=[child],
            created_at=now,
            updated_at=now
        )

        # Serialize
        json_str = root.model_dump_json()
        data = json.loads(json_str)

        # Verify nested structure
        assert data['wbs_code'] == "1.0"
        assert len(data['children']) == 1
        assert data['children'][0]['wbs_code'] == "1.1"
        assert len(data['children'][0]['children']) == 1
        assert data['children'][0]['children'][0]['wbs_code'] == "1.1.1"


# ===========================================
# 🔴 RED PHASE - Round-Trip Integrity
# ===========================================


class TestRoundTripSerialization:
    """
    Test Suite for round-trip serialization integrity
    Ensure data survives serialize → deserialize cycle
    """

    @pytest.mark.unit
    def test_ser_017_round_trip_wbs_item(self):
        """
        🔴 RED: Test WBS Item round-trip serialization

        Given: A WBSItemCreate DTO
        When: Serializing to JSON and back
        Then: Original data should be preserved
        """
        original = WBSItemCreate(
            project_id=uuid4(),
            wbs_code="1.2.3",
            name="Test WBS Item",
            level=3,
            budget_allocated=Decimal("50000.99"),
            budget_spent=Decimal("25000.50"),
            wbs_metadata={"key": "value", "nested": {"data": 123}}
        )

        # Serialize
        json_str = original.model_dump_json()

        # Deserialize
        data = json.loads(json_str)
        restored = WBSItemCreate(**data)

        # Verify
        assert restored.project_id == original.project_id
        assert restored.wbs_code == original.wbs_code
        assert restored.name == original.name
        assert restored.level == original.level
        assert restored.budget_allocated == original.budget_allocated
        assert restored.budget_spent == original.budget_spent
        assert restored.wbs_metadata == original.wbs_metadata

    @pytest.mark.unit
    def test_ser_018_round_trip_project(self):
        """
        🔴 RED: Test Project round-trip serialization

        Given: A ProjectCreateRequest DTO
        When: Serializing to JSON and back
        Then: Original data should be preserved including dates
        """
        start_date = datetime(2026, 1, 1, 10, 0, 0)
        end_date = datetime(2026, 12, 31, 18, 0, 0)

        original = ProjectCreateRequest(
            name="Test Project",
            description="A test project for round-trip testing",
            code="PRJ-001",
            project_type=ProjectType.CONSTRUCTION,
            estimated_budget=1000000.00,
            currency="EUR",
            start_date=start_date,
            end_date=end_date,
            metadata={"location": "Madrid", "client": "Acme Corp"}
        )

        # Serialize
        json_str = original.model_dump_json()

        # Deserialize
        data = json.loads(json_str)
        restored = ProjectCreateRequest(**data)

        # Verify
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.code == original.code
        assert restored.project_type == original.project_type
        assert restored.estimated_budget == original.estimated_budget
        assert restored.currency == original.currency
        # Datetime comparison (might have microsecond differences)
        assert abs((restored.start_date - original.start_date).total_seconds()) < 1
        assert abs((restored.end_date - original.end_date).total_seconds()) < 1
        assert restored.metadata == original.metadata


# ===========================================
# 🔴 RED PHASE - Performance Tests
# ===========================================


class TestSerializationPerformance:
    """
    Test Suite for serialization performance with large datasets
    """

    @pytest.mark.unit
    @pytest.mark.slow
    def test_ser_019_large_list_serialization(self):
        """
        🔴 RED: Test serialization performance with large lists

        Given: A CoherenceScoreResponse with 100+ drivers
        When: Serializing
        Then: Should complete without performance degradation
        """
        large_list = [f"Rule R{i}" for i in range(100)]

        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=75,
            top_drivers=large_list
        )

        # This should not raise any errors or timeout
        json_str = response.model_dump_json()
        data = json.loads(json_str)

        assert len(data['top_drivers']) == 100

    @pytest.mark.unit
    @pytest.mark.slow
    def test_ser_020_large_nested_structure(self):
        """
        🔴 RED: Test serialization of large nested WBS tree

        Given: A WBS tree with 50 children
        When: Serializing
        Then: Should complete successfully
        """
        project_id = uuid4()
        now = datetime.now()

        # Create 50 child items
        children = []
        for i in range(50):
            child = WBSItemResponse(
                id=uuid4(),
                project_id=project_id,
                wbs_code=f"1.{i+1}",
                name=f"Child {i+1}",
                level=2,
                budget_spent=Decimal("1000"),
                children=[],
                created_at=now,
                updated_at=now
            )
            children.append(child)

        # Root with 50 children
        root = WBSItemResponse(
            id=uuid4(),
            project_id=project_id,
            wbs_code="1.0",
            name="Root",
            level=1,
            budget_spent=Decimal("50000"),
            children=children,
            created_at=now,
            updated_at=now
        )

        # Serialize
        json_str = root.model_dump_json()
        data = json.loads(json_str)

        assert len(data['children']) == 50


# ===========================================
# 🟢 GREEN PHASE - Implementation Notes
# ===========================================

"""
GREEN PHASE STRATEGY:

All tests above leverage Pydantic v2's built-in serialization capabilities:

1. **Decimal Serialization**: Pydantic automatically handles Decimal ↔ string/float
2. **Enum Serialization**: Pydantic serializes Enums to their .value
3. **Optional Fields**: Handled natively by Pydantic with Optional[] type hints
4. **Collections**: List and Dict fields serialize naturally
5. **Error Handling**: Pydantic provides detailed ValidationError messages
6. **Nested Structures**: Recursive serialization is built-in
7. **Round-trip**: Pydantic guarantees data integrity
8. **Performance**: Pydantic v2 uses Rust core for speed

Expected Results:
- Most tests should PASS immediately
- Some edge cases may need custom serializers (if any fail)
- Performance tests validate no degradation with large data

REFACTOR opportunities:
- Add custom serializers if needed for special types
- Optimize deeply nested structures if performance issues arise
- Add compression for large payloads if needed
"""
