"""PC-2b.1 (#920): evidence, qualification, proposal and run contracts.

TS-UW-PC2B1-CONTRACT-001. Pure domain contracts: tenant/project explicit at every boundary, the
canonical source location never derived from anonymised model text, every qualification dimension
reported exactly once, no PASS-by-absence, no governance fields in anything a model produces.
"""

from __future__ import annotations

import inspect
from uuid import uuid4

import pytest
from pydantic import ValidationError

from src.evidence.domain.models import LocatorQuality
from src.wbs.intelligence.contracts.evidence import (
    AUTHORITY_BY_INPUT_CLASS,
    CanonicalSourceRef,
    EvidenceAuthority,
    EvidenceManifest,
    InputClass,
    ManifestItem,
    ModelEvidenceCitation,
    ModelVisibleExcerpt,
)
from src.wbs.intelligence.contracts.proposal import (
    PROPOSAL_CONTRACT_VERSION,
    ModelProposalItem,
    ModelResponseEnvelope,
    ProposalOperation,
)
from src.wbs.intelligence.contracts.qualification import (
    QUALIFICATION_VOCAB_VERSION,
    SCHEDULE_EVIDENCE_UNAVAILABLE,
    AvailabilityContext,
    DimensionResult,
    NotEvaluatedReason,
    QualificationDimension,
    QualificationMethod,
    QualificationReport,
    QualificationStatus,
    availability,
)
from src.wbs.intelligence.contracts.run import (
    REUSABLE_OUTCOMES,
    IntelligenceMode,
    ModelFingerprint,
    RunOutcome,
    RunScope,
    RunTarget,
    TargetKind,
    idempotency_key,
)

DIGEST = "sha256:" + "a" * 64
HEX = "b" * 64


def _source(**overrides: object) -> CanonicalSourceRef:
    fields: dict[str, object] = {"document_id": uuid4(), "revision_id": uuid4(), "blob_hash": HEX, "page": 3,
                                 "char_start": 120, "char_end": 180, "locator_quality": LocatorQuality.EXACT}
    fields.update(overrides)
    return CanonicalSourceRef(**fields)  # type: ignore[arg-type]


def _manifest(text: str = "The Contractor shall install 12 km of MV cable.", **scope: object) -> EvidenceManifest:
    return EvidenceManifest(
        tenant_id=scope.get("tenant_id", uuid4()), project_id=scope.get("project_id", uuid4()),  # type: ignore[arg-type]
        items=(ManifestItem(excerpt_id="E1", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE, canonical_source=_source(),
                            model_visible=ModelVisibleExcerpt.of(text, transform="pii-anonymizer/v1")),),
    )


# --------------------------------------------------------------------------- evidence: canonical vs model-visible
def test_the_canonical_locator_is_kept_apart_from_the_anonymised_model_text() -> None:
    original_span = (120, 180)
    source = _source(char_start=original_span[0], char_end=original_span[1])
    anonymised = ModelVisibleExcerpt.of("[PERSON_1] shall install 12 km of MV cable.", transform="pii-anonymizer/v1")
    item = ManifestItem(excerpt_id="E1", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE,
                        canonical_source=source, model_visible=anonymised)
    # anonymisation changed the length; the canonical span is still the ORIGINAL revision's span
    assert len(anonymised.text) != original_span[1] - original_span[0]
    assert (item.canonical_source.char_start, item.canonical_source.char_end) == original_span  # type: ignore[union-attr]
    assert item.model_visible.text_digest.startswith("sha256:")
    assert item.model_visible.anonymised is True


def test_a_model_citation_cannot_carry_source_offsets_or_documents() -> None:
    ModelEvidenceCitation(excerpt_id="E1", basis="DIRECT", quote="install 12 km of MV cable")
    for forbidden in ({"char_start": 1}, {"page": 3}, {"document_id": str(uuid4())}, {"revision_id": str(uuid4())},
                      {"authority": "TRUSTED"}):
        with pytest.raises(ValidationError):
            ModelEvidenceCitation(excerpt_id="E1", basis="DIRECT", quote="x", **forbidden)  # type: ignore[arg-type]


def test_partial_offsets_are_refused() -> None:
    with pytest.raises(ValidationError):
        _source(char_start=10, char_end=None)
    with pytest.raises(ValidationError):
        _source(char_start=20, char_end=10)


