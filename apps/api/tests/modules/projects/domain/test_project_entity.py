"""
Project entity tests (TDD - RED phase).

Refers to Suite ID: TS-UD-PRJ-PRJ-001.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest

from src.projects.domain.models import Project, ProjectStatus, ProjectType


def _project(**overrides):
    now = datetime(2026, 2, 5, 12, 0, 0)
    base = {
        "id": uuid4(),
        "tenant_id": uuid4(),
        "name": "Terminal Upgrade",
        "description": "Airport modernization",
        "code": "PRJ-001",
        "project_type": ProjectType.INFRASTRUCTURE,
        "status": ProjectStatus.DRAFT,
        "estimated_budget": 1500000.0,
        "currency": "USD",
        "start_date": now,
        "end_date": None,
        "coherence_score": None,
        "last_analysis_at": None,
        "created_at": now,
        "updated_at": now,
    }
    base.update(overrides)
    return Project(**base)


class TestProjectEntity:
    """Refers to Suite ID: TS-UD-PRJ-PRJ-001"""

    def test_001_project_creation_all_fields(self) -> None:
        project = _project()
        assert project.name == "Terminal Upgrade"
        assert project.project_type == ProjectType.INFRASTRUCTURE

    def test_002_project_creation_minimum_fields(self) -> None:
        project = _project(description=None, code=None, estimated_budget=None, end_date=None)
        assert project.description is None
        assert project.code is None

    def test_003_project_fails_with_blank_name(self) -> None:
        with pytest.raises(ValueError, match="name cannot be blank"):
            _project(name="   ")

    def test_004_project_fails_with_none_tenant_id(self) -> None:
        with pytest.raises(ValueError, match="tenant_id is required"):
            _project(tenant_id=None)

    def test_005_project_activate_from_draft(self) -> None:
        project = _project(status=ProjectStatus.DRAFT)

        project.activate()

        assert project.status == ProjectStatus.ACTIVE

    def test_006_project_activate_from_completed_rejected(self) -> None:
        project = _project(status=ProjectStatus.COMPLETED)

        with pytest.raises(ValueError, match="cannot activate"):
            project.activate()

    def test_007_project_complete_from_active(self) -> None:
        project = _project(status=ProjectStatus.ACTIVE)

        project.complete()

        assert project.status == ProjectStatus.COMPLETED

    def test_008_project_complete_from_draft_rejected(self) -> None:
        project = _project(status=ProjectStatus.DRAFT)

        with pytest.raises(ValueError, match="cannot complete"):
            project.complete()

    def test_009_project_archive_only_from_completed(self) -> None:
        project = _project(status=ProjectStatus.COMPLETED)

        project.archive()

        assert project.status == ProjectStatus.ARCHIVED

    def test_010_project_negative_budget_rejected(self) -> None:
        with pytest.raises(ValueError, match="estimated_budget must be >= 0"):
            _project(estimated_budget=-1)

    def test_011_project_currency_must_be_three_letters(self) -> None:
        with pytest.raises(ValueError, match="currency must be 3 uppercase letters"):
            _project(currency="usd")

    def test_012_project_ready_for_analysis_requires_contract_document(self) -> None:
        project = _project()
        project.update_document_list(["drawing", "contract"])

        assert project.is_ready_for_analysis() is True
