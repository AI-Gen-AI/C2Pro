"""
Test Suite: TS-UA-DTO-ALL-001 - All DTOs Validation
Component: Application Layer DTOs
Priority: P0 (Critical)
Coverage Target: 98%

This test suite validates ALL DTOs across the application layer, ensuring:
1. Required fields validation
2. Field format validation
3. Range validation
4. Enum validation
5. Serialization/Deserialization correctness

Methodology: TDD Strict (Red → Green → Refactor)
"""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from pydantic import ValidationError

# Import all DTOs to test
from src.procurement.application.dtos import (
    WBSItemBase,
    WBSItemCreate,
    WBSItemResponse,
    BOMItemBase,
    BOMItemCreate,
    BOMItemResponse,
)
from src.analysis.application.dtos import (
    CoherenceScoreResponse,
    AlertBase,
    AlertCreate,
)
from src.stakeholders.application.dtos import (
    StakeholderBase,
    StakeholderCreate,
    StakeholderResponse,
    RACIBase,
    RACICreate,
    RACIResponse,
    RaciMatrixItem,
)
from src.documents.application.dtos import (
    CreateDocumentDTO,
    DocumentResponse,
)
from src.projects.application.dtos import (
    ProjectCreateRequest,
    ProjectDetailResponse,
)

# Import domain enums
from src.procurement.domain.models import BOMCategory, ProcurementStatus, WBSItemType
from src.analysis.domain.enums import AlertSeverity, AlertStatus
from src.stakeholders.domain.models import PowerLevel, InterestLevel, RACIRole
from src.documents.domain.models import DocumentStatus, DocumentType
from src.projects.domain.models import ProjectStatus, ProjectType


# ===========================================
# 🔴 RED PHASE - WBS Item DTO Tests
# ===========================================


class TestWBSItemDTO:
    """
    Test Suite for WBS Item DTOs
    Tests: UA-DTO-001, UA-DTO-002, UA-DTO-003
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_001_wbs_item_dto_required_fields(self):
        """
        🔴 RED: UA-DTO-001 - Test WBS Item DTO required fields validation

        Given: WBSItemCreate DTO without required fields
        When: Attempting to instantiate the DTO
        Then: ValidationError should be raised
        """
        # Missing required fields: project_id, wbs_code, name, level
        with pytest.raises(ValidationError) as exc_info:
            WBSItemCreate()

        errors = exc_info.value.errors()
        required_fields = ['project_id', 'wbs_code', 'name', 'level']

        # Verify that all required fields are in the error messages
        error_fields = [error['loc'][0] for error in errors]
        for field in required_fields:
            assert field in error_fields, f"Required field '{field}' not validated"

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_002_wbs_item_dto_code_format(self):
        """
        🔴 RED: UA-DTO-002 - Test WBS Item code format validation

        Given: WBSItemCreate with invalid wbs_code format
        When: wbs_code exceeds max_length (50 characters)
        Then: ValidationError should be raised
        """
        invalid_code = "1" * 51  # Exceeds max_length of 50

        with pytest.raises(ValidationError) as exc_info:
            WBSItemCreate(
                project_id=uuid4(),
                wbs_code=invalid_code,
                name="Test WBS Item",
                level=1
            )

        errors = exc_info.value.errors()
        assert any('wbs_code' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_003_wbs_item_dto_level_range(self):
        """
        🔴 RED: UA-DTO-003 - Test WBS Item level range validation

        Given: WBSItemCreate with invalid level (negative value)
        When: level < 0 (violates ge=0 constraint)
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            WBSItemCreate(
                project_id=uuid4(),
                wbs_code="1.1",
                name="Test WBS Item",
                level=-1  # Invalid: must be >= 0
            )

        errors = exc_info.value.errors()
        assert any('level' in str(error['loc']) for error in errors)


# ===========================================
# 🔴 RED PHASE - Coherence Result DTO Tests
# ===========================================


