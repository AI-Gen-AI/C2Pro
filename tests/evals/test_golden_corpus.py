"""Regression tests for the 15-bundle golden corpus.

Locks in the fixed corpus size, dimension coverage, schema validity,
and the CI contract of ``evals/run_evals.py``.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EVALS_DIR = REPO_ROOT / "evals"
CORPUS_DIR = EVALS_DIR / "golden_corpus"
BUNDLES_DIR = CORPUS_DIR / "bundles"
MANIFEST_PATH = CORPUS_DIR / "manifest.yaml"

# Make ``evals/`` importable as a package root for ``golden_corpus.schema``.
sys.path.insert(0, str(EVALS_DIR))

from golden_corpus import schema as corpus_schema  # noqa: E402

BUNDLE_ID_RE = re.compile(r"^BUNDLE-\d{3}$")


def _load_manifest() -> corpus_schema.Manifest:
    import yaml

    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))
    return corpus_schema.Manifest.model_validate(data)


def _load_bundle(bundle_id: str) -> corpus_schema.Bundle:
    raw = json.loads((BUNDLES_DIR / f"{bundle_id}.json").read_text(encoding="utf-8"))
    return corpus_schema.Bundle.model_validate(raw)


def test_manifest_lists_exactly_15_bundles() -> None:
    manifest = _load_manifest()
    assert manifest.total_bundles == 15
    assert len(manifest.bundles) == 15


def test_every_manifest_entry_has_a_bundle_file() -> None:
    manifest = _load_manifest()
    for entry in manifest.bundles:
        bundle_path = BUNDLES_DIR / f"{entry.id}.json"
        assert bundle_path.exists(), f"Missing bundle file for {entry.id}"


def test_bundle_ids_are_sequential_and_unique() -> None:
    manifest = _load_manifest()
    ids = [entry.id for entry in manifest.bundles]
    assert len(set(ids)) == len(ids), "duplicate bundle ids"
    assert ids == [f"BUNDLE-{i:03d}" for i in range(1, 16)]


def test_every_bundle_validates_against_schema() -> None:
    manifest = _load_manifest()
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        assert bundle.bundle_id == entry.id
        assert bundle.synthetic is True


def test_all_six_dimensions_are_covered_across_corpus() -> None:
    manifest = _load_manifest()
    dimensions: set[str] = set()
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        dimensions.update(d.value for d in bundle.dimensions)
    assert dimensions == {"Legal", "Quality", "Scope", "Schedule", "Cost", "Technical"}


def test_cross_dimensional_bundles_exist() -> None:
    manifest = _load_manifest()
    multi = [e for e in manifest.bundles if len(e.dimensions) >= 2]
    assert len(multi) >= 4


def test_aggregate_expected_issue_count_meets_minimum() -> None:
    manifest = _load_manifest()
    total = 0
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        assert len(bundle.expected_issues) >= 1
        total += len(bundle.expected_issues)
    assert total >= 20


def test_every_bundle_has_contract_schedule_budget() -> None:
    manifest = _load_manifest()
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        kinds = {doc.kind for doc in bundle.documents}
        assert {"contract", "schedule", "budget"}.issubset(kinds), (
            f"{entry.id} missing core document kinds; has {kinds}"
        )


def test_bundle_and_manifest_dimensions_agree() -> None:
    manifest = _load_manifest()
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        assert {d.value for d in bundle.dimensions} == {
            d.value for d in entry.dimensions
        }
        assert bundle.difficulty.value == entry.difficulty.value
        assert len(bundle.expected_issues) == entry.expected_issue_count


def test_run_evals_ci_mode_exits_zero_on_clean_corpus(tmp_path: Path) -> None:
    output_dir = tmp_path / "results"
    result = subprocess.run(  # noqa: S603 - trusted local script invocation
        [
            sys.executable,
            str(EVALS_DIR / "run_evals.py"),
            "--corpus",
            "--ci",
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    json_path = output_dir / "corpus_results.json"
    xml_path = output_dir / "corpus_results.xml"
    assert json_path.exists()
    assert xml_path.exists()

    report = json.loads(json_path.read_text(encoding="utf-8"))
    assert report["total_bundles"] == 15
    assert report["failed_bundles"] == 0
    assert set(report["dimensions_covered"]) == {
        "Legal",
        "Quality",
        "Scope",
        "Schedule",
        "Cost",
        "Technical",
    }


def test_run_evals_ci_mode_reports_missing_bundle(tmp_path: Path) -> None:
    """If a bundle file is missing the CLI must exit with code 2."""
    import shutil

    corpus_copy = tmp_path / "golden_corpus"
    shutil.copytree(CORPUS_DIR, corpus_copy)
    victim = corpus_copy / "bundles" / "BUNDLE-007.json"
    victim.unlink()

    script = tmp_path / "run_evals_shim.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(EVALS_DIR)!r})\n"
        "import run_evals\n"
        f"run_evals.CORPUS_DIR = __import__('pathlib').Path({str(corpus_copy)!r})\n"
        "run_evals.BUNDLES_DIR = run_evals.CORPUS_DIR / 'bundles'\n"
        "run_evals.MANIFEST_PATH = run_evals.CORPUS_DIR / 'manifest.yaml'\n"
        "sys.exit(run_evals.main(['--corpus', '--ci', '--output', "
        f"{str(tmp_path / 'results')!r}]))\n",
        encoding="utf-8",
    )
    result = subprocess.run(  # noqa: S603 - trusted local script
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert "BUNDLE-007" in result.stdout + result.stderr


def test_every_rule_id_matches_expected_pattern() -> None:
    manifest = _load_manifest()
    pattern = re.compile(r"^[A-Z]{2,10}-\d{1,4}$")
    for entry in manifest.bundles:
        bundle = _load_bundle(entry.id)
        for issue in bundle.expected_issues:
            assert pattern.match(issue.rule_id), (
                f"{bundle.bundle_id} has invalid rule_id {issue.rule_id!r}"
            )
