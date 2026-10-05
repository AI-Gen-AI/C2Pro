"""#861 -- a machine-extracted stakeholder is an OBSERVATION, never a human approval.

TS-UA-861-STAKEHOLDER-OBSERVATION-001. Contract ingestion finds email addresses
and records each as a stakeholder. Before #861 the record was stamped
``APPROVED`` with ``reviewed_by`` = the document uploader and ``reviewed_at`` =
now -- false provenance: nobody reviewed it. The automated path now records a
``PENDING`` observation with no reviewer provenance, never duplicates, and never
downgrades or overwrites a stakeholder a human already decided on. The explicit
human ``POST /stakeholders/projects/{id}`` create is unchanged.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from src.core.approval import ApprovalStatus
from src.documents.adapters.extraction.documents_entity_extraction_service import (
    DocumentsEntityExtractionService,
)
from src.documents.domain.models import Document, DocumentStatus, DocumentType
from src.stakeholders.application.create_stakeholder_use_case import CreateStakeholderUseCase
from src.stakeholders.application.dtos import StakeholderCreateRequest
from src.stakeholders.application.review_stakeholder_approval_use_case import (
    ReviewStakeholderApprovalUseCase,
)
from src.stakeholders.domain.models import InterestLevel, PowerLevel, Stakeholder

pytestmark = pytest.mark.asyncio


class _MemoryRepository:
    """In-memory stakeholder repository honouring tenant + project scoping."""

    def __init__(self, rows: list[Stakeholder] | None = None) -> None:
        self.rows: list[Stakeholder] = list(rows or [])
        self.added: list[Stakeholder] = []
        self.updated: list[Stakeholder] = []

    async def add(self, stakeholder: Stakeholder, tenant_id: UUID) -> None:
        stakeholder.tenant_id = tenant_id
        self.rows.append(stakeholder)
        self.added.append(stakeholder)

    async def get_by_id(self, stakeholder_id: UUID, tenant_id: UUID) -> Stakeholder | None:
        return next((r for r in self.rows if r.id == stakeholder_id and r.tenant_id == tenant_id),
                    None)

    async def find_by_project_email(
        self, project_id: UUID, tenant_id: UUID, email: str
    ) -> list[Stakeholder]:
        return [r for r in self.rows if r.project_id == project_id and r.tenant_id == tenant_id
                and (r.email or "").strip().lower() == email.strip().lower()]

    async def update(self, stakeholder: Stakeholder, tenant_id: UUID) -> None:
        self.updated.append(stakeholder)

    async def commit(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        return None


def _use_case(repository: _MemoryRepository) -> CreateStakeholderUseCase:
    return CreateStakeholderUseCase(repository=repository,  # type: ignore[arg-type]
                                    document_repository=AsyncMock())


def _payload(email: str, name: str | None = None) -> StakeholderCreateRequest:
    return StakeholderCreateRequest(name=name or email.split("@")[0], email=email)


def _existing(project_id: UUID, tenant_id: UUID, email: str, status: ApprovalStatus,
              reviewer: UUID | None = None, name: str = "Jane Doe") -> Stakeholder:
    now = datetime.now(UTC)
    return Stakeholder(
        id=uuid4(), project_id=project_id, tenant_id=tenant_id, name=name, email=email,
        power_level=PowerLevel.HIGH, interest_level=InterestLevel.HIGH,
        approval_status=status.value, reviewed_by=reviewer,
        reviewed_at=now if reviewer else None,
        review_comment="human decision" if reviewer else None,
        stakeholder_metadata={"note": "human edit"}, created_at=now, updated_at=now,
    )


async def _observe(use_case: CreateStakeholderUseCase, project_id: UUID, tenant_id: UUID,
                   email: str, document_id: UUID | None = None) -> Stakeholder | None:
    return await use_case.record_extracted_observation(
        project_id=project_id,
        payload=_payload(email),
        tenant_id=tenant_id,
        source_document_id=document_id or uuid4(),
    )


# ── 1-6, 15: the automated observation ─────────────────────────────────────


async def test_extracted_stakeholder_is_pending_without_reviewer_provenance() -> None:
    repository = _MemoryRepository()
    project_id, tenant_id, document_id = uuid4(), uuid4(), uuid4()

    created = await _observe(_use_case(repository), project_id, tenant_id,
                             "jane.doe@contractor.com", document_id)

    assert created is not None
    assert created.approval_status == ApprovalStatus.PENDING.value  # 1
    assert created.reviewed_by is None  # 2, 15
    assert created.reviewed_at is None  # 3
    assert created.review_comment is None  # 4
    assert created.stakeholder_metadata["source_document_id"] == str(document_id)  # 5
    assert created.stakeholder_metadata["origin"] == "automated_extraction"
    # 6: the column carries a NO ACTION FK to documents on the legacy/Supabase schema
    # (deleting the contract would then fail), so provenance stays in metadata.
    assert created.extracted_from_document_id is None
    assert created.tenant_id == tenant_id and created.project_id == project_id


async def test_observation_seam_cannot_name_a_reviewer() -> None:
    """15: the automated seam has no user / reviewer / status input at all."""
    parameters = set(inspect.signature(
        CreateStakeholderUseCase.record_extracted_observation).parameters)
    assert parameters == {"self", "project_id", "payload", "tenant_id", "source_document_id"}


# ── 7: the explicit human create is unchanged ────────────────────────────────


async def test_manual_create_keeps_its_human_semantics() -> None:
    repository = _MemoryRepository()
    creator = uuid4()

    created = await _use_case(repository).execute(
        project_id=uuid4(), user_id=creator,
        payload=_payload("pm@owner.com", "Project Manager"), tenant_id=uuid4(),
    )

    assert created.approval_status == ApprovalStatus.APPROVED.value
    assert created.reviewed_by == creator
    assert created.reviewed_at is not None


# ── 8-9: the existing human review path writes the real reviewer ─────────────


@pytest.mark.parametrize("decision", [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED])
async def test_human_review_of_an_observation_records_the_actual_reviewer(
    decision: ApprovalStatus,
) -> None:
    repository = _MemoryRepository()
    project_id, tenant_id, reviewer = uuid4(), uuid4(), uuid4()
    observed = await _observe(_use_case(repository), project_id, tenant_id, "x@y.com")
    assert observed is not None

    reviewed, _ = await ReviewStakeholderApprovalUseCase(
        repository=repository  # type: ignore[arg-type]
    ).execute(tenant_id=tenant_id, stakeholder_id=observed.id, status=decision,
              correction_data=None, feedback_comment="checked", user_id=reviewer)

    assert reviewed.approval_status == decision
    assert reviewed.reviewed_by == reviewer
    assert reviewed.reviewed_at is not None


# ── 10-12, 14: rediscovery never duplicates nor overwrites ────────────────────


async def test_reobserving_the_same_email_creates_no_duplicate() -> None:
    repository = _MemoryRepository()
    use_case = _use_case(repository)
    project_id, tenant_id = uuid4(), uuid4()

    first = await _observe(use_case, project_id, tenant_id, "jane@c.com")
    second = await _observe(use_case, project_id, tenant_id, "JANE@C.COM")

    assert first is not None and second is None
    assert len(repository.rows) == 1


@pytest.mark.parametrize(
    "status",
    [ApprovalStatus.APPROVED, ApprovalStatus.REJECTED, ApprovalStatus.CORRECTED,
     ApprovalStatus.PENDING],
)
async def test_rediscovery_never_touches_a_reviewed_or_pending_record(
    status: ApprovalStatus,
) -> None:
    project_id, tenant_id, reviewer = uuid4(), uuid4(), uuid4()
    human = _existing(project_id, tenant_id, "Jane@C.com", status,
                      reviewer=None if status is ApprovalStatus.PENDING else reviewer)
    before = (human.approval_status, human.reviewed_by, human.reviewed_at,
              human.review_comment, dict(human.stakeholder_metadata), human.name)
    repository = _MemoryRepository([human])

    result = await _observe(_use_case(repository), project_id, tenant_id, "jane@c.com")

    assert result is None
    assert repository.added == [] and repository.updated == []
    assert (human.approval_status, human.reviewed_by, human.reviewed_at,
            human.review_comment, dict(human.stakeholder_metadata), human.name) == before


async def test_ambiguous_email_identity_fails_closed() -> None:
    project_id, tenant_id = uuid4(), uuid4()
    repository = _MemoryRepository([
        _existing(project_id, tenant_id, "dup@c.com", ApprovalStatus.APPROVED, uuid4()),
        _existing(project_id, tenant_id, "DUP@c.com", ApprovalStatus.PENDING),
    ])

    assert await _observe(_use_case(repository), project_id, tenant_id, "dup@c.com") is None
    assert repository.added == []


async def test_generated_name_is_not_identity() -> None:
    """14: same derived name, different email -> a distinct observation."""
    project_id, tenant_id = uuid4(), uuid4()
    repository = _MemoryRepository([
        _existing(project_id, tenant_id, "jane.doe@other.com", ApprovalStatus.APPROVED,
                  uuid4(), name="Jane Doe"),
    ])

    created = await _observe(_use_case(repository), project_id, tenant_id, "jane.doe@c.com")

    assert created is not None and created.approval_status == ApprovalStatus.PENDING.value


async def test_observation_without_an_email_is_not_recorded() -> None:
    repository = _MemoryRepository()
    result = await _use_case(repository).record_extracted_observation(
        project_id=uuid4(), payload=StakeholderCreateRequest(name="No Email", email=None),
        tenant_id=uuid4(), source_document_id=uuid4(),
    )
    assert result is None and repository.added == []


# ── 13: tenant / project isolation ───────────────────────────────────────────


async def test_same_email_in_another_project_or_tenant_does_not_block_or_change() -> None:
    project_id, tenant_id = uuid4(), uuid4()
    other_project = _existing(uuid4(), tenant_id, "jane@c.com", ApprovalStatus.APPROVED, uuid4())
    other_tenant = _existing(project_id, uuid4(), "jane@c.com", ApprovalStatus.REJECTED, uuid4())
    repository = _MemoryRepository([other_project, other_tenant])

    created = await _observe(_use_case(repository), project_id, tenant_id, "jane@c.com")

    assert created is not None and created.approval_status == ApprovalStatus.PENDING.value
    assert other_project.approval_status == ApprovalStatus.APPROVED.value
    assert other_tenant.approval_status == ApprovalStatus.REJECTED.value


# ── the documents extraction service uses only the observation seam ──────────


async def test_contract_extraction_records_observations_not_human_creates() -> None:
    use_case = AsyncMock()
    use_case.record_extracted_observation = AsyncMock(return_value=object())
    uploader = uuid4()
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=lambda: use_case, user_id=uploader,
    )
    document = Document(id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
                        document_type=DocumentType.CONTRACT, filename="c.pdf",
                        upload_status=DocumentStatus.PARSED)

    summary = await service.extract_entities_from_document(
        document=document,
        parsed_payload={"text_blocks": [{"text": "Contact jane@c.com or bob@c.com"}]},
        tenant_id=document.tenant_id,
    )

    assert summary["stakeholders"] == 2
    use_case.execute.assert_not_awaited()
    calls = use_case.record_extracted_observation.await_args_list
    assert {c.kwargs["payload"].email for c in calls} == {"jane@c.com", "bob@c.com"}
    for call in calls:
        assert call.kwargs["source_document_id"] == document.id
        assert call.kwargs["tenant_id"] == document.tenant_id
        assert uploader not in call.kwargs.values()


async def test_rediscovered_emails_are_not_counted_as_new() -> None:
    use_case = AsyncMock()
    use_case.record_extracted_observation = AsyncMock(return_value=None)
    service = DocumentsEntityExtractionService(
        stakeholder_use_case_factory=lambda: use_case, user_id=uuid4(),
    )
    document = Document(id=uuid4(), project_id=uuid4(), tenant_id=uuid4(),
                        document_type=DocumentType.CONTRACT, filename="c.pdf",
                        upload_status=DocumentStatus.PARSED)

    summary = await service.extract_entities_from_document(
        document=document, parsed_payload={"text_blocks": [{"text": "jane@c.com"}]},
        tenant_id=document.tenant_id,
    )

    assert summary["stakeholders"] == 0