class TestCoherenceResultDTO:
    """
    Test Suite for Coherence Result DTOs
    Tests: UA-DTO-004, UA-DTO-005, UA-DTO-006
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_004_coherence_result_dto_categories(self):
        """
        🔴 RED: UA-DTO-004 - Test Coherence Result DTO categories structure

        Given: CoherenceScoreResponse with breakdown dictionary
        When: Breakdown contains alert counts by severity
        Then: Breakdown should have correct keys (critical, high, medium, low)
        """
        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=85,
            breakdown={"critical": 2, "high": 5, "medium": 10, "low": 3}
        )

        expected_keys = {"critical", "high", "medium", "low"}
        assert set(response.breakdown.keys()) == expected_keys

    @pytest.mark.unit
    def test_ua_dto_005_coherence_result_dto_weights_sum(self):
        """
        🔴 RED: UA-DTO-005 - Test Coherence Result DTO weights sum validation

        Given: CoherenceScoreResponse (note: weights are in domain, not DTO)
        When: Score is calculated
        Then: Score should be valid integer in range

        Note: This test validates that the DTO accepts valid scores.
        Actual weight normalization is in domain layer.
        """
        # Valid score within range
        response = CoherenceScoreResponse(
            project_id=uuid4(),
            status="CALCULATED",
            score=75
        )
        assert 0 <= response.score <= 100

    @pytest.mark.unit
    def test_ua_dto_006_coherence_result_dto_score_range(self):
        """
        🔴 RED: UA-DTO-006 - Test Coherence Result DTO score range validation

        Given: CoherenceScoreResponse with out-of-range score
        When: score > 100 or score < 0
        Then: ValidationError should be raised
        """
        # Test score > 100
        with pytest.raises(ValidationError) as exc_info:
            CoherenceScoreResponse(
                project_id=uuid4(),
                status="CALCULATED",
                score=101  # Invalid: must be <= 100
            )

        # Test score < 0
        with pytest.raises(ValidationError) as exc_info:
            CoherenceScoreResponse(
                project_id=uuid4(),
                status="CALCULATED",
                score=-1  # Invalid: must be >= 0
            )


# ===========================================
# 🔴 RED PHASE - Alert DTO Tests
# ===========================================


class TestAlertDTO:
    """
    Test Suite for Alert DTOs
    Tests: UA-DTO-007, UA-DTO-008
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_007_alert_dto_required_fields(self):
        """
        🔴 RED: UA-DTO-007 - Test Alert DTO required fields validation

        Given: AlertCreate DTO without required fields
        When: Attempting to instantiate without title, description, severity, project_id
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            AlertCreate()

        errors = exc_info.value.errors()
        required_fields = ['title', 'description', 'severity', 'project_id']
        error_fields = [error['loc'][0] for error in errors]

        for field in required_fields:
            assert field in error_fields, f"Required field '{field}' not validated"

    @pytest.mark.unit
    def test_ua_dto_008_alert_dto_severity_enum(self):
        """
        🔴 RED: UA-DTO-008 - Test Alert DTO severity enum validation

        Given: AlertCreate with invalid severity value
        When: severity is not a valid AlertSeverity enum value
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            AlertCreate(
                project_id=uuid4(),
                title="Test Alert",
                description="Test description",
                severity="INVALID_SEVERITY"  # Invalid enum value
            )

        errors = exc_info.value.errors()
        assert any('severity' in str(error['loc']) for error in errors)


# ===========================================
# 🔴 RED PHASE - Clause DTO Tests
# ===========================================


