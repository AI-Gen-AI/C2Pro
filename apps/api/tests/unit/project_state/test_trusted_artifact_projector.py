"""Trust/revision/tenant isolation before proposing canonical ProjectState.

No SQL, provider calls, source write, HITL decisions or score changes.
"""

from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

import pytest

from src.analysis.domain.contracts import DocumentArtifact, RiskItem
from src.documents.domain.models import Clause as SourceClause
from src.project_state.application.trusted_artifact_projector import (
    TrustedRevisionBundle,
    build_trusted_state_candidate,
)

_TENANT = uuid4()
_PROJECT = uuid4()
_DOC = uuid4()
_REV = uuid4()
_QUOTE = (
    "The Contractor shall pay delay damages equal to 0.5 percent of the "
    "Contract Price for each commenced week of delay, capped at 10 percent."
)
_OTHER = (
    "The Contractor shall indemnify the Employer against third-party bodily "
    "injury arising from the Works, except for exclusions written in this clause."
)


def _source(
    text: str = _QUOTE,
    *,
    document: object = _DOC,
    revision: object = _REV,
    tenant: object = _TENANT,
    project: object = _PROJECT,
    code: str = "8.2",
) -> SourceClause:
    return SourceClause(
        id=uuid4(),
        tenant_id=tenant,
        project_id=project,
        document_id=document,
        revision_id=revision,
        clause_code=code,
        clause_type=None,
        title=None,
        full_text=text,
    )


def _artifact(*, risk_quote: str | None = _QUOTE, status: str = "VERIFIED") -> DocumentArtifact:
    return DocumentArtifact(
        document_id=str(_DOC),
        document_revision_id=str(_REV),
        doc_type="contract",
        extracted_risks=[
            RiskItem(
                title="Delayed completion liabilities",
                description="Delay damages capped at ten percent",
                category="SCHEDULE",
                source_quote=risk_quote,
                source_quote_status=status,
                clause_ref="8.2",
            )
        ],
    )


def _bundle(
    *,
    source: tuple[SourceClause, ...] | None = None,
    trust: str = "trusted",
    lifecycle: str = "active",
    risk_quote: str | None = _QUOTE,
    risk_status: str = "VERIFIED",
) -> TrustedRevisionBundle:
    return TrustedRevisionBundle(
        artifact=_artifact(risk_quote=risk_quote, status=risk_status),
        source_clauses=source if source is not None else (_source(),),
        trust_state=trust,
        lifecycle_status=lifecycle,
    )


def test_only_trusted_revision_clause_and_verbatim_risk_become_canonical() -> None:
    clause = _source()
    bundle = _bundle(source=(clause,))
    one = build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[bundle])
    two = build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[bundle])
    assert one is not None and two is not None
    assert one.state.model_dump(mode="json") == two.state.model_dump(mode="json")
    assert one.state.document_revision_ids == [_REV]
    assert len(one.state.clauses) == len(one.state.risks) == 1
    projected_clause = one.state.clauses[0]
    assert projected_clause.entity_id == clause.id
    assert projected_clause.source_revision_id == _REV
    assert projected_clause.clause_id == "8.2"
    assert projected_clause.evidence[0].tier.value == "weak"
    risk = one.state.risks[0]
    assert risk.source_revision_id == _REV
    assert risk.evidence[0].ref_id == str(clause.id)
    assert risk.evidence[0].tier.value == "weak"
    assert one.diagnostics.source_bound_risks == 1
    assert one.diagnostics.rejected_unverified_risks == 0


@pytest.mark.parametrize(
    ("trust", "lifecycle"),
    [
        ("proposed", "active"),
        ("rejected", "active"),
        ("trusted", "superseded"),
    ],
)
def test_proposed_rejected_or_superseded_artifact_fails_closed(trust: str, lifecycle: str) -> None:
    with pytest.raises(ValueError, match="UNTRUSTED_ARTIFACT"):
        build_trusted_state_candidate(
            project_id=_PROJECT,
            tenant_id=_TENANT,
            bundles=[_bundle(trust=trust, lifecycle=lifecycle)],
        )


@pytest.mark.parametrize(
    "source_change",
    [
        {"tenant": uuid4()},
        {"project": uuid4()},
        {"document": uuid4()},
        {"revision": uuid4()},
    ],
)
def test_wrong_tenant_project_document_or_revision_is_not_projected(source_change) -> None:
    clause = _source(**source_change)
    with pytest.raises(ValueError, match="CROSS_TENANT_OR_DOCUMENT|WRONG_REVISION"):
        build_trusted_state_candidate(
            project_id=_PROJECT, tenant_id=_TENANT, bundles=[_bundle(source=(clause,))]
        )