def test_authority_comes_from_the_input_class_never_from_the_model() -> None:
    assert AUTHORITY_BY_INPUT_CLASS[InputClass.TRUSTED_PROJECT_EVIDENCE] is EvidenceAuthority.TRUSTED
    assert AUTHORITY_BY_INPUT_CLASS[InputClass.PROPOSED_EVIDENCE] is EvidenceAuthority.PROPOSED
    assert AUTHORITY_BY_INPUT_CLASS[InputClass.ADVISORY_EVIDENCE] is EvidenceAuthority.ADVISORY
    assert AUTHORITY_BY_INPUT_CLASS[InputClass.HUMAN_PROVIDED_IMPORT] is EvidenceAuthority.HUMAN_IMPORT
    assert set(AUTHORITY_BY_INPUT_CLASS) == set(InputClass)


def test_user_context_has_no_canonical_document_but_documents_must() -> None:
    ManifestItem(excerpt_id="U1", input_class=InputClass.USER_CONTEXT, canonical_source=None,
                 model_visible=ModelVisibleExcerpt.of("Focus on the substation.", transform="none"))
    with pytest.raises(ValidationError):
        ManifestItem(excerpt_id="E9", input_class=InputClass.TRUSTED_PROJECT_EVIDENCE, canonical_source=None,
                     model_visible=ModelVisibleExcerpt.of("x", transform="none"))


def test_the_manifest_is_tenant_and_project_explicit_and_digested() -> None:
    with pytest.raises(ValidationError):
        EvidenceManifest(items=())  # type: ignore[call-arg]
    tenant, project = uuid4(), uuid4()
    a = _manifest(tenant_id=tenant, project_id=project)
    b = _manifest(tenant_id=tenant, project_id=project)
    assert a.evidence_set_digest != b.evidence_set_digest  # different random canonical sources
    same = EvidenceManifest(tenant_id=tenant, project_id=project, items=a.items)
    assert same.evidence_set_digest == a.evidence_set_digest
    changed = EvidenceManifest(tenant_id=tenant, project_id=project, items=(
        a.items[0].model_copy(update={"model_visible": ModelVisibleExcerpt.of("other", transform="none")}),))
    assert changed.evidence_set_digest != a.evidence_set_digest
    with pytest.raises(ValidationError, match="excerpt"):
        EvidenceManifest(tenant_id=tenant, project_id=project, items=a.items + a.items)


# --------------------------------------------------------------------------- qualification
def test_the_v1_vocabulary_has_exactly_nineteen_dimensions() -> None:
    assert QUALIFICATION_VOCAB_VERSION == "wbs-qualification/v1"
    assert len(QualificationDimension) == 19
    assert {s.value for s in QualificationStatus} == {"SUPPORTED", "GAP", "WARNING", "NOT_EVALUATED", "AMBIGUOUS"}


def test_alignment_dimensions_are_not_evaluated_with_honest_reasons() -> None:
    matrix = availability(AvailabilityContext(has_trusted_contract=True, has_trusted_scope_evidence=True,
                                              ai_qualification_run=True))
    assert matrix[QualificationDimension.SCHEDULE_MAPPING_COVERAGE] is NotEvaluatedReason.GOVERNED_SCHEDULE_UNAVAILABLE
    assert matrix[QualificationDimension.BUDGET_COST_MAPPING_COVERAGE] is NotEvaluatedReason.GOVERNED_COST_MODEL_UNAVAILABLE
    assert matrix[QualificationDimension.PROCUREMENT_BOM_COVERAGE] is (
        NotEvaluatedReason.GOVERNED_PROCUREMENT_MAPPING_UNAVAILABLE)
    assert matrix[QualificationDimension.RESPONSIBILITY_COVERAGE] is NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE
    assert matrix[QualificationDimension.CONTRACT_OBLIGATION_COVERAGE] is NotEvaluatedReason.ALIGNMENT_ENGINE_UNAVAILABLE
    assert matrix[QualificationDimension.SCOPE_COVERAGE] is None
    assert SCHEDULE_EVIDENCE_UNAVAILABLE == "Governed Schedule evidence unavailable"


