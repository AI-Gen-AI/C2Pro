from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "prod-p0c-recovery.yml"
SPEC = ROOT / "apps" / "web" / "src" / "tests" / "e2e" / "prod-acceptance" / "686-p0c-recovery-production.spec.ts"
PREFLIGHT = ROOT / "apps" / "api" / "scripts" / "verify_p0c_prod_recovery.py"


def test_recovery_workflow_is_owner_only_and_bounded() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "github.event.issue.number == 686" in source
    assert "github.event.comment.user.login == github.repository_owner" in source
    assert "github.triggering_actor == github.repository_owner" in source
    assert "startsWith(github.event.comment.body, 'RECOVER-ISSUE-686 ')" in source
    assert (
        'r"source_revision_id=(?P<source_revision_id>[0-9a-fA-F-]{36}) "'
        in source
    )
    assert (
        'r"target_revision_id=(?P<target_revision_id>[0-9a-fA-F-]{36}) "'
        in source
    )
    assert source.index("target_revision_id=(?P<target_revision_id>") < source.index(
        "staged_clear=(?P<staged_clear>true)"
    )
    assert "verify_p0c_prod_recovery.py" in source
    assert "686-p0c-recovery-production.spec.ts" in source
    assert "verify_p0c_prod_journey.py" in source
    assert "build_p0c_prod_qualification_bundle.py" in source
    assert "validate_qualification_evidence.py" in source


def test_recovery_journey_reprocesses_existing_b_instead_of_uploading_b() -> None:
    source = SPEC.read_text(encoding="utf-8")
    assert 'PROD_P0C_TARGET_REVISION_ID' in source
    assert 'name: /^Retry processing /' in source
    assert 'whatChanged.targetRevisionId).toBe(targetRevisionId)' in source
    # Contract B is reference evidence only; the recovery must not upload it as a new revision.
    assert "filePath: contractBPdfPath(revisionManifest)" not in source
    assert "uploadNewVersionThroughUi" in source  # reserved for semantic no-change C


def test_recovery_preflight_is_read_only_and_exactly_two_revisions() -> None:
    source = PREFLIGHT.read_text(encoding="utf-8")
    assert "SET TRANSACTION READ ONLY" in source
    assert "expected exactly A+B revisions" in source
    assert "document must be error before recovery" in source
    assert "A→B revision.changed must not pre-exist" in source
    assert "FROM document_processing_operations" in source
    assert "processing authority is not pinned to the expected failed B state" in source
    assert "owner_token" not in source
    assert "fencing_token" not in source
    assert "last_error" not in source
    assert "payload->>'document_id'=:document_text" in source
    assert "source_revision_id'=:source_text" in source
    assert "target_revision_id'=:target_text" in source
    spec = SPEC.read_text(encoding="utf-8")
    assert 'name: /^Retry processing /' in spec
    assert "await expect(retry).toBeVisible" in spec
    assert "CAST(:document AS text)" not in source
    assert "CAST(:source AS text)" not in source
    assert "CAST(:target AS text)" not in source
