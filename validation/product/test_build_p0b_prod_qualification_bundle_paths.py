from pathlib import Path

import pytest

from validation.product.build_p0b_prod_qualification_bundle import (
    BundleBuildError,
    _resolve_bundle_output,
    _require_full_sha,
    _resolve_run_json,
    _resolve_verifier_json,
)


def test_bundle_input_paths_are_exact_canonical_artifacts(tmp_path: Path) -> None:
    run_path = tmp_path / "apps/web/playwright/.prod-acceptance/run.json"
    run_path.parent.mkdir(parents=True)
    run_path.write_text("{}", encoding="utf-8")

    verifier_path = (
        tmp_path / "evidence/product-qualification/runtime/verifier.json"
    )
    verifier_path.parent.mkdir(parents=True)
    verifier_path.write_text("{}", encoding="utf-8")

    assert _resolve_run_json(run_path, repo_root=tmp_path) == run_path
    assert _resolve_verifier_json(verifier_path, repo_root=tmp_path) == verifier_path

    with pytest.raises(BundleBuildError, match="canonical browser run evidence"):
        _resolve_run_json(tmp_path / "outside.json", repo_root=tmp_path)

    with pytest.raises(BundleBuildError, match="canonical verifier evidence"):
        _resolve_verifier_json(tmp_path / "outside.json", repo_root=tmp_path)


def test_bundle_output_stays_under_qualification_evidence_root(tmp_path: Path) -> None:
    output_root = tmp_path / "evidence/product-qualification"
    output_root.mkdir(parents=True)
    allowed = output_root / "p0b-prod-gh-123-1.yaml"

    assert _resolve_bundle_output(allowed, repo_root=tmp_path) == allowed

    with pytest.raises(BundleBuildError, match="canonical qualification output"):
        _resolve_bundle_output(tmp_path / "outside.yaml", repo_root=tmp_path)

    with pytest.raises(BundleBuildError, match="canonical qualification output"):
        _resolve_bundle_output(
            output_root / "../outside.yaml",
            repo_root=tmp_path,
        )


def test_control_commit_rejects_ref_syntax_and_short_shas() -> None:
    assert _require_full_sha("a" * 40, "control commit") == "a" * 40

    for unsafe in ("main", "abc123", "a" * 40 + ":other", "--help"):
        with pytest.raises(BundleBuildError, match="40-character Git SHA"):
            _require_full_sha(unsafe, "control commit")