def test_ai_dimensions_need_their_evidence_and_an_ai_run() -> None:
    no_ai = availability(AvailabilityContext(has_trusted_contract=True, has_trusted_scope_evidence=True,
                                             ai_qualification_run=False))
    assert no_ai[QualificationDimension.SCOPE_COVERAGE] is NotEvaluatedReason.AI_QUALIFICATION_NOT_RUN
    assert no_ai[QualificationDimension.DUPLICATE_SCOPE] is None  # deterministic part still evaluates
    no_contract = availability(AvailabilityContext(has_trusted_contract=False, has_trusted_scope_evidence=False,
                                                   ai_qualification_run=True))
    assert no_contract[QualificationDimension.MISSING_CONTRACT_SCOPE] is NotEvaluatedReason.NO_TRUSTED_CONTRACT
    assert no_contract[QualificationDimension.SCOPE_COVERAGE] is NotEvaluatedReason.NO_TRUSTED_SCOPE_EVIDENCE


def _result(dim: QualificationDimension, status: QualificationStatus, **extra: object) -> DimensionResult:
    fields: dict[str, object] = {"dimension": dim, "status": status, "method": QualificationMethod.DETERMINISTIC,
                                 "summary": "s"}
    if status is QualificationStatus.NOT_EVALUATED:
        fields["reason_code"] = NotEvaluatedReason.INSUFFICIENT_EVIDENCE
    fields.update(extra)
    return DimensionResult(**fields)  # type: ignore[arg-type]


def test_a_report_carries_every_dimension_exactly_once() -> None:
    full = tuple(_result(d, QualificationStatus.NOT_EVALUATED) for d in QualificationDimension)
    QualificationReport(results=full)
    with pytest.raises(ValidationError, match="exactly once"):
        QualificationReport(results=full[:-1])
    with pytest.raises(ValidationError, match="exactly once"):
        QualificationReport(results=full + full[:1])


def test_not_evaluated_needs_a_reason_and_only_it_has_one() -> None:
    with pytest.raises(ValidationError):
        DimensionResult(dimension=QualificationDimension.GRANULARITY, status=QualificationStatus.NOT_EVALUATED,
                        method=QualificationMethod.DETERMINISTIC, summary="s")
    with pytest.raises(ValidationError):
        _result(QualificationDimension.GRANULARITY, QualificationStatus.GAP,
                reason_code=NotEvaluatedReason.INSUFFICIENT_EVIDENCE)


def test_an_ai_supported_result_without_evidence_is_refused() -> None:
    """No PASS-by-absence: an AI 'SUPPORTED' must cite evidence."""
    with pytest.raises(ValidationError, match="evidence"):
        _result(QualificationDimension.SCOPE_COVERAGE, QualificationStatus.SUPPORTED, method=QualificationMethod.AI)


# --------------------------------------------------------------------------- proposal contract
def test_adopt_legacy_is_never_a_proposal_operation() -> None:
    assert PROPOSAL_CONTRACT_VERSION == "wbs-proposal/v1"
    assert "ADOPT_LEGACY_NODE" not in {op.value for op in ProposalOperation}
    with pytest.raises(ValidationError):
        ModelProposalItem.model_validate({"ref": "p1", "operation": "ADOPT_LEGACY_NODE", "rationale": "r",
                                          "confidence_pct": 50})


@pytest.mark.parametrize("label", [str(uuid4()), "a" * 40, "Upper", "1abc", "with space"])
def test_local_labels_can_never_look_like_canonical_ids(label: str) -> None:
    with pytest.raises(ValidationError):
        ModelProposalItem.model_validate({"ref": "p1", "operation": "ADD_NODE", "creates_label": label,
                                          "spec": {"name": "x"}, "rationale": "r", "confidence_pct": 50})


@pytest.mark.parametrize("field", ["approver", "approved_by", "submit", "status", "profile_pins", "actor",
                                   "tools", "tool_calls", "change_set_id", "created_by_kind"])
def test_governance_like_fields_are_rejected_in_model_output(field: str) -> None:
    envelope = {"contract_version": PROPOSAL_CONTRACT_VERSION, "outcome": "COMPLETE",
                "qualification": [], "findings": [], "proposals": [], "uncovered": []}
    ModelResponseEnvelope.model_validate(envelope)
    with pytest.raises(ValidationError):
        ModelResponseEnvelope.model_validate({**envelope, field: "x"})
    item = {"ref": "p1", "operation": "ADD_NODE", "creates_label": "n1", "spec": {"name": "x"}, "rationale": "r",
            "confidence_pct": 50}
    with pytest.raises(ValidationError):
        ModelProposalItem.model_validate({**item, field: "x"})