class TestClauseDTO:
    """
    Test Suite for Clause DTOs (from Documents module)
    Tests: UA-DTO-009
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_009_clause_dto_required_fields(self):
        """
        🔴 RED: UA-DTO-009 - Test Clause DTO required fields validation

        Given: CreateDocumentDTO (as proxy for clause creation) without required fields
        When: Attempting to instantiate without project_id, filename, document_type
        Then: TypeError/ValueError should be raised (dataclass validation)
        """
        # CreateDocumentDTO is a frozen dataclass, so missing required fields
        # will raise TypeError at instantiation
        with pytest.raises(TypeError):
            CreateDocumentDTO()


# ===========================================
# 🔴 RED PHASE - BOM Item DTO Tests
# ===========================================


class TestBOMItemDTO:
    """
    Test Suite for BOM Item DTOs
    Tests: UA-DTO-010
    """

    @pytest.mark.unit
    @pytest.mark.critical
    def test_ua_dto_010_bom_item_dto_required_fields(self):
        """
        🔴 RED: UA-DTO-010 - Test BOM Item DTO required fields validation

        Given: BOMItemCreate DTO without required fields
        When: Attempting to instantiate without project_id, item_name, quantity
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            BOMItemCreate()

        errors = exc_info.value.errors()
        required_fields = ['project_id', 'item_name', 'quantity']
        error_fields = [error['loc'][0] for error in errors]

        for field in required_fields:
            assert field in error_fields, f"Required field '{field}' not validated"


# ===========================================
# 🔴 RED PHASE - Stakeholder DTO Tests
# ===========================================


class TestStakeholderDTO:
    """
    Test Suite for Stakeholder DTOs
    Tests: UA-DTO-011
    """

    @pytest.mark.unit
    def test_ua_dto_011_stakeholder_dto_required_fields(self):
        """
        🔴 RED: UA-DTO-011 - Test Stakeholder DTO required fields validation

        Given: StakeholderCreate DTO without required fields
        When: Attempting to instantiate without name, project_id
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            StakeholderCreate()

        errors = exc_info.value.errors()
        required_fields = ['name', 'project_id']
        error_fields = [error['loc'][0] for error in errors]

        for field in required_fields:
            assert field in error_fields, f"Required field '{field}' not validated"


# ===========================================
# 🔴 RED PHASE - RACI Matrix DTO Tests
# ===========================================


class TestRACIMatrixDTO:
    """
    Test Suite for RACI Matrix DTOs
    Tests: UA-DTO-012
    """

    @pytest.mark.unit
    def test_ua_dto_012_raci_matrix_dto_validation(self):
        """
        🔴 RED: UA-DTO-012 - Test RACI Matrix DTO validation

        Given: RACICreate DTO with invalid data
        When: Attempting to create RACI assignment with missing required fields
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            RACICreate()

        errors = exc_info.value.errors()
        required_fields = ['stakeholder_id', 'wbs_item_id', 'raci_role', 'project_id']
        error_fields = [error['loc'][0] for error in errors]

        for field in required_fields:
            assert field in error_fields, f"Required field '{field}' not validated"


# ===========================================
# 🔴 RED PHASE - Serialization Tests
# ===========================================


