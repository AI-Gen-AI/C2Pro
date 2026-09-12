"""TDD tests for core.provenance_guard (G2 continuation, MASTER Decision A).

core.reconciler.reconcile_result and core.legacy_closure.reconcile_legacy_closure
both rewrite work-queue.yaml via yaml.safe_load -> yaml.dump, which does not
round-trip comments. Some queue items carry hand-written "DEV-DEBT" provenance
comments (e.g. C2PRO-DEV-05, C2PRO-DEV-13) recording why a work_id exists.
This guard refuses to let a reconciliation write silently discard that meaning
unless it is already captured in a schema-safe .c2pro/evidence/<id>.yaml file.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.provenance_guard import (
    ProvenanceLossError,
    assert_no_uncovered_comment_loss,
    extract_item_comments,
    find_uncovered_comment_loss,
    has_evidence_coverage,
)

SAMPLE_QUEUE_TEXT = """\
schema: c2pro-work-queue-v1
items:
  - work_id: C2PRO-DEV-03
    status: ready
  # DEV-DEBT (registered 2026-08-28): extend the work-envelope schema so
  # product slices get machine-validated envelopes without abusing the
  # control-plane namespace.
  - work_id: C2PRO-DEV-05
    status: ready
"""

SAMPLE_QUEUE_TEXT_AFTER_STRIP = """\
schema: c2pro-work-queue-v1
items:
  - work_id: C2PRO-DEV-03
    status: ready
  - work_id: C2PRO-DEV-05
    status: ready
"""


def test_extract_item_comments_associates_preceding_comment_with_work_id():
    comments = extract_item_comments(SAMPLE_QUEUE_TEXT)
    assert comments["C2PRO-DEV-03"] == ""
    assert "DEV-DEBT (registered 2026-08-28)" in comments["C2PRO-DEV-05"]
    assert "control-plane namespace" in comments["C2PRO-DEV-05"]


def test_has_evidence_coverage_false_when_file_absent(tmp_path):
    assert has_evidence_coverage("C2PRO-DEV-05", tmp_path / "evidence") is False


def test_has_evidence_coverage_false_when_no_summary(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    with open(evidence_dir / "C2PRO-DEV-05.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "schema": "c2pro-evidence-reference-v1",
                "schema_version": 1,
                "work_id": "C2PRO-DEV-05",
                "status": "collecting",
                "references": [{"kind": "git_commit", "locator": "abc123", "immutable": True}],
            },
            f,
        )
    assert has_evidence_coverage("C2PRO-DEV-05", evidence_dir) is False


def test_has_evidence_coverage_true_when_audit_summary_present(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    with open(evidence_dir / "C2PRO-DEV-05.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "schema": "c2pro-evidence-reference-v1",
                "schema_version": 1,
                "work_id": "C2PRO-DEV-05",
                "status": "collecting",
                "references": [
                    {
                        "kind": "audit",
                        "locator": "2f1443e7fa829a3f9bb84ec25d4192a1e8f646bb",
                        "immutable": True,
                        "summary": "DEV-DEBT registration text preserved here.",
                    }
                ],
            },
            f,
        )
    assert has_evidence_coverage("C2PRO-DEV-05", evidence_dir) is True


def test_find_uncovered_comment_loss_detects_missing_coverage(tmp_path):
    lost = find_uncovered_comment_loss(
        SAMPLE_QUEUE_TEXT, SAMPLE_QUEUE_TEXT_AFTER_STRIP, tmp_path / "evidence"
    )
    assert lost == ["C2PRO-DEV-05"]


def test_find_uncovered_comment_loss_empty_when_comment_preserved(tmp_path):
    lost = find_uncovered_comment_loss(SAMPLE_QUEUE_TEXT, SAMPLE_QUEUE_TEXT, tmp_path / "evidence")
    assert lost == []


def test_find_uncovered_comment_loss_empty_when_evidence_exists(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    with open(evidence_dir / "C2PRO-DEV-05.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "schema": "c2pro-evidence-reference-v1",
                "schema_version": 1,
                "work_id": "C2PRO-DEV-05",
                "status": "collecting",
                "references": [
                    {
                        "kind": "audit",
                        "locator": "2f1443e7fa829a3f9bb84ec25d4192a1e8f646bb",
                        "immutable": True,
                        "summary": "preserved",
                    }
                ],
            },
            f,
        )
    lost = find_uncovered_comment_loss(SAMPLE_QUEUE_TEXT, SAMPLE_QUEUE_TEXT_AFTER_STRIP, evidence_dir)
    assert lost == []


def test_assert_no_uncovered_comment_loss_raises_with_work_id_named(tmp_path):
    with pytest.raises(ProvenanceLossError, match="C2PRO-DEV-05"):
        assert_no_uncovered_comment_loss(
            SAMPLE_QUEUE_TEXT, SAMPLE_QUEUE_TEXT_AFTER_STRIP, tmp_path / "evidence"
        )


def test_assert_no_uncovered_comment_loss_passes_once_covered(tmp_path):
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    with open(evidence_dir / "C2PRO-DEV-05.yaml", "w", encoding="utf-8") as f:
        yaml.dump(
            {
                "schema": "c2pro-evidence-reference-v1",
                "schema_version": 1,
                "work_id": "C2PRO-DEV-05",
                "status": "collecting",
                "references": [
                    {"kind": "audit", "locator": "2f1443e7", "immutable": True, "summary": "preserved"}
                ],
            },
            f,
        )
    assert_no_uncovered_comment_loss(SAMPLE_QUEUE_TEXT, SAMPLE_QUEUE_TEXT_AFTER_STRIP, evidence_dir)


# ---------------------------------------------------------------------------
# Real-repository regression: the two ACTUAL debts this guard was built for
# must stay covered. This reads the genuine .c2pro/control/work-queue.yaml
# and .c2pro/evidence/ from this repository -- no fixture, no fabrication.
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_WORK_QUEUE = _REPO_ROOT / ".c2pro" / "control" / "work-queue.yaml"
_REAL_EVIDENCE_DIR = _REPO_ROOT / ".c2pro" / "evidence"


def test_real_dev05_and_dev13_provenance_is_covered():
    real_text = _REAL_WORK_QUEUE.read_text(encoding="utf-8")
    # Simulate the comment-stripping a real reconciliation write performs.
    stripped_text = yaml.dump(yaml.safe_load(real_text), sort_keys=False)
    lost = find_uncovered_comment_loss(real_text, stripped_text, _REAL_EVIDENCE_DIR)
    assert lost == [], (
        f"Real work-queue.yaml provenance comments for {lost} have no "
        ".c2pro/evidence/<id>.yaml coverage -- a reconciliation write would "
        "silently destroy them."
    )