def test_confidence_is_an_integer_percentage() -> None:
    base = {"ref": "p1", "operation": "ADD_NODE", "creates_label": "n1", "spec": {"name": "x"}, "rationale": "r"}
    for bad in (101, -1, 0.5):
        with pytest.raises(ValidationError):
            ModelProposalItem.model_validate({**base, "confidence_pct": bad})


# --------------------------------------------------------------------------- run + idempotency
def _key(**overrides: object) -> str:
    tenant, project = uuid4(), uuid4()
    fields: dict[str, object] = {
        "scope": RunScope(tenant_id=tenant, project_id=project),
        "mode": IntelligenceMode.REVIEW_OPTIMIZE,
        "target": RunTarget(kind=TargetKind.BASELINE, target_id=uuid4(), digest=DIGEST),
        "evidence_set_digest": DIGEST,
        "profile_digests": ["sha256:" + "c" * 64],
        "prompt_templates": [{"task": "wbs_review", "version": "1.0", "digest": DIGEST}],
        "model": ModelFingerprint(provider="anthropic", model="m", routing_tier="standard", temperature_milli=0,
                                  max_tokens=4000),
        "orchestration_version": "wbs-orchestration/v1",
    }
    fields.update(overrides)
    return idempotency_key(**fields)  # type: ignore[arg-type]


def test_the_idempotency_key_is_deterministic_and_input_sensitive() -> None:
    fields: dict[str, object] = {
        "scope": RunScope(tenant_id=uuid4(), project_id=uuid4()),
        "target": RunTarget(kind=TargetKind.BASELINE, target_id=uuid4(), digest=DIGEST),
    }
    first = _key(**fields)
    assert first == _key(**fields)
    assert first.startswith("sha256:")
    for change in ({"evidence_set_digest": "sha256:" + "d" * 64}, {"profile_digests": []},
                   {"orchestration_version": "wbs-orchestration/v2"}, {"rerun_nonce": "human-rerun-1"},
                   {"mode": IntelligenceMode.IMPORT_REVIEW}):
        assert _key(**fields, **change) != first  # type: ignore[arg-type]


def test_the_key_never_crosses_tenants() -> None:
    target = RunTarget(kind=TargetKind.BASELINE, target_id=uuid4(), digest=DIGEST)
    project = uuid4()
    assert _key(scope=RunScope(tenant_id=uuid4(), project_id=project), target=target) != _key(
        scope=RunScope(tenant_id=uuid4(), project_id=project), target=target)


def test_the_key_has_no_volatile_inputs_and_requires_the_scope() -> None:
    params = inspect.signature(idempotency_key).parameters
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params.values())
    assert not {"created_at", "now", "timestamp", "requested_at"} & set(params)
    assert params["scope"].default is inspect.Parameter.empty
    with pytest.raises(ValidationError):
        RunScope(tenant_id=None, project_id=uuid4())  # type: ignore[arg-type]


def test_targets_bind_the_exact_identity() -> None:
    RunTarget(kind=TargetKind.NONE)
    with pytest.raises(ValidationError):
        RunTarget(kind=TargetKind.NONE, digest=DIGEST)
    with pytest.raises(ValidationError):
        RunTarget(kind=TargetKind.BASELINE, target_id=uuid4())  # no digest
    with pytest.raises(ValidationError):
        RunTarget(kind=TargetKind.CANDIDATE, target_id=uuid4(), digest=DIGEST)  # no revision
    RunTarget(kind=TargetKind.CANDIDATE, target_id=uuid4(), digest=DIGEST, change_set_revision=3)


def test_only_complete_partial_and_abstaining_runs_are_reusable() -> None:
    assert {RunOutcome.COMPLETE, RunOutcome.PARTIAL_PROPOSAL, RunOutcome.INSUFFICIENT_EVIDENCE} == REUSABLE_OUTCOMES
    assert RunOutcome.FAILED not in REUSABLE_OUTCOMES and RunOutcome.CANCELLED not in REUSABLE_OUTCOMES