class TestDTOSerialization:
    """
    Test Suite for DTO Serialization/Deserialization
    Tests: UA-DTO-013, UA-DTO-014, UA-DTO-015, UA-DTO-016, UA-DTO-017, UA-DTO-018
    """

    @pytest.mark.unit
    def test_ua_dto_013_serialization_uuid_to_string(self):
        """
        🔴 RED: UA-DTO-013 - Test UUID serialization to string

        Given: A DTO with UUID field
        When: Serializing to dict/JSON
        Then: UUID should be serialized as string
        """
        project_id = uuid4()
        response = CoherenceScoreResponse(
            project_id=project_id,
            status="CALCULATED",
            score=85
        )

        # Pydantic v2 uses model_dump() instead of dict()
        serialized = response.model_dump()
        assert isinstance(serialized['project_id'], UUID)

        # JSON serialization should convert UUID to string
        json_str = response.model_dump_json()
        assert str(project_id) in json_str

    @pytest.mark.unit
    def test_ua_dto_014_serialization_date_iso8601(self):
        """
        🔴 RED: UA-DTO-014 - Test datetime serialization to ISO8601

        Given: A DTO with datetime field
        When: Serializing to JSON
        Then: Datetime should be in ISO8601 format
        """
        now = datetime.now()
        response = DocumentResponse(
            id=uuid4(),
            project_id=uuid4(),
            document_type=DocumentType.CONTRACT,
            filename="test.pdf",
            upload_status=DocumentStatus.UPLOADED,
            created_at=now
        )

        json_str = response.model_dump_json()
        # Check that ISO format is present (contains 'T' separator and timezone/microseconds)
        assert 'T' in json_str

    @pytest.mark.unit
    def test_ua_dto_015_serialization_nested_dto(self):
        """
        🔴 RED: UA-DTO-015 - Test nested DTO serialization

        Given: A DTO with nested DTO field (WBSItemResponse with children)
        When: Serializing to dict
        Then: Nested DTOs should be properly serialized
        """
        parent = WBSItemResponse(
            id=uuid4(),
            project_id=uuid4(),
            wbs_code="1.0",
            name="Parent",
            level=1,
            budget_spent=Decimal("0"),
            children=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        child = WBSItemResponse(
            id=uuid4(),
            project_id=parent.project_id,
            wbs_code="1.1",
            name="Child",
            level=2,
            budget_spent=Decimal("0"),
            children=[],
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        parent_with_children = WBSItemResponse(
            id=parent.id,
            project_id=parent.project_id,
            wbs_code=parent.wbs_code,
            name=parent.name,
            level=parent.level,
            budget_spent=parent.budget_spent,
            children=[child],
            created_at=parent.created_at,
            updated_at=parent.updated_at
        )

        serialized = parent_with_children.model_dump()
        assert len(serialized['children']) == 1
        assert serialized['children'][0]['wbs_code'] == "1.1"

    @pytest.mark.unit
    def test_ua_dto_016_deserialization_string_to_uuid(self):
        """
        🔴 RED: UA-DTO-016 - Test deserialization of string to UUID

        Given: A dict with UUID as string
        When: Deserializing to DTO
        Then: String should be converted to UUID object
        """
        project_id_str = str(uuid4())
        data = {
            "project_id": project_id_str,
            "status": "CALCULATED",
            "score": 85
        }

        response = CoherenceScoreResponse(**data)
        assert isinstance(response.project_id, UUID)
        assert str(response.project_id) == project_id_str

    @pytest.mark.unit
    def test_ua_dto_017_deserialization_date_from_string(self):
        """
        🔴 RED: UA-DTO-017 - Test deserialization of ISO8601 string to datetime

        Given: A dict with datetime as ISO8601 string
        When: Deserializing to DTO
        Then: String should be converted to datetime object
        """
        now = datetime.now()
        iso_string = now.isoformat()

        data = {
            "id": uuid4(),
            "project_id": uuid4(),
            "document_type": "contract",
            "filename": "test.pdf",
            "upload_status": "uploaded",
            "created_at": iso_string
        }

        response = DocumentResponse(**data)
        assert isinstance(response.created_at, datetime)

    @pytest.mark.unit
    def test_ua_dto_018_deserialization_nested_dto(self):
        """
        🔴 RED: UA-DTO-018 - Test deserialization of nested DTOs

        Given: A dict with nested dict structure
        When: Deserializing to DTO with nested DTO field
        Then: Nested dicts should be converted to nested DTO objects
        """
        project_id = uuid4()
        now = datetime.now()

        data = {
            "id": uuid4(),
            "project_id": project_id,
            "wbs_code": "1.0",
            "name": "Parent",
            "level": 1,
            "budget_spent": "0",
            "children": [
                {
                    "id": uuid4(),
                    "project_id": project_id,
                    "wbs_code": "1.1",
                    "name": "Child",
                    "level": 2,
                    "budget_spent": "0",
                    "children": [],
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }
            ],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        response = WBSItemResponse(**data)
        assert len(response.children) == 1
        assert isinstance(response.children[0], WBSItemResponse)
        assert response.children[0].wbs_code == "1.1"


# ===========================================
# Additional Edge Case Tests
# ===========================================


class TestDTOEdgeCases:
    """
    Additional edge case tests for comprehensive coverage
    """

    @pytest.mark.unit
    def test_wbs_item_dto_decimal_budget_validation(self):
        """
        🔴 RED: Test that budget fields accept Decimal values

        Given: WBSItemCreate with Decimal budget values
        When: Valid Decimal values are provided
        Then: DTO should accept them without error
        """
        wbs_item = WBSItemCreate(
            project_id=uuid4(),
            wbs_code="1.0",
            name="Test Item",
            level=1,
            budget_allocated=Decimal("10000.50"),
            budget_spent=Decimal("5000.25")
        )

        assert wbs_item.budget_allocated == Decimal("10000.50")
        assert wbs_item.budget_spent == Decimal("5000.25")

    @pytest.mark.unit
    def test_bom_item_dto_quantity_positive_validation(self):
        """
        🔴 RED: Test that BOM quantity must be positive

        Given: BOMItemCreate with zero or negative quantity
        When: quantity <= 0
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            BOMItemCreate(
                project_id=uuid4(),
                item_name="Test Item",
                quantity=Decimal("0")  # Invalid: must be > 0
            )

        errors = exc_info.value.errors()
        assert any('quantity' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    def test_project_dto_date_validation(self):
        """
        🔴 RED: Test that project end_date must be after start_date

        Given: ProjectCreateRequest with end_date before start_date
        When: end_date <= start_date
        Then: ValidationError should be raised
        """
        start_date = datetime(2026, 1, 1)
        end_date = datetime(2025, 12, 31)  # Before start_date

        with pytest.raises(ValidationError) as exc_info:
            ProjectCreateRequest(
                name="Test Project",
                start_date=start_date,
                end_date=end_date
            )

        errors = exc_info.value.errors()
        assert any('end_date' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    def test_stakeholder_dto_email_validation(self):
        """
        🔴 RED: Test that stakeholder email must be valid format

        Given: StakeholderCreate with invalid email
        When: email doesn't match email pattern
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            StakeholderCreate(
                name="John Doe",
                project_id=uuid4(),
                email="invalid-email"  # Invalid format
            )

        errors = exc_info.value.errors()
        assert any('email' in str(error['loc']) for error in errors)

    @pytest.mark.unit
    def test_stakeholder_dto_name_not_empty(self):
        """
        🔴 RED: Test that stakeholder name cannot be empty or whitespace

        Given: StakeholderCreate with empty/whitespace name
        When: name is empty string or only whitespace
        Then: ValidationError should be raised
        """
        with pytest.raises(ValidationError) as exc_info:
            StakeholderCreate(
                name="   ",  # Only whitespace
                project_id=uuid4()
            )

        errors = exc_info.value.errors()
        assert any('name' in str(error['loc']) for error in errors)


# ===========================================
# 🟢 GREEN PHASE - Implementation Notes
# ===========================================

"""
GREEN PHASE STRATEGY:

All tests above are currently in RED phase as they test existing Pydantic DTOs.
Most tests should already PASS because:

1. Pydantic BaseModel provides automatic validation for:
   - Required fields
   - Type validation
   - Field constraints (ge, le, min_length, max_length)
   - Enum validation

2. Our DTOs already have field validators:
   - WBSItemBase: level with ge=0 constraint
   - BOMItemBase: quantity with gt=Decimal(0) constraint
   - ProjectCreateRequest: end_date validator
   - StakeholderBase: name validator
   - CoherenceScoreResponse: score with ge=0, le=100 constraints

3. Serialization/Deserialization is handled by Pydantic v2:
   - UUID <-> string conversion
   - datetime <-> ISO8601 string conversion
   - Nested model handling

If any tests FAIL, the GREEN phase will involve:
1. Adding missing field validators
2. Adjusting field constraints
3. Adding custom serialization logic if needed

NEXT STEPS:
1. Run pytest to see which tests pass (GREEN) vs fail (RED)
2. For failing tests, implement minimal code to make them pass
3. Refactor with triangulation if needed
"""
