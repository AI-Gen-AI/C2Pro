from pathlib import Path

import pytest

from validation.product.build_p0b_prod_qualification_bundle import (
    BundleBuildError,
    _bundle_output,
    _require_full_sha,
    _require_hitl_alignment,
    _run_json,
    _sha256,
    _verifier_json,
)


def test_bundle_inputs_are_fixed_canonical_artifacts(tmp_path: Path) -> None:
    run_path = tmp_path / "apps/web/playwright/.prod-acceptance/run.json"
    run_path.parent.mkdir(parents=True)
    run_path.write_text("{}", encoding="utf-8")

    verifier_path = (
        tmp_path / "evidence/product-qualification/runtime/verifier.json"
    )
    verifier_path.parent.mkdir(parents=True)
    verifier_path.write_text("{}", encoding="utf-8")

    assert _run_json(repo_root=tmp_path) == run_path
    assert _verifier_json(repo_root=tmp_path) == verifier_path


def test_bundle_output_is_derived_from_github_run_identity(tmp_path: Path) -> None:
    expected = (
        tmp_path
        / "evidence/product-qualification/p0b-prod-gh-123-2.yaml"
    )
    assert _bundle_output(123, 2, repo_root=tmp_path) == expected

    for run_id, attempt in (
        (0, 1),
        (1, 0),
    ):
        with pytest.raises(BundleBuildError, match="positive integer"):
            _bundle_output(run_id, attempt, repo_root=tmp_path)


def test_control_commit_rejects_ref_syntax_and_short_shas() -> None:
    assert _require_full_sha("a" * 40, "control commit") == "a" * 40

    for unsafe in ("main", "abc123", "a" * 40 + ":other", "--help"):
        with pytest.raises(BundleBuildError, match="40-character Git SHA"):
            _require_full_sha(unsafe, "control commit")


def test_sha256_hashes_evidence_bytes(tmp_path: Path) -> None:
    artifact = tmp_path / "evidence.json"
    artifact.write_bytes(b"c2pro-evidence")

    assert (
        _sha256(artifact)
        == "b51e697e6ad7dc2485112282cac26c9e22bc81e3af450b5845841c7505053ddd"
    )


def test_hitl_alignment_requires_same_dedicated_project_and_review() -> None:
    run = {
        "hitl_exercised": True,
        "hitl_project_id": "project-hitl",
        "hitl_document_id": "document-hitl",
        "review_item_id": "review-hitl",
    }
    identifiers = {
        "hitl_project_id": "project-hitl",
        "hitl_document_id": "document-hitl",
        "hitl_review_item_id": "review-hitl",
    }

    assert _require_hitl_alignment(run, identifiers) == {
        "hitl_project_id": "project-hitl",
        "hitl_document_id": "document-hitl",
        "review_item_id": "review-hitl",
    }

    for key, bad in (
        ("hitl_project_id", "other-project"),
        ("hitl_document_id", "other-document"),
        ("hitl_review_item_id", "other-review"),
    ):
        mismatched = dict(identifiers)
        mismatched[key] = bad
        with pytest.raises(BundleBuildError, match="HITL"):
            _require_hitl_alignment(run, mismatched)
