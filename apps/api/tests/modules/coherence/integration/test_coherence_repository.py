"""
Coherence Repository Integration Tests.

Tests for SqlAlchemyCoherenceRepository with database persistence.
Refers to Suite ID: TS-INT-DB-COH-001.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.coherence.adapters.persistence import SqlAlchemyCoherenceRepository
from src.coherence.application.dtos import (
    CalculateCoherenceCommand,
    CoherenceCalculationResult,
)
from src.coherence.application.use_cases import CalculateCoherenceUseCase
from src.coherence.domain.category_weights import CoherenceCategory
from src.core.auth.models import Tenant, SubscriptionPlan
from src.projects.adapters.persistence.models import ProjectORM


@pytest.fixture
async def test_project(db: AsyncSession, test_tenant: Tenant) -> ProjectORM:
    """Create a test project for repository tests."""
    project = ProjectORM(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test Project",
        code="TEST-001",
        description="Test project for coherence repository",
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@pytest.fixture
def coherence_result(test_project: ProjectORM) -> CoherenceCalculationResult:
    """Create a sample coherence result for testing."""
    use_case = CalculateCoherenceUseCase()
    command = CalculateCoherenceCommand(
        project_id=test_project.id,
        contract_price=1000.0,
        bom_items=[{"amount": 1000.0, "budget_line_assigned": True}],
        scope_defined=True,
        schedule_within_contract=True,
        technical_consistent=True,
        legal_compliant=True,
        quality_standard_met=True,
    )
    return use_case.execute(command)


@pytest.mark.asyncio
class TestCoherenceRepository:
    """Refers to Suite ID: TS-INT-DB-COH-001"""

    async def test_001_save_coherence_result(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
        coherence_result: CoherenceCalculationResult,
    ) -> None:
        """Save a coherence result to the database."""
        repository = SqlAlchemyCoherenceRepository(db)

        result_id = await repository.save(coherence_result)

        assert result_id is not None
        assert isinstance(result_id, uuid4().__class__)

    async def test_002_get_by_id_returns_saved_result(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
        coherence_result: CoherenceCalculationResult,
    ) -> None:
        """Get a saved result by ID."""
        repository = SqlAlchemyCoherenceRepository(db)

        result_id = await repository.save(coherence_result)
        retrieved = await repository.get_by_id(result_id)

        assert retrieved is not None
        assert retrieved.project_id == coherence_result.project_id
        assert retrieved.global_score == coherence_result.global_score

    async def test_003_get_by_id_returns_none_for_nonexistent(
        self, db: AsyncSession
    ) -> None:
        """Get by ID returns None for non-existent result."""
        repository = SqlAlchemyCoherenceRepository(db)

        retrieved = await repository.get_by_id(uuid4())

        assert retrieved is None

    async def test_004_get_latest_for_project(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
        coherence_result: CoherenceCalculationResult,
    ) -> None:
        """Get the most recent result for a project."""
        repository = SqlAlchemyCoherenceRepository(db)

        # Save result
        await repository.save(coherence_result)

        # Get latest
        latest = await repository.get_latest_for_project(test_project.id)

        assert latest is not None
        assert latest.project_id == test_project.id
        assert latest.global_score == 100

    async def test_005_get_latest_returns_none_for_nonexistent_project(
        self, db: AsyncSession
    ) -> None:
        """Get latest returns None when project not found."""
        repository = SqlAlchemyCoherenceRepository(db)

        latest = await repository.get_latest_for_project(uuid4())

        assert latest is None

    async def test_006_list_for_project_returns_all_results(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
    ) -> None:
        """List all results for a project with pagination."""
        repository = SqlAlchemyCoherenceRepository(db)
        use_case = CalculateCoherenceUseCase()

        # Create multiple results
        for i in range(3):
            command = CalculateCoherenceCommand(
                project_id=test_project.id,
                scope_defined=(i % 2 == 0),  # Vary scores
            )
            result = use_case.execute(command)
            await repository.save(result)

        # List all
        results, total = await repository.list_for_project(test_project.id, skip=0, limit=10)

        assert total == 3
        assert len(results) == 3
        assert all(r.project_id == test_project.id for r in results)

    async def test_007_list_for_project_pagination(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
    ) -> None:
        """List results respects skip and limit."""
        repository = SqlAlchemyCoherenceRepository(db)
        use_case = CalculateCoherenceUseCase()

        # Create 5 results
        for i in range(5):
            command = CalculateCoherenceCommand(project_id=test_project.id)
            result = use_case.execute(command)
            await repository.save(result)

        # Get page 2 (skip=2, limit=2)
        results, total = await repository.list_for_project(test_project.id, skip=2, limit=2)

        assert total == 5
        assert len(results) == 2

    async def test_008_delete_removes_result(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
        coherence_result: CoherenceCalculationResult,
    ) -> None:
        """Delete removes a coherence result."""
        repository = SqlAlchemyCoherenceRepository(db)

        result_id = await repository.save(coherence_result)
        deleted = await repository.delete(result_id)

        assert deleted is True

        # Verify deleted
        retrieved = await repository.get_by_id(result_id)
        assert retrieved is None

    async def test_009_delete_returns_false_for_nonexistent(
        self, db: AsyncSession
    ) -> None:
        """Delete returns False when result not found."""
        repository = SqlAlchemyCoherenceRepository(db)

        deleted = await repository.delete(uuid4())

        assert deleted is False

    async def test_010_persists_all_category_scores(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
        coherence_result: CoherenceCalculationResult,
    ) -> None:
        """All 6 category scores are persisted correctly."""
        repository = SqlAlchemyCoherenceRepository(db)

        result_id = await repository.save(coherence_result)
        retrieved = await repository.get_by_id(result_id)

        assert retrieved is not None
        assert len(retrieved.category_scores) == 6
        assert all(cat in retrieved.category_scores for cat in CoherenceCategory)

    async def test_011_persists_gaming_detection_data(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
    ) -> None:
        """Gaming detection data is persisted correctly."""
        repository = SqlAlchemyCoherenceRepository(db)
        use_case = CalculateCoherenceUseCase()

        # Create gaming scenario (high score, few docs)
        command = CalculateCoherenceCommand(
            project_id=test_project.id,
            document_count=2,
        )
        result = use_case.execute(command)

        result_id = await repository.save(result)
        retrieved = await repository.get_by_id(result_id)

        assert retrieved is not None
        assert retrieved.is_gaming_detected is True
        assert len(retrieved.gaming_violations) > 0

    async def test_012_persists_alerts(
        self,
        db: AsyncSession,
        test_project: ProjectORM,
    ) -> None:
        """Alerts are persisted correctly."""
        repository = SqlAlchemyCoherenceRepository(db)
        use_case = CalculateCoherenceUseCase()

        # Create scenario with violations
        command = CalculateCoherenceCommand(
            project_id=test_project.id,
            scope_defined=False,
            legal_compliant=False,
        )
        result = use_case.execute(command)

        result_id = await repository.save(result)
        retrieved = await repository.get_by_id(result_id)

        assert retrieved is not None
        assert len(retrieved.alerts) >= 2
        assert all(hasattr(alert, "rule_id") for alert in retrieved.alerts)