def test_missing_revision_is_not_fabricated_and_cannot_anchor_risk() -> None:
    orphan = _source(revision=None)
    candidate = build_trusted_state_candidate(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[_bundle(source=(orphan,))]
    )
    assert candidate is not None
    assert candidate.diagnostics.missing_clause_source_revisions == 1
    assert not candidate.state.clauses
    assert not candidate.state.risks
    assert candidate.diagnostics.rejected_unverified_risks == 1


@pytest.mark.parametrize(
    ("status", "quote"),
    [
        ("NOT_FOUND_IN_DOCUMENT", _QUOTE),
        ("SOURCE_UNAVAILABLE", _QUOTE),
        ("VERIFIED", "An obligation invented outside the physical clause"),
        ("VERIFIED", None),
    ],
)
def test_unverified_or_unlocated_model_risk_does_not_contribute_to_score(
    status: str, quote: str | None
) -> None:
    candidate = build_trusted_state_candidate(
        project_id=_PROJECT,
        tenant_id=_TENANT,
        bundles=[_bundle(risk_status=status, risk_quote=quote)],
    )
    assert candidate is not None
    assert len(candidate.state.clauses) == 1
    assert candidate.state.risks == []
    assert candidate.diagnostics.rejected_unverified_risks == 1


def test_risk_quote_appearing_in_two_physical_clauses_is_ambiguous() -> None:
    candidate = build_trusted_state_candidate(
        project_id=_PROJECT,
        tenant_id=_TENANT,
        bundles=[_bundle(source=(_source(), _source(code="8.3")))],
    )
    assert candidate is not None
    assert len(candidate.state.clauses) == 2
    assert candidate.state.risks == []


def test_duplicate_trusted_document_and_physical_clause_are_rejected() -> None:
    first = _bundle()
    with pytest.raises(ValueError, match="DUPLICATE_DOCUMENT_OR_REVISION"):
        build_trusted_state_candidate(
            project_id=_PROJECT, tenant_id=_TENANT, bundles=[first, first]
        )
    duplicated_clause = _source()
    with pytest.raises(ValueError, match="DUPLICATE_PHYSICAL_CLAUSE"):
        build_trusted_state_candidate(
            project_id=_PROJECT,
            tenant_id=_TENANT,
            bundles=[_bundle(source=(duplicated_clause, duplicated_clause))],
        )


def test_no_trusted_artifacts_never_returns_empty_approved_state() -> None:
    assert build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[]) is None


def test_partial_legacy_clause_is_dropped_but_other_revision_anchored_clause_survives() -> None:
    source = (_source(revision=None), _source(text=_OTHER, code="11.4"))
    candidate = build_trusted_state_candidate(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[_bundle(source=source)]
    )
    assert candidate is not None
    assert len(candidate.state.clauses) == 1
    assert candidate.diagnostics.missing_clause_source_revisions == 1
    assert candidate.diagnostics.rejected_unverified_risks == 1


class _FakeCanonicalRepository:
    def __init__(self, state=None):
        self.state = state
        self.saves = 0

    async def get(self, project_id, tenant_id):
        if self.state and self.state.project_id == project_id and self.state.tenant_id == tenant_id:
            return self.state
        return None

    async def insert_if_absent(self, state):
        if self.state is not None:
            return False
        self.saves += 1
        self.state = state
        return True

    async def save(self, _state):
        raise AssertionError("destructive save() is forbidden during bootstrap")


@pytest.mark.asyncio
async def test_materialization_bootstrap_writes_only_trusted_source_once() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    doc = _bundle()
    first = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[doc], repository=repo
    )
    second = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[doc], repository=repo
    )
    assert first.status == "created"
    assert second.status == "unchanged"
    assert first.trusted_revisions == 1
    assert first.clause_count == first.risk_count == 1
    assert repo.saves == 1
    assert repo.state.document_revision_ids == [_REV]


@pytest.mark.asyncio
async def test_materialization_refuses_untrusted_and_preserves_existing_state() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    with pytest.raises(ValueError, match="UNTRUSTED"):
        await materialize_trusted_state_if_absent(
            project_id=_PROJECT,
            tenant_id=_TENANT,
            bundles=[_bundle(trust="proposed")],
            repository=repo,
        )
    assert repo.saves == 0
    assert repo.state is None
    first = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[_bundle()], repository=repo
    )
    assert first.status == "created"
    old = repo.state
    revision = uuid4()
    # Same project, a new TRUSTED revision: no unsafe overwrite until a
    # versioned reconciliation is implemented and independently tested.
    fresh_clause = _source(revision=revision)
    revised = _bundle(source=(fresh_clause,))
    revised = replace(
        revised,
        artifact=revised.artifact.model_copy(update={"document_revision_id": str(revision)}),
    )
    result = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[revised], repository=repo
    )
    assert result.status == "reconciliation_required"
    assert repo.saves == 1
    assert repo.state is old


