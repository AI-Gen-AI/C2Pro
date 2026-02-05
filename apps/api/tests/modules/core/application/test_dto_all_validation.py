"""
Cross-module DTO validation tests.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.projects.application.dtos import ProjectCreateRequest
from src.stakeholders.application.dtos import StakeholderCreateRequest, StakeholderUpdateRequest


class TestAllDTOValidation:
    """Refers to Suite ID: TS-UA-DTO-ALL-001"""

    def test_create_stakeholder_request_rejects_whitespace_name(self) -> None:
        with pytest.raises(ValidationError):
            StakeholderCreateRequest(name="   ", project_id=uuid4())

    def test_update_stakeholder_request_rejects_whitespace_name(self) -> None:
        with pytest.raises(ValidationError):
            StakeholderUpdateRequest(name="   ")

    def test_project_create_request_normalizes_currency_uppercase(self) -> None:
        dto = ProjectCreateRequest(name="P1", currency="usd")
        assert dto.currency == "USD"