@pytest.mark.asyncio
async def test_untrusted_legacy_source_evidence_never_creates_a_canonical_row() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    outcome = await materialize_trusted_state_if_absent(
        project_id=_PROJECT,
        tenant_id=_TENANT,
        bundles=[_bundle(source=(_source(revision=None),))],
        repository=repo,
    )
    assert outcome.status == "source_provenance_unavailable"
    assert repo.saves == 0


@pytest.mark.asyncio
async def test_empty_trusted_set_does_not_create_a_project_state() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    outcome = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[], repository=repo
    )
    assert outcome.status == "no_trusted_artifacts"
    assert repo.saves == 0


@pytest.mark.asyncio
async def test_all_unverified_risks_prevent_false_clean_90_health_score() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    result = await materialize_trusted_state_if_absent(
        project_id=_PROJECT,
        tenant_id=_TENANT,
        bundles=[_bundle(risk_status="NOT_FOUND_IN_DOCUMENT")],
        repository=repo,
    )
    assert result.status == "source_provenance_unavailable"
    assert result.rejected_unverified_risks == 1
    assert repo.saves == 0
    assert repo.state is None


@pytest.mark.asyncio
async def test_zero_risks_without_clean_assessment_evidence_does_not_score_green() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    trusted = _bundle()
    trusted = replace(trusted, artifact=trusted.artifact.model_copy(update={"extracted_risks": []}))
    result = await materialize_trusted_state_if_absent(
        project_id=_PROJECT, tenant_id=_TENANT, bundles=[trusted], repository=repo
    )
    assert result.status == "source_provenance_unavailable"
    assert repo.saves == 0


@pytest.mark.asyncio
async def test_any_missing_current_trusted_document_revision_blocks_partial_project_state() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    repo = _FakeCanonicalRepository()
    first = _bundle()
    second_doc = uuid4()
    second_rev = uuid4()
    second_artifact = first.artifact.model_copy(
        update={"document_id": str(second_doc), "document_revision_id": str(second_rev)}
    )
    second = TrustedRevisionBundle(
        artifact=second_artifact,
        source_clauses=(),
        trust_state="trusted",
        lifecycle_status="active",
    )
    result = await materialize_trusted_state_if_absent(
        project_id=_PROJECT,
        tenant_id=_TENANT,
        bundles=[first, second],
        repository=repo,
    )
    assert result.status == "source_provenance_unavailable"
    assert repo.saves == 0


def test_duplicate_identical_risk_cannot_double_count_health() -> None:
    identical = _artifact().extracted_risks[0]
    artifact = _artifact().model_copy(update={"extracted_risks": [identical, identical]})
    bundle = replace(_bundle(), artifact=artifact)
    with pytest.raises(ValueError, match="DUPLICATE_RISK"):
        build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[bundle])


def test_risk_ids_and_state_are_order_invariant_for_same_trusted_revision() -> None:
    different = RiskItem(
        title="LD completion delay carve-out",
        description="Delay damages still apply on contractor caused lateness",
        category="LEGAL",
        source_quote=_QUOTE,
        source_quote_status="VERIFIED",
    )
    old_art = _artifact()
    one = replace(
        _bundle(),
        artifact=old_art.model_copy(
            update={"extracted_risks": [old_art.extracted_risks[0], different]}
        ),
    )
    two = replace(
        one,
        artifact=old_art.model_copy(
            update={"extracted_risks": [different, old_art.extracted_risks[0]]}
        ),
    )
    a = build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[one])
    b = build_trusted_state_candidate(project_id=_PROJECT, tenant_id=_TENANT, bundles=[two])
    assert a is not None and b is not None
    assert a.state.model_dump(mode="json") == b.state.model_dump(mode="json")


@pytest.mark.asyncio
async def test_bootstrap_requires_atomic_repository_insert_instead_of_save() -> None:
    from src.project_state.application.materialize_trusted_state import (
        materialize_trusted_state_if_absent,
    )

    class NoAtomicRepo:
        async def get(self, *_args):
            return None

        async def save(self, _state):
            raise AssertionError("Must never use destructive save")

    with pytest.raises(RuntimeError, match="ATOMIC_INSERT_REQUIRED"):
        await materialize_trusted_state_if_absent(
            project_id=_PROJECT, tenant_id=_TENANT, bundles=[_bundle()], repository=NoAtomicRepo()
        )
